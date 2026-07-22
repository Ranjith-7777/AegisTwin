from typing import cast

from fastapi.testclient import TestClient


def prepare(client: TestClient) -> tuple[str, str]:
    run = client.post(
        "/api/v1/simulation/runs",
        json={
            "scenario_id": "staged-compromise-demo",
            "seed": 84,
            "start_time": "2026-07-21T01:30:00Z",
            "playback_speed": 50,
        },
    ).json()
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
    ).json()
    run_id, model_id = str(run["simulation_run_id"]), str(trained["model_id"])
    assert (
        client.post(
            f"/api/v1/detection/runs/{run_id}/score", json={"model_id": model_id}
        ).status_code
        == 200
    )
    return run_id, model_id


def test_staged_scenario_is_deterministic_and_benchmarks_remain_frozen(client: TestClient) -> None:
    scenarios = {
        item["scenario_id"]: item for item in client.get("/api/v1/simulation/scenarios").json()
    }
    assert len(scenarios["normal-operations"]["steps"]) == 6
    assert len(scenarios["credential-compromise"]["steps"]) == 7
    assert len(scenarios["staged-compromise-demo"]["steps"]) == 12
    request = {
        "scenario_id": "staged-compromise-demo",
        "seed": 9,
        "start_time": "2026-07-21T09:00:00Z",
        "playback_speed": 10,
    }
    first = client.post("/api/v1/simulation/runs", json=request).json()
    second = client.post("/api/v1/simulation/runs", json=request).json()
    assert first == second


def test_conservative_mapping_correlation_and_idempotence(client: TestClient) -> None:
    run_id, model_id = prepare(client)
    first = client.post(f"/api/v1/correlation/runs/{run_id}/analyze", json={"model_id": model_id})
    assert first.status_code == 200
    result = first.json()
    assert result["synthetic"] is True
    observations = client.get(f"/api/v1/correlation/runs/{run_id}/techniques").json()["items"]
    technique_ids = {item["technique_id"] for item in observations}
    assert {"T1110.001", "T1078", "T1098", "T1021", "T1567"} <= technique_ids
    assert "T1068" not in technique_ids
    assert "T1041" not in technique_ids
    assert all(item["synthetic"] for item in observations)
    second = client.post(
        f"/api/v1/correlation/runs/{run_id}/analyze", json={"model_id": model_id}
    ).json()
    assert second["incident_candidate_id"] == result["incident_candidate_id"]
    assert second["technique_observation_count"] == result["technique_observation_count"]
    candidates = client.get(f"/api/v1/correlation/runs/{run_id}/incidents").json()["items"]
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["correlation_state"] in {"monitoring", "correlated", "high_priority"}
    assert candidate["correlation_score"] <= 1
    evidence = client.get(
        f"/api/v1/correlation/incidents/{candidate['incident_candidate_id']}/evidence"
    ).json()
    assert len(evidence) == candidate["evidence_count"]
    assert all(item["synthetic"] for item in evidence)


def test_correlation_requires_scoring_and_catalogue_is_local(client: TestClient) -> None:
    run = client.post(
        "/api/v1/simulation/runs",
        json={
            "scenario_id": "staged-compromise-demo",
            "seed": 4,
            "start_time": "2026-07-21T09:00:00Z",
            "playback_speed": 10,
        },
    ).json()
    response = client.post(
        f"/api/v1/correlation/runs/{run['simulation_run_id']}/analyze", json={"model_id": "missing"}
    )
    assert response.status_code == 404
    catalogue = client.get("/api/v1/mitre/techniques").json()
    assert len(catalogue) == 7
    assert all(item["synthetic"] for item in catalogue)


def test_correlation_websocket_preserves_causal_order(client: TestClient) -> None:
    run_id, model_id = prepare(client)
    assert (
        client.post(
            f"/api/v1/correlation/runs/{run_id}/analyze", json={"model_id": model_id}
        ).status_code
        == 200
    )
    with client.websocket_connect(
        f"/api/v1/ws/simulation/runs/{run_id}?after_sequence=10"
    ) as websocket:
        websocket.receive_json()
        websocket.receive_json()
        websocket.send_json(
            {
                "message_type": "start",
                "detection_enabled": True,
                "model_id": model_id,
                "correlation_enabled": True,
            }
        )
        assert websocket.receive_json()["message_type"] == "detection_ready"
        assert websocket.receive_json()["message_type"] == "correlation_ready"
        assert websocket.receive_json()["message_type"] == "playback_started"
        messages = [cast(dict[str, object], websocket.receive_json()) for _ in range(7)]
    types = [str(item["message_type"]) for item in messages]
    assert types[:4] == [
        "telemetry_event",
        "anomaly_assessment",
        "mitre_technique_observation",
        "incident_candidate_update",
    ]
    assert types[-1] == "playback_completed"
    assert all(item["synthetic"] is True for item in messages)
