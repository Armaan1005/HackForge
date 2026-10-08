"""Peer anomaly scoring (spec A4): robust z-scores within peer groups, procedure-mix KL
divergence, Isolation Forest on the z matrix (fit once, reused by Fraud Twin), and the
top-3 drivers as evidence. Member-level anomaly is the spec's first item to cut; omitted.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from ..config import Config
from ..store import DataStore
from .signals import pct, signal

FEATURES = {
    "claims_per_member": ("Claims per member", "claims"), "billed_per_member": ("Billed per member", "inr"),
    "n_members": ("Unique members", "members"), "new_member_share": ("New-member share (180 days)", "share"),
    "em5_share": ("EM5 share of E&M visits", "share"), "avg_billed_per_claim": ("Average billed per claim", "inr"),
    "band_share": ("Threshold-band share", "share"), "weekend_share": ("Weekend share", "share"),
    "top_source_share": ("Inbound referral concentration", "share"), "top_dest_share": ("Outbound referral concentration", "share"),
    "case_mix_index": ("Case-mix index (mean member risk score)", "score"),
    "avg_distance_member_km": ("Average member distance (km)", "km"), "code_mix_kl": ("Procedure-mix KL divergence", "kl"),
    "max_daily_hours": ("Busiest day (hours billed)", "hours"),
}
MIN_CLAIMS = 10
Z_CLIP = 8.0
ALPHA = 0.5


def code_mix_kl(store: DataStore, feats: pd.DataFrame) -> pd.Series:
    """KL(P_provider || P_peer) over procedure codes with additive smoothing (alpha = 0.5)."""
    c = store.claims[store.claims.frequency_code.eq(1)]
    counts = c.groupby(["provider_id", "procedure_code"]).size().unstack(fill_value=0)
    out = pd.Series(np.nan, index=feats.index)
    for key, grp in feats.groupby("peer_key"):
        ids = [p for p in grp.index if p in counts.index]
        if len(ids) < 2:
            continue
        sub = counts.loc[ids]
        sub = sub.loc[:, sub.sum(axis=0) > 0]
        peer = sub.sum(axis=0).to_numpy(float) + ALPHA
        q = peer / peer.sum()
        mat = sub.to_numpy(float) + ALPHA
        p = mat / mat.sum(axis=1, keepdims=True)
        out.loc[ids] = (p * np.log(p / q)).sum(axis=1)
    return out


def robust_z(feats: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """z = (x - median) / (1.4826 · MAD) within the peer group, clipped ±8. When MAD is 0
    the mean absolute deviation (× 1.2533) is used; a constant feature gets z = 0."""
    x = feats[cols].astype(float)
    g = x.groupby(feats["peer_key"])
    med = g.transform("median")
    dev = (x - med).abs()
    mad = dev.groupby(feats["peer_key"]).transform("median") * 1.4826
    alt = dev.groupby(feats["peer_key"]).transform("mean") * 1.2533
    scale = mad.where(mad > 0, alt)
    z = ((x - med) / scale.where(scale > 0)).clip(-Z_CLIP, Z_CLIP)
    return z.fillna(0.0)


def fit_scores(z: pd.DataFrame, seed: int) -> tuple[IsolationForest, pd.Series]:
    model = IsolationForest(n_estimators=200, contamination="auto", random_state=seed)
    model.fit(z.to_numpy())
    raw = -model.score_samples(z.to_numpy())  # higher = more anomalous
    pct_rank = pd.Series(raw, index=z.index).rank(pct=True, method="average")
    return model, pct_rank


def run(store: DataStore, cfg: Config, feats: pd.DataFrame, context: dict) -> list[dict]:
    feats = feats.copy()
    feats["code_mix_kl"] = code_mix_kl(store, feats)
    active = feats[feats.n_claims >= MIN_CLAIMS]
    cols = list(FEATURES)
    z = robust_z(active, cols)
    if context.get("anomaly_model_fixed") is not None:  # Fraud Twin: reuse the baseline model
        model = context["anomaly_model_fixed"]
        raw = -model.score_samples(z.to_numpy())
        score = pd.Series(raw, index=z.index).rank(pct=True, method="average")
    else:
        model, score = fit_scores(z, cfg.seed)
    context.update({"anomaly_model": model, "anomaly_z": z, "anomaly_score": score, "anomaly_cols": cols,
                    "feats_full": feats})
    out = []
    for pid in score[score >= 0.9].sort_values(ascending=False).index:
        s = float(score[pid])
        row = active.loc[pid]
        top = z.loc[pid].abs().sort_values(ascending=False).head(3)
        drivers = ", ".join(f"{FEATURES[f][0].lower()} z={z.loc[pid, f]:.1f}" for f in top.index)
        strength = 0.5 + 0.5 * min(1.0, (s - 0.9) / 0.09)
        n_claims = int(row.n_claims)
        out.append(signal(
            layer="anomaly", method="anomaly.isolation_forest", name=f"Billing profile in the top {max(1, round((1 - s) * 100))}% of peers",
            description=f"{pid} anomaly score {s:.2f} (percentile) within {row.peer_label}; top drivers: {drivers}.",
            entity_type="provider", entity_id=str(pid), value=round(s, 3), comparison_value=0.5,
            comparison_label="peer median anomaly percentile", unit="percentile", threshold=0.9, severity=3,
            strength=strength, sources=[("claims", "billed_amount"), ("claims", "procedure_code"), ("claims", "member_id")],
            extra={"claim_count": n_claims, "drivers": list(top.index)}))
        for f in top.index:
            zv = float(z.loc[pid, f])
            if abs(zv) < 2:
                continue
            peers = active[active.peer_key == row.peer_key][f]
            label, unit = FEATURES[f]
            v = float(row[f]) if pd.notna(row[f]) else 0.0
            med = float(peers.median())
            method = "anomaly.code_mix_kl" if f == "code_mix_kl" else f"anomaly.robust_z.{f}"
            val_txt = pct(v) if unit == "share" else (f"{v:,.0f}" if unit in ("inr", "members", "claims") else f"{v:.2f}")
            med_txt = pct(med) if unit == "share" else (f"{med:,.0f}" if unit in ("inr", "members", "claims") else f"{med:.2f}")
            out.append(signal(
                layer="anomaly", method=method, name=f"{label} far from peers",
                description=f"{label}: {val_txt} vs peer median {med_txt} ({row.peer_label}, n={int(row.peer_n)}); robust z = {zv:.1f}.",
                entity_type="provider", entity_id=str(pid), value=round(v, 4), comparison_value=round(med, 4),
                comparison_label=f"peer median ({row.peer_label}, n={int(row.peer_n)})", unit=unit, threshold=2.0,
                severity=2, strength=min(strength, 0.4 + abs(zv) / 16),
                sources=[("claims", "procedure_code" if f == "code_mix_kl" else "billed_amount"), ("providers", "specialty")],
                extra={"z": round(zv, 2)}))
    return out
