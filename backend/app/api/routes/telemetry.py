from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import RequireViewer
from app.database.session import get_database_session
from app.schemas.telemetry import EventType, Severity, TelemetryEvent, TelemetryEventPage
from app.services.telemetry_service import telemetry_service

router = APIRouter(prefix="/v1/telemetry", tags=["telemetry"])
DatabaseSession = Annotated[Session, Depends(get_database_session)]


@router.get("/events", response_model=TelemetryEventPage, dependencies=[RequireViewer])
def list_events(
    session: DatabaseSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    simulation_run_id: str | None = None,
    event_type: EventType | None = None,
    source_id: str | None = None,
    user_id: str | None = None,
    minimum_severity: Severity | None = None,
) -> TelemetryEventPage:
    return telemetry_service.query_events(
        session,
        page=page,
        page_size=page_size,
        simulation_run_id=simulation_run_id,
        event_type=event_type,
        source_id=source_id,
        user_id=user_id,
        minimum_severity=minimum_severity,
    )


@router.get("/events/{event_id}", response_model=TelemetryEvent, dependencies=[RequireViewer])
def get_event(event_id: str, session: DatabaseSession) -> TelemetryEvent:
    return telemetry_service.get_event(session, event_id)
