"""Add causal synthetic progression prediction persistence."""

from collections.abc import Sequence
from typing import Union
import sqlalchemy as sa
from alembic import op

revision: str = "20260722_0006"
down_revision: Union[str, None] = "20260722_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("progression_catalogue_entries", sa.Column("entry_id", sa.String(60), primary_key=True), sa.Column("source_technique_id", sa.String(20)), sa.Column("destination_technique_id", sa.String(20)), sa.Column("source_tactic", sa.String(60)), sa.Column("destination_tactic", sa.String(60), nullable=False), sa.Column("rationale", sa.String(800), nullable=False), sa.Column("prerequisites_json", sa.JSON(), nullable=False), sa.Column("contradictions_json", sa.JSON(), nullable=False), sa.Column("transition_weight", sa.Float(), nullable=False), sa.Column("catalogue_version", sa.String(40), nullable=False), sa.Column("synthetic", sa.Boolean(), nullable=False))
    op.create_table("prediction_snapshots", sa.Column("prediction_snapshot_id", sa.String(36), primary_key=True), sa.Column("simulation_run_id", sa.String(36), nullable=False), sa.Column("model_id", sa.String(36), nullable=False), sa.Column("incident_candidate_id", sa.String(36)), sa.Column("through_sequence_number", sa.Integer(), nullable=False), sa.Column("predictor_version", sa.String(40), nullable=False), sa.Column("progression_catalogue_version", sa.String(40), nullable=False), sa.Column("prediction_state", sa.String(30), nullable=False), sa.Column("current_stage_estimate", sa.String(60), nullable=False), sa.Column("current_tactic_estimate", sa.String(60), nullable=False), sa.Column("observed_technique_ids_json", sa.JSON(), nullable=False), sa.Column("observed_tactic_ids_json", sa.JSON(), nullable=False), sa.Column("candidate_hypothesis_count", sa.Integer(), nullable=False), sa.Column("insufficient_evidence_reason", sa.String(500)), sa.Column("supporting_evidence_json", sa.JSON(), nullable=False), sa.Column("synthetic", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("simulation_run_id", "model_id", "predictor_version", "through_sequence_number", name="uq_prediction_snapshot"))
    op.create_table("prediction_hypotheses", sa.Column("hypothesis_id", sa.String(36), primary_key=True), sa.Column("prediction_snapshot_id", sa.String(36), nullable=False), sa.Column("rank", sa.Integer(), nullable=False), sa.Column("hypothesis_type", sa.String(30), nullable=False), sa.Column("predicted_technique_id", sa.String(20)), sa.Column("predicted_technique_name", sa.String(120)), sa.Column("predicted_tactic", sa.String(60)), sa.Column("predicted_asset_id", sa.String(100)), sa.Column("predicted_objective", sa.String(60)), sa.Column("prediction_score", sa.Float(), nullable=False), sa.Column("component_scores_json", sa.JSON(), nullable=False), sa.Column("prerequisite_evidence_json", sa.JSON(), nullable=False), sa.Column("contradictory_evidence_json", sa.JSON(), nullable=False), sa.Column("rationale", sa.String(1000), nullable=False), sa.Column("synthetic", sa.Boolean(), nullable=False), sa.UniqueConstraint("prediction_snapshot_id", "hypothesis_type", "rank", name="uq_prediction_hypothesis"))
    op.create_table("prediction_evaluations", sa.Column("evaluation_id", sa.String(36), primary_key=True), sa.Column("simulation_run_id", sa.String(36), nullable=False), sa.Column("model_id", sa.String(36), nullable=False), sa.Column("predictor_version", sa.String(40), nullable=False), sa.Column("metrics_json", sa.JSON(), nullable=False), sa.Column("baseline_metrics_json", sa.JSON(), nullable=False), sa.Column("truth_manifest_version", sa.String(40), nullable=False), sa.Column("synthetic", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    op.drop_table("prediction_evaluations")
    op.drop_table("prediction_hypotheses")
    op.drop_table("prediction_snapshots")
    op.drop_table("progression_catalogue_entries")
