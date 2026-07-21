from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

from sklearn.metrics import average_precision_score, roc_auc_score
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import ModelEvaluationRecord
from app.schemas.detection import Classification, DetectionTrainingRequest, ModelEvaluation
from app.services.detection_dataset_service import detection_dataset_service
from app.services.detection_scoring_service import detection_scoring_service
from app.services.detection_training_service import detection_training_service

EVALUATION_NAMESPACE = UUID("fc46eb38-90fa-42b9-a8b7-b8adb6d70073")


def metric_counts(labels: list[int], predicted: list[int]) -> dict[str, float | int]:
    tp = sum(
        label == 1 and prediction == 1 for label, prediction in zip(labels, predicted, strict=True)
    )
    fp = sum(
        label == 0 and prediction == 1 for label, prediction in zip(labels, predicted, strict=True)
    )
    tn = sum(
        label == 0 and prediction == 0 for label, prediction in zip(labels, predicted, strict=True)
    )
    fn = sum(
        label == 1 and prediction == 0 for label, prediction in zip(labels, predicted, strict=True)
    )
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
        normal_scores = detection_scoring_service.score_events(artifact, normal.events)
        suspicious_scores = detection_scoring_service.score_events(artifact, suspicious.events)

        # Scenario identity is introduced only after all model scoring is complete.
        labels = [0] * len(normal_scores) + [1] * len(suspicious_scores)
        all_scores = normal_scores + suspicious_scores
        predicted = [int(item[3] is Classification.ANOMALOUS) for item in all_scores]
        anomaly_scores = [item[2] for item in all_scores]
        metrics = metric_counts(labels, predicted)
        baseline_predicted = [
            int(
                event.failed_attempts >= 5
                or event.bytes_transferred > artifact.baselines.bytes_p99
                or (
                    event.privilege_level is not None
                    and event.privilege_level.value != "standard"
                    and (event.timestamp.hour < 7 or event.timestamp.hour > 19)
                )
            )
            for event in normal.events + suspicious.events
        ]
        baseline = {
            **metric_counts(labels, baseline_predicted),
            "rules": [
                "failed_attempts >= 5",
                "bytes_transferred above learned normal p99",
                "non-standard privilege outside 07:00-19:00 UTC",
            ],
            "synthetic": True,
        }
        evaluation_id = str(
            uuid5(EVALUATION_NAMESPACE, f"{model_id}:{request.evaluation_seed_range}")
        )
        existing = session.get(ModelEvaluationRecord, evaluation_id)
        if existing is not None:
            return self._schema(existing)
        record = ModelEvaluationRecord(
            evaluation_id=evaluation_id,
            model_id=model_id,
            configuration_json={
                "evaluation_seed_range": request.evaluation_seed_range.model_dump(),
                "label_policy": "scenario identity applied after scoring",
                "synthetic": True,
            },
            normal_event_count=len(normal_scores),
            suspicious_scenario_event_count=len(suspicious_scores),
            true_positive=int(metrics["true_positive"]),
            false_positive=int(metrics["false_positive"]),
            true_negative=int(metrics["true_negative"]),
            false_negative=int(metrics["false_negative"]),
            precision=float(metrics["precision"]),
            recall=float(metrics["recall"]),
            f1_score=float(metrics["f1_score"]),
            false_positive_rate=float(metrics["false_positive_rate"]),
            roc_auc=float(roc_auc_score(labels, anomaly_scores)),
            average_precision=float(average_precision_score(labels, anomaly_scores)),
            baseline_metrics_json=baseline,
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
    def _schema(record: ModelEvaluationRecord) -> ModelEvaluation:
        suspicious = record.suspicious_scenario_event_count
        return ModelEvaluation(
            evaluation_id=record.evaluation_id,
            model_id=record.model_id,
            configuration_json=record.configuration_json,
            normal_event_count=record.normal_event_count,
            suspicious_scenario_event_count=suspicious,
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
            event_level_detection_coverage=record.true_positive / suspicious if suspicious else 0.0,
            normal_events_incorrectly_flagged=record.false_positive,
            suspicious_scenario_events_flagged=record.true_positive,
            baseline_metrics=record.baseline_metrics_json,
            created_at=record.created_at.replace(tzinfo=UTC)
            if record.created_at.tzinfo is None
            else record.created_at,
            synthetic=record.synthetic,
        )


detection_evaluation_service = DetectionEvaluationService()
