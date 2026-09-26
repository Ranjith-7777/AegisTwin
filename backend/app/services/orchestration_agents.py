from dataclasses import dataclass

from app.database.models import ResponseImpactSimulationRecord, ResponseRecommendationRecord
from app.schemas.blue_planning import SecurityGainEvidence
from app.schemas.response import DefensivePlaybook
from app.services import policy_service, synthetic_mutation_service
from app.services.topology_service import topology_service
from app.services.what_if_evidence_service import security_improved

# v2 (Phase 4): Safety Governor now calls `policy_service.evaluate_response_policies`
# (POL-001..POL-006) instead of re-implementing autonomous-eligibility checks inline,
# and both it and the Approval Router are now autonomy-mode-aware - RECOMMEND and
# APPROVAL_REQUIRED never auto-execute regardless of playbook tier, and AUTONOMOUS
# only auto-executes when every applicable policy passes. Agent identities, the
# planner/impact-simulation/execution/verification contracts, and the orchestration
# state machine are unchanged from v1.
AGENT_VERSION = "deterministic-resilience-agent-v2"


@dataclass(frozen=True)
class AgentResult:
    agent_name: str
    decision_type: str
    decision: str
    summary: str
    rationale: str
    warnings: list[str]
    next_agent: str | None
    score: float | None = None


class ResponsePlannerAgent:
    name = "Response Planner Simulation Agent"

    def decide(self, recommendation: ResponseRecommendationRecord) -> AgentResult:
        return AgentResult(
            self.name,
            "plan_selection",
            "selected",
            f"Selected rank {recommendation.rank} synthetic recommendation as the primary step.",
            "The explicitly selected Phase 7A recommendation is retained without "
            "adding redundant actions.",
            [],
            "Impact Simulation Agent",
            recommendation.recommendation_score,
        )


class ImpactSimulationAgent:
    name = "Impact Simulation Agent"

    def decide(
        self,
        recommendation: ResponseRecommendationRecord,
        simulation: ResponseImpactSimulationRecord | None,
        sequence: int,
    ) -> AgentResult:
        valid = simulation is not None and simulation.through_sequence_number == sequence
        return AgentResult(
            self.name,
            "simulation_validation",
            "validated" if valid else "stale",
            "Phase 7A impact simulation is current."
            if valid
            else "Impact simulation is missing or stale.",
            "Execution planning requires an impact simulation at the identical causal sequence.",
            [] if valid else ["Re-run Phase 7A analysis before orchestration."],
            "Safety Governor Agent" if valid else None,
        )


class SafetyGovernorAgent:
    name = "Safety Governor Agent"

    def decide(
        self,
        recommendation: ResponseRecommendationRecord,
        playbook: DefensivePlaybook,
        autonomy_mode: str,
        target_criticality: str | None,
        target_asset_type: str | None,
    ) -> AgentResult:
        nodes = {node.asset_id for node in topology_service.nodes(True)}
        edges = {edge.edge_id for edge in topology_service.edges(True)}
        target_exists = (
            recommendation.target_type == "user"
            or recommendation.target_id in nodes
            or recommendation.target_id in edges
        )
        policy_result = policy_service.evaluate_response_policies(
            synthetic=recommendation.synthetic and target_exists,
            playbook=playbook,
            autonomy_mode=autonomy_mode,
            target_criticality=target_criticality,
            target_asset_type=target_asset_type,
        )
        permitted = target_exists and policy_result.overall_pass
        automatic = (
            permitted
            and autonomy_mode == "autonomous"
            and playbook.approval_tier == "automatic_candidate"
        )
        summary = (
            "Automatically approved for synthetic execution: every applicable policy passed."
            if automatic
            else "Synthetic target and policy constraints validated."
            if permitted
            else "Blocked by policy: " + "; ".join(policy_result.failed_policy_ids)
            if policy_result.failed_policy_ids
            else "Target is unavailable for this synthetic environment."
        )
        warnings = (
            []
            if permitted
            else [
                evaluation.reason
                for evaluation in policy_result.evaluations
                if evaluation.result == "fail"
            ]
        )
        if not target_exists:
            warnings.append("Target is not a known synthetic topology asset or relationship.")
        return AgentResult(
            self.name,
            "policy_review",
            "automatic_approved" if automatic else "permitted" if permitted else "blocked",
            summary,
            "Policy checks (POL-001..POL-006, see policy_service.catalogue()) cover synthetic "
            "targeting, prohibited playbooks, and - in autonomous mode - reversibility, "
            "operational impact, blast radius and critical data-store isolation.",
            warnings,
            "Approval Router Agent" if permitted else None,
        )


