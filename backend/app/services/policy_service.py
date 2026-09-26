"""Phase 4 policy-as-code catalogue and evaluator.

Every policy reports policy_id/result/reason - never an unexplained
boolean. `evaluate_response_policies` is called once per candidate plan
by the Safety Governor Agent; a `fail` blocks that plan outright.
`evaluate_rollback_policy` is called once by the Verification Agent to
decide whether a failed verification must trigger automatic rollback.
See docs/architecture/POLICY_ENGINE.md.
"""

from __future__ import annotations

from app.schemas.policy import PolicyDefinition, PolicyEvaluation, PolicyEvaluationResult
from app.schemas.response import DefensivePlaybook

AUTONOMOUS_MAX_OPERATIONAL_IMPACT = "medium"
AUTONOMOUS_ELIGIBLE_BLAST_RADII = {"single_asset", "single_identity", "single_relationship"}
CRITICAL_TARGET_ASSET_TYPES = {"database", "object_storage"}

_IMPACT_RANK = {"low": 0, "medium": 1, "high": 2}


def catalogue() -> list[PolicyDefinition]:
    return [
        PolicyDefinition(
            policy_id="POL-001",
            name="Synthetic-only targets",
            purpose="Never permit a plan whose target is not a synthetic, "
            "simulation-only resource.",
            applies_to="Every candidate plan",
            decision_effect="Blocks execution if the recommendation is not marked synthetic.",
            enabled=True,
        ),
        PolicyDefinition(
            policy_id="POL-002",
            name="Prohibited playbooks never execute",
            purpose="A playbook explicitly catalogued as prohibited must never run, "
            "under any autonomy mode.",
            applies_to="Every candidate plan",
            decision_effect="Blocks execution if the playbook's approval_tier is 'prohibited'.",
            enabled=True,
        ),
        PolicyDefinition(
            policy_id="POL-003",
            name="Autonomous execution requires reversibility",
            purpose="Irreversible actions must never execute without a human decision.",
            applies_to="Autonomous mode only",
            decision_effect="Blocks automatic execution if the playbook is not reversible.",
            enabled=True,
        ),
        PolicyDefinition(
            policy_id="POL-004",
            name="Maximum allowed operational impact for automation",
            purpose="Automatic execution is restricted to bounded-impact actions.",
            applies_to="Autonomous mode only",
            decision_effect=f"Blocks automatic execution if declared impact exceeds "
            f"'{AUTONOMOUS_MAX_OPERATIONAL_IMPACT}'.",
            enabled=True,
        ),
        PolicyDefinition(
            policy_id="POL-005",
            name="Maximum allowed automatic blast radius",
            purpose="Automatic execution is restricted to a single affected asset, "
            "identity, or relationship - never a whole service.",
            applies_to="Autonomous mode only",
            decision_effect="Blocks automatic execution if the declared blast radius is "
            "broader than a single resource.",
            enabled=True,
        ),
        PolicyDefinition(
            policy_id="POL-006",
            name="Critical data-store isolation requires administrator approval",
            purpose="Actions touching a critical/high database or object store must "
            "never execute automatically.",
            applies_to="Database/object-storage targets with high or critical criticality",
            decision_effect="Blocks automatic execution unless the playbook's own tier "
            "is already administrator_approval.",
            enabled=True,
        ),
        PolicyDefinition(
            policy_id="POL-007",
            name="Failed verification requires rollback where reversible",
            purpose="A response that fails its containment or operational-health check "
            "must be automatically undone when the action is reversible.",
            applies_to="Post-execution verification",
            decision_effect="Triggers automatic synthetic rollback when verification "
            "fails and the executed action is reversible.",
            enabled=True,
        ),
    ]


