import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.exceptions import ConfigurationError
from app.main import create_app


def test_simulation_only_defaults_true() -> None:
    assert Settings(_env_file=None).simulation_only is True


def test_startup_refuses_non_simulation_mode() -> None:
    settings = Settings(_env_file=None, SIMULATION_ONLY=False)
    application = create_app(settings)
    with (
        pytest.raises(ConfigurationError, match="Real-world mode is prohibited"),
        TestClient(application),
    ):
        pass
