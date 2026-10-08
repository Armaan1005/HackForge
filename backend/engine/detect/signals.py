"""Signal: the atom every detection layer emits (spec A9). Cases turn signals into evidence."""

from __future__ import annotations

from typing import Any


def inr(n: float) -> str:
    """₹ formatting used in descriptions: ₹49,800 below 1 lakh, ₹21.84L above."""
    n = float(n)
    if abs(n) >= 100_000:
        return f"₹{n / 100_000:.2f}L"
    return f"₹{int(round(n)):,}"


def pct(x: float, digits: int = 0) -> str:
    return f"{x * 100:.{digits}f}%"


def signal(*, layer: str, method: str, name: str, description: str, entity_type: str, entity_id: str,
           value: Any, comparison_value: Any, comparison_label: str | None, unit: str, threshold: Any,
           severity: int, strength: float, sources: list[tuple[str, str]], claim_ids: list[str] | None = None,
           entity_ids: list[str] | None = None, hard: bool = False, direction: str = "incriminating",
           extra: dict | None = None) -> dict:
    """Build one signal. `entity_id` is the scored entity; `entity_ids` lists everything it is about."""
    ents = [entity_id] + [e for e in (entity_ids or []) if e != entity_id]
    return {
        "layer": layer, "method": method, "name": name, "description": description,
        "entity_type": entity_type, "entity_id": entity_id, "entity_ids": ents,
        "claim_ids": sorted(set(claim_ids or [])), "value": _num(value), "comparison_value": _num(comparison_value),
        "comparison_label": comparison_label, "unit": unit, "threshold": _num(threshold), "severity": int(severity),
        "hard": bool(hard), "strength": round(float(min(1.0, max(0.0, strength))), 3), "direction": direction,
        "sources": [{"table": t, "column": c} for t, c in sources], "extra": extra or {},
    }


def _num(v: Any) -> Any:
    """JSON-friendly numbers: ints stay ints, floats rounded to 4 places, numpy scalars unwrapped."""
    if v is None:
        return None
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, bool):
        return v
    if isinstance(v, float):
        if v != v:  # NaN
            return None
        return int(v) if v.is_integer() and abs(v) >= 1000 else round(v, 4)
    return v
