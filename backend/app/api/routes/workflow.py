from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import RequireAnalyst
from app.database.session import get_database_session
from app.schemas.blue_planning import BluePlanningCompareRequest
from app.schemas.workflow import WorkflowRunResult
from app.services.workflow_coordinator_service import workflow_coordinator

router = APIRouter(prefix="/v1/workflow", tags=["workflow"])
Db = Annotated[Session, Depends(get_database_session)]


@router.post(
    "/runs/{run_id}/execute", response_model=WorkflowRunResult, dependencies=[RequireAnalyst]
)
def run_workflow(
    run_id: str, request: BluePlanningCompareRequest, session: Db
) -> WorkflowRunResult:
    return workflow_coordinator.run(
        session,
        run_id,
        request.model_id,
        request.incident_candidate_id,
        request.through_sequence_number,
        request.top_k,
    )
