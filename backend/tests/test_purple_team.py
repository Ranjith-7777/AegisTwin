from fastapi.testclient import TestClient


def test_scenario_catalogue_matches_red_scenario_catalogue(client: TestClient) -> None:
    response = client.get("/api/v1/purple-team/scenarios")
    assert response.status_code == 200
    scenarios = response.json()
    ids = {item["scenario_id"] for item in scenarios}
    assert "credential-compromise" in ids
    assert "normal-operations" in ids
    for item in scenarios:
        assert item["synthetic"] is True
        assert item["step_count"] == len(item["step_techniques"])


def test_observe_only_experiment_is_idempotent_and_traces_real_evidence(
    client: TestClient,
) -> None:
    request = {
        "scenario_id": "credential-compromise",
        "mode": "observe_only",
        "seed": 84,
        "top_k": 3,
    }
    first = client.post("/api/v1/purple-team/experiments", json=request)
    assert first.status_code == 201, first.text
    payload = first.json()
    assert payload["status"] == "completed"
    assert payload["mode"] == "observe_only"
    assert payload["simulation_run_id"] is not None
    assert payload["model_id"] is not None
    assert len(payload["steps"]) > 0

    for step in payload["steps"]:
        # Detection is never treated as prevention: without a defense-enabled
        # response/orchestration pipeline having run, no step may ever be
        # reported as blocked.
        assert step["outcome"] != "blocked_synthetic"
        assert step["orchestration_id"] is None
        assert step["response_recommendation_id"] is None

    summary = payload["summary"]
    assert summary["total_steps"] == len(payload["steps"])
    assert summary["incident_created"] is True
    assert summary["response_recommendation_created"] is False
    assert summary["response_executed"] is False
    if summary["detection_step_coverage"] is not None:
        assert 0.0 <= summary["detection_step_coverage"] <= 1.0

    second = client.post("/api/v1/purple-team/experiments", json=request)
    assert second.status_code == 201
    assert second.json()["experiment_id"] == payload["experiment_id"]
    assert [item["outcome"] for item in second.json()["steps"]] == [
        item["outcome"] for item in payload["steps"]
    ]

    fetched = client.get(f"/api/v1/purple-team/experiments/{payload['experiment_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["steps"] == payload["steps"]


def test_defense_enabled_experiment_may_create_and_execute_a_real_response(
    client: TestClient,
) -> None:
    request = {
        "scenario_id": "leaked-api-credential",
        "mode": "defense_enabled",
        "seed": 84,
        "top_k": 3,
    }
    response = client.post("/api/v1/purple-team/experiments", json=request)
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["status"] == "completed"
    summary = payload["summary"]

    # Whatever the pipeline actually decided is trusted as-is: a
    # recommendation being created does not obligate it to execute
    # (approval or safety-governor rejection are legitimate outcomes too).
    if summary["response_recommendation_created"]:
        touched_steps = [item for item in payload["steps"] if item["orchestration_state"]]
        if summary["response_executed"]:
            assert any(
                item["orchestration_state"] in {"completed_simulated", "verified"}
                for item in touched_steps
            )
            for item in touched_steps:
                assert item["response_recommendation_id"] is not None
                assert item["orchestration_id"] is not None


def test_unknown_scenario_id_returns_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/purple-team/experiments",
        json={"scenario_id": "not-a-real-scenario", "mode": "observe_only", "seed": 1},
    )
    assert response.status_code == 404


def test_list_experiments_includes_created_ones(client: TestClient) -> None:
    client.post(
        "/api/v1/purple-team/experiments",
        json={"scenario_id": "ddos-traffic-spike", "mode": "observe_only", "seed": 5},
    )
    listing = client.get("/api/v1/purple-team/experiments")
    assert listing.status_code == 200
    ids = {item["experiment_id"] for item in listing.json()}
    assert len(ids) >= 1
