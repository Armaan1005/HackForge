"""M5 acceptance: decoys defended, no planted fraud exonerated, peer context present."""

import json

import pandas as pd

from engine import schemas as S


def _load(processed, gen):
    data_dir = processed[0]
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((data_dir / "processed" / "cases").glob("CASE-*.json"))]
    cleared = json.loads((data_dir / "processed" / "alerts_cleared.json").read_text(encoding="utf-8"))
    gt = pd.read_csv(gen[0] / "ground_truth.csv", dtype=str, keep_default_na=False)
    return cases, cleared, gt


def test_no_planted_fraud_exonerated(processed, gen):
    _, cleared, gt = _load(processed, gen)
    fraud = set(gt[gt.is_decoy == "0"].entity_id)
    assert not fraud & {c["entity_id"] for c in cleared["items"]}
    S.AlertsCleared.model_validate({"total": cleared["total"], "limit": 50, "offset": 0, "items": cleared["items"][:50]})
    assert all(c["exoneration_code"].startswith("EX") and c["facts"] for c in cleared["items"])


def test_decoys_defended(processed, gen):
    cases, _, gt = _load(processed, gen)
    siu = {e["entity_id"] for c in cases if c["verdict"]["status"] == "needs_siu_review"
           for e in c["entities"] if e["role"] in ("billing_provider", "flagged_member", "identity_cluster")}
    decoys = gt[gt.is_decoy == "1"].groupby("scheme_id")["entity_id"].apply(set)
    defended = sum(1 for ents in decoys if not ents & siu)
    assert defended / len(decoys) >= 0.9, (defended, len(decoys))


def test_peer_context(processed):
    data_dir = processed[0]
    for p in sorted((data_dir / "processed" / "cases").glob("CASE-*.json")):
        c = json.loads(p.read_text(encoding="utf-8"))
        if c["primary_entity"]["entity_type"] != "provider":
            continue
        pc = c["peer_context"]
        assert pc and all(x["evidence_id"].startswith("PC-") and x["peer_group"]["n"] >= 1 for x in pc)
        assert all(x["low_sample"] == (x["peer_group"]["n"] < 20) for x in pc if x["metric"] != "Nearest same-type competitor (km)")
        assert any("risk-adjusted" in x["metric"] for x in pc)
