"""ClaimBook (header + service lines, payment dates/statuses) and baseline legitimate claims
for all 8 service types. Baseline never violates a rule on purpose: services stay inside
coverage, before death, outside admission windows and in the member's home area."""

from __future__ import annotations

import math
from collections import Counter, defaultdict

import numpy as np

from . import geo, reference
from .entities import LAST_DAY, TODAY, World, haversine

_CODES = reference.procedure_codes().to_dict("records")
PRICE = {str(r["code"]): int(r["base_price_inr"]) for r in _CODES}
MINUTES = {str(r["code"]): int(r["typical_minutes"]) for r in _CODES}
DRUGS = {str(r["drug_code"]): r for r in reference.drugs().to_dict("records")}
DME = {str(r["item_code"]): r for r in reference.dme_items().to_dict("records")}

SERVICE_SHARE = {
    "professional": 0.38, "facility": 0.12, "pharmacy": 0.18, "lab": 0.14,
    "ambulance": 0.03, "behavioral_health": 0.05, "home_health": 0.05, "dme": 0.05,
}
EM_NORMAL = [0.10, 0.25, 0.35, 0.20, 0.10]
EM_HIGH = [0.05, 0.15, 0.30, 0.25, 0.25]  # oncology / emergency shift right
PROCS = {
    "general_medicine": (0.15, ["GEN-110", "GEN-210"], [0.5, 0.5]),
    "cardiology": (0.35, ["CAR-110", "CAR-220", "CAR-410"], [0.5, 0.35, 0.15]),
    "orthopedics": (0.30, ["ORT-305", "ORT-101", "ORT-214", "ORT-219"], [0.45, 0.30, 0.15, 0.10]),
    "oncology": (0.45, ["ONC-120", "ONC-210"], [0.8, 0.2]),
    "pediatrics": (0.35, ["PED-210", "PED-110"], [0.7, 0.3]),
    "nephrology": (0.05, ["NEP-110"], [1.0]),
    "emergency": (0.40, ["EMR-210", "EMR-110"], [0.6, 0.4]),
}
DX_RANGE = {
    "general_medicine": (1, 40), "cardiology": (41, 55), "orthopedics": (56, 70), "physiotherapy": (56, 70),
    "oncology": (71, 85), "pediatrics": (86, 100), "nephrology": (101, 110), "psychiatry": (111, 125),
    "emergency": (126, 140), "radiology": (1, 150), "pathology": (1, 150), "none": (1, 150),
}
LAB_ORDERABLES = ["LAB-100", "LAB-200", "LAB-300", "LAB-410", "LAB-420", "LAB-430", "LAB-440",
                  "LAB-101", "LAB-104", "LAB-201", "LAB-301"]
LAB_WEIGHTS = [0.18, 0.12, 0.2, 0.04, 0.12, 0.1, 0.12, 0.03, 0.04, 0.02, 0.03]
LAB_PANEL_OF = {"LAB-101": "LAB-100", "LAB-104": "LAB-100", "LAB-201": "LAB-200", "LAB-301": "LAB-300"}


def weekday(d: int) -> int:
    """Monday=0 ... Sunday=6 (day 0 = Tuesday 2025-04-01)."""
    return (1 + d) % 7


