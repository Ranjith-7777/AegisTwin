"""The four defence-strategy implementations under evaluation.

Each strategy answers exactly one question: "given the common detection/
correlation groundwork every experiment already ran, what (if anything) does
this defence mode do about it?" See `experiment_service.ExperimentService`
for the outer lifecycle that runs identical scenario/telemetry/detection/
correlation for all four modes before ever dispatching here - that is what
keeps `NoActiveDefenceStrategy` a fair baseline: it still sees the incident,
it just never acts on it.

Design choice on `StrategyOutcome.security_gain_evidence_before/after`: no
strategy here computes and returns its own `SecurityGainEvidence`. Rule-based
and ML-assisted go through `orchestration_service.execute()` +
`.verify()`, which already independently recomputes real before/after
Attack Graph/Blast Radius evidence via `what_if_evidence_service` and
persists it inside the `ResponseVerificationRecord.metrics_json`; the
Agentic strategy's `WorkflowRunResult.orchestration` carries the same. A
later metrics stage can recompute `SecurityGainEvidence` independently and
uniformly for all four modes (including `no_active_defence`, which has no
orchestration at all) straight from `what_if_evidence_service`, from the
experiment's `run_id`/`detection_model_id`/`through_sequence` alone - so
these fields are left `None` here rather than duplicated from whichever
strategy happened to compute a version of them internally. This keeps
exactly one methodology for "what was the real security gain", used
identically across all four modes at the metrics stage.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import (
    ExperimentRecord,
    ResponseAnalysisRecord,
    ResponseImpactSimulationRecord,
    ResponseRecommendationRecord,
    TelemetryEventRecord,
)
from app.schemas.autonomy import AutonomyMode
from app.schemas.evaluation import DefenceMode
from app.schemas.orchestration import OrchestrationView
from app.schemas.response import DefensivePlaybook
from app.services import what_if_evidence_service
from app.services.autonomy_service import autonomy_service
from app.services.orchestration_agents import synthetic_execution_agent
from app.services.orchestration_service import orchestration_service
from app.services.response_playbook_service import response_playbook_service
from app.services.response_service import response_service
from app.services.topology_path_service import topology_path_service
from app.services.topology_service import TOPOLOGY_VERSION, topology_service
from app.services.workflow_coordinator_service import workflow_coordinator

RULE_ENGINE_VERSION = "rule-based-evaluation-v1"

# Explicit, inspectable, hardcoded rule table - purely a function of
# `experiment.scenario_id`. No ML, no ranking, no evidence-weighted
# heuristics: this is the "dumb baseline" defence mode.
RULE_TABLE: list[dict[str, str]] = [
    {
        "rule_id": "RULE-DDOS-01",
        "condition": "scenario_id == 'ddos-traffic-spike'",
        "playbook_id": "rate-limit-synthetic-gateway",
        "reason": "Volumetric scenario: apply a gateway rate limit regardless of evidence detail.",
    },
    {
        "rule_id": "RULE-INGRESS-01",
        "condition": "scenario_id == 'leaked-api-credential' AND an anomalous "
        "external-ingress edge is observed",
        "playbook_id": "quarantine-synthetic-ingress-edge",
        "reason": "Leaked-credential scenario with an observed anomalous ingress edge: "
        "quarantine the attacker's own ingress route.",
    },
    {
        "rule_id": "RULE-CRED-01",
        "condition": "scenario_id in ('credential-compromise', 'staged-compromise-demo', "
        "'leaked-api-credential')",
        "playbook_id": "revoke-synthetic-sessions",
        "reason": "Credential-flavoured scenario: revoke the evidenced identity's sessions.",
    },
    {
        "rule_id": "RULE-WORKLOAD-01",
        "condition": "scenario_id == 'suspicious-kubernetes-pod'",
        "playbook_id": "quarantine-synthetic-application",
        "reason": "Workload scenario: quarantine the suspicious pod.",
    },
    {
        "rule_id": "RULE-DEFAULT-01",
        "condition": "no match",
        "playbook_id": "increase-synthetic-monitoring",
        "reason": "Safe default: no rule matched, so only observation is increased.",
    },
]


@dataclass
class StrategyOutcome:
    """What a defence strategy actually did, for `ExperimentService` to
    persist onto the `ExperimentRecord` and for the later metrics stage to
    build on. See the module docstring for why the security-gain-evidence
    fields are deliberately left unset here."""

    orchestration_id: str | None = None
    verification_status: str | None = None
    changed_node_ids: list[str] = field(default_factory=list)
    changed_edge_ids: list[str] = field(default_factory=list)
    approval_count: int = 0
    autonomous_action_count: int = 0
    manual_action_count: int = 0
    security_gain_evidence_before: object | None = None
    security_gain_evidence_after: object | None = None
    notes: list[str] = field(default_factory=list)


def _id(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "aegisarena-evaluation:" + ":".join(parts)))


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _effective_sequence(session: Session, run_id: str, through_sequence: int | None) -> int:
    """Mirrors `response_service.analyze()`'s own clamping so a rule-based
    recommendation's `through_sequence_number` always matches a real,
    reachable evidence boundary for this run, exactly like the ranked
    engine's recommendations do."""

    event_total = int(
        session.scalar(
            select(func.count())
            .select_from(TelemetryEventRecord)
            .where(TelemetryEventRecord.simulation_run_id == run_id)
        )
        or 0
    )
    return min(through_sequence or event_total, event_total)


