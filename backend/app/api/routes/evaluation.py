"""Phase 5 Stage 6: the full Evaluation API.

Wires the Stage 1-5 services (`experiment_service`, `evaluation_pipeline`,
`mission_continuity_service`, `batch_service`, `aggregation_service`,
`comparison_service`, `timeline_service`) behind HTTP endpoints, plus
CSV/JSON export and a single-experiment "faculty report" JSON shape (PM
spec Sections 44-45, 67-70). Follows this codebase's established
conventions (see `app.api.routes.blue_planning`/`workflow` for the pattern
copied here): a `Session` dependency injected via
`app.database.session.get_database_session`, `ApplicationError` for every
404 (never raw `HTTPException`), and typed pydantic response models.

Note on `POST /batches`: per PM spec Section 32-33 this runs SYNCHRONOUSLY
- `batch_service.create_batch` executes the whole scenario x seed x
defence_mode matrix sequentially before this endpoint returns a response.
There is no background job/queue in this codebase (deliberately, per the
spec); the HTTP response simply arrives once the batch has finished. Keep
requested matrices small enough that this is an acceptable request
duration - the full 80-experiment canonical matrix is a later, offline
stage, not something this endpoint is meant to serve interactively.
"""

from __future__ import annotations

import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import (
    ExperimentMetricRecord,
    ExperimentRecord,
    IncidentCandidateRecord,
    MissionHealthPointRecord,
)
from app.database.session import get_database_session
from app.events.envelope import DomainEvent, EvaluationExportGeneratedPayload
from app.events.registry import get_event_bus
from app.events.types import EventType
from app.schemas.evaluation import (
    AggregateResultView,
    BatchCreateRequest,
    BatchView,
    BooleanOutcomeSummaryView,
    DefenceMode,
    ExperimentCreate,
    ExperimentDetail,
    ExperimentMetrics,
    ExperimentReport,
    ExperimentStatus,
    ExperimentTimeline,
    ExperimentView,
    MetricSummaryView,
    MissionHealthPoint,
    ModeComparisonResult,
    RobustnessRequest,
    RobustnessResult,
)
from app.services.evaluation.aggregation_service import aggregation_service
from app.services.evaluation.batch_service import batch_service
from app.services.evaluation.comparison_service import comparison_service
from app.services.evaluation.evaluation_pipeline import evaluate_experiment
from app.services.evaluation.experiment_service import experiment_service
from app.services.evaluation.mission_continuity_service import mission_continuity_service
from app.services.evaluation.robustness_service import run_robustness_experiment
from app.services.evaluation.timeline_service import experiment_timeline_service
from app.services.scenario_service import scenario_service

router = APIRouter(prefix="/v1/evaluation", tags=["evaluation"])
Db = Annotated[Session, Depends(get_database_session)]

CSV_COLUMNS: tuple[str, ...] = (
    "experiment_id",
    "scenario_id",
    "seed",
    "defence_mode",
    "status",
    "run_id",
    "incident_candidate_id",
    "orchestration_id",
    "verification_status",
    "ars_total",
    "mci",
    "detection_coverage",
    "detection_timeliness",
    "attack_path_reduction",
    "blast_radius_reduction",
    "critical_exposure_reduction",
    "operational_disruption",
    "time_to_first_detection",
    "time_to_incident",
    "time_to_response",
    "time_to_containment",
    "time_to_verified_recovery",
    "containment_success",
    "verification_success",
    "rollback_required",
    "rollback_success",
    "metrics_version",
    "mci_version",
    "ars_version",
    "topology_version",
    "red_scenario_version",
    "created_at",
)


# ---------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------


def _to_metrics_view(metric_record: ExperimentMetricRecord | None) -> ExperimentMetrics | None:
    if metric_record is None:
        return None
    return ExperimentMetrics(
        metrics_version=metric_record.metrics_version,
        logical_timeline=metric_record.logical_timeline_json,
        computation_latency=metric_record.computation_latency_json,
        raw_metrics=metric_record.raw_metrics_json,
        normalized_metrics=metric_record.normalized_metrics_json,
        computed_at=metric_record.computed_at,
        mci=metric_record.mci,
        mci_version=metric_record.mci_version,
        ars_total=metric_record.ars_total,
        ars_pillars=metric_record.ars_pillars_json,
        ars_version=metric_record.ars_version,
    )


def _mission_health_curve(
    points: list[MissionHealthPointRecord],
) -> list[MissionHealthPoint]:
    return [
        MissionHealthPoint(
            sequence=point.sequence,
            logical_time_sim=point.logical_time_sim,
            mission_health=point.mission_health,
            stage=point.stage,
            reason=point.reason,
        )
        for point in points
    ]


