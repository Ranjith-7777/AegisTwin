from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.session import get_database_session
from app.schemas.autonomy import AutonomyConfig, AutonomyConfigUpdate, AutonomyMode
from app.services.autonomy_service import autonomy_service

router = APIRouter(prefix="/v1/autonomy", tags=["autonomy"])
Db = Annotated[Session, Depends(get_database_session)]


@router.get("", response_model=AutonomyConfig)
def get_autonomy(session: Db) -> AutonomyConfig:
    return autonomy_service.get(session)


@router.put("", response_model=AutonomyConfig)
def set_autonomy(request: AutonomyConfigUpdate, session: Db) -> AutonomyConfig:
    if request.mode == AutonomyMode.AUTONOMOUS and not request.confirm:
        raise ApplicationError(
            "AUTONOMY_CONFIRMATION_REQUIRED",
            "Raising autonomy to AUTONOMOUS requires an explicit confirm=true - this is a "
            "deliberate, non-hidden safety confirmation, not a dramatic warning.",
            422,
        )
    return autonomy_service.set_mode(session, request.mode, request.updated_by)