class DefenceStrategy(ABC):
    mode: DefenceMode

    @abstractmethod
    def execute(
        self,
        session: Session,
        experiment: ExperimentRecord,
        run_id: str,
        model_id: str,
        incident_candidate_id: str | None,
        through_sequence: int | None,
    ) -> StrategyOutcome: ...


class NoActiveDefenceStrategy(DefenceStrategy):
    """Detection/correlation still ran as common groundwork (see
    `ExperimentService`), but this strategy takes no defensive action at
    all: it never calls `response_service`, `blue_planning_service`, or
    `orchestration_service`. Offline scoring in a later stage may still
    measure "what a defender would have seen", but nothing here mutates
    synthetic operational state."""

    mode = DefenceMode.NO_ACTIVE_DEFENCE

    def execute(
        self,
        session: Session,
        experiment: ExperimentRecord,
        run_id: str,
        model_id: str,
        incident_candidate_id: str | None,
        through_sequence: int | None,
    ) -> StrategyOutcome:
        return StrategyOutcome(
            notes=[
                "No active defence: detection/correlation evidence exists but no response "
                "action was taken."
            ]
        )


def _advance_to_terminal(session: Session, orchestration: OrchestrationView) -> StrategyOutcome:
    """Shared post-`orchestration_service.create()` path for the two
    non-agentic-but-acting strategies (rule-based, ml-assisted): these are
    automated evaluation baselines, not a human-in-the-loop demo, so a
    pending human approval gate is auto-approved by the evaluation harness
    itself (never by silently changing autonomy mode or bypassing the
    Safety Governor/Approval Router - both agents still ran and made their
    real decision inside `orchestration_service.create()`; this only
    supplies the human decision that mode would otherwise block on)."""

    approval_count = 0
    pending_states = {"awaiting_analyst_approval", "awaiting_administrator_approval"}
    if orchestration.current_state in pending_states:
        pending = next(
            (item for item in orchestration.approvals if item.approval_state == "pending"), None
        )
        if pending is not None:
            orchestration = orchestration_service.decide_approval(
                session,
                orchestration.orchestration_id,
                pending.approval_request_id,
                pending.required_role,
                "evaluation-engine",
                "approve",
                "Automated evaluation harness approval for a non-agentic defence-strategy "
                "baseline (rule_based/ml_assisted are not the human-in-the-loop autonomy demo).",
            )
            approval_count = 1
    if orchestration.current_state != "approved":
        return StrategyOutcome(
            orchestration_id=orchestration.orchestration_id,
            approval_count=approval_count,
            manual_action_count=approval_count,
            notes=[
                f"Orchestration did not reach 'approved' (state="
                f"'{orchestration.current_state}'); no execution attempted."
            ],
        )
    orchestration = orchestration_service.execute(
        session, orchestration.orchestration_id, None, "none"
    )
    if orchestration.current_state != "synthetic_execution_completed":
        return StrategyOutcome(
            orchestration_id=orchestration.orchestration_id,
            approval_count=approval_count,
            manual_action_count=approval_count,
            notes=[
                f"Synthetic execution did not complete (state='{orchestration.current_state}')."
            ],
        )
    orchestration = orchestration_service.verify(session, orchestration.orchestration_id)
    execution = orchestration.executions[-1] if orchestration.executions else None
    verification = orchestration.verifications[-1] if orchestration.verifications else None
    return StrategyOutcome(
        orchestration_id=orchestration.orchestration_id,
        verification_status=verification.verification_status if verification else None,
        changed_node_ids=list(execution.changed_node_ids) if execution else [],
        changed_edge_ids=list(execution.changed_edge_ids) if execution else [],
        approval_count=approval_count,
        autonomous_action_count=0 if approval_count else 1,
        manual_action_count=approval_count,
    )