class ClaimBook:
    """Collects claim headers and lines; assigns payment dates and statuses."""

    def __init__(self, w: World):
        self.w = w
        self.headers: list[dict] = []
        self.lines: list[list[dict]] = []
        self.lines_by_type: Counter = Counter()
        self.by_provider: dict[int, list[int]] = defaultdict(list)

    def price(self, code: str, units: int = 1) -> int:
        return int(round(PRICE[code] * units * self.w.rng.uniform(0.9, 1.1), -1))

    def add(self, *, member: int, provider: int, day: int, service_type: str, pos: str, lines: list[dict],
            facility: int | None = None, billing: int | None = None, referring: int | None = None,
            freq: int = 1, original: int | None = None, release: int | None = None,
            submit_delay: int | None = None, allowed_ratio: float | None = None, dx: str | None = None,
            denied_ok: bool = True) -> int:
        w = self.w
        delay = submit_delay if submit_delay is not None else w.uniform_int(1, 20)
        submitted = min(max(day, day + delay), LAST_DAY)
        if release is None:
            release = submitted + w.uniform_int(10, 25)
        if release >= TODAY:
            status = "pending"
        elif denied_ok and w.rng.random() < 0.02:
            status = "denied"
        else:
            status = "paid"
        ratio = allowed_ratio if allowed_ratio is not None else float(w.rng.uniform(0.82, 0.97))
        prov = w.providers[provider]
        if dx is None:
            lo, hi = DX_RANGE.get(prov["specialty"], (1, 150))
            dx = f"DX-{w.uniform_int(lo, hi):03d}"
        out_lines = []
        for k, ln in enumerate(lines, start=1):
            units = int(ln.get("units", 1))
            billed = int(ln["billed"]) if "billed" in ln else self.price(ln["code"], units)
            allowed = int(round(billed * ratio))
            row = {
                "line_no": k, "procedure_code": ln["code"], "units": units,
                "duration_minutes": int(ln.get("minutes", MINUTES[ln["code"]] * units)),
                "billed_amount": billed, "allowed_amount": allowed,
                "paid_amount": allowed if status == "paid" else 0,
                "ambulance_miles": ln.get("ambulance_miles"), "pickup_lat": ln.get("pickup_lat"),
                "pickup_lon": ln.get("pickup_lon"), "dropoff_lat": ln.get("dropoff_lat"),
                "dropoff_lon": ln.get("dropoff_lon"), "days_supply": ln.get("days_supply"),
                "drug_code": ln.get("drug_code"), "dme_item_code": ln.get("dme_item_code"),
                "rental_month": ln.get("rental_month"),
            }
            out_lines.append(row)
        tk = len(self.headers)
        self.headers.append({
            "tk": tk, "member": member, "provider": provider,
            "billing": billing if billing is not None else provider,
            "facility": facility if facility is not None else prov["primary_facility"],
            "referring": referring, "service_type": service_type, "pos": pos, "day": day,
            "submitted": submitted, "release": release, "status": status, "freq": freq,
            "original": original, "dx": dx,
        })
        self.lines.append(out_lines)
        self.lines_by_type[service_type] += len(out_lines)
        self.by_provider[provider].append(tk)
        return tk

    def total_lines(self) -> int:
        return sum(self.lines_by_type.values())

    def amount(self, tk: int, col: str = "billed_amount") -> int:
        return sum(ln[col] for ln in self.lines[tk])


# ---------------------------------------------------------------- selection helpers

