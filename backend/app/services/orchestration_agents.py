from dataclasses import dataclass

from app.database.models import ResponseImpactSimulationRecord, ResponseRecommendationRecord
from app.schemas.response import DefensivePlaybook
from app.services.response_playbook_service import response_playbook_service
from app.services.topology_service import topology_service

AGENT_VERSION = "deterministic-simulation-agent-v1"


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
    ) -> AgentResult:
        nodes = {node.asset_id for node in topology_service.nodes(True)}
        edges = {edge.edge_id for edge in topology_service.edges(True)}
        target_exists = (
            recommendation.target_type == "user"
            or recommendation.target_id in nodes
            or recommendation.target_id in edges
        )
        prohibited = playbook.approval_tier == "prohibited"
        permitted = target_exists and not prohibited and recommendation.synthetic
        automatic = (
            permitted
            and playbook.approval_tier == "automatic_candidate"
            and playbook.default_operational_impact == "low"
            and playbook.default_blast_radius == "single_asset"
            and playbook.reversibility == "reversible"
            and playbook.automatic_eligibility
        )
        summary = (
            "Automatically approved for synthetic execution by simulation policy."
            if automatic
            else "Synthetic target and policy constraints validated."
            if permitted
            else "Simulation policy blocked this plan."
        )
        return AgentResult(
            self.name,
            "policy_review",
            "automatic_approved" if automatic else "permitted" if permitted else "blocked",
            summary,
            "Policy checks cover target inventory, impact, blast radius, reversibility "
            "and approval tier.",
            [] if permitted else ["Target is unavailable or the action is prohibited."],
            "Approval Router Agent" if permitted else None,
        )


class ApprovalRouterAgent:
    name = "Approval Router Agent"

    def decide(self, tier: str) -> AgentResult:
        role = "administrator" if tier == "administrator_approval" else "analyst"
        automatic = tier == "automatic_candidate"
        return AgentResult(
            self.name,
            "approval_routing",
            "automatic" if automatic else f"requires_{role}",
            "No human gate required by synthetic simulation policy."
            if automatic
            else f"Routed to synthetic demo {role}.",
            "High-impact actions always require the administrator demonstration role.",
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


class VerificationAgent:
    name = "Verification Agent"

    def verify(
        self, changed_nodes: list[str], changed_edges: list[str], expected_edges: int
    ) -> tuple[str, dict[str, object]]:
        applied = bool(changed_nodes or changed_edges) or expected_edges == 0
        status = "successful_simulation" if applied else "unsuccessful_simulation"
        return status, {
            "intended_mutations_applied": applied,
            "correlated_paths_remaining": max(0, expected_edges - len(changed_edges)),
            "predicted_paths_remaining": 0,
            "expected_relationships_affected": expected_edges,
            "operational_disruption": round(
                len(changed_edges) / max(1, len(topology_service.edges(True))), 6
            ),
            "residual_exposure_score": 0.0 if applied else 1.0,
        }


response_planner_agent = ResponsePlannerAgent()
impact_simulation_agent = ImpactSimulationAgent()
safety_governor_agent = SafetyGovernorAgent()
approval_router_agent = ApprovalRouterAgent()
synthetic_execution_agent = SyntheticExecutionAgent()
verification_agent = VerificationAgent()
