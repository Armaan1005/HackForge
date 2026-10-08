"""Fraud Twin helpers: Scenario Parser (text -> whitelisted params) and Hardening Advisor."""
from __future__ import annotations

import json

from .. import prompts, templates
from ..gateway import LIVE, AIUnavailable, gateway
from ..schemas import HardeningOut, ScenarioOut


def _coerce(spec: dict, raw: dict) -> tuple[dict, list[str]]:
    """Validate params against the whitelist: cast types, clamp to bounds, drop unknowns."""
    params, notes = {}, []
    for name, rule in spec["params"].items():
        v = raw.get(name, rule.get("default"))
        try:
            if rule["type"] == "int":
                v = int(round(float(v)))
            elif rule["type"] == "float":
                v = float(v)
            elif rule["type"] == "bool":
                v = v if isinstance(v, bool) else str(v).strip().lower() in {"true", "yes", "1"}
            elif rule["type"] == "enum" and v not in rule["values"]:
                notes.append(f"{name}: '{v}' not allowed, using {rule['default']}")
                v = rule["default"]
        except (TypeError, ValueError):
            notes.append(f"{name}: could not read '{v}', using {rule.get('default')}")
            v = rule.get("default")
        if rule["type"] in ("int", "float"):
            lo, hi = rule["min"], rule["max"]
            if v < lo or v > hi:
                notes.append(f"{name} {v} outside {lo}–{hi}, clamped")
                v = min(max(v, lo), hi)
        params[name] = v
    unknown = set(raw) - set(spec["params"])
    if unknown:
        notes.append(f"ignored unknown params: {', '.join(sorted(unknown))}")
    return params, notes


async def parse_scenario(text: str, whitelist: dict, priority: int = LIVE) -> dict:
    text = (text or "").strip()[:600]
    if not text:
        return {"supported": False, "reason": "Describe a scheme, e.g. “What if they split ₹2 lakh claims into four?”", "source": "none"}

    fast = templates.parse_scenario_keywords(text, whitelist)
    source, reason = "keywords", None
    if fast is None:
        try:
            out = await gateway.run("scenario_parser", prompts.SCENARIO.format(
                whitelist=json.dumps(whitelist["scenarios"], ensure_ascii=False), text=text), ScenarioOut, system=prompts.BASE, priority=priority)
            if not out.supported or out.scenario not in {s["id"] for s in whitelist["scenarios"]}:
                return {"supported": False, "reason": out.reason or "No whitelisted scenario matches.", "source": "llm"}
            fast = {"scenario": out.scenario, "params": {p.name: p.value for p in out.params}}
            source, reason = "llm", out.reason
        except AIUnavailable as e:
            return {"supported": False, "source": "keywords",
                    "reason": f"Couldn't match that to a supported scenario (AI parser unavailable: {e}). Try wording like “split claims”, “referral ring”, “billing after death”."}

    spec = next(s for s in whitelist["scenarios"] if s["id"] == fast["scenario"])
    params, notes = _coerce(spec, fast["params"])
    return {"supported": True, "scenario": spec["id"], "scenario_name": spec["name"], "params": params,
            "adjustments": notes, "source": source, "reason": reason}


async def advise_hardening(run: dict, tunable: list[dict], priority: int = LIVE) -> dict:
    fallback = templates.suggest_hardening(run.get("miss_reason_summary", []), tunable)
    tun = {t["key"]: t for t in tunable}
    try:
        out = await gateway.run("hardening_advisor", prompts.HARDENING.format(
            misses=json.dumps(run.get("miss_reason_summary", []), ensure_ascii=False),
            tunable=json.dumps(tunable, ensure_ascii=False),
            detection=json.dumps({k: run.get(k) for k in ("detection_rate", "false_positive_rate", "missed")}, ensure_ascii=False),
        ), HardeningOut, system=prompts.BASE, priority=priority)
        t = tun.get(out.param)
        if t is None or not (t["min"] <= out.new_value <= t["max"]):
            raise AIUnavailable(f"advisor proposed an invalid change ({out.param}={out.new_value})")
        value = int(out.new_value) if float(t["current"]).is_integer() else out.new_value
        return {"suggested_change": {"param": out.param, "old_value": t["current"], "new_value": value},
                "explanation": out.explanation, "source": "llm", "requires_approval": True}
    except AIUnavailable as e:
        if fallback is None:
            return {"suggested_change": None, "explanation": "No tunable parameter explains these misses.", "source": "template", "note": str(e)}
        return {"suggested_change": {"param": fallback["param"], "old_value": tun[fallback["param"]]["current"], "new_value": fallback["new_value"]},
                "explanation": fallback["explanation"], "source": "template", "note": str(e), "requires_approval": True}
