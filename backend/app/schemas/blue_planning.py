"""Phase 4 Blue response planning: candidate-plan comparison, what-if
Digital Twin simulation, the Response Utility Score, and Decision
Confidence. See docs/architecture/BLUE_RESPONSE_PLANNING.md.

Terminology (see docs, "Confidence terminology"): `ResponseUtilityScore`
ranks CANDIDATE PLANS against each other; `DecisionConfidence` is a
deterministic EVIDENCE-QUALITY indicator for the selected plan, never a
calibrated probability. Neither is "AI confidence".
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SecurityGainEvidence(BaseModel):
    """Before/after values are always real Attack Graph/Blast Radius
    recomputations over a hypothetical (never persisted) graph exclusion -
    see `blue_planning_service._what_if`."""

    attack_paths_before: int
    attack_paths_after: int
    top_attack_path_score_before: float
    top_attack_path_score_after: float
    critical_targets_reachable_before: int
    critical_targets_reachable_after: int
    blast_radius_reachable_before: int
    blast_radius_reachable_after: int
    blast_radius_critical_before: int
    blast_radius_critical_after: int
    security_gain: float


class ResponseUtilityScoreBreakdown(BaseModel):
    """See docs/architecture/BLUE_RESPONSE_PLANNING.md "Response Utility
    Score" for the exact formula. This is a plan-ranking utility score,
    NOT a machine-learning probability."""

    security_gain: float
    critical_asset_protection: float
    blast_radius_reduction: float
    evidence_quality: float
    reversibility_bonus: float
    operational_impact_penalty: float
    total: float


class CandidatePlanAssessment(BaseModel):
    recommendation_id: str
    playbook_id: str
    playbook_name: str
    action_type: str
    target_type: str
    target_id: str
    required_approval_tier: str
    reversibility: str
    operational_impact: str
    security_gain_evidence: SecurityGainEvidence
    utility_score: ResponseUtilityScoreBreakdown
    policy_pass: bool
    policy_failed_ids: list[str]
    recommended: bool
    synthetic: Literal[True] = True


class DecisionConfidence(BaseModel):
    """A deterministic evidence-quality score, NOT a calibrated
    probability - see docs/architecture/BLUE_RESPONSE_PLANNING.md
    "Decision confidence"."""

    anomaly_evidence: float
    incident_coherence: float
    technique_diversity: float
    attack_path_corroboration: float
    response_simulation_improvement: float
    total: float
    note: str = "This is a deterministic evidence-quality score, not a calibrated probability."
    synthetic: Literal[True] = True


class PlanComparisonResult(BaseModel):
    simulation_run_id: str
    model_id: str
    incident_candidate_id: str
    through_sequence_number: int
    autonomy_mode: str
    candidates: list[CandidatePlanAssessment]
    recommended_recommendation_id: str | None
    decision_confidence: DecisionConfidence | None
    synthetic: Literal[True] = True
