"""One tiny hand-made dataset per rule: a hit and a non-hit (incl. decoys D8 and D9)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

import pandas as pd
import pytest

from engine.config import CONFIG, REPO_DIR
from engine.detect import rules as R
from engine.features import build_provider_features
from engine.generate.__main__ import CLAIM_COLUMNS
from engine.store import DataStore

COLS = {
    "members": ["member_id", "age", "gender", "city", "state", "pincode", "lat", "lon", "plan_id", "coverage_start",
                "coverage_end", "date_of_death", "risk_score", "chronic_conditions", "card_id", "phone_hash", "address_hash"],
    "providers": ["provider_id", "name", "provider_type", "specialty", "primary_facility_id", "owner_id", "bank_account_hash",
                  "city", "state", "pincode", "lat", "lon", "is_rural", "enrolled_date"],
    "facilities": ["facility_id", "name", "facility_type", "city", "state", "pincode", "lat", "lon", "is_rural", "owner_id",
                   "bed_count", "catchment_population"],
    "owners": ["owner_id", "owner_name", "bank_account_hash", "address_hash"],
    "admissions": ["admission_id", "member_id", "facility_id", "admit_date", "discharge_date"],
    "referrals": ["referral_id", "from_provider_id", "to_provider_id", "member_id", "referral_date", "reason_code"],
    "investigations": ["investigation_id", "provider_id", "opened_date", "closed_date", "outcome", "fraud_type", "recovered_amount"],
}
D0 = date(2026, 3, 2)


def day(k: int) -> str:
    return (D0 + timedelta(days=k)).isoformat()


class Mini:
    def __init__(self, tmp):
        self.tmp = tmp
        self.rows = defaultdict(list)
        self.n = 0
        self.facility("FAC-1", 18.52, 73.85)
        self.owner("OWN-1")

    def owner(self, oid):
        self.rows["owners"].append({"owner_id": oid, "owner_name": oid, "bank_account_hash": f"b{oid}", "address_hash": f"a{oid}"})

    def facility(self, fid, lat, lon, ftype="clinic"):
        self.rows["facilities"].append({"facility_id": fid, "name": fid, "facility_type": ftype, "city": "Pune", "state": "MH",
                                        "pincode": "411001", "lat": lat, "lon": lon, "is_rural": 0, "owner_id": "OWN-1",
                                        "bed_count": 0, "catchment_population": 100000})

    def provider(self, pid, specialty="general_medicine", ptype="individual", fac="FAC-1"):
        self.rows["providers"].append({"provider_id": pid, "name": pid, "provider_type": ptype, "specialty": specialty,
                                       "primary_facility_id": fac, "owner_id": "OWN-1", "bank_account_hash": "b",
                                       "city": "Pune", "state": "MH", "pincode": "411001", "lat": 18.52, "lon": 73.85,
                                       "is_rural": 0, "enrolled_date": "2020-01-01"})

    def member(self, mid, dod="", cov_start="2020-01-01", phone=None, addr=None):
        self.rows["members"].append({"member_id": mid, "age": 40, "gender": "F", "city": "Pune", "state": "MH",
                                     "pincode": "411001", "lat": 18.5, "lon": 73.8, "plan_id": "PLN-01",
                                     "coverage_start": cov_start, "coverage_end": "2027-03-31", "date_of_death": dod,
                                     "risk_score": 1.0, "chronic_conditions": 0, "card_id": "HC1",
                                     "phone_hash": phone or f"p{mid}", "address_hash": addr or f"a{mid}"})

    def claim(self, member, provider, code, d, *, cid=None, line=1, units=1, billed=1000, freq=1, original="",
              pos="office", stype="professional", minutes=None, fac="FAC-1", **extra):
        if cid is None:
            self.n += 1
            cid = f"CLM-{self.n:07d}"
        row = {k: "" for k in CLAIM_COLUMNS}
        row.update({"claim_id": cid, "line_no": line, "member_id": member, "provider_id": provider,
                    "billing_provider_id": provider, "facility_id": fac, "service_type": stype, "procedure_code": code,
                    "diagnosis_code": "DX-001", "units": units, "duration_minutes": 15 if minutes is None else minutes,
                    "billed_amount": billed, "allowed_amount": billed, "paid_amount": billed, "service_date": d,
                    "submitted_date": d, "payment_release_date": "2026-09-01", "payment_status": "paid",
                    "frequency_code": freq, "original_claim_id": original, "place_of_service": pos})
        row.update(extra)
        self.rows["claims"].append(row)
        return cid

    def admission(self, member, fac, admit, discharge):
        self.rows["admissions"].append({"admission_id": f"ADM-{len(self.rows['admissions']) + 1}", "member_id": member,
                                        "facility_id": fac, "admit_date": admit, "discharge_date": discharge})

    def referral(self, src, dst, member, d):
        self.rows["referrals"].append({"referral_id": f"REF-{len(self.rows['referrals']) + 1}", "from_provider_id": src,
                                       "to_provider_id": dst, "member_id": member, "referral_date": d, "reason_code": "RSN-01"})

    def run(self, rule):
        raw = self.tmp / "raw"
        raw.mkdir(parents=True, exist_ok=True)
        for name, cols in {**COLS, "claims": CLAIM_COLUMNS}.items():
            pd.DataFrame(self.rows[name], columns=cols).to_csv(raw / f"{name}.csv", index=False)
        store = DataStore(raw, REPO_DIR / "data" / "reference")
        feats = build_provider_features(store, CONFIG)
        return rule(store, CONFIG, feats)


@pytest.fixture
def mini(tmp_path):
    m = Mini(tmp_path)
    m.provider("PRV-1")
    m.member("MEM-1")
    return m


def test_r01_hit_and_d8_corrections_not_hit(tmp_path):
    hit = Mini(tmp_path / "a")
    hit.provider("PRV-1")
    hit.member("MEM-1")
    for _ in range(3):
        hit.claim("MEM-1", "PRV-1", "EM3", day(0))
    s = hit.run(R.r01_exact_duplicate)
    assert len(s) == 1 and s[0]["value"] == 2
    d8 = Mini(tmp_path / "b")
    d8.provider("PRV-1")
    d8.member("MEM-1")
    orig = d8.claim("MEM-1", "PRV-1", "EM3", day(0))
    d8.claim("MEM-1", "PRV-1", "EM3", day(0), freq=7, original=orig)
    o2 = d8.claim("MEM-1", "PRV-1", "EM4", day(3))
    d8.claim("MEM-1", "PRV-1", "EM4", day(3), freq=8, original=o2)
    assert d8.run(R.r01_exact_duplicate) == []


def test_r02_near_duplicate(mini):
    for k in range(3):
        mini.claim("MEM-1", "PRV-1", "EM3", day(10 * k), billed=1000)
        mini.claim("MEM-1", "PRV-1", "EM3", day(10 * k + 1), billed=1020)
    mini.claim("MEM-1", "PRV-1", "EM4", day(50), billed=1000)
    mini.claim("MEM-1", "PRV-1", "EM4", day(51), billed=1500)  # 50% apart: not near
    s = mini.run(R.r02_near_duplicate)
    assert len(s) == 1 and s[0]["value"] == 3


def _em_peers(m, n_peers=6, lines=20, em5=2):
    for p in range(n_peers):
        pid = f"PRV-P{p}"
        m.provider(pid)
        for k in range(lines):
            m.claim("MEM-1", pid, "EM5" if k < em5 else "EM3", day(-150 + k * 5))


def test_r03_upcoding_hit_and_non_hit(tmp_path):
    hit = Mini(tmp_path / "a")
    hit.member("MEM-1")
    _em_peers(hit)
    hit.provider("PRV-X")
    for k in range(30):
        hit.claim("MEM-1", "PRV-X", "EM5" if k < 18 else "EM3", day(-150 + k * 5))
    s = hit.run(R.r03_upcoding)
    assert [x["entity_id"] for x in s] == ["PRV-X"] and s[0]["value"] == 0.6
    miss = Mini(tmp_path / "b")
    miss.member("MEM-1")
    _em_peers(miss)
    miss.provider("PRV-X")
    for k in range(30):
        miss.claim("MEM-1", "PRV-X", "EM5" if k < 3 else "EM3", day(-150 + k * 5))
    assert miss.run(R.r03_upcoding) == []


def test_r04_unbundling(tmp_path):
    hit = Mini(tmp_path / "a")
    hit.provider("PRV-L", "pathology", "lab")
    hit.member("MEM-1")
    for k in range(3):
        cid = hit.claim("MEM-1", "PRV-L", "LAB-101", day(k), stype="lab", pos="lab")
        hit.claim("MEM-1", "PRV-L", "LAB-102", day(k), cid=cid, line=2, stype="lab", pos="lab")
    assert len(hit.run(R.r04_unbundling)) == 1
    miss = Mini(tmp_path / "b")
    miss.provider("PRV-L", "pathology", "lab")
    miss.member("MEM-1")
    for k in range(3):
        miss.claim("MEM-1", "PRV-L", "LAB-100", day(k), stype="lab", pos="lab")
    assert miss.run(R.r04_unbundling) == []


def test_r05_after_death(mini):
    mini.member("MEM-2", dod=day(5))
    mini.claim("MEM-2", "PRV-1", "EM3", day(2))
    assert mini.run(R.r05_after_death) == []
    mini.claim("MEM-2", "PRV-1", "EM3", day(9))
    s = mini.run(R.r05_after_death)
    assert {x["entity_type"] for x in s} == {"member", "provider"} and all(x["hard"] for x in s)


def test_r06_inpatient_hit_and_d9_not_hit(tmp_path):
    hit = Mini(tmp_path / "a")
    hit.facility("FAC-H", 18.6, 73.9, "hospital")
    hit.provider("PRV-HH", "none", "home_health")
    hit.member("MEM-1")
    hit.admission("MEM-1", "FAC-H", day(10), day(15))
    hit.claim("MEM-1", "PRV-HH", "HH-010", day(12), pos="home", stype="home_health")
    assert len(hit.run(R.r06_during_inpatient)) == 1
    d9 = Mini(tmp_path / "b")
    d9.facility("FAC-H", 18.6, 73.9, "hospital")
    d9.provider("PRV-HH", "none", "home_health")
    d9.member("MEM-1")
    d9.admission("MEM-1", "FAC-H", day(10), day(15))
    for k in (10, 15, 16, 18):  # admit day, discharge day, after discharge
        d9.claim("MEM-1", "PRV-HH", "HH-010", day(k), pos="home", stype="home_health")
    assert d9.run(R.r06_during_inpatient) == []


def test_r07_outside_coverage(mini):
    mini.member("MEM-2", cov_start=day(5))
    mini.claim("MEM-2", "PRV-1", "EM3", day(6))
    assert mini.run(R.r07_outside_coverage) == []
    mini.claim("MEM-2", "PRV-1", "EM3", day(1))
    assert len(mini.run(R.r07_outside_coverage)) == 1


def test_r08_impossible_hours(tmp_path):
    hit = Mini(tmp_path / "a")
    hit.provider("PRV-T", "psychiatry", "behavioral")
    hit.member("MEM-1")
    for _ in range(26):
        hit.claim("MEM-1", "PRV-T", "BH-060", day(0), minutes=60, stype="behavioral_health")
    s = hit.run(R.r08_impossible_hours)
    assert len(s) == 1 and s[0]["hard"] and s[0]["value"] == 26.0
    miss = Mini(tmp_path / "b")
    miss.provider("PRV-T", "psychiatry", "behavioral")
    miss.member("MEM-1")
    for _ in range(10):
        miss.claim("MEM-1", "PRV-T", "BH-060", day(0), minutes=60, stype="behavioral_health")
    assert miss.run(R.r08_impossible_hours) == []


def test_r09_impossible_travel(tmp_path):
    for far, expect in ((True, 1), (False, 0)):
        m = Mini(tmp_path / str(far))
        m.facility("FAC-2", 21.15 if far else 18.9, 79.09 if far else 73.85)
        m.provider("PRV-1")
        m.provider("PRV-2", fac="FAC-2")
        m.member("MEM-1")
        m.claim("MEM-1", "PRV-1", "EM3", day(0))
        m.claim("MEM-1", "PRV-2", "EM3", day(0), fac="FAC-2")
        assert len(m.run(R.r09_impossible_travel)) == expect


def test_r10_ambulance_miles(tmp_path):
    for ratio, expect in ((3.0, 1), (1.2, 0)):
        m = Mini(tmp_path / str(ratio))
        m.provider("PRV-A", "emergency", "ambulance")
        m.member("MEM-1")
        km = 30.0
        miles = round(km / 1.609344 * ratio, 1)
        for k in range(2):  # pickup ~30 km north of drop-off
            m.claim("MEM-1", "PRV-A", "AMB-BLS", day(k), stype="ambulance", pos="ambulance", ambulance_miles=miles,
                    pickup_lat=18.52 + km / 110.574, pickup_lon=73.85, dropoff_lat=18.52, dropoff_lon=73.85)
        s = m.run(R.r10_ambulance_miles)
        assert len(s) == expect
        if expect:
            assert s[0]["hard"]


def test_r11_excessive_frequency(tmp_path):
    for visits, expect in ((6, 1), (3, 0)):
        m = Mini(tmp_path / str(visits))
        m.provider("PRV-1")
        for i in range(60):  # 60 ordinary member-provider pairs with 1 visit
            m.member(f"MEM-{i}")
            m.claim(f"MEM-{i}", "PRV-1", "EM3", day(i % 20))
        m.provider("PRV-2")
        for k in range(visits):
            m.claim("MEM-0", "PRV-2", "EM3", day(k * 4))
        assert len(m.run(R.r11_excessive_frequency)) == expect


def test_r12_threshold_hugging(tmp_path):
    for in_band, expect in ((10, 1), (3, 0)):
        m = Mini(tmp_path / str(in_band))
        m.member("MEM-1")
        for p in range(6):
            m.provider(f"PRV-P{p}", "orthopedics")
            for k in range(12):
                m.claim("MEM-1", f"PRV-P{p}", "ORT-305", day(k), billed=3500)
        m.provider("PRV-X", "orthopedics")
        for k in range(12):
            m.claim("MEM-1", "PRV-X", "ORT-214", day(k), billed=45_000 if k < in_band else 20_000)
        s = m.run(R.r12_threshold_hugging)
        assert len(s) == expect
        if expect:
            assert s[0]["entity_id"] == "PRV-X" and s[0]["value"] == round(10 / 12, 3)


def test_r13_dme_overrun(tmp_path):
    for month, expect in ((14, 1), (12, 0)):
        m = Mini(tmp_path / str(month))
        m.provider("PRV-D", "none", "dme")
        m.member("MEM-1")
        m.claim("MEM-1", "PRV-D", "DME-RENT", day(0), stype="dme", pos="home", dme_item_code="DMEI-01", rental_month=month)
        assert len(m.run(R.r13_dme_overrun)) == expect


def test_r14_early_refill(tmp_path):
    for gap, expect in ((10, 1), (30, 0)):
        m = Mini(tmp_path / str(gap))
        m.provider("PRV-P", "none", "pharmacy")
        m.member("MEM-1")
        for k in range(4):
            m.claim("MEM-1", "PRV-P", "RX-FILL", day(k * gap), stype="pharmacy", pos="pharmacy",
                    drug_code="DRG-001", days_supply=30)
        assert len(m.run(R.r14_early_refill)) == expect


def test_r15_referral_concentration(tmp_path):
    hit = Mini(tmp_path / "a")
    hit.member("MEM-1")
    for p in ("PRV-A", "PRV-B"):
        hit.provider(p)
    for k in range(6):
        hit.referral("PRV-A", "PRV-B", "MEM-1", day(k))
    s = hit.run(R.r15_referral_concentration)
    assert len(s) == 1 and s[0]["entity_id"] == "PRV-B" and "PRV-A" in s[0]["entity_ids"]
    miss = Mini(tmp_path / "b")
    miss.member("MEM-1")
    miss.provider("PRV-B")
    for k in range(6):
        miss.provider(f"PRV-S{k}")
        miss.referral(f"PRV-S{k}", "PRV-B", "MEM-1", day(k))
    assert miss.run(R.r15_referral_concentration) == []


def test_r16_identity_sharing(tmp_path):
    for n, expect, hard in ((10, 1, True), (4, 0, False)):
        m = Mini(tmp_path / str(n))
        m.provider("PRV-1")
        for i in range(n):
            m.member(f"MEM-{i}", phone="SHARED")
        s = m.run(R.r16_identity_sharing)
        assert len(s) == expect
        if expect:
            assert s[0]["hard"] is hard and s[0]["value"] == n
