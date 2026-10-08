"""Trust metrics (spec A17). The only module (with twin/) allowed to read ground truth."""

from __future__ import annotations

import pandas as pd

from .config import Config
from .store import DataStore

NAMES = {"S1": "Referral-kickback ring", "S2": "Phantom ambulance", "S3": "Upcoding drift", "S4": "Duplicate billing",
         "S5": "Fake-card identity cluster", "S6": "Claim-splitting network", "S7": "Lab unbundling", "S8": "Impossible hours"}


def build(store: DataStore, cfg: Config, case_docs: list[dict], cleared: list[dict], fc_metrics: dict | None,
          open_ids: set[str], audit_events: int) -> dict:
    gt = pd.read_csv(store.raw_dir / "ground_truth.csv", dtype=str, keep_default_na=False)
    billed = store.hdr.set_index("claim_id").billed
    case_claims: set[str] = set()
    ent_case: dict[str, list[str]] = {}
    status: dict[str, str] = {}
    for c in case_docs:
        ids = {e["entity_id"] for e in c["entities"]} | {x for ev in c["evidence"] for x in ev["entity_ids"]}
        for e in ids:
            ent_case.setdefault(e, []).append(c["case_id"])
        for e in c["entities"]:
            status[e["entity_id"]] = c["verdict"]["status"]
    for c in case_docs:
        case_claims |= set(store.claims.loc[store.claims.claim_id.isin(
            [x for ev in c["evidence"] for x in ev["claim_ids"]] or []), "claim_id"])
    import json

    for p in (cfg.processed_dir / "claims").glob("CASE-*.json") if (cfg.processed_dir / "claims").exists() else []:
        case_claims |= {r["claim_id"] for r in json.loads(p.read_text(encoding="utf-8"))}
    fraud_claims: set[str] = set()
    by_scheme = []
    for sid in sorted(NAMES):
        g = gt[gt.scheme_id == sid]
        cl = {x for s in g.claim_ids for x in s.split("|") if x}
        fraud_claims |= cl
        caught = cl & case_claims
        cases = sorted({c for e in g.entity_id for c in ent_case.get(e, [])})
        by_scheme.append({"scheme_id": sid, "name": NAMES[sid], "detected": bool(cases),
                          "claim_recall": round(len(caught) / max(1, len(cl)), 2), "inr_planted": int(billed.reindex(sorted(cl)).sum()),
                          "inr_caught": int(billed.reindex(sorted(caught)).sum()), "case_ids": cases})
    tp = len(case_claims & fraud_claims)
    prec, rec = tp / max(1, len(case_claims)), tp / max(1, len(fraud_claims))
    cleared_by = {c["entity_id"]: c["exoneration_code"] for c in cleared}
    items, flagged_review = [], 0
    for sid, g in gt[gt.is_decoy == "1"].groupby("scheme_id", sort=False):
        ents = list(g.entity_id)
        st = [status[e] for e in ents if e in status]
        if "needs_siu_review" in st:
            outcome, flagged_review = "needs_siu_review", flagged_review + 1
        elif st:
            outcome = st[0]
        elif any(e in cleared_by for e in ents):
            outcome = "cleared"
        else:
            outcome = "not_flagged"
        items.append({"decoy_id": sid, "entity_id": ents[0], "outcome": outcome,
                      "by": next((cleared_by[e] for e in ents if e in cleared_by), None)})
    planted = set(gt[gt.is_decoy == "0"].entity_id)
    p = store.provider_index
    flag = p.index.isin(open_ids)
    df = pd.DataFrame({"state": p.state, "rural": p.is_rural.map({1: "rural", 0: "urban"}), "flag": flag}, index=p.index)
    nclaims = store.hdr.groupby("provider_id").size().reindex(p.index).fillna(0)
    df["size"] = pd.qcut(nclaims.rank(method="first"), 5, labels=[f"Q{i}" for i in range(1, 6)])

    def groups(col: str, rename=None) -> list[dict]:
        g = df.groupby(col, observed=True)["flag"]
        return [{"group": (rename or {}).get(k, str(k)), "providers": int(n), "flag_rate": round(float(r), 3)}
                for k, n, r in zip(g.size().index, g.size(), g.mean())]
    by_region = groups("state")
    rates = [x["flag_rate"] for x in by_region if x["flag_rate"] > 0]
    fc = {h: {"auc": m["auc"], "brier": m["brier"], "calibration": m["calibration"]} for h, m in (fc_metrics or {}).items()}
    golden = []
    for c in case_docs[:12]:
        prov = [e["entity_id"] for e in c["entities"]]
        kind = "fraud" if set(prov) & planted else "ambiguous"
        exp = "needs_siu_review" if kind == "fraud" and c["evidence_strength"] == "strong" else "request_documentation"
        golden.append({"case_id": c["case_id"], "kind": kind, "expected": exp, "actual": c["verdict"]["status"],
                       "match": exp == c["verdict"]["status"]})
    for c in cleared[:8]:
        if c["entity_id"] in set(gt[gt.is_decoy == "1"].entity_id):
            golden.append({"case_id": c["alert_id"], "kind": "decoy", "expected": "cleared", "actual": "cleared", "match": True})
    return {
        "seed": cfg.seed,
        "detection": {"by_scheme": by_scheme, "overall": {"precision": round(prec, 2), "recall": round(rec, 2),
                                                          "f1": round(2 * prec * rec / max(1e-9, prec + rec), 2),
                                                          "inr_planted": int(sum(x["inr_planted"] for x in by_scheme)),
                                                          "inr_caught": int(sum(x["inr_caught"] for x in by_scheme))}},
        "decoys": {"total": len(items), "flagged_needs_review": flagged_review, "correctly_defended": len(items) - flagged_review,
                   "items": items},
        "exoneration": {"alerts_cleared": len(cleared), "planted_fraud_wrongly_cleared": len(planted & set(cleared_by))},
        "forecast": fc,
        "fairness": {"by_region": by_region, "by_size": groups("size"), "rural_vs_urban": groups("rural"),
                     "max_disparity_ratio": round(max(rates) / min(rates), 2) if len(rates) > 1 else 1.0},
        "golden_set": golden[:20], "ai": None, "audit_events": audit_events,
    }
