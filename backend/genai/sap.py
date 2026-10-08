"""SAP AI Core (Generative AI Hub) backend for the gateway, via the Orchestration service.

Same setup as the Prism (SAP Hackfest) app: service key -> OAuth token -> the running
`orchestration` deployment in the resource group -> /v2/completion with the chosen model.
Model names in the chain look like "sap/anthropic--claude-4.5-sonnet".
The service key file is read at runtime and never logged.
"""
from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass

import httpx
from pydantic import BaseModel

from .config import settings


class SapError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class Usage:
    prompt_token_count: int | None
    candidates_token_count: int | None


_token: tuple[str, float] | None = None   # (access token, expiry)
_deployment_url: str | None = None


def key_available() -> bool:
    return settings.aicore_key_path.exists()


def _key() -> dict:
    return json.loads(settings.aicore_key_path.read_text(encoding="utf-8"))


async def _auth(client: httpx.AsyncClient) -> dict[str, str]:
    global _token, _deployment_url
    k = _key()
    if not _token or _token[1] - time.time() < 60:
        r = await client.post(k["url"].rstrip("/") + "/oauth/token", data={"grant_type": "client_credentials"},
                              auth=(k["clientid"], k["clientsecret"]))
        if r.status_code != 200:
            raise SapError(401, f"SAP AI Core token request failed ({r.status_code})")
        j = r.json()
        _token = (j["access_token"], time.time() + int(j.get("expires_in", 3600)))
    headers = {"Authorization": f"Bearer {_token[0]}", "AI-Resource-Group": settings.sap_resource_group}
    if not _deployment_url:
        api = k["serviceurls"]["AI_API_URL"].rstrip("/")
        r = await client.get(f"{api}/v2/lm/deployments", headers=headers, params={"scenarioId": "orchestration", "status": "RUNNING"})
        running = [d for d in r.json().get("resources", []) if d.get("deploymentUrl")]
        if not running:
            raise SapError(503, f"No running orchestration deployment in resource group '{settings.sap_resource_group}'")
        _deployment_url = running[0]["deploymentUrl"].rstrip("/")
    return headers


def _parse_json(text: str) -> str:
    """Models sometimes wrap JSON in ```json fences or add a sentence: keep only the JSON object."""
    cleaned = re.sub(r"```(?:json)?", "", text or "").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    return cleaned[start:end + 1] if start >= 0 and end > start else cleaned


async def generate(model: str, system: str, prompt: str, schema: type[BaseModel], images: list | None = None) -> tuple[str, Usage]:
    name = model.removeprefix("sap/")
    sys_text = (f"{system}\n\n" if system else "") + (
        "Respond with one valid JSON object only, no markdown, matching this JSON schema:\n"
        + json.dumps(schema.model_json_schema(), separators=(",", ":")))
    user_content: object = "{{?user}}"
    if images:
        user_content = [{"type": "text", "text": "{{?user}}"}] + [
            {"type": "image_url", "image_url": {"url": f"data:{i.mime_type};base64,{base64.b64encode(i.data).decode()}"}} for i in images]
    body = {
        "config": {"modules": {"prompt_templating": {
            "prompt": {"template": [{"role": "system", "content": "{{?system}}"}, {"role": "user", "content": user_content}]},
            "model": {"name": name, "params": {"temperature": 0.2, "max_tokens": settings.sap_max_tokens}},
        }}},
        # prompts contain JSON braces, so they go in as placeholder values, never into the template itself
        "placeholder_values": {"system": sys_text, "user": prompt},
    }
    try:
        async with httpx.AsyncClient(timeout=settings.sap_timeout_s) as client:
            headers = await _auth(client)
            r = await client.post(f"{_deployment_url}/v2/completion", headers=headers, json=body)
    except httpx.TimeoutException as e:
        raise SapError(504, f"SAP AI Core timed out after {settings.sap_timeout_s:.0f}s") from e
    except httpx.HTTPError as e:
        raise SapError(503, f"SAP AI Core not reachable: {type(e).__name__}") from e
    if r.status_code != 200:
        raise SapError(r.status_code, f"SAP AI Core {r.status_code}: {r.text[:300]}")
    res = r.json().get("final_result", {})
    text = res.get("choices", [{}])[0].get("message", {}).get("content", "")
    u = res.get("usage", {})
    return _parse_json(text), Usage(u.get("prompt_tokens"), u.get("completion_tokens"))
