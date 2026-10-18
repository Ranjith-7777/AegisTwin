from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import RequireAnalyst, RequireViewer
from app.core.exceptions import ApplicationError
from app.database.session import get_database_session
from app.schemas.blue_planning import BluePlanningCompareRequest
from app.schemas.workflow import WorkflowRunResult
from app.services.workflow_coordinator_service import workflow_coordinator

router = APIRouter(prefix="/v1/workflow", tags=["workflow"])
Db = Annotated[Session, Depends(get_database_session)]


@router.get("/runs/{run_id}/state", response_model=WorkflowRunResult, dependencies=[RequireViewer])
def workflow_state(
    run_id: str, session: Db, model_id: Annotated[str, Query(min_length=1)]
) -> WorkflowRunResult:
    """Persisted workflow state of a run (read-only; never re-plans or executes)."""

    restored = workflow_coordinator.restore(session, run_id, model_id)
    if restored is None:
        raise ApplicationError(
            "WORKFLOW_STATE_NOT_FOUND",
            "No Blue workflow has been recorded for this run and model.",
            404,
        )
    return restored


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
