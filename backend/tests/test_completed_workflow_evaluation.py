"""Regression coverage for evidence-bound completed-workflow evaluation."""

from __future__ import annotations

from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import (
    ExperimentRecord,
    ResponseOrchestrationRecord,
    ResponseRecommendationRecord,
    ResponseVerificationRecord,
    SimulationRunRecord,
)
from tests.test_blue_planning import prepare


def _session(client: TestClient) -> Session:
    return cast(Session, cast(FastAPI, client.app).state.database.session_factory())


def _run_workflow(
    client: TestClient, run_id: str, model_id: str, incident_id: str
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/workflow/runs/{run_id}/execute",
        json={
            "model_id": model_id,
            "incident_candidate_id": incident_id,
            "through_sequence_number": 10,
            "top_k": 5,
        },
    )
    assert response.status_code == 200, response.text
    return cast("dict[str, Any]", response.json())


def _completed(client: TestClient) -> tuple[str, str]:
    run_id, model_id, incident_id = prepare(client)
    client.put(
        "/api/v1/autonomy",
        json={"mode": "autonomous", "updated_by": "phase-4-test", "confirm": True},
    )
    result = _run_workflow(client, run_id, model_id, incident_id)
    orchestration = result["orchestration"]
    assert orchestration["current_state"] == "verified"
    return run_id, cast(str, orchestration["orchestration_id"])


def _approval_workflow(client: TestClient) -> tuple[str, dict[str, Any]]:
    run_id, model_id, incident_id = prepare(client)
    client.put(
        "/api/v1/autonomy",
        json={"mode": "approval_required", "updated_by": "phase-4-test", "confirm": False},
    )
    result = _run_workflow(client, run_id, model_id, incident_id)
    orchestration = cast("dict[str, Any]", result["orchestration"])
    return run_id, orchestration


def _approve(client: TestClient, orchestration: dict[str, Any]) -> str:
    orchestration_id = cast(str, orchestration["orchestration_id"])
    approval = cast("dict[str, Any]", orchestration["approvals"][0])
    response = client.post(
        f"/api/v1/orchestration/{orchestration_id}/approvals/"
        f"{approval['approval_request_id']}/decide",
        json={
            "actor_role": approval["required_role"],
            "actor_display_name": "Phase 4 Test Operator",
            "decision": "approve",
            "reason": "Approved for isolated synthetic evaluation testing.",
        },
    )
    assert response.status_code == 200, response.text
    return orchestration_id


def test_completed_run_evaluation_reuses_original_run_and_produces_report(
    client: TestClient,
) -> None:
    run_id, orchestration_id = _completed(client)
    session = _session(client)
    try:
        run_count_before = session.scalar(select(func.count(SimulationRunRecord.simulation_run_id)))
    finally:
        session.close()

    response = client.post(f"/api/v1/evaluation/workflows/{orchestration_id}/evaluate")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["evaluation_source"] == "completed_workflow"
    assert body["run_id"] == run_id
    assert body["orchestration_id"] == orchestration_id
    assert body["incident_candidate_id"]
    assert body["metrics"] is not None
    assert body["configuration_json"]["measurement_note"].endswith("no attack replay.")

    session = _session(client)
    try:
        assert (
            session.scalar(select(func.count(SimulationRunRecord.simulation_run_id)))
            == run_count_before
        )
    finally:
        session.close()

    report = client.get(f"/api/v1/evaluation/experiments/{body['experiment_id']}/report").json()
    assert "without replaying the attack" in report["executive_summary"]
    assert report["reproduction"]["evaluation_source"] == "completed_workflow"
    assert report["paired_baseline_comparison"] is None
    assert report["response_verification_rollback_summary"]["orchestration_id"] == orchestration_id
    assert body["experiment_id"] not in {
        item["experiment_id"] for item in client.get("/api/v1/evaluation/experiments").json()
    }
    rerun = client.post(f"/api/v1/evaluation/experiments/{body['experiment_id']}/rerun")
    assert rerun.status_code == 409
    assert rerun.json()["error_code"] == "WORKFLOW_EVALUATION_CANNOT_RERUN"


