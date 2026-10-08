"""Temporal analytics (spec A5) on monthly series per provider: EM5 drift, bursts (isolated vs
region-wide), rapid ramp of new providers, and same-member clustering within
TEMPORAL_WINDOW_DAYS across linked providers (the parameter Fraud Twin hardening tunes).
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.stats import linregress

from ..config import Config
from ..store import DataStore
from .graph_analytics import linked_claims
from .signals import inr, pct, signal

DRIFT_WINDOW_MONTHS = 9
DRIFT_MIN_SLOPE = 0.03  # 3 percentage points per month
DRIFT_MAX_P = 0.05
DRIFT_MIN_EM_PER_MONTH = 5
BURST_MIN_CLAIMS = 12
BURST_MIN_RATIO = 3.0
REGION_WIDE_MIN_PROVIDERS = 5
RAMP_MAX_TENURE_MONTHS = 9


def monthly(store: DataStore) -> pd.DataFrame:
    h = store.hdr[store.hdr.frequency_code.eq(1)]
    return h.assign(month=h.service_date.dt.to_period("M"))


def drift(store: DataStore, cfg: Config, feats: pd.DataFrame) -> list[dict]:
    c = store.claims[store.claims.frequency_code.eq(1) & store.claims.procedure_code.str.fullmatch(r"EM[1-5]")]
    c = c.assign(month=c.service_date.dt.to_period("M"), e5=c.procedure_code.eq("EM5"))
    g = c.groupby(["provider_id", "month"]).agg(n=("e5", "size"), share=("e5", "mean")).reset_index()
    last = pd.Period(pd.Timestamp(cfg.sim_today) - pd.Timedelta(days=1), "M")
    window = pd.period_range(last - DRIFT_WINDOW_MONTHS + 1, last, freq="M")
    out = []
    for pid, grp in g[g.month.isin(window) & (g.n >= DRIFT_MIN_EM_PER_MONTH)].groupby("provider_id"):
        if len(grp) < cfg.DRIFT_MIN_MONTHS:
            continue
        x = np.array([(m - window[0]).n for m in grp.month])
        res = linregress(x, grp.share.to_numpy(float))
        if res.slope <= DRIFT_MIN_SLOPE or res.pvalue >= DRIFT_MAX_P:
            continue
        first, lastrow = grp.iloc[0], grp.iloc[-1]
        ids = c[(c.provider_id == pid) & c.e5 & c.month.isin(set(grp.month))].claim_id
        out.append(signal(
            layer="temporal", method="temporal.em5_drift", name="EM5 share rising month after month",
            description=f"EM5 share rose from {pct(first.share)} ({first.month}) to {pct(lastrow.share)} ({lastrow.month}) "
                        f"over {len(grp)} months: +{res.slope * 100:.1f} pp/month (p={res.pvalue:.3f}).",
            entity_type="provider", entity_id=str(pid), claim_ids=list(ids), value=round(res.slope * 100, 2),
            comparison_value=DRIFT_MIN_SLOPE * 100, comparison_label="drift threshold (pp/month)", unit="pp_per_month",
            threshold=cfg.DRIFT_MIN_MONTHS, severity=3, strength=0.6 + 0.4 * min(1.0, (res.slope - DRIFT_MIN_SLOPE) / 0.05),
            sources=[("claims", "procedure_code"), ("claims", "service_date")],
            extra={"start": round(float(first.share), 3), "end": round(float(lastrow.share), 3), "months": len(grp),
                   "p_value": round(float(res.pvalue), 4)}))
    return out


def bursts(store: DataStore, cfg: Config, feats: pd.DataFrame, context: dict) -> list[dict]:
    h = monthly(store)
    counts = h.groupby(["provider_id", "month"]).size().unstack(fill_value=0).sort_index(axis=1)
    months = list(counts.columns)
    city = store.provider_index["city"]
    found = []  # (provider, month, count, baseline)
    elevated: dict[tuple, set] = defaultdict(set)  # looser test, used only to tag region-wide spikes
    arr = counts.to_numpy().astype(float)
    ids = list(counts.index)
    for j in range(3, len(months)):
        prior = arr[:, max(0, j - 6):j]
        med = np.median(prior, axis=1)
        mad = np.maximum(1.0, np.median(np.abs(prior - med[:, None]), axis=1) * 1.4826)
        cur = arr[:, j]
        for i in np.flatnonzero((cur >= 5) & (cur > med + cfg.BURST_MAD_K * mad)):
            elevated[(city[ids[i]], months[j])].add(ids[i])
        for i in np.flatnonzero((cur >= BURST_MIN_CLAIMS) & (cur > med + cfg.BURST_MAD_K * mad) & (cur >= BURST_MIN_RATIO * np.maximum(med, 1))):
            found.append((ids[i], months[j], int(cur[i]), float(med[i])))
    found.sort(key=lambda t: (t[0], t[1]))
    by_region = elevated
    context["bursts"] = {}
    out = []
    first_burst: dict[str, tuple] = {}
    for pid, m, n, med in found:
        region_n = len(by_region[(city[pid], m)])
        wide = region_n >= REGION_WIDE_MIN_PROVIDERS
        context["bursts"].setdefault(pid, []).append({"month": str(m), "count": n, "baseline": med,
                                                       "region_wide": wide, "providers_spiking": region_n, "city": city[pid]})
        if pid not in first_burst:
            first_burst[pid] = (m, n, med, wide, region_n)
    for pid, (m, n, med, wide, region_n) in sorted(first_burst.items()):
        ids = h[(h.provider_id == pid) & (h.month >= m)].claim_id
        if wide:
            out.append(signal(
                layer="temporal", method="temporal.burst_region_wide", name="Volume spike shared across the region",
                description=f"Monthly claims rose from {med:.0f} to {n} in {m}, while {region_n - 1} other provider(s) in "
                            f"{city[pid]} spiked the same month (region-wide, e.g. seasonal or an event).",
                entity_type="provider", entity_id=str(pid), claim_ids=list(ids), value=n, comparison_value=med,
                comparison_label="median monthly claims, prior 6 months", unit="claims_per_month", threshold=cfg.BURST_MAD_K,
                severity=1, strength=0.3, direction="neutral",
                sources=[("claims", "service_date"), ("providers", "city")], extra={"providers_spiking": region_n}))
        else:
            out.append(signal(
                layer="temporal", method="temporal.burst", name=f"Isolated billing burst starting {m.strftime('%B %Y')}",
                description=f"Monthly claims rose from {med:.0f} to {n} in {m}; no other {city[pid]} provider spiked "
                            f"that month (not region-wide).",
                entity_type="provider", entity_id=str(pid), claim_ids=list(ids), value=n, comparison_value=med,
                comparison_label=f"median monthly claims, 6 months before {m}", unit="claims_per_month",
                threshold=cfg.BURST_MAD_K, severity=2, strength=0.55 + 0.25 * min(1.0, (n - med) / 20),
                sources=[("claims", "service_date")], extra={"region_wide": False}))
    return out


def rapid_ramp(store: DataStore, cfg: Config, feats: pd.DataFrame) -> list[dict]:
    today = pd.Timestamp(cfg.sim_today)
    h = store.hdr[store.hdr.frequency_code.eq(1)]
    out = []
    young = feats[(feats.tenure_months < RAMP_MAX_TENURE_MONTHS) & (feats.n_claims >= 10)]
    for pid, row in young.iterrows():
        since = store.provider_index.loc[pid, "enrolled_date"]
        months = max(1.0, (today - since).days / 30.44)
        rate = row.n_claims / months
        peers = feats[(feats.peer_key == row.peer_key) & (feats.n_claims >= 5)]["claims_per_month"]
        p90 = float(peers.quantile(0.9)) if len(peers) else 0.0
        if rate <= 2 * p90:
            continue
        ids = h[h.provider_id == pid].claim_id
        out.append(signal(
            layer="temporal", method="temporal.rapid_ramp", name="New provider ramping up fast",
            description=f"Enrolled {since.date()} ({months:.0f} months ago) and already billing {rate:.1f} claims/month; "
                        f"peer p90 is {p90:.1f} ({row.peer_label}).",
            entity_type="provider", entity_id=str(pid), claim_ids=list(ids), value=round(rate, 1), comparison_value=round(p90, 1),
            comparison_label=f"peer p90 claims per month ({row.peer_label})", unit="claims_per_month",
            threshold=RAMP_MAX_TENURE_MONTHS, severity=2, strength=0.6,
            sources=[("providers", "enrolled_date"), ("claims", "service_date")]))
    return out


def window_clusters(store: DataStore, cfg: Config, feats: pd.DataFrame, context: dict) -> list[dict]:
    """Same member, different providers that share an owner or facility, within the window."""
    p = store.provider_index
    h = store.hdr[store.hdr.frequency_code.eq(1) & store.hdr.provider_id.isin(p.index)]
    h = h[h.billed >= cfg.THRESHOLD_HUG_LOW * cfg.review_threshold_inr]  # mid/high-value claims only
    h = h.assign(owner=h.provider_id.map(p.owner_id), fac=h.provider_id.map(p.primary_facility_id))
    out = []
    win = cfg.TEMPORAL_WINDOW_DAYS
    links: dict[str, set[str]] = defaultdict(set)
    for col in ("owner", "fac"):
        multi = h.groupby(col)["provider_id"].nunique()
        sub = h[h[col].isin(multi[multi >= 2].index)]
        for key, g in sub.groupby(col):
            linked, _ = linked_claims(g, win)
            if linked:
                links[f"{col}:{key}"] |= linked
    context["window_links"] = links
    for key in sorted(links):
        ids = sorted(links[key])
        if len(ids) < 6:
            continue
        sub = h[h.claim_id.isin(ids)]
        provs = sorted(set(sub.provider_id))
        for pid in provs:
            mine = sub[sub.provider_id == pid]
            out.append(signal(
                layer="temporal", method="temporal.window_cluster", name="Same members billed by linked providers in quick succession",
                description=f"{len(ids)} claims for {sub.member_id.nunique()} shared member(s) were billed by {len(provs)} providers "
                            f"sharing one {'owner' if key.startswith('owner') else 'facility'} within {win} days of each other "
                            f"(total {inr(sub.billed.sum())}).",
                entity_type="provider", entity_id=str(pid), entity_ids=provs, claim_ids=list(mine.claim_id), value=len(ids),
                comparison_value=0, comparison_label=f"linked claims within {win} days (expected few)", unit="claims",
                threshold=win, severity=2, strength=0.55 + 0.25 * min(1.0, len(ids) / 40),
                sources=[("claims", "member_id"), ("claims", "service_date"), ("providers", "owner_id")]))
    return out


def run(store: DataStore, cfg: Config, feats: pd.DataFrame, context: dict) -> list[dict]:
    return (drift(store, cfg, feats) + bursts(store, cfg, feats, context) + rapid_ramp(store, cfg, feats)
            + window_clusters(store, cfg, feats, context))
