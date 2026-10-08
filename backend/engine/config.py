"""Engine configuration: paths, switches and every detection threshold (spec section 3).

Anything Fraud Twin hardening can tune must live here. Values can be overridden from the
environment (backend/.env is loaded by main.py via python-dotenv, never read here directly).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_path(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    if not raw:
        return default
    p = Path(raw)
    return p if p.is_absolute() else (BACKEND_DIR / p).resolve()


@dataclass
class Config:
    # paths
    contracts_dir: Path = REPO_DIR / "contracts"
    data_dir: Path = field(default_factory=lambda: _env_path("DATA_DIR", REPO_DIR / "data"))

    # switches
    seed: int = field(default_factory=lambda: int(os.getenv("SEED", "42")))
    sim_today: date = field(default_factory=lambda: date.fromisoformat(os.getenv("SIM_TODAY", "2026-10-01")))
    history_start: date = date(2025, 4, 1)
    review_threshold_inr: int = 50_000

    # rules
    DUP_NEAR_DAYS: int = 1
    DUP_NEAR_AMOUNT_PCT: float = 0.05
    UPCODE_P90_MULT: float = 1.0
    UPCODE_MEDIAN_MULT: float = 2.0
    MAX_PROVIDER_MINUTES_PER_DAY: int = 24 * 60
    WARN_PROVIDER_MINUTES_PER_DAY: int = 16 * 60
    IMPOSSIBLE_TRAVEL_KM: int = 300
    AMBULANCE_MILES_RATIO: float = 1.5
    AMBULANCE_MILES_SLACK: int = 5
    THRESHOLD_HUG_LOW: float = 0.80
    THRESHOLD_HUG_SHARE: float = 0.35
    EARLY_REFILL_FRACTION: float = 0.75
    IDENTITY_SHARE_MIN: int = 5
    FREQ_PEER_PERCENTILE: int = 99
    # minimum evidence before a rule emits a provider-level signal (small samples are noise)
    DUP_MIN_CLAIMS: int = 2
    NEAR_DUP_MIN_PAIRS: int = 3
    UPCODE_MIN_EM_LINES: int = 20
    UPCODE_RECENT_MONTHS: int = 6
    UPCODE_MAX_PVALUE: float = 0.01  # binomial test vs peer median rate (small-sample guard)
    FREQ_MIN_FAMILY_PAIRS: int = 50  # fewer member-provider pairs: use the service type's p99
    UNBUNDLE_MIN_MEMBER_DAYS: int = 3
    AMBULANCE_MIN_TRIPS: int = 2
    THRESHOLD_HUG_MIN_CLAIMS: int = 10
    THRESHOLD_HUG_MIN_IN_BAND: int = 5
    THRESHOLD_HUG_PEER_MULT: float = 3.0
    EARLY_REFILL_MIN_COUNT: int = 3
    REFERRAL_MIN_INBOUND: int = 5
    IDENTITY_SHARE_HARD: int = 10
    PEER_MIN_N: int = 20
    CASE_GRAPH_NODE_CAP: int = 150

    # graph / temporal
    LOUVAIN_RESOLUTION: float = 1.0
    REFERRAL_CYCLE_MAX_LEN: int = 4
    REFERRAL_CONCENTRATION: float = 0.50
    TEMPORAL_WINDOW_DAYS: int = 30
    DRIFT_MIN_MONTHS: int = 6
    BURST_MAD_K: float = 3.0

    # fusion / exoneration / scoring
    METHOD_WEIGHTS: dict[str, float] = field(
        default_factory=lambda: {"rules": 0.35, "anomaly": 0.25, "temporal": 0.15, "graph": 0.25}
    )
    ALERT_MIN_RISK: int = 20
    HARD_FLOOR: int = 85
    HARD_METHOD_BONUS: int = 5  # +5 risk per extra agreeing method above the hard floor
    CASE_MIN_RISK: int = 55
    SOLE_PROVIDER_KM: int = 60
    CASE_MIX_ADJ_CLEAR_RATIO: float = 1.5
    RECOVERY_RATE: float = 0.60
    EXPLORATION_SHARE: float = 0.10
    HOLD_WINDOW_DAYS: int = 7

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def state_dir(self) -> Path:
        return self.data_dir / "state"


def use_fixtures() -> bool:
    """Read on every request so tests and the shell can flip it without a restart."""
    return _env_bool("USE_FIXTURES", True)


CONFIG = Config()
