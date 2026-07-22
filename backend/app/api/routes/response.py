from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import ResponseImpactSimulationRecord, ResponseRecommendationRecord
from app.database.session import get_database_session
from app.schemas.response import (
    DefensivePlaybook,
    ResponseAnalysisResult,
    ResponseAnalyzeRequest,
    ResponseImpactSimulation,
    ResponseRecommendation,
    ResponseRecommendationPage,
    ResponseRunSummary,
)
from app.services.response_playbook_service import response_playbook_service
from app.services.response_service import response_service

router = APIRouter(prefix="/v1/response", tags=["response"])
Db = Annotated[Session, Depends(get_database_session)]


@router.get("/playbooks", response_model=list[DefensivePlaybook])
def playbooks() -> list[DefensivePlaybook]:
    return response_playbook_service.list()


@router.get("/playbooks/{playbook_id}", response_model=DefensivePlaybook)
def playbook(playbook_id: str) -> DefensivePlaybook:
    return response_playbook_service.get(playbook_id)


@router.post("/runs/{run_id}/analyze", response_model=ResponseAnalysisResult)
def analyze(run_id: str, request: ResponseAnalyzeRequest, session: Db) -> ResponseAnalysisResult:
    return response_service.analyze(
        session,
        run_id,
        request.model_id,
        request.through_sequence_number,
        request.prediction_enabled,
        request.top_k,
        request.force_reanalyze,
    )


@router.get("/runs/{run_id}/recommendations", response_model=ResponseRecommendationPage)
def recommendations(
    run_id: str,
    model_id: str,
    session: Db,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ResponseRecommendationPage:
    filters = [
        ResponseRecommendationRecord.simulation_run_id == run_id,
        ResponseRecommendationRecord.model_id == model_id,
    ]
    total = int(
        session.scalar(
            select(func.count()).select_from(ResponseRecommendationRecord).where(*filters)
        )
        or 0
    )
    rows = list(
        session.scalars(
            select(ResponseRecommendationRecord)
            .where(*filters)
            .order_by(
                ResponseRecommendationRecord.through_sequence_number.desc(),
                ResponseRecommendationRecord.rank,
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return ResponseRecommendationPage(
        items=[response_service.recommendation_schema(session, item) for item in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=(total + page_size - 1) // page_size,
        synthetic=True,
    )


@router.get("/recommendations/{recommendation_id}", response_model=ResponseRecommendation)
def recommendation(recommendation_id: str, session: Db) -> ResponseRecommendation:
    record = session.get(ResponseRecommendationRecord, recommendation_id)
    if record is None:
        raise ApplicationError(
            "RESPONSE_RECOMMENDATION_NOT_FOUND", "The synthetic recommendation was not found.", 404
        )
    return response_service.recommendation_schema(session, record)


@router.get(
    "/recommendations/{recommendation_id}/simulation", response_model=ResponseImpactSimulation
)
def simulation(recommendation_id: str, session: Db) -> ResponseImpactSimulation:
    recommendation = session.get(ResponseRecommendationRecord, recommendation_id)
    record = session.scalar(
        select(ResponseImpactSimulationRecord).where(
            ResponseImpactSimulationRecord.recommendation_id == recommendation_id
        )
    )
    if recommendation is None or record is None:
        raise ApplicationError(
            "RESPONSE_SIMULATION_NOT_FOUND", "The synthetic impact simulation was not found.", 404
        )
    return response_service.simulation_schema(recommendation, record)


@router.get("/runs/{run_id}/summary", response_model=ResponseRunSummary)
def summary(run_id: str, model_id: str, session: Db) -> ResponseRunSummary:
    return response_service.summary(session, run_id, model_id)
