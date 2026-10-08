"""Graph layer (spec A6) and the per-case graph (contract: case_graph.json, ≤ CASE_GRAPH_NODE_CAP nodes).

M3 builds the case subgraph from the tables (providers, owners, banks, facilities,
locations, members, claims, referrals, document authors). M4 adds the analytics
(referral cycles, shared indicators, Louvain communities, exposure, small-claims pattern).
"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd

from ..config import Config
from ..store import DataStore
from .signals import inr


def month(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m")


class CaseGraphBuilder:
    def __init__(self, store: DataStore, cfg: Config, risk: dict[str, int]):
        self.s, self.cfg, self.risk = store, cfg, risk
        self.nodes: dict[str, dict] = {}
        self.edges: dict[tuple, dict] = {}
        self.hist_start = pd.Timestamp(cfg.history_start)

    def node(self, nid: str, ntype: str, label: str, first: str, in_case: bool, attrs: dict | None = None,
             risk=None, flagged: bool | None = None) -> None:
        if nid in self.nodes:
            n = self.nodes[nid]
            n["first_seen_month"] = min(n["first_seen_month"], first)
            n["in_case"] = n["in_case"] or in_case
            return
        r = self.risk.get(nid, risk)
        self.nodes[nid] = {"id": nid, "type": ntype, "label": label, "risk": r,
                           "flagged": bool(flagged if flagged is not None else (r is not None and r >= self.cfg.ALERT_MIN_RISK)),
                           "in_case": in_case, "first_seen_month": first, "attrs": attrs or {}}

    def edge(self, src: str, dst: str, etype: str, first: str, weight: float = 1, evidence: list[str] | None = None) -> None:
        key = (src, dst, etype)
        if key in self.edges:
            e = self.edges[key]
            e["weight"] += weight
            e["first_seen_month"] = min(e["first_seen_month"], first)
            e["evidence_ids"] = sorted(set(e["evidence_ids"]) | set(evidence or []))
            return
        self.edges[key] = {"source": src, "target": dst, "type": etype, "weight": weight, "first_seen_month": first,
                           "evidence_ids": sorted(set(evidence or []))}

    def provider_first(self, pid: str) -> str:
        enr = self.s.provider_index.loc[pid, "enrolled_date"]
        return month(max(enr, self.hist_start))

    def build(self, case_no: int, providers: list[str], related: list[str], claim_ids: list[str],
              members_individual: list[str], identity_members: list[str], ev_by_claim: dict[str, list[str]],
              ev_by_kind: dict[str, list[str]], consult_authors: list[tuple[str, str, str]]) -> dict:
        s = self.s
        pidx, fidx, oidx = s.provider_index, s.facility_index, s.owners.set_index("owner_id")
        h = s.hdr[s.hdr.claim_id.isin(claim_ids)]
        owners_count = pidx.loc[providers, "owner_id"].value_counts() if providers else pd.Series(dtype=int)
        for pid in providers + related:
            p = pidx.loc[pid]
            in_case = pid in providers
            first = self.provider_first(pid)
            self.node(pid, "provider", str(p["name"]), first, in_case, {"specialty": p["specialty"], "city": p["city"]})
            own = p["owner_id"]
            shared_owner = owners_count.get(own, 0) >= 2
            self.node(own, "owner", str(oidx.loc[own, "owner_name"]), first, in_case and shared_owner)
            self.edge(pid, own, "owned_by", first, 1, ev_by_kind.get("ownership"))
            bank = f"BNK-{oidx.loc[own, 'bank_account_hash'][:4]}"
            self.node(bank, "bank", f"Bank acct ••{bank[4:]}", first, in_case and shared_owner)
            self.edge(own, bank, "uses_bank", first, 1, ev_by_kind.get("bank"))
            fac = p["primary_facility_id"]
            f = fidx.loc[fac]
            self.node(fac, "facility", str(f["name"]), first, in_case, {"facility_type": f["facility_type"]})
            self.edge(pid, fac, "practices_at", first, 1, ev_by_kind.get("ownership"))
            loc = f"LOC-{f['pincode']}"
            self.node(loc, "location", f"{f['city']} {f['pincode']}", first, False)
            self.edge(fac, loc, "located_at", first)
        # referrals among case providers
        r = s.referrals
        rr = r[r.from_provider_id.isin(providers) & r.to_provider_id.isin(providers)]
        for (a, b), g in rr.groupby(["from_provider_id", "to_provider_id"]):
            self.edge(a, b, "referral", month(g.referral_date.min()), int(len(g)), ev_by_kind.get("referral"))
        # members: individual nodes for a few (or the identity cluster), the rest as one group
        case_members = h.groupby("member_id").agg(n=("claim_id", "size"), first=("service_date", "min"))
        mi = s.member_index
        shown = set(members_individual) | set(identity_members)
        for m in sorted(shown):
            if m not in mi.index:
                continue
            first = month(case_members.loc[m, "first"]) if m in case_members.index else month(self.hist_start)
            self.node(m, "member", f"Member {m[4:]}", first, True, {"age": int(mi.loc[m, "age"])})
        rest = case_members[~case_members.index.isin(shown)]
        grp = None
        if len(rest):
            grp = f"MGRP-{case_no:04d}-A"
            self.node(grp, "member_group", f"{len(rest)} other members", month(rest["first"].min()), True,
                      {"count": int(len(rest))})
        for (m, pid), g in h[h.provider_id.isin(providers)].groupby(["member_id", "provider_id"]):
            src = m if m in shown else grp
            if src:
                self.edge(src, pid, "treated", month(g.service_date.min()), int(len(g)))
        # identity cluster links
        if identity_members:
            sub = mi.loc[[m for m in identity_members if m in mi.index]]
            for col, etype in (("phone_hash", "shares_phone"), ("address_hash", "lives_at")):
                for val, g in sub.groupby(col):
                    if len(g) < 2:
                        continue
                    if etype == "lives_at":
                        aid = f"ADR-{val[:6]}"
                        self.node(aid, "address", f"Shared address {val[:6]}", month(self.hist_start), True)
                        for m in g.index:
                            self.edge(m, aid, "lives_at", self.nodes[m]["first_seen_month"] if m in self.nodes else month(self.hist_start),
                                      1, ev_by_kind.get("identity"))
                    else:
                        anchor = g.index[0]
                        for m in g.index[1:]:
                            self.edge(m, anchor, "shares_phone", month(self.hist_start), 1, ev_by_kind.get("identity"))
        # claims: the largest individually, the rest grouped
        hc = h[h.provider_id.isin(providers + related)].sort_values(["billed", "claim_id"], ascending=[False, True])
        top = hc.head(2)
        for row in top.itertuples():
            first = month(row.service_date)
            code = s.claims.loc[s.claims.claim_id == row.claim_id, "procedure_code"].iloc[0]
            self.node(row.claim_id, "claim", f"{inr(row.billed)} · {code}", first, True,
                      {"billed_amount": int(row.billed), "service_date": str(row.service_date.date())}, flagged=True)
            self.edge(row.claim_id, row.provider_id, "billed", first, 1, ev_by_claim.get(row.claim_id))
            if row.member_id in self.nodes:
                self.edge(row.claim_id, row.member_id, "billed", first)
        others = hc.iloc[len(top):]
        if len(others):
            cg = f"CGRP-{case_no:04d}-A"
            self.node(cg, "claim_group", f"{len(others)} more claims ({inr(others.billed.sum())})",
                      month(others.service_date.min()), True, {"count": int(len(others)), "amount": int(others.billed.sum())},
                      flagged=True)
            for pid, g in others.groupby("provider_id"):
                evs = sorted({e for c in g.claim_id for e in ev_by_claim.get(c, [])})
                self.edge(cg, pid, "billed", month(g.service_date.min()), int(len(g)), evs)
        # document authors with no link to the member (inserted consults)
        for author, member, ev in consult_authors:
            p = pidx.loc[author]
            self.node(author, "provider", str(p["name"]), month(self.hist_start), False,
                      {"specialty": p["specialty"], "city": p["city"], "note": "appears only as document author"})
            if member not in self.nodes:
                self.node(member, "member", f"Member {member[4:]}", month(self.hist_start), True,
                          {"age": int(mi.loc[member, "age"])})
            self.edge(author, member, "treated", month(self.hist_start), 0, [ev])
        return self.finish(case_no)

    def finish(self, case_no: int) -> dict:
        cap = self.cfg.CASE_GRAPH_NODE_CAP
        order = sorted(self.nodes.values(), key=lambda n: (not n["in_case"], n["type"] in ("location",), n["id"]))
        keep = {n["id"] for n in order[:cap]}
        nodes = [n for n in order if n["id"] in keep]
        edges = []
        for k, e in enumerate(sorted(self.edges.values(), key=lambda e: (e["first_seen_month"], e["source"], e["target"], e["type"])), start=1):
            if e["source"] in keep and e["target"] in keep:
                edges.append({"id": f"E-{k:03d}", **e})
        return {"nodes": nodes, "edges": edges, "truncated": len(self.nodes) > cap, "node_cap": cap,
                "total_nodes": len(self.nodes), "total_edges": len(self.edges)}


def flagged_neighbor_share(store: DataStore, providers: list[str], flagged: set[str]) -> float:
    """Share of providers sharing members or referrals with the case providers that are flagged."""
    h = store.hdr
    members = set(h.loc[h.provider_id.isin(providers), "member_id"])
    neigh = set(h.loc[h.member_id.isin(members), "provider_id"])
    r = store.referrals
    neigh |= set(r.loc[r.from_provider_id.isin(providers), "to_provider_id"]) | set(r.loc[r.to_provider_id.isin(providers), "from_provider_id"])
    neigh -= set(providers)
    if not neigh:
        return 0.0
    return round(len(neigh & flagged) / len(neigh), 2)


__all__ = ["CaseGraphBuilder", "flagged_neighbor_share", "month", "defaultdict"]