class Picker:
    """Cached provider/member pools for baseline generation (reserved entities excluded)."""

    def __init__(self, w: World):
        self.w = w
        self._prov: dict[tuple, tuple[list[int], np.ndarray]] = {}
        self._mem: dict[tuple, list[int]] = {}

    def provider(self, ptype: str, specs: tuple[str, ...] | None, city: str) -> int | None:
        key = (ptype, specs, city)
        if key not in self._prov:
            c = geo.CITY_BY_NAME[city]
            cands = self._cands(ptype, specs, city)
            if not cands:
                for other in sorted(geo.CITIES, key=lambda o: haversine(c.lat, c.lon, o.lat, o.lon)):
                    if other.state == c.state and other.name != city:
                        cands = self._cands(ptype, specs, other.name)
                        if cands:
                            break
            wts = np.array([self.w.providers[i]["volume"] for i in cands], dtype=float)
            self._prov[key] = (cands, wts / wts.sum() if len(cands) else wts)
        cands, wts = self._prov[key]
        if not cands:
            return None
        return cands[int(self.w.rng.choice(len(cands), p=wts))]

    def _cands(self, ptype, specs, city):
        return [i for i, p in enumerate(self.w.providers)
                if p["provider_type"] == ptype and p["city"] == city and i not in self.w.reserved_providers
                and (specs is None or p["specialty"] in specs)]

    def members(self, city: str, kind: str) -> list[int]:
        key = (city, kind)
        if key not in self._mem:
            w = self.w
            base = [m for m in w.members_by_city[city] if m not in w.reserved_members]
            if kind == "child":
                out = [m for m in base if w.members[m]["age"] < 18]
            elif kind == "adult":
                out = [m for m in base if w.members[m]["age"] >= 18]
            elif kind == "general_adult":
                out = [m for m in base if w.members[m]["age"] >= 18 and m not in w.oncology_pool and m not in w.renal_pool]
            elif kind == "onc":
                out = [m for m in base if m in w.oncology_pool]
            elif kind == "renal":
                out = [m for m in base if m in w.renal_pool]
            elif kind == "older":
                out = [m for m in base if w.members[m]["age"] >= 50]
            else:
                out = base
            self._mem[key] = out
        return self._mem[key]

    def member_for(self, specialty: str, city: str) -> int | None:
        w = self.w
        if specialty == "pediatrics":
            pool = self.members(city, "child")
        elif specialty == "oncology" and w.rng.random() < 0.3 and self.members(city, "onc"):
            pool = self.members(city, "onc")
        elif specialty == "nephrology" and w.rng.random() < 0.4 and self.members(city, "renal"):
            pool = self.members(city, "renal")
        elif specialty in ("general_medicine", "emergency", "radiology"):
            pool = self.members(city, "all")
        else:
            pool = self.members(city, "general_adult")
        if not pool:
            pool = self.members(city, "all")
        return pool[int(w.rng.integers(len(pool)))] if pool else None


def pick_day(w: World, m: int, lo: int = 0, hi: int = LAST_DAY, provider: int | None = None,
             tries: int = 8) -> int | None:
    """A service day for member m inside [lo, hi], their coverage/life window, the provider's
    enrolment, outside admissions; Sundays are thinned."""
    mlo, mhi = w.member_window(m)
    lo = max(lo, mlo)
    if provider is not None:
        lo = max(lo, w.providers[provider]["enrolled"])
    hi = min(hi, mhi)
    if lo > hi:
        return None
    for _ in range(tries):
        d = w.uniform_int(lo, hi)
        if weekday(d) == 6 and w.rng.random() < 0.7:
            continue
        if not w.in_admission(m, d):
            return d
    return None


def em_code(w: World, specialty: str, dist: list[float] | None = None) -> str:
    if dist is None:
        dist = EM_HIGH if specialty in ("oncology", "emergency") else EM_NORMAL
    return f"EM{int(w.rng.choice(5, p=dist)) + 1}"


def professional_lines(w: World, specialty: str) -> list[dict]:
    if specialty == "radiology":
        return [{"code": w.choice(["RAD-110", "RAD-210", "RAD-310"], [0.6, 0.28, 0.12])}]
    if specialty == "physiotherapy":
        return [{"code": "PHY-031" if w.rng.random() < 0.02 else "PHY-010"}]
    lines = [{"code": em_code(w, specialty)}]
    p, codes, wts = PROCS.get(specialty, (0.0, [], []))
    if codes and w.rng.random() < p:
        proc = {"code": w.choice(codes, wts)}
        lines = [proc] if w.rng.random() < 0.2 else lines + [proc]
    return lines


# ---------------------------------------------------------------- baseline stages

