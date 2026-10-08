"""Append-only audit log (spec A16): data/state/audit.jsonl."""

from __future__ import annotations

import json
from datetime import datetime

from .config import CONFIG


def _path():
    CONFIG.state_dir.mkdir(parents=True, exist_ok=True)
    return CONFIG.state_dir / "audit.jsonl"


def _items() -> list[dict]:
    p = _path()
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def log_event(actor: str, event: str, case_id: str | None, before: dict | None, after: dict | None, details: dict | None = None) -> str:
    n = len(_items()) + 1
    aid = f"AUD-{n:06d}"
    rec = {"audit_id": aid, "ts": datetime.now().replace(microsecond=0).isoformat(), "actor": actor, "event": event,
           "case_id": case_id, "before": before, "after": after, "details": details or {}}
    with _path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return aid


def read(limit: int = 50) -> dict:
    items = _items()
    return {"total": len(items), "items": list(reversed(items))[:limit]}


def count() -> int:
    return len(_items())
