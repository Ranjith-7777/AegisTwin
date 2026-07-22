from typing import Literal

from pydantic import BaseModel


class SystemStatusResponse(BaseModel):
    system_name: str
    mode: Literal["simulation"]
    operational: bool
    active_incidents: int
    agents_online: int
    version: str
    git_commit: str | None
    build_mode: str
    demo_mode: bool
    database_revision: str
    synthetic_only: bool
    benchmark_report_timestamp: str | None
