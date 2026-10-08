"""Part B HTTP API, mounted at /api/ai."""
from __future__ import annotations

import asyncio
import re
import hashlib
import json
import logging
import socket
from contextlib import asynccontextmanager

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from . import engine_client as engine, ollama, rag
from .agents.brief import write_brief
from .agents.court import run_court
from .agents.explain import ask_case, explain_cleared
from .agents.forensics import analyze_document
from .agents.twin import advise_hardening, parse_scenario
from .config import settings
from .gateway import LIVE, PREWARM, gateway
from .verifier import STATS

log = logging.getLogger("axon.genai")


@asynccontextmanager
async def lifespan(_app):
    gateway.start()
    yield
    await gateway.stop()


router = APIRouter(prefix="/api/ai", tags=["ai"])
AI_DOCS_PER_CASE = 4  # Gemini reviews the most important records; the rest get code checks only

# Results per (case, evidence hash): court -> brief reuse it, and a changed case invalidates it.
_court_cache: dict[str, dict] = {}
_inflight: dict[str, asyncio.Task] = {}


def _case_key(case: dict) -> str:
    return case["case_id"] + ":" + hashlib.sha1(json.dumps(case, sort_keys=True).encode()).hexdigest()[:12]


async def _load_case(case_id: str) -> dict:
    try:
        return await engine.get_case(case_id)
    except engine.EngineError as e:
        raise HTTPException(404, {"code": "not_found", "message": str(e)}) from e
    except Exception as e:  # engine down
        raise HTTPException(503, {"code": "engine_unavailable", "message": f"Engine API unavailable: {e}"}) from e


async def _court(case: dict, priority: int, refresh: bool = False, fresh: bool = False) -> dict:
    key = _case_key(case)
    if not refresh and key in _court_cache:
        return _court_cache[key]
    if key not in _inflight:  # collapse concurrent requests for the same case
        _inflight[key] = asyncio.create_task(run_court(case, priority, fresh))
    try:
        result = await _inflight[key]
    finally:
        _inflight.pop(key, None)
    # Don't pin a template fallback caused by a slow model: the next request picks up Gemini's answer from the cache.
    if not any("still queued" in n for n in result["ai"]["notes"]):
        _court_cache[key] = result
    return result


# ── endpoints ────────────────────────────────────────────────────────────────
@router.get("/lan")
async def lan():
    """This laptop's address on the local network, so judges' phones on the same Wi-Fi can open the app (QR code)."""
    primary = None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # UDP connect sends nothing; it just picks the interface with the default route
            primary = s.getsockname()[0]
    except OSError:
        pass
    try:
        found = {a[4][0] for a in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
    except OSError:
        found = set()
    others = sorted(ip for ip in found if ip != primary and not ip.startswith(("127.", "169.254.")))
    return {"ip": primary or (others[0] if others else None), "candidates": ([primary] if primary else []) + others}


@router.get("/rulebook")
async def rulebook(case_id: str | None = None):
    """The whole rulebook (for the book view), plus which rules retrieval picks for a case."""
    retrieved = []
    if case_id:
        retrieved = [{"id": r["id"], "score": r.get("score")} for r in rag.for_case(await _load_case(case_id))]
    return {"entries": rag.entries(), "case_id": case_id, "retrieved": retrieved}


@router.get("/status")
async def status():
    local = await ollama.available() if any(m.startswith("ollama/") for m in gateway.models) else []
    return {**gateway.status(), "chain": gateway.models, "ollama_models": local, "use_fixtures": settings.use_fixtures, "verifier": STATS}


@router.post("/court/{case_id}")
async def court(case_id: str, refresh: bool = False, fresh: bool = False):
    """fresh=true skips the answer cache so the hearing is argued live by Gemini."""
    return await _court(await _load_case(case_id), LIVE, refresh or fresh, fresh)


@router.get("/brief/{case_id}")
async def brief(case_id: str, format: str = "json"):
    case = await _load_case(case_id)
    result = await write_brief(case, await _court(case, LIVE), LIVE)
    if format == "md":
        return PlainTextResponse(result["markdown"], media_type="text/markdown",
                                 headers={"Content-Disposition": f'attachment; filename="{case_id}-brief.md"'})
    return result


@router.post("/forensics/{case_id}")
async def forensics(case_id: str):
    case = await _load_case(case_id)
    docs = []
    flagged = {i for e in case.get("evidence", []) if e.get("type") == "document" for i in re.findall(r"DOC-\d+", e.get("description", ""))[:1]}
    order = sorted(case.get("documents", []), key=lambda d: (d["document_id"] not in flagged, d.get("format") != "scan"))
    async def one(n: int, d: dict) -> dict:
        doc = await engine.get_document(d["document_id"])
        use_ai = n < AI_DOCS_PER_CASE
        scan = await engine.get_scan(d["document_id"]) if use_ai and d.get("format") == "scan" else None
        return {"document": doc, **await analyze_document(doc, case, scan, LIVE, use_ai=use_ai)}

    # in parallel, so the page waits for one Gemini timeout at most, not one per record
    docs = list(await asyncio.gather(*(one(n, d) for n, d in enumerate(order))))
    return {"case_id": case_id, "documents": docs,
            "injection_detected": any(d["injection_detected"] for d in docs), "affects_score": False}


class ClearedReq(BaseModel):
    limit: int = 20


@router.post("/explain_cleared")
async def explain(req: ClearedReq):
    alerts = (await engine.get_cleared_alerts(req.limit))["items"][: req.limit]
    return await explain_cleared(alerts, LIVE)


class ParseReq(BaseModel):
    text: str


@router.post("/twin/parse")
async def twin_parse(req: ParseReq):
    return await parse_scenario(req.text, await engine.get_twin_scenarios(), LIVE)


class AdviseReq(BaseModel):
    run: dict


@router.post("/twin/advise")
async def twin_advise(req: AdviseReq):
    whitelist = await engine.get_twin_scenarios()
    return await advise_hardening(req.run, whitelist.get("tunable_params", []), LIVE)


class AskReq(BaseModel):
    question: str


@router.post("/ask/{case_id}")
async def ask(case_id: str, req: AskReq):
    return await ask_case(await _load_case(case_id), req.question, LIVE)


@router.get("/trust")
async def trust():
    """Merged into the Trust panel's `ai` block."""
    return {**STATS, "model": settings.model, "enabled": settings.ai_enabled}


@router.post("/prewarm")
async def prewarm(background: BackgroundTasks):
    """Precompute court, brief and forensics for every queued case at low priority (run before the demo)."""
    ids = await engine.get_queue_case_ids()

    async def _run():
        for cid in ids:
            try:
                case = await engine.get_case(cid)
                c = await _court(case, PREWARM)
                await write_brief(case, c, PREWARM)
                for d in case.get("documents", []):
                    doc = await engine.get_document(d["document_id"])
                    await analyze_document(doc, case, None, PREWARM)
            except Exception as e:  # noqa: BLE001
                log.warning("prewarm %s failed: %s", cid, e)

    background.add_task(_run)
    return {"queued_cases": ids}
