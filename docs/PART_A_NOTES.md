# Part A — working notes

Assumptions, decisions and per-milestone handoffs. Spec: [PART_A_ENGINE.md](PART_A_ENGINE.md).

## Assumptions

- **M0 fixture mode ignores path IDs.** `/api/cases/ANY`, `/api/documents/ANY`, `/api/forecast/ANY` etc. return their fixture (CASE-0001, DOC-00031, PRV-00412). Exception: `/api/entities/{id}/neighbors` walks the fixture graph and 404s for IDs not in it.
- **Fixture mode ignores query params** for shaping (`limit`, `offset`, `capacity_hours`, `horizon`), but still validates them (`horizon` ∈ 30/60/90, ints ≥ 0) so Part B sees real error envelopes.
- **Endpoints without a fixture** in fixture mode: `/claims` → `{case_id, total: 0, claims: []}` (claims.csv columns land in M1); `/peer_stats` → derived from `case_detail.peer_context`; `/neighbors` → subgraph of `case_graph`; `/files/scans/*.png` → a synthetic placeholder PNG; `/feedback/reset` → config default weights.
- **POST bodies are validated even in fixture mode**: decision `action` must be one of the 4 actions; Twin `scenario` must be whitelisted (`unsupported_scenario`) and params must be in bounds; harden `param` must be a tunable and within its range (`invalid_param`).
- **`USE_FIXTURES=false` before M3**: `/api/health` reports all layers `unavailable`; data endpoints return 503 `layer_unavailable`.
- **Error envelope** also covers FastAPI's own validation errors (→ 422 `invalid_param`) and unknown routes (→ 404 `not_found`), via `engine.router.install_error_handlers(app)` called from `main.py`.
- **`schemas.py` forbids unknown keys.** Optional fields are only those some fixture item omits (`peer_context.raw_ratio/peer_p90/note`, `projection.label`, scenario param `min/max/unit/values/description`).

### M1 (data generator)
- **Owners = 904**, not 900: 4 extra owners are created for S1 (2, sharing one bank hash), S6 and D7, so planted ownership never leaks onto unrelated providers.
- **Claim = header, line = row.** Amount rules (R12 threshold hugging) work at claim level on `billed_amount`, because pending claims have `paid_amount = 0`. S6 bills `allowed = paid = billed`.
- **Facility codes have `duration_minutes = 0`** (incl. DIA-001), so R08 only measures clinician time. Ambulance trips count 60–75 min.
- **R10 "hard"** should require the trip to be flagged (> 1.5× + 5 mi) *and* > 2×. Very short legitimate trips can exceed 2× from rounding alone.
- **R01/R02 key** must include `drug_code` and `dme_item_code` (pharmacy lines all use `RX-FILL`). S4's 40 duplicate claims give 43 line-level groups (2-line claims).
- **Baseline is rule-clean by construction.** Members only use providers in their home city (or the nearest city for rural towns); services avoid admission windows, coverage gaps and dates after death; accidental exact duplicates are dropped. The test `test_raw_signals_fire_only_on_planted_entities` proves R01/R05/R08/R10/R16 patterns exist only on planted entities.
- **Rural towns** (Gadchiroli, Ramanathapuram, Bahraich, Dahod) each have exactly one hospital. Facility `catchment_population` = city (district for rural) population ÷ same-type facilities in that city.
- **Innocent noise:** 30 random providers get a one-month burst; 150 legitimate corrections/voids (freq 7/8) on random claims.
- `documents.csv` / records / scans land in M2. The generator *writes* ground truth; the quarantine test allows `engine/generate/` as writer and checks that it never reads it back.

### M2 (documents)
- **412 records, 30 scans, 21 tampered documents** (spec said ~400 / ~30 / ~15). Documents use their own random stream (`seed + 1000`), so changing them never shifts claims.
- **Every document gets a JSON record** (contract shape); scan-format documents also get a PNG, and their record has `scan_url`.
- **Signatures are pasted after rotation/noise** into a fixed box (`SIG_BOX`). Honest scans get a per-document jitter of the author's squiggle, so the only pixel-identical signature boxes are the 3 tampered scans.
- **Lab tests print their code in brackets** (`HbA1c [LAB-420]: …`) and every note starts with `Date of service: YYYY-MM-DD.` These are the hooks the deterministic checks use (M3 document evidence).
- **Inserted consults are created the same day**, so they don't also trip `post_submission_creation`; each tamper type is planted on separate documents.
- `style_shift` is LLM-only (Part B); everything else is recoverable by a simple script (`tests/engine/test_documents.py::detect`).

## Handoff log

### M0 — fixture server (done)
1. Done: `engine/{config,schemas,router}.py`, `backend/main.py` (CORS localhost:5173, genai import optional), contract + quarantine tests.
2. Run: `cd backend && uvicorn main:app --port 8000` → http://localhost:8000/api (docs at `/docs`).
3. Next: M1 data generator (`engine/generate/`, spec A1) + reference tables in `data/reference/`.
4. Gotcha: `config.use_fixtures()` reads the env on every request; `main.py` loads `backend/.env` without overriding already-set env vars.
5. Gotcha: when live endpoints land, keep returning raw dicts validated through `schemas.py`; don't `model_dump()` fixture-mode data (int/float formatting must stay byte-identical).

### M1 — data generator (done)
1. Done: `engine/generate/` (geo, reference, entities, claims, schemes S1–S8, decoys D1–D10, `__main__`), reference tables in `data/reference/`, 11 M1 tests.
2. Run: `cd backend && python -m engine.generate --seed 42` → `data/raw/*.csv`, `ground_truth.csv`, `planted_cases.json` (eval-only) in ~5 s; 49,993 lines / 40,116 claims.
3. Seed-42 planted IDs: S6 = PRV-00459, PRV-00827, PRV-00384 (owner OWN-00903, facility FAC-0112); S1 ring = PRV-00037/00351/00404/00728; S2 = PRV-01258; S3 = PRV-00195; S4 = PRV-00041; S7 = PRV-01054; S8 = PRV-01382 + MEM-000178. Full list in `data/raw/planted_cases.json`.
4. Next: M2 documents (`engine/generate/documents.py`, spec A2): records JSON + ~30 PIL scans + S9 tampering + `ground_truth_documents.csv`.
5. Gotcha: entity reservation happens *before* baseline claims (`schemes.reserve_all`, `decoys.reserve_all`); add new planted entities there or baseline will bill them.

### M2 — documents and scans (done)
1. Done: `engine/generate/documents.py`. Records in `data/raw/records/`, scans in `data/raw/scans/`, `documents.csv`, eval-only `ground_truth_documents.csv`.
2. Run: same command, `python -m engine.generate --seed 42` (~18 s total).
3. Tamper → document (seed 42; share in chat only, never via the API): inserted_consult DOC-00319, DOC-00322 · post_submission_creation DOC-00323, DOC-00328 · procedure_absent DOC-00318, DOC-00321 · date_contradiction DOC-00331, DOC-00401 · prompt_injection DOC-00333 (scan) · duplicated_signature DOC-00336, DOC-00338, DOC-00340 · phantom_lab_result DOC-00396, DOC-00398 · templated_values DOC-00046, DOC-00047, DOC-00065, DOC-00071, DOC-00188, DOC-00191 · style_shift DOC-00402.
4. Next: M3: rules R01–R16 → cases → basic scoring → pipeline + live endpoints.
5. Gotcha: `procedures()` must exclude only EM1–EM5, not every code starting with "EM" (EMR-110/210 are procedures).