class RuleBasedDefenceStrategy(DefenceStrategy):
    """Matches `RULE_TABLE` purely on `experiment.scenario_id`, resolves a
    concrete target via simple topology/evidence lookups (no ranking, no
    ML), constructs a minimal `ResponseRecommendationRecord` +
    `ResponseImpactSimulationRecord` for that single rule (bypassing
    `response_service.analyze()`'s candidate generation/ranking entirely),
    then executes it through `orchestration_service` directly."""

    mode = DefenceMode.RULE_BASED

    def execute(
        self,
        session: Session,
        experiment: ExperimentRecord,
        run_id: str,
        model_id: str,
        incident_candidate_id: str | None,
        through_sequence: int | None,
    ) -> StrategyOutcome:
        if incident_candidate_id is None:
            return StrategyOutcome(notes=["No incident candidate: nothing to respond to."])
        sequence = _effective_sequence(session, run_id, through_sequence)
        rule = self._match_rule(experiment.scenario_id, session, run_id, model_id, sequence)
        playbook = response_playbook_service.get(rule["playbook_id"])
        target_type, target_id = self._pick_target(session, run_id, model_id, sequence, playbook)
        if target_id is None:
            return StrategyOutcome(
                notes=[
                    f"Rule {rule['rule_id']} matched playbook '{playbook.playbook_id}' but no "
                    "eligible target could be resolved from the synthetic topology/evidence."
                ]
            )
        recommendation_id = self._persist_recommendation(
            session,
            run_id,
            model_id,
            incident_candidate_id,
            sequence,
            playbook.playbook_id,
            target_type,
            target_id,
            rule,
        )
        orchestration = orchestration_service.create(
            session,
            run_id,
            model_id,
            incident_candidate_id,
            recommendation_id,
            sequence,
        )
        outcome = _advance_to_terminal(session, orchestration)
        outcome.notes = [f"Matched {rule['rule_id']}: {rule['reason']}", *outcome.notes]
        return outcome

    def _match_rule(
        self,
        scenario_id: str,
        session: Session,
        run_id: str,
        model_id: str,
        through_sequence: int | None,
    ) -> dict[str, str]:
        if scenario_id == "ddos-traffic-spike":
            return RULE_TABLE[0]
        if scenario_id == "leaked-api-credential" and self._find_ingress_edge(
            session, run_id, model_id, through_sequence
        ):
            return RULE_TABLE[1]
        credential_scenarios = (
            "credential-compromise",
            "staged-compromise-demo",
            "leaked-api-credential",
        )
        if scenario_id in credential_scenarios:
            return RULE_TABLE[2]
        if scenario_id == "suspicious-kubernetes-pod":
            return RULE_TABLE[3]
        return RULE_TABLE[4]

    def _find_ingress_edge(
        self, session: Session, run_id: str, model_id: str, through_sequence: int | None
    ) -> str | None:
        state = topology_path_service.run_state(session, run_id, model_id, through_sequence)
        known_nodes = {node.asset_id: node for node in topology_service.nodes(include_sink=True)}
        for edge_id in sorted(state.anomalous_observed_edge_ids):
            source_id = edge_id.split("--", 1)[0]
            source = known_nodes.get(source_id)
            if source is not None and source.asset_type == "external_client":
                return edge_id
        return None

    def _pick_target(
        self,
        session: Session,
        run_id: str,
        model_id: str,
        through_sequence: int | None,
        playbook: DefensivePlaybook,
    ) -> tuple[str, str | None]:
        supported = playbook.supported_target_types
        known_nodes = {node.asset_id: node for node in topology_service.nodes(include_sink=True)}
        anchors, _has_evidence = what_if_evidence_service.anchor_asset_ids(
            session, run_id, model_id, through_sequence or 0
        )
        if "relationship" in supported:
            edge_id = self._find_ingress_edge(session, run_id, model_id, through_sequence)
            return "relationship", edge_id
        if "user" in supported:
            statement = select(TelemetryEventRecord.user_id).where(
                TelemetryEventRecord.simulation_run_id == run_id,
                TelemetryEventRecord.user_id.is_not(None),
            )
            if through_sequence is not None:
                statement = statement.limit(through_sequence)
            user_id = session.scalar(statement)
            return "user", user_id
        for candidate in anchors:
            node = known_nodes.get(candidate)
            if node is not None and node.asset_type in supported:
                return node.asset_type, node.asset_id
        for node in topology_service.nodes(include_sink=False):
            if node.asset_type in supported:
                return node.asset_type, node.asset_id
        if anchors:
            return "asset", anchors[0]
        return "asset", None

    def _persist_recommendation(
        self,
        session: Session,
        run_id: str,
        model_id: str,
        incident_candidate_id: str,
        through_sequence: int,
        playbook_id: str,
        target_type: str,
        target_id: str,
        rule: dict[str, str],
    ) -> str:
        playbook = response_playbook_service.get(playbook_id)
        analysis_id = _id("rule-analysis", run_id, model_id, incident_candidate_id, rule["rule_id"])
        analysis = session.get(ResponseAnalysisRecord, analysis_id)
        now = _utc_now()
        if analysis is None:
            analysis = ResponseAnalysisRecord(
                response_analysis_id=analysis_id,
                simulation_run_id=run_id,
                model_id=model_id,
                incident_candidate_id=incident_candidate_id,
                prediction_snapshot_id=None,
                through_sequence_number=through_sequence,
                response_engine_version=RULE_ENGINE_VERSION,
                recommendation_count=1,
                synthetic=True,
                created_at=now,
            )
            session.add(analysis)
        recommendation_id = _id(
            "rule-recommendation", analysis_id, playbook_id, target_type, target_id
        )
        existing = session.get(ResponseRecommendationRecord, recommendation_id)
        if existing is not None:
            return recommendation_id
        recommendation = ResponseRecommendationRecord(
            recommendation_id=recommendation_id,
            response_analysis_id=analysis_id,
            simulation_run_id=run_id,
            model_id=model_id,
            incident_candidate_id=incident_candidate_id,
            prediction_snapshot_id=None,
            through_sequence_number=through_sequence,
            playbook_id=playbook_id,
            target_type=target_type,
            target_id=target_id,
            rank=1,
            recommendation_score=1.0,
            component_scores_json={"rule_match": 1.0},
            penalties_json={},
            defense_score=0.0,
            defense_components_json={},
            defense_explanation=f"Deterministic rule {rule['rule_id']} match - no ranking "
            "performed.",
            required_approval_tier=playbook.approval_tier,
            recommendation_state="simulation_complete",
            evidence_summary_json=[rule["reason"]],
            rationale=f"Rule-based defence strategy: {rule['reason']}",
            warnings_json=[
                "No real defensive action has been approved or performed.",
                "Selected by a deterministic rule table, not ranked evidence.",
            ],
            synthetic=True,
            created_at=now,
        )
        session.add(recommendation)
        session.flush()
        changed_nodes, changed_edges, _summary = synthetic_execution_agent.mutation(recommendation)
        base_edges = topology_service.edges(True)
        simulation = ResponseImpactSimulationRecord(
            simulation_id=_id("rule-simulation", recommendation_id),
            recommendation_id=recommendation_id,
            simulation_run_id=run_id,
            through_sequence_number=through_sequence,
            base_topology_version=TOPOLOGY_VERSION,
            simulation_engine_version=RULE_ENGINE_VERSION,
            target_type=target_type,
            target_id=target_id,
            changed_node_ids_json=changed_nodes,
            changed_edge_ids_json=changed_edges,
            paths_before_json=[],
            paths_after_json=[],
            correlated_paths_interrupted=0,
            predicted_paths_interrupted=0,
            sensitive_assets_reachable_before=0,
            sensitive_assets_reachable_after=0,
            expected_relationships_affected=len(changed_edges),
            affected_asset_count=len(changed_nodes),
            affected_edge_count=len(changed_edges),
            interruption_score=0.0,
            residual_exposure_score=0.0,
            operational_disruption_score=round(len(changed_edges) / max(1, len(base_edges)), 6),
            blast_radius=playbook.default_blast_radius,
            reversibility=playbook.reversibility,
            warnings_json=["Deterministic rule-based simulation - no ranking performed."],
            synthetic=True,
            created_at=now,
        )
        session.add(simulation)
        session.commit()
        return recommendation_id


