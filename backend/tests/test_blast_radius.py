from fastapi.testclient import TestClient


def test_blast_radius_is_deterministic_and_reflects_real_topology(client: TestClient) -> None:
    first = client.post("/api/v1/blast-radius", json={"compromised_asset_ids": ["auth-pod-01"]})
    second = client.post("/api/v1/blast-radius", json={"compromised_asset_ids": ["auth-pod-01"]})
    assert first.status_code == 200
    assert first.json() == second.json()
    payload = first.json()
    assert payload["synthetic"] is True
    assert payload["compromised_asset_ids"] == ["auth-pod-01"]
    assert "iam-service-01" in payload["reachable_asset_ids"]
    assert payload["reachable_count"] == len(payload["reachable_asset_ids"])
    assert payload["critical_count"] == len(payload["critical_assets_at_risk"])
    assert 0.0 <= payload["score"]["total"] <= 100.0


def test_more_compromised_assets_never_shrinks_reachability(client: TestClient) -> None:
    single = client.post(
        "/api/v1/blast-radius", json={"compromised_asset_ids": ["auth-pod-01"]}
    ).json()
    combined = client.post(
        "/api/v1/blast-radius",
        json={"compromised_asset_ids": ["auth-pod-01", "object-storage-01"]},
    ).json()
    assert set(single["reachable_asset_ids"]) <= set(combined["reachable_asset_ids"]) | {
        "object-storage-01"
    }
    assert combined["score"]["total"] >= single["score"]["total"]


def test_unknown_asset_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/blast-radius", json={"compromised_asset_ids": ["not-a-real-asset"]}
    )
    assert response.status_code == 404
    assert response.json()["error_code"] == "BLAST_RADIUS_ASSET_NOT_FOUND"


def test_empty_list_is_rejected_by_schema_validation(client: TestClient) -> None:
    response = client.post("/api/v1/blast-radius", json={"compromised_asset_ids": []})
    assert response.status_code == 422
