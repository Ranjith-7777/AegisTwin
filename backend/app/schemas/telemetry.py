from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress


class EventType(StrEnum):
    AUTHENTICATION = "authentication"
    PORTAL_ACCESS = "portal_access"
    APPLICATION_REQUEST = "application_request"
    DATABASE_QUERY = "database_query"
    DATA_TRANSFER = "data_transfer"
    SESSION = "session"
    PRIVILEGE_CHANGE = "privilege_change"
    INTERNAL_CONNECTION = "internal_connection"


class EventAction(StrEnum):
    LOGIN = "login"
    LOGOUT = "logout"
    ACCESS = "access"
    REQUEST = "request"
    QUERY = "query"
    TRANSFER = "transfer"
    CHANGE_PRIVILEGE = "change_privilege"
    CONNECT = "connect"


class EventOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    ALLOWED = "allowed"
    COMPLETED = "completed"


class Severity(StrEnum):
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


SEVERITY_ORDER: dict[Severity, int] = {
    Severity.INFORMATIONAL: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


class SourceType(StrEnum):
    USER = "user"
    DEVICE = "device"
    SERVER = "server"
    DATABASE = "database"
    SERVICE = "service"


class PrivilegeLevel(StrEnum):
    STANDARD = "standard"
    ELEVATED = "elevated"
    ADMINISTRATOR = "administrator"
    SERVICE = "service"


class TelemetryEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    scenario_id: str
    simulation_run_id: str
    timestamp: datetime
    event_type: EventType
    action: EventAction
    outcome: EventOutcome
    severity: Severity
    source_type: SourceType
    source_id: str
    destination_id: str | None = None
    user_id: str | None = None
    device_id: str | None = None
    source_ip: IPvAnyAddress | None = None
    destination_ip: IPvAnyAddress | None = None
    privilege_level: PrivilegeLevel | None = None
    failed_attempts: Annotated[int, Field(ge=0)] = 0
    bytes_transferred: Annotated[int, Field(ge=0)] = 0
    process_name: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class TelemetryEventPage(BaseModel):
    items: list[TelemetryEvent]
    page: int
    page_size: int
    total: int
    pages: int
