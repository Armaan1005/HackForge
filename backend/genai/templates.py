"""Deterministic fallbacks. Used when Gemini is off, slow or failing, so the UI never blocks.

They only restate Part A's evidence (whose numbers the verifier already accepts).
"""
from __future__ import annotations

import re

from .evidence import STATUS_LABEL, fmt_value


def _strength(sev: int | None) -> str:
    return "strong" if (sev or 0) >= 4 else "moderate" if (sev or 0) >= 2 else "weak"


def _arg_from_evidence(e: dict) -> dict:
    return {
        "point": e.get("description") or e.get("name", ""),
        "evidence_ids": [e["evidence_id"]],
        "metric": e.get("name", ""),
        "case_value": float(e.get("value") or 0),
        "comparison_value": float(e.get("comparison_value") or 0),
        "comparison_label": e.get("comparison_label") or "",
        "strength": _strength(e.get("severity")),
    }


def _arg_from_peer(p: dict) -> dict:
    g = p.get("peer_group") or {}
    metric = p.get("metric", "")
    point = (f"{metric}: {fmt_value(p.get('case_value'), metric)} vs peer median "
             f"{fmt_value(p.get('peer_median'), metric)} ({g.get('label', 'peers')}, n={g.get('n', '?')})")
    if p.get("note"):
        point += f". {p['note']}"
    return {
        "point": point,
        "evidence_ids": [p["evidence_id"]],
        "metric": metric,
        "case_value": float(p.get("case_value") or 0),
        "comparison_value": float(p.get("peer_median") or 0),
        "comparison_label": f"peer median ({g.get('label', 'peers')}, n={g.get('n', '?')})",
        "strength": "moderate",
    }


def prosecution(case: dict) -> dict:
    ev = sorted((e for e in case.get("evidence", []) if e.get("direction") == "incriminating"),
                key=lambda e: (-(e.get("severity") or 0), -(e.get("weight") or 0)))
    args = [_arg_from_evidence(e) for e in ev[:4]]
    args += [_arg_from_peer(p) for p in case.get("peer_context", []) if p.get("direction") == "incriminating"][:2]
    return {"arguments": args[:5]}


def defense(case: dict) -> dict:
    args = [_arg_from_evidence(e) for e in case.get("evidence", []) if e.get("direction") == "exculpatory"]
    args += [_arg_from_peer(p) for p in case.get("peer_context", []) if p.get("direction") in ("exculpatory", "neutral")]
    missing = [f"{m['doc_type'].replace('_', ' ')} for {m.get('claim_count', '?')} claims: {m.get('why', '')}".strip()
               for m in case.get("missing_documents", [])]
    return {"arguments": args[:5], "missing_evidence": missing}


def verdict_summary(case: dict) -> dict:
    v = case.get("verdict", {})
    status = STATUS_LABEL.get(v.get("status", ""), v.get("status", ""))
    reasons = "; ".join(v.get("reasons", [])[:3])
    text = f"{status}. {reasons}." if reasons else f"{status}."
    if v.get("next_action_text"):
        text += f" Next step: {v['next_action_text']}."
    return {"summary": text, "evidence_ids": []}


def brief(case: dict, prosecution_args: list[dict], defense_args: list[dict]) -> dict:
    ns = case.get("network_summary") or {}
    money = case.get("money") or {}
    v = case.get("verdict", {})
    exec_summary = (
        f"{case.get('title')}. Risk {case.get('scores', {}).get('risk')} with {case.get('evidence_strength')} evidence "
        f"and confidence {case.get('confidence')}. Exposure {fmt_value(money.get('dollars_at_risk'), unit='inr')}, "
        f"of which {fmt_value(money.get('pending'), unit='inr')} is still pending."
    )
    network = (f"The case sits in community {ns.get('community_id', 'n/a')} with {ns.get('community_size', '?')} providers "
               f"and {ns.get('connected_claims', '?')} connected claims; "
               f"{fmt_value(ns.get('flagged_neighbor_share'), 'share')} of linked providers are already flagged.") if ns else "No network context."
    timeline = " ".join(f"{t['date']}: {t['description']}." for t in case.get("timeline", [])[:6])
    return {
        "executive_summary": exec_summary,
        "key_findings": [{"text": a["point"], "evidence_ids": a["evidence_ids"]} for a in prosecution_args],
        "alternative_explanations": [{"text": a["point"], "evidence_ids": a["evidence_ids"]} for a in defense_args],
        "network_context": network,
        "timeline_narrative": timeline,
        "recommended_action": v.get("next_action_text") or STATUS_LABEL.get(v.get("status", ""), ""),
    }


CLEARED_TEMPLATES = {
    "EX1_sole_provider": "Only provider of its type within {nearest_competitor_km} km; volume per 1,000 people ({volume_per_1k_pop}) is inside the peer range.",
    "EX2_case_mix_adjusted": "Patients are sicker than average (case-mix {case_mix_index}); utilization falls from {raw_ratio}x to {adjusted_ratio}x after adjustment, under the {clear_threshold}x flag level.",
    "EX3_corrected_claim": "The apparent duplicate is a corrected claim (frequency code {frequency_code}) replacing {original_claim_id}.",
    "EX4_event_or_seasonal": "Spike matches a region-wide event or seasonal pattern shared by unrelated providers.",
    "EX5_chronic_schedule": "Visit frequency matches a known chronic treatment schedule.",
    "EX6_network_explained": "Shared ownership or referral pattern without any billing anomaly.",
}


