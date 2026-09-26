"""Add deterministic simulation and telemetry persistence.

Revision ID: 20260721_0002
Revises: 20260721_0001
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_0002"
down_revision: str | None = "20260721_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "simulation_scenarios",
        sa.Column("scenario_id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("synthetic", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("scenario_id"),
    )
    op.create_table(
        "simulation_runs",
        sa.Column("simulation_run_id", sa.String(length=36), nullable=False),
        sa.Column("scenario_id", sa.String(length=80), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("playback_speed", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scenario_id"], ["simulation_scenarios.scenario_id"]),
        sa.PrimaryKeyConstraint("simulation_run_id"),
    )
    op.create_index("ix_simulation_runs_scenario_id", "simulation_runs", ["scenario_id"])
    op.create_table(
        "telemetry_events",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("scenario_id", sa.String(length=80), nullable=False),
        sa.Column("simulation_run_id", sa.String(length=36), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("severity", sa.String(length=30), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.String(length=100), nullable=False),
        sa.Column("destination_id", sa.String(length=100), nullable=True),
        sa.Column("user_id", sa.String(length=100), nullable=True),
        sa.Column("device_id", sa.String(length=100), nullable=True),
        sa.Column("source_ip", sa.String(length=45), nullable=True),
        sa.Column("destination_ip", sa.String(length=45), nullable=True),
        sa.Column("privilege_level", sa.String(length=30), nullable=True),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("bytes_transferred", sa.Integer(), nullable=False),
        sa.Column("process_name", sa.String(length=120), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["simulation_run_id"], ["simulation_runs.simulation_run_id"]
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("ix_telemetry_events_event_type", "telemetry_events", ["event_type"])
    op.create_index("ix_telemetry_events_scenario_id", "telemetry_events", ["scenario_id"])
    op.create_index(
        "ix_telemetry_events_simulation_run_id", "telemetry_events", ["simulation_run_id"]
    )
    op.create_index("ix_telemetry_events_source_id", "telemetry_events", ["source_id"])
    op.create_index("ix_telemetry_events_timestamp", "telemetry_events", ["timestamp"])
    op.create_index("ix_telemetry_events_user_id", "telemetry_events", ["user_id"])
    op.create_index("ix_telemetry_events_severity", "telemetry_events", ["severity"])


def downgrade() -> None:
    op.drop_table("telemetry_events")
    op.drop_table("simulation_runs")
    op.drop_table("simulation_scenarios")
