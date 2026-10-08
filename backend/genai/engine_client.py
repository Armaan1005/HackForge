"""Reads Part A's outputs: the contract fixtures (USE_FIXTURES=true) or the live engine API."""
from __future__ import annotations

import copy
import json
from functools import lru_cache

import httpx

from .config import settings


class EngineError(Exception):
    pass


@lru_cache(maxsize=32)
def fixture(name: str) -> dict:
    return json.loads((settings.contracts_dir / f"{name}.json").read_text(encoding="utf-8"))


def _fixture_case(case_id: str) -> dict:
    """Fixtures hold one full case (CASE-0001). Other queue IDs reuse its evidence with their own header."""
    case = copy.deepcopy(fixture("case_detail"))
    if case_id == case["case_id"]:
        return case
    row = next((c for c in fixture("queue")["cases"] if c["case_id"] == case_id), None)
    if row is None:
        # Same as the engine's fixture mode: any case ID gets the sample evidence (never a 404),
        # so a UI showing live IDs still works if this process started in fixture mode.
        case.update(case_id=case_id, fixture_sample=True)
        return case
    case.update(case_id=case_id, title=row["title"], pattern=row["pattern"], severity=row["severity"],
                evidence_strength=row["evidence_strength"], confidence=row["confidence"], fixture_sample=True)
    case["scores"]["risk"] = row["risk"]
    case["verdict"]["status"] = row["status"]
    return case


async def _get(path: str, *, raw: bool = False):
    async with httpx.AsyncClient(base_url=settings.engine_url, timeout=10) as client:
        r = await client.get(path)
    if r.status_code == 404:
        raise EngineError(f"not found: {path}")
    r.raise_for_status()
    return r.content if raw else r.json()


async def get_case(case_id: str) -> dict:
    if settings.use_fixtures:
        return _fixture_case(case_id)
    return await _get(f"/api/cases/{case_id}")


async def get_document(document_id: str) -> dict:
    if settings.use_fixtures:
        doc = copy.deepcopy(fixture("document"))
        doc["document_id"] = document_id
        return doc
    return await _get(f"/api/documents/{document_id}")


async def get_scan(document_id: str) -> bytes | None:
    if settings.use_fixtures:
        return None
    try:
        return await _get(f"/api/files/scans/{document_id}.png", raw=True)
    except (EngineError, httpx.HTTPError):
        return None


async def get_cleared_alerts(limit: int = 50) -> dict:
    if settings.use_fixtures:
        return fixture("alerts_cleared")
    return await _get(f"/api/alerts/cleared?limit={limit}")


async def get_twin_scenarios() -> dict:
    if settings.use_fixtures:
        return fixture("twin_scenarios")
    return await _get("/api/twin/scenarios")


async def get_queue_case_ids() -> list[str]:
    if settings.use_fixtures:
        return [c["case_id"] for c in fixture("queue")["cases"]]
    q = await _get("/api/queue?capacity_hours=400&horizon=30")
    return [c["case_id"] for c in q["cases"]]
