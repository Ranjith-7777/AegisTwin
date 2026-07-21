from fastapi import APIRouter

from app.schemas.system import SystemStatusResponse
from app.services.system_service import get_system_status

router = APIRouter(tags=["system"])


@router.get("/system/status", response_model=SystemStatusResponse)
def system_status() -> SystemStatusResponse:
    return get_system_status()
