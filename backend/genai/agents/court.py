"""Evidence Court: Prosecutor and Defense argue from the same evidence pool, the Verdict Clerk words
the code-computed status, and the Citation Verifier sits between all of them and the UI."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime

from .. import prompts, templates, trace
from ..config import settings
from ..evidence import STATUS_LABEL, pool_json
from ..rag import for_case, rule_refs
from ..gateway import LIVE, AIUnavailable, gateway
from ..schemas import DefenseOut, ProsecutionOut, VerdictOut
from ..verifier import index_case, strip_id_refs, verify_arguments, verify_text


async def _agent(name: str, prompt: str, schema, fallback: dict, priority: int, fresh: bool = False) -> tuple[dict, str, str | None]:
    """Returns (output, source, note). source is 'llm' or 'template'."""
    try:
        out = await gateway.run(name, prompt, schema, system=prompts.BASE, priority=priority, fresh=fresh)
        return out.model_dump(), "llm", None
    except AIUnavailable as e:
        return fallback, "template", str(e)


async def run_court(case: dict, priority: int = LIVE, fresh: bool = False) -> dict:
    idx = index_case(case)
    pool = pool_json(case)
    trace.retrieval("court", for_case(case))

    (pros, pros_src, pros_note), (defn, def_src, def_note) = await asyncio.gather(
        _agent("prosecutor", prompts.PROSECUTOR.format(pool=pool), ProsecutionOut, templates.prosecution(case), priority, fresh),
        _agent("defense", prompts.DEFENSE.format(pool=pool), DefenseOut, templates.defense(case), priority, fresh),
    )
    pros_kept, pros_dropped = verify_arguments("prosecutor", pros["arguments"], idx, case)
    def_kept, def_dropped = verify_arguments("defense", defn["arguments"], idx, case)
    trace.verifier("prosecutor", len(pros_kept), pros_dropped)
    trace.verifier("defense", len(def_kept), def_dropped)

    # If the model produced nothing verifiable, fall back to the deterministic side so the panel is never empty.
    if not pros_kept:
        pros_kept, _ = verify_arguments("prosecutor", templates.prosecution(case)["arguments"], idx)
        pros_src = "template"
    if not def_kept:
        def_kept, _ = verify_arguments("defense", templates.defense(case)["arguments"], idx)
        def_src = "template"

    v = case.get("verdict", {})
    status_label = STATUS_LABEL.get(v.get("status", ""), v.get("status", ""))
    missing = defn.get("missing_evidence") or templates.defense(case)["missing_evidence"]
    verdict_prompt = prompts.VERDICT.format(
        status_label=status_label,
        next_action=v.get("next_action_text", ""),
        reasons=json.dumps(v.get("reasons", []), ensure_ascii=False),
        prosecution=json.dumps([a["point"] for a in pros_kept[:3]], ensure_ascii=False),
        defense=json.dumps([a["point"] for a in def_kept[:3]], ensure_ascii=False),
        missing=json.dumps(missing[:4], ensure_ascii=False),
    )
    clerk, clerk_src, clerk_note = await _agent("verdict_clerk", verdict_prompt, VerdictOut, templates.verdict_summary(case), priority, fresh)
    ok, reason = verify_text(clerk["summary"], clerk.get("evidence_ids", []), idx, whole_case=case)
    if not ok or not clerk["summary"].lower().startswith(status_label.lower()):
        clerk, clerk_src = templates.verdict_summary(case), "template"
        clerk_note = reason or "summary did not start with the code-computed status"

    dropped = pros_dropped + def_dropped
    return {
        "case_id": case["case_id"],
        "prosecution": {"arguments": pros_kept, "source": pros_src},
        "defense": {"arguments": def_kept, "missing_evidence": missing, "source": def_src},
        "verdict": {
            "status": v.get("status"),
            "status_label": status_label,
            "next_action": v.get("next_action"),
            "next_action_text": v.get("next_action_text"),
            "confidence": case.get("confidence"),
            "evidence_strength": case.get("evidence_strength"),
            "summary": strip_id_refs(clerk["summary"]),
            "human_approval_required": True,
            "source": clerk_src,
        },
        "rules": rule_refs(pros_kept + def_kept, case),
        "verifier": {
            "checked": len(pros_kept) + len(def_kept) + len(dropped),
            "kept": len(pros_kept) + len(def_kept),
            "dropped": len(dropped),
            "dropped_items": dropped,
        },
        "ai": {
            "model": gateway.last_model.get("prosecutor", gateway.models[0] if gateway.models else settings.model),
            "pending": any("still queued" in n for n in (pros_note, def_note, clerk_note) if n),
            "enabled": settings.ai_enabled,
            "notes": [n for n in (pros_note, def_note, clerk_note) if n],
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
