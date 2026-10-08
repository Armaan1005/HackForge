"""M7: forecast per horizon, contract shape, model metrics, case horizon risk."""

import json

import pytest

from engine import schemas as S


@pytest.mark.parametrize("h", [30, 60, 90])
def test_forecast_endpoint(live_api, processed, h):
    case = json.loads(next((processed[0] / "processed" / "cases").glob("CASE-*.json")).read_text(encoding="utf-8"))
    pid = next(e["entity_id"] for e in case["entities"] if e["entity_id"].startswith("PRV-"))
    r = live_api.get(f"/api/forecast/{pid}?horizon={h}")
    assert r.status_code == 200
    f = S.Forecast.model_validate(r.json())
    assert f.horizon == h and f.probability == f.all_horizons[str(h)] and len(f.top_drivers) == 3
    assert f"{h} days" in f.label_definition


def test_model_metrics_and_case_horizon(processed):
    m = json.loads((processed[0] / "processed" / "forecast_metrics.json").read_text(encoding="utf-8"))
    for h in ("30", "60", "90"):
        assert m[h]["auc"] > 0.7 and 0 <= m[h]["brier"] < 0.25 and m[h]["calibration"]
    for p in (processed[0] / "processed" / "cases").glob("CASE-*.json"):
        c = json.loads(p.read_text(encoding="utf-8"))
        assert set(c["horizon_risk"]) == {"30", "60", "90"}
        assert not any("placeholder" in x for x in c["limitations"]) or c["primary_entity"]["entity_type"] != "provider"
