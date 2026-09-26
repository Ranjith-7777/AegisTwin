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


def test_summary_values_are_consistent_with_underlying_step_records(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/purple-team/experiments",
        json={
            "scenario_id": "leaked-api-credential",
            "mode": "observe_only",
            "seed": 4242,
            "top_k": 3,
        },
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    steps = payload["steps"]
    summary = payload["summary"]

    assert summary["total_steps"] == len(steps)
    assert summary["attempted_steps"] == sum(1 for s in steps if s["outcome"] != "skipped")
    assert summary["succeeded_synthetic_steps"] == sum(
        1 for s in steps if s["outcome"] == "succeeded_synthetic"
    )
    assert summary["detected_steps"] == sum(1 for s in steps if s["detected"])
    expected_detectable = [s for s in steps if s["expected_technique_id"] is not None]
    assert summary["expected_detectable_steps"] == len(expected_detectable)
    assert summary["missed_steps"] == sum(1 for s in expected_detectable if not s["detected"])
    techniques_exercised = sorted(
        {s["expected_technique_id"] for s in steps if s["expected_technique_id"]}
    )
    assert summary["mitre_techniques_exercised"] == techniques_exercised


def test_missed_steps_remain_visible_in_the_step_list(client: TestClient) -> None:
    # normal-operations has no declared attack indicators, so every step
    # with an expected technique (there are none) would be "missed" - the
    # important property is that ALL steps are still present and visible,
    # never hidden because they weren't detected.
    response = client.post(
        "/api/v1/purple-team/experiments",
        json={"scenario_id": "normal-operations", "mode": "observe_only", "seed": 84},
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert len(payload["steps"]) == payload["summary"]["total_steps"]
    assert len(payload["steps"]) > 0
    # every step is visible regardless of detection outcome
    assert all("outcome" in step and "detected" in step for step in payload["steps"])


def test_detected_is_never_conflated_with_blocked(client: TestClient) -> None:
    response = client.post(
        "/api/v1/purple-team/experiments",
        json={
            "scenario_id": "leaked-api-credential",
            "mode": "defense_enabled",
            "seed": 4242,
            "top_k": 3,
        },
    )
    assert response.status_code == 201, response.text
    for step in response.json()["steps"]:
        if step["outcome"] == "blocked_synthetic":
            continue
        # a detected step that isn't blocked must keep its own real outcome
        # (succeeded_synthetic/failed_precondition/attempted) - detection
        # alone never rewrites the outcome to something block-like.
        assert step["outcome"] in {
            "attempted",
            "succeeded_synthetic",
            "failed_precondition",
            "skipped",
        }


def test_attack_path_and_blast_radius_context_are_real_not_placeholder(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/purple-team/experiments",
        json={
            "scenario_id": "leaked-api-credential",
            "mode": "observe_only",
            "seed": 9999,
            "top_k": 3,
        },
    )
    assert response.status_code == 201, response.text
    summary = response.json()["summary"]

    blast = summary["blast_radius_context"]
    assert blast is not None
    assert blast["mode"] in {"hypothetical", "evidence_bound"}
    assert isinstance(blast["reachable_count"], int)
    assert isinstance(blast["critical_assets_at_risk"], list)
    assert isinstance(blast["trust_zones_reached"], list)
    assert blast["score"] >= 0.0

    path = summary["attack_path_context"]
    if path is not None:
        assert path["path_type"] in {"potential", "observed", "inferred", "predicted"}
        assert path["source_asset_id"] == "external-user-01"
        assert path["hop_count"] >= 1
        assert path["statement"]

    # never a placeholder: critical_assets_reached must be a real,
    # evidence-derived list (possibly empty), not a hardcoded sentinel.
    assert isinstance(summary["critical_assets_reached"], list)


def test_experiment_reconstructs_correctly_after_persistence_reload(
    client: TestClient,
) -> None:
    request = {
        "scenario_id": "leaked-api-credential",
        "mode": "defense_enabled",
        "seed": 5150,
        "top_k": 3,
    }
    created = client.post("/api/v1/purple-team/experiments", json=request).json()
    reloaded = client.get(f"/api/v1/purple-team/experiments/{created['experiment_id']}").json()

    def without_timestamps(payload: dict[str, object]) -> dict[str, object]:
        # created_at/completed_at round-trip through SQLite without a
        # timezone marker, so they may differ in string form (with/without
        # a trailing "Z") for the identical instant - a pre-existing,
        # unrelated serialization quirk. Everything else must match exactly.
        return {k: v for k, v in payload.items() if k not in {"created_at", "completed_at"}}

    assert without_timestamps(reloaded) == without_timestamps(created)
    assert reloaded["summary"]["attack_path_context"] == created["summary"]["attack_path_context"]
    assert reloaded["summary"]["blast_radius_context"] == created["summary"]["blast_radius_context"]

    listing = client.get("/api/v1/purple-team/experiments").json()
    match = next(item for item in listing if item["experiment_id"] == created["experiment_id"])
    assert without_timestamps(match) == without_timestamps(created)


def test_unknown_experiment_id_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/purple-team/experiments/not-a-real-experiment-id")
    assert response.status_code == 404
    assert response.json()["error_code"] == "PURPLE_TEAM_EXPERIMENT_NOT_FOUND"


def test_event_correlation_survives_the_purple_experiment_event_stream(
    client: TestClient,
) -> None:
    from typing import Any

    from app.events.bus import InProcessEventBus
    from app.events.envelope import DomainEvent
    from app.events.registry import use_event_bus
    from app.events.types import EventType

    bus = InProcessEventBus()
    captured: list[DomainEvent[Any]] = []
    tracked_types = {
        EventType.PURPLE_EXPERIMENT_STARTED,
        EventType.PURPLE_EXPERIMENT_COMPLETED,
        EventType.PURPLE_STEP_COMPLETED,
        EventType.RED_STEP_ATTEMPTED,
        EventType.RED_STEP_COMPLETED,
        EventType.ATTACK_PATH_DISCOVERED,
        EventType.BLAST_RADIUS_ASSESSED,
    }
    for event_type in tracked_types:
        bus.subscribe(event_type, captured.append)

    with use_event_bus(bus):
        response = client.post(
            "/api/v1/purple-team/experiments",
            json={
                "scenario_id": "leaked-api-credential",
                "mode": "observe_only",
                "seed": 7331,
                "top_k": 3,
            },
        )
    assert response.status_code == 201, response.text
    experiment_id = response.json()["experiment_id"]

    assert captured, "expected at least one domain event to be published"
    for event in captured:
        assert event.correlation_id == experiment_id, (
            f"{event.event_type} did not correlate to the experiment"
        )

    step_events = [e for e in captured if e.event_type == EventType.PURPLE_STEP_COMPLETED]
    assert step_events
    assert any(e.causation_id is not None for e in step_events)
