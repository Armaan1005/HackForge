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

## Handoff log

### M0 — fixture server (done)
1. Done: `engine/{config,schemas,router}.py`, `backend/main.py` (CORS localhost:5173, genai import optional), contract + quarantine tests.
2. Run: `cd backend && uvicorn main:app --port 8000` → http://localhost:8000/api (docs at `/docs`).
3. Next: M1 data generator (`engine/generate/`, spec A1) + reference tables in `data/reference/`.
4. Gotcha: `config.use_fixtures()` reads the env on every request; `main.py` loads `backend/.env` without overriding already-set env vars.
5. Gotcha: when live endpoints land, keep returning raw dicts validated through `schemas.py`; don't `model_dump()` fixture-mode data (int/float formatting must stay byte-identical).
