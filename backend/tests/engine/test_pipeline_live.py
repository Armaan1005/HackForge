"""M3+: pipeline outputs, contract shapes of live responses, planted schemes in cases."""

import json

import pytest

from engine import schemas as S
from engine.config import CONFIG


def load_fixture(name):
    return json.loads((CONFIG.contracts_dir / f"{name}.json").read_text(encoding="utf-8"))


def keys_match(live, fx, path="$"):
    """Same keys as the fixture at every object level (optional fields may be absent)."""
    if isinstance(fx, dict) and isinstance(live, dict):
        model_like = not all(k.isdigit() or k.startswith(("EM", "ORT", "PHY", "EX")) for k in fx)
        if model_like and fx and not any(k in ("attrs", "facts", "params", "service_types", "procedure_codes", "tables",
                                               "exoneration_by_reason", "by_method", "weights", "by_layer", "before",
                                               "after", "details") for k in [path.rsplit(".", 1)[-1]]):
            optional = {"raw_ratio", "peer_p90", "note", "label"}
            missing = set(fx) - set(live) - optional
            extra = set(live) - set(fx) - optional
            assert not missing and not extra, f"{path}: missing {missing}, extra {extra}"
        for k in set(fx) & set(live):
            keys_match(live[k], fx[k], f"{path}.{k}")
    elif isinstance(fx, list) and isinstance(live, list) and fx and live:
        for item in live[:5]:
            keys_match(item, fx[0], f"{path}[]")


def gt_scheme_entities(raw):
    import pandas as pd

    gt = pd.read_csv(raw / "ground_truth.csv", dtype=str, keep_default_na=False)
    return {sid: set(g.entity_id) for sid, g in gt.groupby("scheme_id")}


def test_pipeline_budget_and_layers(processed):
    _, meta = processed
    assert meta["total_ms"] < 30_000
    assert meta["layers"]["rules"] == "ok" and meta["failed_rules"] == []


def test_every_case_validates_and_matches_fixture_keys(processed):
    data_dir, _ = processed
    fx = load_fixture("case_detail")
    files = sorted((data_dir / "processed" / "cases").glob("CASE-*.json"))
    assert files
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        S.CaseDetail.model_validate(doc)
        keys_match(doc, fx)
        assert doc["verdict"]["human_approval_required"] is True
        for ev in doc["evidence"]:
            assert ev["sources"], ev["evidence_id"]
            assert len(ev["claim_ids"]) <= 25
        g = json.loads((data_dir / "processed" / "graphs" / f.name).read_text(encoding="utf-8"))
        S.CaseGraph.model_validate(g)
        assert len(g["nodes"]) <= CONFIG.CASE_GRAPH_NODE_CAP
        ids = {n["id"] for n in g["nodes"]}
        assert all(e["source"] in ids and e["target"] in ids for e in g["edges"])


def test_planted_schemes_appear_in_open_cases(processed, gen):
    data_dir, _ = processed
    schemes = gt_scheme_entities(gen[0])
    in_cases = set()
    for f in (data_dir / "processed" / "cases").glob("CASE-*.json"):
        doc = json.loads(f.read_text(encoding="utf-8"))
        in_cases |= {e["entity_id"] for e in doc["entities"]}
        for ev in doc["evidence"]:
            in_cases |= set(ev["entity_ids"])
    for sid in [f"S{i}" for i in range(1, 9)]:
        assert schemes[sid] & in_cases, f"{sid} not in any case"


def test_live_endpoints(live_api, processed):
    data_dir, _ = processed
    h = live_api.get("/api/health").json()
    assert h["use_fixtures"] is False and h["layers"]["rules"] == "ok"
    ov = live_api.get("/api/overview")
    assert ov.status_code == 200
    S.Overview.model_validate(ov.json())
    keys_match(ov.json(), load_fixture("overview"))
    case_id = sorted(p.stem for p in (data_dir / "processed" / "cases").glob("CASE-*.json"))[0]
    r = live_api.get(f"/api/cases/{case_id}")
    assert r.status_code == 200 and r.json()["case_id"] == case_id
    g = live_api.get(f"/api/cases/{case_id}/graph")
    assert g.status_code == 200
    cl = live_api.get(f"/api/cases/{case_id}/claims?limit=5")
    assert cl.status_code == 200 and len(cl.json()["claims"]) <= 5 and cl.json()["total"] >= 1
    S.CaseClaims.model_validate(cl.json())
    pid = r.json()["entities"][0]["entity_id"]
    if pid.startswith("PRV-"):
        ps = live_api.get(f"/api/entities/{pid}/peer_stats")
        assert ps.status_code == 200
        S.PeerStats.model_validate(ps.json())
    doc_id = r.json()["documents"][0]["document_id"] if r.json()["documents"] else "DOC-00001"
    d = live_api.get(f"/api/documents/{doc_id}")
    assert d.status_code == 200
    S.Document.model_validate(d.json())
    ac = live_api.get("/api/alerts/cleared?limit=3")
    assert ac.status_code == 200
    S.AlertsCleared.model_validate(ac.json())


@pytest.mark.parametrize("path", ["/api/cases/CASE-9999", "/api/cases/CASE-9999/graph", "/api/documents/DOC-99999",
                                  "/api/entities/PRV-99999/peer_stats", "/api/files/scans/DOC-99999.png"])
def test_live_unknown_ids_are_404(live_api, path):
    r = live_api.get(path)
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_live_get_latency(live_api, processed):
    import time

    data_dir, _ = processed
    case_id = sorted(p.stem for p in (data_dir / "processed" / "cases").glob("CASE-*.json"))[0]
    live_api.get(f"/api/cases/{case_id}")
    for path in ["/api/overview", f"/api/cases/{case_id}", f"/api/cases/{case_id}/graph", "/api/alerts/cleared"]:
        t = time.perf_counter()
        assert live_api.get(path).status_code == 200
        assert time.perf_counter() - t < 0.5, path
