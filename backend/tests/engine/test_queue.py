"""M6: queue optimizer respects capacity, is fast, matches the contract, has the demo case."""

import json
import time

import pytest

from engine import schemas as S
from engine.config import CONFIG


@pytest.mark.parametrize("cap", [0, 10, 40, 120])
def test_queue_capacity_and_contract(live_api, cap):
    r = live_api.get(f"/api/queue?capacity_hours={cap}&horizon=60")
    assert r.status_code == 200
    q = S.Queue.model_validate(r.json())
    assert q.hours_used <= cap
    assert sum(c.effort_hours for c in q.cases if c.selected) == q.hours_used
    assert [c.rank for c in q.cases] == list(range(1, len(q.cases) + 1))
    assert all(c.status in ("needs_siu_review", "request_documentation") for c in q.cases if c.selected)


def test_queue_latency(live_api):
    live_api.get("/api/queue")
    t = time.perf_counter()
    assert live_api.get("/api/queue?capacity_hours=55&horizon=90").status_code == 200
    assert time.perf_counter() - t < 0.3


def test_high_risk_case_ranked_low_with_reason(live_api):
    q = live_api.get("/api/queue?capacity_hours=40&horizon=30").json()
    low = [c for c in q["cases"] if c["risk"] >= 90 and not c["selected"]]
    assert low and low[0]["selection_reason"].startswith("Not selected")


def test_overview_selected_today_matches_queue(live_api):
    q = live_api.get("/api/queue").json()
    assert live_api.get("/api/overview").json()["funnel"]["selected_today"] == q["selected_count"]
