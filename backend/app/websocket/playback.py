from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import WebSocket
from pydantic import ValidationError

from app.core.exceptions import ApplicationError
from app.schemas.playback import (
    PlaybackControl,
    PlaybackControlType,
    PlaybackEnvelope,
    PlaybackMetadata,
    PlaybackState,
)
from app.schemas.telemetry import TelemetryEvent
from app.services.playback_detection_service import PlaybackDetectionState

DelayProvider = Callable[[float], Awaitable[None]]
DetectionLoader = Callable[[str], PlaybackDetectionState]


class PlaybackController:
    """Connection-local controller for one persisted synthetic run."""

    def __init__(
        self,
        websocket: WebSocket,
        metadata: PlaybackMetadata,
        events: list[TelemetryEvent],
        delay_provider: DelayProvider,
        after_sequence: int = 0,
        detection_loader: DetectionLoader | None = None,
    ) -> None:
        self.websocket = websocket
        self.metadata = metadata
        self.events = events
        self.delay_provider = delay_provider
        self.connection_id = str(uuid4())
        self.state = PlaybackState.IDLE
        self.cursor = min(after_sequence, len(events))
        self._message_sequence = 0
        self._play_task: asyncio.Task[None] | None = None
        self._play_gate = asyncio.Event()
        self._play_gate.set()
        self._send_lock = asyncio.Lock()
        self._detection_loader = detection_loader
        self._detection: PlaybackDetectionState | None = None

    async def initialise(self) -> None:
        await self.send(
            "connection_ack",
            {
                "connection_id": self.connection_id,
                "state": self.state.value,
                "available_controls": list(self.metadata.available_controls),
                "detection": {
                    "enabled": False,
                    "model_id": None,
                    "scoring_complete": False,
                },
            },
        )
        await self.send(
            "playback_snapshot",
            {
                "run": self.metadata.run.model_dump(mode="json"),
                "total_event_count": len(self.events),
                "starting_after_sequence": self.cursor,
                "playback_speed": self.metadata.default_playback_speed,
                "state": self.state.value,
                "available_controls": list(self.metadata.available_controls),
            },
        )

    async def handle_control(self, raw_message: object) -> None:
        try:
            control = PlaybackControl.model_validate(raw_message)
        except ValidationError:
            await self.send_error(
                "INVALID_CONTROL",
                "Control messages must use start, pause, resume, stop, or ping.",
            )
            return

        if control.message_type is PlaybackControlType.PING:
            await self.send(
                "heartbeat",
                {"state": self.state.value, "current_event_index": self.cursor},
            )
        elif control.message_type is PlaybackControlType.START:
            await self.start(
                control.after_sequence,
                detection_enabled=control.detection_enabled,
                model_id=control.model_id,
            )
        elif control.message_type is PlaybackControlType.PAUSE:
            await self.pause()
        elif control.message_type is PlaybackControlType.RESUME:
            await self.resume()
        elif control.message_type is PlaybackControlType.STOP:
            await self.stop()

    async def start(
        self,
        after_sequence: int | None = None,
        *,
        detection_enabled: bool = False,
        model_id: str | None = None,
    ) -> None:
        if self._play_task is not None and not self._play_task.done():
            await self.send_error("PLAYBACK_ACTIVE", "Playback is already active.")
            return
        if after_sequence is not None:
            self.cursor = min(after_sequence, len(self.events))
        self._detection = None
        if detection_enabled and model_id is not None:
            if self._detection_loader is None:
                await self.send_detection_error(
                    "DETECTION_UNAVAILABLE", "Synthetic anomaly assessment is unavailable."
                )
                return
            try:
                detection = self._detection_loader(model_id)
            except ApplicationError as exc:
                await self.send_detection_error(exc.error_code, exc.message)
                return
            if not detection.complete:
                await self.send(
                    "detection_warning",
                    {
                        "warning_code": "ASSESSMENTS_INCOMPLETE",
                        "message": (
                            "Persisted assessments are incomplete; detection playback was not "
                            "started."
                        ),
                        "model_id": model_id,
                        "missing_assessment_count": len(detection.missing_event_ids),
                        "can_retry": True,
                        "can_continue_telemetry_only": True,
                    },
                )
                return
            self._detection = detection
            await self.send(
                "detection_ready",
                {
                    "enabled": True,
                    "model_id": detection.model_id,
                    "feature_schema_version": detection.feature_schema_version,
                    "calibration_method": detection.calibration_method,
                    "detector_type": detection.detector_type,
                    "assessment_count": len(detection.assessments),
                    "scoring_complete": True,
                    "starting_after_sequence": self.cursor,
                    "synthetic": True,
                },
            )
        self.state = PlaybackState.PLAYING
        self._play_gate.set()
        await self.send(
            "playback_started",
            {"state": self.state.value, "current_event_index": self.cursor},
        )
        self._play_task = asyncio.create_task(self._play())

    async def pause(self) -> None:
        if self.state is not PlaybackState.PLAYING:
            await self.send_error("INVALID_STATE", "Playback can only pause while playing.")
            return
        self.state = PlaybackState.PAUSED
        self._play_gate.clear()
        await self.send(
            "playback_paused",
            {"state": self.state.value, "current_event_index": self.cursor},
        )

    async def resume(self) -> None:
        if self.state is not PlaybackState.PAUSED:
            await self.send_error("INVALID_STATE", "Playback can only resume while paused.")
            return
        self.state = PlaybackState.PLAYING
        self._play_gate.set()
        await self.send(
            "playback_resumed",
            {"state": self.state.value, "current_event_index": self.cursor},
        )

    async def stop(self) -> None:
        if self.state in {PlaybackState.STOPPED, PlaybackState.COMPLETED}:
            return
        self.state = PlaybackState.STOPPED
        self._play_gate.set()
        if self._play_task is not None and not self._play_task.done():
            self._play_task.cancel()
        await self.send(
            "playback_stopped",
            {"state": self.state.value, "current_event_index": self.cursor},
        )

    async def close(self) -> None:
        if self._play_task is not None and not self._play_task.done():
            self._play_task.cancel()
            await asyncio.gather(self._play_task, return_exceptions=True)

    async def _play(self) -> None:
        try:
            while self.cursor < len(self.events):
                await self._play_gate.wait()
                if self.state is not PlaybackState.PLAYING:
                    return
                event = self.events[self.cursor]
                self.cursor += 1
                await self.send(
                    "telemetry_event",
                    {
                        "event_index": self.cursor,
                        "total_event_count": len(self.events),
                        "event": event.model_dump(mode="json"),
                    },
                )
                if self._detection is not None:
                    # Give pause/stop controls a chance to take effect between the pair.
                    await asyncio.sleep(0)
                    await self._play_gate.wait()
                    if self.state is not PlaybackState.PLAYING:
                        return
                    assessment = self._detection.assessments.get(event.event_id)
                    if assessment is None:
                        await self.send(
                            "detection_warning",
                            {
                                "warning_code": "ASSESSMENT_UNAVAILABLE",
                                "message": (
                                    "The persisted assessment for this event is unavailable."
                                ),
                                "model_id": self._detection.model_id,
                                "event_id": event.event_id,
                                "can_retry": True,
                                "can_continue_telemetry_only": True,
                            },
                        )
                        return
                    await self.send("anomaly_assessment", assessment)
                if self.cursor < len(self.events):
                    following = self.events[self.cursor]
                    simulated_delay = (following.timestamp - event.timestamp).total_seconds()
                    real_delay = max(0.0, simulated_delay / self.metadata.default_playback_speed)
                    await self.delay_provider(real_delay)
            self.state = PlaybackState.COMPLETED
            await self.send(
                "playback_completed",
                {"state": self.state.value, "current_event_index": self.cursor},
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self.state = PlaybackState.ERROR
            await self.send_error("PLAYBACK_ERROR", "Synthetic playback could not continue.")

    async def send_error(self, code: str, message: str) -> None:
        await self.send(
            "error",
            {"error_code": code, "message": message, "state": self.state.value},
        )

    async def send_detection_error(self, code: str, message: str) -> None:
        await self.send(
            "detection_error",
            {
                "error_code": code,
                "message": message,
                "can_retry": True,
                "can_continue_telemetry_only": True,
            },
        )

    async def send(self, message_type: str, payload: dict[str, object]) -> None:
        async with self._send_lock:
            self._message_sequence += 1
            envelope = PlaybackEnvelope(
                message_type=message_type,
                run_id=self.metadata.run.simulation_run_id,
                sequence_number=self._message_sequence,
                server_timestamp=datetime.now(UTC),
                synthetic=True,
                payload=payload,
            )
            await self.websocket.send_json(envelope.model_dump(mode="json"))