class ApprovalRouterAgent:
    name = "Approval Router Agent"

    def decide(self, tier: str, autonomy_mode: str, policy_pass: bool) -> AgentResult:
        role = "administrator" if tier == "administrator_approval" else "analyst"
        automatic = autonomy_mode == "autonomous" and tier == "automatic_candidate" and policy_pass
        if autonomy_mode in {"recommend", "approval_required"}:
            rationale = (
                f"Autonomy mode is '{autonomy_mode}': candidate plans are generated and "
                "validated but execution always requires human approval, regardless of "
                "playbook tier."
            )
        else:
            rationale = "High-impact actions always require the administrator demonstration role."
        return AgentResult(
            self.name,
            "approval_routing",
            "automatic" if automatic else f"requires_{role}",
            "No human gate required: autonomous mode and every applicable policy passed."
            if automatic
            else f"Routed to synthetic demo {role}.",
            rationale,
            [],
            "Synthetic Execution Agent" if automatic else None,
        )


class SyntheticExecutionAgent:
    name = "Synthetic Execution Agent"

    def mutation(
        self, recommendation: ResponseRecommendationRecord
    ) -> tuple[list[str], list[str], dict[str, object]]:
        """Thin wrapper: the actual "given this synthetic playbook + target,
        what mutation results" arithmetic is `synthetic_mutation_service
        .compute_mutation`, a shared Phase-4-and-Phase-5 primitive - see that
        module's docstring for why it was extracted out of this agent."""

        return synthetic_mutation_service.compute_mutation(
            recommendation.playbook_id, recommendation.target_id, recommendation.target_type
        )


OPERATIONAL_DISRUPTION_THRESHOLD = 0.5


def _objective_met(
    expected_before: float, expected_after: float, actual_after: float
) -> tuple[bool, bool]:
    """A metric is `applicable` only if the plan itself claimed an
    improvement for it (`expected_after < expected_before`) - a metric the
    plan never promised to move can never create an artificial failure.
    When applicable, the objective is `met` only if the ACTUAL result
    meets or outperforms the EXPECTED (simulated) result - not merely
    improves over the before-state, which is a strictly weaker claim (see
    docs/architecture/VERIFICATION_AND_ROLLBACK.md "IMPROVED vs VERIFIED
    AGAINST EXPECTED OBJECTIVE")."""

    applicable = expected_after < expected_before
    met = (not applicable) or (actual_after <= expected_after)
    return applicable, met


