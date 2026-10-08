"""Exoneration Explainer (one line per cleared alert) and the grounded Ask-the-Case assistant."""
from __future__ import annotations

import json

from .. import prompts, templates
from ..evidence import pool_json
from ..gateway import LIVE, AIUnavailable, gateway
from ..schemas import AskOut, ClearedOut
from ..verifier import allowed_numbers, index_case, number_ok, numbers_in, verify_text


async def explain_cleared(alerts: list[dict], priority: int = LIVE) -> dict:
    by_id = {a["alert_id"]: a for a in alerts}
    lines = {a["alert_id"]: {"text": templates.cleared_line(a), "source": "template"} for a in alerts}
    note = None
    if alerts:
        try:
            payload = [{k: a.get(k) for k in ("alert_id", "entity_name", "triggered_by", "exoneration_code", "facts")} for a in alerts[:20]]
            out = await gateway.run("cleared_explainer", prompts.CLEARED.format(alerts=json.dumps(payload, ensure_ascii=False)),
                                    ClearedOut, system=prompts.BASE, priority=priority)
            for item in out.items:
                a = by_id.get(item.alert_id)
                if not a:
                    continue
                allowed = allowed_numbers([a.get("facts", {}), a.get("entity_name", "")])
                if all(number_ok(n, allowed) for n in numbers_in(item.text)):
                    lines[item.alert_id] = {"text": item.text, "source": "llm"}
        except AIUnavailable as e:
            note = str(e)
    return {"items": [{"alert_id": k, **v} for k, v in lines.items()], "note": note}


async def ask_case(case: dict, question: str, priority: int = LIVE) -> dict:
    idx = index_case(case)
    try:
        out = await gateway.run("ask_case", prompts.ASK.format(pool=pool_json(case), question=question[:500]),
                                AskOut, system=prompts.BASE, priority=priority)
        if out.insufficient:
            return {"answer": out.answer, "evidence_ids": [], "grounded": False, "source": "llm"}
        ok, reason = verify_text(out.answer, out.evidence_ids, idx)
        if ok:
            return {"answer": out.answer, "evidence_ids": [i for i in out.evidence_ids if i in idx], "grounded": True, "source": "llm"}
        return {"answer": f"I couldn't produce a fully grounded answer ({reason}). Check the evidence list directly.",
                "evidence_ids": [], "grounded": False, "source": "verifier"}
    except AIUnavailable as e:
        return {"answer": f"AI assistant unavailable ({e}). The evidence list and peer context show every fact the engine found.",
                "evidence_ids": [], "grounded": False, "source": "unavailable"}
