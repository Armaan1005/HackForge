"""Time Machine (spec A14): monthly snapshots of the case graph + 30/60/90 neighbor projection."""

from __future__ import annotations

import pandas as pd


def build(case: dict, graph: dict, fc: dict | None, context: dict) -> dict:
    months = sorted({n["first_seen_month"] for n in graph["nodes"]} | {e["first_seen_month"] for e in graph["edges"]})
    h = case["hdr"].assign(m=case["hdr"].service_date.dt.strftime("%Y-%m"))
    total = float(h.billed.sum()) or 1.0
    snaps = []
    for m in months:
        sub = h[h.m <= m]
        snaps.append({"month": m, "node_ids": [n["id"] for n in graph["nodes"] if n["first_seen_month"] <= m],
                      "edge_ids": [e["id"] for e in graph["edges"] if e["first_seen_month"] <= m],
                      "claims_count": int(len(sub)), "amount": int(sub.billed.sum()),
                      "risk": int(round(case["risk"] * sub.billed.sum() / total))})
    proj = {"30": [], "60": [], "90": []}
    if fc is not None:
        g = context.get("projection")
        cand = set(case["providers"])
        if g is not None:
            for p in case["providers"]:
                if p in g:
                    cand |= set(sorted(g.neighbors(p), key=lambda x: -g[p][x]["weight"])[:2])
        for hz in proj:
            pr = fc["probs"][hz]
            items = sorted(((p, float(pr.get(p, 0.0))) for p in cand if p in pr.index), key=lambda t: (-t[1], t[0]))[:4]
            proj[hz] = [{"entity_id": p, "probability": round(v, 2)} for p, v in items]
    return {"case_id": case["case_id"], "months": months, "snapshots": snaps, "projection": proj, "fallback": fc is None}


__all__ = ["build", "pd"]
