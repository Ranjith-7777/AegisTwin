"""Add recorded-dataset ingestion: data sources, network flows, evaluations.

Phase 2 (real-world data). Additive only - no existing table changes.
Recorded datasets (e.g. CIC-IDS2017) are imported as `source_kind="replay"`;
see docs/REAL_DATA_INGESTION.md.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261013_0019"
down_revision: Union[str, None] = "20261007_0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "data_sources",
        sa.Column("source_id", sa.String(length=36), primary_key=True),
        sa.Column("source_kind", sa.String(length=20), nullable=False),
        sa.Column("adapter", sa.String(length=40), nullable=False),
        sa.Column("dataset_name", sa.String(length=120), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_sha256", sa.String(length=64), nullable=False),
        sa.Column("file_bytes", sa.Integer(), nullable=False),
        sa.Column("licence", sa.String(length=500), nullable=False),
        sa.Column("citation", sa.String(length=500), nullable=True),
        sa.Column("provenance_notes_json", sa.JSON(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_read", sa.Integer(), nullable=False),
        sa.Column("rows_accepted", sa.Integer(), nullable=False),
        sa.Column("rows_rejected", sa.Integer(), nullable=False),
        sa.Column("rows_duplicate", sa.Integer(), nullable=False),
        sa.Column("rows_unmapped", sa.Integer(), nullable=False),
        sa.Column("rows_timestamp_adjusted", sa.Integer(), nullable=False),
        sa.Column("rows_rate_missing", sa.Integer(), nullable=False),
        sa.Column("rejection_reasons_json", sa.JSON(), nullable=False),
        sa.Column("unmapped_endpoints_json", sa.JSON(), nullable=False),
        sa.Column("label_counts_json", sa.JSON(), nullable=False),
        sa.Column("imported_by", sa.String(length=120), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("file_sha256"),
    )
    op.create_index("ix_data_sources_source_kind", "data_sources", ["source_kind"])

    op.create_table(
        "network_flows",
        sa.Column("flow_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "source_id",
            sa.String(length=36),
            sa.ForeignKey("data_sources.source_id"),
            nullable=False,
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("src_ip", sa.String(length=45), nullable=False),
        sa.Column("src_port", sa.Integer(), nullable=False),
        sa.Column("dst_ip", sa.String(length=45), nullable=False),
        sa.Column("dst_port", sa.Integer(), nullable=False),
        sa.Column("protocol", sa.Integer(), nullable=False),
        sa.Column("duration_s", sa.Float(), nullable=False),
        sa.Column("fwd_packets", sa.Integer(), nullable=False),
        sa.Column("bwd_packets", sa.Integer(), nullable=False),
        sa.Column("fwd_bytes", sa.Integer(), nullable=False),
        sa.Column("bwd_bytes", sa.Integer(), nullable=False),
        sa.Column("syn_count", sa.Integer(), nullable=False),
        sa.Column("fin_count", sa.Integer(), nullable=False),
        sa.Column("rst_count", sa.Integer(), nullable=False),
        sa.Column("psh_count", sa.Integer(), nullable=False),
        sa.Column("ack_count", sa.Integer(), nullable=False),
        sa.Column("flow_bytes_per_s", sa.Float(), nullable=True),
        sa.Column("flow_packets_per_s", sa.Float(), nullable=True),
        sa.Column("src_testbed_identity", sa.String(length=80), nullable=True),
        sa.Column("dst_testbed_identity", sa.String(length=80), nullable=True),
        sa.Column("src_asset_id", sa.String(length=80), nullable=True),
        sa.Column("dst_asset_id", sa.String(length=80), nullable=True),
        sa.Column("evaluation_label", sa.String(length=80), nullable=True),
    )
    op.create_index("ix_network_flows_source_id", "network_flows", ["source_id"])
    op.create_index("ix_network_flows_source_time", "network_flows", ["source_id", "observed_at"])

    op.create_table(
        "network_flow_evaluations",
        sa.Column("evaluation_id", sa.String(length=36), primary_key=True),
        sa.Column("model_version", sa.String(length=60), nullable=False),
        sa.Column("feature_schema_version", sa.String(length=60), nullable=False),
        sa.Column(
            "train_source_id",
            sa.String(length=36),
            sa.ForeignKey("data_sources.source_id"),
            nullable=False,
        ),
        sa.Column(
            "eval_source_id",
            sa.String(length=36),
            sa.ForeignKey("data_sources.source_id"),
            nullable=False,
        ),
        sa.Column("protocol_json", sa.JSON(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("artifact_path", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_network_flow_evaluations_train_source_id",
        "network_flow_evaluations",
        ["train_source_id"],
    )
    op.create_index(
        "ix_network_flow_evaluations_eval_source_id",
        "network_flow_evaluations",
        ["eval_source_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_network_flow_evaluations_eval_source_id", table_name="network_flow_evaluations"
    )
    op.drop_index(
        "ix_network_flow_evaluations_train_source_id", table_name="network_flow_evaluations"
    )
    op.drop_table("network_flow_evaluations")
    op.drop_index("ix_network_flows_source_time", table_name="network_flows")
    op.drop_index("ix_network_flows_source_id", table_name="network_flows")
    op.drop_table("network_flows")
    op.drop_index("ix_data_sources_source_kind", table_name="data_sources")
    op.drop_table("data_sources")
