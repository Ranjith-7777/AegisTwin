from typing import Any, cast

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database.models import AuditEventRecord, SyntheticExecutionRecord
from app.schemas.blue_planning import SecurityGainEvidence
from app.services.orchestration_agents import (
    OPERATIONAL_DISRUPTION_THRESHOLD,
    verification_agent,
)
from app.services.topology_service import topology_service
from tests.test_orchestration import approve, create


def _evidence(**overrides: float) -> SecurityGainEvidence:
    base: dict[str, float] = {
        "attack_paths_before": 2,
        "attack_paths_after": 2,
        "top_attack_path_score_before": 50.0,
        "top_attack_path_score_after": 50.0,
        "critical_targets_reachable_before": 1,
        "critical_targets_reachable_after": 1,
        "blast_radius_reachable_before": 5,
        "blast_radius_reachable_after": 5,
        "blast_radius_critical_before": 1,
        "blast_radius_critical_after": 1,
        "security_gain": 0.0,
    }
    base.update(overrides)
    return SecurityGainEvidence.model_validate(base)


def test_verification_never_treats_a_mutation_existing_alone_as_success() -> None:
    """Regression guard for the pre-Phase-4 flaw: a real mutation occurred
    (changed_edges is non-empty) but the ACTUAL post-execution recomputation
    shows no security improvement over the before-state - overall status
    must be failure even though a mutation genuinely happened."""

    expected = _evidence(attack_paths_after=1)  # the plan promised containment...
    actual = _evidence(attack_paths_after=2)  # ...but the real executed state shows none.
    status, metrics = verification_agent.verify(
        changed_nodes=[],
        changed_edges=["some-edge"],
        expected_edges=1,
        expected_evidence=expected,
        actual_evidence=actual,
        bystander_isolated_asset_ids=[],
    )
    assert status == "unsuccessful_simulation"
    assert metrics["intended_mutations_applied"] is True
    assert metrics["security_effect_confirmed"] is False
    assert metrics["expected_attack_paths_after"] == 1
    assert metrics["actual_attack_paths_after"] == 2


def test_verification_fails_when_bystander_asset_is_unintentionally_isolated() -> None:
    """Real operational-health check: even a genuinely-effective containment
    action must fail verification if it accidentally fully disconnected an
    asset that was never the intended target."""

    expected = _evidence(attack_paths_after=1)
    actual = _evidence(attack_paths_after=1)
    status, metrics = verification_agent.verify(
        changed_nodes=[],
        changed_edges=["some-edge"],
        expected_edges=1,
        expected_evidence=expected,
        actual_evidence=actual,
        bystander_isolated_asset_ids=["unrelated-bystander-asset"],
    )
    assert status == "unsuccessful_simulation"
    assert metrics["security_effect_confirmed"] is True
    assert metrics["operational_health_ok"] is False
    assert metrics["critical_connectivity_preserved"] is False
    assert metrics["bystander_isolated_asset_ids"] == ["unrelated-bystander-asset"]


def test_verification_fails_when_disruption_ratio_exceeds_threshold() -> None:
    total_edges = len(topology_service.edges(True))
    excessive_changed_edges = [f"synthetic-edge-{i}" for i in range(total_edges)]
    expected = _evidence(attack_paths_after=1)
    actual = _evidence(attack_paths_after=1)
    status, metrics = verification_agent.verify(
        changed_nodes=[],
        changed_edges=excessive_changed_edges,
        expected_edges=1,
        expected_evidence=expected,
        actual_evidence=actual,
        bystander_isolated_asset_ids=[],
    )
    assert status == "unsuccessful_simulation"
    assert cast("float", metrics["operational_disruption_score"]) > OPERATIONAL_DISRUPTION_THRESHOLD
    assert metrics["operational_health_ok"] is False


def test_verification_succeeds_only_when_both_checks_pass() -> None:
    expected = _evidence(attack_paths_after=1)
    actual = _evidence(attack_paths_after=1)
    status, metrics = verification_agent.verify(
        changed_nodes=[],
        changed_edges=["some-edge"],
        expected_edges=1,
        expected_evidence=expected,
        actual_evidence=actual,
        bystander_isolated_asset_ids=[],
    )
    assert status == "successful_simulation"
    assert metrics["security_effect_confirmed"] is True
    assert metrics["operational_health_ok"] is True


def test_a_playbook_making_no_security_claim_is_not_penalized_for_having_none() -> None:
    """An observe-only playbook (expected_edges == 0) never claimed a
    security effect, so it must not be failed for lacking one."""

    expected = _evidence()
    actual = _evidence()
    status, metrics = verification_agent.verify(
        changed_nodes=["some-node"],
        changed_edges=[],
        expected_edges=0,
        expected_evidence=expected,
        actual_evidence=actual,
        bystander_isolated_asset_ids=[],
    )
    assert status == "successful_simulation"
    assert metrics["security_effect_confirmed"] is True


# --- Objective semantics: IMPROVED vs VERIFIED AGAINST EXPECTED OBJECTIVE ---
# (PM micro-correction #2 - a mutation that merely improved over the
# before-state is not enough; the plan's own EXPECTED containment objective
# must actually be met for every metric the plan claimed it would improve.)


