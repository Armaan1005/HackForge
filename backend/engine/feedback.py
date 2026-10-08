"""Human decisions + bounded method-weight feedback (spec A16). Only a human decision
records a hold; the engine never acts on its own."""

from __future__ import annotations

import copy
import json
from datetime import datetime

from .audit import log_event
from .config import CONFIG

ETA = 0.05
W_MIN, W_MAX = 0.05, 0.6
CASE_STATUS = {"confirm": "confirmed_by_human", "clear": "cleared_by_human", "need_more_info": "awaiting_records",
               "hold_payment": "open"}


def _read(name: str, default):
    p = CONFIG.state_dir / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _write(name: str, obj) -> None:
    CONFIG.state_dir.mkdir(parents=True, exist_ok=True)
    (CONFIG.state_dir / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def weights() -> dict[str, float]:
    return {**CONFIG.METHOD_WEIGHTS, **_read("weights.json", {})}


def apply_state(doc: dict) -> dict:
    dec = _read("decisions.json", {}).get(doc["case_id"])
    if not dec:
        return doc
    out = copy.deepcopy(doc)
    out["status"] = dec["case_status"]
    out["payment_clock"]["hold_status"] = dec["hold_status"]
    return out


def record_decision(case_id: str, body: dict) -> dict:
    case = json.loads((CONFIG.processed_dir / "cases" / f"{case_id}.json").read_text(encoding="utf-8"))
    decisions = _read("decisions.json", {})
    prev = decisions.get(case_id, {})
    action = body["action"]
    w = weights()
    changes = []
    if action in ("confirm", "clear"):
        sign = 1 if action == "confirm" else -1
        for m, v in case["scores"]["by_method"].items():
            if v >= 0.5:
                new = round(min(W_MAX, max(W_MIN, w[m] * (1 + sign * ETA))), 4)
                changes.append({"method": m, "before": w[m], "after": new})
                w[m] = new
        if changes:
            _write("weights.json", w)
    hold = "held" if action == "hold_payment" else prev.get("hold_status", "none")
    n = sum(1 for _ in decisions) + 1
    rec = {"decision_id": f"DEC-{n:05d}", "case_id": case_id, "action": action, "user": body["user"],
           "recorded_at": datetime.now().replace(microsecond=0).isoformat(), "note": body.get("note"),
           "case_status": CASE_STATUS[action] if action != "hold_payment" else prev.get("case_status", "open"), "hold_status": hold}
    decisions[case_id] = rec
    _write("decisions.json", decisions)
    aid = log_event(body["user"], f"decision.{action}", case_id, {"status": prev.get("case_status", case["verdict"]["status"])},
                    {"status": rec["case_status"], "hold_status": hold}, {"decision_id": rec["decision_id"], "note": body.get("note")})
    if changes:
        log_event("system", "weights.update", case_id, {c["method"]: c["before"] for c in changes},
                  {c["method"]: c["after"] for c in changes}, {"eta": ETA})
    return {"decision_id": rec["decision_id"], "case_id": case_id, "action": action, "user": body["user"],
            "recorded_at": rec["recorded_at"], "weight_changes": changes, "queue_changed": True, "hold_status": hold, "audit_id": aid}


def reset() -> dict:
    p = CONFIG.state_dir / "weights.json"
    before = weights()
    if p.exists():
        p.unlink()
    log_event("analyst", "weights.reset", None, before, dict(CONFIG.METHOD_WEIGHTS))
    return {"reset": True, "weights": dict(CONFIG.METHOD_WEIGHTS)}
