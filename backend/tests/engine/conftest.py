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
