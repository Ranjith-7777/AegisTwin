from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import PredictionSnapshotRecord
from app.services.prediction_service import PREDICTOR_VERSION, prediction_service
from app.services.progression_catalogue_service import PROGRESSION_CATALOGUE_VERSION


@dataclass(frozen=True)
class PlaybackPredictionState:
    model_id: str
    snapshots_by_sequence: dict[int, dict[str, object]]
    complete: bool
    predictor_version: str = PREDICTOR_VERSION
    progression_catalogue_version: str = PROGRESSION_CATALOGUE_VERSION


class PlaybackPredictionService:
    def prepare(
        self, session: Session, run_id: str, model_id: str, event_count: int
    ) -> PlaybackPredictionState:
        rows = list(
            session.scalars(
                select(PredictionSnapshotRecord)
                .where(
                    PredictionSnapshotRecord.simulation_run_id == run_id,
                    PredictionSnapshotRecord.model_id == model_id,
                    PredictionSnapshotRecord.predictor_version == PREDICTOR_VERSION,
                )
                .order_by(PredictionSnapshotRecord.through_sequence_number)
            )
        )
        snapshots = {
            row.through_sequence_number: prediction_service.snapshot_schema(
                session, row
            ).model_dump(mode="json")
            for row in rows
        }
        return PlaybackPredictionState(
            model_id=model_id,
            snapshots_by_sequence=snapshots,
            complete=len(snapshots) == event_count,
        )


playback_prediction_service = PlaybackPredictionService()
