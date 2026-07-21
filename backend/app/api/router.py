from fastapi import APIRouter

from app.api.routes import detection, health, safety, simulation, system, telemetry

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(system.router)
api_router.include_router(safety.router)
api_router.include_router(simulation.router)
api_router.include_router(telemetry.router)
api_router.include_router(detection.router)
