from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.system_service import get_system_status


def test_demo_environment_is_explicit_and_safe(tmp_path: Path) -> None:
    database = tmp_path / "demo.db"
    artifacts = tmp_path / "artifacts"
    settings = Settings(
        ENVIRONMENT="demo",
        DEMO_MODE=True,
        DATABASE_URL=f"sqlite:///{database.as_posix()}",
        MODEL_ARTIFACT_DIR=artifacts,
        SIMULATION_ONLY=True,
        AEGISTWIN_BUILD_MODE="production",
        AEGISTWIN_GIT_COMMIT="abcdef1",
    )
    status = get_system_status(settings=settings)
    assert status.demo_mode is True
    assert status.synthetic_only is True
    assert status.git_commit == "abcdef1"
    assert status.database_revision == "20260817_0009"
    assert "ASUS" not in status.model_dump_json()


def test_invalid_build_revision_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(AEGISTWIN_GIT_COMMIT="local-machine-path")
