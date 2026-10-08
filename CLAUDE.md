# ClaimShield Nexus

Healthcare FWA platform on **100% synthetic data**. Code decides scores, ranks, statuses and INR figures; Gemini agents only explain and argue; a human always decides. No auto-deny, no auto-hold.

## Ownership (stay in your lane)
- **Part A, engine (Vaibhav):** `backend/engine/`, `backend/tests/engine/`, `data/reference/`. Spec: `docs/PART_A_ENGINE.md`
- **Part B, genai + UI (Armaan):** `backend/genai/`, `frontend/`
- **Shared:** `contracts/*.json` + `docs/CONTRACT.md` (the API shapes), `backend/main.py`
- Don't edit the other part's folders. Contract shape changes need a PR labelled `contract`.

## Commands (run from `backend/`)
- Install: `pip install -r requirements.txt`
- Generate data: `python -m engine.generate --seed 42`
- Run pipeline: `python -m engine.pipeline`
- API: `uvicorn main:app --reload --port 8000`
- Tests: `pytest -q` (engine only: `pytest -q tests/engine`)
- Frontend (from `frontend/`): `npm install`, `npm run dev` (port 5173)

## Rules
- API responses must match `contracts/*.json` exactly. Read the one fixture you need, not all of them.
- Seeded and deterministic (SEED=42). Thresholds live in `backend/engine/config.py`.
- Ground truth (`data/raw/ground_truth*.csv`) is read only by `engine/trust.py` and `engine/twin/`.
- Every case fact has an `evidence_id` + `sources`. Never hard-code numbers shown to users.
- Secrets live only in `backend/.env` (git-ignored). Never read, print or commit it.
- Generated data (`data/raw`, `data/processed`, `data/state`, `data/llm_cache`) is large: inspect with `head`/pandas `.head()`, never read whole files.
- Branches `part-a/<module>` / `part-b/<feature>`, small PRs into `main`.

## Working style
- Run the tests/command and show real output before saying something works.
- Prefer small focused edits; don't reformat untouched code.
- For broad searches across the repo, use a subagent and return only the conclusion.
