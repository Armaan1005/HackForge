"""Portfolio queue optimizer (spec A13): re-planned on every request (< 300 ms).

value = expected_recovery + horizon_risk[h] · projected_monthly_loss · (h/30) · RECOVERY_RATE
value *= (1 + member_harm) · (0.8 + 0.1·severity) · strength_mult
priority = value / effort_hours
CP-SAT 0/1 knapsack over (1 − EXPLORATION_SHARE) of capacity; the rest goes to exploration.
"""

from __future__ import annotations

import json
from pathlib import Path

from ortools.sat.python import cp_model

from .config import CONFIG
from .detect.signals import inr

STRENGTH_MULT = {"strong": 1.0, "moderate": 0.75, "weak": 0.4}
ELIGIBLE = {"needs_siu_review", "request_documentation"}
_cache: dict = {}


def load_cases() -> list[dict]:
    meta = CONFIG.processed_dir / "run_meta.json"
    if not meta.is_file():
        raise FileNotFoundError(meta)
    key = (str(CONFIG.processed_dir), meta.stat().st_mtime)
    if _cache.get("key") != key:
        files = sorted((CONFIG.processed_dir / "cases").glob("CASE-*.json"))
        _cache.update(key=key, cases=[json.loads(Path(f).read_text(encoding="utf-8")) for f in files])
    cases = _cache["cases"]
    try:
        from .feedback import apply_state
    except ModuleNotFoundError:
        return cases
    return [apply_state(c) for c in cases]


def current_weights() -> dict[str, float]:
    path = CONFIG.state_dir / "weights.json"
    if path.is_file():
        return {**CONFIG.METHOD_WEIGHTS, **json.loads(path.read_text(encoding="utf-8"))}
    return dict(CONFIG.METHOD_WEIGHTS)


def value_of(c: dict, horizon: int) -> float:
    m = c["money"]
    v = m["expected_recovery"] + c["horizon_risk"][str(horizon)] * m["projected_monthly_loss"] * (horizon / 30) * CONFIG.RECOVERY_RATE
    return v * (1 + c["member_harm"]["score"]) * (0.8 + 0.1 * c["severity"]) * STRENGTH_MULT[c["evidence_strength"]]


def knapsack(values: list[int], weights: list[int], cap: int) -> list[int]:
    if not values or cap <= 0:
        return []
    m = cp_model.CpModel()
    x = [m.NewBoolVar(f"x{i}") for i in range(len(values))]
    m.Add(sum(w * xi for w, xi in zip(weights, x)) <= cap)
    m.Maximize(sum(v * xi for v, xi in zip(values, x)))
    s = cp_model.CpSolver()
    s.parameters.num_workers = 1
    s.parameters.random_seed = CONFIG.seed
    s.parameters.max_time_in_seconds = 0.2
    s.Solve(m)
    return [i for i, xi in enumerate(x) if s.Value(xi)]


