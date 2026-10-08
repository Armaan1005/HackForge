"""M0 contract tests: fixtures validate, fixture mode serves them unchanged, errors are shaped."""

import json

import pytest
from pydantic import ValidationError

from engine import schemas as S
from engine.config import CONFIG


def load(name):
    return json.loads((CONFIG.contracts_dir / f"{name}.json").read_text(encoding="utf-8"))


def test_every_fixture_has_a_model():
    on_disk = {p.stem for p in CONFIG.contracts_dir.glob("*.json")}
    assert on_disk == set(S.FIXTURE_MODELS)


@pytest.mark.parametrize("name", sorted(S.FIXTURE_MODELS))
def test_fixture_validates(name):
    S.FIXTURE_MODELS[name].model_validate(load(name))


def test_schema_rejects_unknown_key():
    data = load("overview")
    data["surprise"] = 1
    with pytest.raises(ValidationError):
        S.Overview.model_validate(data)


GET_FIXTURES = {
    "/api/overview": "overview",
    "/api/alerts/cleared?limit=3&offset=0": "alerts_cleared",
    "/api/queue?capacity_hours=40&horizon=30": "queue",
    "/api/cases/CASE-0001": "case_detail",
    "/api/cases/CASE-0001/graph": "case_graph",
    "/api/cases/CASE-0001/timemachine": "timemachine",
    "/api/forecast/PRV-00412?horizon=30": "forecast",
    "/api/documents/DOC-00031": "document",
    "/api/twin/scenarios": "twin_scenarios",
    "/api/twin/runs/TWIN-20261001-0007/cases/CASE-T007-01": "case_detail",
    "/api/trust": "trust",
    "/api/audit?limit=10": "audit",
}


@pytest.mark.parametrize("path,name", sorted(GET_FIXTURES.items()))
def test_get_serves_fixture_unchanged(client, path, name):
    r = client.get(path)
    assert r.status_code == 200, r.text
    assert r.json() == load(name)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = S.Health.model_validate(r.json())
    assert body.use_fixtures is True


def test_decision_returns_fixture_response(client):
    fx = load("decision")
    r = client.post("/api/cases/CASE-0001/decision", json=fx["request_example"])
    assert r.status_code == 200
    assert r.json() == fx["response"]


def test_twin_run_and_harden(client):
    r = client.post("/api/twin/run", json={"scenario": "claim_splitting", "params": {"splits": 4}, "seed": 7})
    assert r.status_code == 200 and r.json() == load("twin_run")
    r = client.post(
        "/api/twin/harden",
        json={"run_id": "TWIN-20261001-0007", "change": {"param": "TEMPORAL_WINDOW_DAYS", "new_value": 45}},
    )
    assert r.status_code == 200 and r.json() == load("twin_harden")


def test_derived_endpoints_match_schemas(client):
    S.CaseClaims.model_validate(client.get("/api/cases/CASE-0001/claims").json())
    S.PeerStats.model_validate(client.get("/api/entities/PRV-00412/peer_stats").json())
    nb = S.Neighbors.model_validate(client.get("/api/entities/OWN-00233/neighbors?depth=1").json())
    assert {"PRV-00412", "PRV-00413", "PRV-00419", "BNK-7f3a"} <= {n.id for n in nb.nodes}
    deeper = client.get("/api/entities/OWN-00233/neighbors?depth=2").json()
    assert len(deeper["nodes"]) > len(nb.nodes)
    S.FeedbackReset.model_validate(client.post("/api/feedback/reset").json())
    png = client.get("/api/files/scans/DOC-00032.png")
    assert png.status_code == 200 and png.headers["content-type"] == "image/png"
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"


def assert_error(r, status, code):
    assert r.status_code == status, r.text
    body = S.ErrorResponse.model_validate(r.json())
    assert body.error.code == code


@pytest.mark.parametrize(
    "method,path,payload,status,code",
    [
        ("get", "/api/queue?horizon=45", None, 422, "invalid_param"),
        ("get", "/api/queue?capacity_hours=abc", None, 422, "invalid_param"),
        ("get", "/api/forecast/PRV-00412?horizon=7", None, 422, "invalid_param"),
        ("get", "/api/entities/PRV-99999/neighbors", None, 404, "not_found"),
        ("get", "/api/entities/OWN-00233/neighbors?depth=3", None, 422, "invalid_param"),
        ("get", "/api/no/such/route", None, 404, "not_found"),
        ("post", "/api/cases/CASE-0001/decision", {"action": "auto_deny", "user": "x"}, 422, "invalid_param"),
        ("post", "/api/twin/run", {"scenario": "bitcoin_heist"}, 422, "unsupported_scenario"),
        ("post", "/api/twin/run", {"scenario": "claim_splitting", "params": {"splits": 99}}, 422, "invalid_param"),
        ("post", "/api/twin/run", {"scenario": "claim_splitting", "params": {"nope": 1}}, 422, "invalid_param"),
        ("post", "/api/twin/harden", {"run_id": "R", "change": {"param": "SEED", "new_value": 1}}, 422, "invalid_param"),
        ("post", "/api/twin/harden", {"run_id": "R", "change": {"param": "TEMPORAL_WINDOW_DAYS", "new_value": 400}}, 422, "invalid_param"),
    ],
)
def test_errors_are_contract_shaped(client, method, path, payload, status, code):
    r = getattr(client, method)(path, json=payload) if payload is not None else getattr(client, method)(path)
    assert_error(r, status, code)


def test_live_mode_is_honest_until_engine_exists(live_client):
    h = live_client.get("/api/health").json()
    assert h["use_fixtures"] is False
    assert set(h["layers"].values()) == {"unavailable"}
    assert_error(live_client.get("/api/cases/CASE-0001"), 503, "layer_unavailable")
    assert_error(live_client.get("/api/overview"), 503, "layer_unavailable")