def gen_admissions(w: World, book: ClaimBook, pick: Picker, n: int) -> None:
    """Inpatient stays with their facility claims; ~40% arrive by ambulance."""
    cities = [c for c in geo.CITIES]
    wts = np.array([c.weight for c in cities], dtype=float)
    made = 0
    guard = 0
    while made < n and guard < n * 20:
        guard += 1
        c = cities[int(w.rng.choice(len(cities), p=wts / wts.sum()))]
        pool = pick.members(c.name, "all")
        if not pool:
            continue
        m = pool[int(w.rng.integers(len(pool)))]
        if w.rng.random() > min(1.0, 0.25 + w.members[m]["age"] / 90 + 0.15 * w.members[m]["risk"]):
            continue
        hosp_city = c.name if w.hospital_facilities(c.name) else None
        if hosp_city is None:
            continue
        fac = w.choice(w.hospital_facilities(c.name))
        prov = w.facility_provider(fac)
        if prov is None or prov in w.reserved_providers:
            continue
        los = int(min(15, 1 + w.rng.geometric(0.35)))
        mlo, mhi = w.member_window(m)
        lo = max(mlo, w.providers[prov]["enrolled"])
        if lo > mhi - los:
            continue
        admit = w.uniform_int(lo, mhi - los)
        discharge = admit + los
        if not w.admission_free(m, admit, discharge):
            continue
        add_inpatient_stay(w, book, m, fac, prov, admit, discharge)
        made += 1
        if w.rng.random() < 0.4:
            amb = pick.provider("ambulance", None, c.name)
            if amb is not None:
                ambulance_trip(w, book, m, amb, admit, fac)


def add_inpatient_stay(w: World, book: ClaimBook, m: int, fac: int, prov: int, admit: int, discharge: int,
                       tag: str = "") -> int:
    w.add_admission(m, fac, admit, discharge, tag)
    los = discharge - admit
    lines = [{"code": "FAC-IPD", "units": max(1, los)}]
    if w.rng.random() < 0.3:
        lines.append({"code": "FAC-OT"})
    if w.rng.random() < 0.12:
        lines.append({"code": "FAC-ICU", "units": min(max(1, los), 3)})
    return book.add(member=m, provider=prov, day=admit, service_type="facility", pos="inpatient",
                    lines=lines, facility=fac, submit_delay=los + w.uniform_int(1, 15))


def ambulance_trip(w: World, book: ClaimBook, m: int, amb: int, day: int, dest_fac: int,
                   pickup: tuple[float, float] | None = None, miles_ratio: float | None = None,
                   **kw) -> int:
    """One ambulance claim line; miles = road distance (1.05–1.30x straight line) unless overridden."""
    mem = w.members[m]
    f = w.facilities[dest_fac]
    if pickup is None:
        plat, plon = geo.offset_point(mem["lat"], mem["lon"], float(w.rng.uniform(0, 1)), float(w.rng.uniform(0, 6.283)))
    else:
        plat, plon = pickup
    km = haversine(plat, plon, f["lat"], f["lon"])
    ratio = miles_ratio if miles_ratio is not None else float(w.rng.uniform(1.05, 1.30))
    miles = round(km / geo.KM_PER_MILE * ratio + 0.3, 1)
    als = w.rng.random() < 0.15
    code = "AMB-ALS" if als else "AMB-BLS"
    billed = int(round((3500 + 55 * miles) if als else (1500 + 40 * miles), -1))
    line = {"code": code, "billed": billed, "ambulance_miles": miles,
            "pickup_lat": round(plat, 5), "pickup_lon": round(plon, 5),
            "dropoff_lat": f["lat"], "dropoff_lon": f["lon"]}
    return book.add(member=m, provider=amb, day=day, service_type="ambulance", pos="ambulance",
                    lines=[line], facility=dest_fac, **kw)


