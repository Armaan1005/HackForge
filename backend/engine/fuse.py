"""Fused entity risk (spec A7): weighted noisy-OR over detection layers.

    layer_score[m] = max signal strength in layer m
    raw  = 1 - Π_m (1 - w_m · layer_score[m])
    risk = 100 · raw / max_raw   (max_raw = same product with every available layer at 1.0)
    hard signal  -> risk = max(risk, 85)
    methods_agreeing = #layers with layer_score >= 0.5

The normalisation by max_raw is our addition (see docs/PART_A_NOTES.md): without it the
four default weights cap a non-hard entity at 69, below the fixtures' 79–96 and close to
CASE_MIN_RISK. It also means an unavailable layer does not deflate everyone's risk.
"""

from __future__ import annotations

from collections import defaultdict

LAYERS = ("rules", "anomaly", "temporal", "graph")
HARD_FLOOR = 85


def fuse(signals: list[dict], layers: dict[str, str], weights: dict[str, float]) -> dict[tuple[str, str], dict]:
    avail = [m for m in LAYERS if layers.get(m) == "ok"]
    max_raw = 1.0
    for m in avail:
        max_raw *= 1 - weights[m]
    max_raw = 1 - max_raw if avail else 1.0
    score: dict[tuple, dict[str, float]] = defaultdict(lambda: {m: 0.0 for m in LAYERS})
    hard: dict[tuple, bool] = defaultdict(bool)
    sig_idx: dict[tuple, list[int]] = defaultdict(list)
    for i, s in enumerate(signals):
        if s["direction"] != "incriminating":
            continue
        key = (s["entity_type"], s["entity_id"])
        score[key][s["layer"]] = max(score[key][s["layer"]], s["strength"])
        hard[key] |= s["hard"]
        sig_idx[key].append(i)
    out = {}
    for key, by in score.items():
        prod = 1.0
        for m in avail:
            prod *= 1 - weights[m] * by[m]
        risk = 100 * (1 - prod) / max_raw if max_raw > 0 else 0.0
        if hard[key]:
            risk = max(risk, HARD_FLOOR)
        out[key] = {
            "entity_type": key[0], "entity_id": key[1], "risk": int(round(min(100.0, risk))),
            "by_method": {m: round(by[m], 2) for m in LAYERS},
            "methods_agreeing": sum(1 for m in avail if by[m] >= 0.5), "hard": hard[key], "signals": sig_idx[key],
        }
    return out
