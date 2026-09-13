from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import SimulationRunRecord, TelemetryEventRecord
from app.events.envelope import (
    DomainEvent,
    ScenarioStartedPayload,
    TelemetryGeneratedPayload,
)
from app.events.registry import get_event_bus
from app.events.types import EventType
from app.schemas.simulation import SimulationRun, SimulationRunCreate, SimulationRunStatus
from app.schemas.telemetry import TelemetryEvent
from app.services.event_generator import event_generator
from app.services.scenario_service import scenario_service

RUN_NAMESPACE = UUID("fb47dc55-40ba-48fb-bce9-a27be2de1c4e")


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class SimulationRunService:
    def create_run(self, session: Session, request: SimulationRunCreate) -> SimulationRun:
        scenario = scenario_service.get_scenario(session, request.scenario_id)
        start_time = request.start_time.astimezone(UTC)
        deterministic_key = (
            f"{request.scenario_id}:{request.seed}:{start_time.isoformat()}:"
            f"{request.playback_speed:.6f}"
        )
        run_id = str(uuid5(RUN_NAMESPACE, deterministic_key))
        existing = session.get(SimulationRunRecord, run_id)
        if existing is not None:
            return self._to_schema(existing)

        events = event_generator.generate(
            scenario=scenario,
            simulation_run_id=run_id,
            seed=request.seed,
            start_time=start_time,
        )
        run = SimulationRunRecord(
            simulation_run_id=run_id,
            scenario_id=scenario.scenario_id,
            seed=request.seed,
            start_time=start_time,
            playback_speed=request.playback_speed,
            status=SimulationRunStatus.COMPLETED.value,
            event_count=len(events),
            created_at=start_time,
        )
        session.add(run)
        session.add_all([self._event_record(event) for event in events])
        session.flush()
        bus = get_event_bus()
        bus.publish(
            DomainEvent(
                event_type=EventType.SCENARIO_STARTED,
                source="simulation",
                run_id=run_id,
                scenario_id=scenario.scenario_id,
                correlation_id=run_id,
                payload=ScenarioStartedPayload(
                    scenario_id=scenario.scenario_id,
                    seed=request.seed,
                    event_count=len(events),
                ),
            )
        )
        bus.publish(
            DomainEvent(
                event_type=EventType.TELEMETRY_GENERATED,
                source="telemetry",
                run_id=run_id,
                scenario_id=scenario.scenario_id,
                correlation_id=run_id,
                payload=TelemetryGeneratedPayload(run_id=run_id, event_count=len(events)),
            )
        )
        return self._to_schema(run)

    def list_runs(self, session: Session) -> list[SimulationRun]:
        statement = select(SimulationRunRecord).order_by(
            SimulationRunRecord.created_at.desc(), SimulationRunRecord.simulation_run_id
        )
        return [self._to_schema(record) for record in session.scalars(statement)]

    def get_run(self, session: Session, run_id: str) -> SimulationRun:
        record = session.get(SimulationRunRecord, run_id)
        if record is None:
            raise ApplicationError(
                "SIMULATION_RUN_NOT_FOUND", "The requested simulation run was not found.", 404
            )
        return self._to_schema(record)

    @staticmethod
    def _to_schema(record: SimulationRunRecord) -> SimulationRun:
        return SimulationRun(
            simulation_run_id=record.simulation_run_id,
            scenario_id=record.scenario_id,
            seed=record.seed,
            start_time=_aware(record.start_time),
            playback_speed=record.playback_speed,
            status=record.status,
            event_count=record.event_count,
            created_at=_aware(record.created_at),
        )

    @staticmethod
    def _event_record(event: TelemetryEvent) -> TelemetryEventRecord:
        return TelemetryEventRecord(
            event_id=event.event_id,
            scenario_id=event.scenario_id,
            simulation_run_id=event.simulation_run_id,
            timestamp=event.timestamp,
            event_type=event.event_type.value,
            action=event.action.value,
            outcome=event.outcome.value,
            severity=event.severity.value,
            source_type=event.source_type.value,
            source_id=event.source_id,
            destination_id=event.destination_id,
            user_id=event.user_id,
            device_id=event.device_id,
            source_ip=str(event.source_ip) if event.source_ip else None,
            destination_ip=str(event.destination_ip) if event.destination_ip else None,
            privilege_level=event.privilege_level.value if event.privilege_level else None,
            failed_attempts=event.failed_attempts,
            bytes_transferred=event.bytes_transferred,
            process_name=event.process_name,
            event_metadata=event.metadata,
            created_at=event.created_at,
        )


simulation_run_service = SimulationRunService()
