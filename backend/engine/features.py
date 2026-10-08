"""Provider feature table + peer groups (specialty × state, national fallback when n < PEER_MIN_N).

Used by rules (R03, R12), anomaly scoring, peer context and the forecast. Every number here
is a plain statistic over claims/members/referrals so evidence can cite its sources.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .store import DataStore

LABELS = {
    "general_medicine": "General medicine", "orthopedics": "Orthopedics", "physiotherapy": "Physiotherapy",
    "cardiology": "Cardiology", "oncology": "Oncology", "pediatrics": "Pediatrics", "nephrology": "Nephrology",
    "emergency": "Emergency", "radiology": "Radiology", "pathology": "Pathology", "psychiatry": "Psychiatry",
}
TYPE_LABELS = {"facility": "Hospital", "lab": "Lab", "pharmacy": "Pharmacy", "ambulance": "Ambulance",
               "dme": "DME supplier", "home_health": "Home health", "behavioral": "Behavioral health"}


def peer_label(ptype: str, specialty: str, scope: str) -> str:
    base = LABELS.get(specialty) if ptype in ("individual", "group") else TYPE_LABELS.get(ptype, ptype.title())
    if ptype == "facility" and specialty == "nephrology":
        base = "Dialysis center"
    return f"{base or specialty.title()}, {scope}"


def build_provider_features(store: DataStore, cfg: Config) -> pd.DataFrame:
    p = store.providers.set_index("provider_id")
    h = store.hdr[store.hdr.frequency_code == 1]
    c = store.claims[store.claims.frequency_code == 1]
    today = pd.Timestamp(cfg.sim_today)

    f = pd.DataFrame(index=p.index)
    f["provider_type"], f["specialty"], f["state"] = p["provider_type"], p["specialty"], p["state"]
    g = h.groupby("provider_id")
    f["n_claims"] = g.size()
    f["n_members"] = g["member_id"].nunique()
    f["billed_total"] = g["billed"].sum()
    first = g["service_date"].min()
    months = ((today - first).dt.days / 30.44).clip(lower=1)
    f["claims_per_month"] = f["n_claims"] / months
    f["billed_per_member"] = f["billed_total"] / f["n_members"]
    # E&M level mix
    em = c[c.procedure_code.str.fullmatch(r"EM[1-5]")]
    eg = em.groupby("provider_id")
    f["em_lines"] = eg.size()
    f["em5_share"] = em.assign(e5=em.procedure_code.eq("EM5")).groupby("provider_id")["e5"].mean()
    recent = em[em.service_date >= today - pd.DateOffset(months=cfg.UPCODE_RECENT_MONTHS)]
    f["em_lines_recent"] = recent.groupby("provider_id").size()
    f["em5_share_recent"] = recent.assign(e5=recent.procedure_code.eq("EM5")).groupby("provider_id")["e5"].mean()
    # threshold band (claim level, billed amount; pending claims have paid = 0)
    lo, hi = cfg.THRESHOLD_HUG_LOW * cfg.review_threshold_inr, cfg.review_threshold_inr
    band = h.assign(inb=(h.billed >= lo) & (h.billed < hi))
    f["in_band"] = band.groupby("provider_id")["inb"].sum()
    f["band_share"] = band.groupby("provider_id")["inb"].mean()
    # code mix
    cc = c.groupby(["provider_id", "procedure_code"]).size()
    f["distinct_codes"] = cc.groupby(level=0).size()
    top3 = cc.groupby(level=0, group_keys=False).apply(lambda s: s.nlargest(3).sum() / s.sum())
    f["top3_code_share"] = top3
    # case mix: mean member risk score of the members a provider billed
    mrisk = store.members.set_index("member_id")["risk_score"]
    pm = h[["provider_id", "member_id"]].drop_duplicates()
    f["case_mix_index"] = pm.assign(r=pm.member_id.map(mrisk)).groupby("provider_id")["r"].mean()
    f["share_65plus"] = pm.assign(o=pm.member_id.map(store.members.set_index("member_id")["age"]) >= 65).groupby("provider_id")["o"].mean()
    # referrals
    r = store.referrals
    f["referrals_in"] = r.groupby("to_provider_id").size()
    f["referrals_out"] = r.groupby("from_provider_id").size()
    top_src = r.groupby(["to_provider_id", "from_provider_id"]).size()
    f["top_source_share"] = top_src.groupby(level=0).max() / f["referrals_in"]
    f["referral_sources"] = top_src.groupby(level=0).size()
    # history and tenure
    inv = store.investigations
    f["prior_investigations"] = inv[inv.opened_date >= today - pd.DateOffset(months=36)].groupby("provider_id").size()
    f["tenure_months"] = ((today - p["enrolled_date"]).dt.days / 30.44).round(0)
    f = f.fillna({k: 0 for k in ["n_claims", "n_members", "billed_total", "claims_per_month", "em_lines", "em_lines_recent",
                                 "in_band", "distinct_codes", "referrals_in", "referrals_out", "referral_sources",
                                 "prior_investigations"]})
    # peer groups
    klass = f["provider_type"].where(~f["provider_type"].isin(["individual", "group"]), "professional")
    key3 = klass + "|" + f["specialty"] + "|" + f["state"]
    counts = key3.map(key3.value_counts())
    national = klass + "|" + f["specialty"] + "|national"
    f["peer_key"] = np.where(counts >= cfg.PEER_MIN_N, key3, national)
    f["peer_n"] = f["peer_key"].map(f["peer_key"].value_counts()).astype(int)
    f["peer_label"] = [peer_label(t, s, st if k.endswith(st) else "national")
                       for t, s, st, k in zip(f.provider_type, f.specialty, f.state, f.peer_key)]
    return f


def peer_stats(f: pd.DataFrame, provider_id: str, metric: str, min_activity: str | None = None,
               min_value: float = 0) -> dict:
    """value, peer median / p90 / percentile for one metric within the provider's peer group.
    Peers can be restricted to providers with `min_activity` >= `min_value` (e.g. em_lines >= 20)."""
    row = f.loc[provider_id]
    peers = f[f.peer_key == row.peer_key]
    if min_activity:
        peers = peers[peers[min_activity] >= min_value]
    vals = peers[metric].dropna().to_numpy(dtype=float)
    v = float(row[metric]) if pd.notna(row[metric]) else 0.0
    if len(vals) == 0:
        return {"value": v, "peer_median": 0.0, "peer_p90": 0.0, "percentile": None, "n": 0, "label": row.peer_label}
    pct = float(((vals < v).mean() + 0.5 * (vals == v).mean()) * 100)
    return {"value": v, "peer_median": float(np.median(vals)), "peer_p90": float(np.percentile(vals, 90)),
            "percentile": round(pct, 1), "n": int(len(vals)), "label": row.peer_label}
