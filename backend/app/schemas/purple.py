"""Purple Team experiment schemas.

A Purple Team experiment orchestrates EXISTING pipeline services
(simulation, detection, correlation, prediction, and — in DEFENSE_ENABLED
mode — response/orchestration) against one Red scenario and records what
happened at each step. It introduces no new detection or response logic —
see docs/architecture/PURPLE_TEAM.md.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel


class PurpleExperimentMode(StrEnum):
    OBSERVE_ONLY = "observe_only"
    DEFENSE_ENABLED = "defense_enabled"


class RedStepOutcome(StrEnum):
    """See docs/architecture/PURPLE_TEAM.md "Step outcome semantics" — in
    particular, detection is never treated as prevention."""

    ATTEMPTED = "attempted"
    SUCCEEDED_SYNTHETIC = "succeeded_synthetic"
    FAILED_PRECONDITION = "failed_precondition"
    BLOCKED_SYNTHETIC = "blocked_synthetic"
    SKIPPED = "skipped"


class PurpleTeamExperimentCreate(BaseModel):
    scenario_id: str
    mode: PurpleExperimentMode = PurpleExperimentMode.OBSERVE_ONLY
    seed: int = 84
    top_k: int = 3


class PurpleTeamStepResult(BaseModel):
    step_result_id: str
    experiment_id: str
    step_sequence: int
    description: str
    event_id: str | None
    target_asset_id: str | None
    expected_technique_id: str | None
    expected_technique_name: str | None
    outcome: RedStepOutcome
    detected: bool
    anomaly_score: float | None
    classification: str | None
    observed_technique_ids: list[str]
    incident_candidate_id: str | None
    response_recommendation_id: str | None
    orchestration_id: str | None
    orchestration_state: str | None
    synthetic: Literal[True] = True


class PurpleTeamSummary(BaseModel):
    """See docs/architecture/PURPLE_TEAM.md "Metric definitions" for exact formulas."""

    total_steps: int
    attempted_steps: int
    succeeded_synthetic_steps: int
    detected_steps: int
    missed_steps: int
    expected_detectable_steps: int
    detection_step_coverage: float | None
    mitre_techniques_exercised: list[str]
    mitre_techniques_observed: list[str]
    incident_created: bool
    first_detection_sequence: int | None
    response_recommendation_created: bool
    response_executed: bool
    verification_result: str | None
    critical_assets_reached: list[str]
    estimated_blast_radius_count: int | None
    final_outcome: str


class PurpleTeamExperiment(BaseModel):
    experiment_id: str
    scenario_id: str
    scenario_name: str
    mode: PurpleExperimentMode
    seed: int
    simulation_run_id: str | None
    model_id: str | None
    status: Literal["pending", "running", "completed", "failed"]
    error: str | None
    created_at: datetime
    completed_at: datetime | None
    steps: list[PurpleTeamStepResult]
    summary: PurpleTeamSummary | None
    synthetic: Literal[True] = True


class RedScenarioTechniqueSummary(BaseModel):
    step_sequence: int
    technique_id: str | None
    technique_name: str | None
    tactic: str | None
    rationale: str


class RedScenarioSummary(BaseModel):
    scenario_id: str
    name: str
    description: str
    is_red_agent_scenario: bool
    step_count: int
    mitre_technique_ids: list[str]
    step_techniques: list[RedScenarioTechniqueSummary]
    synthetic: Literal[True] = True
