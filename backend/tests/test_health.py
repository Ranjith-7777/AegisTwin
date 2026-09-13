import shutil
from pathlib import Path
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.session import Database


def test_health_reports_real_database_connectivity(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "AegisArena API",
        "environment": "development",
        "simulation_only": True,
        "database": "connected",
    }


def test_application_startup_creates_database_state(client: TestClient) -> None:
    application = cast(FastAPI, client.app)
    assert application.state.database.is_connected() is True


def test_database_connectivity_check_uses_sqlite(tmp_path: Path) -> None:
    database = Database(f"sqlite:///{(tmp_path / 'connectivity.db').as_posix()}")
    try:
        assert database.is_connected() is True
    finally:
        database.dispose()


def test_liveness_does_not_depend_on_database(client: TestClient) -> None:
    response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_reports_all_checks_ok(client: TestClient) -> None:
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    names = {check["name"] for check in body["checks"]}
    assert names == {"database", "model_subsystem", "configuration", "event_bus"}
    assert all(check["status"] == "ok" for check in body["checks"])


def test_readiness_fails_when_model_artifact_dir_is_removed(client: TestClient) -> None:
    application = cast(FastAPI, client.app)
    settings = application.state.settings
    shutil.rmtree(settings.model_artifact_dir)
    response = client.get("/api/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    failed = {check["name"] for check in body["checks"] if check["status"] == "failed"}
    assert "model_subsystem" in failed
