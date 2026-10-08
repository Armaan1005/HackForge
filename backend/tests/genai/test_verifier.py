from genai.engine_client import fixture
from genai.verifier import index_case, numbers_in, verify_arguments, verify_text


def _idx():
    return index_case(fixture("case_detail"))


def test_numbers_are_normalised():
    assert numbers_in("₹21.84L across 47 claims, 94% of them") == [2184000, 47, 94]
    assert numbers_in("PRV-00412 on 2026-09-21 billed EM5") == []  # IDs, dates, codes are not numbers


def test_grounded_argument_is_kept():
    arg = {"point": "44 of 47 claims (94%) sit under the threshold vs a peer median of 11% (n=64)",
           "evidence_ids": ["EV-0001-01"], "case_value": 0.94, "comparison_value": 0.11}
    kept, dropped = verify_arguments("prosecutor", [arg], _idx())
    assert len(kept) == 1 and not dropped


def test_uncited_argument_is_dropped():
    kept, dropped = verify_arguments("prosecutor", [{"point": "Billing is unusual", "evidence_ids": []}], _idx())
    assert not kept and dropped[0]["reason"] == "uncited"


def test_unknown_evidence_id_is_dropped():
    kept, dropped = verify_arguments("defense", [{"point": "Clean history", "evidence_ids": ["EV-9999-99"]}], _idx())
    assert not kept and "unknown evidence" in dropped[0]["reason"]


def test_invented_number_is_dropped():
    arg = {"point": "72% of claims sit under the threshold", "evidence_ids": ["EV-0001-01"], "case_value": 0.94, "comparison_value": 0.11}
    kept, dropped = verify_arguments("prosecutor", [arg], _idx())
    assert not kept and "72" in dropped[0]["reason"]


def test_invented_case_value_is_dropped():
    arg = {"point": "Most claims sit under the threshold", "evidence_ids": ["EV-0001-01"], "case_value": 0.61, "comparison_value": 0.11}
    kept, dropped = verify_arguments("prosecutor", [arg], _idx())
    assert not kept and "case_value" in dropped[0]["reason"]


def test_prose_against_whole_case():
    case = fixture("case_detail")
    ok, _ = verify_text("Needs SIU review: 3 of 4 methods agree and ₹5.32L releases in 3 days.", [], _idx(), whole_case=case)
    assert ok
    ok, reason = verify_text("Needs SIU review: ₹9.99L releases tomorrow.", [], _idx(), whole_case=case)
    assert not ok and reason.startswith("number not in case evidence")


def test_ordinals_and_inline_ids():
    from genai.verifier import strip_id_refs
    assert numbers_in("3 vs 27 (1.6th percentile, n=64)") == [3, 27, 1.6, 64]
    arg = {"point": "Distinct procedure codes billed is 3 vs a peer median of 27 (1.6th percentile, Orthopedics, MH, n=64) [PC-0001-04].",
           "evidence_ids": ["PC-0001-04"], "case_value": 3, "comparison_value": 27}
    kept, dropped = verify_arguments("prosecutor", [arg], _idx())
    assert kept and not dropped
    assert kept[0]["point"].endswith("n=64).")
    assert strip_id_refs("Share is 94% [EV-0001-01, PC-0001-01] vs 11%.") == "Share is 94% vs 11%."


def test_sentence_end_numbers_and_spacing():
    from genai.verifier import strip_id_refs
    assert numbers_in("The claims total ₹21.84L.") == [2184000]
    assert numbers_in("Share is 94%.") == [94]
    assert strip_id_refs("Clean history [EV-0001-09] .") == "Clean history."
