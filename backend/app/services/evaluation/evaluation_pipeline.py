"""Phase 5 Stage 3: the explicit "evaluate this experiment" pipeline step.

Chains `EvaluationMetricsService.compute()` -> Mission Continuity's
`compute_curve()` -> `ResilienceScoreService.compute()`, in that order,
because each later step reads the previous step's persisted output (ARS's
Mission Preservation pillar needs Mission Continuity's final snapshot,
which in turn needs `ExperimentMetricRecord.logical_timeline_json`/
`raw_metrics_json` to already exist).

Deliberately NOT wired into `ExperimentService.create_and_run` yet - the
Stage 3 brief leaves that decision to a later API stage, which may want
"compute metrics" to be its own explicit, separately-triggerable step
(e.g. re-scoring after a metrics-methodology version bump, without
re-running the whole experiment). Call this function directly wherever
that later stage needs the fully-populated result.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.models import ExperimentMetricRecord, ExperimentRecord, MissionHealthPointRecord
from app.events.envelope import DomainEvent, EvaluationMetricsComputedPayload
from app.events.registry import get_event_bus
from app.events.types import EventType
from app.services.evaluation.metrics_service import evaluation_metrics_service
from app.services.evaluation.mission_continuity_service import (
    MCI_VERSION,
    mission_continuity_service,
)
from app.services.evaluation.resilience_score_service import resilience_score_service


def evaluate_experiment(
    session: Session, experiment_id: str
) -> tuple[ExperimentMetricRecord, list[MissionHealthPointRecord]]:
    """Runs the full Phase 5 evaluation pipeline for one experiment and
    returns the fully-populated `ExperimentMetricRecord` (including
    `mci`/`ars_total`/`ars_pillars_json`) and its Mission Health curve."""

    metric_record = evaluation_metrics_service.compute(session, experiment_id)
    points = mission_continuity_service.compute_curve(session, experiment_id)
    mci = mission_continuity_service.compute_mci(points)

    metric_record.mci = mci
    metric_record.mci_version = MCI_VERSION
    session.commit()

    resilience_score_service.compute(session, experiment_id)
    session.refresh(metric_record)

    experiment = session.get(ExperimentRecord, experiment_id)
    get_event_bus().publish(
        DomainEvent(
            event_type=EventType.EVALUATION_METRICS_COMPUTED,
            source="evaluation",
            run_id=experiment.run_id if experiment is not None else None,
            scenario_id=experiment.scenario_id if experiment is not None else None,
            correlation_id=experiment_id,
            causation_id=experiment.batch_id if experiment is not None else None,
            resource_ids=[experiment_id],
            payload=EvaluationMetricsComputedPayload(
                experiment_id=experiment_id,
                ars_total=metric_record.ars_total,
                mci=metric_record.mci,
            ),
        )
    )
    return metric_record, points