class MLAssistedDefenceStrategy(DefenceStrategy):
    """Uses `response_service.analyze()`'s existing Defense-Score ranking
    (no Response Utility Score, no Digital Twin what-if comparison - that is
    the Agentic mode's job), takes the single top-ranked recommendation, and
    executes it through `orchestration_service` directly."""

    mode = DefenceMode.ML_ASSISTED

    def execute(
        self,
        session: Session,
        experiment: ExperimentRecord,
        run_id: str,
        model_id: str,
        incident_candidate_id: str | None,
        through_sequence: int | None,
    ) -> StrategyOutcome:
        if incident_candidate_id is None:
            return StrategyOutcome(notes=["No incident candidate: nothing to respond to."])
        analysis = response_service.analyze(
            session, run_id, model_id, through_sequence, True, 5, False
        )
        if not analysis.recommendations:
            return StrategyOutcome(notes=["No recommendation was generated."])
        top = analysis.recommendations[0]
        orchestration = orchestration_service.create(
            session,
            run_id,
            model_id,
            incident_candidate_id,
            top.recommendation_id,
            top.through_sequence_number,
        )
        outcome = _advance_to_terminal(session, orchestration)
        outcome.notes = [
            f"Selected top-ranked recommendation {top.recommendation_id} "
            f"(playbook '{top.playbook_id}', Defense Score {top.defense_score:.3f}).",
            *outcome.notes,
        ]
        return outcome


