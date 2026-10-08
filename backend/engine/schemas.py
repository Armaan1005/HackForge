"""Pydantic v2 models mirroring contracts/*.json (the API contract, by example).

Every model forbids unknown keys, so a response that drifts from its fixture fails loudly.
Fields that a fixture omits in some items (e.g. peer_context `note`) are optional with a
None default; Part A must still emit the keys the fixture shows. Part B may import these.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

Num = int | float
LayerState = Literal["ok", "unavailable"]
Status = Literal["needs_siu_review", "request_documentation", "monitor", "cleared"]
Direction = Literal["incriminating", "exculpatory", "neutral"]
NodeType = Literal[
    "provider", "member", "member_group", "facility", "owner", "bank",
    "address", "location", "claim", "claim_group",
]
EdgeType = Literal[
    "treated", "referral", "practices_at", "owned_by", "uses_bank",
    "located_at", "lives_at", "shares_phone", "billed", "billed_at",
]
HorizonMap = dict[str, float]  # keys "30", "60", "90"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- shared pieces

class Layers(Strict):
    rules: LayerState
    anomaly: LayerState
    temporal: LayerState
    graph: LayerState


class Source(Strict):
    table: str
    column: str


class GraphNode(Strict):
    id: str
    type: NodeType
    label: str
    risk: Num | None
    flagged: bool
    in_case: bool
    first_seen_month: str
    attrs: dict[str, Any]


class GraphEdge(Strict):
    id: str
    source: str
    target: str
    type: EdgeType
    weight: Num
    first_seen_month: str
    evidence_ids: list[str]


ErrorCode = Literal["not_found", "invalid_param", "unsupported_scenario", "layer_unavailable"]


class Error(Strict):
    code: ErrorCode
    message: str


class ErrorResponse(Strict):
    error: Error


# ---------------------------------------------------------------- health / overview

class Health(Strict):
    status: str
    use_fixtures: bool
    engine_version: str
    layers: Layers


class DateRange(Strict):
    start: str
    end: str


class Funnel(Strict):
    claim_lines: int
    alerts: int
    explained: int
    open_alerts: int
    cases: int
    selected_today: int
    capacity_hours: int


class Overview(Strict):
    synthetic: bool
    seed: int
    sim_today: str
    date_range: DateRange
    currency: Literal["INR"]
    tables: dict[str, int]
    service_types: dict[str, int]
    funnel: Funnel
    exoneration_by_reason: dict[str, int]
    layers: Layers
    engine_version: str
    generated_at: str


# ---------------------------------------------------------------- cleared alerts

class ClearedAlert(Strict):
    alert_id: str
    entity_type: str
    entity_id: str
    entity_name: str
    triggered_by: list[str]
    original_risk: Num
    exoneration_code: str
    facts: dict[str, Any]
    evidence_ids: list[str]
    explanation: str | None


class AlertsCleared(Strict):
    total: int
    limit: int
    offset: int
    items: list[ClearedAlert]


# ---------------------------------------------------------------- case detail

class EntityRef(Strict):
    entity_type: str
    entity_id: str
    name: str


class CaseEntity(Strict):
    entity_type: str
    entity_id: str
    name: str
    role: str
    risk: Num | None


class Scores(Strict):
    risk: Num
    by_method: dict[str, float]
    methods_agreeing: int
    hard_signal: bool


class Money(Strict):
    dollars_at_risk: int
    paid: int
    pending: int
    expected_recovery: int
    projected_monthly_loss: int


class PaymentClock(Strict):
    next_release_date: str | None
    days_until_release: int | None
    pending_claims: int
    pending_amount: int
    hold_recommended: bool
    hold_reason: str | None
    hold_status: str


class MemberHarm(Strict):
    score: float
    members_affected: int
    vulnerable_share: float
    clinical_risk: float
    drivers: list[str]


class Verdict(Strict):
    status: Status
    next_action: str
    next_action_text: str
    reasons: list[str]
    human_approval_required: Literal[True]


class ClaimsSummary(Strict):
    claim_count: int
    amount_min: int
    amount_max: int
    amount_total: int
    under_threshold_share: float
    review_threshold: int
    service_types: dict[str, int]
    procedure_codes: dict[str, int]


class Evidence(Strict):
    evidence_id: str
    type: str
    method: str
    name: str
    description: str
    direction: Direction
    entity_ids: list[str]
    claim_ids: list[str]
    claim_count: int
    value: Num | None
    comparison_value: Num | None
    comparison_label: str | None
    unit: str
    threshold: Num | None
    severity: int
    hard: bool
    weight: float
    sources: list[Source]


class PeerGroup(Strict):
    label: str
    n: int


class PeerContext(Strict):
    evidence_id: str
    metric: str
    entity_id: str
    case_value: Num
    raw_ratio: Num | None = None
    peer_median: Num
    peer_p90: Num | None = None
    percentile: Num | None
    peer_group: PeerGroup
    low_sample: bool
    direction: Direction
    note: str | None = None


class TimelineEvent(Strict):
    date: str
    event_type: str
    description: str
    evidence_ids: list[str]
    claim_ids: list[str]


class NetworkSummary(Strict):
    node_count: int
    edge_count: int
    community_id: str | None
    community_size: int
    flagged_neighbor_share: float
    connected_claims: int


class CaseDocument(Strict):
    document_id: str
    doc_type: str
    format: Literal["json", "scan"]
    claim_ids: list[str]
    path: str
    scan_url: str | None


class MissingDocument(Strict):
    doc_type: str
    claim_ids: list[str]
    claim_count: int
    critical: bool
    why: str


class CaseDetail(Strict):
    case_id: str
    title: str
    pattern: str
    status: str
    currency: Literal["INR"]
    primary_entity: EntityRef
    entities: list[CaseEntity]
    layers: Layers
    scores: Scores
    horizon_risk: HorizonMap
    money: Money
    payment_clock: PaymentClock
    effort_hours: Num
    dead_end_risk: float
    member_harm: MemberHarm
    severity: int
    evidence_strength: Literal["strong", "moderate", "weak"]
    confidence: float
    verdict: Verdict
    claims_summary: ClaimsSummary
    evidence: list[Evidence]
    peer_context: list[PeerContext]
    timeline: list[TimelineEvent]
    network_summary: NetworkSummary
    documents: list[CaseDocument]
    missing_documents: list[MissingDocument]
    limitations: list[str]
    engine_version: str
    generated_at: str


# ---------------------------------------------------------------- graph / time machine

class CaseGraph(Strict):
    case_id: str
    truncated: bool
    node_cap: int
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class Snapshot(Strict):
    month: str
    node_ids: list[str]
    edge_ids: list[str]
    claims_count: int
    amount: int
    risk: Num


class Projection(Strict):
    entity_id: str
    probability: float
    label: str | None = None


class TimeMachine(Strict):
    case_id: str
    months: list[str]
    snapshots: list[Snapshot]
    projection: dict[str, list[Projection]]
    fallback: bool


# ---------------------------------------------------------------- tools for "Ask the Case"

class CaseClaims(Strict):
    case_id: str
    total: int
    claims: list[dict[str, Any]]  # rows of claims.csv


class PeerMetric(Strict):
    metric: str
    value: Num
    peer_median: Num
    peer_p90: Num | None
    percentile: Num | None


class PeerStats(Strict):
    entity_id: str
    peer_group: str
    n: int
    metrics: list[PeerMetric]


class Neighbors(Strict):
    entity_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]


# ---------------------------------------------------------------- forecast

class ForecastDriver(Strict):
    feature: str
    label: str
    value: Num
    peer_median: Num
    contribution: float


class ForecastModel(Strict):
    type: str
    trained_through: str
    holdout: str
    auc_holdout: float
    brier_holdout: float


class Forecast(Strict):
    entity_id: str
    horizon: Literal[30, 60, 90]
    probability: float
    label_definition: str
    top_drivers: list[ForecastDriver]
    all_horizons: HorizonMap
    model: ForecastModel
    limitations: list[str]


# ---------------------------------------------------------------- documents

class BilledProcedure(Strict):
    code: str
    description: str


class DocSection(Strict):
    section_id: str
    heading: str
    text: str
    author_provider_id: str
    created_at: str


class Document(Strict):
    document_id: str
    doc_type: str
    format: Literal["json", "scan"]
    claim_ids: list[str]
    member_id: str
    author_provider_id: str
    facility_id: str | None
    created_at: str
    claim_service_date: str
    claim_submitted_at: str
    billed_procedures: list[BilledProcedure]
    sections: list[DocSection]
    scan_url: str | None


# ---------------------------------------------------------------- queue

class QueueCase(Strict):
    rank: int
    case_id: str
    title: str
    pattern: str
    status: Status
    risk: Num
    dollars_at_risk: int
    expected_recovery: int
    member_harm: float
    severity: int
    evidence_strength: Literal["strong", "moderate", "weak"]
    confidence: float
    effort_hours: Num
    dead_end_risk: float
    recovery_per_hour: int
    priority_score: Num
    horizon_risk: HorizonMap
    days_until_release: int | None
    hold_recommended: bool
    selected: bool
    exploration: bool
    selection_reason: str


class FrontierPoint(Strict):
    hours: Num
    cumulative_recovery: int


class Queue(Strict):
    capacity_hours: int
    horizon: Literal[30, 60, 90]
    currency: Literal["INR"]
    total_cases: int
    eligible_cases: int
    selected_count: int
    hours_used: Num
    exploration_hours_reserved: Num
    expected_recovery_selected: int
    recovery_per_hour: int
    weights: dict[str, float]
    cases: list[QueueCase]
    frontier: list[FrontierPoint]


# ---------------------------------------------------------------- decisions / feedback / audit

class DecisionRequest(Strict):
    action: Literal["confirm", "clear", "need_more_info", "hold_payment"]
    user: str
    note: str | None = None


class WeightChange(Strict):
    method: str
    before: float
    after: float


class DecisionResponse(Strict):
    decision_id: str
    case_id: str
    action: Literal["confirm", "clear", "need_more_info", "hold_payment"]
    user: str
    recorded_at: str
    weight_changes: list[WeightChange]
    queue_changed: bool
    hold_status: str
    audit_id: str


class DecisionFixture(Strict):
    """Shape of contracts/decision.json (request example + response)."""

    request_example: DecisionRequest
    response: DecisionResponse


class FeedbackReset(Strict):
    reset: Literal[True]
    weights: dict[str, float]


class AuditItem(Strict):
    audit_id: str
    ts: str
    actor: str
    event: str
    case_id: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    details: dict[str, Any]


class Audit(Strict):
    total: int
    items: list[AuditItem]


# ---------------------------------------------------------------- Fraud Twin

class ScenarioParam(Strict):
    type: Literal["int", "float", "bool", "enum"]
    default: Any
    min: Num | None = None
    max: Num | None = None
    unit: str | None = None
    values: list[str] | None = None
    description: str | None = None


class Scenario(Strict):
    id: str
    name: str
    description: str
    params: dict[str, ScenarioParam]
    examples: list[str]


class TunableParam(Strict):
    key: str
    current: Num
    min: Num
    max: Num
    description: str
    affects: list[str]


class TwinScenarios(Strict):
    scenarios: list[Scenario]
    tunable_params: list[TunableParam]


class TwinRunRequest(Strict):
    scenario: str
    params: dict[str, Any] = {}
    seed: int = 7


class TwinHardenChange(Strict):
    param: str
    new_value: Num


class TwinHardenRequest(Strict):
    run_id: str
    change: TwinHardenChange


class FalsePositiveRate(Strict):
    baseline: float
    run: float


class MissedClaim(Strict):
    claim_id: str
    reason_code: str
    param_key: str
    threshold: Num
    value: Num
    description: str


class MissReason(Strict):
    reason_code: str
    param_key: str
    count: int
    threshold: Num
    typical_value: Num


class InjectedGraph(Strict):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class TwinRun(Strict):
    run_id: str
    scenario: str
    params: dict[str, Any]
    seed: int
    runtime_ms: int
    sandbox: Literal[True]
    generated: int
    detected: int
    missed: int
    detection_rate: float
    by_layer: dict[str, int]
    false_positive_rate: FalsePositiveRate
    injected_case_ids: list[str]
    missed_claims: list[MissedClaim]
    miss_reason_summary: list[MissReason]
    injected_graph: InjectedGraph
    limitations: list[str]


class HardenChangeApplied(Strict):
    param: str
    old_value: Num
    new_value: Num


class RateSnapshot(Strict):
    detection_rate: float
    false_positive_rate: float


class TwinHarden(Strict):
    run_id: str
    parent_run_id: str
    change: HardenChangeApplied
    applied_to: Literal["sandbox_only"]
    approved_by: str
    scenario: str
    params: dict[str, Any]
    seed: int
    runtime_ms: int
    generated: int
    detected: int
    missed: int
    detection_rate: float
    by_layer: dict[str, int]
    false_positive_rate: FalsePositiveRate
    before: RateSnapshot
    after: RateSnapshot
    injected_case_ids: list[str]
    missed_claims: list[MissedClaim]
    miss_reason_summary: list[MissReason]
    injected_graph: InjectedGraph
    limitations: list[str]


# ---------------------------------------------------------------- trust

class SchemeDetection(Strict):
    scheme_id: str
    name: str
    detected: bool
    claim_recall: float
    inr_planted: int
    inr_caught: int
    case_ids: list[str]


class DetectionOverall(Strict):
    precision: float
    recall: float
    f1: float
    inr_planted: int
    inr_caught: int


class TrustDetection(Strict):
    by_scheme: list[SchemeDetection]
    overall: DetectionOverall


class DecoyItem(Strict):
    decoy_id: str
    entity_id: str
    outcome: str
    by: str | None


class TrustDecoys(Strict):
    total: int
    flagged_needs_review: int
    correctly_defended: int
    items: list[DecoyItem]


class TrustExoneration(Strict):
    alerts_cleared: int
    planted_fraud_wrongly_cleared: int


class CalibrationBin(Strict):
    bin: str
    predicted: float
    observed: float
    n: int


class HorizonMetrics(Strict):
    auc: float
    brier: float
    calibration: list[CalibrationBin]


class FairnessGroup(Strict):
    group: str
    providers: int
    flag_rate: float


class Fairness(Strict):
    by_region: list[FairnessGroup]
    by_size: list[FairnessGroup]
    rural_vs_urban: list[FairnessGroup]
    max_disparity_ratio: float


class GoldenCase(Strict):
    case_id: str
    kind: Literal["fraud", "decoy", "ambiguous"]
    expected: str
    actual: str
    match: bool


class Trust(Strict):
    seed: int
    detection: TrustDetection
    decoys: TrustDecoys
    exoneration: TrustExoneration
    forecast: dict[str, HorizonMetrics]
    fairness: Fairness
    golden_set: list[GoldenCase]
    ai: dict[str, Any] | None  # always null from Part A; Part B fills it
    audit_events: int


# fixture file stem -> model; used by the router and the contract tests
FIXTURE_MODELS: dict[str, type[BaseModel]] = {
    "alerts_cleared": AlertsCleared,
    "audit": Audit,
    "case_detail": CaseDetail,
    "case_graph": CaseGraph,
    "decision": DecisionFixture,
    "document": Document,
    "forecast": Forecast,
    "overview": Overview,
    "queue": Queue,
    "timemachine": TimeMachine,
    "trust": Trust,
    "twin_harden": TwinHarden,
    "twin_run": TwinRun,
    "twin_scenarios": TwinScenarios,
}
