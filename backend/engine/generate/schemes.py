"""Planted fraud S1–S8 (S9 document tampering is planted by documents.py in M2).

Each scheme has reserve() (runs before baseline claims so baseline never touches its
entities) and plant() (adds its claims and ground-truth rows). Numbers are chosen so the
spec's rules (A3) and thresholds (config.py) actually fire.
"""

from __future__ import annotations

import math

from . import geo
from .claims import (
    ClaimBook,
    add_inpatient_stay,
    add_referral,
    ambulance_trip,
    em_code,
    lab_lines,
    pharmacy_line,
    pick_day,
    professional_lines,
    weekday,
)
from .entities import LAST_DAY, TODAY, World, day_iso, haversine, iso_day, short_hash

SCHEME_INFO = {
    "S1": ("Referral-kickback ring", "4 providers refer members around a closed loop A→B→C→D→A; two owners share one bank account."),
    "S2": ("Phantom ambulance", "One ambulance provider bills miles 1.8–3x the map distance and trips while members are inpatient elsewhere."),
    "S3": ("Upcoding drift", "A general-medicine provider's EM5 share rises from 12% to 58% over 9 months with average-risk patients."),
    "S4": ("Duplicate billing", "One provider resubmits 40 exact and 30 near-duplicate claims without marking them as corrections."),
    "S5": ("Fake-card identity cluster", "25 recently enrolled members share 2 phone numbers and 1 address; 4 have services after death."),
    "S6": ("Claim-splitting network", "3 providers sharing one owner and facility bill ~48 claims just under the ₹50,000 review threshold."),
    "S7": ("Lab unbundling", "A lab bills panel components separately instead of the panel code on 80 member-days."),
    "S8": ("Impossible hours and travel", "A therapist bills 26–31 hours on 6 days; one member is seen in two cities ~700 km apart the same day."),
}

CTX: dict[str, dict] = {}


def _new_owner(w: World, name: str) -> int:
    w.owners.append({"owner_name": name,
                     "bank_account_hash": short_hash(f"bank-new-{w.seed}-{len(w.owners)}"),
                     "address_hash": short_hash(f"oaddr-new-{w.seed}-{len(w.owners)}")})
    return len(w.owners) - 1


def _set_owner(w: World, prov: int, owner: int) -> None:
    w.providers[prov]["owner"] = owner
    w.providers[prov]["bank_account_hash"] = w.owners[owner]["bank_account_hash"]


def month_start(k: int) -> int:
    """Day index of the first day of month k (k=0 is April 2025)."""
    y, mth = 2025 + (3 + k) // 12, (3 + k) % 12 + 1
    return iso_day(f"{y}-{mth:02d}-01")


def members_ok(w: World, pool: list[int], day: int) -> list[int]:
    return [m for m in pool if w.ok_day(m, day)]


# ================================================================ reserve

