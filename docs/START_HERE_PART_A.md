# Start here: Part A (Vaibhav)

You're building the **Detection Engine**. Armaan is building Part B (Gemini agents + UI) in parallel, against the example responses in `contracts/`.

## 1. Setup (once)

```bash
git clone https://github.com/Armaan1005/HackForge
```

```bash
cd HackForge
```

```bash
python -m venv .venv
```

```bash
.venv\Scripts\activate
```

```bash
pip install -r backend/requirements.txt
```

```bash
copy .env.example backend\.env
```

```bash
gh auth login
```

You don't need a Gemini key for Part A. Leave `GEMINI_API_KEY` empty.

## 2. What to read

| File | Why |
|---|---|
| `README.md` | ownership, layout, working agreement |
| `docs/PART_A_ENGINE.md` | **your full build spec** (modules A1–A18, milestones M0–M9) |
| `docs/CONTRACT.md` + `contracts/*.json` | the exact shapes your API must return |
| `CLAUDE.md`, `backend/engine/CLAUDE.md` | rules Claude Code loads automatically |

## 3. Kick off Claude Code

Open the `HackForge` folder in Claude Code and paste the prompt below. The repo's `CLAUDE.md` files and `.claude/settings.json` are already set up (safe commands pre-approved, `.env` blocked from reads).

**Token tips:** one session per milestone (start fresh after each PR), check `/context` and stay under ~40%, `/compact <what to keep>` when needed, rewind (Esc Esc) after a failed attempt instead of correcting on top of it.

## 4. The prompt

````text
You are helping me (Vaibhav) build Part A of ClaimShield Nexus, a hackathon project.
My teammate Armaan is building Part B (Gemini agents + React UI) at the same time.
Repo: https://github.com/Armaan1005/HackForge (already cloned; this is the working directory).

## What the project is
A healthcare FWA (fraud, waste, abuse) platform on 100% synthetic data. It detects
suspicious claims and coordinated networks, predicts 30/60/90-day risk, verifies
documentary evidence (including AI-fabricated medical records), and ranks cases for an
SIU team against limited investigator hours. Core rule: CODE decides every score, rank,
status and rupee figure. Gemini (Part B) only reads, argues over and words what my engine
produces. A human always makes the final decision. Nothing is auto-denied or auto-held.

