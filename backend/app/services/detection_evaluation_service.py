from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from statistics import mean, median
from uuid import UUID, uuid5

from sklearn.metrics import average_precision_score, roc_auc_score
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import ModelEvaluationRecord
from app.schemas.detection import Classification, DetectionTrainingRequest, ModelEvaluation
from app.schemas.telemetry import TelemetryEvent
from app.services.detection_dataset_service import SyntheticDataset, detection_dataset_service
from app.services.detection_scoring_service import ScoreTuple, detection_scoring_service
from app.services.detection_training_service import detection_training_service
from app.services.evaluation_truth_service import evaluation_truth_service
from app.services.model_artifact_service import DetectionArtifact

EVALUATION_NAMESPACE = UUID("fc46eb38-90fa-42b9-a8b7-b8adb6d70073")


def metric_counts(labels: list[int], predicted: list[int]) -> dict[str, float | int]:
    pairs = list(zip(labels, predicted, strict=True))
    tp = sum(label == 1 and prediction == 1 for label, prediction in pairs)
    fp = sum(label == 0 and prediction == 1 for label, prediction in pairs)
    tn = sum(label == 0 and prediction == 0 for label, prediction in pairs)
    fn = sum(label == 1 and prediction == 0 for label, prediction in pairs)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "precision": precision,
        "recall": recall,
        "f1_score": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
    }