class AgenticDefenceStrategy(DefenceStrategy):
    """The real Phase 4 closed loop: `workflow_coordinator.run()`, with
    global autonomy temporarily forced to AUTONOMOUS so the loop can reach
    automatic execution/verification for this experiment, and the previous
    mode always restored afterward (this is shared mutable global config -
    other concurrent code and tests must never observe it leaked)."""

    mode = DefenceMode.AGENTIC

    def execute(
        self,
        session: Session,
        experiment: ExperimentRecord,
        run_id: str,
        model_id: str,
        incident_candidate_id: str | None,
        through_sequence: int | None,
    ) -> StrategyOutcome:
        if incident_candidate_id is None:
            return StrategyOutcome(notes=["No incident candidate: nothing to respond to."])
        # `workflow_coordinator.run()` takes a concrete evidence sequence,
        # not an optional "run to completion" marker - resolve it the same
        # way `response_service.analyze()` (and the rule-based strategy)
        # does, so an experiment's `through_sequence=None` means the same
        # thing ("every generated event") in every defence mode.
        sequence = _effective_sequence(session, run_id, through_sequence)
        previous_mode = autonomy_service.get(session).mode
        try:
            autonomy_service.set_mode(session, AutonomyMode.AUTONOMOUS, "evaluation-engine")
            result = workflow_coordinator.run(
                session, run_id, model_id, incident_candidate_id, sequence, top_k=5
            )
        finally:
            autonomy_service.set_mode(session, previous_mode, "evaluation-engine")
        orchestration = result.orchestration
        if orchestration is None:
            return StrategyOutcome(notes=[result.stopped_reason])
        execution = orchestration.executions[-1] if orchestration.executions else None
        verification = orchestration.verifications[-1] if orchestration.verifications else None
        return StrategyOutcome(
            orchestration_id=orchestration.orchestration_id,
            verification_status=verification.verification_status if verification else None,
            changed_node_ids=list(execution.changed_node_ids) if execution else [],
            changed_edge_ids=list(execution.changed_edge_ids) if execution else [],
            approval_count=0,
            autonomous_action_count=1 if result.auto_executed else 0,
            manual_action_count=0,
            notes=[result.stopped_reason],
        )


_STRATEGIES: dict[DefenceMode, DefenceStrategy] = {
    DefenceMode.NO_ACTIVE_DEFENCE: NoActiveDefenceStrategy(),
    DefenceMode.RULE_BASED: RuleBasedDefenceStrategy(),
    DefenceMode.ML_ASSISTED: MLAssistedDefenceStrategy(),
    DefenceMode.AGENTIC: AgenticDefenceStrategy(),
}


def get_strategy(mode: DefenceMode) -> DefenceStrategy:
    return _STRATEGIES[mode]
