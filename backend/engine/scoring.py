"""Case scoring, verdict status and money clock (spec A11). Deterministic; every status
comes with plain-English reasons. The verdict is a recommendation for a human."""

from __future__ import annotations

import math

import pandas as pd

from . import ENGINE_VERSION
from .config import Config
from .detect.signals import inr
from .fuse import LAYERS
from .store import DataStore

SEVERITY = {"phantom_services": 5, "identity_cluster": 5, "impossible_timing": 4, "referral_ring": 4,
            "claim_splitting_network": 4, "upcoding_drift": 3, "duplicate_billing": 3, "unbundling": 2, "mixed": 2}
CLINICAL_RISK = {"phantom_services": 1.0, "identity_cluster": 0.8, "impossible_timing": 0.6, "claim_splitting_network": 0.5,
                 "referral_ring": 0.5, "upcoding_drift": 0.3, "duplicate_billing": 0.3, "unbundling": 0.3, "mixed": 0.3}
HARM_DRIVER = {
    "phantom_services": "Services billed that could not have been delivered",
    "identity_cluster": "Member identities used without matching care",
    "impossible_timing": "Care records that cannot all be true",
    "claim_splitting_network": "Repeated procedures with thin documentation",
    "referral_ring": "Referrals driven by the ring rather than clinical need",
    "upcoding_drift": "Visit levels above what the documentation supports",
    "duplicate_billing": "Billing-only harm (duplicate payments)",
    "unbundling": "Billing-only harm (unbundled panels)",
    "mixed": "Billing-only harm",
}
NEXT_ACTION = {"needs_siu_review": "assign_investigator", "request_documentation": "request_records_then_review",
               "monitor": "monitor_30_days", "cleared": "close_no_action"}
LAYER_NAME = {"rules": "rules", "anomaly": "anomaly", "temporal": "temporal", "graph": "graph"}


