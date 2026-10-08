"""The only path to Gemini.

Protects the free-tier quota during a live demo:
- disk cache keyed by (agent, model, prompt, images) so repeated views cost nothing
- concurrency cap (worker pool) + requests-per-minute sliding window
- priority queue so a judge's live request jumps ahead of background prewarming
- retry with exponential backoff + jitter on 429 / 5xx
- callers get a timeout; the job still finishes in the background and fills the cache
"""
from __future__ import annotations

import asyncio
import hashlib
import itertools
import logging
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel

from . import trace
from .config import settings

log = logging.getLogger("axon.gateway")

LIVE, PREWARM, BACKGROUND = 0, 1, 2
_PRIORITY = {LIVE: 'live', PREWARM: 'prewarm', BACKGROUND: 'background'}
T = TypeVar("T", bound=BaseModel)


class AIUnavailable(Exception):
    """Gemini is disabled, unconfigured, timed out or failed. Callers fall back to templates."""


@dataclass
class Image:
    data: bytes
    mime_type: str = "image/png"


@dataclass(order=True)
class _Job:
    priority: int
    seq: int
    agent: str = field(compare=False)
    prompt: str = field(compare=False)
    system: str = field(compare=False)
    schema: type[BaseModel] = field(compare=False)
    images: list[Image] = field(compare=False)
    cache_path: object = field(compare=False)
    future: asyncio.Future = field(compare=False)


class LLMGateway:
    def __init__(self) -> None:
        self._client = None
        self._queue: asyncio.PriorityQueue[_Job] | None = None
        self._seq = itertools.count()
        self._call_times: deque[float] = deque()
        self._rate_lock: asyncio.Lock | None = None
        self._workers: list[asyncio.Task] = []
        self.stats = {"calls": 0, "cache_hits": 0, "failures": 0, "retries": 0}
        settings.cache_dir.mkdir(parents=True, exist_ok=True)

    # ── lifecycle ────────────────────────────────────────────────────────────
    def start(self) -> None:
        if self._workers:
            return
        self._queue = asyncio.PriorityQueue()
        self._rate_lock = asyncio.Lock()
        if settings.ai_enabled:
            from google import genai

            self._client = genai.Client(api_key=settings.api_key)
        self._workers = [asyncio.create_task(self._worker()) for _ in range(settings.max_concurrent)]

    async def stop(self) -> None:
        for w in self._workers:
            w.cancel()
        self._workers = []

    # ── public API ───────────────────────────────────────────────────────────
    def status(self) -> dict:
        now = time.monotonic()
        recent = sum(1 for t in self._call_times if now - t <= 60)
        return {
            "enabled": settings.ai_enabled,
            "mode": "live" if settings.ai_enabled else ("offline" if settings.ai_offline else "no_api_key"),
            "model": settings.model,
            "queue_depth": self._queue.qsize() if self._queue else 0,
            "calls_this_minute": recent,
            "rpm_limit": settings.rpm,
            "max_concurrent": settings.max_concurrent,
            **self.stats,
        }

    def cache_key(self, agent: str, prompt: str, system: str = "", images: list[Image] | None = None) -> str:
        h = hashlib.sha256(f"{agent}|{settings.model}|{system}|{prompt}".encode())
        for img in images or []:
            h.update(hashlib.sha256(img.data).digest())
        return h.hexdigest()

    def cached(self, agent: str, prompt: str, schema: type[T], system: str = "", images: list[Image] | None = None) -> T | None:
        path = settings.cache_dir / f"{agent}-{self.cache_key(agent, prompt, system, images)[:40]}.json"
        if path.exists():
            try:
                return schema.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception:  # stale cache from an older schema
                path.unlink(missing_ok=True)
        return None

    async def run(
        self,
        agent: str,
        prompt: str,
        schema: type[T],
        *,
        system: str = "",
        images: list[Image] | None = None,
        priority: int = LIVE,
        timeout: float | None = None,
    ) -> T:
        hit = self.cached(agent, prompt, schema, system, images)
        if hit is not None:
            self.stats["cache_hits"] += 1
            trace.cache_hit(agent)
            return hit
        if not settings.ai_enabled:
            reason = "AI disabled" if settings.ai_offline else "GEMINI_API_KEY not set"
            trace.skipped(agent, reason)
            raise AIUnavailable(reason)
        if self._queue is None:
            self.start()
        path = settings.cache_dir / f"{agent}-{self.cache_key(agent, prompt, system, images)[:40]}.json"
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        await self._queue.put(_Job(priority, next(self._seq), agent, prompt, system, schema, images or [], path, fut))
        try:
            # shield: on caller timeout the job keeps running and fills the cache for next time
            return await asyncio.wait_for(asyncio.shield(fut), timeout or settings.timeout_s)
        except asyncio.TimeoutError as e:
            raise AIUnavailable(f"{agent}: timed out, still queued") from e
        except AIUnavailable:
            raise
        except Exception as e:
            raise AIUnavailable(f"{agent}: {type(e).__name__}: {str(e)[:160]}") from e

    # ── internals ────────────────────────────────────────────────────────────
    async def _throttle(self) -> None:
        assert self._rate_lock is not None
        async with self._rate_lock:
            while True:
                now = time.monotonic()
                while self._call_times and now - self._call_times[0] > 60:
                    self._call_times.popleft()
                if len(self._call_times) < settings.rpm:
                    self._call_times.append(now)
                    return
                await asyncio.sleep(60 - (now - self._call_times[0]) + 0.1)

    async def _worker(self) -> None:
        assert self._queue is not None
        while True:
            job = await self._queue.get()
            try:
                result = await self._call(job)
                job.cache_path.write_text(result.model_dump_json(), encoding="utf-8")
                if not job.future.done():
                    job.future.set_result(result)
            except Exception as e:  # noqa: BLE001 - surfaced to the caller
                self.stats["failures"] += 1
                log.warning("gemini call failed: %s", e)
                if not job.future.done():
                    job.future.set_exception(e)
            finally:
                self._queue.task_done()

    async def _call(self, job: _Job, attempts: int = 4) -> BaseModel:
        from google.genai import errors, types

        contents: list = [types.Part.from_bytes(data=i.data, mime_type=i.mime_type) for i in job.images]
        contents.append(job.prompt)
        config = types.GenerateContentConfig(
            system_instruction=job.system or None,
            response_mime_type="application/json",
            response_schema=job.schema,
            temperature=0.2,
        )
        span = trace.start(job.agent, settings.model, job.system, job.prompt, len(job.images), _PRIORITY.get(job.priority, 'live'))
        try:
            for i in range(attempts):
                await self._throttle()
                try:
                    self.stats["calls"] += 1
                    resp = await self._client.aio.models.generate_content(model=settings.model, contents=contents, config=config)
                    result = job.schema.model_validate_json(resp.text)
                    trace.end(span, resp.text, getattr(resp, "usage_metadata", None))
                    return result
                except errors.APIError as e:
                    if (e.code == 429 or e.code >= 500) and i < attempts - 1:
                        self.stats["retries"] += 1
                        trace.retry(span, i + 1, attempts - 1, e)
                        await asyncio.sleep(2**i + random.random())
                        continue
                    raise
            raise AIUnavailable("exhausted retries")
        except Exception as e:
            trace.fail(span, e)
            raise


gateway = LLMGateway()
