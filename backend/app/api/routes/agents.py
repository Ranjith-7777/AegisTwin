from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import RequireViewer
from app.database.session import get_database_session
from app.schemas.agents import AgentRegistry, AgentTrace
from app.services.agent_registry_service import registry, trace_for_orchestration

router = APIRouter(prefix="/v1/agents", tags=["agents"])
Db = Annotated[Session, Depends(get_database_session)]


@router.get("", response_model=AgentRegistry, dependencies=[RequireViewer])
def get_registry() -> AgentRegistry:
    return registry()


@router.get(
    "/orchestrations/{orchestration_id}/trace",
    response_model=AgentTrace,
    dependencies=[RequireViewer],
)
def get_trace(orchestration_id: str, session: Db) -> AgentTrace:
    return trace_for_orchestration(session, orchestration_id)