def gen_referrals(w: World, book: ClaimBook, pick: Picker, n: int) -> None:
    """GP -> specialist/hospital referrals; ~72% lead to a specialist claim within 1–21 days."""
    cities = [c for c in geo.CITIES if not c.is_rural]
    wts = np.array([c.weight for c in cities], dtype=float)
    targets = ("cardiology", "orthopedics", "oncology", "nephrology", "radiology", "physiotherapy", "pediatrics")
    made = 0
    guard = 0
    while made < n and guard < n * 10:
        guard += 1
        c = cities[int(w.rng.choice(len(cities), p=wts / wts.sum()))]
        src = pick.provider("individual", ("general_medicine",), c.name) if w.rng.random() < 0.8 \
            else pick.provider("group", ("general_medicine",), c.name)
        if src is None:
            continue
        if w.rng.random() < 0.12:
            dst = pick.provider("facility", ("none",), c.name)
            spec = "none"
        else:
            spec = w.choice(list(targets), [0.2, 0.22, 0.08, 0.06, 0.18, 0.16, 0.10])
            dst = pick.provider("individual", (spec,), c.name)
        if dst is None or dst == src:
            continue
        m = pick.member_for(spec if spec != "none" else "general_medicine", c.name)
        if m is None:
            continue
        rday = pick_day(w, m, provider=src)
        if rday is None:
            continue
        add_referral(w, src, dst, m, rday)
        made += 1
        if w.rng.random() < 0.72:
            cday = pick_day(w, m, rday + 1, rday + 21, provider=dst, tries=4)
            if cday is None:
                continue
            if spec == "none":
                book.add(member=m, provider=dst, day=cday, service_type="facility", pos="outpatient",
                         lines=[{"code": w.choice(["FAC-OPD", "FAC-DAY"], [0.85, 0.15])}], referring=src)
            else:
                book.add(member=m, provider=dst, day=cday, service_type="professional", pos="office",
                         lines=professional_lines(w, spec), referring=src)


def add_referral(w: World, src: int, dst: int, m: int, day: int, reason: str | None = None) -> None:
    w.referrals.append({"from": src, "to": dst, "member": m, "day": day,
                        "reason_code": reason or f"RSN-{w.uniform_int(1, 30):02d}"})


def gen_walkin_professional(w: World, book: ClaimBook, pick: Picker, target_lines: int,
                            only_provider: int | None = None, month: tuple[int, int] | None = None) -> None:
    profs = [i for i, p in enumerate(w.providers)
             if p["provider_type"] in ("individual", "group") and i not in w.reserved_providers]
    if only_provider is not None:
        profs = [only_provider]
    wts = np.array([w.providers[i]["volume"] for i in profs], dtype=float)
    wts /= wts.sum()
    start = book.lines_by_type["professional"]
    guard = 0
    while book.lines_by_type["professional"] - start < target_lines and guard < target_lines * 10:
        guard += 1
        prov = profs[int(w.rng.choice(len(profs), p=wts))]
        p = w.providers[prov]
        m = pick.member_for(p["specialty"], p["city"])
        if m is None:
            continue
        lo, hi = month if month else (0, LAST_DAY)
        d = pick_day(w, m, lo, hi, provider=prov)
        if d is None:
            continue
        book.add(member=m, provider=prov, day=d, service_type="professional", pos="office",
                 lines=professional_lines(w, p["specialty"]))


def gen_facility_outpatient(w: World, book: ClaimBook, pick: Picker, target_lines: int) -> None:
    hosps = [i for i, p in enumerate(w.providers)
             if p["provider_type"] == "facility" and p["specialty"] == "none" and i not in w.reserved_providers]
    wts = np.array([w.providers[i]["volume"] for i in hosps], dtype=float)
    wts /= wts.sum()
    start = book.lines_by_type["facility"]
    guard = 0
    while book.lines_by_type["facility"] - start < target_lines and guard < target_lines * 10:
        guard += 1
        prov = hosps[int(w.rng.choice(len(hosps), p=wts))]
        p = w.providers[prov]
        m = pick.member_for("general_medicine", p["city"])
        if m is None:
            continue
        d = pick_day(w, m, provider=prov)
        if d is None:
            continue
        code = w.choice(["FAC-OPD", "FAC-ER", "FAC-DAY"], [0.6, 0.3, 0.1])
        book.add(member=m, provider=prov, day=d, service_type="facility", pos="outpatient", lines=[{"code": code}])


def pharmacy_line(w: World, drug: str, days: int | None = None) -> dict:
    dr = DRUGS[drug]
    ds = int(days or dr["typical_days_supply"])
    return {"code": "RX-FILL", "billed": int(round(dr["price_per_day_inr"] * ds * w.rng.uniform(0.95, 1.05), -1)),
            "drug_code": drug, "days_supply": ds}


