"""Static, inspectable registry describing the 7 functional agents and the
analytical subsystems they consume. Does not duplicate agent execution
logic - `app/services/orchestration_agents.py` remains the single
implementation; this module only describes it and reconstructs a trace
from already-persisted `AgentDecisionRecord` rows.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import ResponseOrchestrationRecord
from app.schemas.agents import (
    AgentDescriptor,
    AgentRegistry,
    AgentTrace,
    AgentTraceEntry,
    AnalyticalSubsystemDescriptor,
)
from app.services.orchestration_agents import AGENT_VERSION
from app.services.orchestration_service import orchestration_service

_AGENT_ID_BY_NAME = {
    "Synthetic Red Agent / Scenario Engine": "synthetic_red_agent",
    "Response Planner Simulation Agent": "response_planner",
    "Impact Simulation Agent": "impact_simulation",
    "Safety Governor Agent": "safety_governor",
    "Approval Router Agent": "approval_router",
    "Synthetic Execution Agent": "synthetic_execution",
    "Verification Agent": "verification",
}


def _agents() -> list[AgentDescriptor]:
    return [
        AgentDescriptor(
            agent_id="synthetic_red_agent",
            display_name="Synthetic Red Agent / Scenario Engine",
            side="red",
            role="Generates deterministic synthetic adversary activity from a "
            "structured Red scenario definition (app/schemas/red_scenario.py).",
            description="Not an LLM and not autonomous adversarial planning - a "
            "deterministic scenario/event generator (app/services/event_generator.py, "
            "app/services/scenario_service.py) that replays an authored, MITRE-mapped "
            "step sequence as synthetic telemetry.",
            implementation_type="Deterministic scenario/event generator",
            version="aegisarena-scenario-engine-v1",
            input_types=["RedScenarioDefinition", "seed", "start_time"],
            decision_type="scenario_step_emission",
            output_types=["TelemetryEvent (synthetic)"],
            next_agent=None,
        ),
        AgentDescriptor(
            agent_id="response_planner",
            display_name="Response Planner Agent",
            side="blue",
            role="Generates and ranks candidate defensive plans for an incident.",
            description="Reuses response_service.analyze()'s existing ranked "
            "recommendations as candidates, then enriches the top-K with what-if "
            "Attack Graph/Blast Radius before-after deltas and a Response Utility "
            "Score (app/services/blue_planning_service.py) before selecting the "
            "highest-scoring viable candidate.",
            implementation_type="Deterministic multi-candidate ranking agent",
            version=AGENT_VERSION,
            input_types=[
                "IncidentCandidate",
                "ResponseRecommendation[]",
                "AttackGraph context",
                "BlastRadius context",
            ],
            decision_type="plan_selection",
            output_types=["ranked candidate plans", "selected plan", "rationale"],
            next_agent="impact_simulation",
        ),
        AgentDescriptor(
            agent_id="impact_simulation",
            display_name="Impact Simulation Agent",
            side="blue",
            role="Validates the selected plan's persisted impact simulation is "
            "current for the causal sequence being acted on.",
            description="Confirms a `ResponseImpactSimulationRecord` exists at the "
            "exact `through_sequence_number` being orchestrated - a stale or "
            "missing simulation halts the pipeline honestly rather than proceeding "
            "on outdated evidence.",
            implementation_type="Deterministic validation agent",
            version=AGENT_VERSION,
            input_types=["selected plan", "current Digital Twin/topology state"],
            decision_type="simulation_validation",
            output_types=["validated/stale decision", "before/after graph metrics"],
            next_agent="safety_governor",
        ),
        AgentDescriptor(
            agent_id="safety_governor",
            display_name="Safety Governor Agent",
            side="blue",
            role="Evaluates the selected plan against the Phase 4 policy-as-code "
            "catalogue (app/services/policy_service.py) and existing synthetic-"
            "target/prohibited-tier checks.",
            description="Every policy checked reports policy_id, result and reason "
            "- never an unexplained boolean. A plan failing any policy is blocked, "
            "never silently allowed through.",
            implementation_type="Deterministic policy-as-code evaluation agent",
            version=AGENT_VERSION,
            input_types=["selected plan", "impact evidence", "policy catalogue"],
            decision_type="policy_review",
            output_types=["permit/reject/constrain", "policy evaluations"],
            next_agent="approval_router",
        ),
        AgentDescriptor(
            agent_id="approval_router",
            display_name="Approval Router Agent",
            side="blue",
            role="Routes the permitted plan to automatic execution, analyst "
            "approval, or administrator approval based on autonomy mode, "
            "playbook approval tier, target criticality and policy result.",
            description="AUTONOMOUS mode never bypasses a playbook's own approval "
            "tier or a failed policy - it only allows automatic routing for plans "
            "already eligible under every other check.",
            implementation_type="Deterministic autonomy-aware routing agent",
            version=AGENT_VERSION,
            input_types=["permitted plan", "autonomy mode", "policy result"],
            decision_type="approval_routing",
            output_types=["automatic/analyst/administrator/prohibited"],
            next_agent="synthetic_execution",
        ),
        AgentDescriptor(
            agent_id="synthetic_execution",
            display_name="Synthetic Execution Agent",
            side="blue",
            role="Applies the authorized plan's declared mutation to persisted "
            "synthetic operational state only.",
            description="Never touches real infrastructure, credentials, or the "
            "base topology definition - only the persisted synthetic run/twin "
            "state that Phase 3's Digital Twin already renders.",
            implementation_type="Deterministic synthetic mutation agent",
            version=AGENT_VERSION,
            input_types=["authorized plan"],
            decision_type="synthetic_execution",
            output_types=["mutation evidence (changed nodes/edges)"],
            next_agent="verification",
        ),
        AgentDescriptor(
            agent_id="verification",
            display_name="Verification Agent",
            side="blue",
            role="Checks both security effect and operational health after "
            "execution, and recommends rollback when either fails.",
            description="A mutation having occurred is never treated as success - "
            "security containment and operational health are two independent, "
            "explicitly reported checks (app/services/orchestration_agents.py).",
            implementation_type="Deterministic dual-verification agent",
            version=AGENT_VERSION,
            input_types=["before state", "after state", "containment objective"],
            decision_type="verification",
            output_types=["verified/partial/failed", "containment + health evidence"],
            next_agent=None,
        ),
    ]


def _analytical_subsystems() -> list[AnalyticalSubsystemDescriptor]:
    return [
        AnalyticalSubsystemDescriptor(
            subsystem_id="telemetry",
            display_name="Telemetry",
            description="Deterministic synthetic event stream generated from a scenario.",
            consumed_by=["response_planner"],
        ),
        AnalyticalSubsystemDescriptor(
            subsystem_id="detection",
            display_name="Detection (Isolation Forest)",
            description="An anomaly-scoring model, not an agent - it never decides a "
            "response, only produces an anomaly score/classification per event.",
            consumed_by=["response_planner"],
        ),
        AnalyticalSubsystemDescriptor(
            subsystem_id="incident_correlation",
            display_name="Incident Correlation",
            description="Groups anomalous evidence into an incident candidate.",
            consumed_by=["response_planner"],
        ),
        AnalyticalSubsystemDescriptor(
            subsystem_id="mitre_mapping",
            display_name="MITRE ATT&CK Mapping",
            description="Maps observed evidence to local ATT&CK technique IDs.",
            consumed_by=["response_planner"],
        ),
        AnalyticalSubsystemDescriptor(
            subsystem_id="attack_graph",
            display_name="Attack Graph",
            description="Deterministic ranked attack-path analysis - a tool the "
            "Response Planner queries for before/after security-gain evidence, "
            "never itself a decision-maker.",
            consumed_by=["response_planner", "impact_simulation"],
        ),
        AnalyticalSubsystemDescriptor(
            subsystem_id="blast_radius",
            display_name="Blast Radius",
            description="Deterministic reachability estimate - a tool the Response "
            "Planner queries for before/after security-gain evidence, never itself "
            "a decision-maker.",
            consumed_by=["response_planner", "impact_simulation"],
        ),
        AnalyticalSubsystemDescriptor(
            subsystem_id="prediction",
            display_name="Prediction",
            description="Next-stage progression hypotheses, used opportunistically "
            "as additional evidence.",
            consumed_by=["response_planner"],
        ),
    ]


def registry() -> AgentRegistry:
    agents = _agents()
    return AgentRegistry(
        agents=agents,
        analytical_subsystems=_analytical_subsystems(),
        total_agents=len(agents),
        red_agent_count=sum(1 for item in agents if item.side == "red"),
        blue_agent_count=sum(1 for item in agents if item.side == "blue"),
    )


def trace_for_orchestration(session: Session, orchestration_id: str) -> AgentTrace:
    """Reconstructs the real Blue agent trace from persisted
    `AgentDecisionRecord`s for one orchestration - never fabricated, and
    honestly stops wherever the real pipeline actually stopped."""

    record = session.get(ResponseOrchestrationRecord, orchestration_id)
    if record is None:
        raise ApplicationError(
            "ORCHESTRATION_NOT_FOUND", "The synthetic orchestration was not found.", 404
        )
    view = orchestration_service.view(session, record)
    entries = []
    for index, decision in enumerate(view.decisions, start=1):
        agent_id = _AGENT_ID_BY_NAME.get(decision.agent_name, decision.agent_name)
        entries.append(
            AgentTraceEntry(
                agent_id=agent_id,
                agent_name=decision.agent_name,
                sequence=index,
                timestamp=decision.created_at,
                input_summary=", ".join(decision.input_reference_ids) or "none",
                decision_type=decision.decision_type,
                decision=decision.decision,
                rationale=decision.rationale,
                warnings=decision.warnings,
                resource_ids=decision.input_reference_ids,
                score=decision.ranking_score,
                next_agent=(
                    _AGENT_ID_BY_NAME.get(decision.next_agent, decision.next_agent)
                    if decision.next_agent
                    else None
                ),
                status="reached",
            )
        )
    stopped_reason = None
    if (
        entries
        and entries[-1].next_agent is None
        and view.current_state
        not in {
            "verified",
            "synthetic_rollback_completed",
        }
    ):
        stopped_reason = (
            f"Pipeline stopped after {entries[-1].agent_name}: state is "
            f"'{view.current_state}' - see that decision's warnings for why."
        )
    return AgentTrace(
        orchestration_id=orchestration_id, entries=entries, stopped_reason=stopped_reason
    )
