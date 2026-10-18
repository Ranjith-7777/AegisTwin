"""Read-only API over imported recorded datasets.

Imports and evaluations run from the operator CLI (`python -m app.ingestion`),
never over HTTP, so no endpoint reads arbitrary server paths. Nothing here
can trigger a response action: recorded data is analysed, never acted on.
"""

from collections import Counter
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import RequireViewer
from app.core.exceptions import ApplicationError
from app.database.models import DataSourceRecord, NetworkFlowEvaluationRecord
from app.database.session import get_database_session
from app.schemas.data_sources import (
    BuiltInSource,
    DataSourceCatalogue,
    DataSourceView,
    FlowFindingsResponse,
    FlowFindingView,
    MitreMappingView,
    NetworkFlowEvaluationView,
)
from app.services.network_flow.correlation_service import (
    RULESET_VERSION,
    RuleThresholds,
    correlate,
)

router = APIRouter(prefix="/v1/data-sources", tags=["data-sources"])
Db = Annotated[Session, Depends(get_database_session)]

IMPORT_INSTRUCTIONS = (
    "Download the CIC-IDS2017 labelled-flow CSVs (Monday and Tuesday) from "
    "https://www.unb.ca/cic/datasets/ids-2017.html into datasets/raw/cicids2017/ "
    "(git-ignored), then run: python -m app.ingestion import --adapter cicids2017 "
    "--file <csv> and python -m app.ingestion evaluate --train <monday-source-id> "
    "--eval <tuesday-source-id>. See docs/REAL_DATA_INGESTION.md."
)

BUILT_IN = [
    BuiltInSource(
        source_kind="synthetic",
        name="AegisArena scenario engine",
        status="active",
        description="Deterministic, seeded synthetic telemetry for the Red Agent scenarios.",
    ),
    BuiltInSource(
        source_kind="live_readonly",
        name="Live telemetry (read-only)",
        status="not_implemented",
        description=(
            "No live collector exists. If added, live data must stay read-only and "
            "recommendations-only; it can never trigger real remediation."
        ),
    ),
]


@router.get("", response_model=DataSourceCatalogue, dependencies=[RequireViewer])
def list_sources(request: Request, session: Db) -> DataSourceCatalogue:
    records = session.scalars(
        select(DataSourceRecord).order_by(DataSourceRecord.imported_at.desc())
    ).all()
    return DataSourceCatalogue(
        simulation_only=request.app.state.settings.simulation_only,
        built_in=BUILT_IN,
        imported=[DataSourceView.model_validate(record) for record in records],
        import_instructions=IMPORT_INSTRUCTIONS,
    )


@router.get(
    "/evaluations/latest",
    response_model=NetworkFlowEvaluationView,
    dependencies=[RequireViewer],
)
def latest_evaluation(session: Db) -> NetworkFlowEvaluationView:
    record = session.scalar(
        select(NetworkFlowEvaluationRecord)
        .order_by(NetworkFlowEvaluationRecord.created_at.desc())
        .limit(1)
    )
    if record is None:
        raise ApplicationError(
            "NETWORK_FLOW_EVALUATION_NOT_FOUND",
            "No recorded-dataset evaluation has been run yet.",
            404,
        )
    return NetworkFlowEvaluationView.model_validate(record)


@router.get("/{source_id}", response_model=DataSourceView, dependencies=[RequireViewer])
def get_source(source_id: str, session: Db) -> DataSourceView:
    record = session.get(DataSourceRecord, source_id)
    if record is None:
        raise ApplicationError("DATA_SOURCE_NOT_FOUND", "Unknown data source.", 404)
    return DataSourceView.model_validate(record)


@router.get(
    "/{source_id}/findings",
    response_model=FlowFindingsResponse,
    dependencies=[RequireViewer],
)
def findings(
    source_id: str,
    session: Db,
    window_minutes: Annotated[int, Query(ge=1, le=60)] = 5,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> FlowFindingsResponse:
    if session.get(DataSourceRecord, source_id) is None:
        raise ApplicationError("DATA_SOURCE_NOT_FOUND", "Unknown data source.", 404)
    results = correlate(session, source_id, RuleThresholds(window_minutes=window_minutes))
    ranked = sorted(results, key=lambda item: item.flow_count, reverse=True)[:limit]
    ranked.sort(key=lambda item: item.window_start)
    return FlowFindingsResponse(
        source_id=source_id,
        ruleset_version=RULESET_VERSION,
        window_minutes=window_minutes,
        total_findings=len(results),
        counts_by_rule=dict(Counter(item.rule for item in results)),
        findings=[
            FlowFindingView(
                rule=item.rule,
                window_start=item.window_start,
                window_end=item.window_end,
                src_ip=item.src_ip,
                dst_ip=item.dst_ip,
                src_asset_id=item.src_asset_id,
                dst_asset_id=item.dst_asset_id,
                summary=item.summary,
                flow_count=item.flow_count,
                dst_ports=item.dst_ports,
                total_bytes=item.total_bytes,
                mitre=MitreMappingView(**item.mitre.__dict__) if item.mitre else None,
                label_agreement=item.label_agreement,
            )
            for item in ranked
        ],
        labels_note=(
            "label_agreement is the share of a finding's own flows that the dataset labels "
            "as attacks. Rules never read labels; this column only evaluates them."
        ),
    )
