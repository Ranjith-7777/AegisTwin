from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class OrchestrationCreateRequest(BaseModel):
    model_id: str
    incident_candidate_id: str
    selected_recommendation_id: str
    through_sequence_number: int = Field(ge=1)


class AdvanceRequest(BaseModel):
    expected_state: str | None = None


class ApprovalDecisionRequest(BaseModel):
    actor_role: Literal["analyst", "administrator"]
    actor_display_name: str = Field(min_length=3, max_length=120)
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=3, max_length=1000)


class ExecuteRequest(BaseModel):
    expected_state: str | None = None
    failure_mode: Literal[
        "none",
        "stale_topology_state",
        "target_unavailable",
        "conflicting_mutation",
        "policy_changed",
        "injected_simulator_failure",
    ] = "none"


class RollbackRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
    requested_by: str = Field(min_length=3, max_length=120)


class PlanStep(BaseModel):
    plan_step_id: str
    step_number: int
    playbook_id: str
    recommendation_id: str
    target_type: str
    target_id: str
    required_approval_tier: str
    reversibility: str
    rationale: str
    expected_mutation: dict[str, object]
    current_status: str
    synthetic: bool


class AgentDecision(BaseModel):
    agent_decision_id: str
    agent_name: str
    agent_version: str
    decision_type: str
    input_reference_ids: list[str]
    output_summary: str
    decision: str
    ranking_score: float | None
    rationale: str
    warnings: list[str]
    next_agent: str | None
    created_at: datetime
    synthetic: bool


class ApprovalRequestView(BaseModel):
    approval_request_id: str
    plan_step_id: str | None
    required_role: str
    approval_state: str
    requested_at: datetime
    expires_at: datetime | None
    decided_at: datetime | None
    decided_by: str | None
    decision_reason: str | None
    synthetic: bool


class SyntheticExecutionView(BaseModel):
    execution_id: str
    plan_step_id: str
    playbook_id: str
    target_type: str
    target_id: str
    execution_state: str
    started_at: datetime
    completed_at: datetime | None
    mutation_summary: dict[str, object]
    changed_node_ids: list[str]
    changed_edge_ids: list[str]
    simulated_failure_reason: str | None
    reversible: bool
    synthetic: bool


class VerificationView(BaseModel):
    verification_id: str
    execution_id: str
    verification_status: str
    metrics: dict[str, object]
    unintended_effects: list[str]
    started_at: datetime
    completed_at: datetime
    synthetic: bool


class RollbackView(BaseModel):
    rollback_id: str
    execution_id: str
    reason: str
    requested_by: str
    state: str
    restored_state_reference: str | None
    verification_summary: dict[str, object]
    synthetic: bool


class AuditEventView(BaseModel):
    audit_event_id: str
    sequence_number: int
    event_type: str
    actor_type: str
    actor_id: str
    actor_display_name: str
    previous_event_hash: str
    event_hash: str
    canonical_payload: dict[str, object]
    created_at: datetime
    synthetic: bool


class AuditIntegrity(BaseModel):
    valid: bool
    event_count: int
    first_invalid_sequence: int | None = None
    algorithm: str = "SHA-256 canonical-json-chain-v1"
    synthetic: bool = True


class OrchestrationView(BaseModel):
    orchestration_id: str
    simulation_run_id: str
    model_id: str
    incident_candidate_id: str
    through_sequence_number: int
    orchestration_version: str
    current_state: str
    selected_recommendation_id: str
    required_approval_tier: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    plan_steps: list[PlanStep]
    decisions: list[AgentDecision]
    approvals: list[ApprovalRequestView]
    executions: list[SyntheticExecutionView]
    verifications: list[VerificationView]
    rollback: RollbackView | None
    synthetic: bool


class OrchestrationPage(BaseModel):
    items: list[OrchestrationView]
    total: int
    synthetic: bool = True
