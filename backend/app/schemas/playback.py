from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.simulation import SimulationRun


class PlaybackState(StrEnum):
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ERROR = "error"


class PlaybackControlType(StrEnum):
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    PING = "ping"


class PlaybackControl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_type: PlaybackControlType
    after_sequence: int | None = Field(default=None, ge=0)


class PlaybackEnvelope(BaseModel):
    message_type: str
    run_id: str
    sequence_number: int = Field(ge=1)
    server_timestamp: datetime
    synthetic: Literal[True] = True
    payload: dict[str, object]


class PlaybackMetadata(BaseModel):
    run: SimulationRun
    total_events: int
    first_event_timestamp: datetime | None
    last_event_timestamp: datetime | None
    simulated_duration_seconds: float
    default_playback_speed: float
    synthetic: Literal[True] = True
    available_controls: tuple[str, ...] = ("start", "pause", "resume", "stop", "ping")
