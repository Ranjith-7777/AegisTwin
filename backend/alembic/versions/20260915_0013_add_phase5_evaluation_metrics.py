"""Add Phase 5 evaluation metrics persistence."""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0013"
down_revision: Union[str, None] = "20260915_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def synthetic() -> sa.Column[bool]:
    return sa.Column("synthetic", sa.Boolean(), nullable=False)


def upgrade() -> None:
    op.add_column(
        "experiments",
        sa.Column(
            "changed_node_ids_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")
        ),
    )
    op.add_column(
        "experiments",
        sa.Column(
            "changed_edge_ids_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")
        ),
    )
    op.add_column(
        "experiments",
        sa.Column("autonomous_action_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "experiments",
        sa.Column("manual_action_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("experiments", sa.Column("workflow_latency_ms", sa.Float()))

    op.create_table(
        "experiment_metrics",
        sa.Column("experiment_id", sa.String(36), primary_key=True),
        sa.Column("metrics_version", sa.String(40), nullable=False),
        sa.Column("logical_timeline_json", sa.JSON(), nullable=False),
        sa.Column("computation_latency_json", sa.JSON(), nullable=False),
        sa.Column("raw_metrics_json", sa.JSON(), nullable=False),
        sa.Column("normalized_metrics_json", sa.JSON(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        synthetic(),
    )


def downgrade() -> None:
    op.drop_table("experiment_metrics")
    op.drop_column("experiments", "workflow_latency_ms")
    op.drop_column("experiments", "manual_action_count")
    op.drop_column("experiments", "autonomous_action_count")
    op.drop_column("experiments", "changed_edge_ids_json")
    op.drop_column("experiments", "changed_node_ids_json")
