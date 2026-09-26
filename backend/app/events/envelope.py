"""Canonical domain event envelope.

Every domain event published on the :class:`~app.events.bus.EventBus` is an
instance of :class:`DomainEvent`, parameterised by a typed payload model.
The envelope fields are stable across all event types so consumers (log
handlers, WebSocket broadcasters, a future cloud event bus) can reason about
identity and correlation without knowing the payload shape.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Generic, Literal, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.events.types import EventType

TPayload = TypeVar("TPayload", bound=BaseModel)


class DomainEvent(BaseModel, Generic[TPayload]):
    """Typed envelope wrapping a domain-specific payload model."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    event_version: int = 1
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str
    run_id: str | None = None
    scenario_id: str | None = None
    incident_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    resource_ids: list[str] = Field(default_factory=list)
    payload: TPayload


# --- Typed payloads for the event types this codebase actually publishes ---


class ScenarioStartedPayload(BaseModel):
    scenario_id: str
    seed: int
    event_count: int


class TelemetryGeneratedPayload(BaseModel):
    run_id: str
    event_count: int


class AnomalyDetectedPayload(BaseModel):
    run_id: str
    model_id: str
    assessment_count: int
    anomalous_count: int


class IncidentCreatedPayload(BaseModel):
    incident_candidate_id: str
    run_id: str
    model_id: str
    priority: str
    evidence_count: int
    technique_ids: list[str]


class PredictionGeneratedPayload(BaseModel):
    run_id: str
    model_id: str
    hypothesis_count: int


class ResponseDecisionPayload(BaseModel):
    orchestration_id: str
    run_id: str
    incident_candidate_id: str
    from_state: str
    to_state: str


class ResponseExecutionPayload(BaseModel):
    orchestration_id: str
    execution_id: str
    execution_state: str
    changed_node_count: int
    changed_edge_count: int


class VerificationCompletedPayload(BaseModel):
    orchestration_id: str
    verification_id: str
    verification_status: str


class RollbackPayload(BaseModel):
    orchestration_id: str
    rollback_id: str
    state: str


class ResourceStateChangedPayload(BaseModel):
    orchestration_id: str
    resource_id: str
    resource_type: str
    new_state: str


class AttackPathDiscoveredPayload(BaseModel):
    path_id: str
    path_type: str
    source_asset_id: str
    target_asset_id: str
    hop_count: int
    score: float


class BlastRadiusAssessedPayload(BaseModel):
    compromised_asset_ids: list[str]
    reachable_count: int
    critical_count: int
    score: float


class RedStepPayload(BaseModel):
    experiment_id: str
    scenario_id: str
    step_sequence: int
    expected_technique_id: str | None
    outcome: str


class PurpleExperimentStartedPayload(BaseModel):
    experiment_id: str
    scenario_id: str
    mode: str
    seed: int


class PurpleStepCompletedPayload(BaseModel):
    experiment_id: str
    step_sequence: int
    outcome: str
    detected: bool


class PurpleExperimentCompletedPayload(BaseModel):
    experiment_id: str
    status: str
    detection_step_coverage: float | None
    final_outcome: str


class ResponsePlanGeneratedPayload(BaseModel):
    incident_candidate_id: str
    candidate_count: int
    playbook_ids: list[str]


class ResponsePlanSimulatedPayload(BaseModel):
    recommendation_id: str
    playbook_id: str
    attack_paths_before: int
    attack_paths_after: int
    blast_radius_reachable_before: int
    blast_radius_reachable_after: int
    response_utility_score: float


class ResponsePlanSelectedPayload(BaseModel):
    incident_candidate_id: str
    selected_recommendation_id: str
    response_utility_score: float
    candidate_count: int


class PolicyEvaluatedPayload(BaseModel):
    policy_id: str
    result: str
    reason: str
    recommendation_id: str


class AutonomyDecisionPayload(BaseModel):
    autonomy_mode: str
    recommendation_id: str
    decision: str
    reason: str


class ApprovalRequiredPayload(BaseModel):
    orchestration_id: str
    required_role: str
    reason: str


class RollbackTriggeredPayload(BaseModel):
    orchestration_id: str
    trigger_reason: str
    security_verified: bool
    operational_verified: bool


# --- Phase 5 (Section 101): additive evaluation-engine lifecycle payloads.
# See the `EVALUATION_*` block in `app.events.types.EventType` for why these
# exist alongside (not instead of) the reconstruction-based Experiment
# Timeline. ---


class EvaluationBatchCreatedPayload(BaseModel):
    batch_id: str
    total_experiments: int
    scenario_ids: list[str]
    seeds: list[int]
    defence_modes: list[str]


class EvaluationExperimentStartedPayload(BaseModel):
    experiment_id: str
    scenario_id: str
    seed: int
    defence_mode: str


class EvaluationDefenceCompletedPayload(BaseModel):
    experiment_id: str
    defence_mode: str
    orchestration_id: str | None
    verification_status: str | None


class EvaluationMetricsComputedPayload(BaseModel):
    experiment_id: str
    ars_total: float | None
    mci: float | None


class EvaluationExperimentCompletedPayload(BaseModel):
    experiment_id: str
    status: str


class EvaluationExperimentFailedPayload(BaseModel):
    experiment_id: str
    failure_stage: str | None
    failure_code: str | None


class EvaluationExportGeneratedPayload(BaseModel):
    export_format: Literal["csv", "json"]
    experiment_count: int
    scenario_id: str | None
    defence_mode: str | None
    seed: int | None
    status: str | None
    batch_id: str | None
