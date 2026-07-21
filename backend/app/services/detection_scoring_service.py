from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import AnomalyAssessmentRecord, SimulationRunRecord
from app.schemas.detection import Classification, RunScoringResult
from app.schemas.telemetry import TelemetryEvent
from app.services.detection_training_service import detection_training_service
from app.services.feature_pipeline_service import feature_pipeline_service
from app.services.model_artifact_service import DetectionArtifact, model_artifact_service
from app.services.score_calibration_service import score_calibration_service
from app.services.telemetry_service import telemetry_service

ASSESSMENT_NAMESPACE = UUID("ad668afe-0559-4c4b-a03e-993e56dff72a")


class DetectionScoringService:
    def load_artifact(self, session: Session, model_id: str) -> DetectionArtifact:
        record = detection_training_service.get_record(session, model_id)
        try:
            return model_artifact_service.load(record.artifact_path)
        except (OSError, ValueError) as exc:
            raise ApplicationError(
                "MODEL_ARTIFACT_INVALID",
                "The persisted synthetic model artifact could not be loaded.",
                500,
            ) from exc

    def score_events(
        self, artifact: DetectionArtifact, events: list[TelemetryEvent]
    ) -> list[tuple[TelemetryEvent, float, float, Classification, list[str]]]:
        rows = feature_pipeline_service.extract(events, artifact.baselines)
        raw_scores = artifact.pipeline.decision_function(rows)
        results: list[tuple[TelemetryEvent, float, float, Classification, list[str]]] = []
        for event, row, raw_score in zip(events, rows, raw_scores, strict=True):
            anomaly_score = score_calibration_service.normalise(
                -float(raw_score), artifact.calibration_scores
            )
            classification = (
                Classification.ANOMALOUS
                if anomaly_score >= artifact.calibrated_threshold
                else Classification.NORMAL
            )
            results.append(
                (
                    event,
                    float(raw_score),
                    anomaly_score,
                    classification,
                    feature_pipeline_service.contributing_signals(event, row, artifact.baselines),
                )
            )
        return results

    def score_run(
        self, session: Session, run_id: str, model_id: str, force_rescore: bool
    ) -> RunScoringResult:
        if session.get(SimulationRunRecord, run_id) is None:
            raise ApplicationError(
                "SIMULATION_RUN_NOT_FOUND", "The simulation run was not found.", 404
            )
        artifact = self.load_artifact(session, model_id)
        existing = int(
            session.scalar(
                select(func.count())
                .select_from(AnomalyAssessmentRecord)
                .where(
                    AnomalyAssessmentRecord.model_id == model_id,
                    AnomalyAssessmentRecord.simulation_run_id == run_id,
                )
            )
            or 0
        )
        if existing and not force_rescore:
            anomalous = self._anomalous_count(session, run_id, model_id)
            return RunScoringResult(
                model_id=model_id,
                simulation_run_id=run_id,
                assessment_count=existing,
                anomalous_count=anomalous,
                force_rescore=False,
                synthetic=True,
            )
        if force_rescore:
            session.execute(
                delete(AnomalyAssessmentRecord).where(
                    AnomalyAssessmentRecord.model_id == model_id,
                    AnomalyAssessmentRecord.simulation_run_id == run_id,
                )
            )
        events = telemetry_service.list_run_events(session, run_id)
        scored = self.score_events(artifact, events)
        scored_at = datetime.now(UTC)
        for sequence, (event, raw, anomaly, classification, signals) in enumerate(scored, 1):
            session.add(
                AnomalyAssessmentRecord(
                    assessment_id=str(uuid5(ASSESSMENT_NAMESPACE, f"{model_id}:{event.event_id}")),
                    model_id=model_id,
                    simulation_run_id=run_id,
                    event_id=event.event_id,
                    sequence_number=sequence,
                    raw_score=raw,
                    anomaly_score=anomaly,
                    threshold=artifact.calibrated_threshold,
                    classification=classification.value,
                    contributing_signals_json=signals,
                    scored_at=scored_at,
                    synthetic=True,
                )
            )
        session.flush()
        return RunScoringResult(
            model_id=model_id,
            simulation_run_id=run_id,
            assessment_count=len(scored),
            anomalous_count=sum(item[3] is Classification.ANOMALOUS for item in scored),
            force_rescore=force_rescore,
            synthetic=True,
        )

    @staticmethod
    def _anomalous_count(session: Session, run_id: str, model_id: str) -> int:
        return int(
            session.scalar(
                select(func.count())
                .select_from(AnomalyAssessmentRecord)
                .where(
                    AnomalyAssessmentRecord.model_id == model_id,
                    AnomalyAssessmentRecord.simulation_run_id == run_id,
                    AnomalyAssessmentRecord.classification == Classification.ANOMALOUS.value,
                )
            )
            or 0
        )


detection_scoring_service = DetectionScoringService()
