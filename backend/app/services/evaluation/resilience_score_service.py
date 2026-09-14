"""Phase 5 Stage 3: the Aegis Resilience Score (ARS).

## Locked formula - do not deviate

    ARS = 100 * (0.20*A + 0.35*W + 0.25*M + 0.20*R)

where A = Threat Awareness, W = Withstand/Containment, M = Mission
Preservation, R = Verified Recovery - see `PILLAR_WEIGHTS` and each
pillar's own docstring below for its internal composition.

## N/A handling (locked, two levels - never conflate them)

1. WITHIN a pillar: if one of its submetrics is inapplicable, its weight is
   redistributed across the REMAINING applicable submetric(s) of that SAME
   pillar only. If every submetric in a pillar is inapplicable, the WHOLE
   PILLAR is `None`/inapplicable (never defaulted to 0.0 or 1.0).
2. ACROSS pillars, at the top level: only when a WHOLE pillar is
   inapplicable does its weight get redistributed across the remaining
   applicable pillars. A pillar is never partially discounted at the top
   level - only Section-1-style within-pillar redistribution ever touches a
   still-applicable pillar's internal composition.

In this codebase's actual metric set, M and R can never be wholly N/A
(`operational_disruption` and `V`/`recovery_timeliness` are always
applicable - see their pillar docstrings), so only A and W can ever trigger
top-level renormalization. `total` itself is `None` only if literally every
pillar were N/A, which cannot happen here since R never is - handled
anyway, never assumed impossible.

## Strategy-neutrality (Section 29 - non-negotiable)

`compute_score`, the actual scoring function, takes ONLY an
`ExperimentMetricRecord` (which has no `defence_mode`/`autonomy_mode`/
approval-count/anything-strategy-identifying field - see its docstring in
`app.database.models`) and a `MissionContinuitySnapshot` (which carries
nothing but a single float and a bool). Neither type can express which
defence strategy produced them, so it is structurally impossible for this
function to branch on strategy - not merely "written not to". See
`tests/test_resilience_score.py::test_signature_has_no_strategy_parameter`
for a signature-inspection proof, and
`test_identical_metrics_produce_identical_score` for a behavioural one.
`ResilienceScoreService.compute` is the only place that touches
`ExperimentRecord`/`session` at all - purely to load the two inputs above
and persist the result back onto `ExperimentMetricRecord`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.database.models import ExperimentMetricRecord, ExperimentRecord
from app.services.evaluation.mission_continuity_service import (
    MissionContinuitySnapshot,
    mission_continuity_service,
)

ARS_VERSION = "aegis-resilience-score-v1"

PILLAR_WEIGHTS: dict[str, float] = {"A": 0.20, "W": 0.35, "M": 0.25, "R": 0.20}


@dataclass(frozen=True)
class PillarResult:
    value: float | None
    applicable: bool
    components: dict[str, dict[str, object]] = field(default_factory=dict)


@dataclass(frozen=True)
class ResilienceScoreResult:
    total: float | None
    pillars: dict[str, PillarResult]
    effective_pillar_weights: dict[str, float]
    version: str = ARS_VERSION


def _metric_value(normalized_metrics: dict[str, object], key: str) -> tuple[float | None, bool]:
    """Reads one `Metric`-wrapped entry from `normalized_metrics_json`.
    Missing key or `applicable=False` both mean "not applicable"."""

    entry = normalized_metrics.get(key)
    if not isinstance(entry, dict) or entry.get("applicable") is not True:
        return None, False
    value = entry.get("value")
    if not isinstance(value, (int, float)):
        return None, False
    return float(value), True


def _weighted_pillar(
    items: list[tuple[str, float | None, bool, float]],
) -> PillarResult:
    """Shared within-pillar composition: `items` is
    `(component_name, raw_value, applicable, base_weight)`. Redistributes
    weight across whichever components are applicable; the whole pillar is
    inapplicable only when NONE of its components are."""

    applicable_weight = sum(weight for _, _, applicable, weight in items if applicable)
    components: dict[str, dict[str, object]] = {}
    for name, raw_value, applicable, weight in items:
        effective_weight = (
            (weight / applicable_weight) if applicable and applicable_weight > 0 else 0.0
        )
        components[name] = {
            "raw_value": raw_value,
            "weight": weight,
            "effective_weight": round(effective_weight, 6),
            "applicable": applicable,
        }
    if applicable_weight <= 0:
        return PillarResult(value=None, applicable=False, components=components)
    value = sum(
        raw_value * (weight / applicable_weight)
        for _, raw_value, applicable, weight in items
        if applicable and raw_value is not None
    )
    return PillarResult(value=round(value, 6), applicable=True, components=components)


def _threat_awareness(normalized_metrics: dict[str, object]) -> PillarResult:
    """A = 0.60*DetectionCoverage + 0.40*DetectionTimeliness."""

    coverage_value, coverage_ok = _metric_value(normalized_metrics, "detection_coverage")
    timeliness_value, timeliness_ok = _metric_value(normalized_metrics, "detection_timeliness")
    return _weighted_pillar(
        [
            ("detection_coverage", coverage_value, coverage_ok, 0.60),
            ("detection_timeliness", timeliness_value, timeliness_ok, 0.40),
        ]
    )


def _withstand_containment(normalized_metrics: dict[str, object]) -> PillarResult:
    """W = 0.40*PathReduction + 0.30*BlastRadiusReduction + 0.30*CriticalExposureReduction."""

    path_value, path_ok = _metric_value(normalized_metrics, "attack_path_reduction")
    blast_value, blast_ok = _metric_value(normalized_metrics, "blast_radius_reduction")
    exposure_value, exposure_ok = _metric_value(normalized_metrics, "critical_exposure_reduction")
    return _weighted_pillar(
        [
            ("attack_path_reduction", path_value, path_ok, 0.40),
            ("blast_radius_reduction", blast_value, blast_ok, 0.30),
            ("critical_exposure_reduction", exposure_value, exposure_ok, 0.30),
        ]
    )


def _mission_preservation(
    raw_metrics: dict[str, object], mission_continuity: MissionContinuitySnapshot
) -> PillarResult:
    """M = 0.60*CriticalMissionHealth + 0.40*(1-OperationalDisruption).
    `OperationalDisruption` is always applicable (real 0.0 for
    `no_active_defence`, never N/A - see `metrics_service.py`), so this
    pillar can never be wholly N/A in practice: if `CriticalMissionHealth`
    is somehow inapplicable, weight redistributes to the operational term
    alone. `MissionHealth`'s time-integral counterpart, MCI, is a SEPARATE
    number surfaced elsewhere - never substituted into this snapshot
    value."""

    operational_disruption = raw_metrics.get("operational_disruption")
    if isinstance(operational_disruption, (int, float)):
        disruption_ok = True
        disruption_value: float | None = 1.0 - float(operational_disruption)
    else:
        disruption_ok = False
        disruption_value = None
    return _weighted_pillar(
        [
            (
                "critical_mission_health",
                mission_continuity.critical_mission_health,
                mission_continuity.applicable,
                0.60,
            ),
            ("operational_disruption_inverse", disruption_value, disruption_ok, 0.40),
        ]
    )


def _verified_recovery(
    raw_metrics: dict[str, object], normalized_metrics: dict[str, object]
) -> PillarResult:
    """R = 0.60*V + 0.40*RecoveryTimeliness. `V` is always applicable - 1.0
    only if `verification_success is True` (or a completed rollback
    counts as a confirmed recovered state, per `recovery_timeliness`'s own
    "verified recovery reached" gate in `metrics_service.py`), else 0.0
    (including `no_active_defence`, which never attempted recovery at
    all - Section 27's explicit V=0 case). `recovery_timeliness` is also
    always applicable (Stage 2 design). So this pillar is NEVER wholly
    N/A - confirmed by `test_verified_recovery_never_na`."""

    verification_success = raw_metrics.get("verification_success") is True
    rollback_success = raw_metrics.get("rollback_success") is True
    v_value = 1.0 if verification_success or rollback_success else 0.0
    timeliness_value, timeliness_ok = _metric_value(normalized_metrics, "recovery_timeliness")
    return _weighted_pillar(
        [
            ("verified_recovery_reached", v_value, True, 0.60),
            ("recovery_timeliness", timeliness_value, timeliness_ok, 0.40),
        ]
    )


def compute_score(
    metrics: ExperimentMetricRecord, mission_continuity: MissionContinuitySnapshot
) -> ResilienceScoreResult:
    """The strategy-neutral scoring function itself - see module docstring.
    Deliberately takes no `ExperimentRecord`/`defence_mode`/`autonomy_mode`
    parameter of any kind."""

    normalized_metrics = metrics.normalized_metrics_json
    raw_metrics = metrics.raw_metrics_json

    pillars = {
        "A": _threat_awareness(normalized_metrics),
        "W": _withstand_containment(normalized_metrics),
        "M": _mission_preservation(raw_metrics, mission_continuity),
        "R": _verified_recovery(raw_metrics, normalized_metrics),
    }

    applicable_weight = sum(
        PILLAR_WEIGHTS[name] for name, pillar in pillars.items() if pillar.applicable
    )

    def _effective_weight(name: str, pillar: PillarResult) -> float:
        if not pillar.applicable or applicable_weight <= 0:
            return 0.0
        return round(PILLAR_WEIGHTS[name] / applicable_weight, 6)

    effective_weights = {name: _effective_weight(name, pillar) for name, pillar in pillars.items()}

    if applicable_weight <= 0:
        return ResilienceScoreResult(
            total=None, pillars=pillars, effective_pillar_weights=effective_weights
        )

    total = 100.0 * sum(
        (pillar.value or 0.0) * effective_weights[name]
        for name, pillar in pillars.items()
        if pillar.applicable
    )
    return ResilienceScoreResult(
        total=round(total, 6), pillars=pillars, effective_pillar_weights=effective_weights
    )


class ResilienceScoreService:
    def compute(self, session: Session, experiment_id: str) -> ResilienceScoreResult:
        """Loads the `ExperimentMetricRecord` and Mission Continuity
        snapshot for this experiment, computes ARS via the pure
        `compute_score`, persists `ars_total`/`ars_pillars_json`/
        `ars_version` back onto the metric record, and returns the full
        decomposed result."""

        experiment = session.get(ExperimentRecord, experiment_id)
        if experiment is None:
            raise ValueError(f"Unknown experiment_id: {experiment_id}")
        metrics = session.get(ExperimentMetricRecord, experiment_id)
        if metrics is None:
            raise ValueError(
                f"No ExperimentMetricRecord for {experiment_id}; run "
                "EvaluationMetricsService.compute() first."
            )

        mission_continuity = mission_continuity_service.snapshot(session, experiment)
        result = compute_score(metrics, mission_continuity)

        metrics.ars_total = result.total
        metrics.ars_pillars_json = {
            name: {
                "value": pillar.value,
                "applicable": pillar.applicable,
                "components": pillar.components,
            }
            for name, pillar in result.pillars.items()
        } | {"effective_pillar_weights": result.effective_pillar_weights}
        metrics.ars_version = ARS_VERSION
        session.commit()
        return result


resilience_score_service = ResilienceScoreService()
