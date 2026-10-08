"""Graph analytics (spec A6) with NetworkX: referral cycles, shared indicators, provider
projection + Louvain communities, community risk, network exposure and the
"small claims, big pattern" metric. Re-exported by detect/graph.py as run()/neighbors().
"""

from __future__ import annotations

import json
from collections import defaultdict

import networkx as nx
import numpy as np
import pandas as pd

from ..config import CONFIG, Config
from ..store import DataStore
from .graph import CaseGraphBuilder
from .signals import inr, pct, signal


def _flagged_by_signals(signals: list[dict], anomaly: pd.Series) -> set[str]:
    flagged = {s["entity_id"] for s in signals
               if s["direction"] == "incriminating" and s["entity_type"] == "provider" and s["layer"] == "rules"}
    flagged |= set(anomaly[anomaly >= 0.99].index)
    return flagged


def referral_cycles(store: DataStore, cfg: Config) -> list[tuple[str, ...]]:
    r = store.referrals
    pair = r.groupby(["from_provider_id", "to_provider_id"]).size()
    inbound = r.groupby("to_provider_id").size()
    g = nx.DiGraph()
    for (a, b), n in pair.items():
        if n >= 3 and n / inbound[b] >= cfg.REFERRAL_CONCENTRATION:
            g.add_edge(a, b, weight=int(n))
    cycles = set()
    for cyc in nx.simple_cycles(g, length_bound=cfg.REFERRAL_CYCLE_MAX_LEN):
        if len(cyc) >= 2:
            k = cyc.index(min(cyc))
            cycles.add(tuple(cyc[k:] + cyc[:k]))
    return sorted(cycles)


def projection(store: DataStore) -> tuple[dict[tuple[str, str], dict], dict[str, set[str]]]:
    """Provider–provider ties: shared members, referrals, shared owner/bank/facility."""
    h = store.hdr[store.hdr.frequency_code.eq(1)]
    members_of = h.groupby("provider_id")["member_id"].apply(set).to_dict()
    ties: dict[tuple[str, str], dict] = defaultdict(lambda: {"shared": 0, "referrals": 0, "owner": 0, "bank": 0, "facility": 0})
    by_member = h.drop_duplicates(["member_id", "provider_id"]).groupby("member_id")["provider_id"].apply(sorted)
    for provs in by_member:
        if 2 <= len(provs) <= 12:
            for i in range(len(provs)):
                for j in range(i + 1, len(provs)):
                    ties[(provs[i], provs[j])]["shared"] += 1
    r = store.referrals.groupby(["from_provider_id", "to_provider_id"]).size()
    for (a, b), n in r.items():
        ties[(min(a, b), max(a, b))]["referrals"] += int(n)
    p = store.provider_index
    for col, tag in (("owner_id", "owner"), ("bank_account_hash", "bank"), ("primary_facility_id", "facility")):
        for _, grp in p.groupby(col):
            ids = sorted(grp.index)
            if 2 <= len(ids) <= 12:
                for i in range(len(ids)):
                    for j in range(i + 1, len(ids)):
                        ties[(ids[i], ids[j])][tag] = 1
    return ties, members_of


def tie_weight(t: dict, a: str, b: str, members_of: dict[str, set[str]]) -> tuple[float, float]:
    ma, mb = members_of.get(a, set()), members_of.get(b, set())
    jac = t["shared"] / max(1, len(ma | mb))
    w = ((jac if (jac >= 0.05 and t["shared"] >= 3) else 0.0) + min(1.0, t["referrals"] / 10)
         + t["owner"] + t["bank"] + 0.5 * t["facility"])
    return w, jac


