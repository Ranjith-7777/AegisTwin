from fastapi import APIRouter

from app.api.routes import (
    correlation,
    detection,
    health,
    mitre,
    orchestration,
    prediction,
    response,
    safety,
    simulation,
    system,
    telemetry,
    topology,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(system.router)
api_router.include_router(safety.router)
api_router.include_router(simulation.router)
api_router.include_router(telemetry.router)
api_router.include_router(detection.router)
api_router.include_router(correlation.router)
api_router.include_router(prediction.router)
api_router.include_router(mitre.router)
api_router.include_router(topology.router)
api_router.include_router(response.router)
api_router.include_router(orchestration.router)
