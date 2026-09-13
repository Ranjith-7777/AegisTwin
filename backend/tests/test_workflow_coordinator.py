from typing import Any, cast

from fastapi.testclient import TestClient

from tests.test_blue_planning import prepare


def run_workflow(
    client: TestClient, run_id: str, model_id: str, candidate_id: str, sequence: int = 10
) -> dict[str, Any]:
    return cast(
        "dict[str, Any]",
        client.post(
            f"/api/v1/workflow/runs/{run_id}/execute",
            json={
                "model_id": model_id,
                "incident_candidate_id": candidate_id,
                "through_sequence_number": sequence,
                "top_k": 5,
            },
        ).json(),
    )


def test_recommend_mode_stops_before_any_orchestration_is_created(client: TestClient) -> None:
    run_id, model_id, candidate_id = prepare(client)
    result = run_workflow(client, run_id, model_id, candidate_id)
    assert result["autonomy_mode"] == "recommend"
    assert result["orchestration"] is None
    assert result["auto_executed"] is False
    assert len(result["comparison"]["candidates"]) > 0


def test_approval_required_mode_creates_but_never_auto_executes(client: TestClient) -> None:
    run_id, model_id, candidate_id = prepare(client)
    client.put(
        "/api/v1/autonomy",
        json={"mode": "approval_required", "updated_by": "analyst-1", "confirm": False},
    )
    result = run_workflow(client, run_id, model_id, candidate_id)
    assert result["autonomy_mode"] == "approval_required"
    assert result["orchestration"] is not None
    assert result["orchestration"]["current_state"] in {
        "awaiting_analyst_approval",
        "awaiting_administrator_approval",
    }
    assert result["auto_executed"] is False

    approval = result["orchestration"]["approvals"][0]
    approved = client.post(
        f"/api/v1/orchestration/{result['orchestration']['orchestration_id']}/approvals/"
        f"{approval['approval_request_id']}/decide",
        json={
            "actor_role": approval["required_role"],
            "actor_display_name": "Demo SOC Analyst",
            "decision": "approve",
            "reason": "Approved for simulation demonstration only.",
        },
    ).json()
    assert approved["current_state"] == "approved"
    executed = client.post(
        f"/api/v1/orchestration/{result['orchestration']['orchestration_id']}/execute", json={}
    ).json()
    assert executed["current_state"] == "synthetic_execution_completed"


def test_autonomous_mode_still_requires_approval_for_real_containment(client: TestClient) -> None:
    """AUTONOMOUS never means "execute everything": the highest-ranked
    candidate here has real security value and an analyst_approval tier, so
    even in AUTONOMOUS mode a human decision is still required."""

    run_id, model_id, candidate_id = prepare(client)
    client.put(
        "/api/v1/autonomy",
        json={"mode": "autonomous", "updated_by": "prof-demo", "confirm": True},
    )
    result = run_workflow(client, run_id, model_id, candidate_id)
    assert result["autonomy_mode"] == "autonomous"
    assert result["auto_executed"] is False
    assert result["orchestration"]["current_state"] == "awaiting_analyst_approval"


def test_observe_mode_never_generates_or_executes_a_plan(client: TestClient) -> None:
    run_id, model_id, candidate_id = prepare(client)
    client.put(
        "/api/v1/autonomy",
        json={"mode": "observe", "updated_by": "analyst-1", "confirm": False},
    )
    result = run_workflow(client, run_id, model_id, candidate_id)
    assert result["autonomy_mode"] == "observe"
    assert result["orchestration"] is None
    assert result["auto_executed"] is False


def test_autonomous_self_healing_for_the_one_automation_eligible_playbook(
    client: TestClient,
) -> None:
    """The genuine self-healing demo: for the one playbook the catalogue and
    policy engine jointly permit to run without a human
    (increase-synthetic-monitoring - reversible, low impact, single-asset,
    automatic_candidate), the real agent pipeline creates, auto-approves,
    executes and verifies the response with zero human intervention."""

    run_id, model_id, candidate_id = prepare(client)
    client.put(
        "/api/v1/autonomy",
        json={"mode": "autonomous", "updated_by": "prof-demo", "confirm": True},
    )
    analysis = client.post(
        f"/api/v1/response/runs/{run_id}/analyze",
        json={"model_id": model_id, "through_sequence_number": 10, "top_k": 10},
    ).json()
    monitoring = next(
        item
        for item in analysis["recommendations"]
        if item["playbook_id"] == "increase-synthetic-monitoring"
    )
    orchestration = client.post(
        f"/api/v1/orchestration/runs/{run_id}/create",
        json={
            "model_id": model_id,
            "incident_candidate_id": candidate_id,
            "selected_recommendation_id": monitoring["recommendation_id"],
            "through_sequence_number": 10,
        },
    ).json()
    assert orchestration["current_state"] == "approved"
    assert orchestration["decisions"][-1]["agent_name"] == "Approval Router Agent"
    assert orchestration["decisions"][-1]["decision"] == "automatic"

    executed = client.post(
        f"/api/v1/orchestration/{orchestration['orchestration_id']}/execute", json={}
    ).json()
    assert executed["current_state"] == "synthetic_execution_completed"

    verified = client.post(
        f"/api/v1/orchestration/{orchestration['orchestration_id']}/verify"
    ).json()
    assert verified["current_state"] == "verified"
    assert verified["verifications"][0]["verification_status"] == "successful_simulation"
