"""DataStore: loads data/raw/*.csv into typed pandas frames (cached). Never loads ground truth."""

from __future__ import annotations

import json
from functools import cached_property
from pathlib import Path

import numpy as np
import pandas as pd

from .config import CONFIG, REPO_DIR

DATE_COLS = {
    "claims": ["service_date", "submitted_date", "payment_release_date"],
    "members": ["coverage_start", "coverage_end", "date_of_death"],
    "providers": ["enrolled_date"],
    "admissions": ["admit_date", "discharge_date"],
    "referrals": ["referral_date"],
    "investigations": ["opened_date", "closed_date"],
}
INT_COLS = {
    "claims": ["line_no", "units", "duration_minutes", "billed_amount", "allowed_amount", "paid_amount", "frequency_code"],
    "members": ["age", "chronic_conditions"],
    "facilities": ["is_rural", "bed_count", "catchment_population"],
    "providers": ["is_rural"],
    "investigations": ["recovered_amount"],
}
FLOAT_COLS = {
    "claims": ["ambulance_miles", "pickup_lat", "pickup_lon", "dropoff_lat", "dropoff_lon", "days_supply", "rental_month"],
    "members": ["lat", "lon", "risk_score"],
    "facilities": ["lat", "lon"],
    "providers": ["lat", "lon"],
}


class DataStore:
    """Typed, cached access to generated data. Ground-truth files are never opened here."""

    def __init__(self, raw_dir: Path | None = None, ref_dir: Path | None = None):
        self.raw_dir = Path(raw_dir or CONFIG.raw_dir)
        self.ref_dir = Path(ref_dir or REPO_DIR / "data" / "reference")
        self._records: dict[str, dict] = {}

    def _load(self, name: str) -> pd.DataFrame:
        df = pd.read_csv(self.raw_dir / f"{name}.csv", dtype=str, keep_default_na=False)
        for c in DATE_COLS.get(name, []):
            df[c] = pd.to_datetime(df[c].replace("", None))
        for c in INT_COLS.get(name, []):
            df[c] = df[c].astype(int)
        for c in FLOAT_COLS.get(name, []):
            df[c] = pd.to_numeric(df[c].replace("", np.nan), errors="coerce")
        return df

    @cached_property
    def claims(self) -> pd.DataFrame:
        return self._load("claims")

    @cached_property
    def members(self) -> pd.DataFrame:
        return self._load("members")

    @cached_property
    def providers(self) -> pd.DataFrame:
        return self._load("providers")

    @cached_property
    def facilities(self) -> pd.DataFrame:
        return self._load("facilities")

    @cached_property
    def owners(self) -> pd.DataFrame:
        return self._load("owners")

    @cached_property
    def admissions(self) -> pd.DataFrame:
        return self._load("admissions")

    @cached_property
    def referrals(self) -> pd.DataFrame:
        return self._load("referrals")

    @cached_property
    def investigations(self) -> pd.DataFrame:
        return self._load("investigations")

    @cached_property
    def documents(self) -> pd.DataFrame:
        path = self.raw_dir / "documents.csv"
        if not path.exists():
            return pd.DataFrame(columns=["document_id", "doc_type", "format", "claim_ids", "member_id",
                                         "author_provider_id", "created_at", "path"])
        return pd.read_csv(path, dtype=str, keep_default_na=False)

    @cached_property
    def procedure_codes(self) -> pd.DataFrame:
        return pd.read_csv(self.ref_dir / "procedure_codes.csv", dtype={"code": str})

    @cached_property
    def code_pairs(self) -> pd.DataFrame:
        return pd.read_csv(self.ref_dir / "code_pairs.csv", dtype=str)

    @cached_property
    def dme_items(self) -> pd.DataFrame:
        return pd.read_csv(self.ref_dir / "dme_items.csv")

    def record(self, document_id: str) -> dict:
        if document_id not in self._records:
            self._records[document_id] = json.loads(
                (self.raw_dir / "records" / f"{document_id}.json").read_text(encoding="utf-8"))
        return self._records[document_id]

    # ------------------------------------------------------------ derived frames
    @cached_property
    def hdr(self) -> pd.DataFrame:
        """One row per claim (header): amounts summed over lines, first value of header fields."""
        c = self.claims
        g = c.groupby("claim_id", sort=True)
        h = g.agg(member_id=("member_id", "first"), provider_id=("provider_id", "first"),
                  billing_provider_id=("billing_provider_id", "first"), facility_id=("facility_id", "first"),
                  referring_provider_id=("referring_provider_id", "first"), service_type=("service_type", "first"),
                  place_of_service=("place_of_service", "first"), service_date=("service_date", "first"),
                  submitted_date=("submitted_date", "first"), payment_release_date=("payment_release_date", "first"),
                  payment_status=("payment_status", "first"), frequency_code=("frequency_code", "first"),
                  original_claim_id=("original_claim_id", "first"), billed=("billed_amount", "sum"),
                  allowed=("allowed_amount", "sum"), paid=("paid_amount", "sum"), lines=("line_no", "count"),
                  minutes=("duration_minutes", "sum"))
        return h.reset_index()

    @cached_property
    def provider_index(self) -> pd.DataFrame:
        return self.providers.set_index("provider_id")

    @cached_property
    def member_index(self) -> pd.DataFrame:
        return self.members.set_index("member_id")

    @cached_property
    def facility_index(self) -> pd.DataFrame:
        return self.facilities.set_index("facility_id")
