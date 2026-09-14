"""Add Phase 5 evaluation-only synthetic-action provenance (correcting
Rule-Based/ML-Assisted baseline isolation from Phase 4 orchestration)."""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260916_0016"
down_revision: Union[str, None] = "20260915_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_synthetic_actions",
        sa.Column("action_id", sa.String(36), primary_key=True),
        sa.Column("experiment_id", sa.String(36), nullable=False),
        sa.Column("defence_mode", sa.String(30), nullable=False),
        sa.Column("playbook_id", sa.String(80)),
        sa.Column("target_type", sa.String(30)),
        sa.Column("target_id", sa.String(220)),
        sa.Column("rule_id", sa.String(40)),
        sa.Column("recommendation_rank", sa.Integer()),
        sa.Column("defense_score", sa.Float()),
        sa.Column("through_sequence_number", sa.Integer()),
        sa.Column("changed_node_ids_json", sa.JSON(), nullable=False),
        sa.Column("changed_edge_ids_json", sa.JSON(), nullable=False),
        sa.Column("reversibility", sa.String(30)),
        sa.Column("operational_impact", sa.String(30)),
        sa.Column("blast_radius", sa.String(30)),
        sa.Column("executed", sa.Boolean(), nullable=False),
        sa.Column("note", sa.String(500)),
        sa.Column("synthetic", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_evaluation_synthetic_actions_experiment_id",
        "evaluation_synthetic_actions",
        ["experiment_id"],
    )
    op.add_column(
        "experiments",
        sa.Column("evaluation_action_id", sa.String(36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("experiments", "evaluation_action_id")
    op.drop_index(
        "ix_evaluation_synthetic_actions_experiment_id",
        table_name="evaluation_synthetic_actions",
    )
    op.drop_table("evaluation_synthetic_actions")
