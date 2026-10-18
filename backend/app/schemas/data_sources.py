from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

SourceKindName = Literal["synthetic", "replay", "live_readonly"]


class DataSourceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_id: str
    source_kind: SourceKindName
    adapter: str
    dataset_name: str
    file_name: str
    file_sha256: str
    file_bytes: int
    licence: str
    citation: str | None
    provenance_notes_json: list[str]
    window_start: datetime | None
    window_end: datetime | None
    rows_read: int
    rows_accepted: int
    rows_rejected: int
    rows_duplicate: int
    rows_unmapped: int
    rows_timestamp_adjusted: int
    rows_rate_missing: int
    rejection_reasons_json: dict[str, int]
    unmapped_endpoints_json: dict[str, int]
    label_counts_json: dict[str, int]
    imported_by: str
    imported_at: datetime


class BuiltInSource(BaseModel):
    source_kind: SourceKindName
    name: str
    status: Literal["active", "not_implemented"]
    description: str


class DataSourceCatalogue(BaseModel):
    simulation_only: bool
    built_in: list[BuiltInSource]
    imported: list[DataSourceView]
    import_instructions: str


class NetworkFlowEvaluationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evaluation_id: str
    model_version: str
    feature_schema_version: str
    train_source_id: str
    eval_source_id: str
    protocol_json: dict[str, object]
    metrics_json: dict[str, object]
    created_at: datetime


class MitreMappingView(BaseModel):
    technique_id: str
    name: str
    rationale: str


class FlowFindingView(BaseModel):
    rule: str
    window_start: datetime
    window_end: datetime
    src_ip: str
    dst_ip: str
    src_asset_id: str | None
    dst_asset_id: str | None
    summary: str
    flow_count: int
    dst_ports: list[int]
    total_bytes: int
    mitre: MitreMappingView | None
    label_agreement: float | None


class FlowFindingsResponse(BaseModel):
    source_id: str
    ruleset_version: str
    window_minutes: int
    total_findings: int
    counts_by_rule: dict[str, int]
    findings: list[FlowFindingView]
    labels_note: str
