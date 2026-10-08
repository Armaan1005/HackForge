"""M4 acceptance: anomaly, temporal and graph layers on seed-42 data."""

import warnings

import pandas as pd
import pytest

from engine.config import CONFIG
from engine.detect import anomaly, graph, temporal
from engine.detect.rules import run_rules
from engine.features import build_provider_features
from engine.store import DataStore


@pytest.fixture(scope="module")
def layers(gen):
    warnings.filterwarnings("ignore")
    raw = gen[0]
    s = DataStore(raw)
    f = build_provider_features(s, CONFIG)
    ctx: dict = {"signals": []}
    rs, _ = run_rules(s, CONFIG, f)
    asig = anomaly.run(s, CONFIG, f, ctx)
    tsig = temporal.run(s, CONFIG, f, ctx)
    ctx["signals"] = rs + asig + tsig
    gsig = graph.run(s, CONFIG, f, ctx)
    gt = pd.read_csv(raw / "ground_truth.csv", dtype=str, keep_default_na=False)
    return ctx, asig, tsig, gsig, gt


def ents(gt, sid):
    return set(gt[(gt.scheme_id == sid) & (gt.entity_type == "provider")].entity_id)


def test_anomaly_top_percentiles(layers):
    ctx, _, _, _, gt = layers
    score = ctx["anomaly_score"]
    for sid in ("S3", "S6"):
        assert all(score[p] >= 0.95 for p in ents(gt, sid)), sid


def test_s3_drift_and_d5_region_wide(layers):
    _, _, tsig, _, gt = layers
    drift = [s for s in tsig if s["method"] == "temporal.em5_drift" and s["entity_id"] in ents(gt, "S3")]
    assert drift and 3.0 <= drift[0]["value"] <= 7.0
    wide = {s["entity_id"] for s in tsig if s["method"] == "temporal.burst_region_wide"}
    assert ents(gt, "D5") <= wide


def test_graph_cycle_community_and_d7(layers):
    ctx, _, _, gsig, gt = layers
    cycles = {frozenset(s["entity_ids"]) for s in gsig if s["method"] == "graph.referral_cycle"}
    assert frozenset(ents(gt, "S1")) in cycles
    s6 = ents(gt, "S6")
    assert len({ctx["community_of"][p] for p in s6}) == 1
    small = [s for s in gsig if s["method"] == "graph.small_claims_pattern" and s["entity_id"] in s6]
    assert small and small[0]["extra"]["connected_claims"] >= 40
    d7 = ents(gt, "D7")
    assert len({ctx["community_of"].get(p) for p in d7}) == 1
    flagged_comm = {s["entity_id"] for s in gsig if s["method"] == "graph.louvain_community"}
    assert not (d7 & flagged_comm)