def gen_pharmacy(w: World, book: ClaimBook, pick: Picker, target_lines: int) -> None:
    chronic = [d for d, r in DRUGS.items() if r["chronic"] and d not in ("DRG-013", "DRG-014")]
    acute = [d for d, r in DRUGS.items() if not r["chronic"]]
    start = book.lines_by_type["pharmacy"]
    cities = [c for c in geo.CITIES]
    cw = np.array([c.weight for c in cities], dtype=float)
    cw /= cw.sum()
    guard = 0
    while book.lines_by_type["pharmacy"] - start < target_lines and guard < target_lines * 10:
        guard += 1
        c = cities[int(w.rng.choice(len(cities), p=cw))]
        pool = pick.members(c.name, "all")
        if not pool:
            continue
        m = pool[int(w.rng.integers(len(pool)))]
        ph = pick.provider("pharmacy", None, c.name)
        if ph is None:
            continue
        mem = w.members[m]
        if mem["chronic"] > 0 and mem["age"] >= 18 and w.rng.random() < 0.55:
            drugs = sorted(set(w.choice(chronic) for _ in range(1 + int(w.rng.random() < 0.4))))
            if m in w.oncology_pool and w.rng.random() < 0.3:
                drugs = ["DRG-013"]
            if m in w.renal_pool and w.rng.random() < 0.3:
                drugs = ["DRG-014"]
            d = pick_day(w, m, 0, 300, provider=ph)
            if d is None:
                continue
            ds = int(DRUGS[drugs[0]]["typical_days_supply"])
            for _ in range(int(w.rng.integers(2, 7))):
                if d > LAST_DAY or not w.ok_day(m, d):
                    break
                book.add(member=m, provider=ph, day=d, service_type="pharmacy", pos="pharmacy",
                         lines=[pharmacy_line(w, dg) for dg in drugs])
                d += int(math.ceil(ds * w.rng.uniform(1.0, 1.2)))
        else:
            d = pick_day(w, m, provider=ph)
            if d is None:
                continue
            n_lines = 1 + int(w.rng.random() < 0.35) + int(w.rng.random() < 0.1)
            drugs = sorted(set(w.choice(acute) for _ in range(n_lines)))
            book.add(member=m, provider=ph, day=d, service_type="pharmacy", pos="pharmacy",
                     lines=[pharmacy_line(w, dg) for dg in drugs])


def lab_lines(w: World) -> list[dict]:
    n = int(w.choice([1, 2, 3, 4], [0.4, 0.3, 0.2, 0.1]))
    picked: list[str] = []
    for _ in range(n * 3):
        code = w.choice(LAB_ORDERABLES, LAB_WEIGHTS)
        if code in picked:
            continue
        panel = LAB_PANEL_OF.get(code)
        if panel and (panel in picked or any(LAB_PANEL_OF.get(x) == panel for x in picked)):
            continue
        if code in LAB_PANEL_OF.values() and any(LAB_PANEL_OF.get(x) == code for x in picked):
            continue
        picked.append(code)
        if len(picked) == n:
            break
    return [{"code": c} for c in sorted(picked)]


def gen_lab(w: World, book: ClaimBook, pick: Picker, target_lines: int) -> None:
    start = book.lines_by_type["lab"]
    cities = [c for c in geo.CITIES]
    cw = np.array([c.weight for c in cities], dtype=float)
    cw /= cw.sum()
    guard = 0
    while book.lines_by_type["lab"] - start < target_lines and guard < target_lines * 10:
        guard += 1
        c = cities[int(w.rng.choice(len(cities), p=cw))]
        pool = pick.members(c.name, "all")
        lab = pick.provider("lab", None, c.name)
        if not pool or lab is None:
            continue
        m = pool[int(w.rng.integers(len(pool)))]
        d = pick_day(w, m, provider=lab)
        if d is None:
            continue
        book.add(member=m, provider=lab, day=d, service_type="lab", pos="lab", lines=lab_lines(w))


