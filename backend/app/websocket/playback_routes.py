from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.exceptions import ApplicationError
from app.schemas.playback import PlaybackEnvelope
from app.services.playback_correlation_service import (
    PlaybackCorrelationState,
    playback_correlation_service,
)
from app.services.playback_detection_service import (
    PlaybackDetectionState,
    playback_detection_service,
)
from app.services.playback_prediction_service import (
    PlaybackPredictionState,
    playback_prediction_service,
)
from app.services.playback_service import playback_service
from app.services.telemetry_service import telemetry_service
from app.websocket.playback import PlaybackController

router = APIRouter()
logger = logging.getLogger(__name__)


async def _send_connection_error(
    websocket: WebSocket, run_id: str, code: str, message: str
) -> None:
    envelope = PlaybackEnvelope(
        message_type="error",
        run_id=run_id,
        sequence_number=1,
        server_timestamp=datetime.now(UTC),
        synthetic=True,
        payload={"error_code": code, "message": message, "state": "error"},
    )
    await websocket.send_json(envelope.model_dump(mode="json"))


# Intentionally public, VIEWER-tier, read-only stream: it replays a
# synthetic simulation run's already-recorded telemetry/detection/
# correlation/prediction events and accepts only playback control
# messages (pause/resume/seek) - no state-changing actions against the
# system are exposed here. Left ungated for the same reasons as
# /ws/events (browser WebSocket handshakes cannot reliably carry the
# X-MS-CLIENT-PRINCIPAL* auth headers); see docs/security/AUTHENTICATION.md.
@router.websocket("/api/v1/ws/simulation/runs/{run_id}")
async def simulation_playback_socket(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()
    raw_after_sequence = websocket.query_params.get("after_sequence", "0")
    try:
        after_sequence = int(raw_after_sequence)
        if after_sequence < 0:
            raise ValueError
    except ValueError:
        await _send_connection_error(
            websocket, run_id, "INVALID_RESUME_POSITION", "after_sequence must be zero or greater."
        )
        await websocket.close(code=4400)
        return

    database = websocket.app.state.database
    try:
        with database.session_factory() as session:
            metadata = playback_service.get_metadata(session, run_id)
            events = telemetry_service.list_run_events(session, run_id)
    except ApplicationError:
        await _send_connection_error(
            websocket, run_id, "SIMULATION_RUN_NOT_FOUND", "The simulation run was not found."
        )
        await websocket.close(code=4404)
        return

    delay_provider = getattr(websocket.app.state, "playback_delay_provider", asyncio.sleep)

    def load_detection(model_id: str) -> PlaybackDetectionState:
        with database.session_factory() as session:
            return playback_detection_service.prepare(
                session, run_id, model_id, [event.event_id for event in events]
            )

    def load_correlation(model_id: str) -> PlaybackCorrelationState:
        with database.session_factory() as session:
            return playback_correlation_service.prepare(session, run_id, model_id)

    def load_prediction(model_id: str) -> PlaybackPredictionState:
        with database.session_factory() as session:
            return playback_prediction_service.prepare(session, run_id, model_id, len(events))

    controller = PlaybackController(
        websocket,
        metadata,
        events,
        delay_provider,
        after_sequence=after_sequence,
        detection_loader=load_detection,
        correlation_loader=load_correlation,
        prediction_loader=load_prediction,
    )
    logger.info("Synthetic playback WebSocket connected run_id=%s", run_id)
    await controller.initialise()
    try:
        while True:
            try:
                message = await websocket.receive_json()
            except json.JSONDecodeError:
                await controller.send_error(
                    "MALFORMED_JSON", "Control messages must contain valid JSON."
                )
                continue
            await controller.handle_control(message)
    except WebSocketDisconnect:
        logger.info("Synthetic playback WebSocket disconnected run_id=%s", run_id)
    finally:
        await controller.close()
