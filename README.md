# Axon

**Axon: connected claims tell the truth.** An evidence-first FWA intelligence platform.

> Code finds and scores. Gemini reads what code cannot and argues both sides. Money is held before it leaves. A human always decides.

A unified FWA (fraud, waste, abuse) platform: detects suspicious claims and coordinated networks, predicts 30/60/90-day risk, verifies documentary evidence, argues each case in an **Evidence Court**, and ranks cases against real **investigator capacity** for SIU review.

**All data is synthetic.** No real patient, member, provider or payer data is used anywhere in this repo.

---

## Who owns what

| Area | Owner | Folder |
|---|---|---|
| **Part A: Detection Engine** (data generator, rules, anomaly, temporal, graph, scoring, forecast, queue optimizer, Fraud Twin engine, trust metrics, audit) | Teammate (engine) | `backend/engine/` |
| **Part B: Evidence & Experience** (Gemini agents, Citation Verifier, LLM gateway, brief, UI) | Armaan (GenAI + UI) | `backend/genai/`, `frontend/` |
| **Shared contract** (API shapes + example fixtures) | Both — change only via PR labelled `contract` | `contracts/`, `docs/CONTRACT.md` |
| **App entrypoint** (mounts both routers) | Both — set up once, rarely touched | `backend/main.py` |

Docs:
- **Vaibhav: start with [docs/START_HERE_PART_A.md](docs/START_HERE_PART_A.md)** (setup, reading order, Claude Code prompt, handoffs)
- [docs/PART_A_ENGINE.md](docs/PART_A_ENGINE.md) — full build spec for Part A
- [docs/CONTRACT.md](docs/CONTRACT.md) — every endpoint, request and response shape
- [contracts/](contracts/) — example JSON for every response (Part B builds the UI against these)

---

## Repo layout

```
HackForge/
  README.md
  .env.example            # copy to backend/.env, never commit .env
  docs/
    PART_A_ENGINE.md
    CONTRACT.md
  contracts/              # example responses (the contract, by example)
  backend/
    requirements.txt
    main.py               # FastAPI app: /api -> engine, /api/ai -> genai
    engine/               # Part A
    genai/                # Part B
    tests/
  frontend/               # Part B (React + Vite + Tailwind + Cytoscape.js)
  data/
    reference/            # committed: synthetic code tables, cities
    raw/                  # generated, git-ignored
    processed/            # pipeline output, git-ignored
    state/                # decisions, audit log, feedback weights, git-ignored
    llm_cache/            # Part B cache, git-ignored
```

---

## Setup

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

Generate data, run the pipeline, start the API (from `backend/`):

```bash
python -m engine.generate --seed 42
```

```bash
python -m engine.pipeline
```

```bash
uvicorn main:app --reload --port 8000
```

Frontend (from `frontend/`):

```bash
npm install
```

```bash
npm run dev
```

Open http://localhost:5173. Or launch both from Claude Code with `.claude/launch.json` (`axon-api`, `axon-web`).

---

## Part B status (genai + UI)

Works today on the contract fixtures, before the engine exists:

| Piece | Where | Notes |
|---|---|---|
| LLM gateway | `backend/genai/gateway.py` | disk cache, concurrency cap, RPM limiter, priority queue, backoff, caller timeout |
| Citation Verifier | `backend/genai/verifier.py` | drops uncited statements and numbers not in the cited evidence; counts feed the Trust panel |
| Agents | `backend/genai/agents/` | Prosecutor, Defense, Verdict Clerk, Brief Writer, Document Forensics, Scenario Parser, Hardening Advisor, Exoneration Explainer, Ask-the-Case |
| Fallbacks | `backend/genai/templates.py` | every agent has a deterministic template; the UI labels which one ran |
| UI | `frontend/` | Command, SIU Queue, Case (7 tabs), Explained, Fraud Twin (+ QR judge page), Trust |

- Without `GEMINI_API_KEY` in `backend/.env`, everything still runs on templates. With it, the agents use `GEMINI_MODEL`.
- Before a demo: `POST /api/ai/prewarm` precomputes court, brief and forensics for every queued case so the live demo spends no quota.
- Tests: `pytest -q tests/genai` from `backend/` (offline, no Gemini calls).

---

## Working agreement

1. **Contract first.** Part A's endpoints must return exactly the shapes in `contracts/`. Part B builds against those fixtures with `USE_FIXTURES=true`, then flips to `false` when the engine is live.
2. **Stay in your folder.** Part A edits `backend/engine/` and `backend/tests/engine/`. Part B edits `backend/genai/` and `frontend/`.
3. **Contract changes** = edit the fixture + `docs/CONTRACT.md` in a PR labelled `contract`, and tell the other person. Adding a new optional field is fine; renaming or removing a field needs agreement.
4. **Branches:** `part-a/<module>` and `part-b/<feature>`, PRs into `main`, small and often.
5. **Secrets:** the Gemini key lives only in `backend/.env`. Never commit it, never send it to the frontend.
6. **Code decides, AI explains, humans decide.** No module auto-denies, auto-convicts or auto-holds payment.
