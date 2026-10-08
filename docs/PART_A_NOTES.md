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

### M3 (rules, cases, scoring, live API)
- **Fused risk is normalised** by the maximum the *available* layers could reach: `risk = 100·(1 − Π(1 − w·s)) / (1 − Π(1 − w))`. Taken literally, the spec formula caps a non-hard entity at 69 (below the fixtures' 79–96, barely above `CASE_MIN_RISK` 55), and a missing layer would deflate everyone.
- **Small-sample guards (all in config):** R03 needs ≥ 20 E&M lines *and* a binomial test vs the peer median (`UPCODE_MAX_PVALUE = 0.01`); R12 needs ≥ 10 claims and ≥ 5 in the band; R02 ≥ 3 pairs; R15 ≥ 5 inbound referrals; R11 falls back to the service type's p99 when a code family has < 50 member–provider pairs (otherwise the dialysis decoy defines its own p99).
- **Peer groups** for individual + group practices are by specialty (× state, national fallback when n < 20); other provider types by type.
- **Verdict vs missing documents:** the fixture sends a strong case with 12 missing operative notes to `needs_siu_review`. So: strong + confidence ≥ 0.75 → `needs_siu_review` (records are requested in `next_action_text`); other strong/moderate → `request_documentation`; weak → `monitor`. Missing critical docs still lower confidence (−0.08 each).
- **Evidence strength "strong"** = hard signal + ≥ 2 agreeing methods, or ≥ 3 methods. With rules only (M3) every case is weak → `monitor`; M4's layers lift them.
- **Document cross-checks** (`engine/doccheck.py`) become `type: "document"` evidence; they do not change risk. The prompt-injection line is reported as `document.embedded_instruction` (treated as data).
- **Horizon risk** is a labelled placeholder (from current risk) until the M7 forecast; the limitation line says so.
- **Live API:** a feature whose milestone hasn't landed answers 503 `layer_unavailable`; unknown IDs 404. `/cases/{id}/claims` serves precomputed rows from `processed/claims/`.

### M4 (anomaly, temporal, graph)
- **Anomaly:** Isolation Forest (200 trees, seed) on robust z (median/MAD, MeanAD fallback, clip ±8) of 14 features for providers with ≥ 10 claims; signal at percentile ≥ 0.9 plus top-3 |z| drivers. Model saved to `processed/anomaly_model.joblib` for Fraud Twin. **Member-level anomaly cut** (spec's first cut item).
- **Temporal:** EM5 drift = OLS over the trailing 9 months (months with ≥ 5 E&M), slope > 3 pp/month and p < 0.05. Bursts: ≥ 12 claims, > median + 3·MAD *and* ≥ 3× the prior-6-month median; **region-wide** if ≥ 5 providers in the same city are elevated that month (looser test) → neutral signal (feeds EX4). Rapid ramp: tenure < 9 months and > 2× peer p90. Window clusters: same member, linked providers (shared owner/facility), mid/high-value claims, within `TEMPORAL_WINDOW_DAYS`.
- **Graph "flagged" providers** = rule hits or anomaly ≥ 0.99. Shared owner/facility only becomes evidence with ≥ 2 flagged providers; shared bank across different owners always does. Projection ties: Jaccard ≥ 0.05 with ≥ 3 shared members, referrals, owner, bank, facility (0.5).
- **Case grouping** no longer unions on shared primary facility (hospitals host many unrelated providers); graph cycles/communities/shared indicators supply links instead.

### M5 (exoneration, peer context)
- **EX rules by signal:** R01/R02 → EX3 (≥ 50% of flagged claims corrected); R11 dialysis ≤ 14/30 days → EX5, else event/seasonal → EX4; R03 and case-mix-type anomaly drivers → EX2 (adjusted ratio = max(EM5, billed-per-member ratio) ÷ case-mix ratio < 1.5); volume-type anomaly/bursts/ramp → EX4 (region-wide burst, or same-day cluster: ≥ 20 members each seen by ≥ 3 providers in one city) or EX1 (nearest same-type competitor > 60 km and volume per 1k catchment within peer IQR, ×1.25); graph/window signals → EX6 when max billing |z| < 2 and no rule hits.
- **Cleared only if every incriminating signal is explained and none is hard.** Partial explanations become one exculpatory `exoneration` evidence item per EX code (weight 0, so they inform the Defense without moving confidence).
- **Peer context** is built for the case's top provider: EM5, band share, billed per member, KL, top referral source, case mix, the risk-adjusted ratio (with `raw_ratio`), prior investigations, tenure, nearest competitor (if sole).
- **Generator tweak:** D2 now bills 80 claims (was 160) so its members-per-claim matches peers; its intensity is explained by case mix.

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

### M3 — rules, cases, scoring, live API (done)
1. Done: `store.py`, `features.py`, `detect/{signals,rules,graph}.py` (graph = case subgraph only), `fuse.py`, `doccheck.py`, `cases.py`, `scoring.py`, `pipeline.py`, live mode in `router.py`; 17 rule tests (hit + non-hit, incl. D8/D9), live API tests.
2. Run: `python -m engine.pipeline` (~8 s) → `data/processed/`; then `USE_FIXTURES=false uvicorn main:app`.
3. Seed 42 (rules only): 14 cases; all of S1–S8 are in cases; decoys D2 (oncologist) and D6 (dialysis) are cases until M5 exoneration; 3 cases are innocent noise.
4. Next: M4: anomaly (IsolationForest + robust z + KL), temporal (drift, bursts, ramp), graph analytics (cycles, shared indicators, Louvain, exposure, small-claims pattern).
5. Gotcha: every M3 status is `monitor` by design (one method); don't tune thresholds to "fix" that before M4.

### M4 — four detection layers (done)
1. Done: `detect/anomaly.py`, `detect/temporal.py`, `detect/graph_analytics.py` (+ re-export in `graph.py`, `neighbors()` for the tool endpoint), pipeline context sharing, 3 acceptance tests.
2. Seed 42: 109 alerts → 9 cases (~8 s pipeline). Every S1–S8 is a case, all `needs_siu_review` or `request_documentation`; D2 is the only decoy case (cleared in M5 by EX2).
3. Acceptance: S3 + S6 anomaly ≥ 0.98; S3 drift +4.9 pp/month; D5 burst region-wide; S1 4-cycle; S6 one community, 43 connected claims; D7 one community, not flagged.
4. Next: M5 exoneration (EX1–EX6) + peer context.
5. Gotcha: graph uses the rule + anomaly signals already in `context["signals"]`; keep layer order rules → anomaly → temporal → graph.

### M5 — exoneration + peer context (done)
1. Done: `exonerate.py` (EX1–EX6), `peer_context.py`, partial-explanation evidence, 3 tests.
2. Seed 42: 109 alerts → 27 cleared (EX2 16, EX4 ~9, EX1 2…) → 8 cases = exactly S1–S8; 0 planted fraud cleared; decoys defended ≥ 90%.
3. `peer_context[]` and `/api/alerts/cleared` are live (handoff to Armaan).
4. Next: M6 queue optimizer (OR-Tools CP-SAT knapsack) + money clock.
5. Gotcha: an alert with a hard signal is never cleared, even if every other signal is explained.