def test_A_partial_containment_below_expected_objective_fails() -> None:
    """before=2, expected=0, actual=1: a real improvement over before (2->1)
    but the planned containment objective (eliminate all paths) was NOT met
    - this must FAIL, not pass merely because it "improved"."""

    expected = _evidence(attack_paths_before=2, attack_paths_after=0)
    actual = _evidence(attack_paths_before=2, attack_paths_after=1)
    status, metrics = verification_agent.verify(
        changed_nodes=[],
        changed_edges=["some-edge"],
        expected_edges=1,
        expected_evidence=expected,
        actual_evidence=actual,
        bystander_isolated_asset_ids=[],
    )
    assert status == "unsuccessful_simulation"
    assert metrics["security_improved"] is True  # 1 < 2, a real improvement...
    assert metrics["attack_path_objective_met"] is False  # ...but 1 > 0, objective missed.
    assert metrics["expected_containment_met"] is False
    assert metrics["security_effect_confirmed"] is False


def test_B_actual_meets_expected_objective_exactly_succeeds() -> None:
    """before=2, expected=1, actual=1: actual meets (does not exceed) the
    expected objective exactly - succeeds if operational health passes."""

    expected = _evidence(attack_paths_before=2, attack_paths_after=1)
    actual = _evidence(attack_paths_before=2, attack_paths_after=1)
    status, metrics = verification_agent.verify(
        changed_nodes=[],
        changed_edges=["some-edge"],
        expected_edges=1,
        expected_evidence=expected,
        actual_evidence=actual,
        bystander_isolated_asset_ids=[],
    )
    assert metrics["attack_path_objective_met"] is True
    assert metrics["expected_containment_met"] is True
    assert metrics["security_effect_confirmed"] is True
    assert status == "successful_simulation"


def test_C_actual_outperforms_expected_objective_succeeds() -> None:
    """The actual executed result is BETTER than what was expected/simulated
    - this must succeed, not be penalized for "not matching the prediction
    exactly"."""

    expected = _evidence(attack_paths_before=2, attack_paths_after=1)
    actual = _evidence(attack_paths_before=2, attack_paths_after=0)
    status, metrics = verification_agent.verify(
        changed_nodes=[],
        changed_edges=["some-edge"],
        expected_edges=1,
        expected_evidence=expected,
        actual_evidence=actual,
        bystander_isolated_asset_ids=[],
    )
    assert metrics["attack_path_objective_met"] is True
    assert metrics["security_effect_confirmed"] is True
    assert status == "successful_simulation"


def test_D_blast_radius_objective_underperforming_expected_fails() -> None:
    """The plan claimed a blast-radius reduction (8 -> 6) but the actual
    executed result only reached 7 - the blast-radius objective was part of
    the planned improvement and was not met, so verification must fail even
    though attack paths met their own objective."""

    expected = _evidence(
        attack_paths_before=2,
        attack_paths_after=1,
        blast_radius_reachable_before=8,
        blast_radius_reachable_after=6,
    )
    actual = _evidence(
        attack_paths_before=2,
        attack_paths_after=1,
        blast_radius_reachable_before=8,
        blast_radius_reachable_after=7,
    )
    status, metrics = verification_agent.verify(
        changed_nodes=[],
        changed_edges=["some-edge"],
        expected_edges=1,
        expected_evidence=expected,
        actual_evidence=actual,
        bystander_isolated_asset_ids=[],
    )
    assert metrics["attack_path_objective_met"] is True
    assert metrics["blast_radius_objective_applicable"] is True
    assert metrics["blast_radius_objective_met"] is False
    assert metrics["expected_containment_met"] is False
    assert metrics["security_effect_confirmed"] is False
    assert status == "unsuccessful_simulation"


def test_E_critical_target_objective_underperforming_expected_fails() -> None:
    """The plan claimed a critical target would become unreachable (1 -> 0)
    but the actual result still leaves it reachable (1 -> 1) - must fail."""

    expected = _evidence(
        attack_paths_before=2,
        attack_paths_after=1,
        critical_targets_reachable_before=1,
        critical_targets_reachable_after=0,
    )
    actual = _evidence(
        attack_paths_before=2,
        attack_paths_after=1,
        critical_targets_reachable_before=1,
        critical_targets_reachable_after=1,
    )
    status, metrics = verification_agent.verify(
        changed_nodes=[],
        changed_edges=["some-edge"],
        expected_edges=1,
        expected_evidence=expected,
        actual_evidence=actual,
        bystander_isolated_asset_ids=[],
    )
    assert metrics["critical_target_objective_applicable"] is True
    assert metrics["critical_target_objective_met"] is False
    assert metrics["expected_containment_met"] is False
    assert metrics["security_effect_confirmed"] is False
    assert status == "unsuccessful_simulation"