def gen_ambulance(w: World, book: ClaimBook, pick: Picker, target_lines: int) -> None:
    start = book.lines_by_type["ambulance"]
    cities = [c for c in geo.CITIES]
    cw = np.array([c.weight for c in cities], dtype=float)
    cw /= cw.sum()
    guard = 0
    while book.lines_by_type["ambulance"] - start < target_lines and guard < target_lines * 10:
        guard += 1
        c = cities[int(w.rng.choice(len(cities), p=cw))]
        pool = pick.members(c.name, "all")
        amb = pick.provider("ambulance", None, c.name)
        if not pool or amb is None:
            continue
        m = pool[int(w.rng.integers(len(pool)))]
        hosp = w.hospital_facilities(c.name)
        mem = w.members[m]
        dest = min(hosp, key=lambda f: haversine(mem["lat"], mem["lon"], w.facilities[f]["lat"], w.facilities[f]["lon"]))
        d = pick_day(w, m, provider=amb)
        if d is None:
            continue
        ambulance_trip(w, book, m, amb, d, dest)


def gen_series(w: World, book: ClaimBook, pick: Picker, target_lines: int, kind: str) -> None:
    """Behavioral-health session series, home-health episodes and DME rental chains."""
    stype = {"behavioral": "behavioral_health", "home_health": "home_health", "dme": "dme"}[kind]
    start = book.lines_by_type[stype]
    cities = [c for c in geo.CITIES]
    cw = np.array([c.weight for c in cities], dtype=float)
    cw /= cw.sum()
    guard = 0
    while book.lines_by_type[stype] - start < target_lines and guard < target_lines * 10:
        guard += 1
        c = cities[int(w.rng.choice(len(cities), p=cw))]
        prov = pick.provider(kind, None, c.name)
        pool = pick.members(c.name, "older" if kind != "behavioral" else "adult")
        if prov is None or not pool:
            continue
        m = pool[int(w.rng.integers(len(pool)))]
        d = pick_day(w, m, 0, LAST_DAY - 30, provider=prov)
        if d is None:
            continue
        if kind == "behavioral":
            for k in range(int(w.rng.integers(3, 11))):
                if d > LAST_DAY or not w.ok_day(m, d):
                    break
                code = "BH-090" if k == 0 else w.choice(["BH-030", "BH-045", "BH-060"], [0.25, 0.35, 0.4])
                book.add(member=m, provider=prov, day=d, service_type=stype, pos="office", lines=[{"code": code}])
                d += 7 + w.uniform_int(-1, 2)
        elif kind == "home_health":
            code = w.choice(["HH-010", "HH-020", "HH-030"], [0.5, 0.3, 0.2])
            for _ in range(int(w.rng.integers(4, 13))):
                if d > LAST_DAY or not w.ok_day(m, d):
                    break
                book.add(member=m, provider=prov, day=d, service_type=stype, pos="home", lines=[{"code": code}])
                d += w.uniform_int(2, 4)
        else:
            item = w.choice(sorted(DME))
            it = DME[item]
            if w.rng.random() < 0.2:
                book.add(member=m, provider=prov, day=d, service_type=stype, pos="home",
                         lines=[{"code": "DME-BUY", "billed": int(it["purchase_price_inr"]), "dme_item_code": item}])
                continue
            months = int(w.rng.integers(2, min(int(it["max_rental_months"]), 12) + 1))
            for k in range(1, months + 1):
                if d > LAST_DAY or not w.ok_day(m, d):
                    break
                book.add(member=m, provider=prov, day=d, service_type=stype, pos="home",
                         lines=[{"code": "DME-RENT", "billed": int(it["monthly_rent_inr"]), "dme_item_code": item,
                                 "rental_month": k}])
                d += 30


