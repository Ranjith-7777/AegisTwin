from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["healthy", "unhealthy"]
    service: str
    environment: str
    simulation_only: bool
    database: Literal["connected", "disconnected"]
