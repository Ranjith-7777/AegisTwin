"""Add auditable synthetic incident correlation persistence."""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260722_0005"
down_revision: Union[str, None] = "20260721_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("mitre_technique_catalogue", sa.Column("technique_id", sa.String(20), primary_key=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("tactics_json", sa.JSON(), nullable=False), sa.Column("description", sa.String(500), nullable=False), sa.Column("mapping_conditions", sa.String(800), nullable=False), sa.Column("catalogue_version", sa.String(30), nullable=False), sa.Column("source_name", sa.String(80), nullable=False), sa.Column("reference_date", sa.String(10), nullable=False), sa.Column("synthetic_demo_applicable", sa.Boolean(), nullable=False), sa.Column("synthetic", sa.Boolean(), nullable=False))
    op.create_table("technique_observations", sa.Column("mapping_id", sa.String(36), primary_key=True), sa.Column("technique_id", sa.String(20), nullable=False), sa.Column("technique_name", sa.String(120), nullable=False), sa.Column("simulation_run_id", sa.String(36), nullable=False), sa.Column("model_id", sa.String(36), nullable=False), sa.Column("event_id", sa.String(36), nullable=False), sa.Column("sequence_number", sa.Integer(), nullable=False), sa.Column("mapping_confidence", sa.Float(), nullable=False), sa.Column("evidence_fields_json", sa.JSON(), nullable=False), sa.Column("rationale", sa.String(800), nullable=False), sa.Column("tactic", sa.String(60), nullable=False), sa.Column("mapper_version", sa.String(30), nullable=False), sa.Column("synthetic", sa.Boolean(), nullable=False), sa.UniqueConstraint("simulation_run_id", "model_id", "event_id", "technique_id", "mapper_version", name="uq_technique_observation"))
    op.create_index("ix_technique_run", "technique_observations", ["simulation_run_id"])
    op.create_table("incident_candidates", sa.Column("incident_candidate_id", sa.String(36), primary_key=True), sa.Column("simulation_run_id", sa.String(36), nullable=False), sa.Column("model_id", sa.String(36), nullable=False), sa.Column("title", sa.String(160), nullable=False), sa.Column("summary", sa.String(800), nullable=False), sa.Column("correlation_state", sa.String(30), nullable=False), sa.Column("priority", sa.String(20), nullable=False), sa.Column("correlation_score", sa.Float(), nullable=False), sa.Column("component_scores_json", sa.JSON(), nullable=False), sa.Column("first_sequence_number", sa.Integer(), nullable=False), sa.Column("latest_sequence_number", sa.Integer(), nullable=False), sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("latest_observed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("primary_user_id", sa.String(100)), sa.Column("primary_device_id", sa.String(100)), sa.Column("involved_asset_ids_json", sa.JSON(), nullable=False), sa.Column("observed_tactic_ids_json", sa.JSON(), nullable=False), sa.Column("observed_technique_ids_json", sa.JSON(), nullable=False), sa.Column("evidence_count", sa.Integer(), nullable=False), sa.Column("correlation_engine_version", sa.String(30), nullable=False), sa.Column("synthetic", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("simulation_run_id", "model_id", "correlation_engine_version", name="uq_incident_run_model_engine"))
    op.create_table("incident_evidence", sa.Column("evidence_id", sa.String(36), primary_key=True), sa.Column("incident_candidate_id", sa.String(36), nullable=False), sa.Column("event_id", sa.String(36), nullable=False), sa.Column("assessment_id", sa.String(36)), sa.Column("technique_mapping_id", sa.String(36)), sa.Column("sequence_number", sa.Integer(), nullable=False), sa.Column("evidence_type", sa.String(60), nullable=False), sa.Column("contribution_score", sa.Float(), nullable=False), sa.Column("rationale", sa.String(800), nullable=False), sa.Column("synthetic", sa.Boolean(), nullable=False), sa.UniqueConstraint("incident_candidate_id", "event_id", name="uq_incident_event"))
    op.create_table("incident_candidate_snapshots", sa.Column("snapshot_id", sa.String(36), primary_key=True), sa.Column("incident_candidate_id", sa.String(36), nullable=False), sa.Column("sequence_number", sa.Integer(), nullable=False), sa.Column("snapshot_json", sa.JSON(), nullable=False), sa.Column("synthetic", sa.Boolean(), nullable=False), sa.UniqueConstraint("incident_candidate_id", "sequence_number", name="uq_incident_snapshot"))


def downgrade() -> None:
    op.drop_table("incident_candidate_snapshots")
    op.drop_table("incident_evidence")
    op.drop_table("incident_candidates")
    op.drop_index("ix_technique_run", table_name="technique_observations")
    op.drop_table("technique_observations")
    op.drop_table("mitre_technique_catalogue")
