from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import Principal, RequireAnalyst, RequireViewer, Role
from app.core.exceptions import ApplicationError
from app.database.session import get_database_session
from app.schemas.autonomy import AutonomyConfig, AutonomyConfigUpdate, AutonomyMode
from app.services.autonomy_service import autonomy_service

router = APIRouter(prefix="/v1/autonomy", tags=["autonomy"])
Db = Annotated[Session, Depends(get_database_session)]


@router.get("", response_model=AutonomyConfig, dependencies=[RequireViewer])
def get_autonomy(session: Db) -> AutonomyConfig:
    return autonomy_service.get(session)


@router.put("", response_model=AutonomyConfig)
def set_autonomy(
    request: AutonomyConfigUpdate,
    session: Db,
    principal: Principal = RequireAnalyst,
) -> AutonomyConfig:
    # Raising autonomy to AUTONOMOUS is the highest-impact configuration
    # change in the system (it lets agents act without human approval), so
    # it requires ADMIN even though other autonomy mode changes only need
    # ANALYST. Both tiers share this endpoint, so the ADMIN check is applied
    # explicitly here rather than via a single blanket route dependency.
    if request.mode == AutonomyMode.AUTONOMOUS and principal.role < Role.ADMIN:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Raising autonomy to AUTONOMOUS requires ADMIN role",
        )
    if request.mode == AutonomyMode.AUTONOMOUS and not request.confirm:
        raise ApplicationError(
            "AUTONOMY_CONFIRMATION_REQUIRED",
            "Raising autonomy to AUTONOMOUS requires an explicit confirm=true - this is a "
            "deliberate, non-hidden safety confirmation, not a dramatic warning.",
            422,
        )
    return autonomy_service.set_mode(session, request.mode, request.updated_by)
