from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

RUN_REQUEST = {
    "scenario_id": "credential-compromise",
    "seed": 84,
    "start_time": "2026-07-21T01:30:00Z",
    "playback_speed": 10.0,
}


async def immediate_delay(_: float) -> None:
    await asyncio.sleep(0)


async def blocking_delay(_: float) -> None:
    await asyncio.Event().wait()


def set_delay(client: TestClient, provider: Callable[[float], Awaitable[None]]) -> None:
    application = cast(FastAPI, client.app)
    application.state.playback_delay_provider = provider


def create_run(client: TestClient) -> dict[str, object]:
    response = client.post("/api/v1/simulation/runs", json=RUN_REQUEST)
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def test_missing_run_receives_structured_error(client: TestClient) -> None:
    with client.websocket_connect("/api/v1/ws/simulation/runs/missing") as websocket:
        message = websocket.receive_json()
        assert message["message_type"] == "error"
        assert message["payload"]["error_code"] == "SIMULATION_RUN_NOT_FOUND"
        assert message["synthetic"] is True


def test_connection_acknowledgement_snapshot_and_heartbeat(client: TestClient) -> None:
    run = create_run(client)
    with client.websocket_connect(
        f"/api/v1/ws/simulation/runs/{run['simulation_run_id']}"
    ) as websocket:
        acknowledgement = websocket.receive_json()
        snapshot = websocket.receive_json()
        assert acknowledgement["message_type"] == "connection_ack"
        assert acknowledgement["run_id"] == run["simulation_run_id"]
        assert acknowledgement["synthetic"] is True
        assert snapshot["message_type"] == "playback_snapshot"
        assert snapshot["payload"]["total_event_count"] == 7
        assert snapshot["payload"]["starting_after_sequence"] == 0
        websocket.send_json({"message_type": "ping"})
        heartbeat = websocket.receive_json()
        assert heartbeat["message_type"] == "heartbeat"
        assert heartbeat["payload"]["state"] == "idle"


def test_stable_order_completion_and_synthetic_markers(client: TestClient) -> None:
    set_delay(client, immediate_delay)
    run = create_run(client)
    with client.websocket_connect(
        f"/api/v1/ws/simulation/runs/{run['simulation_run_id']}"
    ) as websocket:
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json({"message_type": "start"})
        assert websocket.receive_json()["message_type"] == "playback_started"
        event_messages = [websocket.receive_json() for _ in range(7)]
        completed = websocket.receive_json()

    assert [message["payload"]["event_index"] for message in event_messages] == list(range(1, 8))
    timestamps = [message["payload"]["event"]["timestamp"] for message in event_messages]
    assert timestamps == sorted(timestamps)
    assert all(message["synthetic"] is True for message in event_messages)
    assert all(
        message["payload"]["event"]["metadata"]["synthetic"] is True for message in event_messages
    )
    assert completed["message_type"] == "playback_completed"
    assert completed["payload"]["state"] == "completed"


def test_pause_resume_and_stop_controls(client: TestClient) -> None:
    set_delay(client, blocking_delay)
    run = create_run(client)
    with client.websocket_connect(
        f"/api/v1/ws/simulation/runs/{run['simulation_run_id']}"
    ) as websocket:
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json({"message_type": "start"})
        assert websocket.receive_json()["message_type"] == "playback_started"
        assert websocket.receive_json()["message_type"] == "telemetry_event"
        websocket.send_json({"message_type": "pause"})
        paused = websocket.receive_json()
        assert paused["message_type"] == "playback_paused"
        assert paused["payload"]["state"] == "paused"
        websocket.send_json({"message_type": "resume"})
        assert websocket.receive_json()["message_type"] == "playback_resumed"
        websocket.send_json({"message_type": "stop"})
        stopped = websocket.receive_json()
        assert stopped["message_type"] == "playback_stopped"
        assert stopped["payload"]["state"] == "stopped"


def test_malformed_and_unsupported_controls_are_rejected(client: TestClient) -> None:
    run = create_run(client)
    with client.websocket_connect(
        f"/api/v1/ws/simulation/runs/{run['simulation_run_id']}"
    ) as websocket:
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_text("{invalid")
        malformed = websocket.receive_json()
        assert malformed["payload"]["error_code"] == "MALFORMED_JSON"
        websocket.send_json({"message_type": "execute"})
        unsupported = websocket.receive_json()
        assert unsupported["payload"]["error_code"] == "INVALID_CONTROL"


def test_resume_after_sequence_does_not_duplicate_events(client: TestClient) -> None:
    set_delay(client, immediate_delay)
    run = create_run(client)
    with client.websocket_connect(
        f"/api/v1/ws/simulation/runs/{run['simulation_run_id']}?after_sequence=3"
    ) as websocket:
        websocket.receive_json()
        snapshot = websocket.receive_json()
        assert snapshot["payload"]["starting_after_sequence"] == 3
        websocket.send_json({"message_type": "start"})
        websocket.receive_json()
        events = [websocket.receive_json() for _ in range(4)]
        assert websocket.receive_json()["message_type"] == "playback_completed"
    assert [event["payload"]["event_index"] for event in events] == [4, 5, 6, 7]


