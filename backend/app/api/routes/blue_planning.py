from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.session import get_database_session
from app.schemas.blue_planning import BluePlanningCompareRequest, PlanComparisonResult
from app.services.blue_planning_service import blue_planning_service

router = APIRouter(prefix="/v1/blue-planning", tags=["blue-planning"])
Db = Annotated[Session, Depends(get_database_session)]


@router.post("/runs/{run_id}/compare", response_model=PlanComparisonResult)
def compare(run_id: str, request: BluePlanningCompareRequest, session: Db) -> PlanComparisonResult:
    return blue_planning_service.compare(
        session,
        run_id,
        request.model_id,
        request.incident_candidate_id,
        request.through_sequence_number,
        request.top_k,
    )


@router.get("/assessments/{assessment_id}", response_model=PlanComparisonResult)
def get_assessment(assessment_id: str, session: Db) -> PlanComparisonResult:
    result = blue_planning_service.load(session, assessment_id)
    if result is None:
        raise ApplicationError(
            "PLAN_ASSESSMENT_NOT_FOUND", "The synthetic plan assessment was not found.", 404
        )
    return result
