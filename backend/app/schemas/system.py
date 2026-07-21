from typing import Literal

from pydantic import BaseModel


class SystemStatusResponse(BaseModel):
    system_name: str
    mode: Literal["simulation"]
    operational: bool
    active_incidents: int
    agents_online: int
