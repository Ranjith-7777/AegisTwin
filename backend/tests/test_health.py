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
