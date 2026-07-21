from app.core.constants import SYSTEM_NAME
from app.schemas.system import SystemStatusResponse


def get_system_status() -> SystemStatusResponse:
    return SystemStatusResponse(
        system_name=SYSTEM_NAME,
        mode="simulation",
        operational=True,
        active_incidents=0,
        agents_online=0,
    )