def cleared_line(alert: dict) -> str:
    tpl = CLEARED_TEMPLATES.get(alert.get("exoneration_code", ""), "Explained by peer context.")
    try:
        return tpl.format(**alert.get("facts", {}))
    except (KeyError, IndexError):
        return tpl.split(";")[0].split("(")[0].strip().rstrip(",") + "."


# ── Fraud Twin fallbacks ────────────────────────────────────────────────────
_KEYWORDS = [
    ("claim_splitting", r"split|break(ing)? (up|into)|smaller claims|under (the )?threshold|below .*limit"),
    ("referral_collusion", r"referr|collu|kickback|coordinat|ring|loop"),
    ("phantom_services", r"phantom|dead|deceased|died|inpatient|admitted|ambulance|miles|never (happened|received)"),
    ("upcoding_drift", r"upcod|level.?5|em5|higher level|creep|drift"),
    ("identity_cluster", r"identit|fake card|same phone|same address|borrowed|stolen card"),
    ("duplicate_billing", r"duplicat|twice|resubmit|same service again|double bill"),
]
_INR = re.compile(r"(?:₹|rs\.?|inr)\s*(\d[\d,]*(?:\.\d+)?)\s*(lakhs?|lacs?|l|k|cr|crore)?", re.IGNORECASE)
_WORDNUM = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}


def _amounts(text: str) -> list[float]:
    mult = {"l": 1e5, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "k": 1e3, "cr": 1e7, "crore": 1e7}
    return [float(m.group(1).replace(",", "")) * mult.get((m.group(2) or "").lower(), 1) for m in _INR.finditer(text)]


def parse_scenario_keywords(text: str, whitelist: dict) -> dict | None:
    """Fast path: recognise common phrasings without spending a Gemini call."""
    t = text.lower()
    for sid, pat in _KEYWORDS:
        if re.search(pat, t):
            spec = next((s for s in whitelist["scenarios"] if s["id"] == sid), None)
            if not spec:
                return None
            params = {k: v.get("default") for k, v in spec["params"].items()}
            amounts = _amounts(text)
            for word, n in _WORDNUM.items():
                t = re.sub(rf"\b{word}\b", str(n), t)
            if sid == "claim_splitting":
                if amounts:
                    params["parent_amount"] = max(amounts)
                if len(amounts) >= 2 and min(amounts) > 0:
                    params["splits"] = round(max(amounts) / min(amounts))
                m = re.search(r"into (\d+)", t)
                if m:
                    params["splits"] = int(m.group(1))
                m = re.search(r"(\d+) (providers|clinics|hospitals)", t)
                if m:
                    params["providers"] = int(m.group(1))
            elif sid == "referral_collusion":
                m = re.search(r"(\d+) (providers|clinics|doctors|hospitals)", t)
                if m:
                    params["providers"] = int(m.group(1))
                params["shared_owner"] = "owner" in t or "same facility" in t or "one referral facility" in t
            elif sid == "phantom_services":
                params["kind"] = "deceased" if re.search(r"dead|deceased|died", t) else "ambulance_miles" if re.search(r"ambulance|miles", t) else "inpatient"
            elif sid == "identity_cluster":
                m = re.search(r"(\d+) (fake|members|cards|people|identities)", t)
                if m:
                    params["members"] = int(m.group(1))
                params["share"] = "both" if ("phone" in t and "address" in t) else "address" if "address" in t else "phone"
            elif sid == "duplicate_billing":
                m = re.search(r"(\d+) days?", t)
                if m:
                    params["day_offset"] = int(m.group(1))
            return {"scenario": sid, "params": params}
    return None


PARAM_PLAIN = {
    "TEMPORAL_WINDOW_DAYS": "linking window (days)",
    "THRESHOLD_HUG_LOW": "near-the-limit band",
    "THRESHOLD_HUG_SHARE": "share of claims near the limit",
    "DUP_NEAR_DAYS": "duplicate window (days)",
    "REFERRAL_CONCENTRATION": "referral concentration trigger",
    "IDENTITY_SHARE_MIN": "shared-identity trigger",
}


def suggest_hardening(miss_reason_summary: list[dict], tunable: list[dict]) -> dict | None:
    """Pick the param behind the most misses and move it just past the typical missed value."""
    tun = {t["key"]: t for t in tunable}
    for r in sorted(miss_reason_summary, key=lambda r: -r.get("count", 0)):
        t = tun.get(r.get("param_key"))
        if not t:
            continue
        thr, typ = float(r.get("threshold", t["current"])), float(r.get("typical_value", t["current"]))
        target = typ * 1.2 if typ > thr else typ * 0.9
        target = min(max(target, t["min"]), t["max"])
        target = round(target) if float(t["current"]).is_integer() else round(target, 2)
        what = PARAM_PLAIN.get(t["key"], t.get("description", t["key"]).lower())
        return {
            "param": t["key"], "new_value": target,
            "explanation": f"{r.get('count')} missed claims sat around {typ:g} on the {what}, just past today's setting of {thr:g}. "
                           f"Moving it to {target:g} should catch them. Check false alarms after the re-run.",
        }
    return None
