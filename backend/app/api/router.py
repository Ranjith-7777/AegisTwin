from fastapi import APIRouter

from app.api.routes import (
    correlation,
    detection,
    health,
    mitre,
    prediction,
    safety,
    simulation,
    system,
    telemetry,
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