def plan(capacity_hours: int = 40, horizon: int = 30) -> dict:
    cases = load_cases()
    rows = []
    for c in cases:
        v = value_of(c, horizon)
        eff = max(1, int(c["effort_hours"]))
        rows.append({"c": c, "value": v, "effort": eff, "priority": v / eff,
                     "eligible": c["verdict"]["status"] in ELIGIBLE and c.get("status", "open") not in ("cleared_by_human",)})
    rows.sort(key=lambda r: (-r["priority"], r["c"]["case_id"]))
    elig = [r for r in rows if r["eligible"]]
    main_cap = int(capacity_hours * (1 - CONFIG.EXPLORATION_SHARE))
    chosen = {elig[i]["c"]["case_id"] for i in knapsack([int(round(r["value"])) for r in elig], [r["effort"] for r in elig], main_cap)}
    used = sum(r["effort"] for r in elig if r["c"]["case_id"] in chosen)
    explore: set[str] = set()
    left = capacity_hours - used
    pool = [r for r in elig if r["c"]["case_id"] not in chosen]
    pool.sort(key=lambda r: (r["c"]["pattern"] != "mixed", abs(r["c"]["confidence"] - 0.5), r["c"]["case_id"]))
    for r in pool:
        if r["effort"] <= left:
            explore.add(r["c"]["case_id"])
            left -= r["effort"]
            break
    out_cases = []
    for rank, r in enumerate(rows, start=1):
        c = r["c"]
        cid = c["case_id"]
        rph = int(round(c["money"]["expected_recovery"] / r["effort"]))
        clock = c["payment_clock"]
        if cid in chosen:
            if c["member_harm"]["score"] >= 0.6 and c["severity"] >= 5:
                reason = f"Selected: high member harm ({c['member_harm']['score']:.2f}) and severity {c['severity']}"
            else:
                reason = f"Selected: {inr(rph)} expected recovery per hour"
            if clock["hold_recommended"] and clock["days_until_release"] is not None:
                d = clock["days_until_release"]
                reason += f"; {inr(clock['pending_amount'])} releases in {d} day{'s' if d != 1 else ''}"
        elif cid in explore:
            reason = ("Exploration: mixed pattern unlike past confirmed fraud" if c["pattern"] == "mixed"
                      else f"Exploration: uncertain case (confidence {c['confidence']:.2f})")
        elif not r["eligible"]:
            reason = f"Not eligible: status {c['verdict']['status']}"
        else:
            why = []
            if c["evidence_strength"] != "strong":
                why.append(f"{c['evidence_strength']} evidence ({c['scores']['methods_agreeing']} method{'s' if c['scores']['methods_agreeing'] != 1 else ''})")
            if r["effort"] >= 15:
                why.append(f"high effort {r['effort']} h")
            elif r["effort"] > capacity_hours - used:
                why.append(f"{r['effort']} h does not fit the remaining {capacity_hours - used} h")
            else:
                why.append("lower total value than the selected mix")
            why.append(f"{inr(rph)} per hour")
            reason = "Not selected: " + ", ".join(why)
        out_cases.append({
            "rank": rank, "case_id": cid, "title": c["title"], "pattern": c["pattern"], "status": c["verdict"]["status"],
            "risk": c["scores"]["risk"], "dollars_at_risk": c["money"]["dollars_at_risk"],
            "expected_recovery": c["money"]["expected_recovery"], "member_harm": c["member_harm"]["score"],
            "severity": c["severity"], "evidence_strength": c["evidence_strength"], "confidence": c["confidence"],
            "effort_hours": c["effort_hours"], "dead_end_risk": c["dead_end_risk"], "recovery_per_hour": rph,
            "priority_score": int(round(r["priority"])), "horizon_risk": c["horizon_risk"],
            "days_until_release": clock["days_until_release"], "hold_recommended": clock["hold_recommended"],
            "selected": cid in chosen or cid in explore, "exploration": cid in explore, "selection_reason": reason,
        })
    frontier, hrs, rec = [{"hours": 0, "cumulative_recovery": 0}], 0, 0
    for r in elig:
        hrs += r["effort"]
        rec += r["c"]["money"]["expected_recovery"]
        frontier.append({"hours": hrs, "cumulative_recovery": int(rec)})
    sel = [r for r in rows if r["c"]["case_id"] in chosen | explore]
    hours_used = sum(r["effort"] for r in sel)
    rec_sel = int(sum(r["c"]["money"]["expected_recovery"] for r in sel))
    return {
        "capacity_hours": capacity_hours, "horizon": horizon, "currency": "INR", "total_cases": len(rows),
        "eligible_cases": len(elig), "selected_count": len(sel), "hours_used": hours_used,
        "exploration_hours_reserved": int(round(capacity_hours * CONFIG.EXPLORATION_SHARE)),
        "expected_recovery_selected": rec_sel, "recovery_per_hour": int(round(rec_sel / hours_used)) if hours_used else 0,
        "weights": current_weights(), "cases": out_cases, "frontier": frontier,
    }
