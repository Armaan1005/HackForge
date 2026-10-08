"""Citation Verifier: plain code between the agents and the UI.

Every agent statement must cite evidence IDs that exist in the case, and every number it states
must come from the cited evidence (allowing %, lakh/thousand/crore and rounding variants).
Anything else is dropped and counted, never shown as fact.
"""
from __future__ import annotations

import json
import re
import threading
from typing import Iterable

from .config import settings

_ID_TOKEN = re.compile(r"\b[A-Z]{2,6}(?:-[A-Z0-9]+)+\b")          # PRV-00412, EV-0001-01, CASE-T007-01
_DATE = re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?(?:T[\d:]+)?\b")    # 2026-09-21, 2026-07
_ALNUM = re.compile(r"\b[A-Za-z]+\d+[A-Za-z\d]*\b")              # EM5, Q1, S6, D2
_NUM = re.compile(
    r"(?:₹|rs\.?\s*|inr\s*)?(\d[\d,]*(?:\.\d+)?)\s*(crore|cr|lakhs?|lacs?|l|k|%|x|×|pp)?(?![\w])",
    re.IGNORECASE,
)
_MULT = {"crore": 1e7, "cr": 1e7, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "l": 1e5, "k": 1e3}


def numbers_in(text: str) -> list[float]:
    """Numbers stated in free text, normalised (₹21.84L -> 2184000, 94% -> 94)."""
    text = _DATE.sub(" ", _ID_TOKEN.sub(" ", text or ""))
    text = _ALNUM.sub(" ", text)
    out = []
    for m in _NUM.finditer(text):
        raw, unit = m.group(1).replace(",", ""), (m.group(2) or "").lower()
        try:
            v = float(raw)
        except ValueError:
            continue
        out.append(v * _MULT.get(unit, 1))
    return out


def _walk_numbers(obj) -> Iterable[float]:
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        yield float(obj)
    elif isinstance(obj, str):
        yield from numbers_in(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk_numbers(v)


def allowed_numbers(items: Iterable[dict]) -> set[float]:
    """All numbers in the cited items plus their percent/scale variants."""
    allowed: set[float] = set()
    for item in items:
        for v in _walk_numbers(item):
            allowed.update({v, round(v, 2), round(v, 1), round(v)})
            if abs(v) <= 1:
                allowed.update({v * 100, round(v * 100, 1), round(v * 100)})
            if abs(v) >= 1e5:
                allowed.update({round(v / 1e5, 2), round(v / 1e5, 1)})  # rupees -> lakh
            if abs(v) >= 1e3:
                allowed.update({round(v / 1e3, 1), round(v / 1e3)})
    return allowed


def number_ok(n: float, allowed: set[float]) -> bool:
    if n in allowed:
        return True
    return any(abs(n - a) <= max(0.011 * abs(a), 0.051) for a in allowed)


def index_case(case: dict) -> dict[str, dict]:
    """evidence_id -> item, across evidence, peer context and documents."""
    idx = {e["evidence_id"]: e for e in case.get("evidence", [])}
    idx.update({p["evidence_id"]: p for p in case.get("peer_context", [])})
    return idx


# ── stats (feeds the Trust panel "AI statements" block) ─────────────────────
_lock = threading.Lock()
_STATS_PATH = settings.state_dir / "verifier_stats.json"


def _load_stats() -> dict:
    try:
        return json.loads(_STATS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"statements_checked": 0, "kept": 0, "uncited_blocked": 0, "numbers_blocked": 0}


STATS = _load_stats()


def _record(kept: int, uncited: int, numbers: int) -> None:
    with _lock:
        STATS["statements_checked"] += kept + uncited + numbers
        STATS["kept"] += kept
        STATS["uncited_blocked"] += uncited
        STATS["numbers_blocked"] += numbers
        try:
            _STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
            _STATS_PATH.write_text(json.dumps(STATS), encoding="utf-8")
        except OSError:
            pass


# ── checks ───────────────────────────────────────────────────────────────────
def check_statement(text: str, cited_ids: list[str], idx: dict[str, dict], extra_numbers: Iterable[float] = ()) -> tuple[list[str], str | None]:
    """Returns (valid_ids, reason_if_rejected)."""
    ids = [i for i in dict.fromkeys(cited_ids) if i in idx]
    if not ids:
        return [], "uncited" if not cited_ids else f"cites unknown evidence {', '.join(cited_ids[:3])}"
    allowed = allowed_numbers(idx[i] for i in ids)
    allowed.update(extra_numbers)
    bad = [n for n in numbers_in(text) if not number_ok(n, allowed)]
    if bad:
        return ids, f"number not in cited evidence: {bad[0]:g}"
    return ids, None


def verify_arguments(agent: str, arguments: list[dict], idx: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    kept, dropped = [], []
    uncited = numbers = 0
    for a in arguments:
        ids, reason = check_statement(a.get("point", ""), a.get("evidence_ids", []), idx)
        if reason is None:
            allowed = allowed_numbers(idx[i] for i in ids)
            for label, v in (("case_value", a.get("case_value")), ("comparison_value", a.get("comparison_value"))):
                if v not in (None, 0) and not number_ok(float(v), allowed):
                    reason = f"{label} {v:g} not in cited evidence"
                    break
        if reason:
            uncited += reason.startswith(("uncited", "cites unknown"))
            numbers += not reason.startswith(("uncited", "cites unknown"))
            dropped.append({"agent": agent, "point": a.get("point", ""), "reason": reason})
        else:
            kept.append({**a, "evidence_ids": ids, "verified": True})
    _record(len(kept), uncited, numbers)
    return kept, dropped


def verify_text(text: str, cited_ids: list[str], idx: dict[str, dict], whole_case: dict | None = None) -> tuple[bool, str | None]:
    """For prose (verdict summary, brief paragraphs).

    With whole_case, numbers may come from anywhere in the case (citations optional);
    otherwise the text must cite evidence and use only its numbers.
    """
    if whole_case is not None:
        allowed = allowed_numbers([whole_case])
        bad = [n for n in numbers_in(text) if not number_ok(n, allowed)]
        reason = f"number not in case evidence: {bad[0]:g}" if bad else None
    else:
        _, reason = check_statement(text, cited_ids, idx)
    is_cite = bool(reason) and reason.startswith(("uncited", "cites"))
    _record(int(reason is None), int(is_cite), int(bool(reason) and not is_cite))
    return reason is None, reason