def reserve_all(w: World) -> None:
    # S1 ring in Lucknow
    city = "Lucknow"
    ring = [w.reserve_provider("individual", s, city) for s in ("general_medicine", "cardiology", "radiology", "orthopedics")]
    o1 = _new_owner(w, f"{w.fake.last_name()} Medicare LLP")
    o2 = _new_owner(w, f"{w.fake.last_name()} Health Services Pvt Ltd")
    w.owners[o2]["bank_account_hash"] = w.owners[o1]["bank_account_hash"]
    for p, o in zip(ring, (o1, o1, o2, o2)):
        _set_owner(w, p, o)
    CTX["S1"] = {"ring": ring, "owners": [o1, o2], "pool": w.city_members(city, 25, 80, exclude_pools=True)[:50]}

    # S2 phantom ambulance in Mumbai
    CTX["S2"] = {"amb": w.reserve_provider("ambulance", None, "Mumbai")}

    # S3 upcoding drift in Nagpur
    CTX["S3"] = {"prov": w.reserve_provider("individual", "general_medicine", "Nagpur")}

    # S4 duplicate billing in Chennai
    CTX["S4"] = {"prov": w.reserve_provider("individual", "general_medicine", "Chennai")}

    # S5 identity cluster in Kanpur
    mems = w.city_members("Kanpur", 22, 70, exclude_pools=True)
    picks = [mems[int(k)] for k in sorted(w.rng.choice(len(mems), size=25, replace=False))]
    w.reserved_members.update(picks)
    phones = [short_hash(f"s5-phone-{w.seed}-{k}") for k in range(2)]
    addr = short_hash(f"s5-addr-{w.seed}")
    for j, m in enumerate(picks):
        mem = w.members[m]
        mem["cov_start"] = w.uniform_int(iso_day("2026-02-01"), iso_day("2026-04-15"))
        mem["cov_end"] = 730
        mem["phone_hash"] = phones[0] if j < 13 else phones[1]
        mem["address_hash"] = addr
        mem["death"] = 10_000
        mem["risk"] = round(float(w.rng.uniform(0.7, 1.2)), 3)
    deceased = picks[:4]
    for m in deceased:
        w.members[m]["death"] = w.uniform_int(iso_day("2026-05-10"), iso_day("2026-06-20"))
    gp = w.reserve_provider("individual", "general_medicine", "Kanpur")
    ph = w.reserve_provider("pharmacy", None, "Kanpur")
    w.providers[gp]["enrolled"] = iso_day("2026-01-15")
    w.providers[ph]["enrolled"] = iso_day("2026-02-01")
    CTX["S5"] = {"members": picks, "deceased": deceased, "gp": gp, "ph": ph}

    # S6 claim-splitting network in Pune: shared owner + shared facility
    a = w.reserve_provider("individual", "orthopedics", "Pune")
    b = w.reserve_provider("individual", "physiotherapy", "Pune")
    c = w.reserve_provider("individual", "orthopedics", "Pune")
    owner = _new_owner(w, "R. Vardhan Healthcare LLP")
    clinics = [i for i, f in enumerate(w.facilities) if f["city"] == "Pune" and f["facility_type"] == "clinic"]
    fac = clinics[0]
    others = [i for i, f in enumerate(w.facilities) if f["city"] == "Pune" and i != fac and f["facility_type"] in ("clinic", "hospital")]
    for i, p in enumerate(w.providers):  # nobody else practices at the network's facility
        if p["primary_facility"] == fac and i not in (a, b, c):
            p["primary_facility"] = others[i % len(others)]
    f = w.facilities[fac]
    f.update({"name": "Sunrise Day Surgery, Pune", "owner": owner})
    names = {a: "Sunrise Ortho Clinic", b: "Sunrise Physio Centre", c: "Vardhan Bone & Joint"}
    for p in (a, b, c):
        pr = w.providers[p]
        pr.update({"name": names[p], "provider_type": "group", "primary_facility": fac,
                   "lat": f["lat"], "lon": f["lon"], "pincode": f["pincode"]})
        _set_owner(w, p, owner)
    w.providers[a]["enrolled"] = iso_day("2025-11-02")
    w.providers[b]["enrolled"] = iso_day("2025-11-02")
    w.providers[c]["enrolled"] = iso_day("2026-05-04")
    pool = w.city_members("Pune", 35, 85, exclude_pools=True)
    CTX["S6"] = {"provs": [a, b, c], "owner": owner, "fac": fac,
                 "pool": [pool[int(k)] for k in sorted(w.rng.choice(len(pool), size=38, replace=False))]}

    # S7 unbundling lab in Bengaluru
    CTX["S7"] = {"lab": w.reserve_provider("lab", None, "Bengaluru")}

    # S8 impossible hours (Delhi therapist) + impossible travel (Mumbai member)
    th = w.reserve_provider("behavioral", None, "Delhi")
    traveler = w.city_members("Mumbai", 30, 60, exclude_pools=True)[7]
    w.reserved_members.add(traveler)
    CTX["S8"] = {"therapist": th, "traveler": traveler}


# ================================================================ plant

def plant_all(w: World, book: ClaimBook) -> None:
    plant_s1(w, book)
    plant_s2(w, book)
    plant_s3(w, book)
    plant_s4(w, book)
    plant_s5(w, book)
    plant_s6(w, book)
    plant_s7(w, book)
    plant_s8(w, book)


