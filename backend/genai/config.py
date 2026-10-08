"""Part B settings, read once from the environment (backend/.env)."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    api_key: str = os.environ.get("GEMINI_API_KEY", "").strip()
    model: str = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    max_concurrent: int = int(os.environ.get("LLM_MAX_CONCURRENT", 2))
    rpm: int = int(os.environ.get("LLM_RPM", 8))
    timeout_s: float = float(os.environ.get("LLM_TIMEOUT_S", 25))
    # true -> never call Gemini, always use deterministic templates (tests, offline demos)
    ai_offline: bool = _bool("AI_OFFLINE", False)
    use_fixtures: bool = _bool("USE_FIXTURES", True)
    engine_url: str = os.environ.get("ENGINE_URL", "http://127.0.0.1:8000").rstrip("/")
    contracts_dir: Path = REPO_DIR / "contracts"
    cache_dir: Path = REPO_DIR / "data" / "llm_cache"
    state_dir: Path = REPO_DIR / "data" / "state"

    @property
    def ai_enabled(self) -> bool:
        return bool(self.api_key) and not self.ai_offline


settings = Settings()
