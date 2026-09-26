"""Phase 5 Stage 4: paired comparison between defence modes for the SAME
scenario/seed.

Per PM spec Section 76, two experiments may only be presented as a "paired"
comparison (same attack replayed, only the defence strategy differing) when
they share the same `scenario_id`, `seed`, `topology_version`, and - once
both have been scored - the same `metrics_version`/`ars_version`/
`mci_version`. `check_fairness` is the single place this is checked;
callers (a later API/UI stage) must call it before labelling any
comparison "paired" and must show a warning otherwise, never silently
present an apples-to-oranges comparison as fair.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ExperimentMetricRecord, ExperimentRecord
from app.schemas.evaluation import (
    ComparisonRow,
    DefenceMode,
    FairnessCheckResult,
    MetricCell,
    ModeComparisonResult,
    PairedDelta,
)

# Metrics shown as raw side-by-side rows. Booleans are listed separately
# from the numeric ones since they are never diffed arithmetically.
NUMERIC_COMPARISON_METRICS: tuple[str, ...] = (
    "ars_total",
    "mci",
    "detection_coverage",
    "time_to_first_detection",
    "time_to_containment",
    "time_to_verified_recovery",
    "attack_path_reduction",
    "blast_radius_reduction",
    "critical_exposure_reduction",
    "operational_disruption",
)
BOOLEAN_COMPARISON_METRICS: tuple[str, ...] = ("containment_success", "verification_success")

# Explicitly called out by the PM spec (Sections 35/61/23) in addition to
# whatever the chosen baseline row's own pairwise deltas already cover.
EXPLICIT_EXTRA_PAIRS: tuple[tuple[DefenceMode, DefenceMode], ...] = (
    (DefenceMode.RULE_BASED, DefenceMode.AGENTIC),
    (DefenceMode.ML_ASSISTED, DefenceMode.AGENTIC),
)


class ComparisonService:
    def check_fairness(
        self,
        experiment_a: ExperimentRecord,
        experiment_b: ExperimentRecord,
        metrics_a: ExperimentMetricRecord | None = None,
        metrics_b: ExperimentMetricRecord | None = None,
    ) -> FairnessCheckResult:
        reasons: list[str] = []

        if experiment_a.scenario_id != experiment_b.scenario_id:
            reasons.append(
                "Different scenario_id: "
                f"{experiment_a.scenario_id!r} vs {experiment_b.scenario_id!r}."
            )
        if experiment_a.seed != experiment_b.seed:
            reasons.append(f"Different seed: {experiment_a.seed!r} vs {experiment_b.seed!r}.")
        if experiment_a.topology_version != experiment_b.topology_version:
            reasons.append(
                "Different topology_version: "
                f"{experiment_a.topology_version!r} vs {experiment_b.topology_version!r}."
            )

        if metrics_a is None or metrics_b is None:
            reasons.append(
                "Metrics have not been computed for both experiments yet; fairness cannot "
                "be confirmed until EvaluationMetricsService.compute()/evaluate_experiment() "
                "has run for each."
            )
        else:
            if metrics_a.metrics_version != metrics_b.metrics_version:
                reasons.append(
                    "Mismatched metrics_version: "
                    f"{metrics_a.metrics_version!r} vs {metrics_b.metrics_version!r}."
                )
            if metrics_a.ars_version != metrics_b.ars_version:
                reasons.append(
                    "Mismatched ars_version: "
                    f"{metrics_a.ars_version!r} vs {metrics_b.ars_version!r}."
                )
            if metrics_a.mci_version != metrics_b.mci_version:
                reasons.append(
                    "Mismatched mci_version: "
                    f"{metrics_a.mci_version!r} vs {metrics_b.mci_version!r}."
                )

        return FairnessCheckResult(paired=len(reasons) == 0, reasons=reasons)

    def compare_modes(
        self,
        session: Session,
        scenario_id: str,
        seed: int,
        defence_modes: list[DefenceMode] | None = None,
    ) -> ModeComparisonResult:
        modes = defence_modes or list(DefenceMode)

        experiments: dict[str, ExperimentRecord] = {}
        metrics: dict[str, ExperimentMetricRecord] = {}
        for mode in modes:
            statement = (
                select(ExperimentRecord)
                .where(
                    ExperimentRecord.scenario_id == scenario_id,
                    ExperimentRecord.seed == seed,
                    ExperimentRecord.defence_mode == mode.value,
                    ExperimentRecord.status == "completed",
                )
                .order_by(ExperimentRecord.created_at.desc())
                .limit(1)
            )
            experiment = session.scalar(statement)
            if experiment is None:
                continue
            experiments[mode.value] = experiment
            metric_record = session.get(ExperimentMetricRecord, experiment.experiment_id)
            if metric_record is not None:
                metrics[mode.value] = metric_record

        available_modes: list[str] = [mode.value for mode in modes if mode.value in experiments]
        missing_modes: list[str] = [mode.value for mode in modes if mode.value not in experiments]

        baseline_mode = (
            DefenceMode.NO_ACTIVE_DEFENCE.value
            if DefenceMode.NO_ACTIVE_DEFENCE.value in available_modes
            else (available_modes[0] if available_modes else None)
        )

        rows = self._build_rows(available_modes, metrics)
        paired_deltas = self._build_paired_deltas(
            available_modes, baseline_mode, experiments, metrics
        )

        return ModeComparisonResult(
            scenario_id=scenario_id,
            seed=seed,
            baseline_mode=baseline_mode,
            available_modes=available_modes,
            missing_modes=missing_modes,
            rows=rows,
            paired_deltas=paired_deltas,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _cell(metric_record: ExperimentMetricRecord | None, metric: str) -> MetricCell:
        if metric_record is None:
            return MetricCell(value=None, applicable=False)
        if metric == "ars_total":
            value = metric_record.ars_total
            return MetricCell(value=value, applicable=value is not None)
        if metric == "mci":
            value = metric_record.mci
            return MetricCell(value=value, applicable=value is not None)
        raw_value = metric_record.raw_metrics_json.get(metric)
        if isinstance(raw_value, bool):
            return MetricCell(value=raw_value, applicable=True)
        if isinstance(raw_value, (int, float)):
            return MetricCell(value=float(raw_value), applicable=True)
        return MetricCell(value=None, applicable=False)

    def _build_rows(
        self, available_modes: list[str], metrics: dict[str, ExperimentMetricRecord]
    ) -> list[ComparisonRow]:
        rows: list[ComparisonRow] = []
        for metric in (*NUMERIC_COMPARISON_METRICS, *BOOLEAN_COMPARISON_METRICS):
            values = {
                mode: self._cell(metrics.get(mode), metric)
                for mode in available_modes
                if mode in metrics
            }
            rows.append(ComparisonRow(metric=metric, values=values))
        return rows

    def _numeric_value(
        self, metrics: dict[str, ExperimentMetricRecord], mode: str, metric: str
    ) -> float | None:
        cell = self._cell(metrics.get(mode), metric)
        if not cell.applicable or isinstance(cell.value, bool):
            return None
        return cell.value

    def _build_paired_deltas(
        self,
        available_modes: list[str],
        baseline_mode: str | None,
        experiments: dict[str, ExperimentRecord],
        metrics: dict[str, ExperimentMetricRecord],
    ) -> list[PairedDelta]:
        pairs: list[tuple[str, str]] = []
        if baseline_mode is not None:
            pairs.extend((baseline_mode, mode) for mode in available_modes if mode != baseline_mode)
        for reference, compared in EXPLICIT_EXTRA_PAIRS:
            pair = (reference.value, compared.value)
            if pair[0] in available_modes and pair[1] in available_modes and pair not in pairs:
                pairs.append(pair)

        deltas: list[PairedDelta] = []
        for reference_mode, compared_mode in pairs:
            fairness = self.check_fairness(
                experiments[reference_mode],
                experiments[compared_mode],
                metrics.get(reference_mode),
                metrics.get(compared_mode),
            )
            for metric in NUMERIC_COMPARISON_METRICS:
                reference_value = self._numeric_value(metrics, reference_mode, metric)
                compared_value = self._numeric_value(metrics, compared_mode, metric)
                delta = (
                    round(compared_value - reference_value, 6)
                    if reference_value is not None and compared_value is not None
                    else None
                )
                deltas.append(
                    PairedDelta(
                        metric=metric,
                        reference_mode=reference_mode,
                        compared_mode=compared_mode,
                        reference_value=reference_value,
                        compared_value=compared_value,
                        delta=delta,
                        paired=fairness.paired,
                        fairness_reasons=fairness.reasons,
                    )
                )
        return deltas


comparison_service = ComparisonService()
