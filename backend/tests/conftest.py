from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.database.base import Base
from app.main import create_app
from app.services.model_artifact_service import model_artifact_service


@pytest.fixture(autouse=True)
def isolate_model_cache() -> Generator[None, None, None]:
    model_artifact_service.clear_cache()
    yield
    model_artifact_service.clear_cache()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        DATABASE_URL=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        DEBUG=False,
        MODEL_ARTIFACT_DIR=tmp_path / "artifacts",
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        application = cast(FastAPI, test_client.app)
        Base.metadata.create_all(application.state.database.engine)
        yield test_client