def score_case(store: DataStore, cfg: Config, case: dict, layers: dict[str, str], missing: list[dict],
               horizon: dict[str, float] | None, hold_status: str = "none") -> dict:
    today = pd.Timestamp(cfg.sim_today)
    risk_of = case["entities_risk"]
    by_method = {m: 0.0 for m in LAYERS}
    hard = False
    for s in case["signals"]:
        if s["direction"] == "incriminating":
            by_method[s["layer"]] = max(by_method[s["layer"]], s["strength"])
            hard |= s["hard"]
    by_method = {m: round(v, 2) for m, v in by_method.items()}
    agreeing = [m for m in LAYERS if layers.get(m) == "ok" and by_method[m] >= 0.5]
    ma = len(agreeing)
    if (hard and ma >= 2) or ma >= 3:
        strength = "strong"
    elif ma == 2:
        strength = "moderate"
    else:
        strength = "weak"
    n_crit = sum(1 for m in missing if m["critical"])
    excul_open = sum(1 for e in case["evidence"] if e["direction"] == "exculpatory" and e["weight"] > 0)
    conf = 0.45 + 0.12 * ma + 0.15 * hard - 0.08 * n_crit - 0.10 * excul_open
    conf = round(min(0.95, max(0.30, conf)), 2)

    # verdict (fixture: strong evidence still goes to SIU while missing records are requested)
    if strength == "strong" and conf >= 0.75:
        status = "needs_siu_review"
    elif strength in ("strong", "moderate"):
        status = "request_documentation"
    else:
        status = "monitor"
    reasons = [f"{ma} of 4 detection methods agree ({', '.join(agreeing) or 'none'})" if ma else "No detection method scores ≥ 0.5"]
    reasons.append(f"Confidence {conf:.2f} {'≥' if conf >= 0.75 else '<'} 0.75")
    if hard:
        hs = next(s for s in case["signals"] if s["hard"])
        reasons.append(f"Hard signal: {hs['name'].lower()} (never exonerated)")
    if n_crit:
        reasons.append(f"{n_crit} critical document type(s) missing: {', '.join(m['doc_type'] for m in missing if m['critical'])}")
    provs = case["providers"]
    if len(provs) > 1 and store.provider_index.loc[provs, "owner_id"].nunique() == 1:
        reasons.append(f"Shared owner links all {len(provs)} providers")

    # money and money clock
    h = case["hdr"]
    pending_mask = h.payment_release_date > today
    paid = int(h.loc[h.payment_status == "paid", "paid"].sum())
    pending = int(h.loc[pending_mask, "allowed"].sum())
    at_risk = paid + pending
    recent = h[h.service_date >= today - pd.DateOffset(days=90)]
    monthly = int(round((recent.loc[recent.payment_status == "paid", "paid"].sum() + recent.loc[recent.payment_release_date > today, "allowed"].sum()) / 3))
    expected = int(round(at_risk * conf * cfg.RECOVERY_RATE))
    effort = int(min(40, round(4 + 0.08 * len(h) + 2 * len(provs) + 1.5 * len(missing))))
    dead_end = round(min(1.0, max(0.0, 1 - conf + 0.1 * n_crit)), 2)
    pend = h[pending_mask]
    if len(pend):
        nxt = pend.payment_release_date.min()
        days = int((nxt - today).days)
        hold = days <= cfg.HOLD_WINDOW_DAYS and strength in ("strong", "moderate") and len(pend) > 0
        reason = (f"{strength.title()} evidence and {inr(pend.allowed.sum())} in {len(pend)} claims releases within {days} days"
                  if hold else None)
        clock = {"next_release_date": str(nxt.date()), "days_until_release": days, "pending_claims": int(len(pend)),
                 "pending_amount": int(pend.allowed.sum()), "hold_recommended": bool(hold), "hold_reason": reason,
                 "hold_status": hold_status}
    else:
        clock = {"next_release_date": None, "days_until_release": None, "pending_claims": 0, "pending_amount": 0,
                 "hold_recommended": False, "hold_reason": None, "hold_status": hold_status}

    # member harm
    mi = store.member_index
    members = sorted(set(h.member_id) | set(case["identity_members"]))
    ages = mi.loc[members, "age"] if members else pd.Series(dtype=int)
    bh_members = set(h.loc[h.service_type == "behavioral_health", "member_id"])
    vulnerable = sorted({m for m in members if mi.loc[m, "age"] >= 65 or m in bh_members})
    vshare = round(len(vulnerable) / max(1, len(members)), 2)
    clinical = CLINICAL_RISK[case["pattern"]]
    size = min(1.0, math.log10(1 + len(members)) / math.log10(101))
    harm = round(0.4 * size + 0.3 * vshare + 0.3 * clinical, 2)
    drivers = [f"{len(members)} members billed", f"{int((ages >= 65).sum())} members aged 65+", HARM_DRIVER[case["pattern"]]]
    if bh_members:
        drivers.insert(2, f"{len(bh_members)} behavioral-health members")

    # next action text
    pending_note = f" for the {len(pend)} pending claims before release" if len(pend) else ""
    if status == "needs_siu_review":
        text = "Assign an investigator"
        if n_crit:
            text += f"; request {missing[0]['doc_type'].replace('_', ' ')}s{pending_note}"
        elif clock["hold_recommended"]:
            text += f"; consider holding {inr(clock['pending_amount'])} releasing in {clock['days_until_release']} days"
    elif status == "request_documentation":
        need = [m["doc_type"].replace("_", " ") + "s" for m in missing] or ["supporting medical records"]
        text = f"Request {', '.join(need)}{pending_note}, then review"
    else:
        text = "Monitor for 30 days; re-score when new claims arrive"

    lim = ["Confidence is a heuristic based on method agreement, not a calibrated probability."]
    for m in LAYERS:
        if layers.get(m) != "ok":
            lim.append(f"The {m} layer did not run; its evidence is missing from this case.")
    for pid in provs:
        tenure = (today - store.provider_index.loc[pid, "enrolled_date"]).days / 30.44
        if tenure < 12:
            lim.append(f"{pid} has only {tenure:.0f} months of history; peer comparison is less reliable.")
    for m in missing:
        if m["critical"]:
            lim.append(f"{m['claim_count']} {m['doc_type'].replace('_', ' ')}s are missing; evidence may change once records are received.")
    doc_ev = [e for e in case["evidence"] if e["type"] == "document"]
    if doc_ev:
        ids = sorted({w for e in doc_ev for w in e["description"].split() if w.startswith("DOC-")})
        lim.append(f"Document checks ({', '.join(ids[:4])}) are deterministic field mismatches; content authenticity needs human review.")
    if horizon is None:
        lim.append("Horizon risk is a placeholder derived from current risk until the forecast model runs.")
    lim.append("All data is synthetic.")

    if horizon is None:
        r = case["risk"] / 100
        horizon = {"30": round(0.55 * r, 2), "60": round(0.65 * r, 2), "90": round(0.72 * r, 2)}

    return {
        "scores": {"risk": case["risk"], "by_method": by_method, "methods_agreeing": ma, "hard_signal": hard},
        "strength": strength, "confidence": conf, "status": status, "reasons": reasons, "next_action_text": text,
        "money": {"dollars_at_risk": at_risk, "paid": paid, "pending": pending, "expected_recovery": expected,
                  "projected_monthly_loss": monthly},
        "payment_clock": clock, "effort_hours": effort, "dead_end_risk": dead_end,
        "member_harm": {"score": harm, "members_affected": len(members), "vulnerable_share": vshare,
                        "clinical_risk": clinical, "drivers": drivers},
        "severity": SEVERITY[case["pattern"]], "limitations": lim, "horizon_risk": horizon, "risk_of": risk_of,
    }


