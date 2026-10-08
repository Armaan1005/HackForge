"""python -m engine.pipeline [--seed 42]: run detection end to end and write data/processed/.

Stages: load → features → rules → anomaly → temporal → graph → fuse → exonerate → documents
→ cases → peer context → scoring → forecast → time machine → trust. A detection layer that
errors (or is not built yet) is logged, marked "unavailable" and the run continues.
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import shutil
import time
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from . import ENGINE_VERSION
from . import schemas as S
from .cases import build_cases, case_graph, missing_documents, timeline
from .config import CONFIG, Config
from .detect.rules import run_rules
from .doccheck import document_flags
from .features import build_provider_features
from .fuse import LAYERS, fuse
from .scoring import score_case, serialize_case
from .store import DataStore

log = logging.getLogger("axon.pipeline")

PEER_METRICS = [("em5_share", "EM5 share of E&M visits"), ("band_share", "Threshold-band share"),
                ("claims_per_month", "Claims per month"), ("billed_per_member", "Billed per member (INR)"),
                ("case_mix_index", "Case-mix index (mean member risk score)"), ("distinct_codes", "Distinct procedure codes"),
                ("top_source_share", "Top referral source share")]


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=_json_default) + "\n",
                    encoding="utf-8", newline="\n")


def _json_default(o):
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else round(float(o), 4)
    if isinstance(o, (pd.Timestamp,)):
        return str(o.date())
    raise TypeError(type(o))


def current_weights(cfg: Config) -> dict[str, float]:
    """Method weights: config defaults, overridden by feedback state when present (A16)."""
    path = cfg.state_dir / "weights.json"
    if path.exists():
        try:
            return {**cfg.METHOD_WEIGHTS, **json.loads(path.read_text(encoding="utf-8"))}
        except (ValueError, OSError):
            log.warning("could not read %s; using default weights", path)
    return dict(cfg.METHOD_WEIGHTS)


def peer_stats_table(feats: pd.DataFrame) -> dict[str, dict]:
    out: dict[str, dict] = {}
    grouped = feats.groupby("peer_key")
    stats = {}
    for col, _ in PEER_METRICS:
        med = grouped[col].transform("median")
        p90 = grouped[col].transform(lambda s: s.quantile(0.9))
        pct = grouped[col].rank(pct=True, method="average") * 100
        stats[col] = (med, p90, pct)
    for pid, row in feats.iterrows():
        metrics = []
        for col, label in PEER_METRICS:
            v = row[col]
            if pd.isna(v):
                continue
            med, p90, pct = (x.loc[pid] for x in stats[col])
            metrics.append({"metric": label, "value": round(float(v), 4), "peer_median": round(float(med), 4),
                            "peer_p90": round(float(p90), 4), "percentile": round(float(pct), 1) if pd.notna(pct) else None})
        out[str(pid)] = {"entity_id": str(pid), "peer_group": row.peer_label, "n": int(row.peer_n), "metrics": metrics}
    return out


def optional_layer(name: str):
    """Import engine.detect.<name> if it exists (layers land milestone by milestone)."""
    try:
        return importlib.import_module(f"engine.detect.{name}")
    except ModuleNotFoundError:
        return None


def run(cfg: Config = CONFIG, raw_dir: Path | None = None, out_dir: Path | None = None) -> dict:
    t_all = time.perf_counter()
    durations: dict[str, int] = {}
    out = Path(out_dir or cfg.processed_dir)

    def stage(name: str, t0: float) -> None:
        durations[name] = int((time.perf_counter() - t0) * 1000)

    t = time.perf_counter()
    store = DataStore(raw_dir or cfg.raw_dir)
    _ = store.claims, store.hdr
    feats = build_provider_features(store, cfg)
    stage("load_features", t)

    layers = {m: "unavailable" for m in LAYERS}
    signals: list[dict] = []
    t = time.perf_counter()
    rule_signals, failed = run_rules(store, cfg, feats)
    signals += rule_signals
    layers["rules"] = "ok" if len(failed) < 16 else "unavailable"
    stage("rules", t)
    context: dict = {"feats": feats, "signals": signals}
    for name in ("anomaly", "temporal", "graph"):
        t = time.perf_counter()
        mod = optional_layer(name)
        if mod is None or not hasattr(mod, "run"):
            stage(name, t)
            continue
        try:
            signals += mod.run(store, cfg, feats, context)
            layers[name] = "ok"
        except Exception:  # noqa: BLE001 - fail safe by design
            log.exception("layer %s failed", name)
        stage(name, t)

    t = time.perf_counter()
    weights = current_weights(cfg)
    entities = {k[1]: v for k, v in fuse(signals, layers, weights, cfg.HARD_FLOOR, cfg.HARD_METHOD_BONUS).items()}
    alerts = {e for e, v in entities.items() if v["risk"] >= cfg.ALERT_MIN_RISK}
    stage("fuse", t)

    t = time.perf_counter()
    cleared: list[dict] = []
    exo = None
    try:
        exo = importlib.import_module("engine.exonerate")
    except ModuleNotFoundError:
        pass
    if exo is not None:
        cleared = exo.run(store, cfg, feats, entities, signals, alerts, context)
    open_ids = alerts - {c["entity_id"] for c in cleared}
    stage("exonerate", t)

    t = time.perf_counter()
    flags = document_flags(store)
    stage("documents", t)

    t = time.perf_counter()
    cases = build_cases(store, cfg, entities, signals, open_ids, flags,
                        extra_links=context.get("case_links"), extra_evidence=context.get("case_evidence"))
    stage("cases", t)

    t = time.perf_counter()
    pc_mod = None
    try:
        pc_mod = importlib.import_module("engine.peer_context")
    except ModuleNotFoundError:
        pass
    risk = {e: v["risk"] for e, v in entities.items()}
    if out.exists():
        shutil.rmtree(out)
    case_docs, index = [], []
    for case in cases:
        missing = missing_documents(store, case)
        horizon = context.get("horizon", {}).get(case["primary"])
        sc = score_case(store, cfg, case, layers, missing, horizon)
        graph = case_graph(store, cfg, case, risk)
        network = {"node_count": graph.pop("total_nodes"), "edge_count": graph.pop("total_edges"),
                   "community_id": context.get("community_of", {}).get(case["primary"]),
                   "community_size": context.get("community_size", {}).get(case["primary"], 0),
                   "flagged_neighbor_share": case["flagged_neighbor_share"], "connected_claims": len(case["claim_ids"])}
        peer = pc_mod.build(store, cfg, context.get("feats_full", feats), case, context) if pc_mod else []
        tl = timeline(store, cfg, case, flags)
        doc = serialize_case(store, cfg, case, sc, layers, peer, tl, network, missing)
        S.CaseDetail.model_validate(doc)
        S.CaseGraph.model_validate(graph)
        dump(out / "cases" / f"{case['case_id']}.json", doc)
        dump(out / "graphs" / f"{case['case_id']}.json", graph)
        rows = store.claims[store.claims.claim_id.isin(case["claim_ids"])]
        dump(out / "claims" / f"{case['case_id']}.json",
             json.loads(rows.astype(object).where(rows.notna(), None).to_json(orient="records", date_format="iso")))
        case_docs.append(doc)
        index.append({"case_id": case["case_id"], "primary": case["primary"], "providers": case["providers"],
                      "entities": sorted(case["entities_risk"]), "claim_ids": case["claim_ids"]})
    stage("scoring", t)

    t = time.perf_counter()
    dump(out / "cases_index.json", index)
    if "anomaly_model" in context:  # fitted once on the baseline; Fraud Twin reuses it
        import joblib

        joblib.dump({"model": context["anomaly_model"], "cols": context["anomaly_cols"]}, out / "anomaly_model.joblib")
    dump(out / "peer_stats.json", peer_stats_table(feats))
    dump(out / "entities.json", {e: {k: v[k] for k in ("entity_type", "risk", "by_method", "methods_agreeing", "hard")}
                                 for e, v in sorted(entities.items())})
    dump(out / "alerts_cleared.json", {"total": len(cleared), "items": cleared})
    exo_counts = {k: 0 for k in ("EX1_sole_provider", "EX2_case_mix_adjusted", "EX3_corrected_claim",
                                 "EX4_event_or_seasonal", "EX5_chronic_schedule", "EX6_network_explained")}
    for c in cleared:
        exo_counts[c["exoneration_code"]] = exo_counts.get(c["exoneration_code"], 0) + 1
    tables = {"claims": int(len(store.claims)), "providers": int(len(store.providers)), "members": int(len(store.members)),
              "facilities": int(len(store.facilities)), "owners": int(len(store.owners)),
              "referrals": int(len(store.referrals)), "admissions": int(len(store.admissions)),
              "investigations": int(len(store.investigations)), "documents": int(len(store.documents))}
    overview = {
        "synthetic": True, "seed": cfg.seed, "sim_today": str(cfg.sim_today),
        "date_range": {"start": str(cfg.history_start), "end": str(cfg.sim_today - timedelta(days=1))},
        "currency": "INR", "tables": tables,
        "service_types": {k: int(v) for k, v in store.claims.service_type.value_counts().items()},
        "funnel": {"claim_lines": tables["claims"], "alerts": len(alerts), "explained": len(cleared),
                   "open_alerts": len(open_ids), "cases": len(cases), "selected_today": 0, "capacity_hours": 40},
        "exoneration_by_reason": exo_counts, "layers": layers, "engine_version": ENGINE_VERSION,
        "generated_at": f"{cfg.sim_today}T08:00:00",
    }
    S.Overview.model_validate(overview)
    dump(out / "overview.json", overview)
    stage("write", t)
    meta = {"seed": cfg.seed, "engine_version": ENGINE_VERSION, "layers": layers, "failed_rules": failed,
            "durations_ms": durations, "total_ms": int((time.perf_counter() - t_all) * 1000),
            "counts": {"signals": len(signals), "alerts": len(alerts), "cleared": len(cleared), "open_alerts": len(open_ids),
                       "cases": len(cases)}}
    dump(out / "run_meta.json", meta)
    return meta


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(prog="python -m engine.pipeline")
    ap.add_argument("--seed", type=int, default=CONFIG.seed)
    args = ap.parse_args(argv)
    CONFIG.seed = args.seed
    print(json.dumps(run(CONFIG), indent=2))


if __name__ == "__main__":
    main()
