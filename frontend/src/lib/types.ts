// Shapes mirror contracts/*.json (Part A) and backend/genai (Part B).

export type Status = 'needs_siu_review' | 'request_documentation' | 'monitor' | 'cleared' | string;
export type Strength = 'strong' | 'moderate' | 'weak' | string;
export type Horizon = 30 | 60 | 90;

export interface Source { table: string; column: string }

export interface Evidence {
  evidence_id: string; type: string; method: string; name: string; description: string;
  direction: 'incriminating' | 'exculpatory' | 'neutral' | string;
  entity_ids: string[]; claim_ids: string[]; claim_count: number;
  value: number | null; comparison_value: number | null; comparison_label: string | null; unit: string;
  threshold: number | null; severity: number; hard: boolean; weight: number; sources: Source[];
}

export interface PeerContext {
  evidence_id: string; metric: string; entity_id: string; case_value: number; raw_ratio?: number;
  peer_median: number | null; peer_p90?: number | null; percentile: number | null;
  peer_group: { label: string; n: number }; low_sample: boolean; direction: string; note?: string;
}

export interface CaseDetail {
  case_id: string; title: string; pattern: string; status: string; currency: string; fixture_sample?: boolean;
  primary_entity: { entity_type: string; entity_id: string; name: string };
  entities: { entity_type: string; entity_id: string; name: string; role: string; risk: number | null }[];
  layers: Record<string, string>;
  scores: { risk: number; by_method: Record<string, number>; methods_agreeing: number; hard_signal: boolean };
  horizon_risk: Record<string, number>;
  money: { dollars_at_risk: number; paid: number; pending: number; expected_recovery: number; projected_monthly_loss: number };
  payment_clock: { next_release_date: string | null; days_until_release: number | null; pending_claims: number; pending_amount: number; hold_recommended: boolean; hold_reason: string; hold_status: string };
  effort_hours: number; dead_end_risk: number;
  member_harm: { score: number; members_affected: number; vulnerable_share: number; clinical_risk: number; drivers: string[] };
  severity: number; evidence_strength: Strength; confidence: number;
  verdict: { status: Status; next_action: string; next_action_text: string; reasons: string[]; human_approval_required: boolean };
  claims_summary: { claim_count: number; amount_min: number; amount_max: number; amount_total: number; under_threshold_share: number; review_threshold: number; service_types: Record<string, number>; procedure_codes: Record<string, number> };
  evidence: Evidence[]; peer_context: PeerContext[];
  timeline: { date: string; event_type: string; description: string; evidence_ids: string[]; claim_ids: string[] }[];
  network_summary: { node_count: number; edge_count: number; community_id: string; community_size: number; flagged_neighbor_share: number; connected_claims: number };
  documents: { document_id: string; doc_type: string; format: string; claim_ids: string[]; path: string; scan_url: string | null }[];
  missing_documents: { doc_type: string; claim_ids: string[]; claim_count: number; critical: boolean; why: string }[];
  limitations: string[];
}

export interface QueueCase {
  rank: number; case_id: string; title: string; pattern: string; status: Status; risk: number;
  dollars_at_risk: number; expected_recovery: number; member_harm: number; severity: number;
  evidence_strength: Strength; confidence: number; effort_hours: number; dead_end_risk: number;
  recovery_per_hour: number; priority_score: number; horizon_risk: Record<string, number>;
  days_until_release: number | null; hold_recommended: boolean; selected: boolean; exploration: boolean; selection_reason: string;
}

export interface Queue {
  capacity_hours: number; horizon: number; currency: string; total_cases: number; eligible_cases: number;
  selected_count: number; hours_used: number; exploration_hours_reserved: number;
  expected_recovery_selected: number; recovery_per_hour: number; weights: Record<string, number>;
  cases: QueueCase[]; frontier: { hours: number; cumulative_recovery: number }[];
}

export interface GNode { id: string; type: string; label: string; risk: number | null; flagged: boolean; in_case: boolean; first_seen_month: string; attrs: Record<string, unknown> }
export interface GEdge { id: string; source: string; target: string; type: string; weight: number; first_seen_month: string; evidence_ids: string[] }
export interface Graph { case_id: string; truncated: boolean; node_cap: number; nodes: GNode[]; edges: GEdge[] }

export interface TimeMachine {
  case_id: string; months: string[];
  snapshots: { month: string; node_ids: string[]; edge_ids: string[]; claims_count: number; amount: number; risk: number }[];
  projection: Record<string, { entity_id: string; probability: number; label?: string }[]>;
}

export interface Argument {
  point: string; evidence_ids: string[]; metric: string; case_value: number; comparison_value: number;
  comparison_label: string; strength: Strength; verified?: boolean;
}
export interface Rule { id: string; kind: 'payer_rule' | 'law'; title: string; text: string; source: string; verify: boolean; cited: boolean }
export interface Court {
  case_id: string;
  prosecution: { arguments: Argument[]; source: string };
  defense: { arguments: Argument[]; missing_evidence: string[]; source: string };
  verdict: { status: Status; status_label: string; next_action: string; next_action_text: string; confidence: number; evidence_strength: Strength; summary: string; human_approval_required: boolean; source: string };
  verifier: { checked: number; kept: number; dropped: number; dropped_items: { agent: string; point: string; reason: string }[] };
  ai: { model: string; enabled: boolean; notes: string[]; pending?: boolean };
  rules?: Rule[];
  generated_at: string;
}

export interface Flag {
  flag_id: string; section_id: string; check: string; observation: string; confidence: number;
  evidence_ids: string[]; source: 'code' | 'ai' | string; label: string;
}
export interface DocRecord {
  document_id: string; doc_type: string; format: string; claim_ids: string[]; member_id: string; author_provider_id: string;
  created_at: string; claim_service_date?: string; claim_submitted_at?: string;
  billed_procedures?: { code: string; description: string }[];
  sections: { section_id: string; heading: string; text: string; author_provider_id: string; created_at: string }[];
  scan_url: string | null;
}
export interface Forensics {
  case_id: string; injection_detected: boolean; affects_score: false;
  documents: { document: DocRecord; document_id: string; integrity_flags: Flag[]; injection_detected: boolean; overall_note: string; source: string; note?: string | null }[];
}

export interface TwinScenarioSpec {
  id: string; name: string; description: string; examples: string[];
  params: Record<string, { type: string; min?: number; max?: number; default: unknown; values?: string[]; unit?: string; description?: string }>;
}
export interface Tunable { key: string; current: number; min: number; max: number; description: string; affects: string[] }
export interface TwinRun {
  run_id: string; scenario: string; params: Record<string, unknown>; seed: number; runtime_ms: number;
  generated: number; detected: number; missed: number; detection_rate: number; by_layer: Record<string, number>;
  false_positive_rate: { baseline: number; run: number }; injected_case_ids: string[];
  missed_claims: { claim_id: string; reason_code: string; param_key: string; threshold: number; value: number; description: string }[];
  miss_reason_summary: { reason_code: string; param_key: string; count: number; threshold: number; typical_value: number }[];
  injected_graph: { nodes: GNode[]; edges: GEdge[] }; limitations: string[];
  before?: { detection_rate: number; false_positive_rate: number }; after?: { detection_rate: number; false_positive_rate: number };
  change?: { param: string; old_value: number; new_value: number };
}

export interface AiStatus {
  enabled: boolean; mode: string; model: string; queue_depth: number; calls_this_minute: number; rpm_limit: number;
  calls: number; cache_hits: number; failures: number; use_fixtures: boolean;
  verifier: { statements_checked: number; kept: number; uncited_blocked: number; numbers_blocked: number };
}
