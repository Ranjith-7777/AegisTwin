from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    detection_enabled: bool = False
    model_id: str | None = Field(default=None, min_length=1, max_length=100)
    correlation_enabled: bool = False
    prediction_enabled: bool = False

    @model_validator(mode="after")
    def detection_model_required(self) -> PlaybackControl:
        if self.detection_enabled and not self.model_id:
            raise ValueError("model_id is required when detection_enabled is true")
        if not self.detection_enabled and self.model_id is not None:
            raise ValueError("model_id requires detection_enabled")
        if self.correlation_enabled and not self.detection_enabled:
            raise ValueError("correlation_enabled requires detection_enabled")
        if self.prediction_enabled and not self.correlation_enabled:
            raise ValueError("prediction_enabled requires correlation_enabled")
        return self


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
