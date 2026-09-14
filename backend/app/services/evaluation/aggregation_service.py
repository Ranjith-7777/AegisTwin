"""Phase 5 Stage 4: aggregate statistics across a group of experiments.

Per PM spec Section 75, failed experiments must not contaminate aggregate
statistics unless explicitly requested (`include_failed=True`) - by default
only `ExperimentRecord.status == "completed"` experiments with a computed
`ExperimentMetricRecord` are aggregated.

## N/A handling

Every metric is aggregated only over experiments where it was actually
applicable (a real, non-`None` raw value, or a normalized `Metric` with
`applicable=True`) - never coercing a not-applicable metric to 0. Each
`MetricSummary`/`BooleanOutcomeSummary` carries the applicable sample size
(`n_applicable`/`total_applicable`) alongside `count` (the full group size)
so a caller can see when a metric's statistics are based on a reduced
sample (e.g. `rollback_success` is typically applicable in only a minority
of runs, since it requires verification to have failed first).

## Standard deviation choice (documented, per Section 36-37)

`std` is the POPULATION standard deviation (`statistics.pstdev`) of the
applicable sample, treated purely as a descriptive spread measure over the
runs actually produced - never a sample standard deviation used to infer
anything about a larger population, and never converted into a confidence
interval or p-value anywhere in this module. Per Sections 36-37, this
project's canonical sample size per cell is 5 seeds (`CANONICAL_SEEDS` in
`batch_service.py`) - far too small for a meaningful significance claim -
so no significance-testing code is added here at all, deliberately.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ExperimentMetricRecord, ExperimentRecord
from app.schemas.evaluation import DefenceMode

# raw_metrics_json fields that are genuinely numeric (int/float) and are NOT
# already represented, N/A-aware, in normalized_metrics_json. The reduction/
# coverage/timeliness metrics that exist in BOTH raw and normalized are
# aggregated from raw_metrics_json alone (its plain `None` already means
# N/A per metrics_service.py's own documented convention), so they are
# listed once, here, and never duplicated under a normalized-only name.
RAW_NUMERIC_METRICS: tuple[str, ...] = (
    "detectable_attack_steps",
    "detected_attack_steps",
    "detection_coverage",
    "false_positive_count",
    "false_positive_rate",
    "time_to_first_detection",
    "time_to_incident",
    "time_to_response",
    "time_to_containment",
    "time_to_verified_recovery",
    "attack_paths_before",
    "attack_paths_after",
    "attack_path_reduction",
    "blast_radius_before",
    "blast_radius_after",
    "blast_radius_reduction",
    "critical_assets_exposed_before",
    "critical_assets_exposed_after",
    "critical_exposure_reduction",
    "affected_asset_count",
    "affected_relationship_count",
    "operational_disruption",
    "bystander_impact_count",
    "residual_exposure_score",
    "approval_count",
    "administrator_approval_count",
    "analyst_approval_count",
    "autonomous_action_count",
    "manual_action_count",
)

# normalized_metrics_json-only fields (no raw counterpart at all).
NORMALIZED_ONLY_METRICS: tuple[str, ...] = ("detection_timeliness", "recovery_timeliness")

# raw_metrics_json boolean outcome fields.
BOOLEAN_OUTCOME_METRICS: tuple[str, ...] = (
    "containment_success",
    "verification_success",
    "rollback_success",
)


@dataclass(frozen=True)
class MetricSummary:
    count: int
    n_applicable: int
    mean: float | None
    median: float | None
    std: float | None
    minimum: float | None
    maximum: float | None


@dataclass(frozen=True)
class BooleanOutcomeSummary:
    total_applicable: int
    success_count: int
    success_rate: float | None


@dataclass(frozen=True)
class AggregateResult:
    group_label: str
    experiment_count: int
    metric_summaries: dict[str, MetricSummary] = field(default_factory=dict)
    boolean_summaries: dict[str, BooleanOutcomeSummary] = field(default_factory=dict)


def _summarize(values: list[float], count: int) -> MetricSummary:
    n_applicable = len(values)
    if n_applicable == 0:
        return MetricSummary(
            count=count,
            n_applicable=0,
            mean=None,
            median=None,
            std=None,
            minimum=None,
            maximum=None,
        )
    return MetricSummary(
        count=count,
        n_applicable=n_applicable,
        mean=round(statistics.mean(values), 6),
        median=round(statistics.median(values), 6),
        std=round(statistics.pstdev(values), 6),
        minimum=round(min(values), 6),
        maximum=round(max(values), 6),
    )


def _summarize_boolean(values: list[bool]) -> BooleanOutcomeSummary:
    total_applicable = len(values)
    success_count = sum(1 for value in values if value)
    success_rate = round(success_count / total_applicable, 6) if total_applicable > 0 else None
    return BooleanOutcomeSummary(
        total_applicable=total_applicable,
        success_count=success_count,
        success_rate=success_rate,
    )


class AggregationService:
    def aggregate(
        self,
        session: Session,
        experiment_ids: list[str] | None = None,
        scenario_id: str | None = None,
        defence_mode: DefenceMode | None = None,
        seeds: list[int] | None = None,
        include_failed: bool = False,
        group_label: str | None = None,
    ) -> AggregateResult:
        statement = select(ExperimentRecord)
        if experiment_ids is not None:
            statement = statement.where(ExperimentRecord.experiment_id.in_(experiment_ids))
        if scenario_id is not None:
            statement = statement.where(ExperimentRecord.scenario_id == scenario_id)
        if defence_mode is not None:
            statement = statement.where(ExperimentRecord.defence_mode == defence_mode.value)
        if seeds is not None:
            statement = statement.where(ExperimentRecord.seed.in_(seeds))
        if not include_failed:
            statement = statement.where(ExperimentRecord.status == "completed")

        experiments = list(session.scalars(statement))
        experiment_count = len(experiments)

        metric_records: list[ExperimentMetricRecord] = []
        for experiment in experiments:
            metric_record = session.get(ExperimentMetricRecord, experiment.experiment_id)
            if metric_record is not None:
                metric_records.append(metric_record)

        metric_summaries: dict[str, MetricSummary] = {}

        def numeric_values(extractor: Callable[[ExperimentMetricRecord], object]) -> list[float]:
            values: list[float] = []
            for record in metric_records:
                value = extractor(record)
                if isinstance(value, bool):
                    continue
                if isinstance(value, (int, float)):
                    values.append(float(value))
            return values

        metric_summaries["ars_total"] = _summarize(
            [record.ars_total for record in metric_records if record.ars_total is not None],
            experiment_count,
        )
        metric_summaries["mci"] = _summarize(
            [record.mci for record in metric_records if record.mci is not None], experiment_count
        )

        def raw_field(record: ExperimentMetricRecord, field_name: str) -> object:
            return record.raw_metrics_json.get(field_name)

        for key in RAW_NUMERIC_METRICS:
            raw_values = numeric_values(partial(raw_field, field_name=key))
            metric_summaries[key] = _summarize(raw_values, experiment_count)

        for key in NORMALIZED_ONLY_METRICS:
            normalized_values: list[float] = []
            for record in metric_records:
                entry = record.normalized_metrics_json.get(key)
                if isinstance(entry, dict) and entry.get("applicable") is True:
                    value = entry.get("value")
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        normalized_values.append(float(value))
            metric_summaries[key] = _summarize(normalized_values, experiment_count)

        boolean_summaries: dict[str, BooleanOutcomeSummary] = {}
        for key in BOOLEAN_OUTCOME_METRICS:
            bool_values = [
                record.raw_metrics_json.get(key)
                for record in metric_records
                if isinstance(record.raw_metrics_json.get(key), bool)
            ]
            boolean_summaries[key] = _summarize_boolean(
                [value for value in bool_values if isinstance(value, bool)]
            )

        label = group_label or self._default_label(scenario_id, defence_mode, seeds)
        return AggregateResult(
            group_label=label,
            experiment_count=experiment_count,
            metric_summaries=metric_summaries,
            boolean_summaries=boolean_summaries,
        )

    @staticmethod
    def _default_label(
        scenario_id: str | None, defence_mode: DefenceMode | None, seeds: list[int] | None
    ) -> str:
        parts = []
        if scenario_id is not None:
            parts.append(f"scenario={scenario_id}")
        if defence_mode is not None:
            parts.append(f"defence_mode={defence_mode.value}")
        if seeds is not None:
            parts.append(f"seeds={seeds}")
        return ", ".join(parts) if parts else "all experiments"


aggregation_service = AggregationService()
