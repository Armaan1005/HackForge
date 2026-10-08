"""Sandbox run + evaluation (spec A15). Never touches data/processed."""

from __future__ import annotations

import dataclasses
import json
import time
from collections import Counter

import joblib

from ..cases import build_cases, case_graph, missing_documents, timeline
from ..config import CONFIG, Config
from ..pipeline import detect, flagged_claims
from ..scoring import score_case, serialize_case
from ..store import DataStore
from .scenarios import inject

LIMIT = "We designed both the attack and the detector, so these results are optimistic. Red-team investigators should write real scenarios."
_BASE: dict = {}


def runs_dir():
    d = CONFIG.state_dir / "twin_runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def baseline() -> dict:
    meta = CONFIG.processed_dir / "run_meta.json"
    key = (str(CONFIG.raw_dir), meta.stat().st_mtime)
    if _BASE.get("key") != key:
        s = DataStore(CONFIG.raw_dir)
        flagged = set(json.loads((CONFIG.processed_dir / "flagged_claims.json").read_text(encoding="utf-8")))
        idx = json.loads((CONFIG.processed_dir / "cases_index.json").read_text(encoding="utf-8"))
        flagged |= {c for x in idx for c in x["claim_ids"]}
        model = joblib.load(CONFIG.processed_dir / "anomaly_model.joblib")["model"]
        _BASE.update(key=key, store=s, flagged=flagged, model=model, n_claims=int(s.claims.claim_id.nunique()))
    return _BASE


def miss_reason(scenario: str, cid: str, meta: dict, cfg: Config, sb: DataStore, d: dict) -> dict:
    h = sb.hdr.set_index("claim_id").loc[cid]
    pid, risk = h.provider_id, d["entities"].get(h.provider_id, {}).get("risk", 0)
    feats = d["feats"]
    if scenario == "claim_splitting":
        span = meta["span"].get(cid, 0)
        if span > cfg.TEMPORAL_WINDOW_DAYS:
            return {"reason_code": "TEMPORAL_WINDOW", "param_key": "TEMPORAL_WINDOW_DAYS", "threshold": cfg.TEMPORAL_WINDOW_DAYS, "value": span,
                    "description": f"Linked claims spread over {span} days, beyond the {cfg.TEMPORAL_WINDOW_DAYS}-day linking window"}
        share = float(feats.loc[pid, "band_share"]) if pid in feats.index else 0.0
        if share < cfg.THRESHOLD_HUG_SHARE:
            return {"reason_code": "BELOW_HUG_SHARE", "param_key": "THRESHOLD_HUG_SHARE", "threshold": cfg.THRESHOLD_HUG_SHARE,
                    "value": round(share, 2), "description": f"Provider's share of claims in the band was {share:.0%}, under the {cfg.THRESHOLD_HUG_SHARE:.0%} flag level"}
        if h.billed < cfg.THRESHOLD_HUG_LOW * cfg.review_threshold_inr:
            v = round(h.billed / cfg.review_threshold_inr, 2)
            return {"reason_code": "BELOW_HUG_LOW", "param_key": "THRESHOLD_HUG_LOW", "threshold": cfg.THRESHOLD_HUG_LOW, "value": v,
                    "description": f"Claim at {v:.0%} of the threshold, below the {cfg.THRESHOLD_HUG_LOW:.0%} band edge"}
    if scenario == "duplicate_billing" and meta.get("day_offset", 0) > cfg.DUP_NEAR_DAYS:
        return {"reason_code": "NEAR_DUP_DAYS", "param_key": "DUP_NEAR_DAYS", "threshold": cfg.DUP_NEAR_DAYS, "value": meta["day_offset"],
                "description": f"Resubmitted {meta['day_offset']} days later, beyond the {cfg.DUP_NEAR_DAYS}-day near-duplicate window"}
    if scenario == "identity_cluster" and meta["params"]["members"] < cfg.IDENTITY_SHARE_MIN:
        return {"reason_code": "BELOW_IDENTITY_MIN", "param_key": "IDENTITY_SHARE_MIN", "threshold": cfg.IDENTITY_SHARE_MIN,
                "value": meta["params"]["members"], "description": "Too few members share the contact detail to flag"}
    if scenario == "referral_collusion":
        sh = float(feats.loc[pid, "top_source_share"]) if pid in feats.index else 0.0
        if sh < cfg.REFERRAL_CONCENTRATION:
            return {"reason_code": "BELOW_REFERRAL_CONCENTRATION", "param_key": "REFERRAL_CONCENTRATION", "threshold": cfg.REFERRAL_CONCENTRATION,
                    "value": round(sh, 2), "description": f"Top referral source share {sh:.0%} under the {cfg.REFERRAL_CONCENTRATION:.0%} flag level"}
    return {"reason_code": "SCORE_BELOW_ALERT", "param_key": "ALERT_MIN_RISK", "threshold": cfg.ALERT_MIN_RISK, "value": risk,
            "description": f"Provider risk {risk} stayed under the alert level {cfg.ALERT_MIN_RISK}"}


