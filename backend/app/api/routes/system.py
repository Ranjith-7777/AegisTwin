from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_database_session
from app.schemas.system import SystemStatusResponse
from app.services.system_service import get_system_status

router = APIRouter(tags=["system"])
Db = Annotated[Session, Depends(get_database_session)]


@router.get("/system/status", response_model=SystemStatusResponse)
def system_status(session: Db) -> SystemStatusResponse:
    return get_system_status(session)
