"""Scenario whitelist + injectors. Injected rows live only in a sandbox DataStore."""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from ..config import CONFIG, Config
from ..generate.__main__ import CLAIM_COLUMNS
from ..store import DataStore


def catalog(cfg: Config = CONFIG) -> dict:
    data = json.loads((cfg.contracts_dir / "twin_scenarios.json").read_text(encoding="utf-8"))
    for t in data["tunable_params"]:
        t["current"] = getattr(cfg, t["key"])
    return data


def defaults(scenario: str) -> dict:
    s = next(x for x in catalog()["scenarios"] if x["id"] == scenario)
    return {k: v["default"] for k, v in s["params"].items()}


class Injector:
    def __init__(self, base: DataStore, cfg: Config, seed: int, run_no: int, city: str = "Ahmedabad"):
        self.b, self.cfg, self.rng, self.n = base, cfg, np.random.default_rng(seed), run_no
        self.city, self.rows = city, {k: [] for k in ("claims", "providers", "owners", "facilities", "members", "referrals")}
        self.seq, self.today = 0, pd.Timestamp(cfg.sim_today)
        self.last = self.today - pd.Timedelta(days=1)
        f = base.facilities[base.facilities.city == city].iloc[0]
        self.fac = f.facility_id
        self.meta: dict = {"span": {}}
        m = base.members
        ok = (m.city == city) & m.date_of_death.isna() & (m.coverage_start < self.today - pd.Timedelta(days=200)) & (m.age >= 18)
        self.pool = sorted(m[ok].member_id)

    def owner(self) -> str:
        oid = f"OWN-T{self.n:03d}"
        self.rows["owners"].append({"owner_id": oid, "owner_name": f"Injected owner {self.n}", "bank_account_hash": f"tb{self.n}",
                                    "address_hash": f"ta{self.n}"})
        return oid

    def provider(self, i: int, spec: str, ptype: str, owner: str, bank: str | None = None) -> str:
        pid = f"PRV-T{self.n:03d}-{i}"
        f = self.b.facility_index.loc[self.fac]
        self.rows["providers"].append({"provider_id": pid, "name": f"Injected provider {i}", "provider_type": ptype, "specialty": spec,
                                       "primary_facility_id": self.fac, "owner_id": owner, "bank_account_hash": bank or f"tb{self.n}",
                                       "city": self.city, "state": f.state, "pincode": f.pincode, "lat": f.lat, "lon": f.lon,
                                       "is_rural": 0, "enrolled_date": str((self.today - pd.Timedelta(days=1100)).date())})
        return pid

    def member(self) -> str:
        return self.pool[int(self.rng.integers(len(self.pool)))]

    def claim(self, member: str, pid: str, day: pd.Timestamp, code: str, billed: int, stype: str = "professional",
              referring: str = "", minutes: int = 30, **extra) -> str:
        self.seq += 1
        cid = f"CLM-T{self.n:03d}-{self.seq:04d}"
        day = min(day, self.last)
        sub = min(day + pd.Timedelta(days=int(self.rng.integers(1, 6))), self.last)
        rel = sub + pd.Timedelta(days=int(self.rng.integers(10, 26)))
        pending = rel > self.today
        row = {k: "" for k in CLAIM_COLUMNS}
        row.update({"claim_id": cid, "line_no": 1, "member_id": member, "provider_id": pid, "billing_provider_id": pid,
                    "facility_id": self.fac, "referring_provider_id": referring, "service_type": stype, "procedure_code": code,
                    "diagnosis_code": "DX-060", "units": 1, "duration_minutes": minutes, "billed_amount": billed,
                    "allowed_amount": billed, "paid_amount": 0 if pending else billed, "service_date": str(day.date()),
                    "submitted_date": str(sub.date()), "payment_release_date": str(rel.date()),
                    "payment_status": "pending" if pending else "paid", "frequency_code": 1, "place_of_service": "office"})
        row.update(extra)
        self.rows["claims"].append(row)
        return cid

    def day(self, lo: int, hi: int) -> pd.Timestamp:
        return self.last - pd.Timedelta(days=int(self.rng.integers(lo, hi + 1)))

    def background(self, pid: str, n: int) -> None:
        for _ in range(n):
            self.claim(self.member(), pid, self.day(1, 520), str(self.rng.choice(["EM2", "EM3"])), int(self.rng.integers(70, 110)) * 10,
                       is_bg=True)

    def frames(self) -> dict[str, pd.DataFrame]:
        out = {}
        for k, v in self.rows.items():
            df = pd.DataFrame(v)
            if k == "claims" and len(df):
                df = df.drop(columns=[c for c in df.columns if c not in CLAIM_COLUMNS])
            out[k] = df
        return out


