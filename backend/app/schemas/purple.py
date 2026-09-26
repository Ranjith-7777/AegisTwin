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


class PurpleAttackPathContext(BaseModel):
    """The real top-ranked `AttackGraphService` path relevant to this
    experiment (from the scenario's structured `initial_access_point` to
    its `high_value_objective` — see `app/schemas/red_scenario.py`).
    `path_type` is `observed` only when the run actually produced
    anomalous-observed evidence; otherwise it honestly falls back to
    `potential` rather than fabricating observed evidence. See
    docs/architecture/PURPLE_TEAM.md "Attack Graph integration"."""

    path_type: str
    source_asset_id: str
    target_asset_id: str
    hop_count: int
    score: float
    statement: str
    through_sequence_number: int | None
    synthetic: Literal[True] = True


class PurpleBlastRadiusContext(BaseModel):
    """The real `BlastRadiusService` estimate rooted at whatever assets
    were actually anomalous-observed during the run (falling back to the
    scenario's `initial_access_point` if none were). `reachable_count`,
    `critical_assets_at_risk`, and `trust_zones_reached` describe assets
    that are AT RISK / REACHABLE from the compromised set — never a claim
    that they were actually reached. See
    docs/architecture/PURPLE_TEAM.md "Blast Radius integration"."""

    compromised_asset_ids: list[str]
    reachable_count: int
    critical_assets_at_risk: list[str]
    trust_zones_reached: list[str]
    score: float
    mode: Literal["hypothetical", "evidence_bound"]
    through_sequence_number: int | None
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
    """Assets that were actually OBSERVED/REACHED per real telemetry
    evidence (anomalous-observed) AND are critical - never merely
    reachable. See `critical_assets_at_risk` on `attack_path_context` /
    `blast_radius_context` for the separate, broader AT-RISK/REACHABLE
    notion."""
    attack_path_context: PurpleAttackPathContext | None
    blast_radius_context: PurpleBlastRadiusContext | None
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
