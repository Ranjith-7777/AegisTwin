from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse | JSONResponse:
    settings = request.app.state.settings
    connected = request.app.state.database.is_connected()
    response = HealthResponse(
        status="healthy" if connected else "unhealthy",
        service=settings.app_name,
        environment=settings.environment,
        simulation_only=settings.simulation_only,
        database="connected" if connected else "disconnected",
    )
    if not connected:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=response.model_dump(),
        )
    return response
