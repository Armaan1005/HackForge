"""Turns a Part A case into the compact evidence pool the agents read (fewer tokens, same facts)."""
from __future__ import annotations

import json

from .rag import for_case

STATUS_LABEL = {
    "needs_siu_review": "Needs SIU review",
    "request_documentation": "Request documentation",
    "monitor": "Monitor",
    "cleared": "Cleared",
}

_EV_KEYS = ("evidence_id", "type", "method", "name", "description", "direction", "value",
            "comparison_value", "comparison_label", "unit", "severity", "hard", "claim_count")
_PC_KEYS = ("evidence_id", "metric", "entity_id", "case_value", "raw_ratio", "peer_median", "peer_p90",
            "percentile", "low_sample", "direction", "note")


def _pick(d: dict, keys: tuple[str, ...]) -> dict:
    return {k: d[k] for k in keys if k in d and d[k] is not None}


def compact_case(case: dict) -> dict:
    peer = []
    for p in case.get("peer_context", []):
        item = _pick(p, _PC_KEYS)
        g = p.get("peer_group") or {}
        item["peer_group"] = f'{g.get("label", "peers")}, n={g.get("n", "?")}'
        peer.append(item)
    v = case.get("verdict", {})
    return {
        "case_id": case["case_id"],
        "title": case.get("title"),
        "pattern": case.get("pattern"),
        "risk": case.get("scores", {}).get("risk"),
        "methods_agreeing": case.get("scores", {}).get("methods_agreeing"),
        "evidence_strength": case.get("evidence_strength"),
        "confidence": case.get("confidence"),
        "status": v.get("status"),
        "next_action_text": v.get("next_action_text"),
        "money": case.get("money"),
        "payment_clock": {k: case.get("payment_clock", {}).get(k) for k in ("days_until_release", "pending_amount", "hold_recommended")},
        "member_harm": {k: case.get("member_harm", {}).get(k) for k in ("score", "members_affected", "vulnerable_share")},
        "claims_summary": case.get("claims_summary"),
        "evidence": [_pick(e, _EV_KEYS) for e in case.get("evidence", [])],
        "peer_context": peer,
        "missing_documents": [{k: m.get(k) for k in ("doc_type", "claim_count", "critical", "why")} for m in case.get("missing_documents", [])],
        "network_summary": case.get("network_summary"),
        "limitations": case.get("limitations", []),
        "rulebook": [{"evidence_id": r["id"], "kind": r["kind"], "title": r["title"], "text": r["text"]} for r in for_case(case)],
    }


def pool_json(case: dict) -> str:
    return json.dumps(compact_case(case), ensure_ascii=False, separators=(",", ":"))


def fmt_value(v: float | int | None, metric: str = "", unit: str = "") -> str:
    """Human formatting that the verifier can still match back to the raw value."""
    if v is None:
        return "n/a"
    m = f"{metric} {unit}".lower()
    if ("share" in m or unit == "share") and abs(v) <= 1:
        return f"{v * 100:.0f}%"
    if unit == "inr" or "amount" in m:
        return f"₹{v / 1e5:.2f}L" if abs(v) >= 1e5 else f"₹{v:,.0f}"
    if isinstance(v, float) and not v.is_integer():
        return f"{v:.2f}".rstrip("0").rstrip(".")
    return f"{v:,.0f}"
