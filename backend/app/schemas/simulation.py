from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.telemetry import (
    EventAction,
    EventOutcome,
    EventType,
    PrivilegeLevel,
    Severity,
    SourceType,
)


class AssetType(StrEnum):
    WORKSTATION = "workstation"
    SERVER = "server"
    DATABASE = "database"
    SERVICE = "service"


class InfrastructureAsset(BaseModel):
    asset_id: str
    name: str
    asset_type: AssetType
    ip_address: str
    criticality: Severity
    relationships: tuple[str, ...] = ()
    synthetic: bool = True


class ScenarioStep(BaseModel):
    sequence: int = Field(ge=1)
    offset_seconds: int = Field(ge=0)
    description: str
    event_type: EventType
    action: EventAction
    outcome: EventOutcome
    severity: Severity
    source_type: SourceType
    source_id: str
    destination_id: str | None = None
    user_id: str | None = None
    device_id: str | None = None
    privilege_level: PrivilegeLevel | None = None
    process_name: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class SimulationScenario(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scenario_id: str
    name: str
    description: str
    steps: list[ScenarioStep]
    synthetic: bool = True


class SimulationRunStatus(StrEnum):
    COMPLETED = "completed"


class SimulationRunCreate(BaseModel):
    scenario_id: str
    seed: int = Field(ge=0, le=2_147_483_647)
    start_time: datetime
    playback_speed: float = Field(default=1.0, gt=0, le=100)

    @field_validator("start_time")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("start_time must include a timezone offset")
        return value


class SimulationRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    simulation_run_id: str
    scenario_id: str
    seed: int
    start_time: datetime
    playback_speed: float
    status: SimulationRunStatus
    event_count: int
    created_at: datetime