def plant_s1(w: World, book: ClaimBook) -> None:
    ctx = CTX["S1"]
    ring, pool = ctx["ring"], ctx["pool"]
    inflated = {
        "general_medicine": lambda: [{"code": w.choice(["EM4", "EM5"], [0.4, 0.6])}],
        "cardiology": lambda: [{"code": "EM4"}, {"code": w.choice(["CAR-220", "CAR-410"], [0.5, 0.5])}],
        "radiology": lambda: [{"code": w.choice(["RAD-210", "RAD-310"], [0.4, 0.6])}],
        "orthopedics": lambda: [{"code": "EM4"}, {"code": w.choice(["ORT-101", "ORT-305"], [0.6, 0.4])}],
    }
    received: dict[int, list[int]] = {p: [] for p in ring}
    for k in range(4):
        src, dst = ring[k], ring[(k + 1) % 4]
        spec = w.providers[dst]["specialty"]
        for _ in range(40):
            m = pool[int(w.rng.integers(len(pool)))]
            rday = pick_day(w, m, 180, LAST_DAY - 12, provider=src)
            if rday is None:
                continue
            add_referral(w, src, dst, m, rday, reason="RSN-07")
            if w.rng.random() < 0.75:
                cday = pick_day(w, m, rday + 1, rday + 10, provider=dst)
                if cday is not None:
                    received[dst].append(book.add(member=m, provider=dst, day=cday, service_type="professional",
                                                  pos="office", lines=inflated[spec](), referring=src))
    # some ordinary activity so the ring is not 100% of their business
    lucknow_gps = w.providers_where("individual", "general_medicine", "Lucknow")
    adults = w.city_members("Lucknow", 18, 90)
    for p in ring:
        spec = w.providers[p]["specialty"]
        for _ in range(5):
            src = w.choice(lucknow_gps)
            m = w.choice(adults)
            d = pick_day(w, m, provider=p)
            if d is None:
                continue
            add_referral(w, src, p, m, max(0, d - 3))
            book.add(member=m, provider=p, day=d, service_type="professional", pos="office",
                     lines=professional_lines(w, spec), referring=src)
        for _ in range(25):
            m = w.choice(adults)
            d = pick_day(w, m, provider=p)
            if d is not None:
                book.add(member=m, provider=p, day=d, service_type="professional", pos="office",
                         lines=professional_lines(w, spec))
    roles = ["ring_member_A", "ring_member_B", "ring_member_C", "ring_member_D"]
    for p, role in zip(ring, roles):
        w.add_truth(entity_type="provider", entity_index=p, scheme_id="S1", role=role, is_decoy=0,
                    notes="Closed referral loop; receives most inbound referrals from the ring", claim_tks=received[p])
    for o in ctx["owners"]:
        w.add_truth(entity_type="owner", entity_index=o, scheme_id="S1", role="shared_bank_owner", is_decoy=0,
                    notes="Shares bank_account_hash with the other ring owner")


def plant_s2(w: World, book: ClaimBook) -> None:
    amb = CTX["S2"]["amb"]
    hosps = w.hospital_facilities("Mumbai")
    adults = w.city_members("Mumbai", 18, 90)
    bad: list[int] = []
    # 42 trips with inflated miles over long legs (so 1.5x + 5 mi is clearly exceeded)
    while len(bad) < 42:
        m = w.choice(adults)
        d = pick_day(w, m, 300, 540, provider=amb)
        if d is None:
            continue
        dest = w.choice(hosps)
        f = w.facilities[dest]
        km = float(w.rng.uniform(28, 50))
        pickup = geo.offset_point(f["lat"], f["lon"], km, float(w.rng.uniform(0.3, 2.0)))
        bad.append(ambulance_trip(w, book, m, amb, d, dest, pickup=pickup,
                                  miles_ratio=float(w.rng.uniform(1.8, 3.0)), allowed_ratio=1.0))
    # 10 trips while the member is inpatient at another hospital
    inpatient: list[int] = []
    guard = 0
    while len(inpatient) < 10 and guard < 2000:
        guard += 1
        m = w.choice(adults)
        h1 = w.choice(hosps)
        prov1 = w.facility_provider(h1)
        los = w.uniform_int(4, 8)
        lo, hi = w.member_window(m)
        start = w.uniform_int(max(lo, 360), max(lo, 360) + 120)
        if start + los > min(hi, 535) or not w.admission_free(m, start, start + los) or prov1 is None:
            continue
        add_inpatient_stay(w, book, m, h1, prov1, start, start + los, tag="S2")
        trip_day = w.uniform_int(start + 1, start + los - 1)
        h2 = w.choice([h for h in hosps if h != h1])
        inpatient.append(ambulance_trip(w, book, m, amb, trip_day, h2, allowed_ratio=1.0))
    # 8 ordinary trips
    for _ in range(8):
        m = w.choice(adults)
        d = pick_day(w, m, 300, 540, provider=amb)
        if d is not None:
            mem = w.members[m]
            dest = min(hosps, key=lambda h: haversine(mem["lat"], mem["lon"], w.facilities[h]["lat"], w.facilities[h]["lon"]))
            ambulance_trip(w, book, m, amb, d, dest)
    w.add_truth(entity_type="provider", entity_index=amb, scheme_id="S2", role="billing_provider", is_decoy=0,
                notes=f"{len(bad)} trips with miles 1.8–3x map distance; {len(inpatient)} trips while member inpatient elsewhere",
                claim_tks=bad + inpatient)


