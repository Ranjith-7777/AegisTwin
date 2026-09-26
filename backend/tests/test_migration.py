"""Validates the Alembic migration chain, in particular the Phase 3
addition (20260818_0010) that adds Purple Team experiment persistence on
top of the full Phase 0-2 schema."""

from collections.abc import Generator
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from app.core.config import get_settings

REPO_ROOT = Path(__file__).resolve().parent.parent


def _alembic_config() -> Config:
    """`alembic/env.py` always reads the URL from `get_settings().database_url`
    rather than any `-x` override or config attribute, so the actual target
    database is selected via the `DATABASE_URL` environment variable plus a
    cleared settings cache (see `_clear_settings_cache` below), not via this
    config object."""
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return config


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Generator[None, None, None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_migration_chain_creates_a_fresh_database_at_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "fresh.db"
    database_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    command.upgrade(_alembic_config(), "head")

    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    assert "purple_team_experiments" in tables
    assert "purple_team_step_results" in tables
    assert "system_state" in tables
    assert "telemetry_events" in tables
    engine.dispose()


def test_migration_upgrades_cleanly_from_the_phase_2_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "phase2_upgrade.db"
    database_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    # The Phase 2 baseline is the last migration before this phase's
    # addition - upgrading only that far reproduces the exact schema a
    # pre-Phase-3 deployment would have.
    command.upgrade(_alembic_config(), "20260817_0009")
    engine = create_engine(database_url)
    tables_before = set(inspect(engine).get_table_names())
    assert "purple_team_experiments" not in tables_before
    engine.dispose()

    command.upgrade(_alembic_config(), "head")
    engine = create_engine(database_url)
    tables_after = set(inspect(engine).get_table_names())
    assert "purple_team_experiments" in tables_after
    assert "purple_team_step_results" in tables_after
    columns = {col["name"] for col in inspect(engine).get_columns("purple_team_step_results")}
    assert {"outcome", "detected", "expected_technique_id", "orchestration_state"} <= columns
    engine.dispose()


def test_migration_downgrade_removes_purple_team_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "downgrade.db"
    database_url = f"sqlite:///{db_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    config = _alembic_config()
    command.upgrade(config, "head")
    command.downgrade(config, "20260817_0009")

    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    assert "purple_team_experiments" not in tables
    assert "purple_team_step_results" not in tables
    assert "system_state" in tables
    engine.dispose()
