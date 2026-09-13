from fastapi.testclient import TestClient

from tests.test_attack_graph import prepare_leaked_credential


def test_blast_radius_is_deterministic_and_reflects_real_topology(client: TestClient) -> None:
    first = client.post("/api/v1/blast-radius", json={"compromised_asset_ids": ["auth-pod-01"]})
    second = client.post("/api/v1/blast-radius", json={"compromised_asset_ids": ["auth-pod-01"]})
    assert first.status_code == 200
    assert first.json() == second.json()
    payload = first.json()
    assert payload["synthetic"] is True
    assert payload["mode"] == "hypothetical"
    assert payload["through_sequence_number"] is None
    assert payload["compromised_asset_ids"] == ["auth-pod-01"]
    assert "iam-service-01" in payload["reachable_asset_ids"]
    # directly-affected must never also appear as "reachable" - they are
    # mutually exclusive categories, not overlapping ones.
    assert set(payload["directly_affected_asset_ids"]).isdisjoint(payload["reachable_asset_ids"])
    assert payload["reachable_count"] == len(payload["reachable_asset_ids"])
    assert payload["critical_count"] == len(payload["critical_assets_at_risk"])
    assert 0.0 <= payload["score"]["total"] <= 100.0


def test_dependent_assets_are_distinct_from_reachable_assets(client: TestClient) -> None:
    payload = client.post(
        "/api/v1/blast-radius", json={"compromised_asset_ids": ["auth-pod-01"]}
    ).json()
    # a dependent service (calls into the affected/reachable set) must
    # never simultaneously be reported as attacker-reachable - those are
    # different operational claims.
    assert set(payload["dependent_asset_ids"]).isdisjoint(payload["reachable_asset_ids"])
    assert set(payload["dependent_asset_ids"]).isdisjoint(payload["compromised_asset_ids"])
    assert payload["dependent_count"] == len(payload["dependent_asset_ids"])


def test_unrelated_assets_are_excluded(client: TestClient) -> None:
    payload = client.post(
        "/api/v1/blast-radius", json={"compromised_asset_ids": ["monitoring-service-01"]}
    ).json()
    involved = (
        set(payload["compromised_asset_ids"])
        | set(payload["reachable_asset_ids"])
        | set(payload["dependent_asset_ids"])
    )
    # Nothing routes backward into the internet-facing entry point from an
    # internal asset - it must be excluded from every category.
    assert "external-user-01" not in involved


def test_hypothetical_mode_allows_any_asset_regardless_of_evidence(client: TestClient) -> None:
    # No simulation_run_id at all - a pure static what-if, so an asset
    # with zero telemetry evidence anywhere is still a valid request.
    response = client.post(
        "/api/v1/blast-radius", json={"compromised_asset_ids": ["object-storage-01"]}
    )
    assert response.status_code == 200
    assert response.json()["mode"] == "hypothetical"


def test_evidence_bound_mode_rejects_an_asset_unsupported_by_evidence(
    client: TestClient,
) -> None:
    run_id, _ = prepare_leaked_credential(client)
    # iam-service-01 only becomes evidenced at sequence 3 (the over-scoped
    # token request) in leaked-api-credential - requesting it as
    # compromised at sequence 1 must be rejected, not silently accepted.
    response = client.post(
        "/api/v1/blast-radius",
        json={
            "compromised_asset_ids": ["iam-service-01"],
            "simulation_run_id": run_id,
            "through_sequence_number": 1,
        },
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "BLAST_RADIUS_EVIDENCE_REQUIRED"


def test_evidence_bound_sequence_n_cannot_use_evidence_from_n_plus_1(
    client: TestClient,
) -> None:
    run_id, _ = prepare_leaked_credential(client)

    def compromise_iam_at(sequence: int) -> int:
        response = client.post(
            "/api/v1/blast-radius",
            json={
                "compromised_asset_ids": ["iam-service-01"],
                "simulation_run_id": run_id,
                "through_sequence_number": sequence,
            },
        )
        return int(response.status_code)

    assert compromise_iam_at(1) == 422
    assert compromise_iam_at(2) == 422
    assert compromise_iam_at(3) == 200
    assert compromise_iam_at(4) == 200


def test_evidence_bound_mode_accepts_an_evidenced_asset_and_reports_resolved_sequence(
    client: TestClient,
) -> None:
    run_id, _ = prepare_leaked_credential(client)
    response = client.post(
        "/api/v1/blast-radius",
        json={
            "compromised_asset_ids": ["external-user-01"],
            "simulation_run_id": run_id,
            "through_sequence_number": 1,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "evidence_bound"
    assert payload["through_sequence_number"] == 1


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
