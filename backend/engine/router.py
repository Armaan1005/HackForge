"""FastAPI router mounted at /api (spec A18).

USE_FIXTURES=true (M0 default): every endpoint serves its contracts/*.json fixture unchanged,
after validating it against engine.schemas. Endpoints without a fixture return small,
contract-shaped responses derived from the fixtures. Fixture mode ignores path IDs except
where noted (neighbors), so Part B can hit real URLs before the engine exists.

USE_FIXTURES=false: live engine output. Until the pipeline exists (M3) every data endpoint
answers 503 layer_unavailable.
"""

from __future__ import annotations

import io
import json
from functools import cache, lru_cache
from typing import Any

from fastapi import APIRouter, Body, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import ENGINE_VERSION
from . import schemas as S
from .config import CONFIG, use_fixtures

router = APIRouter(prefix="/api", tags=["engine"])

HORIZONS = (30, 60, 90)


# ---------------------------------------------------------------- errors

class ApiError(Exception):
    """Raised by handlers; rendered as {"error": {"code", "message"}}."""

    def __init__(self, status: int, code: S.ErrorCode, message: str):
        super().__init__(message)
        self.status = status
        self.code: S.ErrorCode = code
        self.message = message


def _error_body(code: S.ErrorCode, message: str) -> dict[str, Any]:
    return S.ErrorResponse(error=S.Error(code=code, message=message)).model_dump()


def install_error_handlers(app: FastAPI) -> None:
    """Map engine errors, validation errors and 404s onto the contract's error shape."""

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=_error_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in first.get("loc", []))
        return JSONResponse(
            status_code=422,
            content=_error_body("invalid_param", f"{where}: {first.get('msg', 'invalid request')}"),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code: S.ErrorCode = "not_found" if exc.status_code == 404 else "invalid_param"
        return JSONResponse(status_code=exc.status_code, content=_error_body(code, str(exc.detail)))


def _live_unavailable(what: str) -> ApiError:
    return ApiError(
        503,
        "layer_unavailable",
        f"Live engine output for {what} is not built yet. Run the pipeline or set USE_FIXTURES=true.",
    )


def _check_horizon(horizon: int) -> None:
    if horizon not in HORIZONS:
        raise ApiError(422, "invalid_param", f"horizon must be one of {list(HORIZONS)}, got {horizon}")


# ---------------------------------------------------------------- fixtures

@cache
def fixture(name: str) -> dict[str, Any]:
    """Load contracts/<name>.json, validate it against its schema, cache it."""
    path = CONFIG.contracts_dir / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    S.FIXTURE_MODELS[name].model_validate(data)
    return data


def _serve(name: str, what: str) -> dict[str, Any]:
    if use_fixtures():
        return fixture(name)
    raise _live_unavailable(what)


# ---------------------------------------------------------------- health / overview

@router.get("/health", responses={200: {"model": S.Health}})
def health() -> dict[str, Any]:
    if use_fixtures():
        layers = fixture("overview")["layers"]
        status = "ok"
    else:
        layers = {k: "unavailable" for k in ("rules", "anomaly", "temporal", "graph")}
        status = "no_engine_output"
    return S.Health(
        status=status, use_fixtures=use_fixtures(), engine_version=ENGINE_VERSION,
        layers=S.Layers.model_validate(layers),
    ).model_dump()


@router.get("/overview", responses={200: {"model": S.Overview}})
def overview() -> dict[str, Any]:
    return _serve("overview", "overview")


@router.get("/alerts/cleared", responses={200: {"model": S.AlertsCleared}})
def alerts_cleared(limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)) -> dict[str, Any]:
    return _serve("alerts_cleared", "cleared alerts")


# ---------------------------------------------------------------- queue

@router.get("/queue", responses={200: {"model": S.Queue}})
def queue(capacity_hours: int = Query(40, ge=0, le=1000), horizon: int = 30) -> dict[str, Any]:
    _check_horizon(horizon)
    return _serve("queue", "the queue")


