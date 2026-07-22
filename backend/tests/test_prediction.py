from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient

from tests.test_correlation import prepare


def prepare_prediction(client: TestClient) -> tuple[str, str]:
    run_id, model_id = prepare(client)
    correlation = client.post(
        f"/api/v1/correlation/runs/{run_id}/analyze", json={"model_id": model_id}
    )
    assert correlation.status_code == 200
    return run_id, model_id


def test_prediction_is_deterministic_causal_and_idempotent(client: TestClient) -> None:
    run_id, model_id = prepare_prediction(client)
    endpoint = f"/api/v1/prediction/runs/{run_id}/analyze"
    first = client.post(endpoint, json={"model_id": model_id, "top_k": 3})
    assert first.status_code == 200
    assert first.json()["snapshot_count"] == 12
    page = client.get(
        f"/api/v1/prediction/runs/{run_id}/snapshots", params={"model_id": model_id}
    ).json()
    assert page["total"] == 12
    snapshots = page["items"]
    assert snapshots[0]["prediction_state"] == "insufficient_evidence"
    assert snapshots[-1]["current_stage_estimate"] == "session_conclusion"
    assert snapshots[-1]["hypotheses"] == []
    assert all(item["through_sequence_number"] == index for index, item in enumerate(snapshots, 1))
    for snapshot in snapshots:
        serialized = str(snapshot).lower()
        assert "scenario_id" not in serialized
        assert "scenario_name" not in serialized
        for hypothesis in snapshot["hypotheses"]:
            assert 1 <= hypothesis["rank"] <= 3
            assert hypothesis["synthetic"] is True
            assert "contradiction_penalty" in hypothesis["component_scores"]
    second = client.post(endpoint, json={"model_id": model_id, "top_k": 3})
    assert second.status_code == 200
    assert second.json()["hypothesis_count"] == first.json()["hypothesis_count"]
    repeated = client.get(
        f"/api/v1/prediction/runs/{run_id}/snapshots", params={"model_id": model_id}
    ).json()["items"]
    assert [item["prediction_snapshot_id"] for item in repeated] == [
        item["prediction_snapshot_id"] for item in snapshots
    ]


def test_prediction_evaluation_and_truth_isolation(client: TestClient) -> None:
    run_id, model_id = prepare_prediction(client)
    client.post(
        f"/api/v1/prediction/runs/{run_id}/analyze",
        json={"model_id": model_id, "top_k": 3},
    )
    response = client.post(
        f"/api/v1/prediction/runs/{run_id}/evaluate", json={"model_id": model_id}
    )
    assert response.status_code == 200
    payload = response.json()
    bounded = [
        "top_1_technique_accuracy",
        "top_3_technique_accuracy",
        "mean_reciprocal_rank",
        "next_tactic_accuracy",
        "next_asset_top_1_accuracy",
        "next_asset_top_3_accuracy",
        "objective_ranking_accuracy",
        "prediction_coverage",
        "insufficient_evidence_rate",
    ]
    assert all(0 <= payload["metrics"][name] <= 1 for name in bounded)
    assert payload["metrics"]["predictions_after_observation"] == 0
    assert payload["baseline_metrics"]["name"] == "most-common-valid-transition"
    service_source = Path("app/services/prediction_service.py").read_text(encoding="utf-8")
    assert "prediction_truth" not in service_source


def test_prediction_websocket_preserves_causal_order(client: TestClient) -> None:
    run_id, model_id = prepare_prediction(client)
    client.post(
        f"/api/v1/prediction/runs/{run_id}/analyze",
        json={"model_id": model_id, "top_k": 3},
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
                "prediction_enabled": True,
            }
        )
        ready = [websocket.receive_json()["message_type"] for _ in range(4)]
        assert ready == [
            "detection_ready",
            "correlation_ready",
            "prediction_ready",
            "playback_started",
        ]
        messages = [cast(dict[str, object], websocket.receive_json()) for _ in range(9)]
    kinds = [str(item["message_type"]) for item in messages]
    assert kinds.index("next_stage_prediction") > kinds.index("incident_candidate_update")
    prediction = next(item for item in messages if item["message_type"] == "next_stage_prediction")
    assert cast(dict[str, object], prediction["payload"])["through_sequence_number"] == 11
