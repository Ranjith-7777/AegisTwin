"""Add Phase 5 Mission Continuity (MCI) and Aegis Resilience Score (ARS)."""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0014"
down_revision: Union[str, None] = "20260915_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def synthetic() -> sa.Column[bool]:
    return sa.Column("synthetic", sa.Boolean(), nullable=False)


def upgrade() -> None:
    op.add_column("experiment_metrics", sa.Column("mci", sa.Float()))
    op.add_column("experiment_metrics", sa.Column("mci_version", sa.String(40)))
    op.add_column("experiment_metrics", sa.Column("ars_total", sa.Float()))
    op.add_column("experiment_metrics", sa.Column("ars_pillars_json", sa.JSON()))
    op.add_column("experiment_metrics", sa.Column("ars_version", sa.String(40)))

    op.create_table(
        "mission_health_points",
        sa.Column("id", sa.String(60), primary_key=True),
        sa.Column("experiment_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("logical_time_sim", sa.Float(), nullable=False),
        sa.Column("mission_health", sa.Float(), nullable=False),
        sa.Column("stage", sa.String(30), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        synthetic(),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_mission_health_points_experiment_id", "mission_health_points", ["experiment_id"]
    )
    op.create_index(
        "ix_mission_health_points_experiment_seq",
        "mission_health_points",
        ["experiment_id", "sequence"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mission_health_points_experiment_seq", table_name="mission_health_points"
    )
    op.drop_index("ix_mission_health_points_experiment_id", table_name="mission_health_points")
    op.drop_table("mission_health_points")

    op.drop_column("experiment_metrics", "ars_version")
    op.drop_column("experiment_metrics", "ars_pillars_json")
    op.drop_column("experiment_metrics", "ars_total")
    op.drop_column("experiment_metrics", "mci_version")
    op.drop_column("experiment_metrics", "mci")
