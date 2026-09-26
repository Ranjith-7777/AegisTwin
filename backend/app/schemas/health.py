from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["healthy", "unhealthy"]
    service: str
    environment: str
    simulation_only: bool
    database: Literal["connected", "disconnected"]


class LivenessResponse(BaseModel):
    status: Literal["alive"]


class ReadinessCheck(BaseModel):
    name: str
    status: Literal["ok", "failed"]
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: list[ReadinessCheck]
