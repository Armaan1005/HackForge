"""Document Forensics: deterministic cross-checks (code-verified) + Gemini observations (AI-observed).

Record text is hostile input: it is wrapped as untrusted, scanned for prompt injection by code first,
and nothing here can change a score. Flags are labelled for human verification.
"""
from __future__ import annotations

import json
import re

from .. import prompts
from ..gateway import LIVE, AIUnavailable, Image, gateway
from ..schemas import ForensicsOut

_INJECTION = re.compile(
    r"(ignore (all |any )?(previous|prior|above)|system (note|prompt|message)|note to (the )?(ai|reviewer|model)|"
    r"ai reviewer|as an ai|mark (this|the)? ?(claim|case|record)? ?as (cleared|verified|approved|legitimate)|"
    r"disregard (the )?(above|previous)|you are now|do not flag)",
    re.IGNORECASE,
)


_DOC_ID = re.compile(r"DOC-\d+")
# Part A's deterministic document checks (engine/doccheck.py) -> our flag vocabulary
_ENGINE_CHECK = {
    "inserted_consult_author_unlinked": "unlinked_author", "post_submission_creation": "timeline_conflict",
    "date_contradiction": "timeline_conflict", "embedded_instruction": "prompt_injection",
    "duplicated_signature": "signature_reuse", "phantom_lab_result": "phantom_result",
    "procedure_absent": "procedure_absent", "templated_values": "templated_values",
}


def _doc_evidence(case: dict, document_id: str) -> list[dict]:
    """Engine document evidence whose subject (first DOC id mentioned) is this document."""
    out = []
    for e in case.get("evidence", []):
        if e.get("type") != "document":
            continue
        ids = _DOC_ID.findall(f"{e.get('description', '')} {e.get('name', '')}")
        if ids and ids[0] == document_id:
            out.append(e)
    return out


def code_checks(doc: dict, case: dict) -> list[dict]:
    """Code-verified flags: Part A's document checks, plus our injection scan as a backstop."""
    flags: list[dict] = []
    headings = {s.get("heading", "").lower(): s["section_id"] for s in doc.get("sections", [])}

    def flag(section_id, check, observation, evidence_ids=()):
        flags.append({"section_id": section_id, "check": check, "observation": observation, "confidence": 1.0,
                      "evidence_ids": list(evidence_ids), "source": "code", "label": "Code-verified field mismatch"})

    for e in _doc_evidence(case, doc["document_id"]):
        method = e.get("method", "").split(".", 1)[-1]
        quoted = re.findall(r"'([^']+)'", e.get("description", ""))
        section = next((headings[q.lower()] for q in quoted if q.lower() in headings), "-")
        if section == "-" and method == "inserted_consult_author_unlinked":
            section = next((s["section_id"] for s in doc.get("sections", []) if s.get("author_provider_id") in e.get("entity_ids", [])), "-")
        if section == "-" and method == "post_submission_creation" and doc.get("claim_submitted_at"):
            section = next((s["section_id"] for s in doc.get("sections", []) if s.get("created_at", "")[:10] > doc["claim_submitted_at"]), "-")
        flag(section, _ENGINE_CHECK.get(method, "other"), e.get("description", e.get("name", "")), [e["evidence_id"]])

    if not any(f["check"] == "prompt_injection" for f in flags):
        for s in doc.get("sections", []):
            m = _INJECTION.search(s.get("text", ""))
            if m:
                flag(s["section_id"], "prompt_injection", f'Text addressed to an AI reviewer ("{m.group(0)}"). Ignored by Axon.')
    # put injections on the section that contains them
    for f in flags:
        if f["check"] == "prompt_injection" and f["section_id"] == "-":
            sec = next((s["section_id"] for s in doc.get("sections", []) if _INJECTION.search(s.get("text", ""))), "-")
            f["section_id"] = sec
    return flags


async def analyze_document(doc: dict, case: dict, scan: bytes | None = None, priority: int = LIVE, use_ai: bool = True) -> dict:
    flags = code_checks(doc, case)
    context = {
        "document_id": doc["document_id"], "doc_type": doc.get("doc_type"), "member_id": doc.get("member_id"),
        "record_author": doc.get("author_provider_id"), "claim_ids": doc.get("claim_ids"),
        "claim_service_date": doc.get("claim_service_date"), "claim_submitted_at": doc.get("claim_submitted_at"),
        "billed_procedures": doc.get("billed_procedures", []),
        "related_evidence": [{k: e.get(k) for k in ("evidence_id", "name", "description")} for e in _doc_evidence(case, doc["document_id"])],
    }
    body = json.dumps([{k: s.get(k) for k in ("section_id", "heading", "author_provider_id", "created_at", "text")}
                       for s in doc.get("sections", [])], ensure_ascii=False)
    source, note = "llm", None
    try:
        if not use_ai:
            raise AIUnavailable("AI review saved for the most important records (free-tier quota)")
        out = await gateway.run(
            "forensics", prompts.FORENSICS.format(context=json.dumps(context, ensure_ascii=False), document=body),
            ForensicsOut, system=prompts.BASE, images=[Image(scan)] if scan else None, priority=priority,
        )
        proven = {f["check"] for f in flags}  # don't repeat what code already proved
        seen: set[tuple[str, str]] = set()
        valid_sections = {s["section_id"] for s in doc.get("sections", [])} | {"-", "scan"}
        for f in out.flags:
            if f.check in proven or (f.section_id, f.check) in seen or f.section_id not in valid_sections:
                continue
            seen.add((f.section_id, f.check))
            flags.append({**f.model_dump(), "confidence": max(0.0, min(1.0, f.confidence)), "evidence_ids": [],
                          "source": "ai", "label": "AI-observed, human to verify"})
        overall = out.overall_note
    except AIUnavailable as e:
        source, note = "code_only", str(e)
        overall = "AI review unavailable; showing code-verified checks only."

    return {
        "document_id": doc["document_id"],
        "integrity_flags": [{"flag_id": f"FL-{doc['document_id'][-5:]}-{i + 1:02d}", **f} for i, f in enumerate(flags)],
        "injection_detected": any(f["check"] == "prompt_injection" for f in flags),
        "overall_note": overall,
        "source": source,
        "note": note,
        "affects_score": False,
    }
