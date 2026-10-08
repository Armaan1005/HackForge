"""Harden: rerun the same injection (same seed) with one tunable param changed. Sandbox only."""

from __future__ import annotations

from ..config import CONFIG
from .simulate import execute, load, next_run, save, with_param


def run_harden(run_id: str, param: str, new_value) -> dict:
    parent = load(run_id)
    cfg = with_param(CONFIG, param, new_value)
    n, new_id = next_run()
    res = execute(parent["scenario"], parent["params"], parent["seed"], cfg, n, new_id)
    out = {"run_id": new_id, "parent_run_id": run_id,
           "change": {"param": param, "old_value": getattr(CONFIG, param), "new_value": getattr(cfg, param)},
           "applied_to": "sandbox_only", "approved_by": "analyst"}
    for k in ("scenario", "params", "seed", "runtime_ms", "generated", "detected", "missed", "detection_rate", "by_layer",
              "false_positive_rate"):
        out[k] = res[k]
    out["before"] = {"detection_rate": parent["detection_rate"], "false_positive_rate": parent["false_positive_rate"]["run"]}
    out["after"] = {"detection_rate": res["detection_rate"], "false_positive_rate": res["false_positive_rate"]["run"]}
    for k in ("injected_case_ids", "missed_claims", "miss_reason_summary", "injected_graph", "_views", "_run_no"):
        out[k] = res[k]
    out["limitations"] = ["Change applied in the sandbox only. Applying it to live detection needs a separate human decision."]
    return save(out)
