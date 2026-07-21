from __future__ import annotations

from datetime import UTC, datetime
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import AnomalyAssessmentRecord, SimulationRunRecord, TelemetryEventRecord
from app.schemas.detection import AnomalyAssessment, AnomalyAssessmentPage, Classification


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class AssessmentQueryService:
    def query(
        self,
        session: Session,
        run_id: str,
        *,
        page: int,
        page_size: int,
        classification: Classification | None,
        minimum_anomaly_score: float | None,
        event_type: str | None,
        source_id: str | None,
        user_id: str | None,
        model_id: str | None,
    ) -> AnomalyAssessmentPage:
        if session.get(SimulationRunRecord, run_id) is None:
            raise ApplicationError(
                "SIMULATION_RUN_NOT_FOUND", "The simulation run was not found.", 404
            )
        filters = [AnomalyAssessmentRecord.simulation_run_id == run_id]
        if classification:
            filters.append(AnomalyAssessmentRecord.classification == classification.value)
        if minimum_anomaly_score is not None:
            filters.append(AnomalyAssessmentRecord.anomaly_score >= minimum_anomaly_score)
        if event_type:
            filters.append(TelemetryEventRecord.event_type == event_type)
        if source_id:
            filters.append(TelemetryEventRecord.source_id == source_id)
        if user_id:
            filters.append(TelemetryEventRecord.user_id == user_id)
        if model_id:
            filters.append(AnomalyAssessmentRecord.model_id == model_id)
        joined = AnomalyAssessmentRecord.__table__.join(
            TelemetryEventRecord.__table__,
            AnomalyAssessmentRecord.event_id == TelemetryEventRecord.event_id,
        )
        total = int(session.scalar(select(func.count()).select_from(joined).where(*filters)) or 0)
        statement = (
            select(AnomalyAssessmentRecord, TelemetryEventRecord)
            .join(
                TelemetryEventRecord,
                AnomalyAssessmentRecord.event_id == TelemetryEventRecord.event_id,
            )
            .where(*filters)
            .order_by(
                AnomalyAssessmentRecord.sequence_number, AnomalyAssessmentRecord.assessment_id
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [
            self._schema(assessment, event) for assessment, event in session.execute(statement)
        ]
        return AnomalyAssessmentPage(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            pages=ceil(total / page_size) if total else 0,
        )

    @staticmethod
    def _schema(
        assessment: AnomalyAssessmentRecord, event: TelemetryEventRecord
    ) -> AnomalyAssessment:
        return AnomalyAssessment(
            assessment_id=assessment.assessment_id,
            model_id=assessment.model_id,
            simulation_run_id=assessment.simulation_run_id,
            event_id=assessment.event_id,
            sequence_number=assessment.sequence_number,
            event_type=event.event_type,
            source_id=event.source_id,
            user_id=event.user_id,
            raw_score=assessment.raw_score,
            anomaly_score=assessment.anomaly_score,
            threshold=assessment.threshold,
            classification=assessment.classification,
            contributing_signals=assessment.contributing_signals_json,
            scored_at=_aware(assessment.scored_at),
            synthetic=assessment.synthetic,
        )


assessment_query_service = AssessmentQueryService()
