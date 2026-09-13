from dataclasses import dataclass

from app.database.models import ResponseImpactSimulationRecord, ResponseRecommendationRecord
from app.schemas.response import DefensivePlaybook
from app.services import policy_service
from app.services.response_playbook_service import response_playbook_service
from app.services.topology_service import topology_service

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
        playbook = response_playbook_service.get(recommendation.playbook_id)
        operation = str(playbook.topology_mutation_specification["operation"])
        edges = topology_service.edges(True)
        changed_nodes: list[str] = []
        changed_edges: list[str] = []
        if operation == "remove_edge":
            changed_edges = [recommendation.target_id]
        elif operation == "remove_inbound_edges":
            changed_nodes = [recommendation.target_id]
            changed_edges = [
                e.edge_id for e in edges if e.destination_asset_id == recommendation.target_id
            ]
        elif operation == "remove_incident_edges":
            changed_nodes = [recommendation.target_id]
            changed_edges = [
                e.edge_id
                for e in edges
                if recommendation.target_id in {e.source_asset_id, e.destination_asset_id}
            ]
        elif recommendation.target_type != "user":
            changed_nodes = [recommendation.target_id]
        return (
            sorted(changed_nodes),
            sorted(changed_edges),
            {"operation": operation, "scope": "persisted synthetic operational state only"},
        )


OPERATIONAL_DISRUPTION_THRESHOLD = 0.5


class VerificationAgent:
    """Checks BOTH the security effect AND operational health of a real
    synthetic execution against the Impact Simulation computed before
    execution - a mutation merely existing is never, by itself, success
    (see docs/architecture/VERIFICATION_AND_ROLLBACK.md)."""

    name = "Verification Agent"

    def verify(
        self,
        changed_nodes: list[str],
        changed_edges: list[str],
        expected_edges: int,
        sensitive_assets_reachable_before: int,
        sensitive_assets_reachable_after: int,
        correlated_paths_interrupted: int,
        operational_disruption_score: float,
    ) -> tuple[str, dict[str, object]]:
        mutation_applied = bool(changed_nodes or changed_edges) or expected_edges == 0
        no_security_claim = expected_edges == 0
        security_effect_confirmed = no_security_claim or (
            sensitive_assets_reachable_after < sensitive_assets_reachable_before
            or correlated_paths_interrupted > 0
        )
        operational_health_ok = operational_disruption_score <= OPERATIONAL_DISRUPTION_THRESHOLD
        applied = mutation_applied and security_effect_confirmed and operational_health_ok
        status = "successful_simulation" if applied else "unsuccessful_simulation"
        return status, {
            "intended_mutations_applied": mutation_applied,
            "security_effect_confirmed": security_effect_confirmed,
            "operational_health_ok": operational_health_ok,
            "correlated_paths_remaining": max(0, expected_edges - len(changed_edges)),
            "predicted_paths_remaining": 0,
            "expected_relationships_affected": expected_edges,
            "operational_disruption": round(
                len(changed_edges) / max(1, len(topology_service.edges(True))), 6
            ),
            "operational_disruption_score": operational_disruption_score,
            "residual_exposure_score": 0.0 if applied else 1.0,
        }


response_planner_agent = ResponsePlannerAgent()
impact_simulation_agent = ImpactSimulationAgent()
safety_governor_agent = SafetyGovernorAgent()
approval_router_agent = ApprovalRouterAgent()
synthetic_execution_agent = SyntheticExecutionAgent()
verification_agent = VerificationAgent()