class VerificationAgent:
    """Independently recomputes the ACTUAL post-execution synthetic state
    (via the same what_if_evidence_service the Response Planner uses on
    `execution.changed_edge_ids_json` - the real, logged mutation, never a
    prediction) and compares it against the EXPECTED before/after evidence
    computed the identical way from the pre-execution simulation's declared
    mutation. A mutation merely existing is never, by itself, success, and
    neither is a result that merely IMPROVED over the before-state without
    meeting the plan's own EXPECTED containment objective - both a security
    effect AND operational health must independently hold. See
    docs/architecture/VERIFICATION_AND_ROLLBACK.md."""

    name = "Verification Agent"

    def verify(
        self,
        changed_nodes: list[str],
        changed_edges: list[str],
        expected_edges: int,
        expected_evidence: SecurityGainEvidence,
        actual_evidence: SecurityGainEvidence,
        bystander_isolated_asset_ids: list[str],
    ) -> tuple[str, dict[str, object]]:
        mutation_applied = bool(changed_nodes or changed_edges) or expected_edges == 0
        no_security_claim = expected_edges == 0

        # IMPROVED: did the actual result improve at all over the actual
        # before-state, on any of the three metrics? Necessary but not
        # sufficient - see the objective checks below. Shared with Phase 5's
        # mode-agnostic `containment_success` measurement - see
        # `what_if_evidence_service.security_improved`.
        security_improved_result = security_improved(actual_evidence)

        # VERIFIED AGAINST EXPECTED OBJECTIVE: for every metric the plan
        # itself claimed it would improve, did the actual result meet or
        # outperform the expected (simulated) result? A metric the plan
        # never claimed to move is not applicable and can never fail this.
        attack_path_applicable, attack_path_objective_met = _objective_met(
            expected_evidence.attack_paths_before,
            expected_evidence.attack_paths_after,
            actual_evidence.attack_paths_after,
        )
        critical_target_applicable, critical_target_objective_met = _objective_met(
            expected_evidence.critical_targets_reachable_before,
            expected_evidence.critical_targets_reachable_after,
            actual_evidence.critical_targets_reachable_after,
        )
        blast_radius_applicable, blast_radius_objective_met = _objective_met(
            expected_evidence.blast_radius_reachable_before,
            expected_evidence.blast_radius_reachable_after,
            actual_evidence.blast_radius_reachable_after,
        )
        applicability = {
            "attack_path_objective_applicable": attack_path_applicable,
            "critical_target_objective_applicable": critical_target_applicable,
            "blast_radius_objective_applicable": blast_radius_applicable,
        }
        expected_containment_met = (
            attack_path_objective_met
            and critical_target_objective_met
            and blast_radius_objective_met
        )

        # A real security-containment claim requires BOTH: some genuine
        # improvement happened, AND every metric the plan claimed to
        # improve actually met its expected objective. "Improved but fell
        # short of the promised containment" is not success.
        security_effect_confirmed = no_security_claim or (
            security_improved_result and expected_containment_met
        )

        operational_disruption_score = round(
            len(changed_edges) / max(1, len(topology_service.edges(True))), 6
        )
        critical_connectivity_preserved = not bystander_isolated_asset_ids
        operational_health_ok = (
            operational_disruption_score <= OPERATIONAL_DISRUPTION_THRESHOLD
            and critical_connectivity_preserved
        )
        applied = mutation_applied and security_effect_confirmed and operational_health_ok
        status = "successful_simulation" if applied else "unsuccessful_simulation"
        return status, {
            "intended_mutations_applied": mutation_applied,
            "security_effect_confirmed": security_effect_confirmed,
            "security_improved": security_improved_result,
            "expected_containment_met": expected_containment_met,
            "attack_path_objective_met": attack_path_objective_met,
            "critical_target_objective_met": critical_target_objective_met,
            "blast_radius_objective_met": blast_radius_objective_met,
            **applicability,
            "operational_health_ok": operational_health_ok,
            "critical_connectivity_preserved": critical_connectivity_preserved,
            "bystander_isolated_asset_ids": bystander_isolated_asset_ids,
            "expected_attack_paths_after": expected_evidence.attack_paths_after,
            "actual_attack_paths_after": actual_evidence.attack_paths_after,
            "expected_blast_radius_after": expected_evidence.blast_radius_reachable_after,
            "actual_blast_radius_after": actual_evidence.blast_radius_reachable_after,
            "expected_critical_targets_after": expected_evidence.critical_targets_reachable_after,
            "actual_critical_targets_after": actual_evidence.critical_targets_reachable_after,
            "correlated_paths_remaining": max(0, expected_edges - len(changed_edges)),
            "expected_relationships_affected": expected_edges,
            "operational_disruption": operational_disruption_score,
            "operational_disruption_score": operational_disruption_score,
            "residual_exposure_score": 0.0 if applied else 1.0,
        }


response_planner_agent = ResponsePlannerAgent()
impact_simulation_agent = ImpactSimulationAgent()
safety_governor_agent = SafetyGovernorAgent()
approval_router_agent = ApprovalRouterAgent()
synthetic_execution_agent = SyntheticExecutionAgent()
verification_agent = VerificationAgent()
