"""Add Phase 5 evaluation batch runner persistence."""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0015"
down_revision: Union[str, None] = "20260915_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_batches",
        sa.Column("batch_id", sa.String(36), primary_key=True),
        sa.Column("scenario_ids_json", sa.JSON(), nullable=False),
        sa.Column("seeds_json", sa.JSON(), nullable=False),
        sa.Column("defence_modes_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("total_experiments", sa.Integer(), nullable=False),
        sa.Column("completed_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("experiment_ids_json", sa.JSON(), nullable=False),
        sa.Column("max_experiments", sa.Integer()),
        sa.Column("truncated", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("runtime_seconds", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("synthetic", sa.Boolean(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("evaluation_batches")