def execute(scenario: str, params: dict, seed: int, cfg: Config, run_no: int, run_id: str) -> dict:
    t0 = time.perf_counter()
    b = baseline()
    frames, injected, meta = inject(scenario, params, b["store"], cfg, seed, run_no)
    sb = b["store"].with_rows(frames)
    d = detect(sb, cfg, context={"anomaly_model_fixed": b["model"]})
    flagged = flagged_claims(d["signals"], d["entities"], d["open_ids"], cfg)
    cases = build_cases(sb, cfg, d["entities"], d["signals"], d["open_ids"], {}, d["context"].get("case_links"),
                        d["context"].get("case_evidence"))
    case_claims = {c for x in cases for c in x["claim_ids"]}
    caught = flagged | case_claims
    inj = set(injected)
    detected = inj & caught
    by_layer = {}
    for layer in ("rules", "anomaly", "temporal", "graph"):
        ids = set()
        for s in d["signals"]:
            if s["layer"] == layer and s["direction"] == "incriminating" and s["entity_id"] in d["open_ids"]:
                ids.update(s["claim_ids"])
        by_layer[layer] = len(ids & inj)
    clean_total = int(sb.claims.claim_id.nunique()) - len(inj)
    fp_run = round(len(caught - inj) / max(1, clean_total), 3)
    fp_base = round(len(b["flagged"]) / max(1, b["n_claims"]), 3)
    missed = sorted(inj - detected)
    reasons = [{"claim_id": c, **miss_reason(scenario, c, meta, cfg, sb, d)} for c in missed]
    summary = {}
    for r in reasons:
        k = (r["reason_code"], r["param_key"])
        e = summary.setdefault(k, {"reason_code": k[0], "param_key": k[1], "count": 0, "threshold": r["threshold"], "vals": []})
        e["count"] += 1
        e["vals"].append(r["value"])
    miss_summary = [{**{k: v for k, v in e.items() if k != "vals"}, "typical_value": round(sorted(e["vals"])[len(e["vals"]) // 2], 2)}
                    for e in sorted(summary.values(), key=lambda e: -e["count"])]
    inj_cases, views = [], {}
    risk = {e: v["risk"] for e, v in d["entities"].items()}
    k = 0
    for c in cases:
        if not set(c["claim_ids"]) & inj:
            continue
        k += 1
        c["case_id"] = f"CASE-T{run_no:03d}-{k:02d}"
        miss = missing_documents(sb, c)
        sc = score_case(sb, cfg, c, d["layers"], miss, None)
        g = case_graph(sb, cfg, c, risk)
        net = {"node_count": g["total_nodes"], "edge_count": g["total_edges"], "community_id": d["context"].get("community_of", {}).get(c["primary"]),
               "community_size": d["context"].get("community_size", {}).get(c["primary"], 0),
               "flagged_neighbor_share": c["flagged_neighbor_share"], "connected_claims": len(c["claim_ids"])}
        doc = serialize_case(sb, cfg, c, sc, d["layers"], [], timeline(sb, cfg, c, {}), net, miss)
        doc["limitations"].append("Sandbox case from a Fraud Twin run; injected data is synthetic and not part of live detection.")
        views[c["case_id"]] = doc
        inj_cases.append(c["case_id"])
    nodes, edges = [], []
    for pid in meta["providers"]:
        r = risk.get(pid, 0)
        nodes.append({"id": pid, "type": "provider", "label": pid.replace("PRV-", "Injected "), "risk": r, "flagged": r >= cfg.ALERT_MIN_RISK,
                      "in_case": any(pid in views[x]["entities"].__str__() for x in views), "first_seen_month": str(cfg.sim_today)[:7],
                      "attrs": {"injected": True}})
    provs = meta["providers"]
    for i in range(1, len(provs)):
        edges.append({"id": f"TE-{i}", "source": provs[i - 1], "target": provs[i], "type": "referral" if scenario == "referral_collusion" else "owned_by",
                      "weight": 1, "first_seen_month": str(cfg.sim_today)[:7], "evidence_ids": []})
    gen = len(inj)
    return {
        "run_id": run_id, "scenario": scenario, "params": meta["params"], "seed": seed,
        "runtime_ms": int((time.perf_counter() - t0) * 1000), "sandbox": True, "generated": gen, "detected": len(detected),
        "missed": len(missed), "detection_rate": round(len(detected) / gen, 3) if gen else 0.0, "by_layer": by_layer,
        "false_positive_rate": {"baseline": fp_base, "run": fp_run}, "injected_case_ids": inj_cases,
        "missed_claims": reasons[:25], "miss_reason_summary": miss_summary,
        "injected_graph": {"nodes": nodes, "edges": edges}, "limitations": [LIMIT], "_views": views, "_run_no": run_no,
    }


def next_run() -> tuple[int, str]:
    n = len(list(runs_dir().glob("TWIN-*.json"))) + 1
    return n, f"TWIN-{CONFIG.sim_today.strftime('%Y%m%d')}-{n:04d}"


def save(res: dict) -> dict:
    (runs_dir() / f"{res['run_id']}.json").write_text(json.dumps(res, ensure_ascii=False, default=str), encoding="utf-8")
    try:
        from ..audit import log_event

        log_event("analyst", "twin.run" if "change" not in res else "twin.harden", None,
                  {"detection_rate": res.get("before", {}).get("detection_rate")} if "change" in res else None,
                  {"detection_rate": res["detection_rate"]}, {"run_id": res["run_id"], "scenario": res["scenario"]})
    except ModuleNotFoundError:
        pass
    return {k: v for k, v in res.items() if not k.startswith("_")}


def run_scenario(scenario: str, params: dict, seed: int, cfg: Config = CONFIG) -> dict:
    n, run_id = next_run()
    return save(execute(scenario, params, seed, cfg, n, run_id))


def load(run_id: str) -> dict:
    p = runs_dir() / f"{run_id}.json"
    if not p.is_file():
        raise KeyError(run_id)
    return json.loads(p.read_text(encoding="utf-8"))


def sandbox_case(run_id: str, case_id: str) -> dict:
    v = load(run_id)["_views"]
    if case_id not in v:
        raise KeyError(case_id)
    return v[case_id]


def with_param(cfg: Config, key: str, value) -> Config:
    cur = getattr(cfg, key)
    return dataclasses.replace(cfg, **{key: type(cur)(value)})


__all__ = ["run_scenario", "sandbox_case", "execute", "with_param", "Counter"]
