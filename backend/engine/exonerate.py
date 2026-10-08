"""Exoneration filter (spec A8). Deterministic: try to explain every alert away before a
human sees it. An alert is cleared only when *every* incriminating signal is explained and
none is hard; partial explanations stay open and become exculpatory evidence (Defense).
"""

from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np
import pandas as pd

from .config import Config
from .store import DataStore

VOLUME_DRIVERS = {"claims_per_member", "n_members", "new_member_share", "billed_per_member", "avg_billed_per_claim",
                  "weekend_share", "max_daily_hours", "avg_distance_member_km"}
CASEMIX_DRIVERS = {"em5_share", "billed_per_member", "avg_billed_per_claim", "case_mix_index", "code_mix_kl", "claims_per_member",
                   "max_daily_hours"}
BILLING_Z = ["em5_share", "billed_per_member", "avg_billed_per_claim", "band_share", "claims_per_member", "code_mix_kl"]
NAMES = {"EX1": "EX1_sole_provider", "EX2": "EX2_case_mix_adjusted", "EX3": "EX3_corrected_claim",
         "EX4": "EX4_event_or_seasonal", "EX5": "EX5_chronic_schedule", "EX6": "EX6_network_explained"}


def _hav(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = (np.radians(np.asarray(x, float)) for x in (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


class Explainer:
    def __init__(self, store: DataStore, cfg: Config, feats: pd.DataFrame, context: dict):
        self.s, self.cfg, self.f, self.ctx = store, cfg, feats, context
        self.z = context.get("anomaly_z", pd.DataFrame())
        self._event = None

    # ---------------------------------------------------------------- facts
    def sole_provider(self, pid: str) -> dict | None:
        p = self.s.provider_index
        row = p.loc[pid]
        same = p[(p.provider_type == row.provider_type) & (p.specialty == row.specialty) & (p.index != pid)]
        if same.empty:
            return None
        km = float(_hav(row.lat, row.lon, same.lat, same.lon).min())
        if km <= self.cfg.SOLE_PROVIDER_KM:
            return None
        fac = self.s.facility_index
        peers = self.f[(self.f.provider_type == row.provider_type) & (self.f.specialty == row.specialty)
                       & (p.reindex(self.f.index).is_rural == row.is_rural) & (self.f.n_claims >= 10)]
        catch = peers.index.map(lambda x: fac.loc[p.loc[x, "primary_facility_id"], "catchment_population"])
        vol = peers.n_claims / (np.asarray(catch, float) / 1000)
        mine = float(self.f.loc[pid, "n_claims"]) / (fac.loc[row.primary_facility_id, "catchment_population"] / 1000)
        q1, q3 = (float(vol.quantile(0.25)), float(vol.quantile(0.75))) if len(vol) >= 2 else (mine, mine)
        if not (q1 <= mine <= q3 * 1.25):
            return None
        scope = "rural" if row.is_rural else "urban"
        return {"nearest_competitor_km": round(km, 1), "volume_per_1k_pop": round(mine, 3),
                "peer_iqr": [round(q1, 3), round(q3, 3)], "peer_group": f"{row.provider_type} {row.specialty}, {scope}, n={len(vol)}"}

    def case_mix(self, pid: str) -> dict | None:
        f = self.f
        row = f.loc[pid]
        peers = f[(f.peer_key == row.peer_key) & (f.n_claims >= 10)]
        cmi_med = float(peers.case_mix_index.median())
        if not cmi_med or pd.isna(row.case_mix_index):
            return None
        cmi = float(row.case_mix_index) / cmi_med
        ratios = {}
        for col in ("em5_share", "billed_per_member"):
            med = float(peers[col].median())
            if med and pd.notna(row[col]):
                ratios[col] = float(row[col]) / med
        if not ratios:
            return None
        raw = max(ratios.values())
        adj = raw / cmi
        if adj >= self.cfg.CASE_MIX_ADJ_CLEAR_RATIO:
            return None
        return {"raw_ratio": round(raw, 2), "case_mix_index": round(cmi, 2), "adjusted_ratio": round(adj, 2),
                "clear_threshold": self.cfg.CASE_MIX_ADJ_CLEAR_RATIO, "peer_group": f"{row.peer_label}, n={int(row.peer_n)}"}

    def corrected(self, sig: dict) -> dict | None:
        h = self.s.hdr
        corr = h[h.frequency_code.isin([7, 8])]
        ids = set(sig["claim_ids"])
        hit = corr[corr.original_claim_id.isin(ids) | corr.claim_id.isin(ids)]
        if len(ids) == 0 or len(hit) / len(ids) < 0.5:
            return None
        r = hit.iloc[0]
        return {"frequency_code": int(r.frequency_code), "original_claim_id": r.original_claim_id, "replacement_claim_id": r.claim_id}

    def events(self) -> dict[str, dict]:
        """Providers taking part in a same-day cluster: ≥ 20 members each seen by ≥ 3 providers in one city that day."""
        if self._event is None:
            h = self.s.hdr
            city = self.s.facility_index.city
            h = h.assign(city=h.facility_id.map(city))
            per = h.groupby(["city", "service_date", "member_id"])["provider_id"].nunique()
            busy = per[per >= 3].reset_index()
            days = busy.groupby(["city", "service_date"]).size()
            out: dict[str, dict] = {}
            for (c, d), n in days[days >= 20].items():
                mem = set(busy[(busy.city == c) & (busy.service_date == d)].member_id)
                sub = h[(h.city == c) & (h.service_date == d) & h.member_id.isin(mem)]
                provs = sorted(set(sub.provider_id))
                for pid in provs:
                    out[pid] = {"providers_spiking": len(provs), "region": c, "window": str(d.date()), "members": int(n)}
            self._event = out
        return self._event

    def seasonal(self, pid: str) -> dict | None:
        bursts = [b for b in self.ctx.get("bursts", {}).get(pid, []) if b["region_wide"]]
        if not bursts:
            return self.events().get(pid)
        b = bursts[0]
        months = sorted({x["month"] for x in bursts})
        return {"providers_spiking": b["providers_spiking"], "region": b["city"],
                "window": months[0] if len(months) == 1 else f"{months[0]}..{months[-1]}"}

    def max_billing_z(self, pid: str) -> float:
        if self.z.empty or pid not in self.z.index:
            return 0.0
        return float(self.z.loc[pid, [c for c in BILLING_Z if c in self.z.columns]].abs().max())

    # ---------------------------------------------------------------- per signal
    def explain(self, sig: dict) -> tuple[str, dict] | None:
        if sig["hard"]:
            return None
        pid, m = sig["entity_id"], sig["method"]
        if sig["entity_type"] != "provider":
            return None
        drivers = set(sig["extra"].get("drivers", [])) or {m.rsplit(".", 1)[-1]}
        if m in ("rule.R01_exact_duplicate", "rule.R02_near_duplicate"):
            f = self.corrected(sig)
            return ("EX3", f) if f else None
        if m == "rule.R11_excessive_frequency":
            if sig["extra"].get("family") == "dialysis" and sig["value"] <= 14:
                return "EX5", {"regimen": "haemodialysis 3x/week", "expected_freq": 13, "observed_freq": sig["value"],
                               "members": sig["extra"].get("members")}
            ev = self.seasonal(pid)
            return ("EX4", ev) if ev else None
        if m == "rule.R03_upcoding_em_share":
            f = self.case_mix(pid)
            return ("EX2", f) if f else None
        if m.startswith("anomaly.") or m in ("temporal.burst", "temporal.rapid_ramp"):
            ev = self.seasonal(pid)
            if ev and (drivers & VOLUME_DRIVERS or m.startswith("temporal")):
                return "EX4", ev
            if m.startswith("anomaly.") and drivers & CASEMIX_DRIVERS:
                f = self.case_mix(pid)
                if f:
                    return "EX2", f
            f = self.sole_provider(pid)
            if f:
                return "EX1", f
            return None
        if m in ("graph.shared_indicators", "graph.louvain_community", "temporal.window_cluster"):
            z = self.max_billing_z(pid)
            has_rules = any(s["layer"] == "rules" for s in self.ctx.get("signals", [])
                            if s["entity_id"] == pid and s["direction"] == "incriminating")
            if z < 2 and not has_rules:
                src = int(self.f.loc[pid, "referral_sources"]) if pid in self.f.index else 0
                return "EX6", {"sources_count": src, "max_billing_z": round(z, 2)}
        return None


def run(store: DataStore, cfg: Config, feats: pd.DataFrame, entities: dict, signals: list[dict], alerts: set[str],
        context: dict) -> list[dict]:
    ex = Explainer(store, cfg, context.get("feats_full", feats), context)
    cleared, partial = [], defaultdict(list)
    order = sorted(alerts, key=lambda e: (-entities[e]["risk"], e))
    for eid in order:
        ent = entities[eid]
        sigs = [signals[i] for i in ent["signals"]]
        results = [(s, ex.explain(s)) for s in sigs]
        explained = [(s, r) for s, r in results if r]
        if explained and len(explained) == len(results) and not ent["hard"]:
            codes = Counter(r[0] for _, r in explained)
            code = sorted(codes, key=lambda c: (-codes[c], c))[0]
            facts = next(r[1] for _, r in explained if r[0] == code)
            n = len(cleared) + 1
            cleared.append({
                "alert_id": f"ALR-{n:05d}", "entity_type": ent["entity_type"], "entity_id": eid,
                "entity_name": str(store.provider_index.loc[eid, "name"]) if eid.startswith("PRV-") else eid,
                "triggered_by": sorted({s["method"] for s in sigs}), "original_risk": ent["risk"],
                "exoneration_code": NAMES[code], "facts": facts,
                "evidence_ids": [f"EV-A{n:03d}-{k:02d}" for k in range(1, len(explained) + 1)], "explanation": None,
            })
        seen_codes: set[str] = set()
        for s, r in explained:
            if eid in {c["entity_id"] for c in cleared}:
                break
            code, facts = r
            if code in seen_codes:
                continue
            seen_codes.add(code)
            desc = ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in facts.items())
            partial[eid].append({
                "type": "exoneration", "method": f"exonerate.{NAMES[code]}",
                "name": f"Partial explanation ({NAMES[code]})", "description": f"{NAMES[code]}: {desc}.",
                "direction": "exculpatory", "entity_ids": [eid], "claim_ids": [], "claim_count": 0, "value": None,
                "comparison_value": None, "comparison_label": None, "unit": "facts", "threshold": None, "severity": 1,
                "hard": False, "weight": 0.0, "sources": [{"table": "claims", "column": "provider_id"}],
            })
    context["case_evidence"] = {**context.get("case_evidence", {}), **partial}
    return cleared