def test_F_no_security_claim_is_unaffected_by_objective_semantics() -> None:
    """An observe-only action (expected_edges == 0) retains its documented
    vacuous-pass semantics regardless of the new objective checks - it is
    never falsely failed for lacking containment it never claimed."""

    expected = _evidence()
    actual = _evidence()
    status, metrics = verification_agent.verify(
        changed_nodes=["some-node"],
        changed_edges=[],
        expected_edges=0,
        expected_evidence=expected,
        actual_evidence=actual,
        bystander_isolated_asset_ids=[],
    )
    assert status == "successful_simulation"
    assert metrics["security_effect_confirmed"] is True
    # None of the three metrics claimed an improvement (before == after).
    assert metrics["attack_path_objective_applicable"] is False
    assert metrics["critical_target_objective_applicable"] is False
    assert metrics["blast_radius_objective_applicable"] is False
    assert metrics["expected_containment_met"] is True


def test_verification_persists_a_real_agent_decision_record(client: TestClient) -> None:
    """Gap-1 regression: Verification must persist a genuine AgentDecisionRecord
    via the same _decision() mechanism as the other 5 Blue agents, not just a
    verification row/audit event."""

    orchestration = approve(client, create(client))
    client.post(f"/api/v1/orchestration/{orchestration['orchestration_id']}/execute", json={})
    verified = client.post(
        f"/api/v1/orchestration/{orchestration['orchestration_id']}/verify"
    ).json()
    decisions = verified["decisions"]
    assert [d["agent_name"] for d in decisions] == [
        "Response Planner Simulation Agent",
        "Impact Simulation Agent",
        "Safety Governor Agent",
        "Approval Router Agent",
        "Synthetic Execution Agent",
        "Verification Agent",
    ]
    verification_decision = decisions[-1]
    assert verification_decision["decision_type"] == "verification"
    assert verification_decision["decision"] == "successful_simulation"
    assert verification_decision["next_agent"] is None
    assert verification_decision["input_reference_ids"]
    assert verification_decision["rationale"]


def test_failed_verification_automatically_triggers_rollback_for_a_reversible_action(
    client: TestClient,
) -> None:
    """Forces the real dual-check to fail by inflating the ACTUAL executed
    mutation's changed_edge_ids past the operational-disruption threshold,
    then confirms orchestration_service.verify() automatically calls
    rollback() via policy_service.evaluate_rollback_policy - a human never
    has to notice and manually roll back."""

    orchestration = approve(client, create(client))
    client.post(f"/api/v1/orchestration/{orchestration['orchestration_id']}/execute", json={})

    database = client.app.state.database  # type: ignore[attr-defined]
    session = database.session_factory()
    try:
        execution = session.scalar(
            select(SyntheticExecutionRecord).where(
                SyntheticExecutionRecord.orchestration_id == orchestration["orchestration_id"]
            )
        )
        assert execution is not None
        all_edges = [edge.edge_id for edge in topology_service.edges(True)]
        execution.changed_edge_ids_json = all_edges
        session.commit()
    finally:
        session.close()

    verified: dict[str, Any] = cast(
        "dict[str, Any]",
        client.post(f"/api/v1/orchestration/{orchestration['orchestration_id']}/verify").json(),
    )
    assert verified["verifications"][0]["verification_status"] == "unsuccessful_simulation"
    assert verified["current_state"] == "synthetic_rollback_completed"
    assert verified["rollback"] is not None
    assert verified["rollback"]["reason"].startswith("Automatic rollback:")

    database = client.app.state.database  # type: ignore[attr-defined]
    session = database.session_factory()
    try:
        rows = list(
            session.scalars(
                select(AuditEventRecord)
                .where(
                    AuditEventRecord.orchestration_id == orchestration["orchestration_id"],
                    AuditEventRecord.event_type == "synthetic_rollback_completed",
                )
                .order_by(AuditEventRecord.sequence_number.desc())
            )
        )
        assert rows, "expected a synthetic_rollback_completed audit event"
        rollback_audit = rows[0]
        assert rollback_audit.actor_type == "simulation_agent"
        assert rollback_audit.actor_id == "verification-agent"
        assert rollback_audit.canonical_payload_json["automatic"] is True
    finally:
        session.close()


def test_manual_rollback_still_attributes_to_the_human_actor(client: TestClient) -> None:
    orchestration = approve(client, create(client))
    client.post(f"/api/v1/orchestration/{orchestration['orchestration_id']}/execute", json={})
    client.post(f"/api/v1/orchestration/{orchestration['orchestration_id']}/verify")
    client.post(
        f"/api/v1/orchestration/{orchestration['orchestration_id']}/rollback",
        json={"reason": "Restore the demonstration baseline.", "requested_by": "Demo SOC Analyst"},
    )

    database = client.app.state.database  # type: ignore[attr-defined]
    session = database.session_factory()
    try:
        rows = list(
            session.scalars(
                select(AuditEventRecord)
                .where(
                    AuditEventRecord.orchestration_id == orchestration["orchestration_id"],
                    AuditEventRecord.event_type == "synthetic_rollback_completed",
                )
                .order_by(AuditEventRecord.sequence_number.desc())
            )
        )
        assert rows
        rollback_audit = rows[0]
        assert rollback_audit.actor_type == "human"
        assert rollback_audit.actor_id == "demo-operator"
        assert rollback_audit.canonical_payload_json["automatic"] is False
    finally:
        session.close()
