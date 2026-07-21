from __future__ import annotations

from datetime import UTC, datetime
from math import ceil

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import TelemetryEventRecord
from app.schemas.telemetry import (
    SEVERITY_ORDER,
    EventType,
    Severity,
    TelemetryEvent,
    TelemetryEventPage,
)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class TelemetryService:
    def query_events(
        self,
        session: Session,
        *,
        page: int,
        page_size: int,
        simulation_run_id: str | None,
        event_type: EventType | None,
        source_id: str | None,
        user_id: str | None,
        minimum_severity: Severity | None,
    ) -> TelemetryEventPage:
        filters = []
        if simulation_run_id:
            filters.append(TelemetryEventRecord.simulation_run_id == simulation_run_id)
        if event_type:
            filters.append(TelemetryEventRecord.event_type == event_type.value)
        if source_id:
            filters.append(TelemetryEventRecord.source_id == source_id)
        if user_id:
            filters.append(TelemetryEventRecord.user_id == user_id)
        if minimum_severity:
            minimum_rank = SEVERITY_ORDER[minimum_severity]
            accepted = [
                severity.value for severity, rank in SEVERITY_ORDER.items() if rank >= minimum_rank
            ]
            filters.append(TelemetryEventRecord.severity.in_(accepted))

        base: Select[tuple[TelemetryEventRecord]] = select(TelemetryEventRecord).where(*filters)
        total = session.scalar(
            select(func.count()).select_from(TelemetryEventRecord).where(*filters)
        )
        statement = (
            base.order_by(TelemetryEventRecord.timestamp, TelemetryEventRecord.event_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [self._to_schema(record) for record in session.scalars(statement)]
        count = int(total or 0)
        return TelemetryEventPage(
            items=items,
            page=page,
            page_size=page_size,
            total=count,
            pages=ceil(count / page_size) if count else 0,
        )

    def get_event(self, session: Session, event_id: str) -> TelemetryEvent:
        record = session.get(TelemetryEventRecord, event_id)
        if record is None:
            raise ApplicationError(
                "TELEMETRY_EVENT_NOT_FOUND", "The requested telemetry event was not found.", 404
            )
        return self._to_schema(record)

    @staticmethod
    def _to_schema(record: TelemetryEventRecord) -> TelemetryEvent:
        return TelemetryEvent(
            event_id=record.event_id,
            scenario_id=record.scenario_id,
            simulation_run_id=record.simulation_run_id,
            timestamp=_aware(record.timestamp),
            event_type=record.event_type,
            action=record.action,
            outcome=record.outcome,
            severity=record.severity,
            source_type=record.source_type,
            source_id=record.source_id,
            destination_id=record.destination_id,
            user_id=record.user_id,
            device_id=record.device_id,
            source_ip=record.source_ip,
            destination_ip=record.destination_ip,
            privilege_level=record.privilege_level,
            failed_attempts=record.failed_attempts,
            bytes_transferred=record.bytes_transferred,
            process_name=record.process_name,
            metadata=record.event_metadata,
            created_at=_aware(record.created_at),
        )


telemetry_service = TelemetryService()
