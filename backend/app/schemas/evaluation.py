"""Phase 5 reproducible Experiment data model.

An Experiment records one deterministic run of "attack scenario + seed +
detection groundwork + one of the four defence-strategy modes", so results
can be reproduced, paired for comparison (same scenario/seed across modes),
and re-run later. See docs/architecture (Phase 5 evaluation docs, once
added) for the full evaluation methodology - this module only defines the
persisted shape and lifecycle vocabulary; scoring/metrics are a later stage.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DefenceMode(StrEnum):
    """The four defence strategies under evaluation. See
    app/services/evaluation/strategies.py for what each one actually does."""

    NO_ACTIVE_DEFENCE = "no_active_defence"
    RULE_BASED = "rule_based"
    ML_ASSISTED = "ml_assisted"
    AGENTIC = "agentic"


class ExperimentStatus(StrEnum):
    CREATED = "created"
    RUNNING_ATTACK = "running_attack"
    DETECTING = "detecting"
    RESPONDING = "responding"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"


class ExperimentCreate(BaseModel):
    scenario_id: str
    seed: int = Field(ge=0, le=2_147_483_647)
    defence_mode: DefenceMode
    top_k: int = Field(default=5, ge=1, le=20)
    through_sequence: int | None = Field(
        default=None,
        description="Evidence sequence to evaluate through. None means run to completion "
        "(every generated telemetry event for the scenario).",
    )
    label: str | None = None
    notes: str | None = None
    perturbation_id: str | None = Field(
        default=None,
        description="Identifies a partial-observability robustness perturbation applied to "
        "this experiment's evidence. None means the unperturbed baseline.",
    )
    perturbation_params: dict[str, object] | None = None


class ExperimentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    experiment_id: str
    scenario_id: str
    scenario_name: str
    seed: int
    defence_mode: DefenceMode
    detection_model_id: str | None
    topology_version: str
    red_scenario_version: str
    autonomy_mode: str | None
    configuration_json: dict[str, object]
    started_at: datetime | None
    ended_at: datetime | None
    run_id: str | None
    incident_candidate_id: str | None
    orchestration_id: str | None
    status: ExperimentStatus
    failure_stage: str | None
    failure_code: str | None
    failure_message: str | None
    verification_status: str | None
    batch_id: str | None
    rerun_of_experiment_id: str | None
    synthetic: bool = True
    created_at: datetime


class ExperimentMetrics(BaseModel):
    """Phase 5 Stage 6 (API layer): the real, typed evaluation-metrics
    result for one experiment, wrapping `ExperimentMetricRecord`'s JSON
    blobs directly rather than re-modelling their internal shape - the
    exact per-field vocabulary (raw metric names, the `Metric`
    value/applicable/note wrapper in `normalized_metrics_json`,
    `ars_pillars_json`'s pillar breakdown) is owned by
    `app.services.evaluation.metrics_service`/`resilience_score_service`
    and intentionally left as `dict[str, object]` here so this schema never
    drifts out of sync with those modules' own documented conventions."""

    metrics_version: str
    logical_timeline: dict[str, object]
    computation_latency: dict[str, object]
    raw_metrics: dict[str, object]
    normalized_metrics: dict[str, object]
    computed_at: datetime
    mci: float | None
    mci_version: str | None
    ars_total: float | None
    ars_pillars: dict[str, object] | None
    ars_version: str | None


class MissionHealthPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sequence: int
    logical_time_sim: float
    mission_health: float
    stage: str
    reason: str


class BatchView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    batch_id: str
    scenario_ids: list[str] = Field(validation_alias="scenario_ids_json")
    seeds: list[int] = Field(validation_alias="seeds_json")
    defence_modes: list[str] = Field(validation_alias="defence_modes_json")
    status: str
    total_experiments: int
    completed_count: int
    failed_count: int
    experiment_ids: list[str] = Field(validation_alias="experiment_ids_json")
    max_experiments: int | None
    truncated: bool
    started_at: datetime | None
    ended_at: datetime | None
    runtime_seconds: float | None
    created_at: datetime
    synthetic: bool = True


class BatchCreateRequest(BaseModel):
    scenario_ids: list[str]
    seeds: list[int]
    defence_modes: list[DefenceMode]
    max_experiments: int | None = None


class RobustnessRequest(BaseModel):
    """PM spec Section 38: request body for the thin `/robustness`
    convenience endpoint - runs a baseline/perturbed experiment pair for one
    scenario/seed/mode combination. See
    `app.services.evaluation.robustness_service.run_robustness_experiment`."""

    scenario_id: str
    seed: int = Field(ge=0, le=2_147_483_647)
    defence_mode: DefenceMode
    hidden_fraction: float = Field(default=0.3, ge=0.0, le=1.0)


class RobustnessResult(BaseModel):
    baseline: ExperimentView
    perturbed: ExperimentView
    synthetic: Literal[True] = True


class MetricSummaryView(BaseModel):
    count: int
    n_applicable: int
    mean: float | None
    median: float | None
    std: float | None
    minimum: float | None
    maximum: float | None


class BooleanOutcomeSummaryView(BaseModel):
    total_applicable: int
    success_count: int
    success_rate: float | None


class AggregateResultView(BaseModel):
    """Pydantic mirror of `app.services.evaluation.aggregation_service
    .AggregateResult` (a frozen dataclass) - the aggregation service layer
    is deliberately kept framework-agnostic (plain dataclasses, no pydantic
    dependency), so the API layer converts to this typed response model
    rather than relying on FastAPI's best-effort dataclass serialization."""

    group_label: str
    experiment_count: int
    metric_summaries: dict[str, MetricSummaryView]
    boolean_summaries: dict[str, BooleanOutcomeSummaryView]


# ---------------------------------------------------------------------
# Phase 5 Stage 4: paired comparison (see
# app.services.evaluation.comparison_service)
# ---------------------------------------------------------------------


class FairnessCheckResult(BaseModel):
    """Per PM spec Section 76: whether two experiments may honestly be
    treated as a paired comparison. `reasons` is empty iff `paired` is
    True - never populated "for information" on an otherwise-paired
    result."""

    paired: bool
    reasons: list[str] = Field(default_factory=list)


class MetricCell(BaseModel):
    """One (metric, defence_mode) cell in a `ModeComparisonResult` row.
    `applicable=False` means the metric was N/A for this mode's experiment
    (value is always `None` in that case) - the mode's column itself is
    only absent from a row's `values` dict when no completed experiment for
    that mode/scenario/seed was found at all (see `ModeComparisonResult
    .missing_modes`), never zero-filled either way."""

    value: float | bool | None
    applicable: bool


class ComparisonRow(BaseModel):
    metric: str
    values: dict[str, MetricCell]


class PairedDelta(BaseModel):
    """`delta = compared_value - reference_value`, only meaningful for
    numeric metrics (boolean outcome metrics are never diffed here).
    `paired=False` means `reference_mode`'s and `compared_mode`'s
    experiments failed `ComparisonService.check_fairness` against each
    other - the delta is still reported (never hidden), but callers MUST
    surface `fairness_reasons` as a warning rather than presenting it as a
    clean paired comparison, per spec 'show a clear warning or refuse
    paired comparison'."""

    metric: str
    reference_mode: str
    compared_mode: str
    reference_value: float | None
    compared_value: float | None
    delta: float | None
    paired: bool
    fairness_reasons: list[str] = Field(default_factory=list)


class ModeComparisonResult(BaseModel):
    scenario_id: str
    seed: int
    baseline_mode: str | None
    available_modes: list[str]
    missing_modes: list[str]
    rows: list[ComparisonRow]
    paired_deltas: list[PairedDelta]
    synthetic: Literal[True] = True


# ---------------------------------------------------------------------
# Phase 5 Stage 5: unified experiment timeline (see
# app.services.evaluation.timeline_service)
# ---------------------------------------------------------------------


class TimelineEvent(BaseModel):
    """One stage slot in an experiment's reconstructed timeline.

    Every experiment's timeline carries the SAME fixed, ordered set of
    stage slots (see `timeline_service.STAGE_ORDER`) - a stage this
    experiment/mode never reached is still present, with
    `status="skipped_not_applicable"` and an honest one-line reason in
    `summary`, never silently omitted (PM spec Section 40).

    `logical_time_sim` and `wall_clock_time` are deliberately separate
    fields, matching the Stage 2 convention in `metrics_service.py`:
    `logical_time_sim` is seconds since the attack's first simulated event
    (the same convention `ExperimentMetricRecord.logical_timeline_json`
    uses); `wall_clock_time` is the real audit timestamp of the underlying
    database row, when that row actually carries a genuine wall-clock
    stamp (as opposed to a synthetic-timeline value written into a
    `created_at`/`timestamp` column, e.g. telemetry generation - see
    module docstring in `timeline_service.py`). Either may be `None`
    independently of the other.
    """

    sequence: int
    stage: str
    logical_time_sim: float | None
    wall_clock_time: datetime | None
    status: Literal["occurred", "skipped_not_applicable", "failed"]
    summary: str
    resource_ids: list[str] = Field(default_factory=list)
    correlation_id: str | None
    causation_id: str | None


class ExperimentTimeline(BaseModel):
    """The full reconstructed timeline for one experiment - a thin,
    API-serialisable wrapper around an ordered `events` list. See
    `app.services.evaluation.timeline_service.ExperimentTimelineService`."""

    experiment_id: str
    events: list[TimelineEvent]
    synthetic: Literal[True] = True


# ---------------------------------------------------------------------
# Phase 5 Stage 6: full Evaluation API (app.api.routes.evaluation) -
# response shapes that reference the comparison/timeline schemas above,
# so they are declared last.
# ---------------------------------------------------------------------


class ExperimentDetail(ExperimentView):
    """Extends `ExperimentView` with the REAL computed metrics/MCI/ARS
    decomposition, mission-health curve, and timeline - populated by the
    Stage 6 API layer (`app.api.routes.evaluation`) from
    `ExperimentMetricRecord`/`MissionHealthPointRecord`/
    `ExperimentTimelineService`, never left as a placeholder once an
    experiment has actually been evaluated. All four are `None`/empty only
    when the experiment failed before metrics could be computed."""

    metrics: ExperimentMetrics | None = None
    mission_health_curve: list[MissionHealthPoint] = Field(default_factory=list)
    timeline: ExperimentTimeline | None = None


class ExperimentReport(BaseModel):
    """Phase 5 Stage 6 (PM spec Section 67/70): a single-experiment
    "faculty report" JSON shape - plain data for a later UI stage to render
    as a print-friendly page. Deliberately no PDF/HTML generation here."""

    experiment_id: str
    executive_summary: str
    configuration: dict[str, object]
    attack_techniques_observed: list[str]
    detection_evidence_summary: dict[str, object]
    incident_summary: dict[str, object] | None
    attack_graph_and_blast_radius: dict[str, object]
    response_verification_rollback_summary: dict[str, object]
    metrics: ExperimentMetrics | None
    mission_continuity_index: float | None
    ars_decomposition: dict[str, object] | None
    paired_baseline_comparison: ModeComparisonResult | None
    limitations: list[str]
    reproduction: dict[str, object]
    synthetic: Literal[True] = True
