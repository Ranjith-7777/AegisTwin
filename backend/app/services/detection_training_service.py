from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid5

from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction import DictVectorizer
from sklearn.pipeline import Pipeline
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import DetectionModelRecord
from app.schemas.detection import DetectionModel, DetectionTrainingRequest, DetectionTrainingResult
from app.schemas.telemetry import TelemetryEvent
from app.services.detection_dataset_service import detection_dataset_service
from app.services.feature_pipeline_service import (
    FEATURE_SCHEMA_VERSION,
    FeatureBaselines,
    FeatureRow,
    feature_pipeline_service,
)
from app.services.model_artifact_service import DetectionArtifact, model_artifact_service
from app.services.score_calibration_service import (
    CALIBRATION_VERSION,
    score_calibration_service,
)

MODEL_NAMESPACE = UUID("8dc82144-fe02-45b2-a318-10be54abfd44")
MODEL_TYPE = "IsolationForest"
MODEL_VERSION = "isolation-forest-v2"
HYBRID_WEIGHTS = {
    "isolation_forest": 0.35,
    "robust_numerical_deviation": 0.25,
    "categorical_rarity": 0.15,
    "behavioural_transition_rarity": 0.15,
    "infrastructure_novelty": 0.10,
}


class DetectionTrainingService:
    def train(
        self, session: Session, request: DetectionTrainingRequest, artifact_dir: Path
    ) -> DetectionTrainingResult:
        datasets = detection_dataset_service.build_training(request)
        model_id = str(
            uuid5(
                MODEL_NAMESPACE,
                f"{datasets.fingerprint}:{request.random_state}:"
                f"{request.target_false_positive_rate:.8f}:{FEATURE_SCHEMA_VERSION}:"
                f"{request.calibration_method}:{request.use_hybrid_score}:"
                f"{request.n_estimators}:{request.max_samples_fraction}:"
                f"{request.max_features}",
            )
        )
        existing = session.get(DetectionModelRecord, model_id)
        if existing is not None:
            return self._training_result(existing)

        baselines = feature_pipeline_service.learn_baselines(datasets.training.events)
        training_rows = feature_pipeline_service.extract(datasets.training.events, baselines)
        validation_rows = feature_pipeline_service.extract(datasets.validation.events, baselines)
        pipeline = Pipeline(
            [
                ("features", DictVectorizer(sparse=False)),
                (
                    "model",
                    IsolationForest(
                        n_estimators=request.n_estimators,
                        contamination="auto",
                        max_samples=request.max_samples_fraction,
                        max_features=request.max_features,
                        random_state=request.random_state,
                        n_jobs=1,
                    ),
                ),
            ]
        )
        pipeline.fit(training_rows)
        training_isolation = [-float(value) for value in pipeline.decision_function(training_rows)]
        validation_isolation = [
            -float(value) for value in pipeline.decision_function(validation_rows)
        ]
        pure_calibration = score_calibration_service.compare(
            training_isolation,
            validation_isolation,
            request.target_false_positive_rate,
            request.calibration_method,
        )
        training_hybrid = self._hybrid_values(
            datasets.training.events,
            training_rows,
            training_isolation,
            pure_calibration.reference_scores,
            baselines,
        )
        validation_hybrid = self._hybrid_values(
            datasets.validation.events,
            validation_rows,
            validation_isolation,
            pure_calibration.reference_scores,
            baselines,
        )
        final_training = training_hybrid if request.use_hybrid_score else training_isolation
        final_validation = validation_hybrid if request.use_hybrid_score else validation_isolation
        calibration = score_calibration_service.compare(
            final_training,
            final_validation,
            request.target_false_positive_rate,
            request.calibration_method,
        )
        candidate_data: dict[str, dict[str, float | int | str]] = {
            name: {
                "method": candidate.method,
                "raw_threshold": candidate.raw_threshold,
                "normalised_threshold": candidate.normalised_threshold,
                "validation_false_positive_count": candidate.validation_false_positive_count,
                "validation_false_positive_rate": candidate.validation_false_positive_rate,
                "ties_at_threshold": candidate.ties_at_threshold,
            }
            for name, candidate in calibration.candidates.items()
        }
        artifact = DetectionArtifact(
            pipeline=pipeline,
            baselines=baselines,
            calibration_scores=calibration.reference_scores,
            calibrated_threshold=calibration.selected.normalised_threshold,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            calibration_version=CALIBRATION_VERSION,
            calibration_method=request.calibration_method,
            raw_threshold=calibration.selected.raw_threshold,
            pure_isolation_reference=pure_calibration.reference_scores,
            pure_isolation_raw_threshold=pure_calibration.selected.raw_threshold,
            hybrid_weights=HYBRID_WEIGHTS,
            use_hybrid_score=request.use_hybrid_score,
            calibration_candidates=candidate_data,
        )
        artifact_path = model_artifact_service.save(artifact_dir, model_id, artifact)
        record = DetectionModelRecord(
            model_id=model_id,
            model_type=MODEL_TYPE,
            model_version=MODEL_VERSION,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            calibration_version=CALIBRATION_VERSION,
            calibration_method=request.calibration_method,
            artifact_path=str(artifact_path),
            configuration_json={
                **request.model_dump(mode="json"),
                "model_selection": {
                    "selected": "300 estimators, full normal samples and features",
                    "reason": (
                        "Selected using deterministic normal-only stability and validation "
                        "false-positive control; final evaluation labels were not used."
                    ),
                    "bounded_candidates": [
                        "v1: 200 estimators, feature schema v1",
                        "v2: 300 estimators, feature schema v2",
                    ],
                },
                "hybrid_weights": HYBRID_WEIGHTS,
            },
            dataset_fingerprint=datasets.fingerprint,
            random_state=request.random_state,
            target_false_positive_rate=request.target_false_positive_rate,
            calibrated_threshold=calibration.selected.normalised_threshold,
            threshold_percentile=1 - request.target_false_positive_rate,
            training_event_count=len(datasets.training.events),
            validation_event_count=len(datasets.validation.events),
            created_at=datetime.now(UTC),
            synthetic=True,
        )
        session.add(record)
        session.flush()
        return self._training_result(record)

    def list_models(self, session: Session) -> list[DetectionModel]:
        statement = select(DetectionModelRecord).order_by(DetectionModelRecord.created_at.desc())
        return [self._model(record) for record in session.scalars(statement)]

    def get_record(self, session: Session, model_id: str) -> DetectionModelRecord:
        record = session.get(DetectionModelRecord, model_id)
        if record is None:
            raise ApplicationError(
                "DETECTION_MODEL_NOT_FOUND", "The detection model was not found.", 404
            )
        if not Path(record.artifact_path).is_file():
            raise ApplicationError(
                "MODEL_ARTIFACT_NOT_FOUND",
                "The persisted synthetic model artifact was not found.",
                500,
            )
        return record

    def get_model(self, session: Session, model_id: str) -> DetectionModel:
        return self._model(self.get_record(session, model_id))

    @staticmethod
    def _hybrid_values(
        events: list[TelemetryEvent],
        rows: list[FeatureRow],
        isolation_values: list[float],
        isolation_reference: list[float],
        baselines: FeatureBaselines,
    ) -> list[float]:
        values: list[float] = []
        for event, row, isolation in zip(events, rows, isolation_values, strict=True):
            components = feature_pipeline_service.hybrid_components(event, row, baselines)
            isolation_rank = score_calibration_service.normalise(isolation, isolation_reference)
            values.append(
                HYBRID_WEIGHTS["isolation_forest"] * isolation_rank
                + sum(HYBRID_WEIGHTS[name] * value for name, value in components.items())
            )
        return values

    @staticmethod
    def _training_result(record: DetectionModelRecord) -> DetectionTrainingResult:
        return DetectionTrainingResult(
            model_id=record.model_id,
            model_type=record.model_type,
            feature_schema_version=record.feature_schema_version,
            training_event_count=record.training_event_count,
            validation_event_count=record.validation_event_count,
            dataset_fingerprint=record.dataset_fingerprint,
            calibrated_threshold=record.calibrated_threshold,
            target_false_positive_rate=record.target_false_positive_rate,
            synthetic=record.synthetic,
        )

    @staticmethod
    def _model(record: DetectionModelRecord) -> DetectionModel:
        return DetectionModel.model_validate(record)


detection_training_service = DetectionTrainingService()
