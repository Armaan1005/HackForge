"""M1 acceptance tests for the synthetic data generator (spec A1)."""

import hashlib

import numpy as np
import pandas as pd
import pytest

from engine.config import REPO_DIR
from engine.generate.__main__ import run

def digest(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


def test_runtime_under_budget(gen):
    assert gen[1]["seconds"] < 60


def test_deterministic(gen, tmp_path):
    out, _, _ = gen
    run(42, 50_000, tmp_path / "raw2", ref_dir=tmp_path / "ref2")
    assert digest(out) == digest(tmp_path / "raw2")


def test_reference_tables_committed_match(tmp_path):
    from engine.generate.reference import write_reference

    write_reference(tmp_path)
    committed = REPO_DIR / "data" / "reference"
    for p in sorted(tmp_path.glob("*.csv")):  # compare text: git may check files out with CRLF
        assert p.read_bytes().replace(b"\r\n", b"\n") == (committed / p.name).read_bytes().replace(b"\r\n", b"\n"), p.name


def test_scale(gen):
    _, meta, t = gen
    rows = meta["rows"]
    assert rows["providers"] == 1500 and rows["members"] == 20_000 and rows["facilities"] == 300
    assert 48_000 <= rows["claims"] <= 52_000
    assert 8_000 <= rows["referrals"] <= 10_000 and 2_300 <= rows["admissions"] <= 2_700
    assert rows["investigations"] == 120


def test_service_type_shares(gen):
    share = gen[2]["claims"]["service_type"].value_counts(normalize=True)
    target = {"professional": 0.38, "facility": 0.12, "pharmacy": 0.18, "lab": 0.14, "ambulance": 0.03,
              "behavioral_health": 0.05, "home_health": 0.05, "dme": 0.05}
    assert set(share.index) == set(target)
    for k, v in target.items():
        assert abs(share[k] - v) <= 0.03, (k, share[k])


def test_referential_integrity(gen):
    t = gen[2]
    ids = {name: set(t[name][col]) for name, col in [("owners", "owner_id"), ("facilities", "facility_id"),
                                                      ("providers", "provider_id"), ("members", "member_id")]}
    c = t["claims"]
    assert set(t["facilities"]["owner_id"]) <= ids["owners"]
    assert set(t["providers"]["owner_id"]) <= ids["owners"]
    assert set(t["providers"]["primary_facility_id"]) <= ids["facilities"]
    assert set(c["member_id"]) <= ids["members"]
    assert set(c["provider_id"]) | set(c["billing_provider_id"]) <= ids["providers"]
    assert set(c["facility_id"]) <= ids["facilities"]
    assert set(c.loc[c.referring_provider_id != "", "referring_provider_id"]) <= ids["providers"]
    assert set(c.loc[c.original_claim_id != "", "original_claim_id"]) <= set(c["claim_id"])
    assert set(t["admissions"]["member_id"]) <= ids["members"]
    assert set(t["admissions"]["facility_id"]) <= ids["facilities"]
    r = t["referrals"]
    assert set(r["from_provider_id"]) | set(r["to_provider_id"]) <= ids["providers"]
    assert set(r["member_id"]) <= ids["members"]
    assert set(t["investigations"]["provider_id"]) <= ids["providers"]
    gt = t["ground_truth"]
    for etype, key in [("provider", "providers"), ("member", "members"), ("owner", "owners"), ("facility", "facilities")]:
        assert set(gt.loc[gt.entity_type == etype, "entity_id"]) <= ids[key]
    gt_claims = {x for s in gt["claim_ids"] for x in s.split("|") if x}
    assert gt_claims <= set(c["claim_id"])


def test_dates_are_consistent(gen):
    c = gen[2]["claims"]
    assert c["service_date"].min() >= "2025-04-01" and c["service_date"].max() <= "2026-09-30"
    assert (c["submitted_date"] >= c["service_date"]).all()
    assert (c["submitted_date"] <= "2026-09-30").all()
    assert (c["payment_release_date"] > c["submitted_date"]).all()
    assert set(c["frequency_code"]) == {"1", "7", "8"}
    pending = c.loc[c.payment_status == "pending"]
    assert (pending["paid_amount"] == "0").all() and (pending["payment_release_date"] >= "2026-10-01").all()


def test_every_scheme_and_decoy_in_ground_truth(gen):
    gt = gen[2]["ground_truth"]
    expected = {f"S{i}" for i in range(1, 9)} | {f"D{i}" for i in range(1, 11)}
    assert set(gt["scheme_id"]) == expected
    for sid, grp in gt.groupby("scheme_id"):
        assert any(grp["claim_ids"] != ""), f"{sid} has no claim ids"
    assert set(gt.loc[gt.scheme_id.str.startswith("D"), "is_decoy"]) == {"1"}
    assert set(gt.loc[gt.scheme_id.str.startswith("S"), "is_decoy"]) == {"0"}


def _claims_of(t, scheme, etype="provider"):
    gt = t["ground_truth"]
    rows = gt[(gt.scheme_id == scheme) & (gt.entity_type == etype)]
    return {x for s in rows["claim_ids"] for x in s.split("|") if x}, set(rows["entity_id"])


def test_pending_share_and_s6_money_clock(gen):
    t = gen[2]
    c = t["claims"]
    hdr = c.groupby("claim_id").agg(rel=("payment_release_date", "first"), billed=("billed_amount", lambda s: s.astype(int).sum()))
    share = (hdr["rel"] > "2026-10-01").mean()
    assert 0.03 <= share <= 0.08
    s6, provs = _claims_of(t, "S6")
    h = hdr.loc[sorted(s6)]
    assert len(provs) == 3 and 44 <= len(s6) <= 52
    assert h["billed"].between(31_000, 49_800).all()
    assert ((h["billed"] >= 40_000) & (h["billed"] < 50_000)).mean() >= 0.8
    pending = h[h["rel"] > "2026-10-01"]
    assert len(pending) == 12 and (pending["rel"] <= "2026-10-04").all()
    p = t["providers"].set_index("provider_id").loc[sorted(provs)]
    assert p["owner_id"].nunique() == 1 and p["primary_facility_id"].nunique() == 1


def _haversine_miles(df):
    lat1, lon1, lat2, lon2 = (np.radians(df[c].astype(float)) for c in ("pickup_lat", "pickup_lon", "dropoff_lat", "dropoff_lon"))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a)) / 1.609344


