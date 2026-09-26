from fastapi import APIRouter, Request

from app.core.auth import RequireViewer
from app.core.constants import SAFETY_MESSAGE
from app.schemas.safety import SafetyResponse

router = APIRouter(tags=["safety"])


@router.get("/safety", response_model=SafetyResponse, dependencies=[RequireViewer])
def safety(request: Request) -> SafetyResponse:
    return SafetyResponse(
        simulation_only=bool(request.app.state.settings.simulation_only),
        real_world_actions_enabled=False,
        external_targets_allowed=False,
        message=SAFETY_MESSAGE,
    )
