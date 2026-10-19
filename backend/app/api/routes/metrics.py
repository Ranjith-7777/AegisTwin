"""Prometheus-style exposition of the range's persisted state.

Every value is a count read from the database at scrape time (or process
uptime) - nothing is sampled, estimated or kept in memory. Response
latency per request is already in the structured request logs
(`HTTP request completed ... duration_ms=`).
"""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auth import RequireViewer
from app.database.models import (
    AnomalyAssessmentRecord,
    AuditEventRecord,
    ExperimentRecord,
    IncidentCandidateRecord,
    ResponseOrchestrationRecord,
    ResponseVerificationRecord,
    RollbackRecord,
    SimulationRunRecord,
    SyntheticExecutionRecord,
)
from app.database.session import get_database_session

router = APIRouter(tags=["observability"])
Db = Annotated[Session, Depends(get_database_session)]
_STARTED = time.monotonic()


def _count(session: Session, model: type, *conditions: object) -> int:
    statement = select(func.count()).select_from(model)
    for condition in conditions:
        statement = statement.where(condition)  # type: ignore[arg-type]
    return int(session.scalar(statement) or 0)


@router.get("/metrics", dependencies=[RequireViewer], include_in_schema=False)
def metrics(session: Db) -> Response:
    gauges: list[tuple[str, str, int | float, dict[str, str] | None]] = [
        ("aegisarena_up", "Backend process is serving requests.", 1, None),
        (
            "aegisarena_uptime_seconds",
            "Seconds since the backend process started.",
            round(time.monotonic() - _STARTED, 3),
            None,
        ),
        (
            "aegisarena_simulation_runs",
            "Persisted Red Agent simulation runs.",
            _count(session, SimulationRunRecord),
            None,
        ),
        (
            "aegisarena_anomaly_assessments",
            "Persisted anomaly assessments classified anomalous.",
            _count(
                session,
                AnomalyAssessmentRecord,
                AnomalyAssessmentRecord.classification == "anomalous",
            ),
            {"classification": "anomalous"},
        ),
        (
            "aegisarena_incident_candidates",
            "Correlated incident candidates.",
            _count(session, IncidentCandidateRecord),
            None,
        ),
        (
            "aegisarena_orchestrations",
            "Blue Agent response orchestrations.",
            _count(session, ResponseOrchestrationRecord),
            None,
        ),
        (
            "aegisarena_synthetic_executions",
            "Synthetic (twin-only) executions.",
            _count(session, SyntheticExecutionRecord),
            None,
        ),
        (
            "aegisarena_verifications_successful",
            "Verifications that met the expected containment objective.",
            _count(
                session,
                ResponseVerificationRecord,
                ResponseVerificationRecord.verification_status == "successful_simulation",
            ),
            None,
        ),
        ("aegisarena_rollbacks", "Synthetic rollbacks.", _count(session, RollbackRecord), None),
        (
            "aegisarena_audit_events",
            "Hash-chained audit events.",
            _count(session, AuditEventRecord),
            None,
        ),
        (
            "aegisarena_experiments_completed",
            "Completed evaluation experiments.",
            _count(session, ExperimentRecord, ExperimentRecord.status == "completed"),
            None,
        ),
    ]
    lines: list[str] = []
    for name, help_text, value, labels in gauges:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} gauge")
        label_text = (
            "{" + ",".join(f'{key}="{val}"' for key, val in labels.items()) + "}" if labels else ""
        )
        lines.append(f"{name}{label_text} {value}")
    return Response("\n".join(lines) + "\n", media_type="text/plain; version=0.0.4")
