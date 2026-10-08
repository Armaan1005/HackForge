# API Contract

Base URL: `http://localhost:8000`. Engine (Part A) serves `/api/*`. GenAI (Part B) serves `/api/ai/*`.
Every response shape is defined **by example** in [`contracts/`](../contracts/). If this doc and a fixture disagree, the fixture wins — then fix the doc.

**Change rules:** adding an optional field = OK (update fixture). Renaming/removing/retyping = PR labelled `contract` + agreement from both.

Conventions: IDs are prefixed strings; dates ISO `YYYY-MM-DD`, datetimes `YYYY-MM-DDTHH:MM:SS`; money is whole INR integers with `"currency": "INR"` at the top level where relevant; shares are 0–1 floats; risk is 0–100; confidence/probability 0–1.

---

## Part A endpoints (`/api`)

| Method | Path | Query / body | Fixture | Notes |
|---|---|---|---|---|
| GET | `/api/health` | — | — | `{status, use_fixtures, engine_version, layers:{rules,anomaly,temporal,graph}}` |
| GET | `/api/overview` | — | `overview.json` | data counts, service-type mix, funnel |
| GET | `/api/alerts/cleared` | `limit`, `offset` | `alerts_cleared.json` | exonerated alerts + deterministic facts; `explanation` is `null` (Part B fills) |
| GET | `/api/queue` | `capacity_hours` (int, default 40), `horizon` (30\|60\|90) | `queue.json` | re-planned live |
| GET | `/api/cases/{case_id}` | — | `case_detail.json` | **the evidence pool** |
| GET | `/api/cases/{case_id}/graph` | — | `case_graph.json` | ≤ 150 nodes |
| GET | `/api/cases/{case_id}/timemachine` | — | `timemachine.json` | node/edge IDs match graph |
| GET | `/api/cases/{case_id}/claims` | `limit`, `offset` | — | tool for "Ask the Case": `{case_id, total, claims:[claims.csv row]}` |
| GET | `/api/entities/{entity_id}/peer_stats` | — | — | tool: `{entity_id, peer_group, n, metrics:[{metric, value, peer_median, peer_p90, percentile}]}` |
| GET | `/api/entities/{entity_id}/neighbors` | `depth` (1\|2) | — | tool: `{entity_id, nodes:[...], edges:[...]}` same node/edge shape as graph |
| GET | `/api/forecast/{entity_id}` | `horizon` (30\|60\|90) | `forecast.json` | |
| GET | `/api/documents/{document_id}` | — | `document.json` | record JSON; scans via `scan_url` |
| GET | `/api/files/scans/{document_id}.png` | — | — | static PNG |
| POST | `/api/cases/{case_id}/decision` | `decision_request` | `decision.json` | human action; audit-logged |
| POST | `/api/feedback/reset` | — | — | `{reset: true, weights:{...}}` |
| GET | `/api/twin/scenarios` | — | `twin_scenarios.json` | **whitelist** for the Scenario Parser |
| POST | `/api/twin/run` | `{scenario, params, seed}` | `twin_run.json` | sandbox only |
| POST | `/api/twin/harden` | `{run_id, change:{param, new_value}}` | `twin_harden.json` | analyst-approved rerun |
| GET | `/api/twin/runs/{run_id}/cases/{case_id}` | — | `case_detail.json` shape | sandbox case for Judge Challenge |
| GET | `/api/trust` | — | `trust.json` | `ai` block is `null` from Part A |
| GET | `/api/audit` | `limit` | `audit.json` | |

Errors: `{"error": {"code": "not_found" | "invalid_param" | "unsupported_scenario" | "layer_unavailable", "message": "..."}}` with matching HTTP status.

---

## Part B endpoints (`/api/ai`) — for reference

| Method | Path | Returns |
|---|---|---|
| POST | `/api/ai/forensics/{case_id}` | `{integrity_flags:[{flag_id, document_id, section_id, check, label:"AI-observed, human to verify", confidence, evidence_ids}], injection_detected:[...]}` |
| POST | `/api/ai/court/{case_id}` | `{prosecution:{arguments[]}, defense:{arguments[], missing_evidence[]}, verdict:{status, next_action, summary}, verifier:{checked, dropped, dropped_items[]}}` — `status`/`next_action` copied from Part A |
| GET | `/api/ai/brief/{case_id}` | markdown / pdf |
| POST | `/api/ai/explain_cleared` | one-line explanations for cleared alerts |
| POST | `/api/ai/twin/parse` | `{scenario, params}` validated against `/api/twin/scenarios`, or `{error:"unsupported"}` |
| POST | `/api/ai/twin/advise` | `{suggested_change:{param, new_value}, explanation}` from Part A's `miss_reason_summary` |
| POST | `/api/ai/ask/{case_id}` | grounded answer + tool calls made |
| GET | `/api/ai/status` | `{queue_depth, calls_this_minute, model, cache_hits}` |

---

## Key field semantics

### Case (`case_detail.json`)
- `verdict.status` ∈ `needs_siu_review | request_documentation | monitor | cleared` — **computed by Part A**. Part B words it, never changes it.
- `verdict.human_approval_required` is always `true`.
- `evidence[]` — citable atoms. `direction` ∈ `incriminating | exculpatory | neutral`. `value`/`comparison_value` are the numbers agents must quote.
- `peer_context[]` — citable comparisons (IDs `PC-…`); `low_sample: true` when peer n < 20.
- `payment_clock.hold_recommended` is a recommendation; `hold_status` only changes via a human `decision`.
- `horizon_risk` keys are strings `"30"`, `"60"`, `"90"`.
- `layers` reports which detection layers ran; a missing layer = `"unavailable"` and a limitation line.

### Evidence item
`evidence_id, type, method, name, description, direction, entity_ids, claim_ids (≤25), claim_count, value, comparison_value, comparison_label, unit, threshold, severity (1–5), hard, weight, sources[{table,column}]`.

### Graph
Node: `{id, type, label, risk, flagged, in_case, first_seen_month, attrs}`; `type` ∈ `provider, member, member_group, facility, owner, bank, address, location, claim, claim_group`.
Edge: `{id, source, target, type, weight, first_seen_month, evidence_ids}`; `type` ∈ `treated, referral, practices_at, owned_by, uses_bank, located_at, lives_at, shares_phone, billed, billed_at`.

### Queue
`selected` = in today's plan; `exploration` = picked from the 10% exploration reserve; `selection_reason` is a display string computed by code.

### Decision request
```json
{ "action": "confirm | clear | need_more_info | hold_payment", "user": "priya", "note": "optional free text" }
```