def plant_s3(w: World, book: ClaimBook) -> None:
    prov = CTX["S3"]["prov"]
    pool = w.city_members("Nagpur", 18, 85, exclude_pools=True)
    drift: list[int] = []
    for k in range(18):
        lo, hi = month_start(k), (month_start(k + 1) - 1 if k < 17 else LAST_DAY)
        em5 = 0.11 if k < 9 else 0.12 + (0.58 - 0.12) * (k - 9) / 8
        rest = [0.10, 0.25, 0.35, 0.20]
        scale = (1 - em5) / sum(rest)
        dist = [r * scale for r in rest] + [em5]
        for _ in range(20):
            m = w.choice(pool)
            d = pick_day(w, m, lo, hi, provider=prov)
            if d is None:
                continue
            code = em_code(w, "general_medicine", dist)
            tk = book.add(member=m, provider=prov, day=d, service_type="professional", pos="office", lines=[{"code": code}])
            if k >= 9 and code == "EM5":
                drift.append(tk)
    w.add_truth(entity_type="provider", entity_index=prov, scheme_id="S3", role="billing_provider", is_decoy=0,
                notes="EM5 share rises 12% -> 58% from Jan to Sep 2026; patient risk stays average", claim_tks=drift)


def plant_s4(w: World, book: ClaimBook) -> None:
    prov = CTX["S4"]["prov"]
    pool = w.city_members("Chennai", 0, 90)
    originals: list[int] = []
    while len(originals) < 160:
        m = w.choice(pool)
        d = pick_day(w, m, 0, LAST_DAY - 25, provider=prov)
        if d is not None:
            originals.append(book.add(member=m, provider=prov, day=d, service_type="professional", pos="office",
                                      lines=professional_lines(w, "general_medicine")))
    order = [originals[int(k)] for k in w.rng.permutation(len(originals))]
    dups: list[int] = []
    n_exact = n_near = 0
    for tk in order:
        if n_exact == 40 and n_near == 30:
            break
        h = book.headers[tk]
        near = n_exact == 40
        day = h["day"]
        if near:
            for shift in ([1, -1] if w.rng.random() < 0.5 else [-1, 1]):
                if w.ok_day(h["member"], day + shift):
                    day += shift
                    break
            else:
                continue  # cannot shift by a day: use another original
            n_near += 1
        else:
            n_exact += 1
        lines = []
        for ln in book.lines[tk]:
            billed = ln["billed_amount"]
            if near:
                f = float(w.rng.choice([w.rng.uniform(0.97, 0.995), w.rng.uniform(1.005, 1.03)]))
                billed = int(round(billed * f))
            lines.append({"code": ln["procedure_code"], "units": ln["units"], "billed": billed})
        delay = (h["submitted"] - day) + w.uniform_int(5, 20)
        dups.append(book.add(member=h["member"], provider=prov, day=day, service_type="professional", pos="office",
                             lines=lines, submit_delay=delay, dx=h["dx"]))
    w.add_truth(entity_type="provider", entity_index=prov, scheme_id="S4", role="billing_provider", is_decoy=0,
                notes="40 exact duplicates + 30 near duplicates (±1 day, ±3% amount), frequency_code 1", claim_tks=dups)


def plant_s5(w: World, book: ClaimBook) -> None:
    ctx = CTX["S5"]
    gp, ph = ctx["gp"], ctx["ph"]
    by_member: dict[int, list[int]] = {}
    for m in ctx["members"]:
        mem = w.members[m]
        tks: list[int] = []
        deceased = m in ctx["deceased"]
        lo = mem["cov_start"] + 5
        if deceased:
            plan = [(lo, mem["death"] - 1)] + [(mem["death"] + 3, min(LAST_DAY, mem["death"] + 90))] * w.uniform_int(2, 3)
        else:
            plan = [(lo, LAST_DAY)] * w.uniform_int(3, 5)
        for a, b in plan:
            if a > b:
                continue
            d = w.uniform_int(a, b)
            if w.in_admission(m, d):
                continue
            if w.rng.random() < 0.6:
                tks.append(book.add(member=m, provider=gp, day=d, service_type="professional", pos="office",
                                    lines=[{"code": w.choice(["EM3", "EM4"], [0.4, 0.6])}]))
            else:
                tks.append(book.add(member=m, provider=ph, day=d, service_type="pharmacy", pos="pharmacy",
                                    lines=[pharmacy_line(w, w.choice(["DRG-005", "DRG-007", "DRG-013"]))]))
        by_member[m] = tks
    for m, tks in by_member.items():
        role = "deceased_identity" if m in ctx["deceased"] else "shared_identity"
        note = "Service after date_of_death" if m in ctx["deceased"] else "Shares phone/address with the cluster"
        w.add_truth(entity_type="member", entity_index=m, scheme_id="S5", role=role, is_decoy=0, notes=note, claim_tks=tks)
    for p, role in ((gp, "billing_provider"), (ph, "billing_pharmacy")):
        w.add_truth(entity_type="provider", entity_index=p, scheme_id="S5", role=role, is_decoy=0,
                    notes="Recently enrolled; serves the identity cluster", all_claims_of_provider=True)


