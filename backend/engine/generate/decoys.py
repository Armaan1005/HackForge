"""Honest decoys D1–D10: each trips a detector on purpose but has an innocent explanation
that exoneration (A8) or the rule logic (A3) must recognise. Like schemes.py, reserve()
runs before baseline claims and plant() after."""

from __future__ import annotations

from . import geo
from .claims import (
    ClaimBook,
    add_correction,
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
from .entities import LAST_DAY, World, haversine, iso_day
from .schemes import _new_owner, month_start

DECOY_INFO = {
    "D1": ("Sole rural hospital", "Only hospital within 60 km; high volume matches its catchment population."),
    "D2": ("High-complexity oncologist", "High EM5 share explained by very sick patients (risk score ≈ 2.9)."),
    "D3": ("Bus-accident emergency cluster", "30 members brought to one hospital on the same day by several providers."),
    "D4": ("Teaching hospital", "Very high inbound referral concentration, from many unrelated sources."),
    "D5": ("Monsoon dengue burst", "Pediatric clinic lab/visit spike in Jul–Sep, region-wide across Mumbai."),
    "D6": ("Dialysis center", "Members dialysed 3 times a week: a chronic schedule, not excessive frequency."),
    "D7": ("Legit group practice", "5 providers share one owner and facility with normal billing."),
    "D8": ("Corrected claims", "Replacement claims (frequency_code 7) that look like duplicates."),
    "D9": ("Home health after discharge", "Home visits start the day after a hospital discharge."),
    "D10": ("Pharmacy next to a hospital", "High dispensing volume because it sits beside a large hospital."),
}

CTX: dict[str, dict] = {}


def _hospital_provider(w: World, city: str, biggest: bool = True) -> tuple[int, int]:
    """(facility, provider) of the largest (or any) hospital in the city with a free provider."""
    facs = sorted(w.hospital_facilities(city), key=lambda f: (-w.facilities[f]["bed_count"], f))
    for fac in facs:
        p = w.facility_provider(fac)
        if p is not None and p not in w.reserved_providers:
            return fac, p
    raise RuntimeError(f"no hospital provider in {city}")


def reserve_all(w: World) -> None:
    # D1: the two rural towns' only hospitals (not reserved; baseline volume + extra outpatient)
    CTX["D1"] = {"hosp": [_hospital_provider(w, town) for town in ("Gadchiroli", "Bahraich")]}
    # D2: oncologist with very sick patients
    CTX["D2"] = {"prov": w.reserve_provider("individual", "oncology", "Chennai")}
    # D3: event hospital etc. chosen at plant time (not reserved)
    # D4: teaching hospital in Chennai
    fac, prov = _hospital_provider(w, "Chennai")
    w.facilities[fac].update({"name": "Coromandel Teaching Hospital, Chennai", "bed_count": 1200})
    w.providers[prov]["name"] = "Coromandel Teaching Hospital"
    CTX["D4"] = {"fac": fac, "prov": prov}
    # D6: dialysis center provider (facility type with nephrology specialty)
    dial = sorted(i for i, p in enumerate(w.providers)
                  if p["provider_type"] == "facility" and p["specialty"] == "nephrology" and i not in w.reserved_providers)
    dial.sort(key=lambda i: -len(w.members_by_city[w.providers[i]["city"]]))
    w.reserved_providers.add(dial[0])
    CTX["D6"] = {"prov": dial[0]}
    # D7: group practice in Ahmedabad: 5 providers share one owner + clinic, billing stays normal
    cands = w.providers_where("individual", "general_medicine", "Ahmedabad")[:3] + w.providers_where("individual", "pediatrics", "Ahmedabad")[:2]
    owner = _new_owner(w, "Sabarmati Family Physicians LLP")
    clinic = next(i for i, f in enumerate(w.facilities) if f["city"] == "Ahmedabad" and f["facility_type"] == "clinic")
    f = w.facilities[clinic]
    for p in cands:
        w.providers[p].update({"owner": owner, "bank_account_hash": w.owners[owner]["bank_account_hash"],
                               "primary_facility": clinic, "lat": f["lat"], "lon": f["lon"], "pincode": f["pincode"]})
    CTX["D7"] = {"provs": cands, "owner": owner, "fac": clinic}
    # D8: provider that submits corrected claims
    CTX["D8"] = {"prov": w.reserve_provider("individual", "general_medicine", "Delhi")}
    # D9: home health agency in Bengaluru
    CTX["D9"] = {"prov": w.reserve_provider("home_health", None, "Bengaluru")}
    # D10: pharmacy right next to Delhi's largest hospital
    ph = w.reserve_provider("pharmacy", None, "Delhi")
    hfac, _ = _hospital_provider(w, "Delhi")
    hf = w.facilities[hfac]
    w.providers[ph].update({"primary_facility": hfac, "lat": round(hf["lat"] + 0.002, 5), "lon": round(hf["lon"] + 0.002, 5),
                            "pincode": hf["pincode"], "name": "Lifeline Pharmacy, Delhi", "volume": 3.0})
    CTX["D10"] = {"prov": ph, "hfac": hfac}


def plant_all(w: World, book: ClaimBook) -> None:
    plant_d1(w, book)
    plant_d2(w, book)
    plant_d3(w, book)
    plant_d4(w, book)
    plant_d5(w, book)
    plant_d6(w, book)
    plant_d7(w, book)
    plant_d8(w, book)
    plant_d9(w, book)
    plant_d10(w, book)


def plant_d1(w: World, book: ClaimBook) -> None:
    for fac, prov in CTX["D1"]["hosp"]:
        city = w.providers[prov]["city"]
        pool = w.city_members(city)
        for _ in range(150):
            m = w.choice(pool)
            d = pick_day(w, m, provider=prov)
            if d is not None:
                book.add(member=m, provider=prov, day=d, service_type="facility", pos="outpatient",
                         lines=[{"code": w.choice(["FAC-OPD", "FAC-ER", "FAC-DAY"], [0.6, 0.3, 0.1])}])
        w.add_truth(entity_type="provider", entity_index=prov, scheme_id="D1", role="sole_rural_hospital", is_decoy=1,
                    notes=f"Only hospital in {city}; nearest other hospital > 60 km", all_claims_of_provider=True)


def plant_d2(w: World, book: ClaimBook) -> None:
    prov = CTX["D2"]["prov"]
    city = w.providers[prov]["city"]
    pool = [m for m in w.members_by_city[city] if m in w.oncology_pool and m not in w.reserved_members]
    for _ in range(160):
        m = w.choice(pool)
        d = pick_day(w, m, provider=prov)
        if d is None:
            continue
        lines = [{"code": em_code(w, "oncology", [0.02, 0.06, 0.12, 0.20, 0.60])}]
        if w.rng.random() < 0.4:
            lines.append({"code": w.choice(["ONC-120", "ONC-210"], [0.8, 0.2])})
        book.add(member=m, provider=prov, day=d, service_type="professional", pos="office", lines=lines)
    w.add_truth(entity_type="provider", entity_index=prov, scheme_id="D2", role="high_complexity_oncologist", is_decoy=1,
                notes="EM5 ≈ 60% but members' mean risk_score ≈ 2.9 (case-mix)", all_claims_of_provider=True)


def plant_d3(w: World, book: ClaimBook) -> None:
    city, day = "Surat", iso_day("2026-06-14")
    hfac, hosp = _hospital_provider(w, city)
    ambs = (w.providers_where("ambulance", None, city) + w.providers_where("ambulance", None, "Vadodara")
            + w.providers_where("ambulance", None, "Ahmedabad"))[:4]
    docs = (w.providers_where("individual", "emergency", city) + w.providers_where("individual", "emergency", "Vadodara")
            + w.providers_where("individual", "emergency", "Ahmedabad"))[:4]
    rad = w.providers_where("individual", "radiology", city)[:1]
    pool = [m for m in w.city_members(city, 5, 80) if w.ok_day(m, day) and w.admission_free(m, day, day + 6)]
    victims = [pool[int(k)] for k in sorted(w.rng.choice(len(pool), size=30, replace=False))]
    hf = w.facilities[hfac]
    site = geo.offset_point(hf["lat"], hf["lon"], 12.0, 0.8)
    tks: dict[int, list[int]] = {p: [] for p in [hosp, *ambs, *docs, *rad]}
    for j, m in enumerate(victims):
        if j < 12:
            tks[hosp].append(add_inpatient_stay(w, book, m, hfac, hosp, day, day + w.uniform_int(2, 6), tag="D3"))
        tks[hosp].append(book.add(member=m, provider=hosp, day=day, service_type="facility", pos="outpatient",
                                  lines=[{"code": "FAC-ER"}], facility=hfac))
        amb = ambs[j % len(ambs)]
        pickup = geo.offset_point(site[0], site[1], float(w.rng.uniform(0, 0.3)), float(w.rng.uniform(0, 6.28)))
        tks[amb].append(ambulance_trip(w, book, m, amb, day, hfac, pickup=pickup))
        if docs:
            doc = docs[j % len(docs)]
            tks[doc].append(book.add(member=m, provider=doc, day=day, service_type="professional", pos="outpatient",
                                     lines=[{"code": "EM4"}, {"code": "EMR-210"}], facility=hfac))
        if rad and j % 2 == 0:
            tks[rad[0]].append(book.add(member=m, provider=rad[0], day=day, service_type="professional",
                                        pos="outpatient", lines=[{"code": "RAD-210"}], facility=hfac))
    for p, t in tks.items():
        role = "event_hospital" if p == hosp else ("event_ambulance" if p in ambs else "event_clinician")
        w.add_truth(entity_type="provider", entity_index=p, scheme_id="D3", role=role, is_decoy=1,
                    notes="Bus accident in Surat on 2026-06-14: 30 members, several unrelated providers", claim_tks=t)


def plant_d4(w: World, book: ClaimBook) -> None:
    fac, prov = CTX["D4"]["fac"], CTX["D4"]["prov"]
    srcs = sorted(set(w.providers_where("individual", "general_medicine", "Chennai") +
                      w.providers_where("group", "general_medicine", "Chennai") +
                      w.providers_where("individual", "cardiology", "Chennai") +
                      w.providers_where("individual", "nephrology", "Chennai")))
    pool = w.city_members("Chennai", 0, 90)
    for k in range(500):
        src = srcs[k % len(srcs)] if k < len(srcs) else w.choice(srcs)
        m = w.choice(pool)
        rday = pick_day(w, m, provider=src)
        if rday is None:
            continue
        add_referral(w, src, prov, m, rday)
        if w.rng.random() < 0.65:
            cday = pick_day(w, m, rday + 1, rday + 21, provider=prov, tries=4)
            if cday is not None:
                book.add(member=m, provider=prov, day=cday, service_type="facility", pos="outpatient",
                         lines=[{"code": w.choice(["FAC-OPD", "FAC-DAY"], [0.8, 0.2])}], referring=src, facility=fac)
    w.add_truth(entity_type="provider", entity_index=prov, scheme_id="D4", role="teaching_hospital", is_decoy=1,
                notes=f"~500 inbound referrals from {len(srcs)} unrelated sources", all_claims_of_provider=True)


def plant_d5(w: World, book: ClaimBook) -> None:
    city = "Mumbai"
    peds = w.providers_where("group", "pediatrics", city) + w.providers_where("individual", "pediatrics", city)
    clinic = peds[0]
    others = peds[1:4] + w.providers_where("individual", "general_medicine", city)[:2]
    labs = w.providers_where("lab", None, city)[:2]
    kids = w.city_members(city, 0, 17)
    everyone = w.city_members(city)
    spike: list[int] = []
    for months in ((3, 4, 5), (15, 16, 17)):  # Jul–Sep 2025 and Jul–Sep 2026
        for k in months:
            lo, hi = month_start(k), (month_start(k + 1) - 1 if k < 17 else LAST_DAY)
            for prov, n, pool in [(clinic, 35, kids)] + [(o, 10, everyone) for o in others]:
                for _ in range(n):
                    m = w.choice(pool)
                    d = pick_day(w, m, lo, hi, provider=prov)
                    if d is None:
                        continue
                    tk = book.add(member=m, provider=prov, day=d, service_type="professional", pos="office",
                                  lines=[{"code": w.choice(["EM2", "EM3"], [0.5, 0.5])}], dx="DX-095")
                    if prov == clinic:
                        spike.append(tk)
            for lab in labs:
                for _ in range(25):
                    m = w.choice(everyone)
                    d = pick_day(w, m, lo, hi, provider=lab)
                    if d is not None:
                        book.add(member=m, provider=lab, day=d, service_type="lab", pos="lab",
                                 lines=[{"code": "LAB-410"}, {"code": "LAB-300"}], dx="DX-095")
    w.add_truth(entity_type="provider", entity_index=clinic, scheme_id="D5", role="seasonal_burst_clinic", is_decoy=1,
                notes=f"Jul–Sep dengue spike shared by {len(others) + len(labs)} other Mumbai providers", claim_tks=spike)


def plant_d6(w: World, book: ClaimBook) -> None:
    prov = CTX["D6"]["prov"]
    city = w.providers[prov]["city"]
    renal = [m for m in w.members_by_city[city] if m in w.renal_pool and m not in w.reserved_members]
    pool = (renal + w.city_members(city, 40, 85, exclude_pools=True))[:10]
    for m in pool:
        for d in range(iso_day("2025-12-01"), iso_day("2026-05-01")):
            if weekday(d) in (0, 2, 4) and w.ok_day(m, d):
                book.add(member=m, provider=prov, day=d, service_type="facility", pos="outpatient",
                         lines=[{"code": "DIA-001"}], dx="DX-105")
    w.add_truth(entity_type="provider", entity_index=prov, scheme_id="D6", role="dialysis_center", is_decoy=1,
                notes="10 members dialysed Mon/Wed/Fri for 5 months", all_claims_of_provider=True)


def plant_d7(w: World, book: ClaimBook) -> None:
    ctx = CTX["D7"]
    for p in ctx["provs"]:
        w.add_truth(entity_type="provider", entity_index=p, scheme_id="D7", role="group_practice_member", is_decoy=1,
                    notes="Shares owner and clinic with 4 colleagues; billing is normal", all_claims_of_provider=True)
    w.add_truth(entity_type="owner", entity_index=ctx["owner"], scheme_id="D7", role="group_owner", is_decoy=1,
                notes="Legitimate group practice owner")


def plant_d8(w: World, book: ClaimBook) -> None:
    prov = CTX["D8"]["prov"]
    pool = w.city_members("Delhi", 0, 90)
    originals: list[int] = []
    while len(originals) < 45:
        m = w.choice(pool)
        d = pick_day(w, m, 0, LAST_DAY - 40, provider=prov)
        if d is not None:
            originals.append(book.add(member=m, provider=prov, day=d, service_type="professional", pos="office",
                                      lines=professional_lines(w, "general_medicine"), release=None, denied_ok=False))
    picks = [originals[int(k)] for k in w.rng.choice(len(originals), size=18, replace=False)]
    corrections = [add_correction(w, book, tk, void=j >= 15) for j, tk in enumerate(picks)]
    w.add_truth(entity_type="provider", entity_index=prov, scheme_id="D8", role="corrected_claims", is_decoy=1,
                notes="15 replacements (frequency_code 7) + 3 voids (8) of its own claims", claim_tks=corrections)


def plant_d9(w: World, book: ClaimBook) -> None:
    prov = CTX["D9"]["prov"]
    city = "Bengaluru"
    hosps = [h for h in w.hospital_facilities(city) if w.facility_provider(h) is not None]
    pool = w.city_members(city, 55, 90)
    visits: list[int] = []
    made = 0
    guard = 0
    while made < 10 and guard < 3000:
        guard += 1
        m = w.choice(pool)
        h = w.choice(hosps)
        admit = w.uniform_int(200, 470)
        dis = admit + w.uniform_int(3, 7)
        lo, hi = w.member_window(m)
        if not (lo <= admit and dis + 20 <= hi and w.admission_free(m, admit, dis + 20)):
            continue
        hp = w.facility_provider(h)
        if hp is None:
            continue
        add_inpatient_stay(w, book, m, h, hp, admit, dis, tag="D9")
        d = dis + 1
        for _ in range(w.uniform_int(6, 8)):
            if not w.ok_day(m, d):
                break
            visits.append(book.add(member=m, provider=prov, day=d, service_type="home_health", pos="home",
                                   lines=[{"code": w.choice(["HH-010", "HH-020"], [0.6, 0.4])}]))
            d += 2
        made += 1
    w.add_truth(entity_type="provider", entity_index=prov, scheme_id="D9", role="post_discharge_home_health", is_decoy=1,
                notes="Visits start the day after discharge (not during the stay)", claim_tks=visits)


def plant_d10(w: World, book: ClaimBook) -> None:
    prov = CTX["D10"]["prov"]
    pool = w.city_members("Delhi", 0, 90)
    acute = ["DRG-009", "DRG-010", "DRG-011", "DRG-012"]
    chronic = ["DRG-001", "DRG-003", "DRG-004", "DRG-007"]
    n = 0
    while n < 450:
        m = w.choice(pool)
        d = pick_day(w, m, provider=prov)
        if d is None:
            continue
        drugs = sorted({w.choice(acute if w.rng.random() < 0.7 else chronic) for _ in range(w.uniform_int(1, 2))})
        book.add(member=m, provider=prov, day=d, service_type="pharmacy", pos="pharmacy",
                 lines=[pharmacy_line(w, dg) for dg in drugs])
        n += 1
    hf = w.facilities[CTX["D10"]["hfac"]]
    km = haversine(w.providers[prov]["lat"], w.providers[prov]["lon"], hf["lat"], hf["lon"])
    w.add_truth(entity_type="provider", entity_index=prov, scheme_id="D10", role="pharmacy_near_hospital", is_decoy=1,
                notes=f"{km:.1f} km from {hf['name']} ({hf['bed_count']} beds)", all_claims_of_provider=True)


__all__ = ["DECOY_INFO", "lab_lines", "plant_all", "reserve_all"]
