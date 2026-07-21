from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import WebSocket
from pydantic import ValidationError

from app.schemas.playback import (
    PlaybackControl,
    PlaybackControlType,
    PlaybackEnvelope,
    PlaybackMetadata,
    PlaybackState,
)
from app.schemas.telemetry import TelemetryEvent

DelayProvider = Callable[[float], Awaitable[None]]


class PlaybackController:
    """Connection-local controller for one persisted synthetic run."""

    def __init__(
        self,
        websocket: WebSocket,
        metadata: PlaybackMetadata,
        events: list[TelemetryEvent],
        delay_provider: DelayProvider,
        after_sequence: int = 0,
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

    async def initialise(self) -> None:
        await self.send(
            "connection_ack",
            {
                "connection_id": self.connection_id,
                "state": self.state.value,
                "available_controls": list(self.metadata.available_controls),
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
            await self.start(control.after_sequence)
        elif control.message_type is PlaybackControlType.PAUSE:
            await self.pause()
        elif control.message_type is PlaybackControlType.RESUME:
            await self.resume()
        elif control.message_type is PlaybackControlType.STOP:
            await self.stop()

    async def start(self, after_sequence: int | None = None) -> None:
        if self._play_task is not None and not self._play_task.done():
            await self.send_error("PLAYBACK_ACTIVE", "Playback is already active.")
            return
        if after_sequence is not None:
            self.cursor = min(after_sequence, len(self.events))
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
