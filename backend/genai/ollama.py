"""Local Ollama backend for the gateway: no quota, works offline, same structured-JSON contract.

Model names in the chain look like "ollama/qwen2.5:7b". Uses Ollama's structured outputs
(`format` = JSON schema) so answers validate against the same Pydantic models as Gemini's.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx
from pydantic import BaseModel

from .config import settings


class OllamaError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code  # 503 when Ollama isn't running, so the gateway treats it as transient


@dataclass
class Usage:
    prompt_token_count: int | None
    candidates_token_count: int | None


async def generate(model: str, system: str, prompt: str, schema: type[BaseModel]) -> tuple[str, Usage]:
    name = model.removeprefix("ollama/")
    body = {
        "model": name,
        "messages": [*([{"role": "system", "content": system}] if system else []), {"role": "user", "content": prompt}],
        "format": schema.model_json_schema(),
        "stream": False,
        "options": {"temperature": 0.2, "num_ctx": settings.ollama_num_ctx},
        "keep_alive": "30m",
    }
    try:
        async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=settings.ollama_timeout_s) as client:
            r = await client.post("/api/chat", json=body)
    except httpx.ConnectError as e:
        raise OllamaError(503, f"Ollama not reachable at {settings.ollama_url}: is the Ollama app running?") from e
    except httpx.TimeoutException as e:
        raise OllamaError(504, f"Ollama timed out after {settings.ollama_timeout_s:.0f}s") from e
    if r.status_code != 200:
        raise OllamaError(r.status_code if r.status_code >= 500 else 400, f"Ollama {r.status_code}: {r.text[:200]}")
    data = r.json()
    return data["message"]["content"], Usage(data.get("prompt_eval_count"), data.get("eval_count"))


async def available() -> list[str]:
    """Installed local models (empty if Ollama isn't running)."""
    try:
        async with httpx.AsyncClient(base_url=settings.ollama_url, timeout=3) as client:
            r = await client.get("/api/tags")
        return [m["name"] for m in r.json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        return []
