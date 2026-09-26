from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import RequireAdmin, RequireAnalyst, RequireViewer
from app.database.models import ResponseOrchestrationRecord
from app.database.session import get_database_session
from app.schemas.orchestration import (
    AdvanceRequest,
    ApprovalDecisionRequest,
    AuditEventView,
    AuditIntegrity,
    ExecuteRequest,
    OrchestrationCreateRequest,
    OrchestrationPage,
    OrchestrationView,
    RollbackRequest,
)
from app.services.orchestration_service import orchestration_service

router = APIRouter(prefix="/v1/orchestration", tags=["orchestration"])
Db = Annotated[Session, Depends(get_database_session)]


@router.post(
    "/runs/{run_id}/create", response_model=OrchestrationView, dependencies=[RequireAnalyst]
)
def create(run_id: str, request: OrchestrationCreateRequest, session: Db) -> OrchestrationView:
    return orchestration_service.create(
        session,
        run_id,
        request.model_id,
        request.incident_candidate_id,
        request.selected_recommendation_id,
        request.through_sequence_number,
    )


@router.get("", response_model=OrchestrationPage, dependencies=[RequireViewer])
def list_orchestrations(session: Db, run_id: str | None = None) -> OrchestrationPage:
    query = select(ResponseOrchestrationRecord).order_by(
        ResponseOrchestrationRecord.updated_at.desc()
    )
    if run_id is not None:
        query = query.where(ResponseOrchestrationRecord.simulation_run_id == run_id)
    rows = list(session.scalars(query))
    return OrchestrationPage(
        items=[orchestration_service.view(session, row) for row in rows], total=len(rows)
    )


@router.get("/{orchestration_id}", response_model=OrchestrationView, dependencies=[RequireViewer])
def detail(orchestration_id: str, session: Db) -> OrchestrationView:
    return orchestration_service.view(
        session, orchestration_service._get(session, orchestration_id)
    )


@router.get(
    "/{orchestration_id}/plan", response_model=OrchestrationView, dependencies=[RequireViewer]
)
def plan(orchestration_id: str, session: Db) -> OrchestrationView:
    return detail(orchestration_id, session)


@router.get(
    "/{orchestration_id}/decisions",
    response_model=OrchestrationView,
    dependencies=[RequireViewer],
)
def decisions(orchestration_id: str, session: Db) -> OrchestrationView:
    return detail(orchestration_id, session)


@router.post(
    "/{orchestration_id}/advance", response_model=OrchestrationView, dependencies=[RequireAnalyst]
)
def advance(orchestration_id: str, request: AdvanceRequest, session: Db) -> OrchestrationView:
    return orchestration_service.advance(session, orchestration_id, request.expected_state)


@router.post(
    "/{orchestration_id}/approvals/{approval_id}/decide",
    response_model=OrchestrationView,
    dependencies=[RequireAdmin],
)
def decide(
    orchestration_id: str, approval_id: str, request: ApprovalDecisionRequest, session: Db
) -> OrchestrationView:
    return orchestration_service.decide_approval(
        session,
        orchestration_id,
        approval_id,
        request.actor_role,
        request.actor_display_name,
        request.decision,
        request.reason,
    )


@router.post(
    "/{orchestration_id}/execute", response_model=OrchestrationView, dependencies=[RequireAnalyst]
)
def execute(orchestration_id: str, request: ExecuteRequest, session: Db) -> OrchestrationView:
    return orchestration_service.execute(
        session, orchestration_id, request.expected_state, request.failure_mode
    )


@router.post(
    "/{orchestration_id}/verify", response_model=OrchestrationView, dependencies=[RequireAnalyst]
)
def verify(orchestration_id: str, session: Db) -> OrchestrationView:
    return orchestration_service.verify(session, orchestration_id)


@router.post(
    "/{orchestration_id}/rollback", response_model=OrchestrationView, dependencies=[RequireAdmin]
)
def rollback(orchestration_id: str, request: RollbackRequest, session: Db) -> OrchestrationView:
    return orchestration_service.rollback(
        session, orchestration_id, request.reason, request.requested_by
    )


@router.get(
    "/{orchestration_id}/audit",
    response_model=list[AuditEventView],
    dependencies=[RequireViewer],
)
def audit(orchestration_id: str, session: Db) -> list[AuditEventView]:
    return orchestration_service.audit(session, orchestration_id)


@router.get(
    "/{orchestration_id}/audit/verify",
    response_model=AuditIntegrity,
    dependencies=[RequireViewer],
)
def audit_verify(orchestration_id: str, session: Db) -> AuditIntegrity:
    return orchestration_service.verify_audit(session, orchestration_id)