## My job: Part A, the Detection Engine
Before writing any code, read:
1. README.md (ownership, layout, working agreement)
2. docs/PART_A_ENGINE.md (my full build spec: modules A1–A18, milestones M0–M9)
3. docs/CONTRACT.md, and the contracts/*.json fixture(s) for the milestone at hand

The spec and the contracts/ fixtures are the source of truth. If something is ambiguous,
pick the simplest option consistent with the spec, write the assumption in
docs/PART_A_NOTES.md, and keep going. Don't silently change the design.

## Hard rules
- Only create or edit files in backend/engine/, backend/tests/engine/, data/reference/,
  and docs/PART_A_NOTES.md. Never touch backend/genai/ or frontend/ (Armaan's).
  backend/main.py is shared: create it per the spec in A18 if it doesn't exist, and
  guard the genai router import with try/except ImportError so it runs before Part B exists.
- Every API response must match its contracts/*.json fixture exactly (same keys, same
  types, same nesting). If I genuinely need a shape change, stop and tell me. It needs a
  separate PR labelled "contract" and Armaan's agreement. Adding an optional field is OK.
- Deterministic: everything seeded (SEED=42). Same seed means identical outputs.
- Ground truth (data/raw/ground_truth*.csv) is read ONLY by trust.py and twin/.
  Detection, scoring, exoneration and the API must never read it. Add a test for this.
- Every fact in a case gets an evidence_id and sources [{table, column}]. Every number
  shown is computed by code, never hard-coded.
- Hard signals (service after death, >24h/day, ambulance miles >2x map distance,
  identity sharing >=10) are never exonerated.
- If a detection layer fails, log it, mark it "unavailable" in outputs, keep going.
- Synthetic data only: Faker en_IN, synthetic procedure codes (not real CPT/ICD text).
- Python 3.11+, pandas, numpy, scikit-learn, networkx, faker, pillow, ortools, FastAPI,
  Pydantic v2 (see backend/requirements.txt). No database: CSV/Parquet/JSON files only.
  No login, no GNNs.
- Never read whole generated data files (data/raw, data/processed); inspect with head.
- Never commit .env or anything in data/raw, data/processed, data/state.
- Meet the performance budgets in the spec (generate <60s, pipeline <30s, GET <500ms,
  queue re-plan <300ms, Fraud Twin run <20s).

## Build order: work milestone by milestone, in this order
M0  Fixture server: engine/router.py + engine/schemas.py (Pydantic models mirroring
    contracts/), serving contracts/*.json when USE_FIXTURES=true. Plus backend/main.py.
    Armaan is blocked until this exists, so do it first and keep it small.
M1  A1 data generator (python -m engine.generate --seed 42): all tables, all 8 service
    types, planted schemes S1–S9, decoys D1–D10, ground_truth.csv, reference tables.
M2  A2 documents: records JSON + PIL scans + planted tampering incl. the prompt-injection
    line, ground_truth_documents.csv.
M3  A3 rules -> A9 case builder -> A11 basic scoring -> A18 pipeline + live endpoints.
    After this, USE_FIXTURES=false must work for /api/cases/{id}.
M4  A4 anomaly, A5 temporal, A6 graph, A7 fused score
M5  A8 exoneration, A10 peer context
M6  A13 queue optimizer + money clock
M7  A12 forecast
M8  A15 Fraud Twin (run + harden + sandbox case view)
M9  A14 time machine, A16 feedback + audit, A17 trust metrics
If time is short, follow the "what to cut" order in the spec. Never cut A1, A3, A6, A9,
A11, A13, basic A17, or the case graph.

## How to work each milestone
1. Briefly state your plan for the milestone, then implement it.
2. Write the pytest tests listed in the spec's "Testing and definition of done" section
   that apply to it, plus test_contract_shapes for any endpoint you touched.
3. Run the tests and the relevant command (generate / pipeline / uvicorn + curl the
   endpoints). Show me the real output. Don't claim something works without running it.
4. Check the module's acceptance criteria from the spec and report which pass or fail,
   with numbers (e.g. "S6 detected, 44/47 claims; decoys defended 11/12").
5. Commit on a branch named part-a/<milestone-or-module> with a clear message, push,
   and open a PR into main with: gh pr create --base main. Small PRs, one milestone each.
6. Tell me what to send Armaan (see "Handoffs to Part B" in the spec), e.g. after M0
   "fixture server is up", after M2 "records and scans exist, planted doc IDs are …",
   after M3 "3 case IDs to test with: fraud / decoy / ambiguous".

## Quality bar
Readable, typed Python with short docstrings. Thresholds live in engine/config.py, not
inline. Use real numbers in descriptions ("94% of claims vs peer median 11%"), because
Part B's Prosecutor/Defense agents quote them. Seed 42 must produce: every planted scheme
in an open case, >=90% decoys defended, 0 planted fraud wrongly exonerated, and at least
one high-risk case that ranks low in the queue because of weak evidence or high effort
(the demo depends on it).

Start now: read the docs above, summarize the plan for M0 in a few lines, then build M0.
````

## 5. Handoffs to send Armaan

| After | Send |
|---|---|
| M0 | "Fixture server is up at localhost:8000/api" |
| M1/M2 | "Records and scans exist" + the planted document IDs (verbally, never via the API) |
| M3 | "Live cases work" + 3 case IDs: one fraud, one decoy, one ambiguous |
| M5 | "peer_context and alerts_cleared are live" |
| M8 | "Twin scenario whitelist is final" |
| Any time | A PR labelled `contract` if a response shape must change |