class DetectionEvaluationService:
    def evaluate(self, session: Session, model_id: str) -> ModelEvaluation:
        model = detection_training_service.get_record(session, model_id)
        request = DetectionTrainingRequest.model_validate(model.configuration_json)
        artifact = detection_scoring_service.load_artifact(session, model_id)
        normal = detection_dataset_service.build_scenario(
            "normal-operations", request.evaluation_seed_range, "evaluation-normal"
        )
        suspicious = detection_dataset_service.build_scenario(
            "credential-compromise", request.evaluation_seed_range, "evaluation-suspicious"
        )
        validation = detection_dataset_service.build_training(request).validation
        validation_scores = detection_scoring_service.score_events(artifact, validation.events)
        normal_scores = detection_scoring_service.score_events(artifact, normal.events)
        suspicious_scores = detection_scoring_service.score_events(artifact, suspicious.events)
        all_scores = list(normal_scores) + list(suspicious_scores)
        events = normal.events + suspicious.events

        # Benchmark truth remains evaluation-only and is introduced after all scoring.
        event_labels = [evaluation_truth_service.event_label(event) for event in events]
        scenario_labels = [
            evaluation_truth_service.scenario_membership_label(event) for event in events
        ]
        hybrid_predicted = [int(item[3] is Classification.ANOMALOUS) for item in all_scores]
        pure_predicted = [
            int(-item[1] >= artifact.pure_isolation_raw_threshold) for item in all_scores
        ]
        anomaly_scores = [item[2] for item in all_scores]
        pure_scores = [item[5]["isolation_forest"] for item in all_scores]
        event_metrics = self._with_ranking(event_labels, hybrid_predicted, anomaly_scores)
        scenario_metrics = self._with_ranking(scenario_labels, hybrid_predicted, anomaly_scores)
        pure_metrics = self._with_ranking(event_labels, pure_predicted, pure_scores)
        hybrid_metrics = event_metrics
        baseline_predicted = [
            self._baseline(event, artifact.baselines.bytes_p99) for event in events
        ]
        baseline = {
            **metric_counts(event_labels, baseline_predicted),
            "rules": [
                "failed_attempts >= 5",
                "bytes_transferred above learned normal p99",
                "non-standard privilege outside 07:00-19:00 UTC",
            ],
            "synthetic": True,
        }
        run_metrics = self._run_metrics(normal, suspicious, normal_scores, suspicious_scores)
        per_step = self._per_step_metrics(suspicious.events, suspicious_scores)
        distributions = {
            "normal_validation": self._distribution(validation_scores),
            "held_out_normal": self._distribution(normal_scores),
            "credential_compromise": self._distribution(suspicious_scores),
        }
        calibration_comparison = self._calibration_comparison(
            artifact, normal_scores, suspicious_scores, event_labels
        )
        diagnostic = {
            "threshold_location": artifact.calibrated_threshold,
            "raw_threshold": artifact.raw_threshold,
            "score_ties_at_raw_threshold": sum(
                item[5]["hybrid_raw"] == artifact.raw_threshold
                for item in validation_scores + all_scores
            ),
            "normal_validation_false_positive_count": sum(
                item[3] is Classification.ANOMALOUS for item in validation_scores
            ),
            "per_event_type": self._per_event_type(events, all_scores, event_labels),
            "original_low_recall_causes": [
                "scenario-wide labels treated routine scenario events as positives",
                "v1 omitted causal user, binding, transition, and graph context",
                "v1 empirical ranks had coarse threshold resolution around ties",
            ],
            "synthetic": True,
        }
        evaluation_id = str(
            uuid5(
                EVALUATION_NAMESPACE,
                f"{model_id}:{request.evaluation_seed_range}:manifest-v1:v2",
            )
        )
        existing = session.get(ModelEvaluationRecord, evaluation_id)
        if existing is not None:
            return self._schema(existing)
        record = ModelEvaluationRecord(
            evaluation_id=evaluation_id,
            model_id=model_id,
            configuration_json={
                "evaluation_seed_range": request.evaluation_seed_range.model_dump(),
                "label_policy": "separate synthetic benchmark manifest applied after scoring",
                "scenario_membership_comparison": True,
                "synthetic": True,
            },
            normal_event_count=len(normal_scores),
            suspicious_scenario_event_count=len(suspicious_scores),
            true_positive=int(scenario_metrics["true_positive"]),
            false_positive=int(scenario_metrics["false_positive"]),
            true_negative=int(scenario_metrics["true_negative"]),
            false_negative=int(scenario_metrics["false_negative"]),
            precision=float(scenario_metrics["precision"]),
            recall=float(scenario_metrics["recall"]),
            f1_score=float(scenario_metrics["f1_score"]),
            false_positive_rate=float(scenario_metrics["false_positive_rate"]),
            roc_auc=float(scenario_metrics["roc_auc"]),
            average_precision=float(scenario_metrics["average_precision"]),
            baseline_metrics_json=baseline,
            feature_schema_version=artifact.feature_schema_version,
            calibration_method=artifact.calibration_method,
            evaluation_label_mode="evaluation-step-manifest-v1",
            event_level_metrics_json=event_metrics,
            scenario_wide_metrics_json=scenario_metrics,
            run_level_metrics_json=run_metrics,
            per_step_metrics_json=per_step,
            score_distribution_json=distributions,
            calibration_comparison_json=calibration_comparison,
            pure_isolation_metrics_json=pure_metrics,
            hybrid_metrics_json=hybrid_metrics,
            diagnostic_report_json=diagnostic,
            created_at=datetime.now(UTC),
            synthetic=True,
        )
        session.add(record)
        session.flush()
        return self._schema(record)

    def get(self, session: Session, evaluation_id: str) -> ModelEvaluation:
        record = session.get(ModelEvaluationRecord, evaluation_id)
        if record is None:
            raise ApplicationError(
                "EVALUATION_NOT_FOUND", "The model evaluation was not found.", 404
            )
        return self._schema(record)

    @staticmethod
    def _with_ranking(
        labels: list[int], predicted: list[int], scores: list[float]
    ) -> dict[str, float | int | bool]:
        return {
            **metric_counts(labels, predicted),
            "roc_auc": float(roc_auc_score(labels, scores)),
            "average_precision": float(average_precision_score(labels, scores)),
            "positive_event_count": sum(labels),
            "synthetic": True,
        }

    @staticmethod
    def _baseline(event: TelemetryEvent, bytes_p99: float) -> int:
        return int(
            event.failed_attempts >= 5
            or event.bytes_transferred > bytes_p99
            or (
                event.privilege_level is not None
                and event.privilege_level.value != "standard"
                and (event.timestamp.hour < 7 or event.timestamp.hour > 19)
            )
        )

    @staticmethod
    def _distribution(scores: Sequence[ScoreTuple]) -> dict[str, object]:
        values = [float(item[2]) for item in scores]
        return {
            "count": len(values),
            "minimum": min(values),
            "median": median(values),
            "mean": mean(values),
            "maximum": max(values),
            "anomalous_count": sum(item[3] is Classification.ANOMALOUS for item in scores),
        }

    @staticmethod
    def _run_metrics(
        normal: SyntheticDataset,
        suspicious: SyntheticDataset,
        normal_scores: Sequence[ScoreTuple],
        suspicious_scores: Sequence[ScoreTuple],
    ) -> dict[str, object]:
        def counts_by_run(
            run_ids: tuple[str, ...], scores: Sequence[ScoreTuple]
        ) -> dict[str, list[ScoreTuple]]:
            grouped: dict[str, list[ScoreTuple]] = {run_id: [] for run_id in run_ids}
            for item in scores:
                event = item[0]
                assert isinstance(event, TelemetryEvent)
                grouped[event.simulation_run_id].append(item)
            return grouped

        normal_runs = counts_by_run(normal.run_ids, normal_scores)
        suspicious_runs = counts_by_run(suspicious.run_ids, suspicious_scores)
        suspicious_counts = [
            sum(item[3] is Classification.ANOMALOUS for item in items)
            for items in suspicious_runs.values()
        ]
        normal_counts = [
            sum(item[3] is Classification.ANOMALOUS for item in items)
            for items in normal_runs.values()
        ]
        first_sequences: list[int | None] = []
        first_seconds: list[float | None] = []
        for items in suspicious_runs.values():
            first = next(
                (
                    (index, item)
                    for index, item in enumerate(items, 1)
                    if item[3] is Classification.ANOMALOUS
                ),
                None,
            )
            first_sequences.append(first[0] if first else None)
            if first:
                event = first[1][0]
                initial = items[0][0]
                assert isinstance(event, TelemetryEvent) and isinstance(initial, TelemetryEvent)
                first_seconds.append((event.timestamp - initial.timestamp).total_seconds())
            else:
                first_seconds.append(None)
        return {
            "suspicious_run_count": len(suspicious_counts),
            "suspicious_runs_with_any_anomaly_rate": sum(value >= 1 for value in suspicious_counts)
            / len(suspicious_counts),
            "suspicious_runs_with_two_anomalies_rate": sum(
                value >= 2 for value in suspicious_counts
            )
            / len(suspicious_counts),
            "first_anomaly_sequence_by_run": first_sequences,
            "simulated_seconds_to_first_anomaly_by_run": first_seconds,
            "normal_runs_with_any_anomaly": sum(value >= 1 for value in normal_counts),
            "average_anomalies_per_normal_run": mean(normal_counts),
            "average_anomalies_per_suspicious_run": mean(suspicious_counts),
            "synthetic": True,
        }

    @staticmethod
    def _per_step_metrics(
        events: list[TelemetryEvent], scores: Sequence[ScoreTuple]
    ) -> dict[str, object]:
        grouped: dict[int, list[tuple[TelemetryEvent, ScoreTuple]]] = defaultdict(list)
        for event, score in zip(events, scores, strict=True):
            step_value = event.metadata["scenario_step"]
            step = step_value if isinstance(step_value, int) else 0
            grouped[step].append((event, score))
        result: dict[str, object] = {}
        for step, items in sorted(grouped.items()):
            label = evaluation_truth_service.event_label(items[0][0])
            flagged = sum(item[1][3] is Classification.ANOMALOUS for item in items)
            result[str(step)] = {
                "benchmark_anomalous": bool(label),
                "event_count": len(items),
                "flagged_count": flagged,
                "true_positive": flagged if label else 0,
                "false_negative": len(items) - flagged if label else 0,
                "mean_anomaly_score": mean(float(item[1][2]) for item in items),
            }
        return result

    @staticmethod
    def _per_event_type(
        events: list[TelemetryEvent], scores: Sequence[ScoreTuple], labels: list[int]
    ) -> dict[str, object]:
        result: dict[str, dict[str, int]] = defaultdict(
            lambda: {"true_positive": 0, "false_negative": 0}
        )
        for event, score, label in zip(events, scores, labels, strict=True):
            if label:
                key = event.event_type.value
                if score[3] is Classification.ANOMALOUS:
                    result[key]["true_positive"] += 1
                else:
                    result[key]["false_negative"] += 1
        return dict(result)

    @staticmethod
    def _calibration_comparison(
        artifact: DetectionArtifact,
        normal_scores: Sequence[ScoreTuple],
        suspicious_scores: Sequence[ScoreTuple],
        labels: list[int],
    ) -> dict[str, object]:
        results: dict[str, object] = {}
        all_scores = list(normal_scores) + list(suspicious_scores)
        for method, candidate in artifact.calibration_candidates.items():
            threshold = float(candidate["raw_threshold"])
            predicted = [int(float(item[5]["hybrid_raw"]) >= threshold) for item in all_scores]
            metrics = metric_counts(labels, predicted)
            results[method] = {
                **candidate,
                "held_out_normal_false_positive_rate": sum(
                    float(item[5]["hybrid_raw"]) >= threshold for item in normal_scores
                )
                / len(normal_scores),
                "event_level_recall": metrics["recall"],
                "event_level_f1": metrics["f1_score"],
            }
        return results

    @staticmethod
    def _schema(record: ModelEvaluationRecord) -> ModelEvaluation:
        positive_count = record.suspicious_scenario_event_count
        created_at = (
            record.created_at.replace(tzinfo=UTC)
            if record.created_at.tzinfo is None
            else record.created_at
        )
        return ModelEvaluation(
            evaluation_id=record.evaluation_id,
            model_id=record.model_id,
            configuration_json=record.configuration_json,
            normal_event_count=record.normal_event_count,
            suspicious_scenario_event_count=positive_count,
            true_positive=record.true_positive,
            false_positive=record.false_positive,
            true_negative=record.true_negative,
            false_negative=record.false_negative,
            precision=record.precision,
            recall=record.recall,
            f1_score=record.f1_score,
            false_positive_rate=record.false_positive_rate,
            roc_auc=record.roc_auc,
            average_precision=record.average_precision,
            event_level_detection_coverage=record.true_positive / positive_count
            if positive_count
            else 0.0,
            normal_events_incorrectly_flagged=record.false_positive,
            suspicious_scenario_events_flagged=record.true_positive,
            baseline_metrics=record.baseline_metrics_json,
            feature_schema_version=record.feature_schema_version,
            calibration_method=record.calibration_method,
            evaluation_label_mode=record.evaluation_label_mode,
            event_level_metrics=record.event_level_metrics_json,
            scenario_wide_metrics=record.scenario_wide_metrics_json,
            run_level_metrics=record.run_level_metrics_json,
            per_step_metrics=record.per_step_metrics_json,
            score_distribution_summary=record.score_distribution_json,
            calibration_comparison=record.calibration_comparison_json,
            pure_isolation_metrics=record.pure_isolation_metrics_json,
            hybrid_metrics=record.hybrid_metrics_json,
            diagnostic_report=record.diagnostic_report_json,
            created_at=created_at,
            synthetic=record.synthetic,
        )


detection_evaluation_service = DetectionEvaluationService()
