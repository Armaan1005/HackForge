"""Synthetic reference tables (committed to data/reference/). Codes and descriptions are
invented for this project; they are not real CPT/ICD/drug codes."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# code, description, service_type, family, level, typical_minutes, base_price_inr, max_rental_months
_CODES: list[tuple] = [
    ("EM1", "Office visit, level 1 (synthetic)", "professional", "em", 1, 10, 400, None),
    ("EM2", "Office visit, level 2 (synthetic)", "professional", "em", 2, 15, 700, None),
    ("EM3", "Office visit, level 3 (synthetic)", "professional", "em", 3, 25, 1100, None),
    ("EM4", "Office visit, level 4 (synthetic)", "professional", "em", 4, 40, 1700, None),
    ("EM5", "Office visit, level 5 (synthetic)", "professional", "em", 5, 60, 2600, None),
    ("ORT-101", "Closed fracture reduction (synthetic)", "professional", "procedure", None, 45, 18000, None),
    ("ORT-214", "Arthroscopic knee debridement (synthetic)", "professional", "procedure", None, 90, 42000, None),
    ("ORT-219", "Limited shoulder arthroscopy (synthetic)", "professional", "procedure", None, 80, 38000, None),
    ("ORT-305", "Joint injection (synthetic)", "professional", "procedure", None, 20, 3500, None),
    ("CAR-110", "Echocardiogram reading (synthetic)", "professional", "procedure", None, 30, 2500, None),
    ("CAR-220", "Cardiac stress test (synthetic)", "professional", "procedure", None, 45, 6000, None),
    ("CAR-410", "Coronary angiography (synthetic)", "professional", "procedure", None, 90, 35000, None),
    ("ONC-120", "Chemotherapy administration (synthetic)", "professional", "procedure", None, 120, 15000, None),
    ("ONC-210", "Bone marrow biopsy (synthetic)", "professional", "procedure", None, 45, 12000, None),
    ("PED-110", "Newborn assessment (synthetic)", "professional", "procedure", None, 30, 1500, None),
    ("PED-210", "Immunisation administration (synthetic)", "professional", "procedure", None, 10, 600, None),
    ("NEP-110", "Renal biopsy (synthetic)", "professional", "procedure", None, 60, 20000, None),
    ("EMR-110", "Emergency resuscitation (synthetic)", "professional", "procedure", None, 60, 9000, None),
    ("EMR-210", "Complex wound repair (synthetic)", "professional", "procedure", None, 40, 5000, None),
    ("RAD-110", "X-ray reading (synthetic)", "professional", "procedure", None, 10, 800, None),
    ("RAD-210", "CT reading (synthetic)", "professional", "procedure", None, 20, 3500, None),
    ("RAD-310", "MRI reading (synthetic)", "professional", "procedure", None, 30, 6000, None),
    ("PHY-010", "Physiotherapy session (synthetic)", "professional", "procedure", None, 45, 900, None),
    ("PHY-031", "Post-operative rehabilitation package, 10 sessions (synthetic)", "professional", "procedure", None, 60, 24000, None),
    ("GEN-110", "Minor skin procedure (synthetic)", "professional", "procedure", None, 20, 1500, None),
    ("GEN-210", "Nebulisation (synthetic)", "professional", "procedure", None, 15, 500, None),
    ("FAC-IPD", "Inpatient room and board, per day (synthetic)", "facility", "inpatient", None, 0, 6000, None),
    ("FAC-ICU", "Intensive care, per day (synthetic)", "facility", "inpatient", None, 0, 15000, None),
    ("FAC-OT", "Operation theatre charges (synthetic)", "facility", "inpatient", None, 0, 60000, None),
    ("FAC-OPD", "Outpatient facility visit (synthetic)", "facility", "outpatient", None, 0, 1500, None),
    ("FAC-DAY", "Day-care procedure facility fee (synthetic)", "facility", "outpatient", None, 0, 25000, None),
    ("FAC-ER", "Emergency room facility fee (synthetic)", "facility", "outpatient", None, 0, 4000, None),
    ("DIA-001", "Haemodialysis session (synthetic)", "facility", "dialysis", None, 0, 2500, None),
    ("LAB-100", "Basic metabolic panel (synthetic)", "lab", "panel", None, 5, 900, None),
    ("LAB-101", "Sodium (synthetic)", "lab", "component", None, 5, 350, None),
    ("LAB-102", "Potassium (synthetic)", "lab", "component", None, 5, 350, None),
    ("LAB-103", "Creatinine (synthetic)", "lab", "component", None, 5, 350, None),
    ("LAB-104", "Glucose (synthetic)", "lab", "component", None, 5, 350, None),
    ("LAB-200", "Lipid panel (synthetic)", "lab", "panel", None, 5, 800, None),
    ("LAB-201", "Total cholesterol (synthetic)", "lab", "component", None, 5, 400, None),
    ("LAB-202", "HDL cholesterol (synthetic)", "lab", "component", None, 5, 400, None),
    ("LAB-203", "Triglycerides (synthetic)", "lab", "component", None, 5, 400, None),
    ("LAB-300", "Complete blood count panel (synthetic)", "lab", "panel", None, 5, 450, None),
    ("LAB-301", "Haemoglobin (synthetic)", "lab", "component", None, 5, 250, None),
    ("LAB-302", "White cell count (synthetic)", "lab", "component", None, 5, 250, None),
    ("LAB-303", "Platelet count (synthetic)", "lab", "component", None, 5, 250, None),
    ("LAB-410", "Dengue NS1 antigen (synthetic)", "lab", "test", None, 5, 900, None),
    ("LAB-420", "HbA1c (synthetic)", "lab", "test", None, 5, 600, None),
    ("LAB-430", "Thyroid profile (synthetic)", "lab", "test", None, 5, 700, None),
    ("LAB-440", "Urine routine (synthetic)", "lab", "test", None, 5, 250, None),
    ("AMB-BLS", "Basic life support transport (synthetic)", "ambulance", "transport", None, 60, 1500, None),
    ("AMB-ALS", "Advanced life support transport (synthetic)", "ambulance", "transport", None, 75, 3500, None),
    ("BH-030", "Psychotherapy, 30 minutes (synthetic)", "behavioral_health", "therapy", None, 30, 900, None),
    ("BH-045", "Psychotherapy, 45 minutes (synthetic)", "behavioral_health", "therapy", None, 45, 1300, None),
    ("BH-060", "Psychotherapy, 60 minutes (synthetic)", "behavioral_health", "therapy", None, 60, 1800, None),
    ("BH-090", "Psychiatric diagnostic evaluation (synthetic)", "behavioral_health", "evaluation", None, 90, 3000, None),
    ("HH-010", "Skilled nursing home visit (synthetic)", "home_health", "visit", None, 60, 1500, None),
    ("HH-020", "Home physiotherapy visit (synthetic)", "home_health", "visit", None, 45, 1200, None),
    ("HH-030", "Home health aide visit (synthetic)", "home_health", "visit", None, 120, 1000, None),
    ("RX-FILL", "Prescription fill (synthetic)", "pharmacy", "fill", None, 0, 0, None),
    ("DME-RENT", "DME monthly rental (synthetic)", "dme", "rental", None, 0, 0, 13),
    ("DME-BUY", "DME purchase (synthetic)", "dme", "purchase", None, 0, 0, None),
]

CODE_PAIRS = [
    ("LAB-100", "LAB-101"), ("LAB-100", "LAB-102"), ("LAB-100", "LAB-103"), ("LAB-100", "LAB-104"),
    ("LAB-200", "LAB-201"), ("LAB-200", "LAB-202"), ("LAB-200", "LAB-203"),
    ("LAB-300", "LAB-301"), ("LAB-300", "LAB-302"), ("LAB-300", "LAB-303"),
]

# item_code, description, monthly_rent_inr, max_rental_months, purchase_price_inr
DME_ITEMS = [
    ("DMEI-01", "Semi-electric hospital bed (synthetic)", 6000, 13, 60000),
    ("DMEI-02", "Oxygen concentrator (synthetic)", 4500, 36, 55000),
    ("DMEI-03", "Wheelchair, standard (synthetic)", 1500, 13, 12000),
    ("DMEI-04", "CPAP device (synthetic)", 3500, 13, 40000),
    ("DMEI-05", "Nebuliser (synthetic)", 800, 6, 3000),
    ("DMEI-06", "Walker (synthetic)", 500, 6, 2500),
    ("DMEI-07", "Pressure-relief mattress (synthetic)", 2500, 13, 22000),
]

# drug_code, description, drug_class, price_per_day_inr, typical_days_supply, chronic
DRUGS = [
    ("DRG-001", "Synthetic antihypertensive A", "cardiovascular", 12, 30, 1),
    ("DRG-002", "Synthetic antihypertensive B", "cardiovascular", 18, 30, 1),
    ("DRG-003", "Synthetic statin", "cardiovascular", 15, 30, 1),
    ("DRG-004", "Synthetic oral antidiabetic", "endocrine", 10, 30, 1),
    ("DRG-005", "Synthetic insulin pen", "endocrine", 95, 30, 1),
    ("DRG-006", "Synthetic thyroid hormone", "endocrine", 6, 90, 1),
    ("DRG-007", "Synthetic inhaler", "respiratory", 40, 30, 1),
    ("DRG-008", "Synthetic antidepressant", "cns", 22, 30, 1),
    ("DRG-009", "Synthetic broad-spectrum antibiotic", "anti-infective", 60, 7, 0),
    ("DRG-010", "Synthetic analgesic", "analgesic", 8, 7, 0),
    ("DRG-011", "Synthetic antipyretic", "analgesic", 5, 5, 0),
    ("DRG-012", "Synthetic proton pump inhibitor", "gastro", 9, 14, 0),
    ("DRG-013", "Synthetic oral chemotherapy agent", "oncology", 260, 28, 1),
    ("DRG-014", "Synthetic erythropoietin analogue", "renal", 180, 30, 1),
]


def procedure_codes() -> pd.DataFrame:
    cols = ["code", "description", "service_type", "family", "level", "typical_minutes",
            "base_price_inr", "max_rental_months"]
    df = pd.DataFrame(_CODES, columns=cols)
    df["level"] = df["level"].astype("Int64")
    df["max_rental_months"] = df["max_rental_months"].astype("Int64")
    return df


def code_pairs() -> pd.DataFrame:
    return pd.DataFrame(CODE_PAIRS, columns=["panel_code", "component_code"])


def dme_items() -> pd.DataFrame:
    return pd.DataFrame(DME_ITEMS, columns=["item_code", "description", "monthly_rent_inr",
                                            "max_rental_months", "purchase_price_inr"])


def drugs() -> pd.DataFrame:
    return pd.DataFrame(DRUGS, columns=["drug_code", "description", "drug_class",
                                        "price_per_day_inr", "typical_days_supply", "chronic"])


def write_reference(ref_dir: Path) -> None:
    """Write the four reference tables. Deterministic (no randomness)."""
    ref_dir.mkdir(parents=True, exist_ok=True)
    procedure_codes().to_csv(ref_dir / "procedure_codes.csv", index=False, lineterminator="\n")
    code_pairs().to_csv(ref_dir / "code_pairs.csv", index=False, lineterminator="\n")
    dme_items().to_csv(ref_dir / "dme_items.csv", index=False, lineterminator="\n")
    drugs().to_csv(ref_dir / "drugs.csv", index=False, lineterminator="\n")
