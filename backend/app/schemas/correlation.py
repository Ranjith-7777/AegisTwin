from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class CorrelationAnalyzeRequest(BaseModel):
    model_id: str
    force_reanalyze: bool = False


class MitreTechnique(BaseModel):
    technique_id: str
    name: str
    tactics: list[str]
    description: str
    mapping_conditions: str
    catalogue_version: str
    source_name: str
    reference_date: str
    synthetic_demo_applicable: bool
    synthetic: Literal[True] = True


class TechniqueObservation(BaseModel):
    mapping_id: str
    technique_id: str
    technique_name: str
    simulation_run_id: str
    model_id: str
    event_id: str
    sequence_number: int
    mapping_confidence: float
    evidence_fields: dict[str, object]
    rationale: str
    tactic: str
    mapper_version: str
    synthetic: Literal[True] = True


class IncidentEvidence(BaseModel):
    evidence_id: str
    incident_candidate_id: str
    event_id: str
    assessment_id: str | None
    technique_mapping_id: str | None
    sequence_number: int
    evidence_type: str
    contribution_score: float
    rationale: str
    synthetic: Literal[True] = True


class IncidentCandidate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    incident_candidate_id: str
    simulation_run_id: str
    model_id: str
    title: str
    summary: str
    correlation_state: str
    priority: str
    correlation_score: float
    component_scores: dict[str, float]
    first_sequence_number: int
    latest_sequence_number: int
    first_observed_at: datetime
    latest_observed_at: datetime
    primary_user_id: str | None
    primary_device_id: str | None
    involved_asset_ids: list[str]
    observed_tactic_ids: list[str]
    observed_technique_ids: list[str]
    evidence_count: int
    correlation_engine_version: str
    synthetic: Literal[True] = True
    created_at: datetime
    updated_at: datetime


class CorrelationAnalysisResult(BaseModel):
    simulation_run_id: str
    model_id: str
    incident_candidate_id: str | None
    technique_observation_count: int
    evidence_count: int
    snapshot_count: int
    correlation_engine_version: str
    force_reanalyze: bool
    synthetic: Literal[True] = True


class IncidentPage(BaseModel):
    items: list[IncidentCandidate]
    page: int
    page_size: int
    total: int
    pages: int


class TechniqueObservationPage(BaseModel):
    items: list[TechniqueObservation]
    page: int
    page_size: int
    total: int
    pages: int
