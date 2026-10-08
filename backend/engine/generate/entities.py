"""World state shared by all generator stages + entity builders (owners, facilities,
providers, members). Entities are addressed by 0-based index; IDs derive from the index.

Dates are stored as integer day offsets from HISTORY_START (day 0 = 2025-04-01);
SIM_TODAY is day 548. Converted to ISO strings only when tables are written.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
from faker import Faker

from ..config import Config
from . import geo

DAY0 = date(2025, 4, 1)
LAST_DAY = 547  # 2026-09-30, last day with services
TODAY = 548  # SIM_TODAY 2026-10-01
FAR_FUTURE = 10_000

PROVIDER_MIX: list[tuple[str, str, int]] = [
    ("individual", "general_medicine", 300),
    ("individual", "cardiology", 70),
    ("individual", "orthopedics", 100),
    ("individual", "oncology", 50),
    ("individual", "pediatrics", 100),
    ("individual", "nephrology", 40),
    ("individual", "emergency", 60),
    ("individual", "radiology", 50),
    ("individual", "physiotherapy", 60),
    ("group", "general_medicine", 40),
    ("group", "pediatrics", 15),
    ("group", "orthopedics", 15),
    ("facility", "none", 110),
    ("lab", "pathology", 90),
    ("pharmacy", "none", 140),
    ("ambulance", "emergency", 40),
    ("dme", "none", 40),
    ("home_health", "none", 50),
    ("behavioral", "psychiatry", 130),
]

FACILITY_MIX: list[tuple[str, int]] = [
    ("hospital", 100), ("dialysis_center", 10), ("clinic", 80), ("lab", 30), ("pharmacy", 30),
    ("ambulance_base", 15), ("dme_supplier", 10), ("home_health_agency", 10), ("behavioral_center", 15),
]

# provider_type -> preferred facility types for its primary facility
FACILITY_PREF = {
    "individual": ["clinic", "hospital"],
    "group": ["clinic", "hospital"],
    "lab": ["lab", "hospital"],
    "pharmacy": ["pharmacy", "hospital"],
    "ambulance": ["ambulance_base", "hospital"],
    "dme": ["dme_supplier", "clinic"],
    "home_health": ["home_health_agency", "clinic"],
    "behavioral": ["behavioral_center", "clinic"],
}

NAME_WORDS = [
    "Lotus", "Ganga", "Sahyadri", "Nilgiri", "Coral", "Shanti", "Arogya", "Jeevan", "Kaveri",
    "Sanjeevani", "Amrit", "Prakash", "Seva", "Navjeevan", "Kalpataru", "Swasthya", "Chetana",
    "Udaya", "Narmada", "Tulsi", "Vindhya", "Saraswati", "Godavari", "Aravali", "Malabar", "Deccan",
]


def day_iso(d: int) -> str:
    return (DAY0 + timedelta(days=int(d))).isoformat()


def iso_day(s: str) -> int:
    return (date.fromisoformat(s) - DAY0).days


def short_hash(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:12]


@dataclass
class GroundTruth:
    entity_type: str
    entity_index: int  # index into the entity table (or -1 when entity_id is given)
    scheme_id: str
    role: str
    is_decoy: int
    notes: str
    claim_tks: list[int] = field(default_factory=list)
    all_claims_of_provider: bool = False
    entity_id: str | None = None


@dataclass
class World:
    cfg: Config
    seed: int
    rng: np.random.Generator
    fake: Faker
    owners: list[dict] = field(default_factory=list)
    facilities: list[dict] = field(default_factory=list)
    providers: list[dict] = field(default_factory=list)
    members: list[dict] = field(default_factory=list)
    admissions: list[dict] = field(default_factory=list)
    referrals: list[dict] = field(default_factory=list)
    investigations: list[dict] = field(default_factory=list)
    ground_truth: list[GroundTruth] = field(default_factory=list)
    planted: list[dict] = field(default_factory=list)
    reserved_providers: set[int] = field(default_factory=set)
    reserved_members: set[int] = field(default_factory=set)
    member_adm: dict[int, list[tuple[int, int, int]]] = field(default_factory=lambda: defaultdict(list))
    members_by_city: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    oncology_pool: set[int] = field(default_factory=set)
    renal_pool: set[int] = field(default_factory=set)
    book: object = None  # ClaimBook, set by claims.py

    # ------------------------------------------------------------ ids
    @staticmethod
    def owner_id(i: int) -> str:
        return f"OWN-{i + 1:05d}"

    @staticmethod
    def facility_id(i: int) -> str:
        return f"FAC-{i + 1:04d}"

    @staticmethod
    def provider_id(i: int) -> str:
        return f"PRV-{i + 1:05d}"

    @staticmethod
    def member_id(i: int) -> str:
        return f"MEM-{i + 1:06d}"

    # ------------------------------------------------------------ random helpers
    def choice(self, seq, p=None):
        """rng.choice for Python lists that returns the element (keeps types)."""
        if p is not None:
            p = np.asarray(p, dtype=float)
            p = p / p.sum()
        return seq[int(self.rng.choice(len(seq), p=p))]

    def uniform_int(self, lo: int, hi: int) -> int:
        """Inclusive integer in [lo, hi]."""
        return int(self.rng.integers(lo, hi + 1))

    # ------------------------------------------------------------ member eligibility
    def member_window(self, m: int) -> tuple[int, int]:
        """Inclusive service-day window in which member m is alive and covered."""
        mem = self.members[m]
        lo = max(0, mem["cov_start"])
        hi = min(LAST_DAY, mem["cov_end"], mem["death"])
        return lo, hi

    def in_admission(self, m: int, d: int) -> bool:
        return any(a <= d <= b for a, b, _ in self.member_adm.get(m, ()))

    def ok_day(self, m: int, d: int, allow_admission: bool = False) -> bool:
        lo, hi = self.member_window(m)
        if not lo <= d <= hi:
            return False
        return allow_admission or not self.in_admission(m, d)

    def add_admission(self, m: int, fac: int, admit: int, discharge: int, tag: str = "") -> int:
        self.admissions.append({"member": m, "facility": fac, "admit": admit, "discharge": discharge, "tag": tag})
        self.member_adm[m].append((admit, discharge, fac))
        return len(self.admissions) - 1

    def admission_free(self, m: int, a: int, b: int) -> bool:
        """True if [a, b] does not overlap any existing admission of m (with a 1-day gap)."""
        return all(b < s - 1 or a > e + 1 for s, e, _ in self.member_adm.get(m, ()))

    # ------------------------------------------------------------ lookups
    def providers_where(self, ptype: str | None = None, specialty: str | None = None,
                        city: str | None = None, include_reserved: bool = False) -> list[int]:
        out = []
        for i, p in enumerate(self.providers):
            if ptype and p["provider_type"] != ptype:
                continue
            if specialty and p["specialty"] != specialty:
                continue
            if city and p["city"] != city:
                continue
            if not include_reserved and i in self.reserved_providers:
                continue
            out.append(i)
        return out

    def reserve_provider(self, ptype: str, specialty: str | None, city: str) -> int:
        cands = self.providers_where(ptype, specialty, city)
        if not cands:
            raise RuntimeError(f"no free provider {ptype}/{specialty} in {city}")
        i = self.choice(cands)
        self.reserved_providers.add(i)
        return i

    def city_members(self, city: str, min_age: int = 0, max_age: int = 200, exclude_pools: bool = False) -> list[int]:
        out = []
        for m in self.members_by_city[city]:
            if m in self.reserved_members:
                continue
            age = self.members[m]["age"]
            if not min_age <= age <= max_age:
                continue
            if exclude_pools and (m in self.oncology_pool or m in self.renal_pool):
                continue
            out.append(m)
        return out

    def hospital_facilities(self, city: str) -> list[int]:
        return [i for i, f in enumerate(self.facilities) if f["city"] == city and f["facility_type"] == "hospital"]

    def facility_provider(self, fac: int) -> int | None:
        """Facility-type provider whose primary facility is `fac` (hospital/dialysis billing entity)."""
        for i, p in enumerate(self.providers):
            if p["provider_type"] == "facility" and p["primary_facility"] == fac:
                return i
        return None

    def add_truth(self, **kw) -> GroundTruth:
        gt = GroundTruth(**kw)
        self.ground_truth.append(gt)
        return gt


# ---------------------------------------------------------------- builders

def _city_weights(rural_weight: float | None = None) -> tuple[list[geo.City], np.ndarray]:
    cities = geo.CITIES
    w = np.array([c.weight for c in cities], dtype=float)
    return cities, w / w.sum()


def build_owners(w: World, n: int = 900) -> None:
    for i in range(n):
        name = w.fake.name()
        if w.rng.random() < 0.35:
            name = f"{name.split()[-1]} Healthcare {'LLP' if w.rng.random() < 0.5 else 'Pvt Ltd'}"
        w.owners.append({
            "owner_name": name,
            "bank_account_hash": short_hash(f"bank-{w.seed}-{i}-{w.rng.integers(1 << 30)}"),
            "address_hash": short_hash(f"oaddr-{w.seed}-{i}-{w.rng.integers(1 << 30)}"),
        })


def build_facilities(w: World) -> None:
    cities, p = _city_weights()
    city_idx = list(range(len(cities)))
    plan: list[tuple[str, geo.City]] = []
    for ftype, count in FACILITY_MIX:
        if ftype == "hospital":
            # every city gets at least one hospital; rural towns get exactly one (sole provider)
            for c in cities:
                plan.append((ftype, c))
            urban = [i for i in city_idx if not cities[i].is_rural]
            pu = np.array([cities[i].weight for i in urban], dtype=float)
            for _ in range(count - len(cities)):
                plan.append((ftype, cities[w.choice(urban, pu)]))
        else:
            for _ in range(count):
                plan.append((ftype, cities[w.choice(city_idx, p)]))
    for k, (ftype, c) in enumerate(plan):
        if c.is_rural and ftype not in ("hospital", "pharmacy", "clinic"):
            # rural towns only have a hospital, a pharmacy and clinics; move the rest to the nearest city
            c = _nearest_urban(c)
        lat, lon = geo.jitter(w.rng, c, 2.5 if c.is_rural else 9)
        word = w.choice(NAME_WORDS)
        name = {
            "hospital": f"{c.name} {word} Hospital" if not c.is_rural else f"{c.name} Community Hospital",
            "dialysis_center": f"{word} Kidney Care, {c.name}",
            "clinic": f"{word} Clinic, {c.name}",
            "lab": f"{word} Diagnostics, {c.name}",
            "pharmacy": f"{word} Medicals, {c.name}",
            "ambulance_base": f"{word} Ambulance Base, {c.name}",
            "dme_supplier": f"{word} Medical Equipment, {c.name}",
            "home_health_agency": f"{word} Home Care, {c.name}",
            "behavioral_center": f"{word} Mind Wellness Centre, {c.name}",
        }[ftype]
        beds = 0
        if ftype == "hospital":
            beds = 60 if c.is_rural else int(w.rng.integers(50, 600))
        w.facilities.append({
            "name": name, "facility_type": ftype, "city": c.name, "state": c.state,
            "pincode": geo.pincode(w.rng, c), "lat": lat, "lon": lon, "is_rural": int(c.is_rural),
            "owner": k, "bed_count": beds, "catchment_population": 0,
        })
    # catchment: city (or district) population split across same-type facilities in the city
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for f in w.facilities:
        counts[(f["city"], f["facility_type"])] += 1
    for f in w.facilities:
        c = geo.CITY_BY_NAME[f["city"]]
        f["catchment_population"] = int(c.catchment / counts[(f["city"], f["facility_type"])])


def _nearest_urban(c: geo.City) -> geo.City:
    urban = [u for u in geo.CITIES if not u.is_rural and u.state == c.state]
    return min(urban, key=lambda u: float(geo.haversine_km(c.lat, c.lon, u.lat, u.lon)))


def build_providers(w: World) -> None:
    cities, p = _city_weights()
    hospitals_and_dialysis = [i for i, f in enumerate(w.facilities) if f["facility_type"] in ("hospital", "dialysis_center")]
    fac_by_city_type: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, f in enumerate(w.facilities):
        fac_by_city_type[(f["city"], f["facility_type"])].append(i)

    plan: list[tuple[str, str]] = []
    for ptype, spec, n in PROVIDER_MIX:
        plan.extend([(ptype, spec)] * n)
    assert len(plan) == 1500

    fac_cursor = 0
    for ptype, spec in plan:
        if ptype == "facility":
            fac = hospitals_and_dialysis[fac_cursor]
            fac_cursor += 1
            f = w.facilities[fac]
            c = geo.CITY_BY_NAME[f["city"]]
            if f["facility_type"] == "dialysis_center":
                spec = "nephrology"
        else:
            c = cities[w.choice(list(range(len(cities))), p)]
            if c.is_rural and ptype not in ("individual", "pharmacy"):
                c = _nearest_urban(c)
            fac = None
            for ftype in FACILITY_PREF[ptype]:
                opts = fac_by_city_type.get((c.name, ftype))
                if opts:
                    fac = w.choice(opts)
                    break
            if fac is None:  # rural individual with no clinic: the town hospital
                fac = fac_by_city_type[(c.name, "hospital")][0]
            f = w.facilities[fac]
        enrolled = DAY0 - timedelta(days=int(w.rng.integers(200, 5000)))
        if w.rng.random() < 0.05:
            enrolled = DAY0 + timedelta(days=int(w.rng.integers(0, 400)))
        w.providers.append({
            "name": _provider_name(w, ptype, spec, f, c),
            "provider_type": ptype, "specialty": spec, "primary_facility": fac, "owner": None,
            "bank_account_hash": "", "city": c.name, "state": c.state, "pincode": f["pincode"],
            "lat": f["lat"], "lon": f["lon"], "is_rural": int(c.is_rural),
            "enrolled": (enrolled - DAY0).days, "volume": float(w.rng.lognormal(0, 0.7)),
        })

    # ownership: facility providers belong to their facility's owner; others are either
    # independent (first 600 owners after the facility owners) or part of a same-city chain
    n_fac_owners = len(w.facilities)
    free_owners = list(range(n_fac_owners, len(w.owners)))
    others = [i for i, pr in enumerate(w.providers) if pr["provider_type"] != "facility"]
    order = [others[int(k)] for k in w.rng.permutation(len(others))]
    owned_by_city: dict[str, list[int]] = defaultdict(list)
    for i, pr in enumerate(w.providers):
        if pr["provider_type"] == "facility":
            pr["owner"] = w.facilities[pr["primary_facility"]]["owner"]
    for k, i in enumerate(order):
        pr = w.providers[i]
        if k < len(free_owners) or not owned_by_city[pr["city"]]:
            own = free_owners[k % len(free_owners)]
            owned_by_city[pr["city"]].append(i)
            pr["owner"] = own
        else:
            sibling = w.choice(owned_by_city[pr["city"]])
            pr["owner"] = w.providers[sibling]["owner"]
            if w.rng.random() < 0.6:  # group practices often share the clinic too
                pr["primary_facility"] = w.providers[sibling]["primary_facility"]
                sf = w.facilities[pr["primary_facility"]]
                pr["lat"], pr["lon"], pr["pincode"] = sf["lat"], sf["lon"], sf["pincode"]
    for pr in w.providers:
        pr["bank_account_hash"] = w.owners[pr["owner"]]["bank_account_hash"]


def _provider_name(w: World, ptype: str, spec: str, f: dict, c: geo.City) -> str:
    word = w.choice(NAME_WORDS)
    if ptype == "individual":
        label = {"general_medicine": "General Medicine", "physiotherapy": "Physiotherapy"}.get(spec, spec.title())
        return f"Dr. {w.fake.first_name()} {w.fake.last_name()} ({label})"
    if ptype == "behavioral":
        return f"Dr. {w.fake.first_name()} {w.fake.last_name()} (Psychiatry)"
    if ptype == "group":
        return f"{w.fake.last_name()} {'Family Clinic' if spec != 'orthopedics' else 'Bone & Joint Clinic'}"
    if ptype == "facility":
        return f["name"]
    return {
        "lab": f"{word} Diagnostics Lab, {c.name}",
        "pharmacy": f"{word} Pharmacy, {c.name}",
        "ambulance": f"{word} Ambulance Services, {c.name}",
        "dme": f"{word} Medical Supplies, {c.name}",
        "home_health": f"{word} Home Health, {c.name}",
    }[ptype]


def build_members(w: World, n: int = 20_000) -> None:
    cities, p = _city_weights()
    city_choice = w.rng.choice(len(cities), size=n, p=p)
    ages = np.clip(w.rng.gamma(3.0, 12.5, size=n), 0, 95).astype(int)
    base_risk = w.rng.lognormal(-0.18, 0.55, size=n)
    household = 0
    hh_left = 0
    for i in range(n):
        c = cities[int(city_choice[i])]
        age = int(ages[i])
        if w.rng.random() < 0.18:
            age = int(w.rng.integers(0, 18))
        risk = float(base_risk[i]) * (0.7 + age / 80)
        cov_start = -int(w.rng.integers(30, 1800)) if w.rng.random() < 0.85 else int(w.rng.integers(0, 500))
        cov_end = 730 if w.rng.random() > 0.04 else int(w.rng.integers(120, 500))
        death = FAR_FUTURE
        if w.rng.random() < 0.005 + (0.01 if age > 70 else 0):
            death = int(w.rng.integers(max(60, cov_start + 30), 545))
        if hh_left == 0:
            household += 1
            hh_left = int(w.choice([1, 1, 2, 2, 3, 4]))
        hh_left -= 1
        lat, lon = geo.jitter(w.rng, c, 15 if c.is_rural else 10)
        w.members.append({
            "age": age, "gender": "F" if w.rng.random() < 0.5 else "M", "city": c.name, "state": c.state,
            "pincode": geo.pincode(w.rng, c), "lat": lat, "lon": lon,
            "plan_id": f"PLN-{int(w.rng.integers(1, 7)):02d}", "cov_start": cov_start, "cov_end": cov_end,
            "death": death, "risk": round(risk, 3), "chronic": 0,
            "card_id": f"HC{int(w.rng.integers(10**9, 10**10))}",
            "phone_hash": short_hash(f"ph-{w.seed}-{i}"),
            "address_hash": short_hash(f"addr-{w.seed}-{c.name}-{household}"),
        })
        w.members_by_city[c.name].append(i)
    # normalise risk to mean 1.0 before pools are boosted
    mean = float(np.mean([m["risk"] for m in w.members]))
    for m in w.members:
        m["risk"] = round(m["risk"] / mean, 3)
    adults = [i for i, m in enumerate(w.members) if m["age"] >= 30 and m["death"] == FAR_FUTURE]
    picks = w.rng.choice(len(adults), size=1000, replace=False)
    onc = [adults[int(k)] for k in picks[:700]]
    ren = [adults[int(k)] for k in picks[700:]]
    for i in onc:
        w.members[i]["risk"] = round(float(w.rng.uniform(2.4, 3.4)), 3)
    for i in ren:
        w.members[i]["risk"] = round(float(w.rng.uniform(2.3, 3.3)), 3)
    w.oncology_pool, w.renal_pool = set(onc), set(ren)
    for m in w.members:
        m["chronic"] = int(min(6, w.rng.poisson(max(0.1, m["risk"] - 0.4))))


def make_world(cfg: Config, seed: int) -> World:
    Faker.seed(seed)
    fake = Faker("en_IN")
    fake.seed_instance(seed)
    w = World(cfg=cfg, seed=seed, rng=np.random.default_rng(seed), fake=fake)
    build_owners(w)
    build_facilities(w)
    build_providers(w)
    build_members(w)
    return w


def haversine(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    return float(geo.haversine_km(a_lat, a_lon, b_lat, b_lon))


__all__ = [
    "DAY0",
    "FAR_FUTURE",
    "LAST_DAY",
    "TODAY",
    "World",
    "day_iso",
    "haversine",
    "iso_day",
    "make_world",
    "math",
    "short_hash",
]
