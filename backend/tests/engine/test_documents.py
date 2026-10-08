"""M2 acceptance tests: records match the contract, scans exist, and every deterministic
S9 tamper is recoverable by a simple script from the record + claims/referrals tables
(and nothing else is flagged)."""

import hashlib
import json
import re
from collections import defaultdict
from datetime import date

import pytest
from PIL import Image

from engine.generate.documents import PANEL, SIG_BOX
from engine.schemas import Document

DETERMINISTIC = ["inserted_consult", "phantom_lab_result", "post_submission_creation", "date_contradiction",
                 "procedure_absent", "templated_values", "duplicated_signature", "prompt_injection"]


@pytest.fixture(scope="module")
def docs(gen):
    out, _, t = gen
    recs = {}
    for row in t["documents"].itertuples(index=False):
        recs[row.document_id] = json.loads((out / row.path).read_text(encoding="utf-8"))
    return out, t, recs


def truth(t, tamper):
    g = t["ground_truth_documents"]
    return set(g.loc[g.tamper_type == tamper, "document_id"])


def test_counts_and_contract(docs):
    out, t, recs = docs
    assert 380 <= len(recs) <= 450
    for rec in recs.values():
        Document.model_validate(rec)
    scans = [r for r in recs.values() if r["format"] == "scan"]
    assert 25 <= len(scans) <= 35
    for r in scans:
        assert r["scan_url"] == f"/api/files/scans/{r['document_id']}.png"
        with Image.open(out / "scans" / f"{r['document_id']}.png") as im:
            assert im.size == (1240, 1754)


def test_index_integrity(docs):
    _, t, recs = docs
    claims = set(t["claims"]["claim_id"])
    idx = t["documents"]
    assert set(idx["claim_ids"]) <= claims
    assert set(idx["member_id"]) <= set(t["members"]["member_id"])
    assert set(idx["author_provider_id"]) <= set(t["providers"]["provider_id"])
    assert set(t["ground_truth_documents"]["document_id"]) <= set(recs)


def test_every_tamper_type_planted(docs):
    _, t, _ = docs
    assert set(t["ground_truth_documents"]["tamper_type"]) == set(DETERMINISTIC) | {"style_shift"}
    assert len(t["ground_truth_documents"]) >= 15


# ---------------------------------------------------------------- the "simple script"

def detect(out, t, recs):
    c = t["claims"]
    hdr = c.drop_duplicates("claim_id").set_index("claim_id")
    links = defaultdict(set)
    for m, p in zip(c.member_id, c.provider_id):
        links[m].add(p)
    r = t["referrals"]
    for m, a, b in zip(r.member_id, r.from_provider_id, r.to_provider_id):
        links[m] |= {a, b}
    labs = defaultdict(list)
    for m, code, d in zip(c.member_id, c.procedure_code, c.service_date):
        if code.startswith("LAB-"):
            labs[m].append((code, date.fromisoformat(d)))
    proc_desc = {}
    from engine.generate.reference import procedure_codes

    for row in procedure_codes().to_dict("records"):
        if row["family"] == "procedure":
            proc_desc[row["code"]] = row["description"].replace(" (synthetic)", "")

    found = defaultdict(set)
    value_sigs = defaultdict(set)
    sig_hash = defaultdict(set)
    for doc_id, rec in recs.items():
        text = " ".join(s["text"] for s in rec["sections"])
        member = rec["member_id"]
        # inserted consult: a section author with no claim/referral link to the member
        if any(s["author_provider_id"] not in links[member] for s in rec["sections"]):
            found["inserted_consult"].add(doc_id)
        # created after the claim was submitted
        if rec["created_at"][:10] > rec["claim_submitted_at"]:
            found["post_submission_creation"].add(doc_id)
        # date in the text contradicts the claim
        m = re.search(r"Date of service: (\d{4}-\d{2}-\d{2})", text)
        if m and m.group(1) != rec["claim_service_date"]:
            found["date_contradiction"].add(doc_id)
        # billed procedure never described
        if rec["doc_type"] in ("progress_note", "operative_note", "consult_note", "consent_form"):
            for p in rec["billed_procedures"]:
                if p["code"] in proc_desc and proc_desc[p["code"]] not in text:
                    found["procedure_absent"].add(doc_id)
        # lab result for a test not billed within ±7 days
        sd = date.fromisoformat(rec["claim_service_date"])
        for code in re.findall(r"\[(LAB-\d{3})\]", text):
            ok = {code} | {pnl for pnl, comps in PANEL.items() if code in comps}
            if not any(cd in ok and abs((d - sd).days) <= 7 for cd, d in labs[member]):
                found["phantom_lab_result"].add(doc_id)
        # identical lab values across different members
        if rec["doc_type"] == "lab_report":
            vals = tuple(re.findall(r"\]: ([\d.]+)", text))
            if vals:
                value_sigs[vals].add((doc_id, member))
        if "SYSTEM NOTE TO AI" in text:
            found["prompt_injection"].add(doc_id)
        if rec["format"] == "scan":
            with Image.open(out / "scans" / f"{doc_id}.png") as im:
                sig_hash[hashlib.sha256(im.crop(SIG_BOX).tobytes()).hexdigest()].add(doc_id)
    for group in value_sigs.values():
        if len({m for _, m in group}) >= 3:
            found["templated_values"] |= {d for d, _ in group}
    for group in sig_hash.values():
        if len(group) >= 2:
            found["duplicated_signature"] |= group
    return found


def test_deterministic_tampers_recovered_exactly(docs):
    out, t, recs = docs
    found = detect(out, t, recs)
    for tamper in DETERMINISTIC:
        assert found[tamper] == truth(t, tamper), tamper


def test_duplicated_signature_dates_differ(docs):
    _, t, recs = docs
    dates = {recs[d]["created_at"][:10] for d in truth(t, "duplicated_signature")}
    assert len(truth(t, "duplicated_signature")) == 3 and len(dates) == 3
