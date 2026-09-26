from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.database.models import AuditEventRecord
from tests.test_response import prepare_response


def prepared(client: TestClient) -> tuple[str, str, dict[str, Any]]:
    run_id, model_id = prepare_response(client)
    analysis = client.post(
        f"/api/v1/response/runs/{run_id}/analyze",
        json={"model_id": model_id, "through_sequence_number": 10, "top_k": 10},
    ).json()
    recommendation = next(
        item
        for item in analysis["recommendations"]
        if item["required_approval_tier"] == "analyst_approval"
    )
    return run_id, model_id, recommendation


def create(client: TestClient) -> dict[str, Any]:
    run_id, model_id, recommendation = prepared(client)
    return cast(
        "dict[str, Any]",
        client.post(
            f"/api/v1/orchestration/runs/{run_id}/create",
            json={
                "model_id": model_id,
                "incident_candidate_id": recommendation["incident_candidate_id"],
                "selected_recommendation_id": recommendation["recommendation_id"],
                "through_sequence_number": 10,
            },
        ).json(),
    )


def approve(client: TestClient, orchestration: dict[str, Any]) -> dict[str, Any]:
    approval = orchestration["approvals"][0]
    return cast(
        "dict[str, Any]",
        client.post(
            f"/api/v1/orchestration/{orchestration['orchestration_id']}/approvals/"
            f"{approval['approval_request_id']}/decide",
            json={
                "actor_role": "analyst",
                "actor_display_name": "Demo SOC Analyst",
                "decision": "approve",
                "reason": "Approved for simulation demonstration only.",
            },
        ).json(),
    )


def test_deterministic_agents_approval_execution_verification_and_rollback(
    client: TestClient,
) -> None:
    first = create(client)
    repeated = create(client)
    assert repeated["orchestration_id"] == first["orchestration_id"]
    assert first["current_state"] == "awaiting_analyst_approval"
    assert [item["agent_name"] for item in first["decisions"]] == [
        "Response Planner Simulation Agent",
        "Impact Simulation Agent",
        "Safety Governor Agent",
        "Approval Router Agent",
    ]
    approved = approve(client, first)
    assert approved["current_state"] == "approved"
    executed = client.post(
        f"/api/v1/orchestration/{first['orchestration_id']}/execute", json={}
    ).json()
    assert executed["current_state"] == "synthetic_execution_completed"
    assert executed["executions"][0]["execution_state"] == "completed_simulated"
    assert (
        client.post(f"/api/v1/orchestration/{first['orchestration_id']}/execute", json={}).json()[
            "executions"
        ][0]["execution_id"]
        == executed["executions"][0]["execution_id"]
    )
    verified = client.post(f"/api/v1/orchestration/{first['orchestration_id']}/verify").json()
    assert verified["verifications"][0]["verification_status"] == "successful_simulation"
    rolled_back = client.post(
        f"/api/v1/orchestration/{first['orchestration_id']}/rollback",
        json={"reason": "Restore the demonstration baseline.", "requested_by": "Demo SOC Analyst"},
    ).json()
    assert rolled_back["current_state"] == "synthetic_rollback_completed"
    assert rolled_back["executions"][0]["execution_state"] == "rolled_back_simulated"
    assert (
        client.get(f"/api/v1/orchestration/{first['orchestration_id']}/audit/verify").json()[
            "valid"
        ]
        is True
    )


def test_approval_roles_rejection_and_conflicts(client: TestClient) -> None:
    orchestration = create(client)
    approval = orchestration["approvals"][0]
    # An administrator may satisfy an analyst-level gate; the inverse is tested by policy code.
    rejected = client.post(
        f"/api/v1/orchestration/{orchestration['orchestration_id']}/approvals/"
        f"{approval['approval_request_id']}/decide",
        json={
            "actor_role": "analyst",
            "actor_display_name": "Demo SOC Analyst",
            "decision": "reject",
            "reason": "Demonstration rejection.",
        },
    )
    assert rejected.status_code == 200
    assert (
        client.post(
            f"/api/v1/orchestration/{orchestration['orchestration_id']}/execute", json={}
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/api/v1/orchestration/{orchestration['orchestration_id']}/approvals/"
            f"{approval['approval_request_id']}/decide",
            json={
                "actor_role": "analyst",
                "actor_display_name": "Demo SOC Analyst",
                "decision": "approve",
                "reason": "Contradictory decision.",
            },
        ).status_code
        == 409
    )


def test_deterministic_failure_and_base_topology_immutability(client: TestClient) -> None:
    orchestration = approve(client, create(client))
    before = client.get("/api/v1/topology", params={"include_synthetic_sink": True}).json()
    failed = client.post(
        f"/api/v1/orchestration/{orchestration['orchestration_id']}/execute",
        json={"failure_mode": "injected_simulator_failure"},
    ).json()
    after = client.get("/api/v1/topology", params={"include_synthetic_sink": True}).json()
    assert failed["current_state"] == "synthetic_execution_failed"
    assert failed["executions"][0]["simulated_failure_reason"] == "injected_simulator_failure"
    assert before["nodes"] == after["nodes"]
    assert before["edges"] == after["edges"]


def test_audit_tampering_is_detected_and_sources_have_no_execution_integrations(
    client: TestClient,
) -> None:
    orchestration = create(client)
    oid = orchestration["orchestration_id"]
    sessions = cast(FastAPI, client.app).state.database.session()
    session = next(sessions)
    try:
        session.execute(
            update(AuditEventRecord)
            .where(AuditEventRecord.orchestration_id == oid, AuditEventRecord.sequence_number == 1)
            .values(event_hash="f" * 64)
        )
        session.commit()
    finally:
        sessions.close()
    integrity = client.get(f"/api/v1/orchestration/{oid}/audit/verify").json()
    assert integrity["valid"] is False
    assert integrity["first_invalid_sequence"] == 1
    source = " ".join(
        Path(path).read_text(encoding="utf-8").lower()
        for path in [
            "app/services/orchestration_service.py",
            "app/services/orchestration_agents.py",
        ]
    )
    assert not any(term in source for term in ["subprocess", "os.system", "requests.", "socket."])
    assert "threat eliminated" not in source and "breach contained" not in source
