"""The four defence-strategy implementations under evaluation.

Each strategy answers exactly one question: "given the common detection/
correlation groundwork every experiment already ran, what (if anything) does
this defence mode do about it?" See `experiment_service.ExperimentService`
for the outer lifecycle that runs identical scenario/telemetry/detection/
correlation for all four modes before ever dispatching here - that is what
keeps `NoActiveDefenceStrategy` a fair baseline: it still sees the incident,
it just never acts on it.

## Correction: Rule-Based/ML-Assisted must never touch Phase 4 orchestration

`RuleBasedDefenceStrategy` and `MLAssistedDefenceStrategy` are supposed to be
simple, non-agentic baselines - that is the entire point of comparing them
against `AgenticDefenceStrategy`. They previously called
`orchestration_service.create()`/`.execute()`/`.verify()` (and even
auto-approved pending approvals via `.decide_approval()`), which internally
runs ALL SIX of Phase 4's Blue agents (Response Planner, Impact Simulation,
Safety Governor, Approval Router, Synthetic Execution, Verification) and
persists an `AgentDecisionRecord` for each - secretly giving the "dumb"
baselines the benefit of the full six-agent system and invalidating the
comparison. They now call `synthetic_mutation_service.compute_mutation()`
directly (the same pure topology/playbook-spec arithmetic
`SyntheticExecutionAgent.mutation()` uses, extracted into a shared,
evaluation-neutral primitive) and persist their own lightweight,
evaluation-only `EvaluationSyntheticActionRecord` - never an
`AgentDecisionRecord`, never a `ResponseOrchestrationRecord`. See
`app.services.synthetic_mutation_service` and
`app.database.models.EvaluationSyntheticActionRecord`.

Approval semantics are no longer faked either: the old path silently
auto-approved any pending human approval gate via an "evaluation-engine"
identity, which meant a baseline could "execute" a playbook that a real
non-agentic defender could never have run automatically. Both strategies now
only ever execute a playbook that is genuinely auto-eligible
(`DefensivePlaybook.automatic_eligibility`, which - confirmed by reading
`response_playbook_service.PLAYBOOKS` - is exactly consistent with
`approval_tier == "automatic_candidate"` for every playbook in the
catalogue, so either field is authoritative; `automatic_eligibility` is used
here as the single source of truth):

- Rule-Based: if `RULE_TABLE`'s matched playbook is not auto-eligible, it
  falls back to the documented safe default (`increase-synthetic-monitoring`,
  itself auto-eligible). If even the fallback is not auto-eligible (it
  always is, today, but this is not hardcoded as an assumption), no safe
  response is executed at all.
- ML-Assisted: walks `response_service.analyze()`'s ranked recommendations in
  order and executes the FIRST one whose playbook is auto-eligible (a
  single-shot selection restricted to what a baseline could safely execute
  without a human, not the full Response Utility Score ranking Agentic mode
  uses). If none of the ranked recommendations are auto-eligible, no safe
  response is executed.

In both "nothing auto-eligible" cases, this is recorded honestly - an
`EvaluationSyntheticActionRecord` with `executed=False` and an explanatory
`note` - rather than silently doing nothing or fabricating an approval.

Design choice on `StrategyOutcome.security_gain_evidence_before/after`: no
strategy here computes and returns its own `SecurityGainEvidence`. The
metrics stage recomputes `SecurityGainEvidence` independently and uniformly
for all four modes (including `no_active_defence`, which has no orchestration
or synthetic action at all) straight from `what_if_evidence_service`, from
the experiment's `run_id`/`detection_model_id`/`through_sequence` alone - so
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
    EvaluationSyntheticActionRecord,
    ExperimentRecord,
    TelemetryEventRecord,
)
from app.schemas.autonomy import AutonomyMode
from app.schemas.evaluation import DefenceMode
from app.schemas.response import DefensivePlaybook
from app.services import synthetic_mutation_service, what_if_evidence_service
from app.services.autonomy_service import autonomy_service
from app.services.response_playbook_service import response_playbook_service
from app.services.response_service import response_service
from app.services.topology_path_service import topology_path_service
from app.services.topology_service import topology_service
from app.services.workflow_coordinator_service import workflow_coordinator

# The documented safe default for Rule-Based's fallback when its matched
# rule's playbook is not auto-eligible - see the module docstring's approval
# semantics section. Confirmed auto-eligible in `response_playbook_service
# .PLAYBOOKS` (it is also `RULE_TABLE[4]`'s own default playbook).
SAFE_DEFAULT_PLAYBOOK_ID = "increase-synthetic-monitoring"

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
    # Rule-Based/ML-Assisted only: references the `EvaluationSyntheticAction
    # Record` these two strategies persist instead of a Phase 4
    # `ResponseOrchestrationRecord` - see the module docstring. Always
    # `None` for `no_active_defence` and `agentic` (which keeps using
    # `orchestration_id` instead).
    evaluation_action_id: str | None = None


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


def _persist_evaluation_action(
    session: Session,
    experiment: ExperimentRecord,
    defence_mode: DefenceMode,
    playbook: DefensivePlaybook | None,
    target_type: str | None,
    target_id: str | None,
    changed_node_ids: list[str],
    changed_edge_ids: list[str],
    executed: bool,
    note: str | None,
    rule_id: str | None = None,
    recommendation_rank: int | None = None,
    defense_score: float | None = None,
    through_sequence_number: int | None = None,
) -> str:
    """Persists Rule-Based/ML-Assisted's own lightweight, evaluation-only
    provenance record - NEVER an `AgentDecisionRecord`, and with no
    `orchestration_id` at all, because no Phase 4 orchestration ever runs for
    these two modes. Deterministic on `experiment.experiment_id` (which is
    already unique per experiment), so re-invoking is idempotent."""

    action_id = _id("eval-action", experiment.experiment_id)
    existing = session.get(EvaluationSyntheticActionRecord, action_id)
    if existing is not None:
        return action_id
    session.add(
        EvaluationSyntheticActionRecord(
            action_id=action_id,
            experiment_id=experiment.experiment_id,
            defence_mode=defence_mode.value,
            playbook_id=playbook.playbook_id if playbook else None,
            target_type=target_type,
            target_id=target_id,
            rule_id=rule_id,
            recommendation_rank=recommendation_rank,
            defense_score=defense_score,
            through_sequence_number=through_sequence_number,
            changed_node_ids_json=changed_node_ids,
            changed_edge_ids_json=changed_edge_ids,
            reversibility=playbook.reversibility if playbook else None,
            operational_impact=playbook.default_operational_impact if playbook else None,
            blast_radius=playbook.default_blast_radius if playbook else None,
            executed=executed,
            note=note,
            synthetic=True,
            created_at=_utc_now(),
        )
    )
    session.commit()
    return action_id


class RuleBasedDefenceStrategy(DefenceStrategy):
    """Matches `RULE_TABLE` purely on `experiment.scenario_id`, resolves a
    concrete target via simple topology/evidence lookups (no ranking, no
    ML, no `response_service.analyze()`), and - if the matched playbook (or
    its safe-default fallback) is genuinely auto-eligible - executes it via
    `synthetic_mutation_service.compute_mutation()` directly. Never calls
    `orchestration_service`, `blue_planning_service`, or
    `workflow_coordinator`. See the module docstring for the approval-
    eligibility policy."""

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
        matched_playbook = response_playbook_service.get(rule["playbook_id"])
        notes = [f"Matched {rule['rule_id']}: {rule['reason']}"]

        playbook = matched_playbook
        if not matched_playbook.automatic_eligibility:
            fallback = response_playbook_service.get(SAFE_DEFAULT_PLAYBOOK_ID)
            if not fallback.automatic_eligibility:
                action_id = _persist_evaluation_action(
                    session,
                    experiment,
                    self.mode,
                    None,
                    None,
                    None,
                    [],
                    [],
                    executed=False,
                    note=(
                        f"Rule {rule['rule_id']}'s playbook '{matched_playbook.playbook_id}' is "
                        "not auto-eligible, and the safe default fallback is not auto-eligible "
                        "either; no safe response was executed."
                    ),
                    rule_id=rule["rule_id"],
                    through_sequence_number=sequence,
                )
                notes.append(
                    "Neither the matched playbook nor the safe default fallback is "
                    "auto-eligible; no safe response was executed."
                )
                return StrategyOutcome(evaluation_action_id=action_id, notes=notes)
            playbook = fallback
            notes.append(
                f"Playbook '{matched_playbook.playbook_id}' is not auto-eligible for an "
                f"unattended baseline; executed the safe default '{playbook.playbook_id}' "
                "instead."
            )

        target_type, target_id = self._pick_target(session, run_id, model_id, sequence, playbook)
        if target_id is None:
            action_id = _persist_evaluation_action(
                session,
                experiment,
                self.mode,
                playbook,
                None,
                None,
                [],
                [],
                executed=False,
                note=(
                    f"Playbook '{playbook.playbook_id}' is auto-eligible but no eligible target "
                    "could be resolved from the synthetic topology/evidence."
                ),
                rule_id=rule["rule_id"],
                through_sequence_number=sequence,
            )
            notes.append(
                f"Playbook '{playbook.playbook_id}' is auto-eligible but no eligible target "
                "could be resolved from the synthetic topology/evidence."
            )
            return StrategyOutcome(evaluation_action_id=action_id, notes=notes)

        changed_nodes, changed_edges, _summary = synthetic_mutation_service.compute_mutation(
            playbook.playbook_id, target_id, target_type
        )
        action_id = _persist_evaluation_action(
            session,
            experiment,
            self.mode,
            playbook,
            target_type,
            target_id,
            changed_nodes,
            changed_edges,
            executed=True,
            note=None,
            rule_id=rule["rule_id"],
            through_sequence_number=sequence,
        )
        return StrategyOutcome(
            evaluation_action_id=action_id,
            changed_node_ids=changed_nodes,
            changed_edge_ids=changed_edges,
            autonomous_action_count=1,
            notes=notes,
        )

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


class MLAssistedDefenceStrategy(DefenceStrategy):
    """Uses `response_service.analyze()`'s existing Defense-Score ranking
    (no Response Utility Score, no Digital Twin what-if comparison - that is
    the Agentic mode's job) and walks the ranked recommendations in order,
    executing the FIRST one whose playbook is genuinely auto-eligible via
    `synthetic_mutation_service.compute_mutation()` directly - a single-shot
    selection restricted to what an unattended baseline could safely
    execute, never `orchestration_service`/`workflow_coordinator`. See the
    module docstring for the approval-eligibility policy."""

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
        # `response_service.analyze()` persists its own `ResponseAnalysisRecord`
        # /`ResponseRecommendationRecord`/`ResponseImpactSimulationRecord`s
        # regardless of what this strategy does with the result - that
        # candidate-generation/ranking machinery is real analytical work,
        # not an agent decision, and is shared with the Agentic/ML-Assisted
        # human-in-the-loop demo paths elsewhere in this codebase.
        analysis = response_service.analyze(
            session, run_id, model_id, through_sequence, True, 5, False
        )
        if not analysis.recommendations:
            return StrategyOutcome(notes=["No recommendation was generated."])

        selected = None
        selected_playbook = None
        for recommendation in analysis.recommendations:
            playbook = response_playbook_service.get(recommendation.playbook_id)
            if playbook.automatic_eligibility:
                selected = recommendation
                selected_playbook = playbook
                break

        if selected is None or selected_playbook is None:
            action_id = _persist_evaluation_action(
                session,
                experiment,
                self.mode,
                None,
                None,
                None,
                [],
                [],
                executed=False,
                note=(
                    f"None of the {len(analysis.recommendations)} ranked recommendations were "
                    "auto-eligible for unattended baseline execution; no safe response was "
                    "executed."
                ),
            )
            return StrategyOutcome(
                evaluation_action_id=action_id,
                notes=[
                    f"None of the {len(analysis.recommendations)} ranked recommendations were "
                    "auto-eligible; no safe response was executed."
                ],
            )

        changed_nodes, changed_edges, _summary = synthetic_mutation_service.compute_mutation(
            selected.playbook_id, selected.target_id, selected.target_type
        )
        action_id = _persist_evaluation_action(
            session,
            experiment,
            self.mode,
            selected_playbook,
            selected.target_type,
            selected.target_id,
            changed_nodes,
            changed_edges,
            executed=True,
            note=None,
            recommendation_rank=selected.rank,
            defense_score=selected.defense_score,
            through_sequence_number=selected.through_sequence_number,
        )
        return StrategyOutcome(
            evaluation_action_id=action_id,
            changed_node_ids=changed_nodes,
            changed_edge_ids=changed_edges,
            autonomous_action_count=1,
            notes=[
                f"Selected first auto-eligible recommendation {selected.recommendation_id} "
                f"(rank {selected.rank}, playbook '{selected.playbook_id}', "
                f"Defense Score {selected.defense_score:.3f})."
            ],
        )


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
