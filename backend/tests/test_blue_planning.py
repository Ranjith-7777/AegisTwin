from typing import Any, cast

from fastapi.testclient import TestClient


def prepare(client: TestClient) -> tuple[str, str, str]:
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
    analyze = client.post(
        f"/api/v1/correlation/runs/{run_id}/analyze", json={"model_id": model_id}
    ).json()
    return run_id, model_id, str(analyze["incident_candidate_id"])


def compare(
    client: TestClient, run_id: str, model_id: str, candidate_id: str, sequence: int = 10
) -> dict[str, Any]:
    return cast(
        "dict[str, Any]",
        client.post(
            f"/api/v1/blue-planning/runs/{run_id}/compare",
            json={
                "model_id": model_id,
                "incident_candidate_id": candidate_id,
                "through_sequence_number": sequence,
                "top_k": 5,
            },
        ).json(),
    )


def test_comparison_produces_ranked_candidates_with_a_recommended_plan(
    client: TestClient,
) -> None:
    run_id, model_id, candidate_id = prepare(client)
    result = compare(client, run_id, model_id, candidate_id)
    assert len(result["candidates"]) >= 2
    scores = [c["utility_score"]["total"] for c in result["candidates"]]
    assert scores == sorted(scores, reverse=True)
    assert result["recommended_recommendation_id"] is not None
    recommended = [c for c in result["candidates"] if c["recommended"]]
    assert len(recommended) == 1
    assert recommended[0]["recommendation_id"] == result["recommended_recommendation_id"]


def test_observation_only_playbook_never_shows_a_false_security_gain(
    client: TestClient,
) -> None:
    """Regression test for a real bug: an observe-only mutation (annotate_node)
    must never be credited with removing attack paths it never touched."""

    run_id, model_id, candidate_id = prepare(client)
    result = compare(client, run_id, model_id, candidate_id)
    monitoring = next(
        c for c in result["candidates"] if c["playbook_id"] == "increase-synthetic-monitoring"
    )
    assert monitoring["security_gain_evidence"]["security_gain"] == 0.0
    assert (
        monitoring["security_gain_evidence"]["attack_paths_before"]
        == (monitoring["security_gain_evidence"]["attack_paths_after"])
    )


def test_an_edge_removing_playbook_shows_real_nonzero_security_gain(client: TestClient) -> None:
    run_id, model_id, candidate_id = prepare(client)
    result = compare(client, run_id, model_id, candidate_id)
    by_id = {c["playbook_id"]: c for c in result["candidates"]}
    assert "block-synthetic-route" in by_id
    edge_removal = by_id["block-synthetic-route"]
    assert edge_removal["security_gain_evidence"]["security_gain"] > 0.0
    assert (
        edge_removal["security_gain_evidence"]["attack_paths_after"]
        < edge_removal["security_gain_evidence"]["attack_paths_before"]
    )


def test_what_if_comparison_never_mutates_the_persisted_topology(client: TestClient) -> None:
    before = client.get("/api/v1/topology", params={"include_synthetic_sink": True}).json()
    run_id, model_id, candidate_id = prepare(client)
    compare(client, run_id, model_id, candidate_id)
    after = client.get("/api/v1/topology", params={"include_synthetic_sink": True}).json()
    assert before["nodes"] == after["nodes"]
    assert before["edges"] == after["edges"]


def test_comparison_is_deterministic_for_identical_inputs(client: TestClient) -> None:
    run_id, model_id, candidate_id = prepare(client)
    first = compare(client, run_id, model_id, candidate_id)
    second = compare(client, run_id, model_id, candidate_id)
    assert first["candidates"] == second["candidates"]
    assert first["decision_confidence"] == second["decision_confidence"]


def test_decision_confidence_is_never_called_a_probability(client: TestClient) -> None:
    run_id, model_id, candidate_id = prepare(client)
    result = compare(client, run_id, model_id, candidate_id)
    assert "not a calibrated probability" in result["decision_confidence"]["note"]


def test_assessment_is_reconstructable_after_reload(client: TestClient) -> None:
    from app.services.blue_planning_service import blue_planning_service

    run_id, model_id, candidate_id = prepare(client)
    result = compare(client, run_id, model_id, candidate_id)
    assessment_id = blue_planning_service.assessment_id(run_id, model_id, candidate_id, 10)
    reloaded = client.get(f"/api/v1/blue-planning/assessments/{assessment_id}").json()
    assert reloaded["candidates"] == result["candidates"]
    assert reloaded["recommended_recommendation_id"] == result["recommended_recommendation_id"]


def test_unknown_assessment_id_is_404(client: TestClient) -> None:
    response = client.get("/api/v1/blue-planning/assessments/does-not-exist")
    assert response.status_code == 404


def test_a_policy_failing_candidate_is_never_recommended(client: TestClient) -> None:
    run_id, model_id, candidate_id = prepare(client)
    client.put(
        "/api/v1/autonomy",
        json={"mode": "autonomous", "updated_by": "analyst-1", "confirm": True},
    )
    result = compare(client, run_id, model_id, candidate_id)
    for candidate in result["candidates"]:
        if not candidate["policy_pass"]:
            assert candidate["recommended"] is False
