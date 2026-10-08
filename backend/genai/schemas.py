"""Structured outputs the Gemini agents must return (also used as response_schema)."""
from typing import Literal

from pydantic import BaseModel, Field

Strength = Literal["strong", "moderate", "weak"]


class Argument(BaseModel):
    point: str = Field(description="One sentence that states the case value AND a comparison, with the peer group")
    evidence_ids: list[str] = Field(description="1+ evidence_id values copied exactly from the evidence JSON")
    metric: str
    case_value: float
    comparison_value: float
    comparison_label: str
    strength: Strength


class ProsecutionOut(BaseModel):
    arguments: list[Argument]


class DefenseOut(BaseModel):
    arguments: list[Argument]
    missing_evidence: list[str] = Field(description="Documents or facts that would resolve the doubt")


class VerdictOut(BaseModel):
    summary: str = Field(description="2-3 plain sentences. Must not change the given status or next action.")
    evidence_ids: list[str]


class BriefPoint(BaseModel):
    text: str
    evidence_ids: list[str]


class BriefOut(BaseModel):
    executive_summary: str
    key_findings: list[BriefPoint]
    alternative_explanations: list[BriefPoint]
    network_context: str
    timeline_narrative: str
    recommended_action: str


ForensicCheck = Literal[
    "inserted_content", "unlinked_author", "phantom_result", "timeline_conflict",
    "procedure_absent", "templated_values", "style_shift", "signature_reuse", "prompt_injection", "other",
]


class ForensicFlagOut(BaseModel):
    section_id: str
    check: ForensicCheck
    observation: str = Field(description="What looks inconsistent, in one sentence. Observations only, no conclusions.")
    confidence: float = Field(description="0 to 1")


class ForensicsOut(BaseModel):
    flags: list[ForensicFlagOut]
    overall_note: str


class ScenarioParam(BaseModel):
    name: str
    value: str


class ScenarioOut(BaseModel):
    supported: bool
    scenario: str
    params: list[ScenarioParam]
    reason: str


class HardeningOut(BaseModel):
    param: str
    new_value: float
    explanation: str


class ClearedLine(BaseModel):
    alert_id: str
    text: str


class ClearedOut(BaseModel):
    items: list[ClearedLine]


class AskOut(BaseModel):
    answer: str
    evidence_ids: list[str]
    insufficient: bool = Field(description="true if the evidence cannot answer the question")
