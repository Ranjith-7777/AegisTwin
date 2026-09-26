from pathlib import Path

from fastapi.testclient import TestClient

from tests.test_prediction import prepare_prediction


def prepare_response(client: TestClient) -> tuple[str, str]:
    run_id, model_id = prepare_prediction(client)
    prediction = client.post(
        f"/api/v1/prediction/runs/{run_id}/analyze",
        json={"model_id": model_id, "top_k": 3},
    )
    assert prediction.status_code == 200
    return run_id, model_id


def test_playbook_catalogue_is_safe_versioned_and_deterministic(client: TestClient) -> None:
    first = client.get("/api/v1/response/playbooks")
    second = client.get("/api/v1/response/playbooks")
    assert first.status_code == 200
    assert first.json() == second.json()
    playbooks = first.json()
    assert len(playbooks) == 10
    assert all(item["synthetic"] is True for item in playbooks)
    assert all(
        item["catalogue_version"] == "aegisarena-blue-agent-playbooks-v1" for item in playbooks
    )
    high_impact = [item for item in playbooks if item["default_operational_impact"] == "high"]
    assert all(item["approval_tier"] == "administrator_approval" for item in high_impact)
    serialized = str(playbooks).lower()
    assert not any(term in serialized for term in ["powershell", "sudo", "iptables", "subprocess"])


def test_response_analysis_is_ranked_idempotent_synthetic_and_causal(client: TestClient) -> None:
    run_id, model_id = prepare_response(client)
    endpoint = f"/api/v1/response/runs/{run_id}/analyze"
    request = {
        "model_id": model_id,
        "through_sequence_number": 10,
        "prediction_enabled": True,
        "top_k": 5,
    }
    first = client.post(endpoint, json=request)
    assert first.status_code == 200, first.text
    payload = first.json()
    assert payload["through_sequence_number"] == 10
    assert payload["recommendation_count"] == 5
    recommendations = payload["recommendations"]
    assert [item["rank"] for item in recommendations] == list(range(1, 6))
    # The Blue Agent ranks on Defense Score, not on the raw composite score.
    assert [item["defense_score"] for item in recommendations] == sorted(
        [item["defense_score"] for item in recommendations], reverse=True
    )
    for item in recommendations:
        components = item["defense_components"]
        assert set(components) == {
            "security_improvement",
            "service_disruption",
            "resource_cost",
            "sla_penalty",
            "defense_score",
        }
        assert components["defense_score"] == item["defense_score"]
        assert item["defense_score"] == round(
            components["security_improvement"]
            - components["service_disruption"]
            - components["resource_cost"]
            - components["sla_penalty"],
            6,
        )
        assert "Defense Score" in item["defense_explanation"]
    assert all(item["synthetic"] and item["simulation"]["synthetic"] for item in recommendations)
    assert all(item["through_sequence_number"] == 10 for item in recommendations)
    assert all(item["required_approval_tier"] != "prohibited" for item in recommendations)
    assert all(
        "guarantee containment" in " ".join(item["warnings"]).lower() for item in recommendations
    )
    repeated = client.post(endpoint, json=request).json()
    assert repeated["response_analysis_id"] == payload["response_analysis_id"]
    assert [item["recommendation_id"] for item in repeated["recommendations"]] == [
        item["recommendation_id"] for item in recommendations
    ]


def test_clone_simulation_preserves_base_topology_and_reports_distinct_paths(
    client: TestClient,
) -> None:
    run_id, model_id = prepare_response(client)
    before = client.get("/api/v1/topology", params={"include_synthetic_sink": True}).json()
    payload = client.post(
        f"/api/v1/response/runs/{run_id}/analyze",
        json={"model_id": model_id, "through_sequence_number": 10, "top_k": 10},
    ).json()
    after = client.get("/api/v1/topology", params={"include_synthetic_sink": True}).json()
    assert before["nodes"] == after["nodes"]
    assert before["edges"] == after["edges"]
    simulations = [item["simulation"] for item in payload["recommendations"]]
    routes = [
        item
        for item in payload["recommendations"]
        if item["playbook_id"] == "block-synthetic-route"
    ]
    assert routes, [item["playbook_id"] for item in payload["recommendations"]]
    assert all(item["correlated_paths_interrupted"] >= 0 for item in simulations)
    assert all(item["predicted_paths_interrupted"] >= 0 for item in simulations)
    assert any(item["expected_relationships_affected"] > 0 for item in simulations), [
        (item["playbook_id"], item["target_id"], item["simulation"]["changed_edge_ids"])
        for item in payload["recommendations"]
    ]
    assert all(
        len(item["paths_before"]) <= 40 and len(item["paths_after"]) <= 40 for item in simulations
    )


def test_sequence_prefix_excludes_future_evidence_and_force_is_transactional(
    client: TestClient,
) -> None:
    run_id, model_id = prepare_response(client)
    endpoint = f"/api/v1/response/runs/{run_id}/analyze"
    early = client.post(
        endpoint,
        json={"model_id": model_id, "through_sequence_number": 4, "top_k": 5},
    )
    assert early.status_code == 200, early.text
    serialized = str(early.json()).lower()
    assert "sequence 5" not in serialized
    forced = client.post(
        endpoint,
        json={
            "model_id": model_id,
            "through_sequence_number": 4,
            "top_k": 5,
            "force_reanalyze": True,
        },
    )
    assert forced.status_code == 200
    assert forced.json()["response_analysis_id"] == early.json()["response_analysis_id"]
    page = client.get(
        f"/api/v1/response/runs/{run_id}/recommendations",
        params={"model_id": model_id},
    ).json()
    assert page["total"] == forced.json()["recommendation_count"]


def test_response_source_contains_no_execution_integrations() -> None:
    source = Path("app/services/response_service.py").read_text(encoding="utf-8").lower()
    assert not any(term in source for term in ["subprocess", "socket.", "requests.", "os.system"])
    assert "scenario_id ==" not in source
