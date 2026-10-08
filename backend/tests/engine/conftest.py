import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


@pytest.fixture
def client(monkeypatch):
    """TestClient in fixture mode."""
    from fastapi.testclient import TestClient

    monkeypatch.setenv("USE_FIXTURES", "true")
    from main import app

    return TestClient(app)


@pytest.fixture
def live_client(monkeypatch):
    """TestClient with USE_FIXTURES=false (live engine)."""
    from fastapi.testclient import TestClient

    monkeypatch.setenv("USE_FIXTURES", "false")
    from main import app

    return TestClient(app)


TABLES = ["owners", "facilities", "providers", "members", "admissions", "referrals", "claims",
          "investigations", "ground_truth", "documents", "ground_truth_documents"]


@pytest.fixture(scope="session")
def gen(tmp_path_factory):
    """Generate seed-42 data once per test session: (out_dir, meta, tables-as-str)."""
    import pandas as pd

    from engine.generate.__main__ import run

    out = tmp_path_factory.mktemp("data") / "raw"
    meta = run(42, 50_000, out, ref_dir=tmp_path_factory.mktemp("ref"))
    t = {name: pd.read_csv(out / f"{name}.csv", dtype=str, keep_default_na=False) for name in TABLES}
    return out, meta, t


@pytest.fixture(scope="session")
def processed(gen):
    """Run the pipeline once on the session data: (data_dir, run_meta)."""
    from engine.config import CONFIG
    from engine.pipeline import run as run_pipeline

    raw = gen[0]
    meta = run_pipeline(CONFIG, raw_dir=raw, out_dir=raw.parent / "processed")
    return raw.parent, meta


@pytest.fixture
def live_api(processed, monkeypatch):
    """TestClient in live mode reading the session's generated + processed data."""
    from fastapi.testclient import TestClient

    from engine.config import CONFIG

    monkeypatch.setenv("USE_FIXTURES", "false")
    monkeypatch.setattr(CONFIG, "data_dir", processed[0])
    from main import app

    return TestClient(app)
