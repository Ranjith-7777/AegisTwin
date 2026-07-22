from fastapi.testclient import TestClient

from tests.test_prediction import prepare_prediction


def test_topology_inventory_is_stable_synthetic_and_documentation_only(client: TestClient) -> None:
    first = client.get("/api/v1/topology")
    second = client.get("/api/v1/topology")
    assert first.status_code == 200
    payload = first.json()
    assert payload["topology_version"] == "aegistwin-synthetic-topology-v1"
    assert [item["asset_id"] for item in payload["nodes"]] == [
        "employee-laptop-01",
        "administrator-workstation-01",
        "authentication-server-01",
        "examination-portal-01",
        "application-server-01",
        "examination-database-01",
        "backup-server-01",
        "monitoring-server-01",
    ]
    assert [item["edge_id"] for item in payload["edges"]] == [
        item["edge_id"] for item in second.json()["edges"]
    ]
    assert all(item["synthetic"] is True for item in payload["nodes"] + payload["edges"])
    serialized = str(payload)
    assert "192.0.2." not in serialized
    assert "198.51.100." not in serialized
    assert "203.0.113." not in serialized
    assert "simulation-egress-sink-01" not in serialized


def test_neighbourhood_expected_path_and_errors(client: TestClient) -> None:
    neighbourhood = client.get("/api/v1/topology/nodes/application-server-01/neighbours").json()
    assert neighbourhood["node"]["synthetic"] is True
    assert "examination-database-01" in {item["asset_id"] for item in neighbourhood["neighbours"]}
    path = client.get(
        "/api/v1/topology/paths",
        params={
            "source_asset_id": "employee-laptop-01",
            "destination_asset_id": "examination-database-01",
            "path_type": "expected",
        },
    ).json()["items"][0]
    assert path["ordered_node_ids"] == [
        "employee-laptop-01",
        "authentication-server-01",
        "application-server-01",
        "examination-database-01",
    ]
    assert path["hypothetical"] is False
    missing = client.get("/api/v1/topology/nodes/not-real")
    assert missing.status_code == 404
    assert missing.json()["error_code"] == "TOPOLOGY_ASSET_NOT_FOUND"
    unreachable = client.get(
        "/api/v1/topology/paths",
        params={
            "source_asset_id": "examination-database-01",
            "destination_asset_id": "employee-laptop-01",
        },
    )
    assert unreachable.status_code == 404
    assert unreachable.json()["error_code"] == "TOPOLOGY_PATH_UNREACHABLE"


def test_run_paths_are_causal_isolated_and_prediction_is_hypothetical(
    client: TestClient,
) -> None:
    run_id, model_id = prepare_prediction(client)
    client.post(
        f"/api/v1/prediction/runs/{run_id}/analyze",
        json={"model_id": model_id, "top_k": 3},
    )
    early = client.get(
        "/api/v1/topology/paths",
        params={
            "source_asset_id": "application-server-01",
            "destination_asset_id": "simulation-egress-sink-01",
            "path_type": "observed",
            "simulation_run_id": run_id,
            "through_sequence_number": 10,
        },
    )
    assert early.status_code == 404
    observed = client.get(
        "/api/v1/topology/paths",
        params={
            "source_asset_id": "application-server-01",
            "destination_asset_id": "simulation-egress-sink-01",
            "path_type": "observed",
            "simulation_run_id": run_id,
            "through_sequence_number": 11,
        },
    )
    assert observed.status_code == 200
    assert observed.json()["items"][0]["through_sequence_number"] == 11
    predicted = client.get(
        "/api/v1/topology/paths",
        params={
            "source_asset_id": "examination-database-01",
            "destination_asset_id": "backup-server-01",
            "path_type": "predicted",
            "simulation_run_id": run_id,
            "model_id": model_id,
            "through_sequence_number": 10,
        },
    )
    assert predicted.status_code == 200
    item = predicted.json()["items"][0]
    assert item["hypothetical"] is True
    assert item["statement"] == "Hypothetical path derived from synthetic ranked predictions."
    assert item["synthetic"] is True
    state = client.get(
        f"/api/v1/topology/runs/{run_id}/state",
        params={"model_id": model_id, "through_sequence_number": 10},
    ).json()
    assert "simulation-egress-sink-01" not in state["observed_asset_ids"]
    other_run, _ = prepare_prediction(client)
    other = client.get(
        f"/api/v1/topology/runs/{other_run}/state",
        params={"model_id": model_id, "through_sequence_number": 4},
    ).json()
    assert other["current_sequence_limit"] == 4
    assert "simulation-egress-sink-01" not in other["observed_asset_ids"]
