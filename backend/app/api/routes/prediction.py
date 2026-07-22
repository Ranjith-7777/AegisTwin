from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import (
    PredictionEvaluationRecord,
    PredictionHypothesisRecord,
    PredictionSnapshotRecord,
)
from app.database.session import get_database_session
from app.schemas.prediction import (
    PredictionAnalysisResult,
    PredictionAnalyzeRequest,
    PredictionEvaluation,
    PredictionHypothesis,
    PredictionSnapshot,
    PredictionSnapshotPage,
)
from app.services.prediction_evaluation_service import prediction_evaluation_service
from app.services.prediction_service import prediction_service

router = APIRouter(prefix="/v1/prediction", tags=["prediction"])
Db = Annotated[Session, Depends(get_database_session)]


@router.post("/runs/{run_id}/analyze", response_model=PredictionAnalysisResult)
def analyze(
    run_id: str, request: PredictionAnalyzeRequest, session: Db
) -> PredictionAnalysisResult:
    return prediction_service.analyze(
        session, run_id, request.model_id, request.force_reanalyze, request.top_k
    )


@router.get("/runs/{run_id}/snapshots", response_model=PredictionSnapshotPage)
def snapshots(
    run_id: str,
    model_id: str,
    session: Db,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PredictionSnapshotPage:
    filters = [
        PredictionSnapshotRecord.simulation_run_id == run_id,
        PredictionSnapshotRecord.model_id == model_id,
    ]
    total = int(
        session.scalar(select(func.count()).select_from(PredictionSnapshotRecord).where(*filters))
        or 0
    )
    rows = list(
        session.scalars(
            select(PredictionSnapshotRecord)
            .where(*filters)
            .order_by(PredictionSnapshotRecord.through_sequence_number)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return PredictionSnapshotPage(
        items=[prediction_service.snapshot_schema(session, item) for item in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/runs/{run_id}/latest", response_model=PredictionSnapshot)
def latest(run_id: str, model_id: str, session: Db) -> PredictionSnapshot:
    record = session.scalar(
        select(PredictionSnapshotRecord)
        .where(
            PredictionSnapshotRecord.simulation_run_id == run_id,
            PredictionSnapshotRecord.model_id == model_id,
        )
        .order_by(PredictionSnapshotRecord.through_sequence_number.desc())
    )
    return _snapshot_or_404(session, record)


@router.get("/snapshots/{snapshot_id}", response_model=PredictionSnapshot)
def snapshot(snapshot_id: str, session: Db) -> PredictionSnapshot:
    return _snapshot_or_404(session, session.get(PredictionSnapshotRecord, snapshot_id))


@router.get("/snapshots/{snapshot_id}/hypotheses", response_model=list[PredictionHypothesis])
def hypotheses(snapshot_id: str, session: Db) -> list[PredictionHypothesis]:
    if session.get(PredictionSnapshotRecord, snapshot_id) is None:
        raise ApplicationError(
            "PREDICTION_SNAPSHOT_NOT_FOUND", "The prediction snapshot was not found.", 404
        )
    rows = session.scalars(
        select(PredictionHypothesisRecord)
        .where(PredictionHypothesisRecord.prediction_snapshot_id == snapshot_id)
        .order_by(PredictionHypothesisRecord.hypothesis_type, PredictionHypothesisRecord.rank)
    )
    return [prediction_service.hypothesis_schema(item) for item in rows]


@router.post("/runs/{run_id}/evaluate", response_model=PredictionEvaluation)
def evaluate(run_id: str, request: PredictionAnalyzeRequest, session: Db) -> PredictionEvaluation:
    return prediction_evaluation_service.evaluate(session, run_id, request.model_id)


@router.get("/evaluations/{evaluation_id}", response_model=PredictionEvaluation)
def evaluation(evaluation_id: str, session: Db) -> PredictionEvaluation:
    record = session.get(PredictionEvaluationRecord, evaluation_id)
    if record is None:
        raise ApplicationError(
            "PREDICTION_EVALUATION_NOT_FOUND", "The prediction evaluation was not found.", 404
        )
    return prediction_evaluation_service.schema(record)


def _snapshot_or_404(
    session: Session, record: PredictionSnapshotRecord | None
) -> PredictionSnapshot:
    if record is None:
        raise ApplicationError(
            "PREDICTION_SNAPSHOT_NOT_FOUND", "The prediction snapshot was not found.", 404
        )
    return prediction_service.snapshot_schema(session, record)
