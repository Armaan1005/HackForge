"""Case builder + evidence pool (spec A9).

Open alerts (entities with fused risk >= ALERT_MIN_RISK that were not exonerated) are
grouped with union-find over: entities named together in one signal, providers sharing an
owner or primary facility, and graph links (communities, cycles) supplied by the graph
layer. Components whose top risk reaches CASE_MIN_RISK become cases, numbered by risk.
"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from .config import Config
from .detect.graph import CaseGraphBuilder, flagged_neighbor_share
from .detect.signals import inr
from .store import DataStore

PATTERN_WEIGHTS: dict[str, dict[str, float]] = {
    "claim_splitting_network": {"rule.R12_threshold_hugging": 1.5, "graph.small_claims_pattern": 1.0},
    "referral_ring": {"rule.R15_referral_concentration": 1.0, "graph.referral_cycle": 1.5, "graph.shared_bank": 1.0},
    "phantom_services": {"rule.R10_ambulance_miles": 1.5, "rule.R06_service_during_inpatient": 1.0},
    "upcoding_drift": {"rule.R03_upcoding_em_share": 1.0, "temporal.em5_drift": 1.5},
    "duplicate_billing": {"rule.R01_exact_duplicate": 1.0, "rule.R02_near_duplicate": 0.8},
    "identity_cluster": {"rule.R16_identity_sharing": 1.5, "rule.R07_outside_coverage": 0.5},
    "unbundling": {"rule.R04_unbundling": 1.0},
    "impossible_timing": {"rule.R08_impossible_hours": 1.5, "rule.R09_impossible_travel": 1.2},
}
OPNOTE_CODES = {"ORT-101", "ORT-214", "ORT-219", "CAR-410", "NEP-110", "ONC-210"}
TYPE_OF_LAYER = {"rules": "rule", "anomaly": "anomaly", "temporal": "temporal", "graph": "graph"}
EVENT_OF_METHOD = {
    "rule.R12_threshold_hugging": "threshold_hugging", "rule.R01_exact_duplicate": "duplicate_billing",
    "rule.R02_near_duplicate": "duplicate_billing", "rule.R03_upcoding_em_share": "upcoding",
    "rule.R04_unbundling": "unbundling", "rule.R05_service_after_death": "service_after_death",
    "rule.R06_service_during_inpatient": "service_during_inpatient", "rule.R08_impossible_hours": "impossible_hours",
    "rule.R09_impossible_travel": "impossible_travel", "rule.R10_ambulance_miles": "ambulance_miles",
    "rule.R11_excessive_frequency": "excessive_frequency", "rule.R15_referral_concentration": "referral_concentration",
}


class UnionFind:
    def __init__(self, items):
        self.p = {x: x for x in items}

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        if a in self.p and b in self.p:
            ra, rb = self.find(a), self.find(b)
            if ra != rb:
                self.p[max(ra, rb)] = min(ra, rb)


def group_alerts(store: DataStore, entities: dict, signals: list[dict], open_ids: set[str],
                 extra_links: list[tuple[str, str]] | None = None) -> list[list[str]]:
    uf = UnionFind(sorted(open_ids))
    for eid in sorted(open_ids):
        ent = entities[eid]
        for i in ent["signals"]:
            for other in signals[i]["entity_ids"]:
                if other in open_ids:
                    uf.union(eid, other)
    provs = [e for e in open_ids if e.startswith("PRV-")]
    pidx = store.provider_index
    for col in ("owner_id",):
        by: dict[str, list[str]] = defaultdict(list)
        for pid in sorted(provs):
            by[pidx.loc[pid, col]].append(pid)
        for members in by.values():
            for other in members[1:]:
                uf.union(members[0], other)
    for a, b in extra_links or []:
        uf.union(a, b)
    comps: dict[str, list[str]] = defaultdict(list)
    for x in sorted(open_ids):
        comps[uf.find(x)].append(x)
    return list(comps.values())


def pick_pattern(sigs: list[dict]) -> str:
    methods = {s["method"] for s in sigs}
    score: dict[str, float] = defaultdict(float)
    for s in sigs:
        for pat, wts in PATTERN_WEIGHTS.items():
            if s["method"] in wts:
                score[pat] += wts[s["method"]] * s["strength"] * s["severity"]
        if s["method"] == "rule.R05_service_after_death":
            target = "identity_cluster" if "rule.R16_identity_sharing" in methods else "phantom_services"
            score[target] += 1.0 * s["strength"] * s["severity"]
    if not score:
        return "mixed"
    return max(sorted(score), key=lambda k: score[k])


def entity_name(store: DataStore, eid: str, sigs: list[dict]) -> str:
    if eid.startswith("PRV-"):
        return str(store.provider_index.loc[eid, "name"])
    if eid.startswith("MEM-"):
        return f"Member {eid[4:]}"
    if eid.startswith("MGRP-"):
        s = next((x for x in sigs if x["entity_id"] == eid), None)
        return s["name"] if s else eid
    return eid


def title_for(pattern: str, store: DataStore, providers: list[str], sigs: list[dict], n_members: int) -> str:
    pidx = store.provider_index
    first = str(pidx.loc[providers[0], "name"]) if providers else ""
    shared_owner = len(providers) > 1 and pidx.loc[providers, "owner_id"].nunique() == 1
    by = {s["method"]: s for s in sigs}
    if pattern == "claim_splitting_network":
        tail = " sharing one owner" if shared_owner else ""
        return f"Claim-splitting network across {len(providers)} provider{'s' if len(providers) > 1 else ''}{tail}"
    if pattern == "referral_ring":
        return f"Referral loop among {len(providers)} providers"
    if pattern == "phantom_services":
        if "rule.R10_ambulance_miles" in by:
            return f"Ambulance miles billed at {by['rule.R10_ambulance_miles']['value']}x map distance"
        return f"Services that could not have happened at {first}"
    if pattern == "upcoding_drift":
        return f"Top-level visit share rising at {first}"
    if pattern == "duplicate_billing":
        return f"Duplicate claims billed by {first}"
    if pattern == "identity_cluster":
        return f"Identity cluster: {n_members} members sharing contact details"
    if pattern == "unbundling":
        return f"Lab panels unbundled at {first}"
    if pattern == "impossible_timing":
        if "rule.R08_impossible_hours" in by:
            return f"{by['rule.R08_impossible_hours']['value']} hours billed in one day by {first}"
        s = by.get("rule.R09_impossible_travel")
        return f"Member seen {s['value']:.0f} km apart on the same day" if s else "Impossible timing"
    return f"Unusual billing pattern at {first}" if first else "Unusual billing pattern"


def evidence_from_signal(s: dict, ev_id: str) -> dict:
    return {
        "evidence_id": ev_id, "type": TYPE_OF_LAYER.get(s["layer"], s["layer"]), "method": s["method"], "name": s["name"],
        "description": s["description"], "direction": s["direction"], "entity_ids": s["entity_ids"][:12],
        "claim_ids": s["claim_ids"][:25], "claim_count": len(s["claim_ids"]), "value": s["value"],
        "comparison_value": s["comparison_value"], "comparison_label": s["comparison_label"], "unit": s["unit"],
        "threshold": s["threshold"], "severity": s["severity"], "hard": s["hard"], "weight": 0.0, "sources": s["sources"],
    }


def build_cases(store: DataStore, cfg: Config, entities: dict, signals: list[dict], open_ids: set[str],
                doc_flags: dict[str, list[dict]], extra_links: list[tuple[str, str]] | None = None,
                extra_evidence: dict[str, list[dict]] | None = None) -> list[dict]:
    comps = group_alerts(store, entities, signals, open_ids, extra_links)
    risk = {eid: e["risk"] for eid, e in entities.items()}
    flagged = {eid for eid, e in entities.items() if e["risk"] >= cfg.ALERT_MIN_RISK and eid.startswith("PRV-")}
    raw_cases = []
    for comp in comps:
        top = max(risk[e] for e in comp)
        if top < cfg.CASE_MIN_RISK:
            continue
        groups = [e for e in comp if e.startswith("MGRP-")]
        provs = sorted([e for e in comp if e.startswith("PRV-")], key=lambda e: (-risk[e], e))
        mems = sorted([e for e in comp if e.startswith("MEM-")], key=lambda e: (-risk[e], e))
        if groups:
            primary = max(groups, key=lambda g: (len(next(signals[i] for i in entities[g]["signals"])["entity_ids"]), g))
        elif provs:
            primary = provs[0]
        else:
            primary = mems[0]
        raw_cases.append((top, primary, comp, provs, mems, groups))
    raw_cases.sort(key=lambda t: (-t[0], t[1]))

    docs = store.documents
    doc_claims = defaultdict(list)
    for row in docs.itertuples(index=False):
        for cid in str(row.claim_ids).split("|"):
            doc_claims[cid].append(row)
    cases = []
    for n, (top, primary, comp, provs, mems, groups) in enumerate(raw_cases, start=1):
        sigs = [signals[i] for e in comp for i in entities[e]["signals"]]
        sigs.sort(key=lambda s: (-s["strength"] * s["severity"], s["method"], s["entity_id"]))
        identity_members = sorted({m for g in groups for s in sigs if s["entity_id"] == g for m in s["extra"].get("members", [])})
        related = sorted({x for s in sigs for x in s["entity_ids"] if x.startswith("PRV-") and x not in provs})
        claim_ids = sorted({c for s in sigs for c in s["claim_ids"]})
        evidence: list[dict] = []
        ev_by_claim: dict[str, list[str]] = defaultdict(list)
        ev_by_kind: dict[str, list[str]] = defaultdict(list)

        def next_id(prefix: str = "EV") -> str:
            return f"{prefix}-{n:04d}-{len(evidence) + 1:02d}"

        for s in sigs:
            ev = evidence_from_signal(s, next_id())
            evidence.append(ev)
            for c in s["claim_ids"]:
                ev_by_claim[c].append(ev["evidence_id"])
            if s["method"] in ("rule.R15_referral_concentration", "graph.referral_cycle"):
                ev_by_kind["referral"].append(ev["evidence_id"])
            if s["method"] == "rule.R16_identity_sharing":
                ev_by_kind["identity"].append(ev["evidence_id"])
            if s["method"] in ("graph.shared_indicators", "graph.louvain_community"):
                ev_by_kind["ownership"].append(ev["evidence_id"])
            if s["method"] == "graph.shared_bank":
                ev_by_kind["bank"].append(ev["evidence_id"])
        for e in sorted(comp):
            for ev in (extra_evidence or {}).get(e, []):
                evidence.append({**ev, "evidence_id": next_id()})
        # document cross-checks on the case's claims
        case_docs, consult_authors = [], []
        seen_docs = set()
        for cid in claim_ids:
            for row in doc_claims.get(cid, []):
                if row.document_id in seen_docs:
                    continue
                seen_docs.add(row.document_id)
                case_docs.append(row)
        for row in sorted(case_docs, key=lambda r: r.document_id):
            for fl in doc_flags.get(row.document_id, []):
                ev = {
                    "evidence_id": next_id(), "type": "document", "method": f"document.{fl['check']}", "name": fl["name"],
                    "description": fl["description"], "direction": "incriminating", "entity_ids": fl["entity_ids"],
                    "claim_ids": fl["claim_ids"], "claim_count": len(fl["claim_ids"]), "value": fl["value"],
                    "comparison_value": fl["comparison_value"], "comparison_label": fl["comparison_label"],
                    "unit": fl["unit"], "threshold": None, "severity": fl["severity"], "hard": False, "weight": 0.0,
                    "sources": fl["sources"],
                }
                evidence.append(ev)
                for c in fl["claim_ids"]:
                    ev_by_claim[c].append(ev["evidence_id"])
                if fl["check"] == "inserted_consult_author_unlinked":
                    consult_authors.append((fl["entity_ids"][0], fl["entity_ids"][1], ev["evidence_id"]))
        # history (defense material when clean)
        inv = store.investigations
        since = pd.Timestamp(cfg.sim_today) - pd.DateOffset(months=36)
        mine = inv[inv.provider_id.isin(provs) & (inv.opened_date >= since)]
        if provs:
            confirmed = mine[mine.outcome == "confirmed"]
            if len(confirmed):
                evidence.append({
                    "evidence_id": next_id(), "type": "history", "method": "history.prior_investigations",
                    "name": "Prior confirmed SIU investigation", "description":
                    f"{len(confirmed)} confirmed SIU investigation(s) in the last 36 months among the case providers "
                    f"({', '.join(sorted(set(confirmed.provider_id)))}).", "direction": "incriminating",
                    "entity_ids": sorted(set(confirmed.provider_id)), "claim_ids": [], "claim_count": 0,
                    "value": int(len(confirmed)), "comparison_value": 0, "comparison_label": "confirmed investigations in 36 months",
                    "unit": "count", "threshold": None, "severity": 2, "hard": False, "weight": 0.0,
                    "sources": [{"table": "investigations", "column": "outcome"}]})
            else:
                who = f"None of the {len(provs)} providers has a" if len(provs) > 1 else f"{provs[0]} has no"
                evidence.append({
                    "evidence_id": next_id(), "type": "history", "method": "history.prior_investigations",
                    "name": "No prior confirmed SIU investigations",
                    "description": f"{who} a confirmed SIU investigation in the last 36 months "
                                   f"({len(mine)} investigation(s) opened, none confirmed).",
                    "direction": "exculpatory", "entity_ids": provs, "claim_ids": [], "claim_count": 0, "value": 0,
                    "comparison_value": None, "comparison_label": "confirmed investigations in 36 months", "unit": "count",
                    "threshold": None, "severity": 1, "hard": False, "weight": 0.0,
                    "sources": [{"table": "investigations", "column": "provider_id"}]})
        # weights: share of incriminating strength (documents/history carry no weight in the score)
        inc = [(ev, s) for ev, s in zip(evidence, sigs) if s["direction"] == "incriminating"]
        total = sum(s["strength"] for _, s in inc) or 1.0
        for ev, s in inc:
            ev["weight"] = round(s["strength"] / total, 2)

        h = store.hdr[store.hdr.claim_id.isin(claim_ids)]
        pattern = pick_pattern(sigs)
        n_members = len(identity_members) if identity_members else int(h.member_id.nunique())
        cases.append({
            "n": n, "case_id": f"CASE-{n:04d}", "pattern": pattern,
            "title": title_for(pattern, store, provs, sigs, n_members), "primary": primary, "providers": provs,
            "members": mems, "groups": groups, "identity_members": identity_members, "related": related,
            "entities_risk": {e: risk[e] for e in comp}, "signals": sigs, "claim_ids": claim_ids, "hdr": h,
            "evidence": evidence, "ev_by_claim": ev_by_claim, "ev_by_kind": ev_by_kind, "consult_authors": consult_authors,
            "documents": case_docs, "risk": top,
            "flagged_neighbor_share": flagged_neighbor_share(store, provs, flagged) if provs else 0.0,
        })
    return cases


def missing_documents(store: DataStore, case: dict) -> list[dict]:
    h = case["hdr"]
    have = defaultdict(set)
    for row in case["documents"]:
        for cid in str(row.claim_ids).split("|"):
            have[cid].add(row.doc_type)
    c = store.claims[store.claims.claim_id.isin(case["claim_ids"])]
    out = []
    op = sorted(set(c.loc[c.procedure_code.isin(OPNOTE_CODES), "claim_id"]))
    missing_op = [cid for cid in op if "operative_note" not in have[cid]]
    if missing_op:
        codes = sorted(set(c.loc[c.claim_id.isin(missing_op) & c.procedure_code.isin(OPNOTE_CODES), "procedure_code"]))
        out.append({"doc_type": "operative_note", "claim_ids": missing_op[:25], "claim_count": len(missing_op),
                    "critical": True, "why": f"Procedure claims {'/'.join(codes)} require an operative note"})
    ipd = sorted(set(c.loc[c.procedure_code == "FAC-IPD", "claim_id"]))
    missing_ds = [cid for cid in ipd if "discharge_summary" not in have[cid]]
    if missing_ds:
        out.append({"doc_type": "discharge_summary", "claim_ids": missing_ds[:25], "claim_count": len(missing_ds),
                    "critical": False, "why": "Inpatient stays require a discharge summary"})
    ref = h[h.referring_provider_id != ""]
    if len(ref):
        r = store.referrals
        keys = set(zip(r.from_provider_id, r.to_provider_id, r.member_id))
        no_rec = sorted(cid for cid, a, b, m in zip(ref.claim_id, ref.referring_provider_id, ref.provider_id, ref.member_id)
                        if (a, b, m) not in keys)
        if no_rec:
            out.append({"doc_type": "referral_letter", "claim_ids": no_rec[:25], "claim_count": len(no_rec), "critical": False,
                        "why": f"{len(no_rec)} claims list a referring provider with no referral record"})
    return out


def timeline(store: DataStore, cfg: Config, case: dict, doc_flags: dict[str, list[dict]]) -> list[dict]:
    h = case["hdr"]
    events = []
    hist = pd.Timestamp(cfg.history_start)
    pidx = store.provider_index
    for pid in case["providers"]:
        enr = pidx.loc[pid, "enrolled_date"]
        if enr >= hist:
            events.append({"date": str(enr.date()), "event_type": "enrolment", "description": f"{pid} enrolled",
                           "evidence_ids": [], "claim_ids": []})
    if len(h):
        first = h.sort_values(["service_date", "claim_id"]).iloc[0]
        events.append({"date": str(first.service_date.date()), "event_type": "first_claim",
                       "description": f"First implicated claim {first.claim_id}", "evidence_ids": [], "claim_ids": [first.claim_id]})
    seen = set()
    for ev in case["evidence"]:
        et = EVENT_OF_METHOD.get(ev["method"])
        if not et or not ev["claim_ids"] or (et, tuple(ev["entity_ids"][:1])) in seen:
            continue
        seen.add((et, tuple(ev["entity_ids"][:1])))
        sub = h[h.claim_id.isin(ev["claim_ids"])]
        if sub.empty:
            continue
        row = sub.sort_values(["service_date", "claim_id"]).iloc[0]
        events.append({"date": str(row.service_date.date()), "event_type": et,
                       "description": f"First of {ev['claim_count']} claims: {ev['name'].lower()}",
                       "evidence_ids": [ev["evidence_id"]], "claim_ids": [row.claim_id]})
    for m in case["identity_members"] + case["members"]:
        dod = store.member_index.loc[m, "date_of_death"]
        if pd.notna(dod):
            events.append({"date": str(dod.date()), "event_type": "member_death", "description": f"{m} recorded deceased",
                           "evidence_ids": [], "claim_ids": []})
    for row in case["documents"]:
        fl = doc_flags.get(row.document_id, [])
        if not fl:
            continue
        evs = [e["evidence_id"] for e in case["evidence"] if e["type"] == "document" and row.document_id in e["description"]]
        events.append({"date": str(row.created_at)[:10], "event_type": "document_created",
                       "description": f"{row.document_id} created ({', '.join(sorted({f['check'] for f in fl}))})",
                       "evidence_ids": evs[:3], "claim_ids": [str(row.claim_ids).split('|')[0]]})
    pend = h[h.payment_release_date > pd.Timestamp(cfg.sim_today)]
    if len(pend):
        nxt = pend.payment_release_date.min()
        events.append({"date": str(nxt.date()), "event_type": "payment_release",
                       "description": f"{len(pend)} pending claims worth {inr(pend.allowed.sum())} scheduled for release",
                       "evidence_ids": [], "claim_ids": []})
    events.sort(key=lambda e: (e["date"], e["event_type"]))
    if len(events) > 14:
        events = events[:7] + events[-7:]
    return events


def case_graph(store: DataStore, cfg: Config, case: dict, risk: dict[str, int]) -> dict:
    h = case["hdr"]
    top_members = list(h.groupby("member_id").size().sort_values(ascending=False).index[:1])
    b = CaseGraphBuilder(store, cfg, risk)
    g = b.build(case["n"], case["providers"], case["related"], case["claim_ids"], top_members,
                case["identity_members"], case["ev_by_claim"], case["ev_by_kind"], case["consult_authors"])
    return {"case_id": case["case_id"], **g}