def test_two_clients_have_isolated_playback_state(client: TestClient) -> None:
    set_delay(client, blocking_delay)
    run = create_run(client)
    url = f"/api/v1/ws/simulation/runs/{run['simulation_run_id']}"
    with client.websocket_connect(url) as first, client.websocket_connect(url) as second:
        for socket in (first, second):
            socket.receive_json()
            socket.receive_json()
            socket.send_json({"message_type": "start"})
            socket.receive_json()
            socket.receive_json()
        first.send_json({"message_type": "stop"})
        assert first.receive_json()["message_type"] == "playback_stopped"
        second.send_json({"message_type": "ping"})
        heartbeat = second.receive_json()
        assert heartbeat["message_type"] == "heartbeat"
        assert heartbeat["payload"]["state"] == "playing"


def test_playback_metadata_endpoint(client: TestClient) -> None:
    run = create_run(client)
    response = client.get(f"/api/v1/simulation/runs/{run['simulation_run_id']}/playback")
    assert response.status_code == 200
    body = response.json()
    assert body["total_events"] == 7
    assert body["simulated_duration_seconds"] == 310
    assert body["synthetic"] is True


def create_scored_model(client: TestClient, run_id: str) -> str:
    trained = client.post(
        "/api/v1/detection/models/train",
        json={
            "training_seed_range": {"start": 1, "end": 1},
            "validation_seed_range": {"start": 2, "end": 2},
            "evaluation_seed_range": {"start": 3, "end": 3},
            "random_state": 17,
            "target_false_positive_rate": 0.1,
            "n_estimators": 100,
        },
    )
    assert trained.status_code == 201
    model_id = str(trained.json()["model_id"])
    scored = client.post(
        f"/api/v1/detection/runs/{run_id}/score",
        json={"model_id": model_id},
    )
    assert scored.status_code == 200
    return model_id


def test_detection_playback_streams_event_then_persisted_assessment(client: TestClient) -> None:
    set_delay(client, immediate_delay)
    run = create_run(client)
    run_id = str(run["simulation_run_id"])
    model_id = create_scored_model(client, run_id)
    with client.websocket_connect(f"/api/v1/ws/simulation/runs/{run_id}") as websocket:
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json(
            {"message_type": "start", "detection_enabled": True, "model_id": model_id}
        )
        assert websocket.receive_json()["message_type"] == "detection_ready"
        assert websocket.receive_json()["message_type"] == "playback_started"
        pairs = [(websocket.receive_json(), websocket.receive_json()) for _ in range(7)]
        assert websocket.receive_json()["message_type"] == "playback_completed"
    for event_message, assessment_message in pairs:
        assert event_message["message_type"] == "telemetry_event"
        assert assessment_message["message_type"] == "anomaly_assessment"
        assessment = assessment_message["payload"]
        assert assessment["event_id"] == event_message["payload"]["event"]["event_id"]
        assert assessment["model_id"] == model_id
        assert assessment["synthetic"] is True
        assert "attack_probability" not in assessment


def test_detection_reconnect_skips_prior_event_assessment_pairs(client: TestClient) -> None:
    set_delay(client, immediate_delay)
    run = create_run(client)
    run_id = str(run["simulation_run_id"])
    model_id = create_scored_model(client, run_id)
    with client.websocket_connect(
        f"/api/v1/ws/simulation/runs/{run_id}?after_sequence=5"
    ) as websocket:
        websocket.receive_json()
        snapshot = websocket.receive_json()
        assert snapshot["payload"]["starting_after_sequence"] == 5
        websocket.send_json(
            {"message_type": "start", "detection_enabled": True, "model_id": model_id}
        )
        websocket.receive_json()
        websocket.receive_json()
        messages = [websocket.receive_json() for _ in range(4)]
    assert [item["message_type"] for item in messages] == [
        "telemetry_event",
        "anomaly_assessment",
        "telemetry_event",
        "anomaly_assessment",
    ]
    assert [messages[0]["payload"]["event_index"], messages[2]["payload"]["event_index"]] == [6, 7]


def test_detection_controls_reject_missing_model_and_preserve_telemetry_fallback(
    client: TestClient,
) -> None:
    set_delay(client, immediate_delay)
    run = create_run(client)
    run_id = str(run["simulation_run_id"])
    with client.websocket_connect(f"/api/v1/ws/simulation/runs/{run_id}") as websocket:
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json({"message_type": "start", "detection_enabled": True})
        assert websocket.receive_json()["payload"]["error_code"] == "INVALID_CONTROL"
        websocket.send_json({"message_type": "start"})
        assert websocket.receive_json()["message_type"] == "playback_started"
        assert websocket.receive_json()["message_type"] == "telemetry_event"
