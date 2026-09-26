"""Add Phase 5 evaluation experiment persistence."""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0012"
down_revision: Union[str, None] = "20260901_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def synthetic() -> sa.Column[bool]:
    return sa.Column("synthetic", sa.Boolean(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("experiment_id", sa.String(36), primary_key=True),
        sa.Column("scenario_id", sa.String(80), nullable=False),
        sa.Column("scenario_name", sa.String(120), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("defence_mode", sa.String(30), nullable=False),
        sa.Column("detection_model_id", sa.String(36)),
        sa.Column("topology_version", sa.String(60), nullable=False),
        sa.Column("red_scenario_version", sa.String(60), nullable=False),
        sa.Column("autonomy_mode", sa.String(30)),
        sa.Column("configuration_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("run_id", sa.String(36)),
        sa.Column("incident_candidate_id", sa.String(36)),
        sa.Column("orchestration_id", sa.String(36)),
        sa.Column("status", sa.String(30), nullable=False, server_default="created"),
        sa.Column("failure_stage", sa.String(30)),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("failure_message", sa.String(1000)),
        sa.Column("verification_status", sa.String(50)),
        sa.Column("batch_id", sa.String(36)),
        sa.Column("rerun_of_experiment_id", sa.String(36)),
        synthetic(),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_experiments_identity",
        "experiments",
        ["scenario_id", "seed", "defence_mode"],
    )
    op.create_index("ix_experiments_batch_id", "experiments", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_experiments_batch_id", table_name="experiments")
    op.drop_index("ix_experiments_identity", table_name="experiments")
    op.drop_table("experiments")
