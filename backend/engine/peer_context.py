"""Peer context builder (spec A10): citable peer comparisons (PC-{case#}-{nn}) so the
Prosecutor and Defense quote real numbers. Every item names its peer group and n."""

from __future__ import annotations

import pandas as pd

from .config import Config
from .exonerate import Explainer
from .features import peer_stats
from .store import DataStore

METRICS = [  # column, label, min-activity column, incriminating when high?
    ("em5_share", "EM5 share of E&M visits", "em_lines", True),
    ("band_share", "Threshold-band share (₹40k–₹49,999)", "n_claims", True),
    ("billed_per_member", "Billed per member (INR)", "n_claims", True),
    ("code_mix_kl", "Procedure-mix KL divergence vs peers", "n_claims", True),
    ("top_source_share", "Top referral source share", "referrals_in", True),
]


def build(store: DataStore, cfg: Config, feats: pd.DataFrame, case: dict, context: dict | None = None) -> list[dict]:
    provs = case["providers"]
    if not provs:
        return []
    pid = provs[0]
    n = case["n"]
    out: list[dict] = []
    row = feats.loc[pid]

    def add(metric: str, value, st: dict, direction: str, note: str | None = None, raw_ratio=None, entity: str = pid) -> None:
        item = {"evidence_id": f"PC-{n:04d}-{len(out) + 1:02d}", "metric": metric, "entity_id": entity,
                "case_value": round(float(value), 3)}
        if raw_ratio is not None:
            item["raw_ratio"] = round(float(raw_ratio), 2)
        item["peer_median"] = round(float(st["peer_median"]), 3)
        if st.get("peer_p90") is not None:
            item["peer_p90"] = round(float(st["peer_p90"]), 3)
        item.update({"percentile": st.get("percentile"), "peer_group": {"label": st["label"], "n": int(st["n"])},
                     "low_sample": int(st["n"]) < cfg.PEER_MIN_N, "direction": direction})
        if note:
            item["note"] = note
        out.append(item)

    for col, label, act, high_bad in METRICS:
        if col not in feats.columns or pd.isna(row.get(col)) or float(row[col]) == 0:
            continue
        st = peer_stats(feats, pid, col, act, 1)
        if st["n"] == 0:
            continue
        pctl = st["percentile"] or 0
        direction = "incriminating" if high_bad and pctl >= 90 else ("neutral" if pctl >= 25 else "exculpatory")
        add(label, row[col], st, direction)
    # case mix and the risk-adjusted utilisation ratio (the Defense's best friend)
    cmi = peer_stats(feats, pid, "case_mix_index", "n_claims", 1)
    if cmi["n"]:
        higher = (cmi["percentile"] or 0) >= 75
        add("Case-mix index (mean member risk score)", row.case_mix_index, cmi,
            "exculpatory" if higher else "incriminating",
            "Members are sicker than most peers'; part of the volume may be explained" if higher
            else "Members are not sicker than average, so case mix does not explain volume")
        bpm = peer_stats(feats, pid, "billed_per_member", "n_claims", 1)
        if bpm["peer_median"] and cmi["peer_median"]:
            raw = bpm["value"] / bpm["peer_median"]
            adj = raw / (cmi["value"] / cmi["peer_median"])
            ok = adj < cfg.CASE_MIX_ADJ_CLEAR_RATIO
            add("Billed per member, risk-adjusted ratio", adj, {**bpm, "peer_median": 1.0, "peer_p90": None}, "exculpatory" if ok else "incriminating",
                f"{raw:.1f}x raw {'falls to' if adj < raw else 'stays at'} {adj:.1f}x after case-mix adjustment", raw_ratio=raw)
    # history, tenure, rural access
    inv = int(row.prior_investigations)
    add("Prior SIU investigations (36 months)", inv, peer_stats(feats, pid, "prior_investigations"),
        "exculpatory" if inv == 0 else "incriminating")
    ten = peer_stats(feats, pid, "tenure_months")
    add("Provider tenure (months since enrolment)", row.tenure_months, ten, "neutral",
        "New providers have less history to compare against" if row.tenure_months < 12 else None)
    sole = Explainer(store, cfg, feats, context or {}).sole_provider(pid)
    if sole:
        add("Nearest same-type competitor (km)", sole["nearest_competitor_km"],
            {"peer_median": cfg.SOLE_PROVIDER_KM, "peer_p90": None, "percentile": None, "label": sole["peer_group"], "n": 1},
            "exculpatory", "Sole provider for the area; high volume may reflect access, not fraud")
    return out
