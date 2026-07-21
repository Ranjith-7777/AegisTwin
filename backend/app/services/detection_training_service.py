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
from app.services.detection_dataset_service import detection_dataset_service
from app.services.feature_pipeline_service import FEATURE_SCHEMA_VERSION, feature_pipeline_service
from app.services.model_artifact_service import DetectionArtifact, model_artifact_service
from app.services.score_calibration_service import (
    CALIBRATION_VERSION,
    score_calibration_service,
)

MODEL_NAMESPACE = UUID("8dc82144-fe02-45b2-a318-10be54abfd44")
MODEL_TYPE = "IsolationForest"
MODEL_VERSION = "isolation-forest-v1"


class DetectionTrainingService:
    def train(
        self, session: Session, request: DetectionTrainingRequest, artifact_dir: Path
    ) -> DetectionTrainingResult:
        datasets = detection_dataset_service.build_training(request)
        model_id = str(
            uuid5(
                MODEL_NAMESPACE,
                f"{datasets.fingerprint}:{request.random_state}:"
                f"{request.target_false_positive_rate:.8f}:{FEATURE_SCHEMA_VERSION}",
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
                        n_estimators=200,
                        contamination="auto",
                        random_state=request.random_state,
                        n_jobs=1,
                    ),
                ),
            ]
        )
        pipeline.fit(training_rows)
        training_anomaly = [-float(value) for value in pipeline.decision_function(training_rows)]
        validation_anomaly = [
            -float(value) for value in pipeline.decision_function(validation_rows)
        ]
        calibration = score_calibration_service.calibrate(
            training_anomaly,
            validation_anomaly,
            request.target_false_positive_rate,
        )
        artifact = DetectionArtifact(
            pipeline=pipeline,
            baselines=baselines,
            calibration_scores=calibration.reference_scores,
            calibrated_threshold=calibration.normalised_threshold,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            calibration_version=CALIBRATION_VERSION,
        )
        artifact_path = model_artifact_service.save(artifact_dir, model_id, artifact)
        record = DetectionModelRecord(
            model_id=model_id,
            model_type=MODEL_TYPE,
            model_version=MODEL_VERSION,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            calibration_version=CALIBRATION_VERSION,
            artifact_path=str(artifact_path),
            configuration_json=request.model_dump(mode="json"),
            dataset_fingerprint=datasets.fingerprint,
            random_state=request.random_state,
            target_false_positive_rate=request.target_false_positive_rate,
            calibrated_threshold=calibration.normalised_threshold,
            threshold_percentile=calibration.threshold_percentile,
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
