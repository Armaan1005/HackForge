"""The only path to Gemini.

Protects the free-tier quota during a live demo:
- disk cache keyed by (agent, prompt, images) so repeated views cost nothing
- in-flight de-duplication: the same prompt asked twice waits on one call
- concurrency cap (worker pool) + a requests-per-minute window *per model*
- model fallback chain: a model that is overloaded (503) or out of quota (429) rests for
  the delay Google asks for, and the next model in the chain answers instead
- priority queue so a judge's live request jumps ahead of background prewarming
- callers get a timeout; the job still finishes in the background and fills the cache
"""
from __future__ import annotations

import asyncio
import hashlib
import itertools
import logging
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel

from . import trace
from .config import settings

log = logging.getLogger("axon.gateway")

LIVE, PREWARM, BACKGROUND = 0, 1, 2
_PRIORITY = {LIVE: "live", PREWARM: "prewarm", BACKGROUND: "background"}
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


def _retry_after(err: Exception, default: float) -> float:
    """Seconds Google asks us to wait ("retryDelay": "15s" / "retry in 15.05s"), else default."""
    m = re.search(r"retry(?:Delay'?: '| in )(\d+(?:\.\d+)?)s", str(err))
    return float(m.group(1)) + 0.5 if m else default


def _consume(fut: asyncio.Future) -> None:
    """Mark a background failure as handled so asyncio doesn't print 'exception never retrieved'."""
    if not fut.cancelled():
        fut.exception()


class LLMGateway:
    def __init__(self) -> None:
        self._client = None
        self._queue: asyncio.PriorityQueue[_Job] | None = None
        self._seq = itertools.count()
        self._calls: dict[str, deque[float]] = defaultdict(deque)   # model -> call timestamps (60 s window)
        self._resting: dict[str, float] = {}                        # model -> monotonic time it may be used again
        self._pending: dict[str, asyncio.Future] = {}               # cache key -> in-flight future
        self._rate_lock: asyncio.Lock | None = None
        self._workers: list[asyncio.Task] = []
        self.stats = {"calls": 0, "cache_hits": 0, "failures": 0, "retries": 0, "fallbacks": 0}
        self.last_model: dict[str, str] = {}
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
    @property
    def models(self) -> list[str]:
        return [settings.model, *[m for m in settings.fallback_models if m != settings.model]]

    def status(self) -> dict:
        now = time.monotonic()
        per_model = {m: sum(1 for t in self._calls[m] if now - t <= 60) for m in self.models}
        return {
            "enabled": settings.ai_enabled,
            "mode": "live" if settings.ai_enabled else ("offline" if settings.ai_offline else "no_api_key"),
            "model": settings.model,
            "fallback_models": settings.fallback_models,
            "resting": {m: round(t - now) for m, t in self._resting.items() if t > now},
            "queue_depth": self._queue.qsize() if self._queue else 0,
            "calls_this_minute": sum(per_model.values()),
            "calls_per_model": per_model,
            "rpm_limit": settings.rpm,
            "max_concurrent": settings.max_concurrent,
            **self.stats,
        }

    def cache_key(self, agent: str, prompt: str, system: str = "", images: list[Image] | None = None) -> str:
        h = hashlib.sha256(f"{agent}|{system}|{prompt}".encode())
        for img in images or []:
            h.update(hashlib.sha256(img.data).digest())
        return h.hexdigest()

    def _path(self, agent: str, key: str):
        return settings.cache_dir / f"{agent}-{key[:40]}.json"

    def cached(self, agent: str, prompt: str, schema: type[T], system: str = "", images: list[Image] | None = None) -> T | None:
        path = self._path(agent, self.cache_key(agent, prompt, system, images))
        if path.exists():
            try:
                return schema.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception:  # stale cache from an older schema
                path.unlink(missing_ok=True)
        return None

    async def run(self, agent: str, prompt: str, schema: type[T], *, system: str = "", images: list[Image] | None = None,
                  priority: int = LIVE, timeout: float | None = None) -> T:
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
        key = self.cache_key(agent, prompt, system, images)
        fut = self._pending.get(key)
        if fut is None or fut.done():
            fut = asyncio.get_running_loop().create_future()
            fut.add_done_callback(_consume)
            fut.add_done_callback(lambda _f, k=key: self._pending.pop(k, None))
            self._pending[key] = fut
            await self._queue.put(_Job(priority, next(self._seq), agent, prompt, system, schema, images or [], self._path(agent, key), fut))
        else:
            trace.skipped(agent, "same request already in flight, sharing it")
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
    async def _pick_model(self) -> str:
        """First model in the chain that is not resting and has room in its per-minute window.
        If none is free, wait for the earliest one."""
        assert self._rate_lock is not None
        async with self._rate_lock:
            while True:
                now = time.monotonic()
                waits = []
                for m in self.models:
                    calls = self._calls[m]
                    while calls and now - calls[0] > 60:
                        calls.popleft()
                    rest = self._resting.get(m, 0) - now
                    if rest > 0:
                        waits.append(rest)
                        continue
                    if len(calls) < settings.rpm:
                        calls.append(now)
                        return m
                    waits.append(60 - (now - calls[0]))
                await asyncio.sleep(max(0.2, min(waits) + 0.1))

    async def _worker(self) -> None:
        assert self._queue is not None
        while True:
            job = await self._queue.get()
            try:
                result = await self._call(job)
                job.cache_path.write_text(result.model_dump_json(), encoding="utf-8")
                if not job.future.done():
                    job.future.set_result(result)
            except Exception as e:  # noqa: BLE001 - surfaced to the caller (and the trace)
                self.stats["failures"] += 1
                log.debug("gemini call failed: %s", e)
                if not job.future.done():
                    job.future.set_exception(e)
            finally:
                self._queue.task_done()

    async def _call(self, job: _Job) -> BaseModel:
        from google.genai import errors, types

        contents: list = [types.Part.from_bytes(data=i.data, mime_type=i.mime_type) for i in job.images]
        contents.append(job.prompt)
        config = types.GenerateContentConfig(
            system_instruction=job.system or None,
            response_mime_type="application/json",
            response_schema=job.schema,
            temperature=0.2,
        )
        attempts = len(self.models) + 1
        model = await self._pick_model()
        span = trace.start(job.agent, model, job.system, job.prompt, len(job.images), _PRIORITY.get(job.priority, "live"))
        try:
            for i in range(attempts):
                try:
                    self.stats["calls"] += 1
                    resp = await self._client.aio.models.generate_content(model=model, contents=contents, config=config)
                    result = job.schema.model_validate_json(resp.text)
                    self.last_model[job.agent] = model
                    trace.end(span, resp.text, getattr(resp, "usage_metadata", None), model=model)
                    return result
                except errors.APIError as e:
                    if not (e.code == 429 or e.code >= 500) or i == attempts - 1:
                        raise
                    # rest this model for as long as Google asks (or a short default), then use the next free one
                    self._resting[model] = time.monotonic() + _retry_after(e, 20 if e.code == 429 else 8)
                    self.stats["retries"] += 1
                    nxt = await self._pick_model()
                    if nxt != model:
                        self.stats["fallbacks"] += 1
                    trace.switch(span, model, nxt, e)
                    model = nxt
            raise AIUnavailable("exhausted retries")
        except Exception as e:
            trace.fail(span, e)
            raise


gateway = LLMGateway()