# ---------------------------------------------------------------- cases

@router.get("/cases/{case_id}", responses={200: {"model": S.CaseDetail}})
def case_detail(case_id: str) -> dict[str, Any]:
    return _serve("case_detail", f"case {case_id}")


@router.get("/cases/{case_id}/graph", responses={200: {"model": S.CaseGraph}})
def case_graph(case_id: str) -> dict[str, Any]:
    return _serve("case_graph", f"graph of {case_id}")


@router.get("/cases/{case_id}/timemachine", responses={200: {"model": S.TimeMachine}})
def case_timemachine(case_id: str) -> dict[str, Any]:
    return _serve("timemachine", f"time machine of {case_id}")


@router.get("/cases/{case_id}/claims", responses={200: {"model": S.CaseClaims}})
def case_claims(
    case_id: str, limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)
) -> dict[str, Any]:
    if not use_fixtures():
        raise _live_unavailable(f"claims of {case_id}")
    # No claims fixture exists and claims.csv columns are defined in M1; empty but well-shaped.
    return S.CaseClaims(case_id=case_id, total=0, claims=[]).model_dump()


@router.post("/cases/{case_id}/decision", responses={200: {"model": S.DecisionResponse}})
def case_decision(case_id: str, body: S.DecisionRequest = Body(...)) -> dict[str, Any]:
    if not use_fixtures():
        raise _live_unavailable("decisions")
    return fixture("decision")["response"]


# ---------------------------------------------------------------- entities

@router.get("/entities/{entity_id}/peer_stats", responses={200: {"model": S.PeerStats}})
def peer_stats(entity_id: str) -> dict[str, Any]:
    if not use_fixtures():
        raise _live_unavailable(f"peer stats of {entity_id}")
    items = fixture("case_detail")["peer_context"]
    own = [p for p in items if p["entity_id"] == entity_id] or items
    group = own[0]["peer_group"]
    metrics = [
        S.PeerMetric(
            metric=p["metric"],
            value=p["case_value"],
            peer_median=p["peer_median"],
            peer_p90=p.get("peer_p90"),
            percentile=p["percentile"],
        )
        for p in own
    ]
    return S.PeerStats(entity_id=entity_id, peer_group=group["label"], n=group["n"], metrics=metrics).model_dump()


@router.get("/entities/{entity_id}/neighbors", responses={200: {"model": S.Neighbors}})
def neighbors(entity_id: str, depth: int = 1) -> dict[str, Any]:
    if depth not in (1, 2):
        raise ApiError(422, "invalid_param", f"depth must be 1 or 2, got {depth}")
    if not use_fixtures():
        raise _live_unavailable(f"neighbors of {entity_id}")
    g = fixture("case_graph")
    if not any(n["id"] == entity_id for n in g["nodes"]):
        raise ApiError(404, "not_found", f"{entity_id} is not in the fixture graph")
    keep, frontier = {entity_id}, {entity_id}
    for _ in range(depth):
        nxt = set()
        for e in g["edges"]:
            if e["source"] in frontier:
                nxt.add(e["target"])
            if e["target"] in frontier:
                nxt.add(e["source"])
        frontier = nxt - keep
        keep |= nxt
    nodes = [n for n in g["nodes"] if n["id"] in keep]
    edges = [e for e in g["edges"] if e["source"] in keep and e["target"] in keep]
    return {"entity_id": entity_id, "nodes": nodes, "edges": edges}


# ---------------------------------------------------------------- forecast / documents

@router.get("/forecast/{entity_id}", responses={200: {"model": S.Forecast}})
def forecast(entity_id: str, horizon: int = 30) -> dict[str, Any]:
    _check_horizon(horizon)
    return _serve("forecast", f"forecast of {entity_id}")


@router.get("/documents/{document_id}", responses={200: {"model": S.Document}})
def document(document_id: str) -> dict[str, Any]:
    return _serve("document", f"document {document_id}")


