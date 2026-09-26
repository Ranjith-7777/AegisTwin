"""Add Phase 4 autonomy config and response plan assessment persistence."""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260901_0011"
down_revision: Union[str, None] = "20260818_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def synthetic() -> sa.Column[bool]:
    return sa.Column("synthetic", sa.Boolean(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "autonomy_config",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("mode", sa.String(30), nullable=False, server_default="recommend"),
        sa.Column("updated_by", sa.String(120), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        synthetic(),
    )
    op.create_table(
        "response_plan_assessments",
        sa.Column("assessment_id", sa.String(36), primary_key=True),
        sa.Column("simulation_run_id", sa.String(36), nullable=False),
        sa.Column("model_id", sa.String(36), nullable=False),
        sa.Column("incident_candidate_id", sa.String(36), nullable=False),
        sa.Column("through_sequence_number", sa.Integer(), nullable=False),
        sa.Column("autonomy_mode", sa.String(30), nullable=False),
        sa.Column("candidates_json", sa.JSON(), nullable=False),
        sa.Column("selected_recommendation_id", sa.String(36)),
        sa.Column("decision_confidence_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        synthetic(),
        sa.UniqueConstraint(
            "simulation_run_id",
            "model_id",
            "incident_candidate_id",
            "through_sequence_number",
            name="uq_response_plan_assessment_identity",
        ),
    )
    op.create_index(
        "ix_response_plan_assessments_simulation_run_id",
        "response_plan_assessments",
        ["simulation_run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_response_plan_assessments_simulation_run_id",
        table_name="response_plan_assessments",
    )
    op.drop_table("response_plan_assessments")
    op.drop_table("autonomy_config")
