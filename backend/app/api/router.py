from fastapi import APIRouter

from app.api.routes import health, safety, system

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(system.router)
api_router.include_router(safety.router)
