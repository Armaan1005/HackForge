"""M8 Fraud Twin + M9 time machine, decisions/audit, trust."""

import json

from engine import schemas as S


def test_twin_default_and_harden(live_api):
    sc = S.TwinScenarios.model_validate(live_api.get("/api/twin/scenarios").json())
    assert {s.id for s in sc.scenarios} >= {"claim_splitting", "duplicate_billing"}
    r = live_api.post("/api/twin/run", json={"scenario": "claim_splitting", "params": {}, "seed": 7}).json()
    run = S.TwinRun.model_validate(r)
    assert 0.80 <= run.detection_rate <= 0.97 and run.runtime_ms < 20_000
    assert run.missed == 0 or run.miss_reason_summary
    h = S.TwinHarden.model_validate(live_api.post("/api/twin/harden", json={
        "run_id": run.run_id, "change": {"param": "TEMPORAL_WINDOW_DAYS", "new_value": 45}}).json())
    assert h.after.detection_rate >= h.before.detection_rate
    assert h.after.false_positive_rate - h.before.false_positive_rate <= 0.005
    if run.injected_case_ids:
        c = live_api.get(f"/api/twin/runs/{run.run_id}/cases/{run.injected_case_ids[0]}")
        assert c.status_code == 200
        S.CaseDetail.model_validate(c.json())


def test_timemachine_matches_graph(live_api, processed):
    cid = sorted(p.stem for p in (processed[0] / "processed" / "cases").glob("CASE-*.json"))[0]
    tm = S.TimeMachine.model_validate(live_api.get(f"/api/cases/{cid}/timemachine").json())
    g = live_api.get(f"/api/cases/{cid}/graph").json()
    ids = {n["id"] for n in g["nodes"]}
    assert set(tm.snapshots[-1].node_ids) <= ids


def test_decision_audit_reset_trust(live_api, processed):
    cid = sorted(p.stem for p in (processed[0] / "processed" / "cases").glob("CASE-*.json"))[0]
    d = S.DecisionResponse.model_validate(live_api.post(f"/api/cases/{cid}/decision",
                                          json={"action": "hold_payment", "user": "priya"}).json())
    assert d.hold_status == "held"
    assert live_api.get(f"/api/cases/{cid}").json()["payment_clock"]["hold_status"] == "held"
    d2 = live_api.post(f"/api/cases/{cid}/decision", json={"action": "confirm", "user": "priya"}).json()
    assert d2["weight_changes"]
    a = S.Audit.model_validate(live_api.get("/api/audit?limit=5").json())
    assert a.total >= 3
    S.FeedbackReset.model_validate(live_api.post("/api/feedback/reset").json())
    t = S.Trust.model_validate(live_api.get("/api/trust").json())
    assert t.exoneration.planted_fraud_wrongly_cleared == 0
    assert t.decoys.correctly_defended / t.decoys.total >= 0.9
    assert all(s.detected for s in t.detection.by_scheme) and t.ai is None
