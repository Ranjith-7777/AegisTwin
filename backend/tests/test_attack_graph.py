from typing import Any

from fastapi.testclient import TestClient

from tests.test_correlation import prepare


def prepare_leaked_credential(client: TestClient) -> tuple[str, str]:
    run = client.post(
        "/api/v1/simulation/runs",
        json={
            "scenario_id": "leaked-api-credential",
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


def test_potential_paths_are_deterministic_and_ranked(client: TestClient) -> None:
    first = client.get(
        "/api/v1/attack-graph/paths",
        params={"source_asset_id": "external-user-01", "path_type": "potential", "max_paths": 3},
    )
    second = client.get(
        "/api/v1/attack-graph/paths",
        params={"source_asset_id": "external-user-01", "path_type": "potential", "max_paths": 3},
    )
    assert first.status_code == 200
    payload = first.json()
    assert payload == second.json()
    assert payload["path_type"] == "potential"
    assert len(payload["paths"]) <= 3
    scores = [item["score"]["total"] for item in payload["paths"]]
    assert scores == sorted(scores, reverse=True)
    for path in payload["paths"]:
        assert path["synthetic"] is True
        assert path["ordered_asset_ids"][0] == "external-user-01"
        assert len(path["steps"]) == path["hop_count"]
        for step in path["steps"]:
            assert step["synthetic"] is True
            assert step["attack_semantics"]
            assert step["reason"]


def test_potential_path_to_explicit_target_matches_expected_topology_path(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/attack-graph/paths",
        params={
            "source_asset_id": "external-user-01",
            "target_asset_id": "cloud-database-01",
            "path_type": "potential",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    top_path = payload["paths"][0]
    assert top_path["ordered_asset_ids"][0] == "external-user-01"
    assert top_path["ordered_asset_ids"][-1] == "cloud-database-01"
    assert top_path["target_criticality"] == "critical"
    assert all(path["target_asset_id"] == "cloud-database-01" for path in payload["paths"])


def test_unknown_asset_returns_404(client: TestClient) -> None:
    response = client.get(
        "/api/v1/attack-graph/paths", params={"source_asset_id": "not-a-real-asset"}
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "ATTACK_GRAPH_ASSET_NOT_FOUND"


def test_observed_path_type_requires_a_run(client: TestClient) -> None:
    response = client.get(
        "/api/v1/attack-graph/paths",
        params={"source_asset_id": "external-user-01", "path_type": "observed"},
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "ATTACK_GRAPH_RUN_REQUIRED"


def test_observed_paths_are_bounded_by_real_telemetry_evidence(client: TestClient) -> None:
    run_id, model_id = prepare(client)
    observed = client.get(
        "/api/v1/attack-graph/paths",
        params={
            "source_asset_id": "external-user-01",
            "path_type": "observed",
            "simulation_run_id": run_id,
            "model_id": model_id,
        },
    )
    assert observed.status_code == 200
    potential = client.get(
        "/api/v1/attack-graph/paths",
        params={"source_asset_id": "external-user-01", "path_type": "potential"},
    ).json()
    observed_payload = observed.json()
    assert isinstance(potential["paths"], list)
    for path in observed_payload["paths"]:
        assert path["path_type"] == "observed"
        assert path["through_sequence_number"] is None


def test_path_types_remain_semantically_distinct(client: TestClient) -> None:
    run_id, model_id = prepare(client)
    results = {}
    for path_type in ("potential", "observed", "inferred", "predicted"):
        response = client.get(
            "/api/v1/attack-graph/paths",
            params={
                "source_asset_id": "external-user-01",
                "path_type": path_type,
                "simulation_run_id": run_id,
                "model_id": model_id,
            },
        )
        assert response.status_code == 200, response.text
        results[path_type] = response.json()
        for path in results[path_type]["paths"]:
            assert path["path_type"] == path_type


def test_observed_path_at_sequence_n_never_uses_evidence_from_n_plus_1(
    client: TestClient,
) -> None:
    """A concrete, empirical proof of sequence-bounding: the observed path
    from external-user-01 to iam-service-01 in leaked-api-credential only
    becomes discoverable once telemetry through sequence 3 is included
    (that step is where the over-scoped IAM token request actually
    happens) - it must be absent at sequences 1 and 2, which is only
    possible if the engine truly never leaks evidence from a later
    sequence backward."""

    run_id, model_id = prepare_leaked_credential(client)

    def paths_at(sequence: int) -> list[dict[str, Any]]:
        response = client.get(
            "/api/v1/attack-graph/paths",
            params={
                "source_asset_id": "external-user-01",
                "target_asset_id": "iam-service-01",
                "path_type": "observed",
                "simulation_run_id": run_id,
                "model_id": model_id,
                "through_sequence_number": sequence,
            },
        )
        assert response.status_code == 200, response.text
        result: list[dict[str, Any]] = response.json()["paths"]
        return result

    assert paths_at(1) == []
    assert paths_at(2) == []
    at_three = paths_at(3)
    assert len(at_three) == 1
    assert at_three[0]["ordered_asset_ids"][-1] == "iam-service-01"
    # once the evidence exists it remains discoverable at every later sequence too
    assert len(paths_at(4)) == 1
    assert len(paths_at(1000)) == 1