def test_repeat_completed_run_evaluation_is_idempotent(client: TestClient) -> None:
    _run_id, orchestration_id = _completed(client)
    first = client.post(f"/api/v1/evaluation/workflows/{orchestration_id}/evaluate")
    second = client.post(f"/api/v1/evaluation/workflows/{orchestration_id}/evaluate")
    assert first.status_code == second.status_code == 200
    assert first.json()["experiment_id"] == second.json()["experiment_id"]

    session = _session(client)
    try:
        count = session.scalar(
            select(func.count(ExperimentRecord.experiment_id)).where(
                ExperimentRecord.orchestration_id == orchestration_id,
                ExperimentRecord.evaluation_source == "completed_workflow",
            )
        )
        assert count == 1
    finally:
        session.close()


def test_incomplete_workflow_is_rejected(client: TestClient) -> None:
    _run_id, pending = _approval_workflow(client)
    pending_id = cast(str, pending["orchestration_id"])
    response = client.post(f"/api/v1/evaluation/workflows/{pending_id}/evaluate")
    assert response.status_code == 409
    assert response.json()["error_code"] == "WORKFLOW_EVALUATION_NOT_READY"


def test_missing_verification_evidence_is_rejected(client: TestClient) -> None:
    _run_id, completed_id = _completed(client)
    session = _session(client)
    try:
        verification = session.scalar(
            select(ResponseVerificationRecord).where(
                ResponseVerificationRecord.orchestration_id == completed_id
            )
        )
        assert verification is not None
        session.delete(verification)
        session.commit()
    finally:
        session.close()
    response = client.post(f"/api/v1/evaluation/workflows/{completed_id}/evaluate")
    assert response.status_code == 409
    assert response.json()["error_code"] == "WORKFLOW_EVIDENCE_INCOMPLETE"


def test_incorrect_run_orchestration_association_is_rejected(client: TestClient) -> None:
    _run_id, orchestration_id = _completed(client)
    session = _session(client)
    try:
        orchestration = session.get(ResponseOrchestrationRecord, orchestration_id)
        assert orchestration is not None
        record = session.get(ResponseRecommendationRecord, orchestration.selected_recommendation_id)
        assert record is not None
        record.simulation_run_id = "mismatched-run"
        session.commit()
    finally:
        session.close()

    response = client.post(f"/api/v1/evaluation/workflows/{orchestration_id}/evaluate")
    assert response.status_code == 409
    assert response.json()["error_code"] == "WORKFLOW_EVIDENCE_MISMATCH"


def test_failed_execution_is_evaluated_with_verification_unavailable(client: TestClient) -> None:
    run_id, orchestration = _approval_workflow(client)
    orchestration_id = _approve(client, orchestration)
    failed = client.post(
        f"/api/v1/orchestration/{orchestration_id}/execute",
        json={"failure_mode": "injected_simulator_failure"},
    )
    assert failed.status_code == 200
    assert failed.json()["current_state"] == "synthetic_execution_failed"

    response = client.post(f"/api/v1/evaluation/workflows/{orchestration_id}/evaluate")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["run_id"] == run_id
    assert body["configuration_json"]["workflow_terminal_state"] == "synthetic_execution_failed"
    assert body["metrics"]["raw_metrics"]["verification_success"] is None
    assert body["metrics"]["raw_metrics"]["rollback_success"] is None


def test_rolled_back_workflow_report_uses_persisted_rollback_evidence(
    client: TestClient,
) -> None:
    _run_id, orchestration_id = _completed(client)
    rollback = client.post(
        f"/api/v1/orchestration/{orchestration_id}/rollback",
        json={
            "reason": "Restore the synthetic pre-execution state for evaluation.",
            "requested_by": "Phase 4 Test Operator",
        },
    )
    assert rollback.status_code == 200, rollback.text
    assert rollback.json()["current_state"] == "synthetic_rollback_completed"

    response = client.post(f"/api/v1/evaluation/workflows/{orchestration_id}/evaluate")
    assert response.status_code == 200, response.text
    body = response.json()
    raw = body["metrics"]["raw_metrics"]
    assert raw["rollback_required"] is False
    assert raw["rollback_success"] is True
    assert body["configuration_json"]["source_evidence"]["rollback_id"]
    rollback_stage = next(
        event for event in body["timeline"]["events"] if event["stage"] == "rollback"
    )
    assert rollback_stage["status"] == "occurred"
