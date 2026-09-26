from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import (
    IncidentCandidateRecord,
    IncidentCandidateSnapshotRecord,
    TechniqueObservationRecord,
)
from app.services.correlation_service import ENGINE_VERSION


@dataclass(frozen=True)
class PlaybackCorrelationState:
    model_id: str
    observations_by_sequence: dict[int, list[dict[str, object]]]
    updates_by_sequence: dict[int, dict[str, object]]
    complete: bool


class PlaybackCorrelationService:
    def prepare(self, session: Session, run_id: str, model_id: str) -> PlaybackCorrelationState:
        candidate = session.scalar(
            select(IncidentCandidateRecord).where(
                IncidentCandidateRecord.simulation_run_id == run_id,
                IncidentCandidateRecord.model_id == model_id,
                IncidentCandidateRecord.correlation_engine_version == ENGINE_VERSION,
            )
        )
        if candidate is None:
            raise ApplicationError(
                "CORRELATION_NOT_READY", "Synthetic correlation analysis has not completed.", 409
            )
        observations: dict[int, list[dict[str, object]]] = {}
        for item in session.scalars(
            select(TechniqueObservationRecord)
            .where(
                TechniqueObservationRecord.simulation_run_id == run_id,
                TechniqueObservationRecord.model_id == model_id,
            )
            .order_by(TechniqueObservationRecord.sequence_number)
        ):
            observations.setdefault(item.sequence_number, []).append(
                {
                    "mapping_id": item.mapping_id,
                    "technique_id": item.technique_id,
                    "technique_name": item.technique_name,
                    "event_id": item.event_id,
                    "sequence_number": item.sequence_number,
                    "mapping_confidence": item.mapping_confidence,
                    "evidence_fields": item.evidence_fields_json,
                    "rationale": item.rationale,
                    "tactic": item.tactic,
                    "mapper_version": item.mapper_version,
                    "model_id": model_id,
                    "synthetic": True,
                }
            )
        updates = {
            item.sequence_number: item.snapshot_json
            for item in session.scalars(
                select(IncidentCandidateSnapshotRecord)
                .where(
                    IncidentCandidateSnapshotRecord.incident_candidate_id
                    == candidate.incident_candidate_id
                )
                .order_by(IncidentCandidateSnapshotRecord.sequence_number)
            )
        }
        return PlaybackCorrelationState(
            model_id=model_id,
            observations_by_sequence=observations,
            updates_by_sequence=updates,
            complete=bool(updates),
        )


playback_correlation_service = PlaybackCorrelationService()
