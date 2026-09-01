from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

ApprovalTier = Literal[
    "automatic_candidate", "analyst_approval", "administrator_approval", "prohibited"
]
RecommendationState = Literal[
    "proposed",
    "simulation_pending",
    "simulation_complete",
    "blocked_by_policy",
    "superseded",
    "unavailable",
]


class DefensivePlaybook(BaseModel):
    playbook_id: str
    playbook_version: str
    name: str
    description: str
    action_type: str
    supported_target_types: list[str]
    required_evidence: list[str]
    disqualifying_conditions: list[str]
    topology_mutation_specification: dict[str, object]
    reversibility: str
    default_operational_impact: str
    default_blast_radius: str
    approval_tier: ApprovalTier
    automatic_eligibility: bool
    synthetic: Literal[True] = True
    catalogue_version: str
    resource_cost_weight: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0
    sla_sensitivity_weight: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0


class ResponseAnalyzeRequest(BaseModel):
    model_id: str
    through_sequence_number: Annotated[int | None, Field(ge=1)] = None
    prediction_enabled: bool = True
    top_k: Annotated[int, Field(ge=1, le=10)] = 5
    force_reanalyze: bool = False


class ResponseImpactSimulation(BaseModel):
    simulation_id: str
    recommendation_id: str
    run_id: str
    through_sequence_number: int
    base_topology_version: str
    simulation_engine_version: str
    target_type: str
    target_id: str
    changed_node_ids: list[str]
    changed_edge_ids: list[str]
    paths_before: list[dict[str, object]]
    paths_after: list[dict[str, object]]
    correlated_paths_interrupted: int
    predicted_paths_interrupted: int
    sensitive_assets_reachable_before: int
    sensitive_assets_reachable_after: int
    expected_relationships_affected: int
    affected_asset_count: int
    affected_edge_count: int
    interruption_score: float
    residual_exposure_score: float
    operational_disruption_score: float
    blast_radius: str
    reversibility: str
    approval_tier: ApprovalTier
    warnings: list[str]
    synthetic: Literal[True] = True
    created_at: datetime


class ResponseRecommendation(BaseModel):
    recommendation_id: str
    response_analysis_id: str
    run_id: str
    model_id: str
    incident_candidate_id: str
    prediction_snapshot_id: str | None
    through_sequence_number: int
    playbook_id: str
    playbook_name: str
    target_type: str
    target_id: str
    rank: int
    recommendation_score: float
    component_scores: dict[str, float]
    penalties: dict[str, float]
    defense_score: float
    defense_components: dict[str, float]
    defense_explanation: str
    required_approval_tier: ApprovalTier
    recommendation_state: RecommendationState
    evidence_summary: list[str]
    rationale: str
    warnings: list[str]
    synthetic: Literal[True] = True
    created_at: datetime
    simulation: ResponseImpactSimulation | None = None


class ResponseAnalysisResult(BaseModel):
    response_analysis_id: str
    run_id: str
    model_id: str
    incident_candidate_id: str
    prediction_snapshot_id: str | None
    through_sequence_number: int
    response_engine_version: str
    recommendation_count: int
    recommendations: list[ResponseRecommendation]
    force_reanalyze: bool
    synthetic: Literal[True] = True
    created_at: datetime


class ResponseRecommendationPage(BaseModel):
    items: list[ResponseRecommendation]
    page: int
    page_size: int
    total: int
    pages: int
    synthetic: Literal[True] = True


class ResponseRunSummary(BaseModel):
    run_id: str
    model_id: str
    through_sequence_number: int
    recommendation_count: int
    top_recommendation: ResponseRecommendation | None
    analysis_sequence: int
    synthetic: Literal[True] = True