def run(store: DataStore, cfg: Config, feats: pd.DataFrame, context: dict) -> list[dict]:
    signals_so_far = context.get("signals", [])
    anomaly = context.get("anomaly_score", pd.Series(dtype=float))
    flagged = _flagged_by_signals(signals_so_far, anomaly)
    p = store.provider_index
    h = store.hdr[store.hdr.frequency_code.eq(1)]
    out: list[dict] = []
    links: list[tuple[str, str]] = []

    # 1. referral cycles
    for cyc in referral_cycles(store, cfg):
        ids = h[h.provider_id.isin(cyc) & h.referring_provider_id.isin(cyc)]
        hops = " → ".join(list(cyc) + [cyc[0]])
        for pid in cyc:
            out.append(signal(
                layer="graph", method="graph.referral_cycle", name=f"Closed referral loop of {len(cyc)} providers",
                description=f"Referrals run in a closed loop {hops}; each hop carries ≥ {pct(cfg.REFERRAL_CONCENTRATION)} "
                            f"of the next provider's inbound referrals.",
                entity_type="provider", entity_id=pid, entity_ids=list(cyc), claim_ids=list(ids[ids.provider_id == pid].claim_id),
                value=len(cyc), comparison_value=0, comparison_label="closed referral loops expected", unit="providers",
                threshold=cfg.REFERRAL_CYCLE_MAX_LEN, severity=4, strength=0.9,
                sources=[("referrals", "from_provider_id"), ("referrals", "to_provider_id")]))
        links += [(cyc[0], x) for x in cyc[1:]]

    # 2. shared indicators
    pr = p.reset_index()
    for bank, grp in pr.groupby("bank_account_hash"):
        if grp.owner_id.nunique() >= 2 and len(grp) <= 12:
            ids = sorted(grp.provider_id)
            for pid in ids:
                out.append(signal(
                    layer="graph", method="graph.shared_bank", name="One bank account behind different owners",
                    description=f"{grp.owner_id.nunique()} different owners ({', '.join(sorted(set(grp.owner_id)))}) are paid "
                                f"into the same bank account (••{str(bank)[:4]}), covering {len(ids)} providers.",
                    entity_type="provider", entity_id=pid, entity_ids=ids + sorted(set(grp.owner_id)),
                    value=int(grp.owner_id.nunique()), comparison_value=1, comparison_label="owners per bank account (expected 1)",
                    unit="owners", threshold=None, severity=4, strength=0.75,
                    sources=[("owners", "bank_account_hash"), ("providers", "owner_id")]))
            links += [(ids[0], x) for x in ids[1:]]
    for col, label in (("owner_id", "owner"), ("primary_facility_id", "facility")):
        for key, grp in pr.groupby(col):
            ids = sorted(grp.provider_id)
            hot = [x for x in ids if x in flagged]
            if not (2 <= len(ids) <= 12) or len(hot) < 2:
                continue
            for pid in hot:
                out.append(signal(
                    layer="graph", method="graph.shared_indicators", name=f"Flagged providers sharing one {label}",
                    description=f"{len(hot)} of the {len(ids)} providers sharing {label} {key} have billing anomalies or rule "
                                f"hits ({', '.join(hot)}); a shared {label} alone is common for legitimate groups.",
                    entity_type="provider", entity_id=pid, entity_ids=hot + [str(key)], value=len(hot), comparison_value=len(ids),
                    comparison_label=f"providers sharing the {label}", unit="providers", threshold=2, severity=3, strength=0.6,
                    sources=[("providers", col)]))
            links += [(hot[0], x) for x in hot[1:]]

    # 3. projection + Louvain communities
    ties, members_of = projection(store)
    g = nx.Graph()
    jac_of = {}
    for (a, b), t in sorted(ties.items()):
        w, jac = tie_weight(t, a, b, members_of)
        jac_of[(a, b)] = jac
        if w > 0:
            g.add_edge(a, b, weight=w)
    comms = nx.community.louvain_communities(g, weight="weight", resolution=cfg.LOUVAIN_RESOLUTION, seed=cfg.seed) \
        if g.number_of_edges() else []
    comms = sorted((sorted(c) for c in comms), key=lambda c: (-len(c), c[0]))
    community_of, community_size = {}, {}
    for k, c in enumerate(comms, start=1):
        for pid in c:
            community_of[pid] = f"COM-{k:03d}"
            community_size[pid] = len(c)
    context.update({"community_of": community_of, "community_size": community_size, "projection": g,
                    "communities": comms, "flagged_providers": flagged})
    context["network_exposure"] = {n: round(sum(1 for x in g.neighbors(n) if x in flagged) / max(1, g.degree(n)), 3)
                                   for n in g.nodes}
    city = p["city"]
    unrelated = [jac_of[k] for k, t in ties.items() if t["owner"] == 0 and t["facility"] == 0 and t["bank"] == 0
                 and city.get(k[0]) == city.get(k[1])]
    base_jac = float(np.median(unrelated)) if unrelated else 0.0

    # 4–6. community risk and the small-claims pattern
    lo, hi = cfg.THRESHOLD_HUG_LOW * cfg.review_threshold_inr, cfg.review_threshold_inr
    for c in comms:
        hot = [x for x in c if x in flagged]
        if len(c) < 2 or len(c) > 40 or len(hot) < 2:
            continue
        mem = set().union(*(members_of.get(x, set()) for x in hot))
        pair_j = [jac_of.get((min(a, b), max(a, b)), 0.0) for i, a in enumerate(hot) for b in hot[i + 1:]]
        jac = max(pair_j) if pair_j else 0.0
        anom = float(anomaly.reindex(hot).fillna(0).mean())
        own = sorted(set(p.loc[hot, "owner_id"]))
        facs = sorted(set(p.loc[hot, "primary_facility_id"]))
        tie_txt = []
        if len(own) == 1:
            tie_txt.append(f"share owner {own[0]}")
        if len(facs) == 1:
            tie_txt.append(f"facility {facs[0]}")
        cid = community_of[hot[0]]
        joined = (" and ".join(tie_txt) + ", and ") if tie_txt else ""
        for pid in hot:
            out.append(signal(
                layer="graph", method="graph.louvain_community",
                name=f"{len(hot)} flagged providers form one tightly linked community",
                description=f"{', '.join(hot)} {joined}treat an overlapping pool of {len(mem)} members (Jaccard {jac:.2f}); "
                            f"community {cid} has {len(c)} providers, mean anomaly {anom:.2f}.",
                entity_type="provider", entity_id=pid, entity_ids=hot + own + facs, value=round(jac, 2),
                comparison_value=round(base_jac, 2), comparison_label="median member overlap between unrelated same-city providers",
                unit="jaccard", threshold=0.05, severity=4,
                strength=0.55 + 0.25 * min(1.0, (len(hot) - 1) / 3) + (0.1 if len(own) == 1 else 0.0),
                sources=[("providers", "owner_id"), ("providers", "primary_facility_id"), ("claims", "member_id")],
                extra={"community_id": cid, "community_size": len(c)}))
        links += [(hot[0], x) for x in hot[1:]]
        sub = h[h.provider_id.isin(hot)]
        band = sub[(sub.billed >= lo) & (sub.billed < hi)].sort_values(["service_date", "claim_id"])
        if len(band) < 20 or len(band) / len(sub) < 0.4:
            continue
        d = band.service_date.to_numpy()
        gaps = np.diff(d) / np.timedelta64(1, "D")
        linked = int(1 + (gaps <= cfg.TEMPORAL_WINDOW_DAYS).sum())
        span = int((band.service_date.max() - band.service_date.min()).days)
        for pid in hot:
            out.append(signal(
                layer="graph", method="graph.small_claims_pattern",
                name=f"{len(band)} connected mid-value claims, none above the threshold individually",
                description=f"No single claim exceeds {inr(band.billed.max())}, but the {len(band)} connected claims across "
                            f"{len(hot)} providers total {inr(band.billed.sum())} over {span} days "
                            f"({linked} within {cfg.TEMPORAL_WINDOW_DAYS} days of the previous one).",
                entity_type="provider", entity_id=pid, entity_ids=hot, claim_ids=list(band.claim_id),
                value=int(band.billed.sum()), comparison_value=int(band.billed.max()), comparison_label="largest single claim",
                unit="inr", threshold=None, severity=4, strength=0.85,
                sources=[("claims", "billed_amount"), ("claims", "service_date")],
                extra={"connected_claims": len(band), "linked_within_window": linked, "span_days": span}))
    context["case_links"] = links
    return out