def plant_s6(w: World, book: ClaimBook) -> None:
    ctx = CTX["S6"]
    a, b, c = ctx["provs"]
    pool = ctx["pool"]
    adults = w.city_members("Pune", 18, 90)
    # pre-burst: ordinary low volume
    for p, code_fn in ((a, lambda: [{"code": em_code(w, "orthopedics")}]),
                       (b, lambda: [{"code": "PHY-010"}]),
                       (c, lambda: [{"code": em_code(w, "orthopedics")}])):
        start = w.providers[p]["enrolled"]
        for k in range(18):
            lo, hi = month_start(k), month_start(k + 1) - 1
            if hi < start or lo >= iso_day("2026-07-01"):
                continue
            for _ in range(w.uniform_int(1, 2)):
                m = w.choice(adults)
                d = pick_day(w, m, max(lo, start), hi, provider=p)
                if d is not None:
                    book.add(member=m, provider=p, day=d, service_type="professional", pos="office", lines=code_fn())
    # burst: 48 claims just under the review threshold, 9 Jul – 21 Sep 2026
    plan = [(a, "ORT-214")] * 13 + [(a, "ORT-219")] * 11 + [(b, "PHY-031")] * 12 + [(c, "ORT-214")] * 8 + [(c, "ORT-219")] * 4
    order = [plan[int(k)] for k in w.rng.permutation(len(plan))]
    first, last_paid, last = iso_day("2026-07-09"), iso_day("2026-08-24"), iso_day("2026-09-21")
    first_pending = iso_day("2026-09-06")
    days = sorted([w.uniform_int(first, last_paid) for _ in range(36)]) + sorted([w.uniform_int(first_pending, last) for _ in range(12)])
    days[0], days[-1] = first, last
    n_low = 5
    burst: dict[int, list[int]] = {a: [], b: [], c: []}
    used: set[tuple[int, int, str, int]] = set()
    for j, ((prov, code), day) in enumerate(zip(order, days)):
        m = None
        for _ in range(50):
            cand = w.choice(pool)
            if w.ok_day(cand, day) and (cand, prov, code, day) not in used:
                m = cand
                used.add((cand, prov, code, day))
                break
        if m is None:
            continue
        billed = w.uniform_int(310, 399) * 100 if j < n_low else w.uniform_int(400, 498) * 100
        pending = j >= 36
        if pending:
            delay = w.uniform_int(1, 3)
            release = max(TODAY + 1, min(TODAY + 3, day + delay + 10))
        else:
            delay, release = w.uniform_int(1, 5), None
        referring = a if prov == b else (b if prov == c and w.rng.random() < 0.75 else None)
        if referring is not None:
            add_referral(w, referring, prov, m, max(0, day - w.uniform_int(1, 5)), reason="RSN-12")
        tk = book.add(member=m, provider=prov, day=day, service_type="professional", pos="outpatient",
                      lines=[{"code": code, "billed": billed}], referring=referring, submit_delay=delay,
                      release=release, allowed_ratio=1.0, denied_ok=False)
        burst[prov].append(tk)
    for p, role in ((a, "billing_provider"), (b, "billing_provider"), (c, "billing_provider")):
        w.add_truth(entity_type="provider", entity_index=p, scheme_id="S6", role=role, is_decoy=0,
                    notes="Claims ₹31,000–₹49,800, just under the ₹50,000 review threshold", claim_tks=burst[p])
    all_burst = burst[a] + burst[b] + burst[c]
    w.add_truth(entity_type="owner", entity_index=ctx["owner"], scheme_id="S6", role="shared_owner", is_decoy=0,
                notes="Owns all 3 providers", claim_tks=all_burst)
    w.add_truth(entity_type="facility", entity_index=ctx["fac"], scheme_id="S6", role="shared_facility", is_decoy=0,
                notes="Primary facility of all 3 providers", claim_tks=all_burst)


