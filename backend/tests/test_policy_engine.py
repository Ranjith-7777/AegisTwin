from fastapi.testclient import TestClient

from app.services import policy_service
from app.services.response_playbook_service import response_playbook_service


def test_catalogue_has_seven_policies_with_ids_and_reasons(client: TestClient) -> None:
    policies = client.get("/api/v1/policies").json()
    assert {p["policy_id"] for p in policies} == {f"POL-00{i}" for i in range(1, 8)}
    for policy in policies:
        assert policy["purpose"]
        assert policy["decision_effect"]


def test_non_autonomous_modes_report_pol_003_to_006_as_not_applicable() -> None:
    playbook = response_playbook_service.get("block-synthetic-route")
    for mode in ("observe", "recommend", "approval_required"):
        result = policy_service.evaluate_response_policies(
            synthetic=True,
            playbook=playbook,
            autonomy_mode=mode,
            target_criticality=None,
            target_asset_type=None,
        )
        by_id = {e.policy_id: e for e in result.evaluations}
        assert by_id["POL-003"].result == "not_applicable"
        assert by_id["POL-004"].result == "not_applicable"
        assert by_id["POL-005"].result == "not_applicable"
        assert by_id["POL-006"].result == "not_applicable"


def test_autonomous_mode_blocks_a_non_reversible_or_high_impact_playbook() -> None:
    playbook = response_playbook_service.get("quarantine-synthetic-application")
    result = policy_service.evaluate_response_policies(
        synthetic=True,
        playbook=playbook,
        autonomy_mode="autonomous",
        target_criticality=None,
        target_asset_type=None,
    )
    assert result.overall_pass is False
    assert "POL-004" in result.failed_policy_ids or "POL-005" in result.failed_policy_ids


def test_autonomous_mode_permits_the_observation_only_playbook() -> None:
    playbook = response_playbook_service.get("increase-synthetic-monitoring")
    result = policy_service.evaluate_response_policies(
        synthetic=True,
        playbook=playbook,
        autonomy_mode="autonomous",
        target_criticality=None,
        target_asset_type=None,
    )
    assert result.overall_pass is True
    assert result.failed_policy_ids == []


def test_autonomous_mode_permits_the_real_containment_playbook_with_explicit_reasons() -> None:
    """The one playbook eligible for full automation that actually changes
    synthetic connectivity - `quarantine-synthetic-ingress-edge` - must pass
    every applicable policy, and each pass must carry a real, specific
    reason (never a bare boolean)."""

    playbook = response_playbook_service.get("quarantine-synthetic-ingress-edge")
    result = policy_service.evaluate_response_policies(
        synthetic=True,
        playbook=playbook,
        autonomy_mode="autonomous",
        target_criticality=None,
        target_asset_type=None,
    )
    assert result.overall_pass is True
    assert result.failed_policy_ids == []
    by_id = {e.policy_id: e for e in result.evaluations}
    assert by_id["POL-003"].result == "pass"
    assert "reversible" in by_id["POL-003"].reason.lower()
    assert by_id["POL-004"].result == "pass"
    assert "low" in by_id["POL-004"].reason.lower()
    assert by_id["POL-005"].result == "pass"
    assert "single-resource" in by_id["POL-005"].reason.lower()
    assert by_id["POL-006"].result == "not_applicable"


def test_the_containment_playbook_cannot_target_a_critical_datastore_automatically() -> None:
    """Even though the catalogue tiers it automatic_candidate, POL-006 still
    blocks automation if it were ever pointed at a critical database or
    object store - autonomy can never bypass this."""

    playbook = response_playbook_service.get("quarantine-synthetic-ingress-edge")
    result = policy_service.evaluate_response_policies(
        synthetic=True,
        playbook=playbook,
        autonomy_mode="autonomous",
        target_criticality="critical",
        target_asset_type="database",
    )
    assert result.overall_pass is False
    assert "POL-006" in result.failed_policy_ids


def test_critical_datastore_requires_administrator_approval_even_when_reversible() -> None:
    """POL-006 must block automatic execution against a critical database even
    for a hypothetically low-tier, reversible playbook - criticality of the
    target, not just the playbook's own declared tier, gates automation."""

    from app.schemas.response import DefensivePlaybook

    low_tier_playbook_targeting_a_database = DefensivePlaybook(
        playbook_id="test-low-tier-database-action",
        playbook_version="1.0",
        name="test",
        description="test",
        action_type="test",
        supported_target_types=["database"],
        required_evidence=[],
        disqualifying_conditions=[],
        topology_mutation_specification={"operation": "remove_inbound_edges"},
        reversibility="reversible",
        default_operational_impact="low",
        default_blast_radius="single_asset",
        approval_tier="automatic_candidate",
        automatic_eligibility=True,
        catalogue_version="test",
    )
    result = policy_service.evaluate_response_policies(
        synthetic=True,
        playbook=low_tier_playbook_targeting_a_database,
        autonomy_mode="autonomous",
        target_criticality="critical",
        target_asset_type="database",
    )
    by_id = {e.policy_id: e for e in result.evaluations}
    assert by_id["POL-006"].result == "fail"
    assert result.overall_pass is False

    already_admin = response_playbook_service.get("protect-sensitive-synthetic-database")
    admin_result = policy_service.evaluate_response_policies(
        synthetic=True,
        playbook=already_admin,
        autonomy_mode="autonomous",
        target_criticality="critical",
        target_asset_type="database",
    )
    assert {e.policy_id: e for e in admin_result.evaluations}["POL-006"].result == "pass"


def test_prohibited_playbook_always_fails_regardless_of_autonomy_mode() -> None:
    from app.schemas.response import DefensivePlaybook

    prohibited = DefensivePlaybook(
        playbook_id="test-prohibited",
        playbook_version="1.0",
        name="test",
        description="test",
        action_type="test",
        supported_target_types=["asset"],
        required_evidence=[],
        disqualifying_conditions=[],
        topology_mutation_specification={"operation": "annotate_node"},
        reversibility="reversible",
        default_operational_impact="low",
        default_blast_radius="single_asset",
        approval_tier="prohibited",
        automatic_eligibility=False,
        catalogue_version="test",
    )
    for mode in ("observe", "recommend", "approval_required", "autonomous"):
        result = policy_service.evaluate_response_policies(
            synthetic=True,
            playbook=prohibited,
            autonomy_mode=mode,
            target_criticality=None,
            target_asset_type=None,
        )
        assert result.overall_pass is False
        assert "POL-002" in result.failed_policy_ids


def test_rollback_policy_requires_rollback_only_when_verification_failed_and_reversible() -> None:
    assert (
        policy_service.evaluate_rollback_policy(verification_failed=False, reversible=True).result
        == "not_applicable"
    )
    assert (
        policy_service.evaluate_rollback_policy(verification_failed=True, reversible=True).result
        == "fail"
    )
    assert (
        policy_service.evaluate_rollback_policy(verification_failed=True, reversible=False).result
        == "pass"
    )


def test_policy_evaluation_is_deterministic() -> None:
    playbook = response_playbook_service.get("block-synthetic-route")
    first = policy_service.evaluate_response_policies(
        synthetic=True,
        playbook=playbook,
        autonomy_mode="autonomous",
        target_criticality="high",
        target_asset_type="database",
    )
    second = policy_service.evaluate_response_policies(
        synthetic=True,
        playbook=playbook,
        autonomy_mode="autonomous",
        target_criticality="high",
        target_asset_type="database",
    )
    assert first == second
