from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from fastapi.testclient import TestClient

RUN_REQUEST = {
    "scenario_id": "credential-compromise",
    "seed": 42,
    "start_time": "2026-07-21T01:30:00Z",
    "playback_speed": 2.0,
}


def create_run(client: TestClient, **overrides: object) -> dict[str, object]:
    payload = {**RUN_REQUEST, **overrides}
    response = client.post("/api/v1/simulation/runs", json=payload)
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def events_for_run(client: TestClient, run_id: object) -> list[dict[str, object]]:
    response = client.get(
        "/api/v1/telemetry/events",
        params={"simulation_run_id": str(run_id), "page_size": 100},
    )
    assert response.status_code == 200
    body = cast(dict[str, object], response.json())
    return cast(list[dict[str, object]], body["items"])


def test_scenario_listing_and_inventory_are_synthetic(client: TestClient) -> None:
    response = client.get("/api/v1/simulation/scenarios")
    assert response.status_code == 200
    scenarios = response.json()
    assert [scenario["scenario_id"] for scenario in scenarios] == [
        "normal-operations",
        "credential-compromise",
        "staged-compromise-demo",
        "leaked-api-credential",
        "suspicious-kubernetes-pod",
        "ddos-traffic-spike",
    ]
    assert all(scenario["synthetic"] is True for scenario in scenarios)

    inventory = client.get("/api/v1/simulation/infrastructure").json()
    assert len(inventory) == 13
    assert {asset["asset_id"] for asset in inventory} >= {
        "external-user-01",
        "kubernetes-cluster-01",
        "cloud-database-01",
        "monitoring-service-01",
    }
    assert all(asset["synthetic"] is True for asset in inventory)


def test_valid_scenario_run_is_created_and_persisted(client: TestClient) -> None:
    run = create_run(client)
    assert run["scenario_id"] == "credential-compromise"
    assert run["event_count"] == 7
    assert run["status"] == "completed"

    fetched = client.get(f"/api/v1/simulation/runs/{run['simulation_run_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["simulation_run_id"] == run["simulation_run_id"]
    assert len(events_for_run(client, run["simulation_run_id"])) == 7


def test_invalid_scenario_is_rejected_with_structured_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/simulation/runs",
        json={**RUN_REQUEST, "scenario_id": "unknown-scenario"},
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "SCENARIO_NOT_FOUND"
    assert response.json()["correlation_id"] == response.headers["X-Correlation-ID"]


def test_same_seed_and_start_time_produce_identical_events(client: TestClient) -> None:
    first = create_run(client)
    second = create_run(client)
    assert first == second
    assert events_for_run(client, first["simulation_run_id"]) == events_for_run(
        client, second["simulation_run_id"]
    )


def test_different_seeds_change_permitted_synthetic_values(client: TestClient) -> None:
    first = create_run(client, seed=10)
    second = create_run(client, seed=11)
    first_events = events_for_run(client, first["simulation_run_id"])
    second_events = events_for_run(client, second["simulation_run_id"])
    assert (
        first_events[0]["failed_attempts"] != second_events[0]["failed_attempts"]
        or first_events[-1]["bytes_transferred"] != second_events[-1]["bytes_transferred"]
    )


def test_event_ordering_is_stable(client: TestClient) -> None:
    run = create_run(client)
    events = events_for_run(client, run["simulation_run_id"])
    timestamps = [
        datetime.fromisoformat(str(event["timestamp"]).replace("Z", "+00:00")) for event in events
    ]
    assert timestamps == sorted(timestamps)
    assert timestamps[0] == datetime(2026, 7, 21, 1, 30, tzinfo=UTC)


def test_telemetry_filtering_works(client: TestClient) -> None:
    run = create_run(client)
    run_id = run["simulation_run_id"]
    by_type = client.get(
        "/api/v1/telemetry/events",
        params={"simulation_run_id": run_id, "event_type": "authentication"},
    ).json()
    assert by_type["total"] == 2
    assert all(item["event_type"] == "authentication" for item in by_type["items"])

    high = client.get(
        "/api/v1/telemetry/events",
        params={"simulation_run_id": run_id, "minimum_severity": "high"},
    ).json()
    assert high["total"] == 3
    assert {item["severity"] for item in high["items"]} == {"high"}

    by_source = client.get(
        "/api/v1/telemetry/events",
        params={"simulation_run_id": run_id, "source_id": "application-pod-01"},
    ).json()
    assert by_source["total"] == 1

    by_user = client.get(
        "/api/v1/telemetry/events",
        params={"simulation_run_id": run_id, "user_id": "synthetic-user-01"},
    ).json()
    assert by_user["total"] == 7


def test_telemetry_pagination_is_stable(client: TestClient) -> None:
    run = create_run(client)
    parameters = {"simulation_run_id": run["simulation_run_id"], "page_size": 3}
    first = client.get("/api/v1/telemetry/events", params={**parameters, "page": 1}).json()
    second = client.get("/api/v1/telemetry/events", params={**parameters, "page": 2}).json()
    third = client.get("/api/v1/telemetry/events", params={**parameters, "page": 3}).json()
    assert (first["total"], first["pages"]) == (7, 3)
    assert [len(first["items"]), len(second["items"]), len(third["items"])] == [3, 3, 1]
    ids = [item["event_id"] for page in (first, second, third) for item in page["items"]]
    assert len(ids) == len(set(ids)) == 7


def test_event_detail_and_missing_resources(client: TestClient) -> None:
    run = create_run(client)
    event = events_for_run(client, run["simulation_run_id"])[0]
    response = client.get(f"/api/v1/telemetry/events/{event['event_id']}")
    assert response.status_code == 200
    assert response.json()["metadata"]["synthetic"] is True
    missing = client.get("/api/v1/telemetry/events/missing-event")
    assert missing.status_code == 404
    assert missing.json()["error_code"] == "TELEMETRY_EVENT_NOT_FOUND"


def test_events_contain_no_model_score_or_confirmed_verdict(client: TestClient) -> None:
    run = create_run(client)
    serialised = str(events_for_run(client, run["simulation_run_id"])).lower()
    for prohibited in ("anomaly_score", "confirmed_attack", "attack_verdict"):
        assert prohibited not in serialised
    assert "'synthetic': true" in serialised


def test_malformed_run_input_returns_typed_validation_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/simulation/runs",
        json={**RUN_REQUEST, "start_time": "2026-07-21T01:30:00", "playback_speed": 0},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"
