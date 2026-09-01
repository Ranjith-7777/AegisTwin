from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_application_factory_returns_fastapi(app: FastAPI) -> None:
    assert isinstance(app, FastAPI)


def test_system_status_is_foundation_data(client: TestClient) -> None:
    response = client.get("/api/system/status")
    assert response.status_code == 200
    assert response.json() == {
        "system_name": "AegisArena",
        "system_tagline": "Cloud Cyber Defense Range",
        "mode": "simulation",
        "operational": True,
        "active_incidents": 0,
        "agents_online": 8,
        "red_agent_runs": 0,
        "blue_agent_orchestrations": 0,
        "version": "0.9.0",
        "git_commit": None,
        "build_mode": "development",
        "demo_mode": False,
        "database_revision": "20260817_0009",
        "synthetic_only": True,
        "benchmark_report_timestamp": None,
    }
