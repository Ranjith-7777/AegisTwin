from __future__ import annotations

from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient

from app.schemas.detection import DetectionTrainingRequest, SeedRange
from app.services.detection_dataset_service import detection_dataset_service
from app.services.detection_scoring_service import detection_scoring_service
from app.services.feature_pipeline_service import (
    EXCLUDED_LEAKAGE_FIELDS,
    INCLUDED_FEATURES,
    feature_pipeline_service,
)
from app.services.model_artifact_service import model_artifact_service

TRAINING_REQUEST = {
    "training_seed_range": {"start": 1, "end": 5},
    "validation_seed_range": {"start": 6, "end": 10},
    "evaluation_seed_range": {"start": 11, "end": 13},
    "random_state": 17,
    "target_false_positive_rate": 0.1,
    "n_estimators": 100,
}
TARGET_FALSE_POSITIVE_RATE = 0.1


def train(client: TestClient) -> dict[str, object]:
    response = client.post("/api/v1/detection/models/train", json=TRAINING_REQUEST)
    assert response.status_code == 201, response.text
    return cast(dict[str, object], response.json())


def create_run(client: TestClient, scenario: str = "credential-compromise") -> dict[str, object]:
    response = client.post(
        "/api/v1/simulation/runs",
        json={
            "scenario_id": scenario,
            "seed": 101,
            "start_time": "2026-07-21T01:30:00Z",
            "playback_speed": 10,
        },
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


def score(
    client: TestClient, run_id: object, model_id: object, force: bool = False
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/detection/runs/{run_id}/score",
        json={"model_id": model_id, "force_rescore": force},
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, object], response.json())


def test_dataset_is_deterministic_normal_only_and_split_by_run() -> None:
    request = DetectionTrainingRequest.model_validate(TRAINING_REQUEST)
    first = detection_dataset_service.build_training(request)
    second = detection_dataset_service.build_training(request)
    assert first.fingerprint == second.fingerprint
    assert set(first.training.run_ids).isdisjoint(first.validation.run_ids)
    assert {event.scenario_id for event in first.training.events + first.validation.events} == {
        "normal-operations"
    }
    assert {event.simulation_run_id for event in first.training.events} == set(
        first.training.run_ids
    )


def test_feature_schema_excludes_leakage_and_handles_missing_values() -> None:
    request = DetectionTrainingRequest.model_validate(TRAINING_REQUEST)
    events = detection_dataset_service.build_training(request).training.events
    baseline = feature_pipeline_service.learn_baselines(events)
    missing = events[0].model_copy(
        update={"destination_id": None, "user_id": None, "device_id": None, "privilege_level": None}
    )
    row = feature_pipeline_service.extract([missing], baseline)[0]
    assert set(row) == set(INCLUDED_FEATURES)
    assert set(row).isdisjoint(EXCLUDED_LEAKAGE_FIELDS)
    assert row["privilege_level"] == "missing"
    assert "severity" not in row


