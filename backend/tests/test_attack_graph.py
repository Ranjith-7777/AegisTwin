from fastapi.testclient import TestClient

from tests.test_correlation import prepare


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
