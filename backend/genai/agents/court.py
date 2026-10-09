"""Evidence Court: Prosecutor and Defense argue from the same evidence pool, the Verdict Clerk words
the code-computed status, and the Citation Verifier sits between all of them and the UI."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Awaitable, Callable

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


Emit = Callable[[dict], Awaitable[None]]


def side_events(result: dict) -> list[dict]:
    """A finished court result as the events a live stream would have sent (used when the answer is cached)."""
    dropped = result["verifier"]["dropped_items"]
    return [
        {"event": "side", "side": "prosecution", "arguments": result["prosecution"]["arguments"], "source": result["prosecution"]["source"], "rules": result.get("rules", []),
         "dropped": [d for d in dropped if d.get("agent") == "prosecutor"], "model": result["ai"]["model"]},
        {"event": "side", "side": "defense", "arguments": result["defense"]["arguments"], "source": result["defense"]["source"], "rules": result.get("rules", []),
         "missing_evidence": result["defense"]["missing_evidence"], "dropped": [d for d in dropped if d.get("agent") == "defense"],
         "model": result["ai"]["model"]},
    ]


async def run_court(case: dict, priority: int = LIVE, fresh: bool = False, emit: Emit | None = None) -> dict:
    """emit (optional) receives each side the moment it is verified, so the UI can start the hearing early."""
    idx = index_case(case)
    pool = pool_json(case)
    trace.retrieval("court", for_case(case))

    async def side(name: str, agent: str, prompt: str, schema, template: dict):
        out, src, note = await _agent(agent, prompt, schema, template, priority, fresh)
        kept, dropped = verify_arguments(agent, out["arguments"], idx, case)
        trace.verifier(agent, len(kept), dropped)
        # If the model produced nothing verifiable, fall back to the deterministic side so the panel is never empty.
        if not kept:
            kept, _ = verify_arguments(agent, template["arguments"], idx)
            src = "template"
        if emit:
            ev = {"event": "side", "side": name, "arguments": kept, "source": src, "dropped": dropped, "rules": rule_refs(kept, case),
                  "model": gateway.last_model.get(agent, gateway.models[0] if gateway.models else settings.model)}
            if name == "defense":
                ev["missing_evidence"] = out.get("missing_evidence") or template["missing_evidence"]
            await emit(ev)
        return out, src, note, kept, dropped

    (pros, pros_src, pros_note, pros_kept, pros_dropped), (defn, def_src, def_note, def_kept, def_dropped) = await asyncio.gather(
        side("prosecution", "prosecutor", prompts.PROSECUTOR.format(pool=pool), ProsecutionOut, templates.prosecution(case)),
        side("defense", "defense", prompts.DEFENSE.format(pool=pool), DefenseOut, templates.defense(case)),
    )

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
