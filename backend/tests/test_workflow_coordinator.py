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


def test_autonomous_mode_still_requires_approval_for_an_analyst_tier_candidate(
    client: TestClient,
) -> None:
    """AUTONOMOUS never means "execute everything": even though
    `block-synthetic-route` has real, evidenced security value, its
    catalogue tier is `analyst_approval` (not `automatic_candidate`), so
    creating an orchestration for it directly - regardless of how it ranks
    against other candidates - must still require a human decision in
    AUTONOMOUS mode."""

    run_id, model_id, candidate_id = prepare(client)
    client.put(
        "/api/v1/autonomy",
        json={"mode": "autonomous", "updated_by": "prof-demo", "confirm": True},
    )
    analysis = client.post(
        f"/api/v1/response/runs/{run_id}/analyze",
        json={"model_id": model_id, "through_sequence_number": 10, "top_k": 10},
    ).json()
    block_route = next(
        item
        for item in analysis["recommendations"]
        if item["playbook_id"] == "block-synthetic-route"
    )
    orchestration = client.post(
        f"/api/v1/orchestration/runs/{run_id}/create",
        json={
            "model_id": model_id,
            "incident_candidate_id": candidate_id,
            "selected_recommendation_id": block_route["recommendation_id"],
            "through_sequence_number": 10,
        },
    ).json()
    assert orchestration["current_state"] == "awaiting_analyst_approval"
    assert orchestration["decisions"][-1]["decision"] == "requires_analyst"


def test_observe_mode_never_generates_or_executes_a_plan(client: TestClient) -> None:
    """OBSERVE means detection/evidence only. The Coordinator must stop
    BEFORE blue_planning_service.compare() ever runs - no candidate plan is
    generated, ranked, or persisted, and no ResponsePlanAssessmentRecord is
    written for this identity."""

    from app.services.blue_planning_service import blue_planning_service

    run_id, model_id, candidate_id = prepare(client)
    client.put(
        "/api/v1/autonomy",
        json={"mode": "observe", "updated_by": "analyst-1", "confirm": False},
    )
    result = run_workflow(client, run_id, model_id, candidate_id)
    assert result["autonomy_mode"] == "observe"
    assert result["orchestration"] is None
    assert result["auto_executed"] is False
    assert result["comparison"] is None

    assessment_id = blue_planning_service.assessment_id(run_id, model_id, candidate_id, 10)
    assert client.get(f"/api/v1/blue-planning/assessments/{assessment_id}").status_code == 404


def test_autonomous_self_healing_performs_real_containment_end_to_end(
    client: TestClient,
) -> None:
    """The genuine autonomous self-healing loop, driven entirely by
    `WorkflowCoordinator.run()` with NO manual recommendation selection:
    `quarantine-synthetic-ingress-edge` - a real edge_restriction playbook
    that removes the attacker's evidenced ingress relationship, not a mere
    observation - is the highest-ranked, policy-eligible candidate, so the
    Coordinator creates, auto-approves, executes and independently verifies
    it with zero human approval records. `increase-synthetic-monitoring`
    (observe-only) is deliberately NOT the selected plan here: it has no
    containment effect and must never be mislabeled "self-healing"."""

    run_id, model_id, candidate_id = prepare(client)
    client.put(
        "/api/v1/autonomy",
        json={"mode": "autonomous", "updated_by": "prof-demo", "confirm": True},
    )
    result = run_workflow(client, run_id, model_id, candidate_id)

    assert result["autonomy_mode"] == "autonomous"
    assert result["auto_executed"] is True
    assert result["auto_verified"] is True

    recommended = result["comparison"]["recommended_recommendation_id"]
    top_candidate = next(
        c for c in result["comparison"]["candidates"] if c["recommendation_id"] == recommended
    )
    assert top_candidate["playbook_id"] == "quarantine-synthetic-ingress-edge"
    assert top_candidate["action_type"] == "edge_restriction"
    assert top_candidate["security_gain_evidence"]["security_gain"] > 0.0
    assert (
        top_candidate["security_gain_evidence"]["attack_paths_after"]
        < top_candidate["security_gain_evidence"]["attack_paths_before"]
    )

    orchestration = result["orchestration"]
    assert orchestration["selected_recommendation_id"] == recommended
    assert orchestration["current_state"] == "verified"
    assert orchestration["approvals"] == []  # zero human approval records
    assert [d["agent_name"] for d in orchestration["decisions"]] == [
        "Response Planner Simulation Agent",
        "Impact Simulation Agent",
        "Safety Governor Agent",
        "Approval Router Agent",
        "Synthetic Execution Agent",
        "Verification Agent",
    ]
    assert orchestration["decisions"][2]["decision"] == "automatic_approved"
    assert orchestration["decisions"][3]["decision"] == "automatic"

    verification = orchestration["verifications"][0]
    assert verification["verification_status"] == "successful_simulation"
    metrics = verification["metrics"]
    assert metrics["security_effect_confirmed"] is True
    assert metrics["operational_health_ok"] is True
    assert (
        metrics["actual_attack_paths_after"]
        < top_candidate["security_gain_evidence"]["attack_paths_before"]
    )
    assert metrics["actual_critical_targets_after"] <= metrics["expected_critical_targets_after"]
