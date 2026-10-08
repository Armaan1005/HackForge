import os
import sys
from pathlib import Path

# Tests never call Gemini and always read the contract fixtures.
os.environ["AI_OFFLINE"] = "true"
os.environ["USE_FIXTURES"] = "true"
import tempfile  # noqa: E402
os.environ["LLM_CACHE_DIR"] = tempfile.mkdtemp(prefix="axon-llm-cache-")  # never read real cached answers
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_stats(tmp_path, monkeypatch):
    """Keep verifier counters out of data/state so the Trust panel only counts real runs."""
    from genai import verifier

    monkeypatch.setattr(verifier, "_STATS_PATH", tmp_path / "verifier_stats.json")
