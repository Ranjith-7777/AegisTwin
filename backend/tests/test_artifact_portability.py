"""Regression tests: detection-model artifacts are portable and self-healing.

Background: records used to persist an absolute, machine-specific
`artifact_path` (e.g. `D:\\AegisArena\\artifacts\\models\\<id>.joblib`). After the
repository moved, every scoring call returned 500 MODEL_ARTIFACT_NOT_FOUND
and re-training returned the same broken record forever.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.artifacts import artifact_file_name, resolve_artifact_path
from app.core.config import Settings
from app.database.models import DetectionModelRecord
from tests.test_detection import TRAINING_REQUEST, create_run, score, train


def _db_record(client: TestClient, model_id: str) -> DetectionModelRecord:
    app = cast(FastAPI, client.app)
    with app.state.database.session_factory() as session:
        record = session.get(DetectionModelRecord, model_id)
        assert record is not None
        session.expunge(record)
        return cast(DetectionModelRecord, record)


def _set_stored_path(client: TestClient, model_id: str, value: str) -> None:
    app = cast(FastAPI, client.app)
    with app.state.database.session_factory() as session:
        record = session.get(DetectionModelRecord, model_id)
        assert record is not None
        record.artifact_path = value
        session.commit()


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("abc.joblib", "abc.joblib"),
        ("D:\\AegisArena\\artifacts\\models\\abc.joblib", "abc.joblib"),
        ("/var/lib/aegisarena/models/abc.joblib", "abc.joblib"),
        ("artifacts/models/abc.joblib", "abc.joblib"),
    ],
)
def test_artifact_file_name_strips_any_directory(stored: str, expected: str) -> None:
    assert artifact_file_name(stored) == expected


def test_artifact_file_name_rejects_directory_only_values() -> None:
    with pytest.raises(ValueError):
        artifact_file_name("models/")


def test_relative_artifact_dir_is_anchored_to_backend_not_cwd() -> None:
    settings = Settings(_env_file=None, MODEL_ARTIFACT_DIR="artifacts/models")
    assert settings.model_artifact_dir.is_absolute()
    assert settings.model_artifact_dir.parts[-3:] == ("backend", "artifacts", "models")


def test_new_records_store_only_a_file_name(client: TestClient, settings: Settings) -> None:
    model_id = str(train(client)["model_id"])
    record = _db_record(client, model_id)
    assert record.artifact_path == f"{model_id}.joblib"
    detail = client.get(f"/api/v1/detection/models/{model_id}").json()
    assert Path(detail["artifact_path"]) == settings.model_artifact_dir.resolve() / (
        f"{model_id}.joblib"
    )
    assert detail["artifact_available"] is True


def test_legacy_absolute_path_from_another_checkout_still_scores(client: TestClient) -> None:
    model_id = str(train(client)["model_id"])
    _set_stored_path(client, model_id, f"D:\\AegisArena\\artifacts\\models\\{model_id}.joblib")
    run = create_run(client)
    result = score(client, run["simulation_run_id"], model_id)
    assert result["assessment_count"] == run["event_count"]
    # The legacy value is normalised to the portable form on first use.
    assert _db_record(client, model_id).artifact_path == f"{model_id}.joblib"


def test_missing_artifact_is_rebuilt_deterministically_on_scoring(client: TestClient) -> None:
    model_id = str(train(client)["model_id"])
    run = create_run(client)
    first = client.get(
        f"/api/v1/detection/runs/{run['simulation_run_id']}/assessments",
        params={"model_id": model_id},
    )
    assert first.status_code == 200
    score(client, run["simulation_run_id"], model_id)
    before = client.get(
        f"/api/v1/detection/runs/{run['simulation_run_id']}/assessments",
        params={"model_id": model_id, "page_size": 100},
    ).json()

    resolve_artifact_path(f"{model_id}.joblib").unlink()
    listed = {item["model_id"]: item for item in client.get("/api/v1/detection/models").json()}
    assert listed[model_id]["artifact_available"] is False

    score(client, run["simulation_run_id"], model_id, force=True)
    assert resolve_artifact_path(f"{model_id}.joblib").is_file()
    after = client.get(
        f"/api/v1/detection/runs/{run['simulation_run_id']}/assessments",
        params={"model_id": model_id, "page_size": 100},
    ).json()
    scores_before = [item["anomaly_score"] for item in before["items"]]
    scores_after = [item["anomaly_score"] for item in after["items"]]
    assert scores_before == scores_after


def test_retraining_a_model_whose_artifact_vanished_recreates_it(client: TestClient) -> None:
    model_id = str(train(client)["model_id"])
    path = resolve_artifact_path(f"{model_id}.joblib")
    path.unlink()
    again = client.post("/api/v1/detection/models/train", json=TRAINING_REQUEST)
    assert again.status_code == 201
    assert again.json()["model_id"] == model_id
    assert path.is_file()


def test_unrecoverable_artifact_reports_clear_error(client: TestClient) -> None:
    model_id = str(train(client)["model_id"])
    resolve_artifact_path(f"{model_id}.joblib").unlink()
    # A record whose stored file name no longer matches its training
    # configuration cannot be proven identical, so it is never silently
    # replaced with a different model.
    _set_stored_path(client, model_id, "someone-elses-model.joblib")
    response = client.get(f"/api/v1/detection/models/{model_id}")
    assert response.status_code == 500
    assert response.json()["error_code"] == "MODEL_ARTIFACT_NOT_FOUND"