def test_training_is_idempotent_and_artifact_reloads(client: TestClient) -> None:
    first = train(client)
    second = train(client)
    assert first == second
    detail = client.get(f"/api/v1/detection/models/{first['model_id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["synthetic"] is True
    assert body["training_event_count"] == 30
    assert body["validation_event_count"] == 30
    artifact = model_artifact_service.load(body["artifact_path"])
    assert artifact.feature_schema_version == "synthetic-behaviour-v2"
    assert Path(body["artifact_path"]).is_file()


def test_calibration_respects_validation_target_with_finite_sample_tolerance(
    client: TestClient,
) -> None:
    model = train(client)
    detail = client.get(f"/api/v1/detection/models/{model['model_id']}").json()
    artifact = model_artifact_service.load(detail["artifact_path"])
    request = DetectionTrainingRequest.model_validate(TRAINING_REQUEST)
    validation = detection_dataset_service.build_training(request).validation.events
    results = detection_scoring_service.score_events(artifact, validation)
    observed = sum(item[3].value == "anomalous" for item in results) / len(results)
    assert observed <= TARGET_FALSE_POSITIVE_RATE + 1 / len(results)


def test_scoring_is_bounded_ordered_idempotent_and_synthetic(client: TestClient) -> None:
    model = train(client)
    run = create_run(client)
    first = score(client, run["simulation_run_id"], model["model_id"])
    second = score(client, run["simulation_run_id"], model["model_id"])
    assert first["assessment_count"] == second["assessment_count"] == run["event_count"]
    response = client.get(
        f"/api/v1/detection/runs/{run['simulation_run_id']}/assessments",
        params={"model_id": model["model_id"], "page_size": 100},
    )
    assessments = response.json()["items"]
    assert len(assessments) == run["event_count"]
    assert all(0 <= item["anomaly_score"] <= 1 for item in assessments)
    assert all(item["synthetic"] is True for item in assessments)
    assert [item["sequence_number"] for item in assessments] == list(
        range(1, int(run["event_count"]) + 1)
    )
    ranked = sorted(assessments, key=lambda item: item["raw_score"], reverse=True)
    assert ranked[0]["anomaly_score"] <= ranked[-1]["anomaly_score"]


def test_forced_rescore_replaces_assessments_without_duplicates(client: TestClient) -> None:
    model = train(client)
    run = create_run(client)
    score(client, run["simulation_run_id"], model["model_id"])
    forced = score(client, run["simulation_run_id"], model["model_id"], True)
    assert forced["force_rescore"] is True
    page = client.get(
        f"/api/v1/detection/runs/{run['simulation_run_id']}/assessments",
        params={"page_size": 100},
    ).json()
    assert page["total"] == run["event_count"]
    assert len({item["assessment_id"] for item in page["items"]}) == run["event_count"]


def test_assessments_stay_with_run_and_explanations_are_limited(client: TestClient) -> None:
    model = train(client)
    suspicious = create_run(client)
    normal = create_run(client, "normal-operations")
    score(client, suspicious["simulation_run_id"], model["model_id"])
    score(client, normal["simulation_run_id"], model["model_id"])
    page = client.get(
        f"/api/v1/detection/runs/{suspicious['simulation_run_id']}/assessments",
        params={"page_size": 100},
    ).json()
    assert all(
        item["simulation_run_id"] == suspicious["simulation_run_id"] for item in page["items"]
    )
    assert all(item["contributing_signals"] for item in page["items"])
    serialised = str(page).lower()
    for verdict in ("confirmed attack", "compromised", "malicious actor", "breach confirmed"):
        assert verdict not in serialised


def test_assessment_pagination_and_filters(client: TestClient) -> None:
    model = train(client)
    run = create_run(client)
    score(client, run["simulation_run_id"], model["model_id"])
    base = f"/api/v1/detection/runs/{run['simulation_run_id']}/assessments"
    first = client.get(base, params={"page_size": 3, "page": 1}).json()
    second = client.get(base, params={"page_size": 3, "page": 2}).json()
    assert first["pages"] == 3
    assert len(first["items"]) == len(second["items"]) == 3
    authentication = client.get(base, params={"event_type": "authentication"}).json()
    assert authentication["total"] == 2
    source = client.get(base, params={"source_id": "application-server-01"}).json()
    assert source["total"] == 1
    user = client.get(base, params={"user_id": "synthetic-user-01"}).json()
    assert user["total"] == 7
    high_score = client.get(base, params={"minimum_anomaly_score": 0.8}).json()
    assert all(item["anomaly_score"] >= 0.8 for item in high_score["items"])
    anomalous = client.get(base, params={"classification": "anomalous"}).json()
    assert all(item["classification"] == "anomalous" for item in anomalous["items"])


def test_evaluation_metrics_and_rule_baseline_are_persisted(client: TestClient) -> None:
    model = train(client)
    response = client.post(f"/api/v1/detection/models/{model['model_id']}/evaluate")
    assert response.status_code == 200, response.text
    evaluation = response.json()
    assert evaluation["synthetic"] is True
    assert evaluation["normal_event_count"] == 18
    assert evaluation["suspicious_scenario_event_count"] == 21
    assert evaluation["true_positive"] + evaluation["false_negative"] == 21
    assert evaluation["true_negative"] + evaluation["false_positive"] == 18
    assert 0 <= evaluation["precision"] <= 1
    assert 0 <= evaluation["recall"] <= 1
    assert 0 <= evaluation["f1_score"] <= 1
    assert evaluation["roc_auc"] is not None
    assert evaluation["average_precision"] is not None
    assert evaluation["baseline_metrics"]["synthetic"] is True
    fetched = client.get(f"/api/v1/detection/evaluations/{evaluation['evaluation_id']}")
    assert fetched.status_code == 200
    assert fetched.json() == evaluation


def test_model_listing_and_structured_missing_errors(client: TestClient) -> None:
    model = train(client)
    listed = client.get("/api/v1/detection/models")
    assert listed.status_code == 200
    assert [item["model_id"] for item in listed.json()] == [model["model_id"]]
    missing_model = client.get("/api/v1/detection/models/missing")
    assert missing_model.status_code == 404
    assert missing_model.json()["error_code"] == "DETECTION_MODEL_NOT_FOUND"
    missing_run = client.post(
        "/api/v1/detection/runs/missing/score", json={"model_id": model["model_id"]}
    )
    assert missing_run.status_code == 404
    assert missing_run.json()["error_code"] == "SIMULATION_RUN_NOT_FOUND"


def test_invalid_overlapping_training_configuration_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/detection/models/train",
        json={
            **TRAINING_REQUEST,
            "validation_seed_range": TRAINING_REQUEST["training_seed_range"],
        },
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"


def test_seed_range_values_are_inclusive() -> None:
    assert list(SeedRange(start=3, end=5).values()) == [3, 4, 5]
