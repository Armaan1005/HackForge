# Part A: Detection Engine

Full spec: `docs/PART_A_ENGINE.md`. Read only the section for the module you're building (sections are A1–A18), plus that module's fixture in `contracts/`.

- Build in milestone order M0 → M9 (spec, "Build order").
- Every response passes through Pydantic models in `engine/schemas.py` that mirror `contracts/`.
- `USE_FIXTURES=true` → `engine/router.py` serves `contracts/*.json` unchanged.
- No module except `trust.py` and `twin/` may import or read ground truth (there's a test for it).
- Hard signals are never exonerated. Failed layers are marked `"unavailable"`, never crash the pipeline.
- Budgets: generate < 60 s, pipeline < 30 s, GET < 500 ms, queue < 300 ms, Fraud Twin < 20 s.
- Each milestone ends with: tests passing, acceptance criteria reported with numbers, a PR, and a handoff note for Part B.
