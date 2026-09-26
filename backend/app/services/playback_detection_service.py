from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import AnomalyAssessmentRecord, DetectionModelRecord
from app.services.detection_scoring_service import detection_scoring_service


@dataclass(frozen=True)
class PlaybackDetectionState:
    model_id: str
    feature_schema_version: str
    calibration_method: str
    detector_type: str
    assessments: dict[str, dict[str, object]]
    complete: bool
    missing_event_ids: tuple[str, ...]


class PlaybackDetectionService:
    """Loads persisted synthetic assessments; it never performs live scoring."""

    def prepare(
        self, session: Session, run_id: str, model_id: str, event_ids: list[str]
    ) -> PlaybackDetectionState:
        model = session.get(DetectionModelRecord, model_id)
        if model is None:
            raise ApplicationError(
                "DETECTION_MODEL_NOT_FOUND", "The detection model was not found.", 404
            )
        if not model.synthetic:
            raise ApplicationError(
                "MODEL_NOT_SYNTHETIC", "Only synthetic detection models may be used.", 400
            )
        # Loading once here verifies artifact availability and warms the process-local cache.
        detection_scoring_service.load_artifact(session, model_id)
        rows = list(
            session.scalars(
                select(AnomalyAssessmentRecord)
                .where(
                    AnomalyAssessmentRecord.simulation_run_id == run_id,
                    AnomalyAssessmentRecord.model_id == model_id,
                )
                .order_by(AnomalyAssessmentRecord.sequence_number)
            )
        )
        by_event = {
            row.event_id: {
                "assessment_id": row.assessment_id,
                "model_id": row.model_id,
                "event_id": row.event_id,
                "sequence_number": row.sequence_number,
                "feature_schema_version": model.feature_schema_version,
                "calibration_method": model.calibration_method,
                "detector_type": model.model_type,
                "raw_isolation_forest_score": row.raw_score,
                "isolation_forest_rank": row.component_scores_json.get("isolation_forest", 0.0),
                "hybrid_anomaly_score": row.anomaly_score,
                "threshold": row.threshold,
                "classification": row.classification,
                "contributing_signals": row.contributing_signals_json,
                "component_scores": row.component_scores_json,
                "synthetic": True,
            }
            for row in rows
            if row.synthetic
        }
        missing = tuple(event_id for event_id in event_ids if event_id not in by_event)
        return PlaybackDetectionState(
            model_id=model_id,
            feature_schema_version=model.feature_schema_version,
            calibration_method=model.calibration_method,
            detector_type=model.model_type,
            assessments=by_event,
            complete=not missing and len(by_event) == len(event_ids),
            missing_event_ids=missing,
        )


playback_detection_service = PlaybackDetectionService()
