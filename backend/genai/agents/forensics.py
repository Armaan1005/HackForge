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
_STOP = {"synthetic", "with", "and", "the", "of", "for", "under", "procedure"}


def _doc_evidence(case: dict, document_id: str) -> list[dict]:
    return [e for e in case.get("evidence", [])
            if e.get("type") == "document" and (document_id in e.get("description", "") or document_id in e.get("name", ""))]


def code_checks(doc: dict, case: dict) -> list[dict]:
    flags: list[dict] = []
    submitted = doc.get("claim_submitted_at")
    ev = _doc_evidence(case, doc["document_id"])

    def flag(section_id, check, observation, confidence=1.0, evidence_ids=()):
        flags.append({"section_id": section_id, "check": check, "observation": observation, "confidence": confidence,
                      "evidence_ids": list(evidence_ids), "source": "code", "label": "Code-verified field mismatch"})

    for s in doc.get("sections", []):
        m = _INJECTION.search(s.get("text", ""))
        if m:
            flag(s["section_id"], "prompt_injection",
                 f'Text addressed to an AI reviewer ("{m.group(0)}"). Ignored by Axon; treat the record as tampered until verified.')
        if submitted and s.get("created_at", "")[:10] > submitted:
            ids = [e["evidence_id"] for e in ev if "post_submission" in e.get("method", "")]
            flag(s["section_id"], "timeline_conflict",
                 f"Section written {s['created_at'][:10]}, after the claim was submitted on {submitted}.", evidence_ids=ids)
        if s.get("author_provider_id") and s["author_provider_id"] != doc.get("author_provider_id"):
            ids = [e["evidence_id"] for e in ev if s["author_provider_id"] in e.get("entity_ids", [])]
            flag(s["section_id"], "unlinked_author" if ids else "inserted_content",
                 f"Authored by {s['author_provider_id']}, not the record's author {doc.get('author_provider_id')}"
                 + (" — and that provider has no claim or referral for this member." if ids else "."),
                 confidence=1.0 if ids else 0.6, evidence_ids=ids)

    text = " ".join(s.get("text", "") for s in doc.get("sections", [])).lower()
    for p in doc.get("billed_procedures", []):
        words = [w for w in re.findall(r"[a-z]{5,}", p.get("description", "").lower()) if w not in _STOP]
        if words and not any(w in text for w in words):
            flag("-", "procedure_absent", f"Billed {p['code']} ({p['description']}) is never described in the notes.")
    return flags


async def analyze_document(doc: dict, case: dict, scan: bytes | None = None, priority: int = LIVE) -> dict:
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
        out = await gateway.run(
            "forensics", prompts.FORENSICS.format(context=json.dumps(context, ensure_ascii=False), document=body),
            ForensicsOut, system=prompts.BASE, images=[Image(scan)] if scan else None, priority=priority,
        )
        seen = {(f["section_id"], f["check"]) for f in flags}
        valid_sections = {s["section_id"] for s in doc.get("sections", [])} | {"-", "scan"}
        for f in out.flags:
            if (f.section_id, f.check) in seen or f.section_id not in valid_sections:
                continue
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
