from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class PredictionAnalyzeRequest(BaseModel):
    model_id: str
    force_reanalyze: bool = False
    top_k: Annotated[int, Field(ge=1, le=5)] = 3


class PredictionHypothesis(BaseModel):
    hypothesis_id: str
    prediction_snapshot_id: str
    rank: int
    hypothesis_type: str
    predicted_technique_id: str | None
    predicted_technique_name: str | None
    predicted_tactic: str | None
    predicted_asset_id: str | None
    predicted_objective: str | None
    prediction_score: float
    component_scores: dict[str, float]
    prerequisite_evidence: list[str]
    contradictory_evidence: list[str]
    rationale: str
    synthetic: Literal[True] = True


class PredictionSnapshot(BaseModel):
    prediction_snapshot_id: str
    simulation_run_id: str
    model_id: str
    incident_candidate_id: str | None
    through_sequence_number: int
    predictor_version: str
    progression_catalogue_version: str
    prediction_state: str
    current_stage_estimate: str
    current_tactic_estimate: str
    observed_technique_ids: list[str]
    observed_tactic_ids: list[str]
    candidate_hypothesis_count: int
    insufficient_evidence_reason: str | None
    supporting_evidence: list[str]
    hypotheses: list[PredictionHypothesis] = Field(default_factory=list)
    synthetic: Literal[True] = True
    created_at: datetime


class PredictionAnalysisResult(BaseModel):
    simulation_run_id: str
    model_id: str
    snapshot_count: int
    hypothesis_count: int
    predictor_version: str
    progression_catalogue_version: str
    top_k: int
    force_reanalyze: bool
    synthetic: Literal[True] = True


class PredictionSnapshotPage(BaseModel):
    items: list[PredictionSnapshot]
    page: int
    page_size: int
    total: int
    pages: int


class PredictionEvaluation(BaseModel):
    evaluation_id: str
    simulation_run_id: str
    model_id: str
    predictor_version: str
    metrics: dict[str, object]
    baseline_metrics: dict[str, object]
    truth_manifest_version: str
    synthetic: Literal[True] = True
    created_at: datetime
