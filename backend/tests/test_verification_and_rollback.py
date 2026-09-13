from typing import Any, cast

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database.models import ResponseImpactSimulationRecord
from app.services.orchestration_agents import (
    OPERATIONAL_DISRUPTION_THRESHOLD,
    verification_agent,
)
from tests.test_orchestration import approve, create


def test_verification_never_treats_a_mutation_existing_alone_as_success() -> None:
    """Regression guard for the pre-Phase-4 flaw: a real mutation occurred
    (changed_edges is non-empty) but neither the security effect nor the
    operational health check passed - overall status must be failure."""

    status, metrics = verification_agent.verify(
        changed_nodes=[],
        changed_edges=["some-edge"],
        expected_edges=1,
        sensitive_assets_reachable_before=3,
        sensitive_assets_reachable_after=3,
        correlated_paths_interrupted=0,
        operational_disruption_score=0.1,
    )
    assert status == "unsuccessful_simulation"
    assert metrics["intended_mutations_applied"] is True
    assert metrics["security_effect_confirmed"] is False


def test_verification_fails_when_operational_health_is_violated_even_if_secure() -> None:
    status, metrics = verification_agent.verify(
        changed_nodes=[],
        changed_edges=["some-edge"],
        expected_edges=1,
        sensitive_assets_reachable_before=3,
        sensitive_assets_reachable_after=1,
        correlated_paths_interrupted=1,
        operational_disruption_score=OPERATIONAL_DISRUPTION_THRESHOLD + 0.01,
    )
    assert status == "unsuccessful_simulation"
    assert metrics["security_effect_confirmed"] is True
    assert metrics["operational_health_ok"] is False


def test_verification_succeeds_only_when_both_checks_pass() -> None:
    status, metrics = verification_agent.verify(
        changed_nodes=[],
        changed_edges=["some-edge"],
        expected_edges=1,
        sensitive_assets_reachable_before=3,
        sensitive_assets_reachable_after=1,
        correlated_paths_interrupted=1,
        operational_disruption_score=0.1,
    )
    assert status == "successful_simulation"
    assert metrics["security_effect_confirmed"] is True
    assert metrics["operational_health_ok"] is True


def test_a_playbook_making_no_security_claim_is_not_penalized_for_having_none() -> None:
    """An observe-only playbook (expected_edges == 0) never claimed a
    security effect, so it must not be failed for lacking one."""

    status, metrics = verification_agent.verify(
        changed_nodes=["some-node"],
        changed_edges=[],
        expected_edges=0,
        sensitive_assets_reachable_before=3,
        sensitive_assets_reachable_after=3,
        correlated_paths_interrupted=0,
        operational_disruption_score=0.0,
    )
    assert status == "successful_simulation"
    assert metrics["security_effect_confirmed"] is True


def test_failed_verification_automatically_triggers_rollback_for_a_reversible_action(
    client: TestClient,
) -> None:
    """Forces the real dual-check to fail by degrading the persisted Impact
    Simulation's operational_disruption_score past the threshold after
    execution, then confirms orchestration_service.verify() automatically
    calls rollback() via policy_service.evaluate_rollback_policy - a human
    never has to notice and manually roll back."""

    orchestration = approve(client, create(client))
    client.post(f"/api/v1/orchestration/{orchestration['orchestration_id']}/execute", json={})

    database = client.app.state.database  # type: ignore[attr-defined]
    session = database.session_factory()
    try:
        simulation = session.scalar(
            select(ResponseImpactSimulationRecord).where(
                ResponseImpactSimulationRecord.recommendation_id
                == orchestration["selected_recommendation_id"]
            )
        )
        assert simulation is not None
        simulation.operational_disruption_score = OPERATIONAL_DISRUPTION_THRESHOLD + 0.5
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