def evaluate_response_policies(
    *,
    synthetic: bool,
    playbook: DefensivePlaybook,
    autonomy_mode: str,
    target_criticality: str | None,
    target_asset_type: str | None,
) -> PolicyEvaluationResult:
    evaluations: list[PolicyEvaluation] = []

    evaluations.append(
        PolicyEvaluation(
            policy_id="POL-001",
            policy_name="Synthetic-only targets",
            result="pass" if synthetic else "fail",
            reason="Recommendation is marked synthetic."
            if synthetic
            else "Recommendation is not marked synthetic - rejected.",
        )
    )

    prohibited = playbook.approval_tier == "prohibited"
    evaluations.append(
        PolicyEvaluation(
            policy_id="POL-002",
            policy_name="Prohibited playbooks never execute",
            result="fail" if prohibited else "pass",
            reason=f"Playbook '{playbook.playbook_id}' approval tier is 'prohibited'."
            if prohibited
            else f"Playbook '{playbook.playbook_id}' is not prohibited.",
        )
    )

    is_autonomous = autonomy_mode == "autonomous"
    if is_autonomous:
        reversible = playbook.reversibility == "reversible"
        evaluations.append(
            PolicyEvaluation(
                policy_id="POL-003",
                policy_name="Autonomous execution requires reversibility",
                result="pass" if reversible else "fail",
                reason="Playbook is reversible."
                if reversible
                else f"Playbook reversibility is '{playbook.reversibility}', not reversible.",
            )
        )
        impact_ok = (
            _IMPACT_RANK.get(playbook.default_operational_impact, 2)
            <= _IMPACT_RANK[AUTONOMOUS_MAX_OPERATIONAL_IMPACT]
        )
        evaluations.append(
            PolicyEvaluation(
                policy_id="POL-004",
                policy_name="Maximum allowed operational impact for automation",
                result="pass" if impact_ok else "fail",
                reason=f"Declared impact '{playbook.default_operational_impact}' is within "
                f"the autonomous limit."
                if impact_ok
                else f"Declared impact '{playbook.default_operational_impact}' exceeds the "
                f"autonomous limit of '{AUTONOMOUS_MAX_OPERATIONAL_IMPACT}'.",
            )
        )
        blast_ok = playbook.default_blast_radius in AUTONOMOUS_ELIGIBLE_BLAST_RADII
        evaluations.append(
            PolicyEvaluation(
                policy_id="POL-005",
                policy_name="Maximum allowed automatic blast radius",
                result="pass" if blast_ok else "fail",
                reason=f"Declared blast radius '{playbook.default_blast_radius}' is "
                f"single-resource scoped."
                if blast_ok
                else f"Declared blast radius '{playbook.default_blast_radius}' is broader "
                f"than a single resource - requires a human decision.",
            )
        )
        critical_datastore = (
            target_asset_type in CRITICAL_TARGET_ASSET_TYPES
            and target_criticality in {"high", "critical"}
        )
        if critical_datastore:
            already_admin = playbook.approval_tier == "administrator_approval"
            evaluations.append(
                PolicyEvaluation(
                    policy_id="POL-006",
                    policy_name="Critical data-store isolation requires administrator approval",
                    result="pass" if already_admin else "fail",
                    reason="Playbook already requires administrator approval."
                    if already_admin
                    else f"Target is a {target_criticality} {target_asset_type} - automatic "
                    "execution is never permitted for this class of target.",
                )
            )
        else:
            evaluations.append(
                PolicyEvaluation(
                    policy_id="POL-006",
                    policy_name="Critical data-store isolation requires administrator approval",
                    result="not_applicable",
                    reason="Target is not a high/critical database or object store.",
                )
            )
    else:
        for policy_id, name in (
            ("POL-003", "Autonomous execution requires reversibility"),
            ("POL-004", "Maximum allowed operational impact for automation"),
            ("POL-005", "Maximum allowed automatic blast radius"),
            ("POL-006", "Critical data-store isolation requires administrator approval"),
        ):
            evaluations.append(
                PolicyEvaluation(
                    policy_id=policy_id,
                    policy_name=name,
                    result="not_applicable",
                    reason=f"Autonomy mode is '{autonomy_mode}', not autonomous.",
                )
            )

    failed = [item.policy_id for item in evaluations if item.result == "fail"]
    return PolicyEvaluationResult(
        evaluations=evaluations, overall_pass=len(failed) == 0, failed_policy_ids=failed
    )


def evaluate_rollback_policy(*, verification_failed: bool, reversible: bool) -> PolicyEvaluation:
    if not verification_failed:
        return PolicyEvaluation(
            policy_id="POL-007",
            policy_name="Failed verification requires rollback where reversible",
            result="not_applicable",
            reason="Verification succeeded - no rollback consideration needed.",
        )
    if reversible:
        return PolicyEvaluation(
            policy_id="POL-007",
            policy_name="Failed verification requires rollback where reversible",
            result="fail",
            reason="Verification failed and the action is reversible - automatic "
            "rollback is required.",
        )
    return PolicyEvaluation(
        policy_id="POL-007",
        policy_name="Failed verification requires rollback where reversible",
        result="pass",
        reason="Verification failed but the action is not reversible - rollback is "
        "not possible; this must be surfaced to a human operator.",
    )
