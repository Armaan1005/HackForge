"""python -m engine.generate --seed 42 [--claims 50000] [--out ../data/raw]

Writes data/raw/*.csv, ground_truth.csv and planted_cases.json (both eval-only), and the
reference tables in data/reference/. Same seed => byte-identical files.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from ..config import CONFIG, REPO_DIR
from . import decoys, schemes
from .claims import ClaimBook, generate_baseline
from .entities import World, day_iso, make_world
from .reference import write_reference

PLANTED_LINES_ESTIMATE = 6100  # lines added by schemes + decoys (keeps service shares on target)

CLAIM_COLUMNS = [
    "claim_id", "line_no", "member_id", "provider_id", "billing_provider_id", "facility_id",
    "referring_provider_id", "service_type", "procedure_code", "diagnosis_code", "units", "duration_minutes",
    "billed_amount", "allowed_amount", "paid_amount", "service_date", "submitted_date", "payment_release_date",
    "payment_status", "frequency_code", "original_claim_id", "place_of_service", "ambulance_miles",
    "pickup_lat", "pickup_lon", "dropoff_lat", "dropoff_lon", "days_supply", "drug_code", "dme_item_code",
    "rental_month",
]


def build_investigations(w: World) -> None:
    planted = {g.entity_index for g in w.ground_truth if g.entity_type == "provider" and not g.is_decoy}
    cands = [i for i in range(len(w.providers)) if i not in planted]
    picks = sorted(int(k) for k in w.rng.choice(len(cands), size=120, replace=False))
    types = ["upcoding", "duplicate_billing", "phantom_services", "kickbacks", "identity_theft", "unbundling"]
    for k in picks:
        opened = w.uniform_int(-1000, 500)
        closed = opened + w.uniform_int(30, 300)
        if closed > 547:
            outcome, closed_s = "ongoing", ""
        else:
            outcome = w.choice(["confirmed", "cleared", "insufficient_evidence"], [0.25, 0.45, 0.30])
            closed_s = day_iso(closed)
        w.investigations.append({
            "provider_id": w.provider_id(cands[k]), "opened_date": day_iso(opened), "closed_date": closed_s,
            "outcome": outcome, "fraud_type": w.choice(types),
            "recovered_amount": w.uniform_int(20, 800) * 1000 if outcome == "confirmed" else 0,
        })


def finalize(w: World, book: ClaimBook) -> dict[str, pd.DataFrame]:
    out: dict[str, pd.DataFrame] = {}
    out["owners"] = pd.DataFrame([
        {"owner_id": w.owner_id(i), "owner_name": o["owner_name"], "bank_account_hash": o["bank_account_hash"],
         "address_hash": o["address_hash"]} for i, o in enumerate(w.owners)])
    out["facilities"] = pd.DataFrame([
        {"facility_id": w.facility_id(i), "name": f["name"], "facility_type": f["facility_type"], "city": f["city"],
         "state": f["state"], "pincode": f["pincode"], "lat": f["lat"], "lon": f["lon"], "is_rural": f["is_rural"],
         "owner_id": w.owner_id(f["owner"]), "bed_count": f["bed_count"],
         "catchment_population": f["catchment_population"]} for i, f in enumerate(w.facilities)])
    out["providers"] = pd.DataFrame([
        {"provider_id": w.provider_id(i), "name": p["name"], "provider_type": p["provider_type"],
         "specialty": p["specialty"], "primary_facility_id": w.facility_id(p["primary_facility"]),
         "owner_id": w.owner_id(p["owner"]), "bank_account_hash": p["bank_account_hash"], "city": p["city"],
         "state": p["state"], "pincode": p["pincode"], "lat": p["lat"], "lon": p["lon"], "is_rural": p["is_rural"],
         "enrolled_date": day_iso(p["enrolled"])} for i, p in enumerate(w.providers)])
    out["members"] = pd.DataFrame([
        {"member_id": w.member_id(i), "age": m["age"], "gender": m["gender"], "city": m["city"], "state": m["state"],
         "pincode": m["pincode"], "lat": m["lat"], "lon": m["lon"], "plan_id": m["plan_id"],
         "coverage_start": day_iso(m["cov_start"]), "coverage_end": day_iso(m["cov_end"]),
         "date_of_death": day_iso(m["death"]) if m["death"] < 10_000 else "",
         "risk_score": m["risk"], "chronic_conditions": m["chronic"], "card_id": m["card_id"],
         "phone_hash": m["phone_hash"], "address_hash": m["address_hash"]} for i, m in enumerate(w.members)])

    adm = sorted(w.admissions, key=lambda a: (a["admit"], a["member"], a["facility"], a["discharge"]))
    out["admissions"] = pd.DataFrame([
        {"admission_id": f"ADM-{k + 1:06d}", "member_id": w.member_id(a["member"]),
         "facility_id": w.facility_id(a["facility"]), "admit_date": day_iso(a["admit"]),
         "discharge_date": day_iso(a["discharge"])} for k, a in enumerate(adm)])
    refs = sorted(w.referrals, key=lambda r: (r["day"], r["from"], r["to"], r["member"], r["reason_code"]))
    out["referrals"] = pd.DataFrame([
        {"referral_id": f"REF-{k + 1:06d}", "from_provider_id": w.provider_id(r["from"]),
         "to_provider_id": w.provider_id(r["to"]), "member_id": w.member_id(r["member"]),
         "referral_date": day_iso(r["day"]), "reason_code": r["reason_code"]} for k, r in enumerate(refs)])

    live = [h for h in book.headers if not h.get("dropped")]
    live.sort(key=lambda h: (h["day"], h["provider"], h["member"], h["tk"]))
    cid = {h["tk"]: f"CLM-{k + 1:07d}" for k, h in enumerate(live)}
    rows = []
    for h in live:
        for ln in book.lines[h["tk"]]:
            rows.append({
                "claim_id": cid[h["tk"]], "line_no": ln["line_no"], "member_id": w.member_id(h["member"]),
                "provider_id": w.provider_id(h["provider"]), "billing_provider_id": w.provider_id(h["billing"]),
                "facility_id": w.facility_id(h["facility"]),
                "referring_provider_id": w.provider_id(h["referring"]) if h["referring"] is not None else "",
                "service_type": h["service_type"], "procedure_code": ln["procedure_code"], "diagnosis_code": h["dx"],
                "units": ln["units"], "duration_minutes": ln["duration_minutes"], "billed_amount": ln["billed_amount"],
                "allowed_amount": ln["allowed_amount"], "paid_amount": ln["paid_amount"],
                "service_date": day_iso(h["day"]), "submitted_date": day_iso(h["submitted"]),
                "payment_release_date": day_iso(h["release"]), "payment_status": h["status"],
                "frequency_code": h["freq"], "original_claim_id": cid.get(h["original"], "") if h["original"] is not None else "",
                "place_of_service": h["pos"], "ambulance_miles": ln["ambulance_miles"], "pickup_lat": ln["pickup_lat"],
                "pickup_lon": ln["pickup_lon"], "dropoff_lat": ln["dropoff_lat"], "dropoff_lon": ln["dropoff_lon"],
                "days_supply": ln["days_supply"], "drug_code": ln["drug_code"] or "",
                "dme_item_code": ln["dme_item_code"] or "", "rental_month": ln["rental_month"],
            })
    claims = pd.DataFrame(rows, columns=CLAIM_COLUMNS)
    for col in ("days_supply", "rental_month"):
        claims[col] = claims[col].astype("Int64")
    out["claims"] = claims

    out["investigations"] = pd.DataFrame(
        [{"investigation_id": f"INV-{k + 1:04d}", **inv} for k, inv in enumerate(w.investigations)])

    gt_rows = []
    for g in w.ground_truth:
        if g.all_claims_of_provider:
            tks = [tk for tk in book.by_provider[g.entity_index] if tk in cid]
        else:
            tks = [tk for tk in g.claim_tks if tk in cid]
        ids = sorted({cid[tk] for tk in tks})
        ent_id = g.entity_id or {
            "provider": w.provider_id, "member": w.member_id, "owner": w.owner_id, "facility": w.facility_id,
        }[g.entity_type](g.entity_index)
        gt_rows.append({"entity_type": g.entity_type, "entity_id": ent_id, "scheme_id": g.scheme_id, "role": g.role,
                        "claim_ids": "|".join(ids), "is_decoy": g.is_decoy, "notes": g.notes})
    gt = pd.DataFrame(gt_rows)
    gt["_k"] = gt["scheme_id"].str[0].map({"S": 0, "D": 1}) * 100 + gt["scheme_id"].str[1:].astype(int)
    out["ground_truth"] = gt.sort_values(["_k", "entity_type", "entity_id"]).drop(columns="_k").reset_index(drop=True)
    return out


def planted_summary(tables: dict[str, pd.DataFrame]) -> list[dict]:
    gt = tables["ground_truth"]
    claims = tables["claims"]
    billed = claims.groupby("claim_id")["billed_amount"].sum()
    info = {**schemes.SCHEME_INFO, **decoys.DECOY_INFO}
    out = []
    for sid, grp in gt.groupby("scheme_id", sort=False):
        ids = sorted({c for s in grp["claim_ids"] for c in s.split("|") if c})
        name, desc = info[sid]
        out.append({
            "scheme_id": sid, "name": name, "is_decoy": bool(grp["is_decoy"].iloc[0]), "description": desc,
            "entities": [{"entity_type": r.entity_type, "entity_id": r.entity_id, "role": r.role} for r in grp.itertuples()],
            "claim_count": len(ids), "billed_total_inr": int(billed.reindex(ids).sum()),
        })
    return out


def run(seed: int, n_claims: int, out_dir: Path, ref_dir: Path | None = None) -> dict:
    t0 = time.perf_counter()
    write_reference(ref_dir or REPO_DIR / "data" / "reference")
    w = make_world(CONFIG, seed)
    schemes.reserve_all(w)
    decoys.reserve_all(w)
    book = ClaimBook(w)
    w.book = book
    scale = n_claims / 50_000
    generate_baseline(w, book, int(n_claims - PLANTED_LINES_ESTIMATE * scale))
    schemes.plant_all(w, book)
    decoys.plant_all(w, book)
    build_investigations(w)
    tables = finalize(w, book)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(out_dir / f"{name}.csv", index=False, lineterminator="\n")
    (out_dir / "planted_cases.json").write_text(
        json.dumps(planted_summary(tables), indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return {"seconds": round(time.perf_counter() - t0, 2),
            "rows": {k: len(v) for k, v in tables.items()},
            "service_lines": tables["claims"]["service_type"].value_counts().to_dict()}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m engine.generate")
    ap.add_argument("--seed", type=int, default=CONFIG.seed)
    ap.add_argument("--claims", type=int, default=50_000)
    ap.add_argument("--out", type=Path, default=CONFIG.raw_dir)
    args = ap.parse_args(argv)
    meta = run(args.seed, args.claims, args.out)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
