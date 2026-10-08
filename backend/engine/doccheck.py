"""Deterministic document cross-checks (spec A2/A9): record fields vs the claims tables.

These are field mismatches, not authenticity judgements; Part B's forensics agent adds
AI-observed flags on top, which never change the engine's score.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import date

from PIL import Image

from .generate.documents import PANEL, SIG_BOX
from .store import DataStore

DATE_RE = re.compile(r"Date of service: (\d{4}-\d{2}-\d{2})")
LAB_RE = re.compile(r"\[(LAB-\d{3})\]")
VALUE_RE = re.compile(r"\]: ([\d.]+)")


def _flag(check: str, doc: dict, section_id: str, name: str, description: str, value, comparison_value,
          comparison_label: str, unit: str, severity: int, sources: list[tuple[str, str]], entity_ids: list[str]) -> dict:
    return {"check": check, "document_id": doc["document_id"], "section_id": section_id, "name": name,
            "description": description, "value": value, "comparison_value": comparison_value,
            "comparison_label": comparison_label, "unit": unit, "severity": severity,
            "sources": [{"table": t, "column": c} for t, c in sources], "entity_ids": entity_ids,
            "claim_ids": doc["claim_ids"]}


def document_flags(store: DataStore) -> dict[str, list[dict]]:
    """Run every deterministic check over every record. Returns {document_id: [flag, ...]}."""
    docs = store.documents
    if docs.empty:
        return {}
    c = store.claims
    links: dict[str, set[str]] = defaultdict(set)
    for m, p in zip(c.member_id, c.provider_id):
        links[m].add(p)
    r = store.referrals
    for m, a, b in zip(r.member_id, r.from_provider_id, r.to_provider_id):
        links[m] |= {a, b}
    labs: dict[str, list[tuple[str, date]]] = defaultdict(list)
    lab_lines = c[c.service_type == "lab"]
    for m, code, d in zip(lab_lines.member_id, lab_lines.procedure_code, lab_lines.service_date):
        labs[m].append((code, d.date()))
    pc = store.procedure_codes
    proc_desc = {str(k): str(v).replace(" (synthetic)", "") for k, v in zip(pc.code, pc.description)
                 if pc.loc[pc.code == k, "family"].iloc[0] == "procedure"}

    flags: dict[str, list[dict]] = defaultdict(list)
    value_groups: dict[tuple, list[tuple[str, str]]] = defaultdict(list)
    sig_groups: dict[str, list[str]] = defaultdict(list)
    recs = {d: store.record(d) for d in docs.document_id}
    for doc_id, rec in recs.items():
        text = " ".join(s["text"] for s in rec["sections"])
        member = rec["member_id"]
        for s in rec["sections"]:
            a = s["author_provider_id"]
            if a not in links[member]:
                flags[doc_id].append(_flag(
                    "inserted_consult_author_unlinked", rec, s["section_id"],
                    "Section authored by a provider with no link to the member",
                    f"{doc_id} section '{s['heading']}' is authored by {a}, who has no claim or referral for {member}.",
                    0, 1, "expected: at least one claim or referral linking author and member", "count", 4,
                    [("documents", "author_provider_id"), ("claims", "provider_id"), ("referrals", "from_provider_id")],
                    [a, member]))
        created, submitted = rec["created_at"][:10], rec["claim_submitted_at"]
        if created > submitted:
            days = (date.fromisoformat(created) - date.fromisoformat(submitted)).days
            flags[doc_id].append(_flag(
                "post_submission_creation", rec, rec["sections"][-1]["section_id"], "Record created after the claim was submitted",
                f"{doc_id} created {created}, {days} days after claim {rec['claim_ids'][0]} was submitted on {submitted}.",
                days, 0, "days after submission (expected ≤ 0)", "days", 3,
                [("documents", "created_at"), ("claims", "submitted_date")], [rec["author_provider_id"]]))
        m = DATE_RE.search(text)
        if m and m.group(1) != rec["claim_service_date"]:
            gap = abs((date.fromisoformat(m.group(1)) - date.fromisoformat(rec["claim_service_date"])).days)
            flags[doc_id].append(_flag(
                "date_contradiction", rec, rec["sections"][0]["section_id"], "Date in the note contradicts the claim",
                f"{doc_id} says the service was on {m.group(1)}; the claim's service date is {rec['claim_service_date']} ({gap} days apart).",
                gap, 0, "days between note date and claim service date", "days", 3,
                [("documents", "sections.text"), ("claims", "service_date")], [rec["author_provider_id"]]))
        if rec["doc_type"] in ("progress_note", "operative_note", "consult_note", "consent_form"):
            for p in rec["billed_procedures"]:
                if p["code"] in proc_desc and proc_desc[p["code"]] not in text:
                    flags[doc_id].append(_flag(
                        "procedure_absent", rec, "", "Billed procedure not described in the record",
                        f"Claim {rec['claim_ids'][0]} bills {p['code']} ({proc_desc[p['code']]}), which {doc_id} never mentions.",
                        0, 1, "mentions of the billed procedure (expected ≥ 1)", "count", 3,
                        [("claims", "procedure_code"), ("documents", "sections.text")], [rec["author_provider_id"]]))
        sd = date.fromisoformat(rec["claim_service_date"])
        for code in sorted(set(LAB_RE.findall(text))):
            ok = {code} | {pnl for pnl, comps in PANEL.items() if code in comps}
            if not any(cd in ok and abs((d - sd).days) <= 7 for cd, d in labs[member]):
                sid = next((s["section_id"] for s in rec["sections"] if f"[{code}]" in s["text"]), "")
                flags[doc_id].append(_flag(
                    "phantom_lab_result", rec, sid, "Lab result for a test never billed",
                    f"{doc_id} reports {code}, but no {code} claim exists for {member} within 7 days of {sd}.",
                    0, 1, "matching lab claims within ±7 days (expected ≥ 1)", "count", 4,
                    [("documents", "sections.text"), ("claims", "procedure_code")], [member]))
        if rec["doc_type"] == "lab_report":
            vals = tuple(VALUE_RE.findall(text))
            if vals:
                value_groups[vals].append((doc_id, member))
        if rec["format"] == "scan":
            path = store.raw_dir / "scans" / f"{doc_id}.png"
            if path.exists():
                with Image.open(path) as im:
                    sig_groups[hashlib.sha256(im.crop(SIG_BOX).tobytes()).hexdigest()].append(doc_id)
    for group in value_groups.values():
        members = {m for _, m in group}
        if len(members) >= 3:
            for doc_id, _ in group:
                rec = recs[doc_id]
                sid = next((s["section_id"] for s in rec["sections"] if s["heading"] == "Results"), "")
                flags[doc_id].append(_flag(
                    "templated_values", rec, sid, "Identical lab values across different members",
                    f"{doc_id} has exactly the same lab values as {len(group) - 1} other report(s) for {len(members) - 1} other member(s).",
                    len(members), 1, "members sharing this exact set of values (expected 1)", "members", 3,
                    [("documents", "sections.text")], sorted(members)))
    for docs_same in sig_groups.values():
        if len(docs_same) >= 2:
            for doc_id in docs_same:
                rec = recs[doc_id]
                flags[doc_id].append(_flag(
                    "duplicated_signature", rec, "", "Signature image identical to other scans",
                    f"The signature on {doc_id} is pixel-identical to {len(docs_same) - 1} other scan(s) "
                    f"({', '.join(d for d in docs_same if d != doc_id)}).",
                    len(docs_same), 1, "scans sharing this exact signature bitmap (expected 1)", "scans", 3,
                    [("scans", "signature_region")], [rec["author_provider_id"]]))
    for doc_id, rec in recs.items():
        if any("SYSTEM NOTE TO AI" in s["text"] for s in rec["sections"]):
            sid = next(s["section_id"] for s in rec["sections"] if "SYSTEM NOTE TO AI" in s["text"])
            flags[doc_id].append(_flag(
                "embedded_instruction", rec, sid, "Text addressed to an AI reviewer",
                f"{doc_id} contains an instruction addressed to an automated reviewer; it is treated as data and ignored.",
                1, 0, "embedded instructions (expected 0)", "count", 2, [("documents", "sections.text")],
                [rec["author_provider_id"]]))
    return dict(flags)