def _ensure_evaluated(
    session: Session, experiment: ExperimentRecord
) -> ExperimentMetricRecord | None:
    """Reads the persisted `ExperimentMetricRecord` if one already exists
    (per spec Section 74, "derived metrics may be recomputed only with
    explicit version/change semantics" - never blindly recomputed on every
    GET); computes it once, only if genuinely missing and the experiment
    actually completed."""

    metric_record = session.get(ExperimentMetricRecord, experiment.experiment_id)
    if metric_record is not None:
        return metric_record
    if experiment.status != ExperimentStatus.COMPLETED.value:
        return None
    metric_record, _points = evaluate_experiment(session, experiment.experiment_id)
    return metric_record


def _experiment_detail(session: Session, experiment: ExperimentRecord) -> ExperimentDetail:
    metric_record = _ensure_evaluated(session, experiment)
    curve = mission_continuity_service.get_curve(session, experiment.experiment_id)
    timeline = experiment_timeline_service.build_timeline(session, experiment.experiment_id)
    return ExperimentDetail(
        **ExperimentView.model_validate(experiment).model_dump(),
        metrics=_to_metrics_view(metric_record),
        mission_health_curve=_mission_health_curve(curve),
        timeline=timeline,
    )


def _batch_view(batch: object) -> BatchView:
    return BatchView.model_validate(batch)


# ---------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------


@router.post("/experiments", response_model=ExperimentDetail)
def create_experiment(request: ExperimentCreate, session: Db) -> ExperimentDetail:
    """Creates and runs a single ad-hoc experiment, then IMMEDIATELY
    evaluates it (metrics/MCI/ARS) - matching the batch runner's per-
    experiment behaviour, so a caller never has to remember a separate
    "now compute metrics" step."""

    experiment = experiment_service.create_and_run(session, request)
    if experiment.status == ExperimentStatus.COMPLETED.value:
        evaluate_experiment(session, experiment.experiment_id)
    return _experiment_detail(session, experiment)


@router.get("/experiments", response_model=list[ExperimentView])
def list_experiments(
    session: Db,
    scenario_id: str | None = None,
    defence_mode: DefenceMode | None = None,
    seed: int | None = None,
    status: ExperimentStatus | None = None,
    batch_id: str | None = None,
) -> list[ExperimentRecord]:
    return experiment_service.list(
        session,
        scenario_id=scenario_id,
        defence_mode=defence_mode,
        seed=seed,
        status=status,
        batch_id=batch_id,
    )


