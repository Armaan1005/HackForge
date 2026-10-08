"""Rules engine R01–R16 (spec A3). Each rule: (store, cfg, feats) -> list[signal].

Rules read only claims/members/providers/facilities/admissions/referrals/reference tables.
Thresholds come from config and are reported in every signal so the UI can show them.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable

import numpy as np
import pandas as pd
from scipy.stats import binom

from ..config import Config
from ..features import peer_stats
from ..store import DataStore
from .signals import inr, pct, signal

log = logging.getLogger("axon.rules")
KM_PER_MILE = 1.609344


def _hav_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = (np.radians(np.asarray(x, dtype=float)) for x in (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def _originals(c: pd.DataFrame) -> pd.DataFrame:
    """Lines that are not replacements/voids, and not originals that were later voided/replaced."""
    corrected = set(c.loc[c.frequency_code.isin([7, 8]), "original_claim_id"])
    return c[~c.frequency_code.isin([7, 8]) & ~c.claim_id.isin(corrected)]


DUP_KEY = ["member_id", "provider_id", "procedure_code", "drug_code", "dme_item_code"]


def r01_exact_duplicate(store: DataStore, cfg: Config, feats: pd.DataFrame) -> list[dict]:
    o = _originals(store.claims)
    sub = store.hdr.set_index("claim_id")["submitted_date"]
    grp = o.groupby(DUP_KEY + ["service_date", "units"])["claim_id"].agg(lambda s: sorted(set(s)))
    grp = grp[grp.map(len) > 1]
    dups: dict[str, set[str]] = defaultdict(set)
    for key, ids in grp.items():
        first = min(ids, key=lambda i: (sub[i], i))
        dups[key[1]] |= set(ids) - {first}
    out = []
    for prov in sorted(dups):
        ids = dups[prov]
        if len(ids) < cfg.DUP_MIN_CLAIMS:
            continue
        n_all = int(feats.loc[prov, "n_claims"])
        out.append(signal(
            layer="rules", method="rule.R01_exact_duplicate", name="Exact duplicate claims",
            description=f"{len(ids)} claims repeat another claim exactly (same member, code, date and units) "
                        f"without being marked as a correction; {pct(len(ids) / max(n_all, 1))} of the provider's {n_all} claims.",
            entity_type="provider", entity_id=prov, claim_ids=sorted(ids), value=len(ids), comparison_value=0,
            comparison_label="expected exact duplicates (frequency_code 1)", unit="claims", threshold=None, severity=3,
            strength=0.5 + min(0.5, len(ids) / 40),
            sources=[("claims", "member_id"), ("claims", "procedure_code"), ("claims", "service_date"),
                     ("claims", "units"), ("claims", "frequency_code")]))
    return out


def r02_near_duplicate(store: DataStore, cfg: Config, feats: pd.DataFrame) -> list[dict]:
    o = _originals(store.claims).sort_values(DUP_KEY + ["service_date", "claim_id"])
    same = (o[DUP_KEY] == o[DUP_KEY].shift()).all(axis=1)
    gap = (o["service_date"] - o["service_date"].shift()).dt.days
    prev_amt = o["billed_amount"].shift()
    rel = (o["billed_amount"] - prev_amt).abs() / np.maximum(o["billed_amount"], prev_amt)
    near = same & (gap > 0) & (gap <= cfg.DUP_NEAR_DAYS) & (rel <= cfg.DUP_NEAR_AMOUNT_PCT)
    near |= same & (gap == 0) & (rel > 0) & (rel <= cfg.DUP_NEAR_AMOUNT_PCT) & (o["claim_id"] != o["claim_id"].shift())
    hits = o[near]
    out = []
    for prov, g in hits.groupby("provider_id"):
        ids = sorted(set(g["claim_id"]))
        if len(ids) < cfg.NEAR_DUP_MIN_PAIRS:
            continue
        out.append(signal(
            layer="rules", method="rule.R02_near_duplicate", name="Near-duplicate claims",
            description=f"{len(ids)} claims repeat an earlier claim for the same member and code within "
                        f"{cfg.DUP_NEAR_DAYS} day(s) at an amount within {pct(cfg.DUP_NEAR_AMOUNT_PCT)}.",
            entity_type="provider", entity_id=str(prov), claim_ids=ids, value=len(ids), comparison_value=0,
            comparison_label="expected near-duplicates", unit="claims", threshold=cfg.DUP_NEAR_DAYS, severity=3,
            strength=0.5 + min(0.5, len(ids) / 40),
            sources=[("claims", "member_id"), ("claims", "procedure_code"), ("claims", "service_date"), ("claims", "billed_amount")]))
    return out


def r03_upcoding(store: DataStore, cfg: Config, feats: pd.DataFrame) -> list[dict]:
    out = []
    today = pd.Timestamp(cfg.sim_today)
    em = store.claims[store.claims.procedure_code.eq("EM5") & store.claims.frequency_code.eq(1)]
    for prov, row in feats[feats.em_lines >= cfg.UPCODE_MIN_EM_LINES].iterrows():
        recent = row.em_lines_recent >= cfg.UPCODE_MIN_EM_LINES
        share = float(row.em5_share_recent if recent else row.em5_share)
        st = peer_stats(feats, str(prov), "em5_share", "em_lines", cfg.UPCODE_MIN_EM_LINES)
        med, p90 = st["peer_median"], st["peer_p90"]
        if st["n"] < 5 or share <= p90 * cfg.UPCODE_P90_MULT or share <= med * cfg.UPCODE_MEDIAN_MULT:
            continue
        window = f"the last {cfg.UPCODE_RECENT_MONTHS} months" if recent else "18 months"
        n_em = int(row.em_lines_recent if recent else row.em_lines)
        pval = float(binom.sf(round(share * n_em) - 1, n_em, max(med, 0.01)))
        if pval >= cfg.UPCODE_MAX_PVALUE:
            continue
        mine = em[em.provider_id == prov]
        if recent:
            mine = mine[mine.service_date >= today - pd.DateOffset(months=cfg.UPCODE_RECENT_MONTHS)]
        ratio = share / med if med > 0 else 3.0
        out.append(signal(
            layer="rules", method="rule.R03_upcoding_em_share", name="High share of top-level (EM5) visits",
            description=f"EM5 is {pct(share)} of {n_em} E&M visits in {window}; peer median {pct(med)}, "
                        f"p90 {pct(p90)} ({st['label']}, n={st['n']}).",
            entity_type="provider", entity_id=str(prov), claim_ids=list(mine["claim_id"]), value=round(share, 3),
            comparison_value=round(med, 3), comparison_label=f"peer median ({st['label']}, n={st['n']})", unit="share",
            threshold=round(p90 * cfg.UPCODE_P90_MULT, 3), severity=3, strength=0.5 + 0.5 * min(1.0, (ratio - 2) / 3),
            sources=[("claims", "procedure_code"), ("providers", "specialty"), ("providers", "state")],
            extra={"peer_p90": round(p90, 3), "percentile": st["percentile"], "window": window, "p_value": pval}))
    return out


def r04_unbundling(store: DataStore, cfg: Config, feats: pd.DataFrame) -> list[dict]:
    pairs = store.code_pairs
    comp_to_panel = dict(zip(pairs.component_code, pairs.panel_code))
    lab = store.claims[store.claims.service_type.eq("lab") & store.claims.frequency_code.eq(1)].copy()
    lab["panel"] = lab["procedure_code"].map(comp_to_panel)
    key = ["provider_id", "member_id", "service_date"]
    comps = lab.dropna(subset=["panel"]).groupby(key + ["panel"]).size()
    split = comps[comps >= 2].reset_index()[key]
    panels = lab[lab.procedure_code.isin(set(pairs.panel_code))][key + ["procedure_code"]].rename(columns={"procedure_code": "panel"})
    both = lab.dropna(subset=["panel"])[key + ["panel"]].merge(panels, on=key + ["panel"])[key]
    bad = pd.concat([split, both]).drop_duplicates()
    ids = lab.merge(bad, on=key).groupby(key)["claim_id"].agg(lambda s: sorted(set(s)))
    hits: dict[str, list] = defaultdict(list)
    for (prov, mem, day), cs in ids.items():
        hits[str(prov)].append((mem, day, cs))
    out = []
    for prov in sorted(hits):
        md = hits[prov]
        if len(md) < cfg.UNBUNDLE_MIN_MEMBER_DAYS:
            continue
        ids = sorted({c for _, _, cs in md for c in cs})
        out.append(signal(
            layer="rules", method="rule.R04_unbundling", name="Lab panels billed as separate components",
            description=f"On {len(md)} member-days the lab billed two or more components of the same panel "
                        f"separately instead of the panel code.",
            entity_type="provider", entity_id=prov, claim_ids=ids, value=len(md), comparison_value=0,
            comparison_label="member-days expected with split panels", unit="member_days",
            threshold=cfg.UNBUNDLE_MIN_MEMBER_DAYS, severity=2, strength=0.5 + min(0.5, len(md) / 100),
            sources=[("claims", "procedure_code"), ("code_pairs", "component_code"), ("claims", "service_date")]))
    return out


def r05_after_death(store: DataStore, cfg: Config, feats: pd.DataFrame) -> list[dict]:
    h = store.hdr.merge(store.members[["member_id", "date_of_death"]], on="member_id")
    bad = h[h.date_of_death.notna() & (h.service_date > h.date_of_death)]
    out = []
    for mem, g in bad.groupby("member_id"):
        days = int((g.service_date - g.date_of_death).dt.days.max())
        provs = sorted(set(g.provider_id))
        out.append(signal(
            layer="rules", method="rule.R05_service_after_death", name="Services billed after the member's death",
            description=f"{len(g)} claims for {mem} dated after the recorded date of death "
                        f"({g.date_of_death.iloc[0].date()}), up to {days} days later.",
            entity_type="member", entity_id=str(mem), entity_ids=provs, claim_ids=list(g.claim_id), value=days,
            comparison_value=0, comparison_label="days after date of death (expected none)", unit="days", threshold=0,
            severity=5, hard=True, strength=1.0,
            sources=[("claims", "service_date"), ("members", "date_of_death")]))
    for prov, g in bad.groupby("provider_id"):
        mems = sorted(set(g.member_id))
        out.append(signal(
            layer="rules", method="rule.R05_service_after_death", name="Billed services for deceased members",
            description=f"{len(g)} claims for {len(mems)} member(s) dated after their recorded date of death.",
            entity_type="provider", entity_id=str(prov), entity_ids=mems, claim_ids=list(g.claim_id), value=len(g),
            comparison_value=0, comparison_label="claims after death (expected none)", unit="claims", threshold=0,
            severity=5, hard=True, strength=1.0, sources=[("claims", "service_date"), ("members", "date_of_death")]))
    return out


def r06_during_inpatient(store: DataStore, cfg: Config, feats: pd.DataFrame) -> list[dict]:
    h = store.hdr[store.hdr.place_of_service.isin(["outpatient", "office", "home", "ambulance"])]
    m = h.merge(store.admissions, on="member_id", suffixes=("", "_adm"))
    bad = m[(m.service_date > m.admit_date) & (m.service_date < m.discharge_date) & (m.facility_id != m.facility_id_adm)]
    out = []
    for prov, g in bad.groupby("provider_id"):
        ids = sorted(set(g.claim_id))
        out.append(signal(
            layer="rules", method="rule.R06_service_during_inpatient", name="Services while the member was inpatient elsewhere",
            description=f"{len(ids)} claims dated strictly inside another facility's admission (admission and "
                        f"discharge days excluded) for {g.member_id.nunique()} member(s).",
            entity_type="provider", entity_id=str(prov), entity_ids=sorted(set(g.member_id))[:10], claim_ids=ids,
            value=len(ids), comparison_value=0, comparison_label="claims inside another facility's stay (expected none)",
            unit="claims", threshold=None, severity=4, strength=0.6 + min(0.4, len(ids) / 25),
            sources=[("claims", "service_date"), ("admissions", "admit_date"), ("admissions", "discharge_date"),
                     ("claims", "place_of_service")]))
    return out


def r07_outside_coverage(store: DataStore, cfg: Config, feats: pd.DataFrame) -> list[dict]:
    h = store.hdr.merge(store.members[["member_id", "coverage_start", "coverage_end"]], on="member_id")
    bad = h[(h.service_date < h.coverage_start) | (h.service_date > h.coverage_end)]
    out = []
    for mem, g in bad.groupby("member_id"):
        out.append(signal(
            layer="rules", method="rule.R07_outside_coverage", name="Services outside the coverage period",
            description=f"{len(g)} claims for {mem} fall outside coverage "
                        f"{g.coverage_start.iloc[0].date()} – {g.coverage_end.iloc[0].date()}.",
            entity_type="member", entity_id=str(mem), entity_ids=sorted(set(g.provider_id)), claim_ids=list(g.claim_id),
            value=len(g), comparison_value=0, comparison_label="claims outside coverage", unit="claims", threshold=None,
            severity=3, strength=0.7, sources=[("claims", "service_date"), ("members", "coverage_start"), ("members", "coverage_end")]))
    return out


def r08_impossible_hours(store: DataStore, cfg: Config, feats: pd.DataFrame) -> list[dict]:
    c = store.claims[store.claims.frequency_code.eq(1)]
    day = c.groupby(["provider_id", "service_date"]).agg(minutes=("duration_minutes", "sum"), ids=("claim_id", lambda s: sorted(set(s))))
    warn = day[day.minutes > cfg.WARN_PROVIDER_MINUTES_PER_DAY]
    out = []
    for prov, g in warn.groupby(level=0):
        hard_days = g[g.minutes > cfg.MAX_PROVIDER_MINUTES_PER_DAY]
        worst = float(g.minutes.max()) / 60
        hard = len(hard_days) > 0
        ids = sorted({i for lst in g.ids for i in lst})
        dates = ", ".join(str(d.date()) for d in g.index.get_level_values(1)[:6])
        limit = (cfg.MAX_PROVIDER_MINUTES_PER_DAY if hard else cfg.WARN_PROVIDER_MINUTES_PER_DAY) / 60
        out.append(signal(
            layer="rules", method="rule.R08_impossible_hours", name="More hours billed than fit in a day",
            description=f"Billed up to {worst:.1f} hours of services in one day on {len(g)} day(s) "
                        f"({dates}); limit {limit:.0f} hours.",
            entity_type="provider", entity_id=str(prov), claim_ids=ids, value=round(worst, 1), comparison_value=limit,
            comparison_label="hours available in a day" if hard else "warning level (hours per day)", unit="hours",
            threshold=limit, severity=5 if hard else 3, hard=hard, strength=1.0 if hard else 0.6,
            sources=[("claims", "duration_minutes"), ("claims", "service_date")],
            extra={"days": len(g), "hard_days": len(hard_days)}))
    return out


def r09_impossible_travel(store: DataStore, cfg: Config, feats: pd.DataFrame) -> list[dict]:
    h = store.hdr[store.hdr.service_type.ne("ambulance") & store.hdr.frequency_code.eq(1)]
    multi = h[h.duplicated(["member_id", "service_date"], keep=False)]
    fac = store.facility_index
    multi = multi.assign(lat=multi.facility_id.map(fac.lat), lon=multi.facility_id.map(fac.lon))
    out = []
    for (mem, day), g in multi.groupby(["member_id", "service_date"]):
        if g.facility_id.nunique() < 2:
            continue
        a = g[["lat", "lon"]].to_numpy()
        d = _hav_km(a[:, None, 0], a[:, None, 1], a[None, :, 0], a[None, :, 1])
        km = float(d.max())
        if km <= cfg.IMPOSSIBLE_TRAVEL_KM:
            continue
        cities = ", ".join(sorted(set(g.facility_id.map(fac.city))))
        out.append(signal(
            layer="rules", method="rule.R09_impossible_travel", name="Member seen in two distant places on one day",
            description=f"{mem} has services {km:.0f} km apart on {day.date()} ({cities}).",
            entity_type="member", entity_id=str(mem), entity_ids=sorted(set(g.provider_id)), claim_ids=list(g.claim_id),
            value=round(km, 1), comparison_value=cfg.IMPOSSIBLE_TRAVEL_KM, comparison_label="maximum plausible same-day distance",
            unit="km", threshold=cfg.IMPOSSIBLE_TRAVEL_KM, severity=4, strength=0.8,
            sources=[("claims", "facility_id"), ("facilities", "lat"), ("facilities", "lon"), ("claims", "service_date")]))
    return out


def r10_ambulance_miles(store: DataStore, cfg: Config, feats: pd.DataFrame) -> list[dict]:
    a = store.claims[store.claims.service_type.eq("ambulance") & store.claims.ambulance_miles.notna()].copy()
    a["map_miles"] = _hav_km(a.pickup_lat, a.pickup_lon, a.dropoff_lat, a.dropoff_lon) / KM_PER_MILE
    a["ratio"] = a.ambulance_miles / a.map_miles.clip(lower=0.1)
    a["flag"] = a.ambulance_miles > cfg.AMBULANCE_MILES_RATIO * a.map_miles + cfg.AMBULANCE_MILES_SLACK
    a["hard"] = a.flag & (a.ambulance_miles > 2 * a.map_miles)
    out = []
    for prov, g in a.groupby("provider_id"):
        f = g[g.flag]
        if len(f) < cfg.AMBULANCE_MIN_TRIPS:
            continue
        med = float(f.ratio.median())
        out.append(signal(
            layer="rules", method="rule.R10_ambulance_miles", name="Ambulance miles far above map distance",
            description=f"{len(f)} of {len(g)} trips billed a median {med:.1f}x the straight-line pickup→drop-off "
                        f"distance (max {f.ratio.max():.1f}x); allowed {cfg.AMBULANCE_MILES_RATIO}x + {cfg.AMBULANCE_MILES_SLACK} mi.",
            entity_type="provider", entity_id=str(prov), claim_ids=list(f.claim_id), value=round(med, 2),
            comparison_value=cfg.AMBULANCE_MILES_RATIO,
            comparison_label=f"allowed ratio ({cfg.AMBULANCE_MILES_RATIO}x map distance + {cfg.AMBULANCE_MILES_SLACK} mi)",
            unit="ratio", threshold=cfg.AMBULANCE_MILES_RATIO, severity=4, hard=bool(f.hard.any()),
            strength=1.0 if f.hard.any() else 0.7,
            sources=[("claims", "ambulance_miles"), ("claims", "pickup_lat"), ("claims", "pickup_lon"),
                     ("claims", "dropoff_lat"), ("claims", "dropoff_lon")],
            extra={"trips_flagged": len(f), "trips_total": len(g), "hard_trips": int(f.hard.sum())}))
    return out


def r11_excessive_frequency(store: DataStore, cfg: Config, feats: pd.DataFrame) -> list[dict]:
    fam = dict(zip(store.procedure_codes.code, store.procedure_codes.family))
    h = store.claims[store.claims.frequency_code.eq(1)].drop_duplicates("claim_id")
    h = h.assign(family=h.procedure_code.map(fam)).sort_values(["provider_id", "member_id", "family", "service_date"])
    key = ["provider_id", "member_id", "family"]
    roll = (h.set_index("service_date").groupby(key)["claim_id"].rolling("30D").count())
    df = roll.groupby(level=[0, 1, 2]).max().rename("max30").reset_index()
    df["ids"] = df.set_index(key).index.map(h.groupby(key)["claim_id"].agg(list))
    stype = h.drop_duplicates(key).set_index(key)["service_type"]
    df["service_type"] = df.set_index(key).index.map(stype)
    pairs_per_family = df.groupby("family").size()
    p99_family = df.groupby("family")["max30"].quantile(cfg.FREQ_PEER_PERCENTILE / 100)
    p99_stype = df.groupby("service_type")["max30"].quantile(cfg.FREQ_PEER_PERCENTILE / 100)
    small = df.family.map(pairs_per_family) < cfg.FREQ_MIN_FAMILY_PAIRS
    df["p99"] = np.where(small, df.service_type.map(p99_stype), df.family.map(p99_family))
    flagged = df[(df.max30 > df.p99) & (df.max30 >= 4)]
    out = []
    for prov, g in flagged.groupby("provider_id"):
        top = g.sort_values("max30", ascending=False).iloc[0]
        out.append(signal(
            layer="rules", method="rule.R11_excessive_frequency", name="Visit frequency above the 99th percentile",
            description=f"{len(g)} member(s) billed up to {int(top.max30)} '{top.family}' services in 30 days; "
                        f"peer 99th percentile is {top.p99:.0f}.",
            entity_type="provider", entity_id=str(prov), entity_ids=sorted(g.member_id)[:10],
            claim_ids=[i for lst in g.ids for i in lst], value=int(top.max30), comparison_value=round(float(top.p99), 1),
            comparison_label=f"p{cfg.FREQ_PEER_PERCENTILE} services per member per 30 days ({top.family})", unit="services_per_30d",
            threshold=cfg.FREQ_PEER_PERCENTILE, severity=2, strength=min(0.8, 0.5 + 0.05 * len(g)),
            sources=[("claims", "service_date"), ("claims", "member_id"), ("procedure_codes", "family")],
            extra={"family": top.family, "members": len(g)}))
    return out


def r12_threshold_hugging(store: DataStore, cfg: Config, feats: pd.DataFrame) -> list[dict]:
    lo, hi = cfg.THRESHOLD_HUG_LOW * cfg.review_threshold_inr, cfg.review_threshold_inr
    h = store.hdr[store.hdr.frequency_code.eq(1)]
    out = []
    cand = feats[(feats.n_claims >= cfg.THRESHOLD_HUG_MIN_CLAIMS) & (feats.in_band >= cfg.THRESHOLD_HUG_MIN_IN_BAND)]
    for prov, row in cand.iterrows():
        st = peer_stats(feats, str(prov), "band_share", "n_claims", cfg.THRESHOLD_HUG_MIN_CLAIMS)
        share, med = float(row.band_share), st["peer_median"]
        if share <= cfg.THRESHOLD_HUG_SHARE or share <= cfg.THRESHOLD_HUG_PEER_MULT * med:
            continue
        mine = h[(h.provider_id == prov) & (h.billed >= lo) & (h.billed < hi)]
        out.append(signal(
            layer="rules", method="rule.R12_threshold_hugging",
            name=f"Claims clustered just below the {inr(hi)} review threshold",
            description=f"{int(row.in_band)} of {int(row.n_claims)} claims ({pct(share)}) are billed between "
                        f"{inr(lo)} and {inr(hi - 1)}; the peer median is {pct(med)} ({st['label']}, n={st['n']}).",
            entity_type="provider", entity_id=str(prov), claim_ids=list(mine.claim_id), value=round(share, 3),
            comparison_value=round(med, 3), comparison_label=f"peer median ({st['label']}, n={st['n']})", unit="share",
            threshold=cfg.THRESHOLD_HUG_SHARE, severity=3,
            strength=0.5 + 0.5 * min(1.0, (share - cfg.THRESHOLD_HUG_SHARE) / 0.5),
            sources=[("claims", "billed_amount"), ("providers", "specialty")],
            extra={"in_band": int(row.in_band), "n_claims": int(row.n_claims), "band": [lo, hi - 1]}))
    return out


def r13_dme_overrun(store: DataStore, cfg: Config, feats: pd.DataFrame) -> list[dict]:
    d = store.claims[store.claims.rental_month.notna()]
    mx = store.dme_items.set_index("item_code")["max_rental_months"]
    d = d.assign(max_m=d.dme_item_code.map(mx))
    bad = d[d.rental_month > d.max_m]
    out = []
    for prov, g in bad.groupby("provider_id"):
        out.append(signal(
            layer="rules", method="rule.R13_dme_rental_overrun", name="DME rented beyond the allowed months",
            description=f"{len(g)} rental claims exceed the item's maximum rental months (up to month {int(g.rental_month.max())}).",
            entity_type="provider", entity_id=str(prov), claim_ids=list(g.claim_id), value=int(g.rental_month.max()),
            comparison_value=int(g.max_m.min()), comparison_label="maximum rental months for the item", unit="months",
            threshold=None, severity=2, strength=0.6, sources=[("claims", "rental_month"), ("dme_items", "max_rental_months")]))
    return out


def r14_early_refill(store: DataStore, cfg: Config, feats: pd.DataFrame) -> list[dict]:
    p = store.claims[store.claims.days_supply.notna() & store.claims.frequency_code.eq(1)].sort_values(
        ["member_id", "drug_code", "service_date"])
    same = (p.member_id == p.member_id.shift()) & (p.drug_code == p.drug_code.shift())
    gap = (p.service_date - p.service_date.shift()).dt.days
    early = same & (gap < cfg.EARLY_REFILL_FRACTION * p.days_supply.shift())
    e = p[early]
    counts = e.groupby(["provider_id", "member_id", "drug_code"]).size()
    flagged = counts[counts >= cfg.EARLY_REFILL_MIN_COUNT]
    out = []
    for prov, g in flagged.groupby(level=0):
        mems = sorted(set(g.index.get_level_values(1)))
        ids = e[(e.provider_id == prov) & e.member_id.isin(mems)].claim_id
        out.append(signal(
            layer="rules", method="rule.R14_early_refill", name="Repeated early pharmacy refills",
            description=f"{int(g.sum())} refills for {len(mems)} member(s) came before {pct(cfg.EARLY_REFILL_FRACTION)} "
                        f"of the previous supply was used.",
            entity_type="provider", entity_id=str(prov), entity_ids=mems[:10], claim_ids=list(ids), value=int(g.sum()),
            comparison_value=cfg.EARLY_REFILL_MIN_COUNT, comparison_label="early refills per member-drug to flag", unit="refills",
            threshold=cfg.EARLY_REFILL_FRACTION, severity=2, strength=0.6,
            sources=[("claims", "days_supply"), ("claims", "drug_code"), ("claims", "service_date")]))
    return out


def r15_referral_concentration(store: DataStore, cfg: Config, feats: pd.DataFrame) -> list[dict]:
    r = store.referrals
    pair = r.groupby(["to_provider_id", "from_provider_id"]).size()
    out_total = r.groupby("from_provider_id").size()
    out = []
    for to, g in pair.groupby(level=0):
        total = int(g.sum())
        if total < cfg.REFERRAL_MIN_INBOUND:
            continue
        src = g.idxmax()[1]
        share = float(g.max()) / total
        src_share = float(g.max()) / float(out_total[src])
        if share < cfg.REFERRAL_CONCENTRATION or src_share < cfg.REFERRAL_CONCENTRATION:
            continue
        refs = r[(r.to_provider_id == to) & (r.from_provider_id == src)]
        h = store.hdr
        ids = h[(h.provider_id == to) & (h.referring_provider_id == src)].claim_id
        out.append(signal(
            layer="rules", method="rule.R15_referral_concentration", name="Referrals concentrated on one source",
            description=f"{int(g.max())} of {total} inbound referrals ({pct(share)}) come from {src}, which sends "
                        f"{pct(src_share)} of its own referrals here.",
            entity_type="provider", entity_id=str(to), entity_ids=[str(src)], claim_ids=list(ids), value=round(share, 3),
            comparison_value=cfg.REFERRAL_CONCENTRATION, comparison_label="concentration threshold", unit="share",
            threshold=cfg.REFERRAL_CONCENTRATION, severity=2, strength=0.5 + 0.5 * min(1.0, (share - 0.5) / 0.5),
            sources=[("referrals", "from_provider_id"), ("referrals", "to_provider_id")],
            extra={"source": str(src), "source_share": round(src_share, 3), "referrals": len(refs)}))
    return out


def r16_identity_sharing(store: DataStore, cfg: Config, feats: pd.DataFrame) -> list[dict]:
    m = store.members
    h = store.hdr
    out = []
    for col, label in (("phone_hash", "phone number"), ("address_hash", "address")):
        vc = m[col].value_counts()
        for val in sorted(vc[vc >= cfg.IDENTITY_SHARE_MIN].index):
            mems = sorted(m.loc[m[col] == val, "member_id"])
            claims = h[h.member_id.isin(mems)]
            by_prov = claims.groupby("provider_id")["member_id"].nunique()
            provs = sorted(by_prov[by_prov >= 3].index)
            hard = len(mems) >= cfg.IDENTITY_SHARE_HARD
            out.append(signal(
                layer="rules", method="rule.R16_identity_sharing", name=f"{len(mems)} members share one {label}",
                description=f"{len(mems)} members share the same {label} (hash {val[:6]}…); "
                            f"{len(provs)} provider(s) billed 3 or more of them.",
                entity_type="member_group", entity_id=f"MGRP-{col[:2].upper()}-{val[:6]}", entity_ids=mems + provs,
                claim_ids=list(claims.claim_id), value=len(mems), comparison_value=cfg.IDENTITY_SHARE_MIN,
                comparison_label=f"members sharing a {label} needed to flag", unit="members",
                threshold=cfg.IDENTITY_SHARE_HARD if hard else cfg.IDENTITY_SHARE_MIN, severity=4, hard=hard,
                strength=1.0 if hard else 0.7, sources=[("members", col)],
                extra={"members": mems, "providers": provs, "share": col}))
    return out


RULES: list[tuple[str, Callable[[DataStore, Config, pd.DataFrame], list[dict]]]] = [
    ("R01", r01_exact_duplicate), ("R02", r02_near_duplicate), ("R03", r03_upcoding), ("R04", r04_unbundling),
    ("R05", r05_after_death), ("R06", r06_during_inpatient), ("R07", r07_outside_coverage),
    ("R08", r08_impossible_hours), ("R09", r09_impossible_travel), ("R10", r10_ambulance_miles),
    ("R11", r11_excessive_frequency), ("R12", r12_threshold_hugging), ("R13", r13_dme_overrun),
    ("R14", r14_early_refill), ("R15", r15_referral_concentration), ("R16", r16_identity_sharing),
]


def run_rules(store: DataStore, cfg: Config, feats: pd.DataFrame) -> tuple[list[dict], list[str]]:
    """Run every rule; a failing rule is logged and listed, never fatal."""
    signals, failed = [], []
    for rid, fn in RULES:
        try:
            signals.extend(fn(store, cfg, feats))
        except Exception:  # noqa: BLE001 - fail safe by design
            log.exception("rule %s failed", rid)
            failed.append(rid)
    return signals, failed
