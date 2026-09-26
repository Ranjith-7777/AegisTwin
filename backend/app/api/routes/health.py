from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.schemas.health import (
    HealthResponse,
    LivenessResponse,
    ReadinessCheck,
    ReadinessResponse,
)

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


@router.get("/health/live", response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    """Liveness: the process is running and able to answer requests.

    Deliberately does not touch the database or any other dependency —
    a slow or down dependency should surface via readiness, not liveness,
    so an orchestrator never kills a healthy process over a transient
    dependency blip.
    """
    return LivenessResponse(status="alive")


@router.get("/health/ready", response_model=ReadinessResponse)
def readiness(request: Request) -> ReadinessResponse | JSONResponse:
    """Readiness: critical dependencies are usable right now.

    Checks are intentionally cheap (a `SELECT 1`, a directory-existence
    check, an in-memory attribute lookup) so this endpoint remains safe to
    poll frequently.
    """
    settings = request.app.state.settings
    checks: list[ReadinessCheck] = []

    database_ok = request.app.state.database.is_connected()
    checks.append(
        ReadinessCheck(
            name="database",
            status="ok" if database_ok else "failed",
            detail=None if database_ok else "Database connectivity check failed.",
        )
    )

    model_dir_ok = settings.model_artifact_dir.is_dir()
    checks.append(
        ReadinessCheck(
            name="model_subsystem",
            status="ok" if model_dir_ok else "failed",
            detail=None if model_dir_ok else "Model artifact directory is unavailable.",
        )
    )

    simulation_ok = settings.simulation_only
    checks.append(
        ReadinessCheck(
            name="configuration",
            status="ok" if simulation_ok else "failed",
            detail=None if simulation_ok else "SIMULATION_ONLY must be enabled.",
        )
    )

    event_bus_ok = getattr(request.app.state, "event_bus", None) is not None
    checks.append(
        ReadinessCheck(
            name="event_bus",
            status="ok" if event_bus_ok else "failed",
            detail=None if event_bus_ok else "Event bus is not initialised.",
        )
    )

    overall = "ready" if all(check.status == "ok" for check in checks) else "not_ready"
    response = ReadinessResponse(status=overall, checks=checks)
    if overall != "ready":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=response.model_dump(),
        )
    return response