def inject(scenario: str, params: dict, base: DataStore, cfg: Config, seed: int, run_no: int) -> tuple[dict, list[str], dict]:
    p = {**defaults(scenario), **params}
    j = Injector(base, cfg, seed, run_no)
    injected: list[str] = []
    T = cfg.review_threshold_inr
    if scenario == "claim_splitting":
        own = j.owner()
        k = int(p["providers"])
        provs = [j.provider(i + 1, "orthopedics" if i % 2 == 0 else "physiotherapy", "group", own) for i in range(k)]
        per = {pid: 0 for pid in provs}
        for n in range(int(p["count"])):
            m = j.member()
            P = p["parent_amount"] * j.rng.uniform(0.9, 1.1)
            s = int(p["splits"])
            amt = int(min(P / s, T - 100) * j.rng.uniform(0.9, 1.0) // 100 * 100)
            S = p["spread_days"] * j.rng.uniform(0.6, 1.6)
            start = j.day(int(math.ceil(S)) + 1, 150 + int(math.ceil(S)))
            for q in range(s):
                pid = provs[(n + q) % k]
                off = int(round(S * q / max(1, s - 1)))
                code = "ORT-214" if "1" in pid[-1:] or pid.endswith("3") else "PHY-031"
                cid = j.claim(m, pid, start + pd.Timedelta(days=off), code, amt, minutes=60)
                j.meta["span"][cid] = off
                injected.append(cid)
                per[pid] += 1
        for i, pid in enumerate(provs):  # the last provider is a busy clinic that dilutes its split share
            j.background(pid, int(per[pid] * j.rng.uniform(2.6, 3.2)) if (k >= 3 and i == k - 1) else int(j.rng.integers(5, 20)))
    elif scenario == "referral_collusion":
        own = j.owner()
        k = int(p["providers"])
        owners = [own] + ([own] * (k - 1) if p["shared_owner"] else [j.owner() + "" for _ in range(0)] or [own] * (k - 1))
        provs = [j.provider(i + 1, "general_medicine", "individual", owners[i], bank=f"tb{run_no}" if p["shared_bank"] else f"tb{run_no}-{i}")
                 for i in range(k)]
        for i, src in enumerate(provs):
            dst = provs[(i + 1) % k]
            for _ in range(int(p["referrals_per_month"] * p["months"] / k) or 1):
                m = j.member()
                d = j.day(5, int(30 * p["months"]))
                j.rows["referrals"].append({"referral_id": f"REF-T{run_no:03d}-{len(j.rows['referrals']) + 1}", "from_provider_id": src,
                                            "to_provider_id": dst, "member_id": m, "referral_date": str(d.date()), "reason_code": "RSN-07"})
                injected.append(j.claim(m, dst, d + pd.Timedelta(days=3), "EM5", 2600, referring=src))
    elif scenario == "phantom_services":
        own = j.owner()
        kind = p["kind"]
        pid = j.provider(1, "emergency" if kind == "ambulance_miles" else "none", "ambulance" if kind == "ambulance_miles" else "home_health", own)
        adm = base.admissions[base.admissions.member_id.isin(base.members.member_id)]
        dead = base.members[base.members.date_of_death.notna()]
        for i in range(int(p["count"])):
            if kind == "deceased" and len(dead):
                r = dead.iloc[i % len(dead)]
                d = min(r.date_of_death + pd.Timedelta(days=int(j.rng.integers(3, 40))), j.last)
                if d <= r.date_of_death:
                    continue
                injected.append(j.claim(r.member_id, pid, d, "HH-010", 1500, stype="home_health"))
            elif kind == "inpatient" and len(adm):
                r = adm.iloc[int(j.rng.integers(len(adm)))]
                if (r.discharge_date - r.admit_date).days < 2:
                    continue
                injected.append(j.claim(r.member_id, pid, r.admit_date + pd.Timedelta(days=1), "HH-010", 1500, stype="home_health"))
            else:
                f = base.facility_index.loc[j.fac]
                km = j.rng.uniform(8, 40)
                ratio = j.rng.uniform(1.2, 3.0)
                injected.append(j.claim(j.member(), pid, j.day(1, 150), "AMB-BLS", int(1500 + 40 * km / 1.609 * ratio), stype="ambulance",
                                        ambulance_miles=round(km / 1.609344 * ratio, 1), pickup_lat=f.lat + km / 110.574,
                                        pickup_lon=f.lon, dropoff_lat=f.lat, dropoff_lon=f.lon, minutes=60))
    elif scenario == "upcoding_drift":
        pid = j.provider(1, "general_medicine", "individual", j.owner())
        months = int(p["months"])
        for mo in range(months):
            share = p["start_share"] + (p["end_share"] - p["start_share"]) * mo / max(1, months - 1)
            for _ in range(20):
                code = "EM5" if j.rng.random() < share else str(j.rng.choice(["EM2", "EM3", "EM4"]))
                cid = j.claim(j.member(), pid, j.last - pd.Timedelta(days=30 * (months - 1 - mo) + int(j.rng.integers(0, 29))),
                              code, 2600 if code == "EM5" else 1100)
                if code == "EM5":
                    injected.append(cid)
    elif scenario == "identity_cluster":
        own = j.owner()
        provs = [j.provider(i + 1, "general_medicine", "individual", own) for i in range(int(p["providers"]))]
        tmpl = base.members[base.members.member_id == j.pool[0]].iloc[0].to_dict()
        for i in range(int(p["members"])):
            mid = f"MEM-T{run_no:03d}-{i + 1:03d}"
            row = {**tmpl, "member_id": mid, "coverage_start": str((j.today - pd.Timedelta(days=200)).date()),
                   "coverage_end": "2027-03-31", "date_of_death": "",
                   "phone_hash": f"tp{run_no}" if p["share"] in ("phone", "both") else f"tp{run_no}-{i}",
                   "address_hash": f"tad{run_no}" if p["share"] in ("address", "both") else f"tad{run_no}-{i}"}
            j.rows["members"].append({k: (str(v.date()) if isinstance(v, pd.Timestamp) else v) for k, v in row.items()})
            for _ in range(3):
                injected.append(j.claim(mid, provs[i % len(provs)], j.day(1, 150), "EM4", 1700))
    elif scenario == "duplicate_billing":
        pid = j.provider(1, "general_medicine", "individual", j.owner())
        origs = [j.claim(j.member(), pid, j.day(10, 300), "EM3", 1100, is_bg=True) for _ in range(int(p["count"]) * 2)]
        rows = {r["claim_id"]: r for r in j.rows["claims"]}
        for cid in origs[: int(p["count"])]:
            r = rows[cid]
            d = pd.Timestamp(r["service_date"]) + pd.Timedelta(days=int(p["day_offset"]))
            amt = int(r["billed_amount"] * (j.rng.uniform(0.97, 1.03) if p["near_duplicate"] else 1))
            injected.append(j.claim(r["member_id"], pid, d, "EM3", amt))
        j.meta["day_offset"] = int(p["day_offset"])
    else:
        raise KeyError(scenario)
    j.meta["params"] = p
    j.meta["providers"] = [r["provider_id"] for r in j.rows["providers"]]
    return j.frames(), injected, j.meta
