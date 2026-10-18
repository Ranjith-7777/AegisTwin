"""Regression tests for browser CORS behaviour used by the frontend."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "DATABASE_URL": f"sqlite:///{(tmp_path / 'cors.db').as_posix()}",
        "MODEL_ARTIFACT_DIR": tmp_path / "artifacts",
        "AUTH_DEV_BYPASS_ROLE": "ADMIN",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


@pytest.fixture
def dev_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    with TestClient(create_app(_settings(tmp_path))) as client:
        yield client


def _preflight(client: TestClient, origin: str, method: str) -> int:
    response = client.options(
        "/api/v1/autonomy",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "content-type",
        },
    )
    allowed_origin = response.headers.get("access-control-allow-origin")
    return response.status_code if allowed_origin == origin else 400


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
@pytest.mark.parametrize("method", ["GET", "POST", "PUT"])
def test_default_dev_origins_allow_every_frontend_method(
    dev_client: TestClient, origin: str, method: str
) -> None:
    assert _preflight(dev_client, origin, method) == 200


def test_put_autonomy_preflight_was_previously_rejected_is_now_allowed(
    dev_client: TestClient,
) -> None:
    response = dev_client.options(
        "/api/v1/autonomy",
        headers={"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "PUT"},
    )
    assert response.status_code == 200
    assert "PUT" in response.headers["access-control-allow-methods"]


def test_unlisted_origin_and_method_are_rejected(dev_client: TestClient) -> None:
    assert _preflight(dev_client, "http://evil.example", "GET") != 200
    response = dev_client.options(
        "/api/v1/autonomy",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "DELETE"},
    )
    assert response.status_code == 400


def test_localhost_only_env_value_also_admits_127_in_development(tmp_path: Path) -> None:
    settings = _settings(tmp_path, CORS_ORIGINS="http://localhost:5173")
    assert settings.cors_origins == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_loopback_aliases_are_never_added_in_production(tmp_path: Path) -> None:
    settings = _settings(
        tmp_path,
        ENVIRONMENT="production",
        AUTH_DEV_BYPASS_ROLE=None,
        CORS_ORIGINS="http://localhost:8080",
    )
    assert settings.cors_origins == ["http://localhost:8080"]


def test_wildcard_origin_is_still_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        _settings(tmp_path, CORS_ORIGINS="*")
