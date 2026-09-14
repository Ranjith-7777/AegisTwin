"""Unit tests for the Aegis Resilience Score (ARS) - Phase 5 Stage 3.

These construct `ExperimentMetricRecord`-shaped inputs directly (never a
full end-to-end experiment) so they stay fast and exercise
`compute_score` in isolation, per the Stage 3 brief's "easy to unit test
independently" requirement.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime

from app.database.models import ExperimentMetricRecord
from app.services.evaluation.mission_continuity_service import MissionContinuitySnapshot
from app.services.evaluation.resilience_score_service import (
    ARS_VERSION,
    PILLAR_WEIGHTS,
    compute_score,
)


def _metric(value: float | bool | None, applicable: bool = True) -> dict[str, object]:
    return {"value": value, "applicable": applicable, "note": None}


def _na(note: str = "not applicable") -> dict[str, object]:
    return {"value": None, "applicable": False, "note": note}


def _record(
    *,
    detection_coverage: dict[str, object] | None = None,
    detection_timeliness: dict[str, object] | None = None,
    attack_path_reduction: dict[str, object] | None = None,
    blast_radius_reduction: dict[str, object] | None = None,
    critical_exposure_reduction: dict[str, object] | None = None,
    recovery_timeliness: dict[str, object] | None = None,
    operational_disruption: float = 0.2,
    verification_success: bool | None = True,
    rollback_success: bool | None = None,
) -> ExperimentMetricRecord:
    normalized = {
        "detection_coverage": detection_coverage or _metric(0.8),
        "detection_timeliness": detection_timeliness or _metric(0.7),
        "attack_path_reduction": attack_path_reduction or _metric(0.6),
        "blast_radius_reduction": blast_radius_reduction or _metric(0.5),
        "critical_exposure_reduction": critical_exposure_reduction or _metric(0.5),
        "false_positive_rate": _metric(0.1),
        "recovery_timeliness": recovery_timeliness or _metric(0.9),
    }
    raw = {
        "operational_disruption": operational_disruption,
        "verification_success": verification_success,
        "rollback_success": rollback_success,
    }
    return ExperimentMetricRecord(
        experiment_id="exp-1",
        metrics_version="aegis-evaluation-metrics-v1",
        logical_timeline_json={},
        computation_latency_json={},
        raw_metrics_json=raw,
        normalized_metrics_json=normalized,
        computed_at=datetime.now(UTC),
        synthetic=True,
    )


FULL_MISSION = MissionContinuitySnapshot(critical_mission_health=0.9, applicable=True)
NA_MISSION = MissionContinuitySnapshot(critical_mission_health=None, applicable=False)


def test_score_always_in_0_100() -> None:
    for coverage in (0.0, 0.25, 0.5, 0.75, 1.0):
        record = _record(detection_coverage=_metric(coverage))
        result = compute_score(record, FULL_MISSION)
        assert result.total is not None
        assert 0.0 <= result.total <= 100.0


def test_higher_detection_coverage_gives_higher_threat_awareness() -> None:
    low = compute_score(_record(detection_coverage=_metric(0.2)), FULL_MISSION)
    high = compute_score(_record(detection_coverage=_metric(0.9)), FULL_MISSION)
    assert low.pillars["A"].value is not None
    assert high.pillars["A"].value is not None
    assert high.pillars["A"].value > low.pillars["A"].value
    assert high.total is not None
    assert low.total is not None
    assert high.total > low.total


def test_better_attack_path_reduction_gives_higher_withstand() -> None:
    low = compute_score(_record(attack_path_reduction=_metric(0.1)), FULL_MISSION)
    high = compute_score(_record(attack_path_reduction=_metric(0.9)), FULL_MISSION)
    assert low.pillars["W"].value is not None
    assert high.pillars["W"].value is not None
    assert high.pillars["W"].value > low.pillars["W"].value


def test_better_critical_exposure_reduction_gives_higher_withstand() -> None:
    low = compute_score(_record(critical_exposure_reduction=_metric(0.0)), FULL_MISSION)
    high = compute_score(_record(critical_exposure_reduction=_metric(1.0)), FULL_MISSION)
    assert low.pillars["W"].value is not None
    assert high.pillars["W"].value is not None
    assert high.pillars["W"].value > low.pillars["W"].value


def test_higher_operational_disruption_gives_lower_mission_preservation() -> None:
    low_disruption = compute_score(_record(operational_disruption=0.0), FULL_MISSION)
    high_disruption = compute_score(_record(operational_disruption=0.8), FULL_MISSION)
    assert low_disruption.pillars["M"].value is not None
    assert high_disruption.pillars["M"].value is not None
    assert low_disruption.pillars["M"].value > high_disruption.pillars["M"].value


def test_failed_verification_gives_lower_verified_recovery() -> None:
    verified = compute_score(
        _record(verification_success=True, rollback_success=None), FULL_MISSION
    )
    failed = compute_score(
        _record(verification_success=False, rollback_success=False), FULL_MISSION
    )
    assert verified.pillars["R"].value is not None
    assert failed.pillars["R"].value is not None
    assert verified.pillars["R"].value > failed.pillars["R"].value


def test_slower_recovery_gives_lower_verified_recovery() -> None:
    fast = compute_score(_record(recovery_timeliness=_metric(0.95)), FULL_MISSION)
    slow = compute_score(_record(recovery_timeliness=_metric(0.1)), FULL_MISSION)
    assert fast.pillars["R"].value is not None
    assert slow.pillars["R"].value is not None
    assert fast.pillars["R"].value > slow.pillars["R"].value


def test_within_pillar_na_redistribution_is_correct() -> None:
    """detection_coverage is N/A -> A = 1.00 * DetectionTimeliness (weight
    fully redistributed to the one remaining applicable submetric).
    With detection_timeliness=0.7: A should be exactly 0.7 (hand-computed:
    0.40/(0.40) * 0.7 = 0.7)."""

    record = _record(detection_coverage=_na(), detection_timeliness=_metric(0.7))
    result = compute_score(record, FULL_MISSION)
    assert result.pillars["A"].applicable is True
    assert result.pillars["A"].value == 0.7


def test_whole_pillar_na_renormalizes_top_level() -> None:
    """Both A submetrics N/A -> pillar A is wholly inapplicable, so ARS
    renormalizes across W, M, R only:

        ARS = 100 * (0.35*W + 0.25*M + 0.20*R) / (0.35 + 0.25 + 0.20)

    Hand-computed with W=0.55 (0.40*0.6+0.30*0.5+0.30*0.5), M=0.84
    (0.60*0.9 + 0.40*(1-0.2)=0.54+0.32=0.86 - recompute below), R=0.94
    (0.60*1.0+0.40*0.9=0.6+0.36=0.96) using this test's fixture defaults
    (attack_path_reduction=0.6, blast_radius_reduction=0.5,
    critical_exposure_reduction=0.5, operational_disruption=0.2,
    critical_mission_health=0.9, verification_success=True,
    recovery_timeliness=0.9):

        W = 0.40*0.6 + 0.30*0.5 + 0.30*0.5 = 0.24 + 0.15 + 0.15 = 0.54
        M = 0.60*0.9 + 0.40*(1-0.2) = 0.54 + 0.32 = 0.86
        R = 0.60*1.0 + 0.40*0.9 = 0.60 + 0.36 = 0.96
        renormalized_total_weight = 0.35 + 0.25 + 0.20 = 0.80
        ARS = 100 * (0.35*0.54 + 0.25*0.86 + 0.20*0.96) / 0.80
            = 100 * (0.189 + 0.215 + 0.192) / 0.80
            = 100 * 0.596 / 0.80 = 74.5
    """

    record = _record(detection_coverage=_na(), detection_timeliness=_na())
    result = compute_score(record, FULL_MISSION)
    assert result.pillars["A"].applicable is False
    assert result.pillars["A"].value is None
    assert result.effective_pillar_weights["A"] == 0.0
    assert result.total is not None
    assert result.total == 74.5


def test_verified_recovery_never_na() -> None:
    # Even the bleakest case (nothing ever attempted/verified/recovered,
    # as for no_active_defence) must leave R applicable with V=0.0, not N/A.
    record = _record(
        verification_success=None,
        rollback_success=None,
        recovery_timeliness=_metric(0.0, applicable=True),
    )
    result = compute_score(record, FULL_MISSION)
    assert result.pillars["R"].applicable is True
    assert result.pillars["R"].value == 0.0


def test_signature_has_no_strategy_parameter() -> None:
    """Structural proof of strategy-neutrality: `compute_score`'s
    parameters can never carry a defence-mode/autonomy-mode/experiment
    identifier - neither its own parameter names nor the field names of
    either parameter type mention strategy at all."""

    signature = inspect.signature(compute_score)
    parameter_names = set(signature.parameters)
    assert parameter_names == {"metrics", "mission_continuity"}
    for banned in ("defence_mode", "autonomy_mode", "experiment", "session"):
        assert banned not in parameter_names

    metric_fields = set(ExperimentMetricRecord.__mapper__.columns.keys())
    assert "defence_mode" not in metric_fields
    assert "autonomy_mode" not in metric_fields

    snapshot_fields = {f.name for f in MissionContinuitySnapshot.__dataclass_fields__.values()}
    assert "defence_mode" not in snapshot_fields
    assert "autonomy_mode" not in snapshot_fields


def test_identical_metrics_produce_identical_score() -> None:
    """Two calls with identical metric inputs always produce an identical
    score, regardless of any surrounding experiment context - there is no
    hidden global state `compute_score` could be reading."""

    record_a = _record()
    record_b = _record()
    result_a = compute_score(record_a, FULL_MISSION)
    result_b = compute_score(record_b, FULL_MISSION)
    assert result_a.total == result_b.total
    for name in PILLAR_WEIGHTS:
        assert result_a.pillars[name].value == result_b.pillars[name].value


def test_decomposition_sums_correctly_using_effective_weights() -> None:
    record = _record()
    result = compute_score(record, FULL_MISSION)
    assert result.total is not None
    recomputed = 100.0 * sum(
        (result.pillars[name].value or 0.0) * result.effective_pillar_weights[name]
        for name in PILLAR_WEIGHTS
        if result.pillars[name].applicable
    )
    assert round(recomputed, 6) == round(result.total, 6)
    assert round(sum(result.effective_pillar_weights.values()), 6) == 1.0


def test_version_fields_present_and_equal_documented_constants() -> None:
    assert ARS_VERSION == "aegis-resilience-score-v1"
    result = compute_score(_record(), FULL_MISSION)
    assert result.version == ARS_VERSION


def test_mission_preservation_na_when_mission_continuity_inapplicable() -> None:
    result = compute_score(_record(), NA_MISSION)
    # Weight redistributes entirely to (1 - operational_disruption); the
    # pillar itself is never wholly N/A because operational_disruption is
    # always applicable.
    assert result.pillars["M"].applicable is True
    assert result.pillars["M"].components["critical_mission_health"]["applicable"] is False