_NETWORK: dict = {}


def neighbors(entity_id: str, depth: int) -> dict:
    """Ego network for the 'Ask the Case' tool (same node/edge shape as the case graph)."""
    from ..router import ApiError

    if "store" not in _NETWORK or _NETWORK.get("raw") != CONFIG.raw_dir:
        _NETWORK.update(store=DataStore(CONFIG.raw_dir), raw=CONFIG.raw_dir)
    s: DataStore = _NETWORK["store"]
    risk = {}
    ent_path = CONFIG.processed_dir / "entities.json"
    if ent_path.exists():
        risk = {k: v["risk"] for k, v in json.loads(ent_path.read_text(encoding="utf-8")).items()}
    if entity_id.startswith("PRV-") and entity_id in s.provider_index.index:
        providers = [entity_id]
        if depth == 2:
            r = s.referrals
            partners = (set(r.loc[r.from_provider_id == entity_id, "to_provider_id"])
                        | set(r.loc[r.to_provider_id == entity_id, "from_provider_id"]))
            own = s.provider_index.loc[entity_id, "owner_id"]
            partners |= set(s.provider_index.index[s.provider_index.owner_id == own])
            providers = sorted({entity_id} | set(sorted(partners)[:15]))
        members: list[str] = []
    elif entity_id.startswith("MEM-") and entity_id in s.member_index.index:
        providers = sorted(set(s.hdr.loc[s.hdr.member_id == entity_id, "provider_id"]))[:20]
        members = [entity_id]
    else:
        raise ApiError(404, "not_found", f"{entity_id} not found")
    claims = sorted(s.hdr.loc[s.hdr.provider_id.isin(providers), "claim_id"])[:500]
    g = CaseGraphBuilder(s, CONFIG, risk).build(0, providers, [], claims, members, [], {}, {}, [])
    return {"entity_id": entity_id, "nodes": g["nodes"], "edges": g["edges"]}
