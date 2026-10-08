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
    # free tier allows 5 requests/minute per model: stay under it, and fall back across models
    rpm: int = int(os.environ.get("LLM_RPM", 4))
    fallback_models: tuple[str, ...] = tuple(m.strip() for m in os.environ.get(
        "GEMINI_FALLBACK_MODELS", "gemini-3.7-flash,gemini-3.6-flash,gemini-3.5-flash-lite").split(",") if m.strip())
    timeout_s: float = float(os.environ.get("LLM_TIMEOUT_S", 25))
    # local Ollama: OLLAMA_MODEL=qwen2.5:7b adds "ollama/qwen2.5:7b" as the last link of the chain;
    # GEMINI_MODEL=ollama/qwen2.5:7b makes it the main model (fully offline, no key needed)
    ollama_model: str = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b").strip()  # set empty to disable
    ollama_url: str = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    ollama_num_ctx: int = int(os.environ.get("OLLAMA_NUM_CTX", 8192))  # fits a 6 GB GPU with the 3B model
    ollama_timeout_s: float = float(os.environ.get("OLLAMA_TIMEOUT_S", 120))
    # true -> never call Gemini, always use deterministic templates (tests, offline demos)
    ai_offline: bool = _bool("AI_OFFLINE", False)
    use_fixtures: bool = _bool("USE_FIXTURES", True)
    engine_url: str = os.environ.get("ENGINE_URL", "http://127.0.0.1:8000").rstrip("/")
    contracts_dir: Path = REPO_DIR / "contracts"
    cache_dir: Path = REPO_DIR / "data" / "llm_cache"
    state_dir: Path = REPO_DIR / "data" / "state"

    @property
    def ai_enabled(self) -> bool:
        uses_ollama = bool(self.ollama_model) or self.model.startswith("ollama/")
        return (bool(self.api_key) or uses_ollama) and not self.ai_offline


settings = Settings()