@router.get("/experiments/export.csv")
def export_experiments_csv(
    session: Db,
    scenario_id: str | None = None,
    defence_mode: DefenceMode | None = None,
    seed: int | None = None,
    status: ExperimentStatus | None = None,
    batch_id: str | None = None,
) -> PlainTextResponse:
    experiments = experiment_service.list(
        session,
        scenario_id=scenario_id,
        defence_mode=defence_mode,
        seed=seed,
        status=status,
        batch_id=batch_id,
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for experiment in experiments:
        writer.writerow(_csv_row(session, experiment))

    get_event_bus().publish(
        DomainEvent(
            event_type=EventType.EVALUATION_EXPORT_GENERATED,
            source="evaluation",
            resource_ids=[experiment.experiment_id for experiment in experiments],
            payload=EvaluationExportGeneratedPayload(
                export_format="csv",
                experiment_count=len(experiments),
                scenario_id=scenario_id,
                defence_mode=defence_mode.value if defence_mode is not None else None,
                seed=seed,
                status=status.value if status is not None else None,
                batch_id=batch_id,
            ),
        )
    )
    return PlainTextResponse(content=buffer.getvalue(), media_type="text/csv")


def _csv_row(session: Session, experiment: ExperimentRecord) -> list[object]:
    metric_record = session.get(ExperimentMetricRecord, experiment.experiment_id)
    raw = metric_record.raw_metrics_json if metric_record is not None else {}
    normalized = metric_record.normalized_metrics_json if metric_record is not None else {}

    def normalized_value(key: str) -> object:
        entry = normalized.get(key)
        if isinstance(entry, dict) and entry.get("applicable") is True:
            return entry.get("value")
        return None

    return [
        experiment.experiment_id,
        experiment.scenario_id,
        experiment.seed,
        experiment.defence_mode,
        experiment.status,
        experiment.run_id,
        experiment.incident_candidate_id,
        experiment.orchestration_id,
        experiment.verification_status,
        metric_record.ars_total if metric_record is not None else None,
        metric_record.mci if metric_record is not None else None,
        raw.get("detection_coverage"),
        normalized_value("detection_timeliness"),
        raw.get("attack_path_reduction"),
        raw.get("blast_radius_reduction"),
        raw.get("critical_exposure_reduction"),
        raw.get("operational_disruption"),
        raw.get("time_to_first_detection"),
        raw.get("time_to_incident"),
        raw.get("time_to_response"),
        raw.get("time_to_containment"),
        raw.get("time_to_verified_recovery"),
        raw.get("containment_success"),
        raw.get("verification_success"),
        raw.get("rollback_required"),
        raw.get("rollback_success"),
        metric_record.metrics_version if metric_record is not None else None,
        metric_record.mci_version if metric_record is not None else None,
        metric_record.ars_version if metric_record is not None else None,
        experiment.topology_version,
        experiment.red_scenario_version,
        experiment.created_at.isoformat(),
    ]


@router.get("/experiments/export.json", response_model=list[ExperimentDetail])
def export_experiments_json(
    session: Db,
    scenario_id: str | None = None,
    defence_mode: DefenceMode | None = None,
    seed: int | None = None,
    status: ExperimentStatus | None = None,
    batch_id: str | None = None,
) -> list[ExperimentDetail]:
    experiments = experiment_service.list(
        session,
        scenario_id=scenario_id,
        defence_mode=defence_mode,
        seed=seed,
        status=status,
        batch_id=batch_id,
    )
    details = [_experiment_detail(session, experiment) for experiment in experiments]

    get_event_bus().publish(
        DomainEvent(
            event_type=EventType.EVALUATION_EXPORT_GENERATED,
            source="evaluation",
            resource_ids=[experiment.experiment_id for experiment in experiments],
            payload=EvaluationExportGeneratedPayload(
                export_format="json",
                experiment_count=len(experiments),
                scenario_id=scenario_id,
                defence_mode=defence_mode.value if defence_mode is not None else None,
                seed=seed,
                status=status.value if status is not None else None,
                batch_id=batch_id,
            ),
        )
    )
    return details


@router.get("/experiments/{experiment_id}", response_model=ExperimentDetail)
def get_experiment(experiment_id: str, session: Db) -> ExperimentDetail:
    experiment = experiment_service.get(session, experiment_id)
    return _experiment_detail(session, experiment)


@router.post("/experiments/{experiment_id}/rerun", response_model=ExperimentDetail)
def rerun_experiment(experiment_id: str, session: Db) -> ExperimentDetail:
    """Creates a NEW experiment with the same configuration (scenario_id,
    seed, defence_mode, top_k, through_sequence) as `experiment_id`, sets
    `rerun_of_experiment_id`, and runs+evaluates it fully. The original
    experiment is never touched."""

    original = experiment_service.get(session, experiment_id)
    configuration = original.configuration_json
    raw_top_k = configuration.get("top_k", 5)
    top_k = int(raw_top_k) if isinstance(raw_top_k, (int, float, str)) else 5
    raw_through_sequence = configuration.get("through_sequence")
    through_sequence = (
        int(raw_through_sequence) if isinstance(raw_through_sequence, (int, float)) else None
    )
    request = ExperimentCreate(
        scenario_id=original.scenario_id,
        seed=original.seed,
        defence_mode=DefenceMode(original.defence_mode),
        top_k=top_k,
        through_sequence=through_sequence,
    )
    rerun = experiment_service.create_and_run(session, request)
    rerun.rerun_of_experiment_id = original.experiment_id
    session.commit()
    if rerun.status == ExperimentStatus.COMPLETED.value:
        evaluate_experiment(session, rerun.experiment_id)
    return _experiment_detail(session, rerun)


@router.get("/experiments/{experiment_id}/metrics", response_model=ExperimentMetrics)
def get_experiment_metrics(experiment_id: str, session: Db) -> ExperimentMetrics:
    experiment = experiment_service.get(session, experiment_id)
    metric_record = _ensure_evaluated(session, experiment)
    if metric_record is None:
        raise ApplicationError(
            "EXPERIMENT_METRICS_NOT_AVAILABLE",
            "No metrics are available for this experiment (it has not completed).",
            404,
        )
    metrics = _to_metrics_view(metric_record)
    assert metrics is not None
    return metrics


@router.get("/experiments/{experiment_id}/timeline", response_model=ExperimentTimeline)
def get_experiment_timeline(experiment_id: str, session: Db) -> ExperimentTimeline:
    experiment_service.get(session, experiment_id)  # 404s if unknown
    return experiment_timeline_service.build_timeline(session, experiment_id)


@router.get("/experiments/{experiment_id}/report", response_model=ExperimentReport)
def get_experiment_report(experiment_id: str, session: Db) -> ExperimentReport:
    experiment = experiment_service.get(session, experiment_id)
    metric_record = _ensure_evaluated(session, experiment)
    scenario = scenario_service.get_scenario(session, experiment.scenario_id)

    ars_total_text = (
        f"{metric_record.ars_total:.1f}"
        if metric_record and metric_record.ars_total is not None
        else "N/A"
    )
    verification_text = experiment.verification_status or "not reached"
    executive_summary = (
        f"Experiment {experiment.experiment_id} ran '{scenario.name}' (seed={experiment.seed}) "
        f"under '{experiment.defence_mode}' defence. Verification status: {verification_text}. "
        f"Aegis Resilience Score: {ars_total_text}/100."
    )

    incident = (
        session.get(IncidentCandidateRecord, experiment.incident_candidate_id)
        if experiment.incident_candidate_id is not None
        else None
    )
    attack_techniques = list(incident.observed_technique_ids_json) if incident is not None else []

    raw = metric_record.raw_metrics_json if metric_record is not None else {}
    detection_evidence_summary = {
        "detectable_attack_steps": raw.get("detectable_attack_steps"),
        "detected_attack_steps": raw.get("detected_attack_steps"),
        "detection_coverage": raw.get("detection_coverage"),
        "false_positive_count": raw.get("false_positive_count"),
        "false_positive_rate": raw.get("false_positive_rate"),
        "time_to_first_detection": raw.get("time_to_first_detection"),
    }
    incident_summary = (
        {
            "incident_candidate_id": incident.incident_candidate_id,
            "priority": incident.priority,
            "correlation_score": incident.correlation_score,
            "evidence_count": incident.evidence_count,
            "observed_technique_ids": incident.observed_technique_ids_json,
            "observed_tactic_ids": incident.observed_tactic_ids_json,
        }
        if incident is not None
        else None
    )
    attack_graph_and_blast_radius = {
        "attack_paths_before": raw.get("attack_paths_before"),
        "attack_paths_after": raw.get("attack_paths_after"),
        "attack_path_reduction": raw.get("attack_path_reduction"),
        "blast_radius_before": raw.get("blast_radius_before"),
        "blast_radius_after": raw.get("blast_radius_after"),
        "blast_radius_reduction": raw.get("blast_radius_reduction"),
        "critical_assets_exposed_before": raw.get("critical_assets_exposed_before"),
        "critical_assets_exposed_after": raw.get("critical_assets_exposed_after"),
        "critical_exposure_reduction": raw.get("critical_exposure_reduction"),
    }
    response_verification_rollback_summary = {
        "orchestration_id": experiment.orchestration_id,
        "verification_status": experiment.verification_status,
        "containment_success": raw.get("containment_success"),
        "verification_success": raw.get("verification_success"),
        "rollback_required": raw.get("rollback_required"),
        "rollback_success": raw.get("rollback_success"),
        "time_to_response": raw.get("time_to_response"),
        "time_to_containment": raw.get("time_to_containment"),
        "time_to_verified_recovery": raw.get("time_to_verified_recovery"),
        "operational_disruption": raw.get("operational_disruption"),
    }

    paired_comparison: ModeComparisonResult | None = None
    try:
        candidate = comparison_service.compare_modes(
            session, experiment.scenario_id, experiment.seed
        )
        if len(candidate.available_modes) > 1:
            paired_comparison = candidate
    except Exception:
        paired_comparison = None

    limitations = [
        "Sample size of one experiment; no statistical significance implied.",
        "Attack Graph/Blast Radius figures are ephemeral what-if recomputations at "
        "measurement time, not persisted per-call audit rows.",
    ]
    if experiment.defence_mode == DefenceMode.NO_ACTIVE_DEFENCE.value:
        limitations.append(
            "no_active_defence never dispatches a response, so response/verification/"
            "rollback metrics are honestly not applicable (N/A) for this experiment."
        )

    reproduction = {
        "experiment_id": experiment.experiment_id,
        "scenario_id": experiment.scenario_id,
        "seed": experiment.seed,
        "defence_mode": experiment.defence_mode,
        "topology_version": experiment.topology_version,
        "red_scenario_version": experiment.red_scenario_version,
        "detection_model_id": experiment.detection_model_id,
        "metrics_version": metric_record.metrics_version if metric_record is not None else None,
        "mci_version": metric_record.mci_version if metric_record is not None else None,
        "ars_version": metric_record.ars_version if metric_record is not None else None,
    }

    return ExperimentReport(
        experiment_id=experiment.experiment_id,
        executive_summary=executive_summary,
        configuration=experiment.configuration_json,
        attack_techniques_observed=attack_techniques,
        detection_evidence_summary=detection_evidence_summary,
        incident_summary=incident_summary,
        attack_graph_and_blast_radius=attack_graph_and_blast_radius,
        response_verification_rollback_summary=response_verification_rollback_summary,
        metrics=_to_metrics_view(metric_record),
        mission_continuity_index=metric_record.mci if metric_record is not None else None,
        ars_decomposition=metric_record.ars_pillars_json if metric_record is not None else None,
        paired_baseline_comparison=paired_comparison,
        limitations=limitations,
        reproduction=reproduction,
    )


# ---------------------------------------------------------------------
# Batches
# ---------------------------------------------------------------------


@router.post("/batches", response_model=BatchView)
def create_batch(request: BatchCreateRequest, session: Db) -> BatchView:
    """Runs the requested scenario x seed x defence_mode matrix
    SYNCHRONOUSLY - this call blocks until the whole batch has completed
    (see module docstring)."""

    batch = batch_service.create_batch(
        session,
        scenario_ids=request.scenario_ids,
        seeds=request.seeds,
        defence_modes=request.defence_modes,
        max_experiments=request.max_experiments,
    )
    return _batch_view(batch)


@router.get("/batches", response_model=list[BatchView])
def list_batches(session: Db) -> list[BatchView]:
    return [_batch_view(batch) for batch in batch_service.list(session)]


@router.get("/batches/{batch_id}", response_model=BatchView)
def get_batch(batch_id: str, session: Db) -> BatchView:
    return _batch_view(batch_service.get(session, batch_id))


# ---------------------------------------------------------------------
# Robustness (PM spec Section 38: partial-observability robustness test)
# ---------------------------------------------------------------------


@router.post("/robustness", response_model=RobustnessResult)
def create_robustness_experiment(request: RobustnessRequest, session: Db) -> RobustnessResult:
    """Runs ONE baseline/perturbed experiment pair for a single scenario/
    seed/defence_mode combination and evaluates both - a deliberately
    SEPARATE capability from `POST /batches`'s canonical matrix (per spec,
    never part of the default 80-run matrix). Synchronous, like
    `POST /batches`: this call blocks until both experiments have run and
    been evaluated."""

    baseline, perturbed = run_robustness_experiment(
        session,
        scenario_id=request.scenario_id,
        seed=request.seed,
        defence_mode=request.defence_mode,
        hidden_fraction=request.hidden_fraction,
    )
    return RobustnessResult(
        baseline=ExperimentView.model_validate(baseline),
        perturbed=ExperimentView.model_validate(perturbed),
    )


# ---------------------------------------------------------------------
# Compare / Aggregate
# ---------------------------------------------------------------------


@router.get("/compare", response_model=ModeComparisonResult)
def compare_modes(
    session: Db,
    scenario_id: str,
    seed: int,
    defence_modes: Annotated[list[DefenceMode] | None, Query()] = None,
) -> ModeComparisonResult:
    return comparison_service.compare_modes(session, scenario_id, seed, defence_modes)


@router.get("/aggregate", response_model=AggregateResultView)
def aggregate(
    session: Db,
    scenario_id: str | None = None,
    defence_mode: DefenceMode | None = None,
    seeds: Annotated[list[int] | None, Query()] = None,
    include_failed: bool = False,
) -> AggregateResultView:
    result = aggregation_service.aggregate(
        session,
        scenario_id=scenario_id,
        defence_mode=defence_mode,
        seeds=seeds,
        include_failed=include_failed,
    )
    return AggregateResultView(
        group_label=result.group_label,
        experiment_count=result.experiment_count,
        metric_summaries={
            key: MetricSummaryView(
                count=summary.count,
                n_applicable=summary.n_applicable,
                mean=summary.mean,
                median=summary.median,
                std=summary.std,
                minimum=summary.minimum,
                maximum=summary.maximum,
            )
            for key, summary in result.metric_summaries.items()
        },
        boolean_summaries={
            key: BooleanOutcomeSummaryView(
                total_applicable=summary.total_applicable,
                success_count=summary.success_count,
                success_rate=summary.success_rate,
            )
            for key, summary in result.boolean_summaries.items()
        },
    )
