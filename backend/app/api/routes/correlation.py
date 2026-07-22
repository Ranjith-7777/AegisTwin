from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import (
    IncidentCandidateRecord,
    IncidentEvidenceRecord,
    TechniqueObservationRecord,
)
from app.database.session import get_database_session
from app.schemas.correlation import (
    CorrelationAnalysisResult,
    CorrelationAnalyzeRequest,
    IncidentCandidate,
    IncidentEvidence,
    IncidentPage,
    TechniqueObservation,
    TechniqueObservationPage,
)
from app.services.correlation_service import correlation_service

router = APIRouter(prefix="/v1/correlation", tags=["correlation"])
Db = Annotated[Session, Depends(get_database_session)]


@router.post("/runs/{run_id}/analyze", response_model=CorrelationAnalysisResult)
def analyze(
    run_id: str, request: CorrelationAnalyzeRequest, session: Db
) -> CorrelationAnalysisResult:
    return correlation_service.analyze(session, run_id, request.model_id, request.force_reanalyze)


@router.get("/runs/{run_id}/incidents", response_model=IncidentPage)
def incidents(
    run_id: str,
    session: Db,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    state: str | None = None,
    priority: str | None = None,
) -> IncidentPage:
    filters = [IncidentCandidateRecord.simulation_run_id == run_id]
    if state:
        filters.append(IncidentCandidateRecord.correlation_state == state)
    if priority:
        filters.append(IncidentCandidateRecord.priority == priority)
    total = int(
        session.scalar(select(func.count()).select_from(IncidentCandidateRecord).where(*filters))
        or 0
    )
    rows = list(
        session.scalars(
            select(IncidentCandidateRecord)
            .where(*filters)
            .order_by(IncidentCandidateRecord.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return IncidentPage(
        items=[correlation_service.candidate_schema(item) for item in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=ceil_pages(total, page_size),
    )


@router.get("/incidents/{candidate_id}", response_model=IncidentCandidate)
def incident(candidate_id: str, session: Db) -> IncidentCandidate:
    record = session.get(IncidentCandidateRecord, candidate_id)
    if record is None:
        raise ApplicationError(
            "INCIDENT_CANDIDATE_NOT_FOUND", "The incident candidate was not found.", 404
        )
    return correlation_service.candidate_schema(record)


@router.get("/incidents/{candidate_id}/evidence", response_model=list[IncidentEvidence])
def evidence(candidate_id: str, session: Db) -> list[IncidentEvidence]:
    rows = session.scalars(
        select(IncidentEvidenceRecord)
        .where(IncidentEvidenceRecord.incident_candidate_id == candidate_id)
        .order_by(IncidentEvidenceRecord.sequence_number)
    )
    return [
        IncidentEvidence(
            evidence_id=item.evidence_id,
            incident_candidate_id=item.incident_candidate_id,
            event_id=item.event_id,
            assessment_id=item.assessment_id,
            technique_mapping_id=item.technique_mapping_id,
            sequence_number=item.sequence_number,
            evidence_type=item.evidence_type,
            contribution_score=item.contribution_score,
            rationale=item.rationale,
            synthetic=True,
        )
        for item in rows
    ]


@router.get("/runs/{run_id}/techniques", response_model=TechniqueObservationPage)
def techniques(
    run_id: str,
    session: Db,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TechniqueObservationPage:
    total = int(
        session.scalar(
            select(func.count())
            .select_from(TechniqueObservationRecord)
            .where(TechniqueObservationRecord.simulation_run_id == run_id)
        )
        or 0
    )
    rows = list(
        session.scalars(
            select(TechniqueObservationRecord)
            .where(TechniqueObservationRecord.simulation_run_id == run_id)
            .order_by(TechniqueObservationRecord.sequence_number)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return TechniqueObservationPage(
        items=[observation_schema(item) for item in rows],
        page=page,
        page_size=page_size,
        total=total,
        pages=ceil_pages(total, page_size),
    )


def observation_schema(item: TechniqueObservationRecord) -> TechniqueObservation:
    return TechniqueObservation(
        mapping_id=item.mapping_id,
        technique_id=item.technique_id,
        technique_name=item.technique_name,
        simulation_run_id=item.simulation_run_id,
        model_id=item.model_id,
        event_id=item.event_id,
        sequence_number=item.sequence_number,
        mapping_confidence=item.mapping_confidence,
        evidence_fields=item.evidence_fields_json,
        rationale=item.rationale,
        tactic=item.tactic,
        mapper_version=item.mapper_version,
        synthetic=True,
    )


def ceil_pages(total: int, size: int) -> int:
    return (total + size - 1) // size
