from genai import rag
from genai.verifier import index_case, verify_arguments

CASE = {"case_id": "C1", "pattern": "claim_splitting_network", "title": "Claims split under the review limit",
        "evidence": [{"evidence_id": "EV-1", "type": "statistical", "name": "Threshold hugging", "value": 0.62, "comparison_value": 0.08}]}


def test_retrieves_relevant_rule_and_human_review_rule():
    ids = [r["id"] for r in rag.for_case(CASE)]
    assert "POL-014" in ids and "POL-033" in ids and any(i.startswith("LAW-") for i in ids)


def test_verifier_rule_citations():
    idx = index_case(CASE)
    kept, dropped = verify_arguments("p", [
        {"point": "62% of claims sit just under the limit vs 8% for peers.", "evidence_ids": ["EV-1", "POL-014"]},
        {"point": "Split claims breach policy.", "evidence_ids": ["POL-014"]},             # rule alone: struck
        {"point": "62% vs 8%.", "evidence_ids": ["EV-1", "POL-099"]},                      # unretrieved rule: removed
        {"point": "Claims sit under the 50000 limit.", "evidence_ids": ["EV-1", "POL-014"]},  # number only in rule text
    ], idx)
    assert [k["evidence_ids"] for k in kept] == [["EV-1", "POL-014"], ["EV-1"]]
    assert len(dropped) == 2
