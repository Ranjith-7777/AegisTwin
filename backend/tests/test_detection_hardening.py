from __future__ import annotations

from typing import cast

from fastapi.testclient import TestClient

from app.schemas.detection import DetectionTrainingRequest
from app.schemas.telemetry import TelemetryEvent
from app.services.detection_dataset_service import detection_dataset_service
from app.services.evaluation_truth_service import evaluation_truth_service
from app.services.feature_pipeline_service import (
    EXCLUDED_LEAKAGE_FIELDS,
    FEATURE_SCHEMA_VERSION,
    feature_pipeline_service,
)
from app.services.model_artifact_service import model_artifact_service
from app.services.score_calibration_service import score_calibration_service

HARDENING_REQUEST = {
    "training_seed_range": {"start": 1, "end": 5},
    "validation_seed_range": {"start": 6, "end": 10},
    "evaluation_seed_range": {"start": 11, "end": 13},
    "random_state": 17,
    "target_false_positive_rate": 0.1,
    "n_estimators": 100,
}


def train(client: TestClient) -> dict[str, object]:
    response = client.post("/api/v1/detection/models/train", json=HARDENING_REQUEST)
    assert response.status_code == 201, response.text
    return cast(dict[str, object], response.json())


def test_benchmark_labels_are_separate_from_telemetry_and_features() -> None:
    manifest = evaluation_truth_service.manifest()
    assert len(manifest) == 7
    assert sum(label.anomalous for label in manifest) == 6
    assert all(label.synthetic for label in manifest)
    telemetry_fields = set(TelemetryEvent.model_fields)
    assert "evaluation_label" not in telemetry_fields
    assert "benchmark_anomalous" not in telemetry_fields
    assert "evaluation_label" in EXCLUDED_LEAKAGE_FIELDS


def test_v2_context_is_deterministic_and_uses_no_future_events() -> None:
    request = DetectionTrainingRequest.model_validate(HARDENING_REQUEST)
    training = detection_dataset_service.build_training(request).training
    baselines = feature_pipeline_service.learn_baselines(training.events)
    suspicious = detection_dataset_service.build_scenario(
        "credential-compromise", request.evaluation_seed_range, "causal-check"
    )
    run_events = [
        event for event in suspicious.events if event.simulation_run_id == suspicious.run_ids[0]
    ]
    full = feature_pipeline_service.extract(run_events, baselines)
    repeated = feature_pipeline_service.extract(run_events, baselines)
    assert full == repeated
    for position in range(1, len(run_events) + 1):
        prefix = feature_pipeline_service.extract(run_events[:position], baselines)
        assert prefix[-1] == full[position - 1]


def test_normal_baselines_exclude_validation_and_evaluation_runs() -> None:
    request = DetectionTrainingRequest.model_validate(HARDENING_REQUEST)
    datasets = detection_dataset_service.build_training(request)
    baselines = feature_pipeline_service.learn_baselines(datasets.training.events)
    assert baselines.event_count == len(datasets.training.events) == 30
    assert set(datasets.training.run_ids).isdisjoint(datasets.validation.run_ids)
    changed_evaluation = request.model_copy(
        update={"evaluation_seed_range": {"start": 40, "end": 41}}
    )
    changed_evaluation = DetectionTrainingRequest.model_validate(changed_evaluation)
    assert (
        detection_dataset_service.build_training(changed_evaluation).fingerprint
        == datasets.fingerprint
    )


def test_unknown_categories_are_explicit_and_do_not_fit_encoders() -> None:
    request = DetectionTrainingRequest.model_validate(HARDENING_REQUEST)
    training = detection_dataset_service.build_training(request).training
    baselines = feature_pipeline_service.learn_baselines(training.events)
    unknown = training.events[0].model_copy(
        update={
            "source_id": "synthetic-unknown-source",
            "destination_id": "synthetic-unknown-destination",
            "device_id": "synthetic-unknown-device",
        }
    )
    row = feature_pipeline_service.extract([unknown], baselines)[0]
    assert row["source_asset_type"] == "unknown"
    assert row["destination_asset_type"] == "unknown"
    assert row["device_frequency"] == 0


def test_score_ties_and_false_positive_count_calibration_are_deterministic() -> None:
    training = [0.1, 0.2, 0.2, 0.3]
    validation = [0.2, 0.2, 0.8, 0.8]
    first = score_calibration_service.compare(training, validation, 0.25, "validation-fp-count-v2")
    second = score_calibration_service.compare(training, validation, 0.25, "validation-fp-count-v2")
    assert first == second
    assert first.selected.validation_false_positive_count <= 1
    assert set(first.candidates) == {
        "empirical-quantile-v2",
        "interpolated-ecdf-v2",
        "validation-fp-count-v2",
    }


def test_v2_artifact_evaluation_modes_run_metrics_and_hybrid_audit(
    client: TestClient,
) -> None:
    model = train(client)
    detail = client.get(f"/api/v1/detection/models/{model['model_id']}").json()
    artifact = model_artifact_service.load(detail["artifact_path"])
    assert artifact.feature_schema_version == FEATURE_SCHEMA_VERSION
    assert artifact.calibration_method == "interpolated-ecdf-v2"
    assert sum(artifact.hybrid_weights.values()) == 1.0
    evaluation = client.post(f"/api/v1/detection/models/{model['model_id']}/evaluate").json()
    assert evaluation["evaluation_label_mode"] == "evaluation-step-manifest-v1"
    assert evaluation["event_level_metrics"]["positive_event_count"] == 18
    assert evaluation["scenario_wide_metrics"]["positive_event_count"] == 21
    assert evaluation["event_level_metrics"] != evaluation["scenario_wide_metrics"]
    assert evaluation["run_level_metrics"]["suspicious_runs_with_any_anomaly_rate"] >= 0
    assert evaluation["score_distribution_summary"]["held_out_normal"]["count"] == 18
    assert set(evaluation["calibration_comparison"]) == {
        "empirical-quantile-v2",
        "interpolated-ecdf-v2",
        "validation-fp-count-v2",
    }
    assert evaluation["pure_isolation_metrics"]["synthetic"] is True
    assert evaluation["hybrid_metrics"]["synthetic"] is True

    run_response = client.post(
        "/api/v1/simulation/runs",
        json={
            "scenario_id": "credential-compromise",
            "seed": 101,
            "start_time": "2026-07-21T01:30:00Z",
            "playback_speed": 10,
        },
    )
    run_id = run_response.json()["simulation_run_id"]
    scored = client.post(
        f"/api/v1/detection/runs/{run_id}/score",
        json={"model_id": model["model_id"]},
    )
    assert scored.status_code == 200
    assessments = client.get(
        f"/api/v1/detection/runs/{run_id}/assessments",
        params={"page_size": 100},
    ).json()["items"]
    assert all(item["component_scores"] for item in assessments)
    assert all(item["synthetic"] is True for item in assessments)
    assert all("confirmed attack" not in str(item).lower() for item in assessments)
