"""End-to-end over /api/ai with Gemini disabled: every agent must fall back to grounded templates."""
import json

from fastapi.testclient import TestClient

from genai.engine_client import fixture
from genai.templates import parse_scenario_keywords, suggest_hardening
from main import app


def client():
    return TestClient(app)


def test_court_is_grounded_and_keeps_code_status():
    with client() as c:
        r = c.post("/api/ai/court/CASE-0001").json()
    assert r["verdict"]["status"] == fixture("case_detail")["verdict"]["status"]
    assert r["verdict"]["human_approval_required"] is True
    assert r["prosecution"]["arguments"] and r["defense"]["arguments"]
    assert r["verifier"]["dropped"] == 0
    assert all(a["evidence_ids"] for a in r["prosecution"]["arguments"] + r["defense"]["arguments"])


def test_court_stream_sends_each_side_then_the_full_result():
    with client() as c:
        lines = [json.loads(x) for x in c.post("/api/ai/court/CASE-0001/stream?refresh=true").text.splitlines() if x]
    sides = [e for e in lines if e["event"] == "side"]
    assert {e["side"] for e in sides} == {"prosecution", "defense"}
    assert all(e["arguments"] and all(a["evidence_ids"] for a in e["arguments"]) for e in sides)
    assert lines[-1]["event"] == "done"
    done = lines[-1]["court"]
    assert done["verdict"]["human_approval_required"] is True
    by_side = {e["side"]: e["arguments"] for e in sides}
    assert by_side["prosecution"] == done["prosecution"]["arguments"] and by_side["defense"] == done["defense"]["arguments"]


def test_unknown_case_uses_sample_in_fixture_mode():
    with client() as c:
        r = c.post("/api/ai/court/CASE-0099")
    assert r.status_code == 200 and r.json()["case_id"] == "CASE-0099"


def test_brief_markdown_has_required_sections():
    with client() as c:
        md = c.get("/api/ai/brief/CASE-0001?format=md").text
    for heading in ("## Key findings", "## Alternative explanations", "## Timeline", "## Evidence table",
                    "## Confidence and limitations", "## Recommended human-review action"):
        assert heading in md
    assert "Human approval required" in md


def test_forensics_catches_planted_tampering():
    with client() as c:
        r = c.post("/api/ai/forensics/CASE-0001").json()
    assert r["injection_detected"] is True and r["affects_score"] is False
    checks = {(f["section_id"], f["check"]) for f in r["documents"][0]["integrity_flags"]}
    assert ("S4", "prompt_injection") in checks
    assert ("S3", "timeline_conflict") in checks
    assert ("S3", "unlinked_author") in checks


def test_scenario_parser_keywords_and_bounds():
    wl = fixture("twin_scenarios")
    p = parse_scenario_keywords("What if fraudsters split ₹2 lakh claims into four ₹50,000 claims?", wl)
    assert p["scenario"] == "claim_splitting" and p["params"]["parent_amount"] == 200000 and p["params"]["splits"] == 4
    with client() as c:
        clamped = c.post("/api/ai/twin/parse", json={"text": "split ₹50 crore claims into 400 pieces"}).json()
        unsupported = c.post("/api/ai/twin/parse", json={"text": "what if aliens bill us"}).json()
    assert clamped["supported"] and clamped["params"]["splits"] == 10 and clamped["adjustments"]
    assert unsupported["supported"] is False


def test_hardening_suggestion_stays_in_bounds():
    run = fixture("twin_run")
    tun = fixture("twin_scenarios")["tunable_params"]
    s = suggest_hardening(run["miss_reason_summary"], tun)
    t = next(x for x in tun if x["key"] == s["param"])
    assert s["param"] == "TEMPORAL_WINDOW_DAYS" and t["min"] <= s["new_value"] <= t["max"] and s["new_value"] > 38
    with client() as c:
        r = c.post("/api/ai/twin/advise", json={"run": run}).json()
    assert r["requires_approval"] is True


def test_cleared_explanations_use_only_facts():
    with client() as c:
        items = c.post("/api/ai/explain_cleared", json={"limit": 3}).json()["items"]
    assert len(items) == 3
    assert "78.4" in json.dumps(items)  # EX1 nearest competitor distance comes straight from the facts
