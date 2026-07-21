"""Add detection quality diagnostics and hybrid audit fields.

Revision ID: 20260721_0004
Revises: 20260721_0003
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_0004"
down_revision: str | None = "20260721_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("detection_models") as batch:
        batch.add_column(sa.Column("calibration_method", sa.String(60), nullable=False, server_default="empirical-quantile-v1"))
    with op.batch_alter_table("anomaly_assessments") as batch:
        batch.add_column(sa.Column("component_scores_json", sa.JSON(), nullable=False, server_default="{}"))
    with op.batch_alter_table("model_evaluations") as batch:
        batch.add_column(sa.Column("feature_schema_version", sa.String(30), nullable=False, server_default="synthetic-behaviour-v1"))
        batch.add_column(sa.Column("calibration_method", sa.String(60), nullable=False, server_default="empirical-quantile-v1"))
        batch.add_column(sa.Column("evaluation_label_mode", sa.String(60), nullable=False, server_default="scenario-wide"))
        for name in (
            "event_level_metrics_json",
            "scenario_wide_metrics_json",
            "run_level_metrics_json",
            "per_step_metrics_json",
            "score_distribution_json",
            "calibration_comparison_json",
            "pure_isolation_metrics_json",
            "hybrid_metrics_json",
            "diagnostic_report_json",
        ):
            batch.add_column(sa.Column(name, sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("model_evaluations") as batch:
        for name in (
            "diagnostic_report_json",
            "hybrid_metrics_json",
            "pure_isolation_metrics_json",
            "calibration_comparison_json",
            "score_distribution_json",
            "per_step_metrics_json",
            "run_level_metrics_json",
            "scenario_wide_metrics_json",
            "event_level_metrics_json",
            "evaluation_label_mode",
            "calibration_method",
            "feature_schema_version",
        ):
            batch.drop_column(name)
    with op.batch_alter_table("anomaly_assessments") as batch:
        batch.drop_column("component_scores_json")
    with op.batch_alter_table("detection_models") as batch:
        batch.drop_column("calibration_method")