def test_raw_signals_fire_only_on_planted_entities(gen):
    """Sanity check of the data (not the rules engine): each hard pattern exists only where planted."""
    t = gen[2]
    c = t["claims"].copy()
    c["duration_minutes"] = c["duration_minutes"].astype(int)
    # R08 impossible hours -> only the S8 therapist
    minutes = c.groupby(["provider_id", "service_date"])["duration_minutes"].sum()
    _, s8 = _claims_of(t, "S8")
    assert set(minutes[minutes > 24 * 60].index.get_level_values(0)) == s8
    assert (minutes[minutes > 24 * 60] >= 26 * 60).all()
    # R05 service after death -> only S5 members
    mem = t["members"]
    cd = c.merge(mem[["member_id", "date_of_death"]], on="member_id")
    after = cd[(cd.date_of_death != "") & (cd.service_date > cd.date_of_death)]
    _, s5_members = _claims_of(t, "S5", "member")
    assert len(after) > 0 and set(after["member_id"]) <= s5_members
    # R16 identity sharing (>= 5 members) -> only the S5 cluster
    shared = set()
    for col in ("phone_hash", "address_hash"):
        vc = mem[col].value_counts()
        shared |= set(mem[mem[col].isin(vc[vc >= 5].index)]["member_id"])
    assert shared == s5_members
    # R10 ambulance miles > 1.5x map + 5 -> only the S2 provider
    a = c[c.service_type == "ambulance"]
    flagged = a[a["ambulance_miles"].astype(float) > 1.5 * _haversine_miles(a) + 5]
    _, s2 = _claims_of(t, "S2")
    assert set(flagged["provider_id"]) == s2 and len(flagged) >= 40
    # R01 exact duplicate (excluding frequency 7/8) -> only the S4 provider
    orig = c[~c.frequency_code.isin(["7", "8"])]
    dup = orig.groupby(["member_id", "provider_id", "procedure_code", "drug_code", "service_date", "units"])["claim_id"].nunique()
    _, s4 = _claims_of(t, "S4")
    assert set(dup[dup > 1].index.get_level_values(1)) == s4


def test_decoy_d8_corrections_and_d9_after_discharge(gen):
    t = gen[2]
    c = t["claims"]
    d8, _ = _claims_of(t, "D8")
    rows = c[c.claim_id.isin(d8)].drop_duplicates("claim_id")
    assert set(rows["frequency_code"]) <= {"7", "8"} and (rows["original_claim_id"] != "").all()
    orig = c.drop_duplicates("claim_id").set_index("claim_id").loc[rows["original_claim_id"]]
    assert (orig["member_id"].values == rows["member_id"].values).all()
    assert (orig["service_date"].values == rows["service_date"].values).all()
    d9, _ = _claims_of(t, "D9")
    visits = c[c.claim_id.isin(d9)]
    adm = t["admissions"]
    v = visits.merge(adm, on="member_id")
    inside = v[(v.service_date >= v.admit_date) & (v.service_date <= v.discharge_date)]
    assert len(visits) >= 40 and inside.empty
