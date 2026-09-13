"""Add Phase 3 Purple Team experiment and step-result persistence."""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260818_0010"
down_revision: Union[str, None] = "20260817_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def synthetic() -> sa.Column[bool]:
    return sa.Column("synthetic", sa.Boolean(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "purple_team_experiments",
        sa.Column("experiment_id", sa.String(36), primary_key=True),
        sa.Column("scenario_id", sa.String(80), nullable=False),
        sa.Column("mode", sa.String(30), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=False),
        sa.Column("simulation_run_id", sa.String(36)),
        sa.Column("model_id", sa.String(36)),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("error", sa.String(500)),
        sa.Column("summary_json", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        synthetic(),
        sa.UniqueConstraint("scenario_id", "mode", "seed", name="uq_purple_experiment_identity"),
    )
    op.create_index(
        "ix_purple_team_experiments_scenario_id", "purple_team_experiments", ["scenario_id"]
    )
    op.create_table(
        "purple_team_step_results",
        sa.Column("step_result_id", sa.String(36), primary_key=True),
        sa.Column(
            "experiment_id",
            sa.String(36),
            sa.ForeignKey("purple_team_experiments.experiment_id"),
            nullable=False,
        ),
        sa.Column("step_sequence", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("event_id", sa.String(36)),
        sa.Column("target_asset_id", sa.String(100)),
        sa.Column("expected_technique_id", sa.String(20)),
        sa.Column("expected_technique_name", sa.String(120)),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("detected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("anomaly_score", sa.Float()),
        sa.Column("classification", sa.String(20)),
        sa.Column("observed_technique_ids_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("incident_candidate_id", sa.String(36)),
        sa.Column("response_recommendation_id", sa.String(36)),
        sa.Column("orchestration_id", sa.String(36)),
        sa.Column("orchestration_state", sa.String(60)),
        synthetic(),
        sa.UniqueConstraint("experiment_id", "step_sequence", name="uq_purple_step_sequence"),
    )
    op.create_index(
        "ix_purple_team_step_results_experiment_id", "purple_team_step_results", ["experiment_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_purple_team_step_results_experiment_id", table_name="purple_team_step_results")
    op.drop_table("purple_team_step_results")
    op.drop_index("ix_purple_team_experiments_scenario_id", table_name="purple_team_experiments")
    op.drop_table("purple_team_experiments")
