"""Authorization (RBAC) tests for the routes wired up in app.core.auth.

These tests exercise the real dependency-injection wiring end to end
through the FastAPI TestClient, rather than unit-testing app.core.auth in
isolation, so a mistake in how a route wires ``RequireViewer`` /
``RequireAnalyst`` / ``RequireAdmin`` would actually be caught here.

Representative routes used below:
- VIEWER read-only: GET /api/v1/topology (no DB fixture required, public).
- ANALYST-tier mutation: POST /api/v1/simulation/runs (self-contained -
  scenarios are static/in-memory, so no other fixture data is needed).
- ADMIN-tier mutation: PUT /api/v1/autonomy with mode=autonomous (also
  self-contained - the autonomy config is a lazily-created singleton row).

``get_current_principal`` resolves its ``Settings`` via
``request.app.state.settings`` (the instance the app was constructed with),
matching ``get_database_session``'s pattern. Tests that need a non-default
auth configuration (admin allow-list, dev bypass, anonymous disabled, etc.)
therefore build their own app instance with the desired ``Settings`` via a
local helper rather than overriding a dependency.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.database.base import Base
from app.main import create_app
from app.services.model_artifact_service import model_artifact_service

PRINCIPAL_ID_HEADER = "X-MS-CLIENT-PRINCIPAL-ID"
PRINCIPAL_HEADER = "X-MS-CLIENT-PRINCIPAL"


@pytest.fixture(autouse=True)
def isolate_model_cache() -> Generator[None, None, None]:
    model_artifact_service.clear_cache()
    yield
    model_artifact_service.clear_cache()


def _base_settings_kwargs(tmp_path: Path) -> dict[str, Any]:
    return {
        "_env_file": None,
        "DATABASE_URL": f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        "DEBUG": False,
        "MODEL_ARTIFACT_DIR": tmp_path / "artifacts",
    }


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(**_base_settings_kwargs(tmp_path))


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        application = cast(FastAPI, test_client.app)
        Base.metadata.create_all(application.state.database.engine)
        yield test_client


def _client_with_settings(overridden: Settings) -> Generator[TestClient, None, None]:
    application = create_app(overridden)
    with TestClient(application) as test_client:
        Base.metadata.create_all(application.state.database.engine)
        yield test_client


def _run_create_payload() -> dict[str, Any]:
    return {
        "scenario_id": "normal-operations",
        "seed": 1,
        "start_time": "2026-01-01T00:00:00+00:00",
        "playback_speed": 1.0,
    }


def _autonomy_autonomous_payload(updated_by: str) -> dict[str, Any]:
    return {"mode": "autonomous", "updated_by": updated_by, "confirm": True}


# ---------------------------------------------------------------------
# 1. VIEWER (anonymous) can read a representative read-only route
# ---------------------------------------------------------------------


def test_anonymous_viewer_can_read_topology(client: TestClient) -> None:
    response = client.get("/api/v1/topology")
    assert response.status_code == 200


# ---------------------------------------------------------------------
# 2. VIEWER (anonymous) is denied a representative ANALYST-tier route
# ---------------------------------------------------------------------


def test_anonymous_viewer_denied_analyst_route(client: TestClient) -> None:
    response = client.post("/api/v1/simulation/runs", json=_run_create_payload())
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------
# 3. ANALYST can call a representative ANALYST-tier route
# ---------------------------------------------------------------------


def test_analyst_can_create_simulation_run(client: TestClient) -> None:
    response = client.post(
        "/api/v1/simulation/runs",
        json=_run_create_payload(),
        headers={PRINCIPAL_ID_HEADER: "analyst-1"},
    )
    assert response.status_code == 201


# ---------------------------------------------------------------------
# 4. ANALYST is denied a representative ADMIN-tier route
# ---------------------------------------------------------------------


def test_analyst_denied_admin_route(client: TestClient) -> None:
    response = client.put(
        "/api/v1/autonomy",
        json=_autonomy_autonomous_payload("analyst-1"),
        headers={PRINCIPAL_ID_HEADER: "analyst-1"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------
# 5. ADMIN (principal id present in settings.admin_principal_ids) can call
#    the ADMIN-tier route
# ---------------------------------------------------------------------


def test_admin_can_call_admin_route(tmp_path: Path) -> None:
    admin_settings = Settings(**_base_settings_kwargs(tmp_path), ADMIN_PRINCIPAL_IDS=["admin-1"])
    for client in _client_with_settings(admin_settings):
        response = client.put(
            "/api/v1/autonomy",
            json=_autonomy_autonomous_payload("admin-1"),
            headers={PRINCIPAL_ID_HEADER: "admin-1"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "autonomous"


def test_non_admin_principal_id_is_analyst_not_admin(tmp_path: Path) -> None:
    admin_settings = Settings(**_base_settings_kwargs(tmp_path), ADMIN_PRINCIPAL_IDS=["admin-1"])
    for client in _client_with_settings(admin_settings):
        response = client.put(
            "/api/v1/autonomy",
            json=_autonomy_autonomous_payload("analyst-2"),
            headers={PRINCIPAL_ID_HEADER: "analyst-2"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------
# 6. Missing/invalid principal header combinations behave safely
# ---------------------------------------------------------------------


def test_principal_header_without_id_falls_back_to_anonymous_viewer(client: TestClient) -> None:
    # X-MS-CLIENT-PRINCIPAL present but no X-MS-CLIENT-PRINCIPAL-ID: must not
    # crash, and must resolve to anonymous VIEWER (not authenticated).
    response = client.get(
        "/api/v1/topology",
        headers={PRINCIPAL_HEADER: "eyJub3QiOiJhIHJlYWwgcHJpbmNpcGFsIn0="},
    )
    assert response.status_code == 200


def test_malformed_principal_header_does_not_crash(client: TestClient) -> None:
    # X-MS-CLIENT-PRINCIPAL-ID present alongside an X-MS-CLIENT-PRINCIPAL
    # value that is not valid base64/JSON: decoding failure must be
    # swallowed (logged, ignored) rather than raising/500ing, and the
    # caller should still resolve via the principal id (ANALYST, since it
    # is not in the empty default admin allow-list).
    response = client.post(
        "/api/v1/simulation/runs",
        json=_run_create_payload(),
        headers={
            PRINCIPAL_ID_HEADER: "analyst-3",
            PRINCIPAL_HEADER: "not-valid-base64!!!",
        },
    )
    assert response.status_code == 201


def test_no_headers_and_anonymous_disabled_requires_authentication(tmp_path: Path) -> None:
    no_anonymous_settings = Settings(
        **_base_settings_kwargs(tmp_path), ALLOW_ANONYMOUS_VIEWER=False
    )
    for client in _client_with_settings(no_anonymous_settings):
        response = client.get("/api/v1/topology")
        assert response.status_code == 401


# ---------------------------------------------------------------------
# 7. AUTH_DEV_BYPASS_ROLE
# ---------------------------------------------------------------------


def test_dev_bypass_role_admin_grants_admin_without_headers(tmp_path: Path) -> None:
    bypass_settings = Settings(
        **_base_settings_kwargs(tmp_path),
        ENVIRONMENT="development",
        AUTH_DEV_BYPASS_ROLE="ADMIN",
    )
    for client in _client_with_settings(bypass_settings):
        response = client.put("/api/v1/autonomy", json=_autonomy_autonomous_payload("dev-bypass"))
        assert response.status_code == 200


def test_dev_bypass_role_rejected_in_production_settings() -> None:
    with pytest.raises(ValidationError):  # wraps the ValueError from model_post_init
        Settings(
            _env_file=None,
            ENVIRONMENT="production",
            AUTH_DEV_BYPASS_ROLE="ADMIN",
        )
