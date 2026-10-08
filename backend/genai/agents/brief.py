"""Brief Writer: turns the verified court output + evidence into an investigation brief (Markdown)."""
from __future__ import annotations

import json

from .. import prompts, templates, trace
from ..rag import for_case, rule_refs
from ..evidence import STATUS_LABEL, fmt_value, pool_json
from ..gateway import LIVE, AIUnavailable, gateway
from ..schemas import BriefOut
from ..verifier import index_case, verify_text


def _verified_points(points: list[dict], idx: dict) -> list[dict]:
    out = []
    for p in points:
        ok, _ = verify_text(p["text"], p.get("evidence_ids", []), idx)
        if ok:
            out.append(p)
    return out


async def write_brief(case: dict, court: dict, priority: int = LIVE) -> dict:
    idx = index_case(case)
    trace.retrieval("brief_writer", for_case(case))
    pros, defn = court["prosecution"]["arguments"], court["defense"]["arguments"]
    fallback = templates.brief(case, pros, defn)
    source, note = "llm", None
    try:
        out = await gateway.run(
            "brief_writer",
            prompts.BRIEF.format(
                pool=pool_json(case),
                timeline=json.dumps(case.get("timeline", []), ensure_ascii=False),
                prosecution=json.dumps([{"point": a["point"], "ids": a["evidence_ids"]} for a in pros], ensure_ascii=False),
                defense=json.dumps([{"point": a["point"], "ids": a["evidence_ids"]} for a in defn], ensure_ascii=False),
            ),
            BriefOut, system=prompts.BASE, priority=priority,
        )
        b = out.model_dump()
        b["key_findings"] = _verified_points(b["key_findings"], idx) or fallback["key_findings"]
        b["alternative_explanations"] = _verified_points(b["alternative_explanations"], idx) or fallback["alternative_explanations"]
        for field in ("executive_summary", "network_context", "timeline_narrative", "recommended_action"):
            ok, _ = verify_text(b[field], [], idx, whole_case=case)
            if not ok:
                b[field] = fallback[field]
    except AIUnavailable as e:
        b, source, note = fallback, "template", str(e)

    b["rules"] = rule_refs(pros + defn + b.get("key_findings", []) + b.get("alternative_explanations", []), case)
    return {"case_id": case["case_id"], "sections": b, "markdown": render_markdown(case, court, b), "source": source, "note": note}


def render_markdown(case: dict, court: dict, b: dict) -> str:
    v = case.get("verdict", {})
    money = case.get("money", {})
    clock = case.get("payment_clock", {})
    harm = case.get("member_harm", {})
    cite = lambda ids: " " + " ".join(f"`{i}`" for i in ids) if ids else ""  # noqa: E731
    lines = [
        f"# Investigation brief: {case['case_id']}",
        f"**{case.get('title')}**  ",
        "*Axon · synthetic data · advisory only: a human investigator decides.*",
        "",
        "| Status | Risk | Evidence | Confidence | Exposure | Pending | Release in | Members |",
        "|---|---|---|---|---|---|---|---|",
        f"| {STATUS_LABEL.get(v.get('status', ''), '')} | {case.get('scores', {}).get('risk')} | {case.get('evidence_strength')} | "
        f"{case.get('confidence')} | {fmt_value(money.get('dollars_at_risk'), unit='inr')} | {fmt_value(money.get('pending'), unit='inr')} | "
        f"{clock.get('days_until_release', 'n/a')} days | {harm.get('members_affected', 'n/a')} |",
        "",
        "## Summary",
        b["executive_summary"],
        "",
        "## Key findings",
        *[f"- {p['text']}{cite(p.get('evidence_ids'))}" for p in b["key_findings"]],
        "",
        "## Alternative explanations (defense)",
        *[f"- {p['text']}{cite(p.get('evidence_ids'))}" for p in b["alternative_explanations"]],
        "",
        "## Network context",
        b["network_context"],
        "",
        "## Timeline",
        *[f"- **{t['date']}** {t['description']}{cite(t.get('evidence_ids'))}" for t in case.get("timeline", [])],
        "",
        "## Evidence table",
        "| ID | Finding | Value | Comparison | Sources |",
        "|---|---|---|---|---|",
        *[f"| `{e['evidence_id']}` | {e['name']} | {fmt_value(e.get('value'), e.get('name', ''), e.get('unit', ''))} | "
          f"{fmt_value(e.get('comparison_value'), e.get('name', ''), e.get('unit', ''))} {e.get('comparison_label') or ''} | "
          f"{', '.join(s['table'] + '.' + s['column'] for s in e.get('sources', []))} |" for e in case.get("evidence", [])],
        "",
        "## Missing documents",
        *([f"- {m['doc_type'].replace('_', ' ')} ({m.get('claim_count')} claims){' · critical' if m.get('critical') else ''}: {m.get('why')}"
           for m in case.get("missing_documents", [])] or ["- None"]),
        "",
        "## Confidence and limitations",
        f"Evidence strength **{case.get('evidence_strength')}**, confidence **{case.get('confidence')}** "
        f"({case.get('scores', {}).get('methods_agreeing')} detection methods agree).",
        *[f"- {lim}" for lim in case.get("limitations", [])],
        f"- Citation Verifier: {court['verifier']['kept']} statements kept, {court['verifier']['dropped']} unsupported statements removed.",
        "",
        "## Policy and legal references (retrieved, for human review)",
        *[f"- `{r['id']}` **{r['title']}**: {r['text']} *({r['source']}{'; verify against the official text before use' if r['verify'] else ''})*"
          for r in b.get("rules", []) if r["cited"] or r["kind"] == "law"],
        "",
        "## Recommended human-review action",
        b["recommended_action"],
        "",
        "> No automatic denial. No fraud finding. Human approval required for every action.",
    ]
    return "\n".join(lines)
