"""Add offline synthetic anomaly detection persistence.

Revision ID: 20260721_0003
Revises: 20260721_0002
Create Date: 2026-07-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_0003"
down_revision: str | None = "20260721_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "detection_models",
        sa.Column("model_id", sa.String(36), primary_key=True),
        sa.Column("model_type", sa.String(60), nullable=False),
        sa.Column("model_version", sa.String(30), nullable=False),
        sa.Column("feature_schema_version", sa.String(30), nullable=False),
        sa.Column("calibration_version", sa.String(30), nullable=False),
        sa.Column("artifact_path", sa.String(500), nullable=False),
        sa.Column("configuration_json", sa.JSON(), nullable=False),
        sa.Column("dataset_fingerprint", sa.String(64), nullable=False),
        sa.Column("random_state", sa.Integer(), nullable=False),
        sa.Column("target_false_positive_rate", sa.Float(), nullable=False),
        sa.Column("calibrated_threshold", sa.Float(), nullable=False),
        sa.Column("threshold_percentile", sa.Float(), nullable=False),
        sa.Column("training_event_count", sa.Integer(), nullable=False),
        sa.Column("validation_event_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("synthetic", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_detection_models_dataset_fingerprint", "detection_models", ["dataset_fingerprint"])
    op.create_table(
        "anomaly_assessments",
        sa.Column("assessment_id", sa.String(36), primary_key=True),
        sa.Column("model_id", sa.String(36), sa.ForeignKey("detection_models.model_id"), nullable=False),
        sa.Column("simulation_run_id", sa.String(36), sa.ForeignKey("simulation_runs.simulation_run_id"), nullable=False),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("telemetry_events.event_id"), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("raw_score", sa.Float(), nullable=False),
        sa.Column("anomaly_score", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("classification", sa.String(20), nullable=False),
        sa.Column("contributing_signals_json", sa.JSON(), nullable=False),
        sa.Column("scored_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("synthetic", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("model_id", "event_id", name="uq_assessment_model_event"),
    )
    for column in ("model_id", "simulation_run_id", "event_id", "anomaly_score", "classification"):
        op.create_index(f"ix_anomaly_assessments_{column}", "anomaly_assessments", [column])
    op.create_table(
        "model_evaluations",
        sa.Column("evaluation_id", sa.String(36), primary_key=True),
        sa.Column("model_id", sa.String(36), sa.ForeignKey("detection_models.model_id"), nullable=False),
        sa.Column("configuration_json", sa.JSON(), nullable=False),
        sa.Column("normal_event_count", sa.Integer(), nullable=False),
        sa.Column("suspicious_scenario_event_count", sa.Integer(), nullable=False),
        sa.Column("true_positive", sa.Integer(), nullable=False),
        sa.Column("false_positive", sa.Integer(), nullable=False),
        sa.Column("true_negative", sa.Integer(), nullable=False),
        sa.Column("false_negative", sa.Integer(), nullable=False),
        sa.Column("precision", sa.Float(), nullable=False),
        sa.Column("recall", sa.Float(), nullable=False),
        sa.Column("f1_score", sa.Float(), nullable=False),
        sa.Column("false_positive_rate", sa.Float(), nullable=False),
        sa.Column("roc_auc", sa.Float(), nullable=True),
        sa.Column("average_precision", sa.Float(), nullable=True),
        sa.Column("baseline_metrics_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("synthetic", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_model_evaluations_model_id", "model_evaluations", ["model_id"])


def downgrade() -> None:
    op.drop_table("model_evaluations")
    op.drop_table("anomaly_assessments")
    op.drop_table("detection_models")
