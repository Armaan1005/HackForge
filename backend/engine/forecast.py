"""30/60/90-day forecast (spec A12): "likelihood of repeat or escalating FWA over the horizon".

Monthly snapshots t (month 6 .. SIM_TODAY − H) with features from data ≤ t; label = the
provider gets newly flagged claims (claims named in its incriminating signals) in (t, t+H].
That is a date-filterable stand-in for "new signal or +10 risk" (re-running every layer per
snapshot would blow the 30 s budget). One HistGradientBoosting model per horizon,
time-based holdout (last 3 snapshot months), AUC / Brier / 10-bin calibration.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import brier_score_loss, roc_auc_score

from .config import Config
from .store import DataStore

HORIZONS = (30, 60, 90)
FEATURES = {
    "claims_90d": ("Claims in the last 90 days", "claims"),
    "volume_slope_3m": ("Monthly claim growth (last 3 months)", "ratio"),
    "claims_per_member": ("Claims per member", "claims"),
    "billed_per_member": ("Billed per member", "inr"),
    "em5_share": ("EM5 share of E&M visits", "share"),
    "threshold_hug_share": ("Share of claims just under ₹50k", "share"),
    "weekend_share": ("Weekend share", "share"),
    "prior_flagged_claims": ("Previously flagged claims", "claims"),
    "prior_investigations": ("Prior SIU investigations", "count"),
    "tenure_months": ("Months since enrolment", "months"),
    "case_mix_index": ("Case-mix index", "score"),
    "network_exposure": ("Share of linked providers already flagged", "share"),
}
LABEL = "New incriminating signal, or newly flagged claims, within the next {h} days"


def snapshot(store: DataStore, cfg: Config, t: pd.Timestamp, flagged_dates: pd.DataFrame, exposure: dict) -> pd.DataFrame:
    h = store.hdr[(store.hdr.frequency_code == 1) & (store.hdr.service_date <= t)]
    lo, hi = cfg.THRESHOLD_HUG_LOW * cfg.review_threshold_inr, cfg.review_threshold_inr
    g = h.groupby("provider_id")
    f = pd.DataFrame(index=sorted(store.provider_index.index))
    recent = h[h.service_date > t - pd.Timedelta(days=90)]
    f["claims_90d"] = recent.groupby("provider_id").size()
    m3 = recent.groupby("provider_id").size()
    prev = h[(h.service_date > t - pd.Timedelta(days=180)) & (h.service_date <= t - pd.Timedelta(days=90))].groupby("provider_id").size()
    f["volume_slope_3m"] = (m3.reindex(f.index).fillna(0) + 1) / (prev.reindex(f.index).fillna(0) + 1)
    f["claims_per_member"] = g.size() / g["member_id"].nunique()
    f["billed_per_member"] = g["billed"].sum() / g["member_id"].nunique()
    em = store.claims[(store.claims.service_date <= t) & store.claims.procedure_code.str.fullmatch(r"EM[1-5]")]
    f["em5_share"] = em.assign(e=em.procedure_code.eq("EM5")).groupby("provider_id")["e"].mean()
    f["threshold_hug_share"] = h.assign(b=(h.billed >= lo) & (h.billed < hi)).groupby("provider_id")["b"].mean()
    f["weekend_share"] = h.assign(w=h.service_date.dt.dayofweek >= 5).groupby("provider_id")["w"].mean()
    f["prior_flagged_claims"] = flagged_dates[flagged_dates.service_date <= t].groupby("provider_id").size()
    inv = store.investigations
    f["prior_investigations"] = inv[inv.opened_date <= t].groupby("provider_id").size()
    f["tenure_months"] = ((t - store.provider_index.enrolled_date).dt.days / 30.44).reindex(f.index)
    mrisk = store.member_index.risk_score
    pm = h[["provider_id", "member_id"]].drop_duplicates()
    f["case_mix_index"] = pm.assign(r=pm.member_id.map(mrisk)).groupby("provider_id")["r"].mean()
    f["network_exposure"] = pd.Series(exposure).reindex(f.index)
    f = f.fillna({"claims_90d": 0, "prior_flagged_claims": 0, "prior_investigations": 0, "network_exposure": 0})
    f["active"] = g.size().reindex(f.index).fillna(0) >= 3
    return f


def run(store: DataStore, cfg: Config, signals: list[dict], context: dict) -> dict:
    today = pd.Timestamp(cfg.sim_today)
    flagged = defaultdict(set)
    for s in signals:
        if s["direction"] == "incriminating" and s["entity_type"] == "provider":
            flagged[s["entity_id"]] |= set(s["claim_ids"])
    hdr = store.hdr.set_index("claim_id")
    rows = [(p, c) for p, cs in flagged.items() for c in cs if c in hdr.index]
    fd = pd.DataFrame(rows, columns=["provider_id", "claim_id"])
    fd["service_date"] = fd.claim_id.map(hdr.service_date)
    exposure = context.get("network_exposure", {})
    month_ends = pd.date_range(pd.Timestamp(cfg.history_start) + pd.DateOffset(months=6), today, freq="ME")
    snaps = {t: snapshot(store, cfg, t, fd, exposure) for t in month_ends}
    now = snapshot(store, cfg, today - pd.Timedelta(days=1), fd, exposure)
    cols = list(FEATURES)
    models, metrics, probs, drivers = {}, {}, {}, {}
    for H in HORIZONS:
        train_rows = []
        for t, f in snaps.items():
            if t + pd.Timedelta(days=H) > today:
                continue
            win = fd[(fd.service_date > t) & (fd.service_date <= t + pd.Timedelta(days=H))]
            lab = f.index.isin(set(win.provider_id))
            d = f[f.active].assign(label=lab[f.active.to_numpy()], t=t)
            train_rows.append(d)
        data = pd.concat(train_rows)
        ts = sorted(data.t.unique())
        hold = set(ts[-3:])
        tr, te = data[~data.t.isin(hold)], data[data.t.isin(hold)]
        model = HistGradientBoostingClassifier(random_state=cfg.seed, max_iter=200, learning_rate=0.08)
        model.fit(tr[cols], tr.label.astype(int))
        p = model.predict_proba(te[cols])[:, 1]
        y = te.label.astype(int).to_numpy()
        auc = float(roc_auc_score(y, p)) if len(set(y)) > 1 else float("nan")
        cal = []
        for k in range(10):
            m = (p >= k / 10) & (p < (k + 1) / 10 if k < 9 else p <= 1.0)
            if m.sum():
                cal.append({"bin": f"{k / 10:.1f}-{(k + 1) / 10:.1f}", "predicted": round(float(p[m].mean()), 3),
                            "observed": round(float(y[m].mean()), 3), "n": int(m.sum())})
        imp = permutation_importance(model, te[cols], y, n_repeats=3, random_state=cfg.seed, scoring="roc_auc")
        importance = pd.Series(np.clip(imp.importances_mean, 0, None), index=cols)
        metrics[str(H)] = {"auc": round(auc, 3), "brier": round(float(brier_score_loss(y, p)), 3), "calibration": cal,
                           "trained_through": str(pd.Timestamp(max(tr.t)).date()),
                           "holdout": f"{pd.Timestamp(ts[-3]).strftime('%Y-%m')}..{pd.Timestamp(ts[-1]).strftime('%Y-%m')} (time-based)",
                           "positives": int(data.label.sum()), "rows": int(len(data))}
        models[H] = model
        probs[str(H)] = pd.Series(model.predict_proba(now[cols])[:, 1], index=now.index)
        drivers[str(H)] = importance
    context["forecast_snapshot"] = now
    return {"models": models, "metrics": metrics, "probs": probs, "importance": drivers, "now": now}


def entity_docs(feats: pd.DataFrame, fc: dict, ids: list[str]) -> dict[str, dict]:
    """Forecast documents for many providers at once (drivers = |z| within peer group × importance)."""
    now = fc["now"].reindex(ids)
    cols = list(FEATURES)
    key = feats["peer_key"].reindex(ids)
    x = now[cols].astype(float)
    med = x.groupby(key).transform("median")
    dev = (x - med).abs()
    mad = dev.groupby(key).transform("median")
    mad = mad.where(mad > 0, dev.groupby(key).transform("mean")).where(lambda m: m > 0, 1.0)
    z = (dev / mad).fillna(0).clip(upper=5) / 5
    out: dict[str, dict] = {}
    per_h = {}
    for h in ("30", "60", "90"):
        sc = z * fc["importance"][h].reindex(cols).to_numpy()
        per_h[h] = sc
    for pid in ids:
        allh = {h: round(float(fc["probs"][h][pid]), 3) for h in ("30", "60", "90")}
        by_h = {}
        for h in ("30", "60", "90"):
            row = per_h[h].loc[pid]
            top = sorted(cols, key=lambda c: (-row[c], c))[:3]
            m = fc["metrics"][h]
            by_h[h] = {
                "horizon": int(h), "probability": allh[h], "label_definition": LABEL.format(h=h),
                "top_drivers": [{"feature": c, "label": FEATURES[c][0],
                                 "value": round(float(x.at[pid, c]), 3) if pd.notna(x.at[pid, c]) else 0.0,
                                 "peer_median": round(float(med.at[pid, c]), 3) if pd.notna(med.at[pid, c]) else 0.0,
                                 "contribution": round(float(row[c]), 3)} for c in top],
                "model": {"type": "HistGradientBoostingClassifier", "trained_through": m["trained_through"],
                          "holdout": m["holdout"], "auc_holdout": m["auc"], "brier_holdout": m["brier"]},
            }
        doc = {"entity_id": pid, **by_h["30"], "all_horizons": allh,
               "limitations": ["Trained on synthetic data; calibration is shown in the Trust panel.",
                               "The label comes from the same detectors (newly flagged claims), so holdout scores are optimistic."]}
        doc = {k: doc[k] for k in ("entity_id", "horizon", "probability", "label_definition", "top_drivers",
                                   "all_horizons", "model", "limitations")}
        doc["by_horizon"] = by_h
        out[pid] = doc
    return out