def gen_noise(w: World, book: ClaimBook, pick: Picker) -> None:
    """~2% innocent noise: short bursts at random providers + legitimate corrections/voids."""
    profs = [i for i, p in enumerate(w.providers)
             if p["provider_type"] in ("individual", "group") and i not in w.reserved_providers]
    for k in w.rng.choice(len(profs), size=30, replace=False):
        prov = profs[int(k)]
        start = w.uniform_int(0, LAST_DAY - 30)
        gen_walkin_professional(w, book, pick, int(w.rng.integers(8, 20)), only_provider=prov, month=(start, start + 29))
    # legitimate corrections (freq 7) and voids (freq 8) on random paid claims
    candidates = [h["tk"] for h in book.headers
                  if not h.get("dropped") and h["status"] == "paid" and h["freq"] == 1 and h["provider"] not in w.reserved_providers
                  and h["service_type"] in ("professional", "lab", "pharmacy")]
    picks = w.rng.choice(len(candidates), size=150, replace=False)
    for j, k in enumerate(picks):
        add_correction(w, book, candidates[int(k)], void=j % 5 == 0)


def add_correction(w: World, book: ClaimBook, tk: int, void: bool = False) -> int:
    """Replacement (freq 7) or void (freq 8) of an existing claim: same member/provider/date/codes."""
    h = book.headers[tk]
    lines = []
    for ln in book.lines[tk]:
        new = {k: ln[k] for k in ("ambulance_miles", "pickup_lat", "pickup_lon", "dropoff_lat", "dropoff_lon",
                                  "days_supply", "drug_code", "dme_item_code", "rental_month") if ln[k] is not None}
        new.update({"code": ln["procedure_code"], "units": ln["units"],
                    "billed": ln["billed_amount"] if void else int(round(ln["billed_amount"] * w.rng.uniform(0.9, 1.05), -1))})
        lines.append(new)
    sub = min(LAST_DAY, h["submitted"] + w.uniform_int(3, 15))
    new_tk = book.add(member=h["member"], provider=h["provider"], day=h["day"], service_type=h["service_type"],
                      pos=h["pos"], lines=lines, facility=h["facility"], billing=h["billing"], referring=h["referring"],
                      freq=8 if void else 7, original=tk, submit_delay=sub - h["day"], dx=h["dx"], denied_ok=False)
    if void:
        for ln in book.lines[new_tk]:
            ln["paid_amount"] = 0
        book.headers[new_tk]["status"] = "denied"
    return new_tk


def dedupe_baseline(w: World, book: ClaimBook) -> int:
    """Drop accidental exact duplicates among baseline originals so R01 only fires on planted data."""
    seen: set[tuple] = set()
    drop: set[int] = set()
    for h in book.headers:
        if h["freq"] != 1:
            continue
        for ln in book.lines[h["tk"]]:
            key = (h["member"], h["provider"], ln["procedure_code"], ln["drug_code"], ln["dme_item_code"],
                   h["day"], ln["units"])
            if key in seen:
                drop.add(h["tk"])
            seen.add(key)
    for tk in drop:
        h = book.headers[tk]
        book.lines_by_type[h["service_type"]] -= len(book.lines[tk])
        book.lines[tk] = []
        h["dropped"] = True
    return len(drop)


def generate_baseline(w: World, book: ClaimBook, n_lines: int) -> None:
    pick = Picker(w)
    target = {k: int(v * n_lines) for k, v in SERVICE_SHARE.items()}
    gen_admissions(w, book, pick, 2430)
    gen_referrals(w, book, pick, 8300)
    gen_walkin_professional(w, book, pick, target["professional"] - book.lines_by_type["professional"])
    gen_facility_outpatient(w, book, pick, max(0, target["facility"] - book.lines_by_type["facility"]))
    gen_pharmacy(w, book, pick, target["pharmacy"])
    gen_lab(w, book, pick, target["lab"])
    gen_ambulance(w, book, pick, max(0, target["ambulance"] - book.lines_by_type["ambulance"]))
    gen_series(w, book, pick, target["behavioral_health"], "behavioral")
    gen_series(w, book, pick, target["home_health"], "home_health")
    gen_series(w, book, pick, target["dme"], "dme")
    dedupe_baseline(w, book)
    gen_noise(w, book, pick)