@lru_cache(maxsize=1)
def _placeholder_png() -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (850, 1100), "white")
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, 810, 140], outline="black", width=3)
    d.text((60, 70), "AXON - FIXTURE SCAN PLACEHOLDER (synthetic)", fill="black")
    d.text((60, 180), "Real scans are rendered by the engine in milestone M2.", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@router.get("/files/scans/{document_id}.png", response_class=Response)
def scan(document_id: str) -> Response:
    if use_fixtures():
        return Response(content=_placeholder_png(), media_type="image/png")
    path = CONFIG.raw_dir / "scans" / f"{document_id}.png"
    if not path.is_file():
        raise ApiError(404, "not_found", f"No scan for {document_id}")
    return Response(content=path.read_bytes(), media_type="image/png")


# ---------------------------------------------------------------- feedback / audit / trust

@router.post("/feedback/reset", responses={200: {"model": S.FeedbackReset}})
def feedback_reset() -> dict[str, Any]:
    if not use_fixtures():
        raise _live_unavailable("feedback")
    return S.FeedbackReset(reset=True, weights=dict(CONFIG.METHOD_WEIGHTS)).model_dump()


@router.get("/audit", responses={200: {"model": S.Audit}})
def audit(limit: int = Query(50, ge=1, le=1000)) -> dict[str, Any]:
    return _serve("audit", "the audit log")


@router.get("/trust", responses={200: {"model": S.Trust}})
def trust() -> dict[str, Any]:
    return _serve("trust", "trust metrics")


# ---------------------------------------------------------------- Fraud Twin

@router.get("/twin/scenarios", responses={200: {"model": S.TwinScenarios}})
def twin_scenarios() -> dict[str, Any]:
    return _serve("twin_scenarios", "Twin scenarios")


def _validate_twin_params(scenario: dict[str, Any], params: dict[str, Any]) -> None:
    """Reject unknown params and out-of-range values against the whitelist."""
    spec = scenario["params"]
    for key, val in params.items():
        if key not in spec:
            raise ApiError(422, "invalid_param", f"{scenario['id']} has no param '{key}'")
        p = spec[key]
        t = p["type"]
        if t == "bool":
            ok = isinstance(val, bool)
        elif t == "enum":
            ok = val in p["values"]
        else:
            ok = isinstance(val, (int, float)) and not isinstance(val, bool)
            if ok and t == "int":
                ok = float(val).is_integer()
            if ok:
                ok = p["min"] <= val <= p["max"]
        if not ok:
            raise ApiError(422, "invalid_param", f"{key}={val!r} is outside the allowed range for {scenario['id']}")


@router.post("/twin/run", responses={200: {"model": S.TwinRun}})
def twin_run(body: S.TwinRunRequest = Body(...)) -> dict[str, Any]:
    whitelist = {s["id"]: s for s in fixture("twin_scenarios")["scenarios"]}
    if body.scenario not in whitelist:
        raise ApiError(422, "unsupported_scenario", f"'{body.scenario}' is not in the scenario whitelist")
    _validate_twin_params(whitelist[body.scenario], body.params)
    return _serve("twin_run", "Fraud Twin")


@router.post("/twin/harden", responses={200: {"model": S.TwinHarden}})
def twin_harden(body: S.TwinHardenRequest = Body(...)) -> dict[str, Any]:
    tunables = {t["key"]: t for t in fixture("twin_scenarios")["tunable_params"]}
    t = tunables.get(body.change.param)
    if t is None:
        raise ApiError(422, "invalid_param", f"'{body.change.param}' is not a tunable param")
    if not t["min"] <= body.change.new_value <= t["max"]:
        raise ApiError(422, "invalid_param", f"{body.change.param} must be within [{t['min']}, {t['max']}]")
    return _serve("twin_harden", "Fraud Twin hardening")


@router.get("/twin/runs/{run_id}/cases/{case_id}", responses={200: {"model": S.CaseDetail}})
def twin_case(run_id: str, case_id: str) -> dict[str, Any]:
    return _serve("case_detail", f"sandbox case {case_id} of {run_id}")
