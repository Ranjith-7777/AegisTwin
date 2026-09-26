"""Add synthetic response recommendation and impact simulation persistence."""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260722_0007"
down_revision: Union[str, None] = "20260722_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("response_playbook_catalogue", sa.Column("playbook_id", sa.String(80), primary_key=True), sa.Column("playbook_version", sa.String(30), nullable=False), sa.Column("catalogue_version", sa.String(30), nullable=False), sa.Column("definition_json", sa.JSON(), nullable=False), sa.Column("synthetic", sa.Boolean(), nullable=False))
    op.create_table("response_analyses", sa.Column("response_analysis_id", sa.String(36), primary_key=True), sa.Column("simulation_run_id", sa.String(36), nullable=False), sa.Column("model_id", sa.String(36), nullable=False), sa.Column("incident_candidate_id", sa.String(36), nullable=False), sa.Column("prediction_snapshot_id", sa.String(36)), sa.Column("through_sequence_number", sa.Integer(), nullable=False), sa.Column("response_engine_version", sa.String(40), nullable=False), sa.Column("recommendation_count", sa.Integer(), nullable=False), sa.Column("synthetic", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("simulation_run_id", "model_id", "incident_candidate_id", "through_sequence_number", "response_engine_version", name="uq_response_analysis"))
    op.create_table("response_recommendations", sa.Column("recommendation_id", sa.String(36), primary_key=True), sa.Column("response_analysis_id", sa.String(36), nullable=False), sa.Column("simulation_run_id", sa.String(36), nullable=False), sa.Column("model_id", sa.String(36), nullable=False), sa.Column("incident_candidate_id", sa.String(36), nullable=False), sa.Column("prediction_snapshot_id", sa.String(36)), sa.Column("through_sequence_number", sa.Integer(), nullable=False), sa.Column("playbook_id", sa.String(80), nullable=False), sa.Column("target_type", sa.String(30), nullable=False), sa.Column("target_id", sa.String(220), nullable=False), sa.Column("rank", sa.Integer(), nullable=False), sa.Column("recommendation_score", sa.Float(), nullable=False), sa.Column("component_scores_json", sa.JSON(), nullable=False), sa.Column("penalties_json", sa.JSON(), nullable=False), sa.Column("required_approval_tier", sa.String(40), nullable=False), sa.Column("recommendation_state", sa.String(40), nullable=False), sa.Column("evidence_summary_json", sa.JSON(), nullable=False), sa.Column("rationale", sa.String(1000), nullable=False), sa.Column("warnings_json", sa.JSON(), nullable=False), sa.Column("synthetic", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("response_analysis_id", "playbook_id", "target_type", "target_id", name="uq_response_recommendation_target"))
    op.create_table("response_impact_simulations", sa.Column("simulation_id", sa.String(36), primary_key=True), sa.Column("recommendation_id", sa.String(36), nullable=False, unique=True), sa.Column("simulation_run_id", sa.String(36), nullable=False), sa.Column("through_sequence_number", sa.Integer(), nullable=False), sa.Column("base_topology_version", sa.String(60), nullable=False), sa.Column("simulation_engine_version", sa.String(40), nullable=False), sa.Column("target_type", sa.String(30), nullable=False), sa.Column("target_id", sa.String(220), nullable=False), sa.Column("changed_node_ids_json", sa.JSON(), nullable=False), sa.Column("changed_edge_ids_json", sa.JSON(), nullable=False), sa.Column("paths_before_json", sa.JSON(), nullable=False), sa.Column("paths_after_json", sa.JSON(), nullable=False), sa.Column("correlated_paths_interrupted", sa.Integer(), nullable=False), sa.Column("predicted_paths_interrupted", sa.Integer(), nullable=False), sa.Column("sensitive_assets_reachable_before", sa.Integer(), nullable=False), sa.Column("sensitive_assets_reachable_after", sa.Integer(), nullable=False), sa.Column("expected_relationships_affected", sa.Integer(), nullable=False), sa.Column("affected_asset_count", sa.Integer(), nullable=False), sa.Column("affected_edge_count", sa.Integer(), nullable=False), sa.Column("interruption_score", sa.Float(), nullable=False), sa.Column("residual_exposure_score", sa.Float(), nullable=False), sa.Column("operational_disruption_score", sa.Float(), nullable=False), sa.Column("blast_radius", sa.String(30), nullable=False), sa.Column("reversibility", sa.String(30), nullable=False), sa.Column("warnings_json", sa.JSON(), nullable=False), sa.Column("synthetic", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))


def downgrade() -> None:
    op.drop_table("response_impact_simulations")
    op.drop_table("response_recommendations")
    op.drop_table("response_analyses")
    op.drop_table("response_playbook_catalogue")
