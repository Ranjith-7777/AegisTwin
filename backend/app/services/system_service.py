from typing import Any

from sqlalchemy import Select, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.constants import AGENT_ROSTER, SYSTEM_NAME, SYSTEM_TAGLINE
from app.database.models import (
    IncidentCandidateRecord,
    ResponseOrchestrationRecord,
    SimulationRunRecord,
)
from app.schemas.system import SystemStatusResponse

# Correlation states that represent an incident still demanding operator attention.
OPEN_CORRELATION_STATES = ("correlated", "high_priority")


def _count(session: Session, statement: Select[tuple[Any, ...]]) -> int:
    return int(session.scalar(statement) or 0)


def _database_revision(session: Session | None) -> str:
    """The Alembic revision actually applied to the connected database
    (previously a hardcoded, long-stale constant). `unversioned` means the
    schema was created without Alembic (e.g. a test `create_all`)."""

    if session is None:
        return "unknown"
    try:
        revision = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    except SQLAlchemyError:
        session.rollback()
        return "unversioned"
    return str(revision) if revision else "unversioned"


def get_system_status(
    session: Session | None = None, settings: Settings | None = None
) -> SystemStatusResponse:
    active_settings = settings or get_settings()
    active_incidents = 0
    red_agent_runs = 0
    blue_agent_orchestrations = 0
    if session is not None:
        active_incidents = _count(
            session,
            select(func.count())
            .select_from(IncidentCandidateRecord)
            .where(IncidentCandidateRecord.correlation_state.in_(OPEN_CORRELATION_STATES)),
        )
        red_agent_runs = _count(session, select(func.count()).select_from(SimulationRunRecord))
        blue_agent_orchestrations = _count(
            session, select(func.count()).select_from(ResponseOrchestrationRecord)
        )
    return SystemStatusResponse(
        system_name=SYSTEM_NAME,
        system_tagline=SYSTEM_TAGLINE,
        mode="simulation",
        operational=True,
        active_incidents=active_incidents,
        agents_online=len(AGENT_ROSTER),
        red_agent_runs=red_agent_runs,
        blue_agent_orchestrations=blue_agent_orchestrations,
        version="0.9.0",
        git_commit=active_settings.git_commit,
        build_mode=active_settings.build_mode,
        demo_mode=active_settings.demo_mode,
        database_revision=_database_revision(session),
        environment=active_settings.environment,
        synthetic_only=active_settings.simulation_only,
        benchmark_report_timestamp=active_settings.benchmark_report_timestamp,
    )