def plant_s7(w: World, book: ClaimBook) -> None:
    lab = CTX["S7"]["lab"]
    pool = w.city_members("Bengaluru", 0, 90)
    for _ in range(120):
        m = w.choice(pool)
        d = pick_day(w, m, provider=lab)
        if d is not None:
            book.add(member=m, provider=lab, day=d, service_type="lab", pos="lab", lines=lab_lines(w))
    panels = {"LAB-100": ["LAB-101", "LAB-102", "LAB-103", "LAB-104"],
              "LAB-200": ["LAB-201", "LAB-202", "LAB-203"],
              "LAB-300": ["LAB-301", "LAB-302", "LAB-303"]}
    unbundled: list[int] = []
    while len(unbundled) < 80:
        m = w.choice(pool)
        d = pick_day(w, m, 60, LAST_DAY, provider=lab)
        if d is None:
            continue
        chosen = sorted(w.rng.choice(sorted(panels), size=w.uniform_int(1, 2), replace=False).tolist())
        lines = [{"code": comp} for pnl in chosen for comp in panels[pnl]]
        unbundled.append(book.add(member=m, provider=lab, day=d, service_type="lab", pos="lab", lines=lines))
    w.add_truth(entity_type="provider", entity_index=lab, scheme_id="S7", role="billing_provider", is_decoy=0,
                notes="Panel components billed separately on the same member/date", claim_tks=unbundled)


def plant_s8(w: World, book: ClaimBook) -> None:
    ctx = CTX["S8"]
    th = ctx["therapist"]
    adults = w.city_members("Delhi", 18, 80)
    for _ in range(14):  # ordinary weekly series
        m = w.choice(adults)
        d = pick_day(w, m, 0, LAST_DAY - 60, provider=th)
        if d is None:
            continue
        for k in range(w.uniform_int(4, 8)):
            if not w.ok_day(m, d):
                break
            book.add(member=m, provider=th, day=d, service_type="behavioral_health", pos="office",
                     lines=[{"code": "BH-090" if k == 0 else "BH-060"}])
            d += 7
    candidates = [d for d in range(iso_day("2026-02-01"), iso_day("2026-09-20")) if weekday(d) < 5]
    heavy_days = sorted(int(x) for x in w.rng.choice(candidates, size=6, replace=False))
    heavy: list[int] = []
    for d in heavy_days:
        hours = w.uniform_int(26, 31)
        avail = members_ok(w, adults, d)
        chosen = [avail[int(k)] for k in w.rng.choice(len(avail), size=hours, replace=False)]
        for m in chosen:
            heavy.append(book.add(member=m, provider=th, day=d, service_type="behavioral_health", pos="office",
                                  lines=[{"code": "BH-060"}]))
    w.add_truth(entity_type="provider", entity_index=th, scheme_id="S8", role="billing_provider", is_decoy=0,
                notes=f"26–31 hours billed on 6 days ({', '.join(day_iso(d) for d in heavy_days)})", claim_tks=heavy)
    # impossible travel: Mumbai member seen in Mumbai and Nagpur on the same day
    m = ctx["traveler"]
    day = next(d for d in range(500, 540) if w.ok_day(m, d) and weekday(d) < 5)
    mum = w.choice(w.providers_where("individual", "general_medicine", "Mumbai"))
    nag = w.choice(w.providers_where("individual", "general_medicine", "Nagpur"))
    t1 = book.add(member=m, provider=mum, day=day, service_type="professional", pos="office", lines=[{"code": "EM3"}])
    t2 = book.add(member=m, provider=nag, day=day, service_type="professional", pos="office", lines=[{"code": "EM4"}])
    km = haversine(w.facilities[w.providers[mum]["primary_facility"]]["lat"], w.facilities[w.providers[mum]["primary_facility"]]["lon"],
                   w.facilities[w.providers[nag]["primary_facility"]]["lat"], w.facilities[w.providers[nag]["primary_facility"]]["lon"])
    w.add_truth(entity_type="member", entity_index=m, scheme_id="S8", role="impossible_travel", is_decoy=0,
                notes=f"Seen in Mumbai and Nagpur on {day_iso(day)} ({math.floor(km)} km apart)", claim_tks=[t1, t2])
