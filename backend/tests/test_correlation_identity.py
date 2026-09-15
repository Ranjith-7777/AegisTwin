from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.database.base import Base
from app.events.bus import InProcessEventBus
from app.events.envelope import DomainEvent
from app.events.registry import use_event_bus
from app.events.types import EventType
from app.main import create_app

RUN_REQUEST = {
    "scenario_id": "staged-compromise-demo",
    "seed": 84,
    "start_time": "2026-07-21T01:30:00Z",
    "playback_speed": 50,
}
TRAIN_REQUEST = {
    "training_seed_range": {"start": 1, "end": 1},
    "validation_seed_range": {"start": 2, "end": 2},
    "evaluation_seed_range": {"start": 3, "end": 3},
    "random_state": 17,
    "target_false_positive_rate": 0.1,
    "n_estimators": 100,
}


@pytest.fixture
def isolated_client(tmp_path: Path) -> Iterator[tuple[TestClient, InProcessEventBus]]:
    settings = Settings(
        _env_file=None,
        DATABASE_URL=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        DEBUG=False,
        MODEL_ARTIFACT_DIR=tmp_path / "artifacts",
        AUTH_DEV_BYPASS_ROLE="ADMIN",
    )
    bus = InProcessEventBus()
    with use_event_bus(bus), TestClient(create_app(settings)) as test_client:
        application = cast(FastAPI, test_client.app)
        Base.metadata.create_all(application.state.database.engine)
        yield test_client, bus


def _score_and_correlate(client: TestClient) -> tuple[str, str]:
    run = client.post("/api/v1/simulation/runs", json=RUN_REQUEST).json()
    trained = client.post("/api/v1/detection/models/train", json=TRAIN_REQUEST).json()
    run_id, model_id = str(run["simulation_run_id"]), str(trained["model_id"])
    assert (
        client.post(
            f"/api/v1/detection/runs/{run_id}/score", json={"model_id": model_id}
        ).status_code
        == 200
    )
    return run_id, model_id


def test_run_id_is_stable_correlation_id_across_pipeline_events(
    isolated_client: tuple[TestClient, InProcessEventBus],
) -> None:
    client, bus = isolated_client
    seen: list[DomainEvent] = []  # type: ignore[type-arg]
    for event_type in (
        EventType.SCENARIO_STARTED,
        EventType.TELEMETRY_GENERATED,
        EventType.ANOMALY_DETECTED,
        EventType.INCIDENT_CREATED,
        EventType.PREDICTION_GENERATED,
    ):
        bus.subscribe(event_type, seen.append)

    run_id, model_id = _score_and_correlate(client)
    assert (
        client.post(
            f"/api/v1/correlation/runs/{run_id}/analyze", json={"model_id": model_id}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/prediction/runs/{run_id}/analyze",
            json={"model_id": model_id, "top_k": 3},
        ).status_code
        == 200
    )

    event_types_seen = {event.event_type for event in seen}
    assert event_types_seen == {
        EventType.SCENARIO_STARTED,
        EventType.TELEMETRY_GENERATED,
        EventType.ANOMALY_DETECTED,
        EventType.INCIDENT_CREATED,
        EventType.PREDICTION_GENERATED,
    }
    assert all(event.run_id == run_id for event in seen)
    assert all(event.correlation_id == run_id for event in seen)


def test_duplicate_scenario_start_is_idempotent_and_does_not_republish(
    isolated_client: tuple[TestClient, InProcessEventBus],
) -> None:
    client, bus = isolated_client
    started: list[DomainEvent] = []  # type: ignore[type-arg]
    bus.subscribe(EventType.SCENARIO_STARTED, started.append)

    first = client.post("/api/v1/simulation/runs", json=RUN_REQUEST).json()
    second = client.post("/api/v1/simulation/runs", json=RUN_REQUEST).json()

    assert first["simulation_run_id"] == second["simulation_run_id"]
    assert len(started) == 1, "scenario.started must publish exactly once per distinct run"


def test_incident_id_flows_into_response_decision_events(
    isolated_client: tuple[TestClient, InProcessEventBus],
) -> None:
    client, bus = isolated_client
    responses: list[DomainEvent] = []  # type: ignore[type-arg]
    for event_type in (EventType.RESPONSE_PROPOSED, EventType.RESPONSE_APPROVED):
        bus.subscribe(event_type, responses.append)

    run_id, model_id = _score_and_correlate(client)
    correlation = client.post(
        f"/api/v1/correlation/runs/{run_id}/analyze", json={"model_id": model_id}
    ).json()
    client.post(
        f"/api/v1/prediction/runs/{run_id}/analyze",
        json={"model_id": model_id, "top_k": 3},
    )
    analysis = client.post(
        f"/api/v1/response/runs/{run_id}/analyze",
        json={"model_id": model_id, "through_sequence_number": 10, "top_k": 10},
    ).json()
    recommendation = next(
        item
        for item in analysis["recommendations"]
        if item["required_approval_tier"] == "analyst_approval"
    )
    client.post(
        f"/api/v1/orchestration/runs/{run_id}/create",
        json={
            "model_id": model_id,
            "incident_candidate_id": recommendation["incident_candidate_id"],
            "selected_recommendation_id": recommendation["recommendation_id"],
            "through_sequence_number": 10,
        },
    )

    assert responses, "expected at least one response.* decision event"
    assert all(event.run_id == run_id for event in responses)
    assert all(event.incident_id == correlation["incident_candidate_id"] for event in responses)