def case_entities(store: DataStore, case: dict) -> list[dict]:
    pidx = store.provider_index
    risk = case["entities_risk"]
    out = []
    for pid in case["providers"]:
        out.append({"entity_type": "provider", "entity_id": pid, "name": str(pidx.loc[pid, "name"]),
                    "role": "billing_provider", "risk": risk[pid]})
    for g in case["groups"]:
        s = next(x for x in case["signals"] if x["entity_id"] == g)
        out.append({"entity_type": "member_group", "entity_id": g, "name": s["name"], "role": "identity_cluster", "risk": risk[g]})
    for m in case["members"]:
        out.append({"entity_type": "member", "entity_id": m, "name": f"Member {m[4:]}", "role": "flagged_member", "risk": risk[m]})
    provs = case["providers"]
    if len(provs) > 1:
        owners = pidx.loc[provs, "owner_id"].value_counts()
        own_names = store.owners.set_index("owner_id")["owner_name"]
        for own, k in owners.items():
            if k >= 2:
                out.append({"entity_type": "owner", "entity_id": own, "name": str(own_names[own]), "role": "shared_owner", "risk": None})
        facs = pidx.loc[provs, "primary_facility_id"].value_counts()
        for fac, k in facs.items():
            if k >= 2:
                out.append({"entity_type": "facility", "entity_id": fac, "name": str(store.facility_index.loc[fac, "name"]),
                            "role": "shared_facility", "risk": None})
    for pid in case["related"]:
        out.append({"entity_type": "provider", "entity_id": pid, "name": str(pidx.loc[pid, "name"]),
                    "role": "related_provider", "risk": risk.get(pid)})
    n_mem = int(case["hdr"].member_id.nunique())
    if n_mem and not case["groups"]:
        out.append({"entity_type": "member_group", "entity_id": f"MGRP-{case['n']:04d}-A", "name": f"{n_mem} members",
                    "role": "members_served", "risk": None})
    return out


def claims_summary(cfg: Config, store: DataStore, case: dict) -> dict:
    h = case["hdr"]
    lo, hi = cfg.THRESHOLD_HUG_LOW * cfg.review_threshold_inr, cfg.review_threshold_inr
    codes = store.claims[store.claims.claim_id.isin(case["claim_ids"])].procedure_code.value_counts().head(6)
    return {
        "claim_count": int(len(h)), "amount_min": int(h.billed.min()) if len(h) else 0,
        "amount_max": int(h.billed.max()) if len(h) else 0, "amount_total": int(h.billed.sum()),
        "under_threshold_share": round(float(((h.billed >= lo) & (h.billed < hi)).mean()), 2) if len(h) else 0.0,
        "review_threshold": cfg.review_threshold_inr,
        "service_types": {k: int(v) for k, v in h.service_type.value_counts().items()},
        "procedure_codes": {k: int(v) for k, v in codes.items()},
    }


def serialize_case(store: DataStore, cfg: Config, case: dict, sc: dict, layers: dict[str, str], peer_context: list[dict],
                   timeline: list[dict], network: dict, missing: list[dict]) -> dict:
    pidx = store.provider_index
    prim = case["primary"]
    if prim.startswith("PRV-"):
        primary = {"entity_type": "provider", "entity_id": prim, "name": str(pidx.loc[prim, "name"])}
    elif prim.startswith("MGRP-"):
        s = next(x for x in case["signals"] if x["entity_id"] == prim)
        primary = {"entity_type": "member_group", "entity_id": prim, "name": s["name"]}
    else:
        primary = {"entity_type": "member", "entity_id": prim, "name": f"Member {prim[4:]}"}
    docs = [{"document_id": r.document_id, "doc_type": r.doc_type, "format": r.format,
             "claim_ids": str(r.claim_ids).split("|"), "path": f"/api/documents/{r.document_id}",
             "scan_url": f"/api/files/scans/{r.document_id}.png" if r.format == "scan" else None}
            for r in sorted(case["documents"], key=lambda r: r.document_id)]
    return {
        "case_id": case["case_id"], "title": case["title"], "pattern": case["pattern"], "status": "open", "currency": "INR",
        "primary_entity": primary, "entities": case_entities(store, case), "layers": layers, "scores": sc["scores"],
        "horizon_risk": sc["horizon_risk"], "money": sc["money"], "payment_clock": sc["payment_clock"],
        "effort_hours": sc["effort_hours"], "dead_end_risk": sc["dead_end_risk"], "member_harm": sc["member_harm"],
        "severity": sc["severity"], "evidence_strength": sc["strength"], "confidence": sc["confidence"],
        "verdict": {"status": sc["status"], "next_action": NEXT_ACTION[sc["status"]], "next_action_text": sc["next_action_text"],
                    "reasons": sc["reasons"], "human_approval_required": True},
        "claims_summary": claims_summary(cfg, store, case), "evidence": case["evidence"], "peer_context": peer_context,
        "timeline": timeline, "network_summary": network, "documents": docs, "missing_documents": missing,
        "limitations": sc["limitations"], "engine_version": ENGINE_VERSION, "generated_at": f"{cfg.sim_today}T08:00:00",
    }
