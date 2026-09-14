"""Phase 5 Stage 5: Unified Experiment Observability - timeline
reconstruction (PM spec Section 39-41).

## Reconstruction, not an event-log query

This codebase has no persisted domain-event log table: `AuditEventRecord`
(`app/database/models.py`) is a hash-chained audit trail scoped to ONE
`orchestration_id`, not a general cross-stage event store, and the
in-process `EventBus` (`app.events.registry.get_event_bus`) is ephemeral -
publishing is fire-and-forget for whichever handlers (websocket
broadcasters, tests) happen to be subscribed at publish time; nothing
durable is written by the bus itself. Building "reconstruct a timeline of
stages" (PM spec Section 40, its own wording) by querying a persisted event
log is therefore not just unnecessary but impossible today without first
adding invasive Stage-1-4 event-persistence plumbing this stage was
explicitly told to avoid.

So `ExperimentTimelineService.build_timeline` reconstructs the FULL honest
timeline directly from the real typed rows Phases 1-4 already persist
(`ExperimentRecord` and everything it transitively points to:
`SimulationRunRecord`/`TelemetryEventRecord`, `AnomalyAssessmentRecord`,
`IncidentCandidateRecord`, `ResponseOrchestrationRecord` and its children).
The additive Phase 5 domain events defined in `app.events.types`/
`app.events.envelope` (Section 101) are a SEPARATE, lightweight layer for
live cross-service correlation (e.g. a websocket UI watching a batch run
progress) - they are not consulted here and are not required for a
timeline to be complete.

## Time conventions (must match `metrics_service.py` exactly - see its
module docstring "1. Logical (simulation) time vs. wall-clock latency")

`logical_time_sim` is seconds since the attack's first simulated telemetry
event, computed via the SAME `_event_time_at_sequence`/`_first_detection_time`
helpers `EvaluationMetricsService` uses (reused directly, not
reimplemented, so the two stages can never silently drift apart).

`wall_clock_time` is the real `datetime.now(UTC)` audit stamp already
written by Phase 1-4 services (`IncidentCandidateRecord.created_at`,
`AnomalyAssessmentRecord.scored_at`, `ResponseOrchestrationRecord.created_at`,
`ApprovalRequestRecord.requested_at`/`decided_at`,
`SyntheticExecutionRecord.started_at`/`completed_at`,
`ResponseVerificationRecord.started_at`/`completed_at`,
`RollbackRecord.started_at`/`completed_at`) - confirmed real by reading each
service's own `datetime.now(UTC)` call sites, not assumed. It is
deliberately left `None` for the two stages whose only persisted timestamp
column is actually a SYNTHETIC-timeline value, not a genuine wall-clock
audit stamp: `SimulationRunRecord.created_at`/`TelemetryEventRecord.created_at`
are both written as the canonical simulated start time / the event's own
simulated timestamp (see `simulation_service.py`/`event_generator.py`),
never `datetime.now(UTC)` - presenting either as "wall clock" would be a
fabrication.

## Fixed stage order (PM spec Section 40 - "show skipped/not-applicable
stages honestly", never silently omit a stage)

Every experiment's timeline carries exactly the stages in `STAGE_ORDER`,
each always present with `status` one of "occurred" /
"skipped_not_applicable" / "failed". `attack_graph_evaluated` and
`blast_radius_evaluated` are marked `skipped_not_applicable` for every
experiment (not conditionally) because this codebase's Attack Graph/Blast
Radius recomputation (`what_if_evidence_service`, called from
`metrics_service._security_metrics`) is a measurement-phase, ephemeral
what-if computation with no per-call persisted audit row to reconstruct a
timestamp from - confirmed by grepping `app/database/models.py` for an
`AttackPathAnalysisRecord`/`BlastRadiusAssessmentRecord`-shaped table: none
exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    AnomalyAssessmentRecord,
    ApprovalRequestRecord,
    EvaluationSyntheticActionRecord,
    ExperimentRecord,
    IncidentCandidateRecord,
    ResponseOrchestrationRecord,
    ResponsePlanAssessmentRecord,
    ResponseRecommendationRecord,
    ResponseVerificationRecord,
    RollbackRecord,
    SimulationRunRecord,
    SyntheticExecutionRecord,
    TelemetryEventRecord,
)
from app.schemas.detection import Classification
from app.schemas.evaluation import DefenceMode, ExperimentTimeline, TimelineEvent
from app.services.evaluation.metrics_service import evaluation_metrics_service
from app.services.telemetry_service import telemetry_service

STAGE_ORDER: tuple[str, ...] = (
    "experiment_created",
    "red_scenario_started",
    "telemetry_generated",
    "detection",
    "incident_correlated",
    "attack_graph_evaluated",
    "blast_radius_evaluated",
    "response_selected",
    "what_if_planning",
    "policy_evaluated",
    "approval",
    "synthetic_execution",
    "verification",
    "rollback",
    "experiment_completed",
)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


@dataclass
class _Ctx:
    """Evidence gathered once per `build_timeline` call and shared across
    the per-stage `_stage_*` builders, so each builder stays a small, honest
    function of the rows it actually needs rather than re-querying."""

    session: Session
    experiment: ExperimentRecord
    attack_start: datetime | None
    orchestration: ResponseOrchestrationRecord | None


class ExperimentTimelineService:
    def build_timeline(self, session: Session, experiment_id: str) -> ExperimentTimeline:
        experiment = session.get(ExperimentRecord, experiment_id)
        if experiment is None:
            raise ValueError(f"Unknown experiment_id: {experiment_id}")

        attack_start = (
            evaluation_metrics_service._event_time_at_sequence(session, experiment.run_id, 1)
            if experiment.run_id is not None
            else None
        )
        orchestration = (
            session.get(ResponseOrchestrationRecord, experiment.orchestration_id)
            if experiment.orchestration_id is not None
            else None
        )
        ctx = _Ctx(
            session=session,
            experiment=experiment,
            attack_start=attack_start,
            orchestration=orchestration,
        )

        builders = (
            self._stage_experiment_created,
            self._stage_red_scenario_started,
            self._stage_telemetry_generated,
            self._stage_detection,
            self._stage_incident_correlated,
            self._stage_attack_graph_evaluated,
            self._stage_blast_radius_evaluated,
            self._stage_response_selected,
            self._stage_what_if_planning,
            self._stage_policy_evaluated,
            self._stage_approval,
            self._stage_synthetic_execution,
            self._stage_verification,
            self._stage_rollback,
            self._stage_experiment_completed,
        )
        events = [builder(ctx, sequence) for sequence, builder in enumerate(builders, start=1)]
        assert [event.stage for event in events] == list(STAGE_ORDER)
        return ExperimentTimeline(experiment_id=experiment_id, events=events)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _seconds_since(value: datetime | None, origin: datetime | None) -> float | None:
        if value is None or origin is None:
            return None
        return round((value - origin).total_seconds(), 6)

    def _event(
        self,
        sequence: int,
        stage: str,
        status: str,
        summary: str,
        logical_time_sim: float | None = None,
        wall_clock_time: datetime | None = None,
        resource_ids: list[str] | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> TimelineEvent:
        return TimelineEvent(
            sequence=sequence,
            stage=stage,
            logical_time_sim=logical_time_sim,
            wall_clock_time=_aware(wall_clock_time),
            status=status,
            summary=summary,
            resource_ids=resource_ids or [],
            correlation_id=correlation_id,
            causation_id=causation_id,
        )

    # ------------------------------------------------------------------
    # Stage builders - one per `STAGE_ORDER` entry, in that exact order
    # ------------------------------------------------------------------

    def _stage_experiment_created(self, ctx: _Ctx, sequence: int) -> TimelineEvent:
        experiment = ctx.experiment
        return self._event(
            sequence,
            "experiment_created",
            "occurred",
            f"Experiment created for scenario '{experiment.scenario_id}' "
            f"(seed={experiment.seed}, defence_mode={experiment.defence_mode}).",
            wall_clock_time=experiment.created_at,
            resource_ids=[experiment.experiment_id],
            correlation_id=experiment.experiment_id,
            causation_id=experiment.batch_id,
        )

    def _stage_red_scenario_started(self, ctx: _Ctx, sequence: int) -> TimelineEvent:
        experiment = ctx.experiment
        if experiment.run_id is None:
            return self._event(
                sequence,
                "red_scenario_started",
                "skipped_not_applicable",
                "No simulation run was created before this experiment failed.",
                correlation_id=experiment.experiment_id,
            )
        run = ctx.session.get(SimulationRunRecord, experiment.run_id)
        if run is None:
            return self._event(
                sequence,
                "red_scenario_started",
                "skipped_not_applicable",
                "Simulation run record could not be found.",
                correlation_id=experiment.experiment_id,
            )
        return self._event(
            sequence,
            "red_scenario_started",
            "occurred",
            f"Red scenario '{run.scenario_id}' started (seed={run.seed}, "
            f"{run.event_count} events planned).",
            logical_time_sim=0.0,
            resource_ids=[run.simulation_run_id],
            correlation_id=experiment.experiment_id,
        )

    def _stage_telemetry_generated(self, ctx: _Ctx, sequence: int) -> TimelineEvent:
        experiment = ctx.experiment
        if experiment.run_id is None:
            return self._event(
                sequence,
                "telemetry_generated",
                "skipped_not_applicable",
                "No simulation run was created before this experiment failed.",
                correlation_id=experiment.experiment_id,
            )
        events = telemetry_service.list_run_events(ctx.session, experiment.run_id)
        if not events:
            return self._event(
                sequence,
                "telemetry_generated",
                "skipped_not_applicable",
                "The simulation run produced zero telemetry events.",
                correlation_id=experiment.experiment_id,
                resource_ids=[experiment.run_id],
            )
        last_event = events[-1]
        horizon = self._seconds_since(_aware(last_event.timestamp), ctx.attack_start)
        return self._event(
            sequence,
            "telemetry_generated",
            "occurred",
            f"{len(events)} telemetry events generated for run '{experiment.run_id}'.",
            logical_time_sim=horizon,
            resource_ids=[experiment.run_id],
            correlation_id=experiment.experiment_id,
        )

    def _stage_detection(self, ctx: _Ctx, sequence: int) -> TimelineEvent:
        experiment = ctx.experiment
        if experiment.run_id is None or experiment.detection_model_id is None:
            return self._event(
                sequence,
                "detection",
                "skipped_not_applicable",
                "No detection model was trained/scored before this experiment failed.",
                correlation_id=experiment.experiment_id,
            )
        statement = (
            select(AnomalyAssessmentRecord)
            .where(
                AnomalyAssessmentRecord.simulation_run_id == experiment.run_id,
                AnomalyAssessmentRecord.model_id == experiment.detection_model_id,
                AnomalyAssessmentRecord.classification == Classification.ANOMALOUS.value,
            )
            .order_by(AnomalyAssessmentRecord.sequence_number)
            .limit(1)
        )
        assessment = ctx.session.scalar(statement)
        if assessment is None:
            return self._event(
                sequence,
                "detection",
                "skipped_not_applicable",
                "No anomalous detection was produced for this run.",
                correlation_id=experiment.experiment_id,
            )
        event = ctx.session.get(TelemetryEventRecord, assessment.event_id)
        event_time = _aware(event.timestamp) if event is not None else None
        return self._event(
            sequence,
            "detection",
            "occurred",
            f"Anomaly detected (anomaly_score={assessment.anomaly_score:.3f}) on event "
            f"'{assessment.event_id}'.",
            logical_time_sim=self._seconds_since(event_time, ctx.attack_start),
            wall_clock_time=assessment.scored_at,
            resource_ids=[assessment.assessment_id, assessment.event_id],
            correlation_id=experiment.experiment_id,
        )

    def _stage_incident_correlated(self, ctx: _Ctx, sequence: int) -> TimelineEvent:
        experiment = ctx.experiment
        if experiment.incident_candidate_id is None:
            return self._event(
                sequence,
                "incident_correlated",
                "skipped_not_applicable",
                "No incident candidate was correlated for this run.",
                correlation_id=experiment.experiment_id,
            )
        incident = ctx.session.get(IncidentCandidateRecord, experiment.incident_candidate_id)
        if incident is None:
            return self._event(
                sequence,
                "incident_correlated",
                "skipped_not_applicable",
                "Incident candidate record could not be found.",
                correlation_id=experiment.experiment_id,
            )
        return self._event(
            sequence,
            "incident_correlated",
            "occurred",
            f"Incident candidate correlated (priority={incident.priority}, "
            f"correlation_score={incident.correlation_score:.3f}, "
            f"evidence_count={incident.evidence_count}).",
            logical_time_sim=self._seconds_since(
                _aware(incident.first_observed_at), ctx.attack_start
            ),
            wall_clock_time=incident.created_at,
            resource_ids=[incident.incident_candidate_id],
            correlation_id=experiment.experiment_id,
        )

    def _stage_attack_graph_evaluated(self, ctx: _Ctx, sequence: int) -> TimelineEvent:
        return self._event(
            sequence,
            "attack_graph_evaluated",
            "skipped_not_applicable",
            "Attack Graph recomputation is an ephemeral, measurement-phase what-if "
            "computation (what_if_evidence_service, invoked from the metrics stage) - it "
            "is not persisted as a per-call audit row for this experiment, so no honest "
            "timestamp exists to reconstruct here.",
            correlation_id=ctx.experiment.experiment_id,
        )

    def _stage_blast_radius_evaluated(self, ctx: _Ctx, sequence: int) -> TimelineEvent:
        return self._event(
            sequence,
            "blast_radius_evaluated",
            "skipped_not_applicable",
            "Blast Radius recomputation is an ephemeral, measurement-phase what-if "
            "computation (what_if_evidence_service, invoked from the metrics stage) - it "
            "is not persisted as a per-call audit row for this experiment, so no honest "
            "timestamp exists to reconstruct here.",
            correlation_id=ctx.experiment.experiment_id,
        )

    def _response_instant(self, ctx: _Ctx) -> datetime | None:
        if ctx.orchestration is None or ctx.experiment.run_id is None:
            return None
        return evaluation_metrics_service._event_time_at_sequence(
            ctx.session, ctx.experiment.run_id, ctx.orchestration.through_sequence_number
        )

    def _stage_response_selected(self, ctx: _Ctx, sequence: int) -> TimelineEvent:
        experiment = ctx.experiment
        if ctx.orchestration is None:
            # Rule-Based/ML-Assisted never create a Phase 4
            # `ResponseOrchestrationRecord` (see `strategies.py` module
            # docstring) - their own response selection/execution is
            # recorded on an `EvaluationSyntheticActionRecord` instead.
            if experiment.evaluation_action_id is not None:
                return self._stage_response_selected_evaluation_action(ctx, sequence)
            if experiment.defence_mode == DefenceMode.NO_ACTIVE_DEFENCE.value:
                reason = (
                    "no_active_defence bypasses response selection by design "
                    "(fairness baseline: it still observes the incident, it just never acts)."
                )
            else:
                reason = "No response plan was selected during this run."
            return self._event(
                sequence,
                "response_selected",
                "skipped_not_applicable",
                reason,
                correlation_id=experiment.experiment_id,
            )
        recommendation = ctx.session.get(
            ResponseRecommendationRecord, ctx.orchestration.selected_recommendation_id
        )
        response_instant = self._response_instant(ctx)
        summary = (
            f"Response plan selected (playbook='{recommendation.playbook_id}', "
            f"target={recommendation.target_type}:{recommendation.target_id})."
            if recommendation is not None
            else f"Response plan selected (recommendation_id="
            f"'{ctx.orchestration.selected_recommendation_id}')."
        )
        return self._event(
            sequence,
            "response_selected",
            "occurred",
            summary,
            logical_time_sim=self._seconds_since(response_instant, ctx.attack_start),
            wall_clock_time=ctx.orchestration.created_at,
            resource_ids=[
                ctx.orchestration.orchestration_id,
                ctx.orchestration.selected_recommendation_id,
            ],
            correlation_id=experiment.experiment_id,
        )

    def _stage_response_selected_evaluation_action(self, ctx: _Ctx, sequence: int) -> TimelineEvent:
        """Rule-Based/ML-Assisted's own response-selection evidence - an
        `EvaluationSyntheticActionRecord`, never a Phase 4
        `ResponseOrchestrationRecord`/`ResponseRecommendationRecord`. See
        `app.services.evaluation.strategies` module docstring."""

        experiment = ctx.experiment
        action = ctx.session.get(EvaluationSyntheticActionRecord, experiment.evaluation_action_id)
        if action is None or not action.executed:
            note = action.note if action is not None else None
            return self._event(
                sequence,
                "response_selected",
                "failed",
                note
                or f"'{experiment.defence_mode}' found no auto-eligible safe response to execute.",
                correlation_id=experiment.experiment_id,
                resource_ids=[action.action_id] if action is not None else [],
            )
        summary = (
            f"'{experiment.defence_mode}' selected and executed playbook "
            f"'{action.playbook_id}' against target {action.target_type}:{action.target_id} "
            "(no Phase 4 orchestration - see strategies.py)."
        )
        return self._event(
            sequence,
            "response_selected",
            "occurred",
            summary,
            wall_clock_time=action.created_at,
            resource_ids=[action.action_id],
            correlation_id=experiment.experiment_id,
        )

    def _plan_assessment(self, ctx: _Ctx) -> ResponsePlanAssessmentRecord | None:
        experiment = ctx.experiment
        if experiment.run_id is None or experiment.incident_candidate_id is None:
            return None
        statement = (
            select(ResponsePlanAssessmentRecord)
            .where(
                ResponsePlanAssessmentRecord.simulation_run_id == experiment.run_id,
                ResponsePlanAssessmentRecord.model_id == experiment.detection_model_id,
                ResponsePlanAssessmentRecord.incident_candidate_id
                == experiment.incident_candidate_id,
            )
            .order_by(ResponsePlanAssessmentRecord.created_at.desc())
            .limit(1)
        )
        return ctx.session.scalar(statement)

    def _stage_what_if_planning(self, ctx: _Ctx, sequence: int) -> TimelineEvent:
        experiment = ctx.experiment
        if experiment.defence_mode != DefenceMode.AGENTIC.value:
            return self._event(
                sequence,
                "what_if_planning",
                "skipped_not_applicable",
                f"'{experiment.defence_mode}' bypasses Digital Twin what-if planning by "
                "design - only the agentic strategy ranks candidate plans through "
                "blue_planning_service.compare().",
                correlation_id=experiment.experiment_id,
            )
        assessment = self._plan_assessment(ctx)
        if assessment is None:
            return self._event(
                sequence,
                "what_if_planning",
                "skipped_not_applicable",
                "No plan comparison was produced (the agentic workflow stopped before "
                "reaching Response Planner comparison, e.g. no incident candidate).",
                correlation_id=experiment.experiment_id,
            )
        response_instant = self._response_instant(ctx)
        candidate_count = len(assessment.candidates_json)
        return self._event(
            sequence,
            "what_if_planning",
            "occurred",
            f"Compared {candidate_count} candidate response plan(s) via Digital Twin "
            "what-if simulation (blue_planning_service.compare()).",
            logical_time_sim=self._seconds_since(response_instant, ctx.attack_start),
            wall_clock_time=assessment.created_at,
            resource_ids=[assessment.assessment_id],
            correlation_id=experiment.experiment_id,
        )

    def _stage_policy_evaluated(self, ctx: _Ctx, sequence: int) -> TimelineEvent:
        experiment = ctx.experiment
        if experiment.defence_mode != DefenceMode.AGENTIC.value:
            return self._event(
                sequence,
                "policy_evaluated",
                "skipped_not_applicable",
                f"'{experiment.defence_mode}' bypasses Safety Governor policy evaluation "
                "during plan comparison by design - only the agentic strategy's candidate "
                "plans carry a policy_pass/policy_failed_ids verdict.",
                correlation_id=experiment.experiment_id,
            )
        assessment = self._plan_assessment(ctx)
        if assessment is None:
            return self._event(
                sequence,
                "policy_evaluated",
                "skipped_not_applicable",
                "No plan comparison was produced, so no policy evaluation evidence exists.",
                correlation_id=experiment.experiment_id,
            )
        candidates = assessment.candidates_json
        passed = sum(1 for candidate in candidates if candidate.get("policy_pass"))
        failed_ids: list[str] = []
        for candidate in candidates:
            raw_failed_ids = candidate.get("policy_failed_ids", [])
            if isinstance(raw_failed_ids, list):
                failed_ids.extend(str(item) for item in raw_failed_ids)
        response_instant = self._response_instant(ctx)
        return self._event(
            sequence,
            "policy_evaluated",
            "occurred",
            f"Policy evaluated {len(candidates)} candidate plan(s): {passed} passed, "
            f"{len(candidates) - passed} failed.",
            logical_time_sim=self._seconds_since(response_instant, ctx.attack_start),
            wall_clock_time=assessment.created_at,
            resource_ids=[assessment.assessment_id, *sorted(set(failed_ids))],
            correlation_id=experiment.experiment_id,
        )

    def _stage_approval(self, ctx: _Ctx, sequence: int) -> TimelineEvent:
        experiment = ctx.experiment
        if ctx.orchestration is None:
            return self._event(
                sequence,
                "approval",
                "skipped_not_applicable",
                "No orchestration was created, so no approval could have been requested.",
                correlation_id=experiment.experiment_id,
            )
        statement = (
            select(ApprovalRequestRecord)
            .where(ApprovalRequestRecord.orchestration_id == ctx.orchestration.orchestration_id)
            .order_by(ApprovalRequestRecord.requested_at)
        )
        approvals = list(ctx.session.scalars(statement))
        if not approvals:
            return self._event(
                sequence,
                "approval",
                "skipped_not_applicable",
                "No human approval was required for this orchestration (fully automated "
                "path, or the Approval Router never routed a plan for approval).",
                correlation_id=experiment.experiment_id,
            )
        latest = approvals[-1]
        states = ", ".join(f"{item.required_role}={item.approval_state}" for item in approvals)
        response_instant = self._response_instant(ctx)
        return self._event(
            sequence,
            "approval",
            "occurred",
            f"{len(approvals)} approval request(s): {states}.",
            logical_time_sim=self._seconds_since(response_instant, ctx.attack_start),
            wall_clock_time=latest.decided_at or latest.requested_at,
            resource_ids=[item.approval_request_id for item in approvals],
            correlation_id=experiment.experiment_id,
        )

    def _stage_synthetic_execution(self, ctx: _Ctx, sequence: int) -> TimelineEvent:
        experiment = ctx.experiment
        if ctx.orchestration is None:
            return self._event(
                sequence,
                "synthetic_execution",
                "skipped_not_applicable",
                "No orchestration was created, so no execution was attempted.",
                correlation_id=experiment.experiment_id,
            )
        statement = select(SyntheticExecutionRecord).where(
            SyntheticExecutionRecord.orchestration_id == ctx.orchestration.orchestration_id
        )
        execution = ctx.session.scalar(statement)
        if execution is None:
            return self._event(
                sequence,
                "synthetic_execution",
                "skipped_not_applicable",
                "Execution was never reached (orchestration did not reach an approved "
                "state, or approval was never granted).",
                correlation_id=experiment.experiment_id,
            )
        response_instant = self._response_instant(ctx)
        status = "occurred" if execution.execution_state == "completed_simulated" else "failed"
        return self._event(
            sequence,
            "synthetic_execution",
            status,
            f"Synthetic execution {execution.execution_state} "
            f"({len(execution.changed_node_ids_json)} node(s), "
            f"{len(execution.changed_edge_ids_json)} edge(s) changed).",
            logical_time_sim=self._seconds_since(response_instant, ctx.attack_start),
            wall_clock_time=execution.completed_at or execution.started_at,
            resource_ids=[execution.execution_id],
            correlation_id=experiment.experiment_id,
        )

    def _stage_verification(self, ctx: _Ctx, sequence: int) -> TimelineEvent:
        experiment = ctx.experiment
        if ctx.orchestration is None:
            return self._event(
                sequence,
                "verification",
                "skipped_not_applicable",
                "No orchestration was created, so no verification was attempted.",
                correlation_id=experiment.experiment_id,
            )
        statement = select(ResponseVerificationRecord).where(
            ResponseVerificationRecord.orchestration_id == ctx.orchestration.orchestration_id
        )
        verification = ctx.session.scalar(statement)
        if verification is None:
            return self._event(
                sequence,
                "verification",
                "skipped_not_applicable",
                "Verification was never reached (synthetic execution did not complete).",
                correlation_id=experiment.experiment_id,
            )
        response_instant = self._response_instant(ctx)
        # Verification OCCURRED at this simulated instant regardless of its
        # outcome (see metrics_service.py's own note) - success/failure is a
        # separate fact, not a timing question, so status stays "occurred".
        return self._event(
            sequence,
            "verification",
            "occurred",
            f"Verification completed with status '{verification.verification_status}'.",
            logical_time_sim=self._seconds_since(response_instant, ctx.attack_start),
            wall_clock_time=verification.completed_at,
            resource_ids=[verification.verification_id],
            correlation_id=experiment.experiment_id,
        )

    def _stage_rollback(self, ctx: _Ctx, sequence: int) -> TimelineEvent:
        experiment = ctx.experiment
        if ctx.orchestration is None:
            return self._event(
                sequence,
                "rollback",
                "skipped_not_applicable",
                "No orchestration was created, so no rollback could have been triggered.",
                correlation_id=experiment.experiment_id,
            )
        statement = select(RollbackRecord).where(
            RollbackRecord.orchestration_id == ctx.orchestration.orchestration_id
        )
        rollback = ctx.session.scalar(statement)
        if rollback is None:
            return self._event(
                sequence,
                "rollback",
                "skipped_not_applicable",
                "No rollback was triggered (verification succeeded, or execution/"
                "verification was never reached).",
                correlation_id=experiment.experiment_id,
            )
        response_instant = self._response_instant(ctx)
        status = "occurred" if rollback.state == "synthetic_rollback_completed" else "failed"
        return self._event(
            sequence,
            "rollback",
            status,
            f"Rollback {rollback.state} ({rollback.reason}).",
            logical_time_sim=self._seconds_since(response_instant, ctx.attack_start),
            wall_clock_time=rollback.completed_at or rollback.started_at,
            resource_ids=[rollback.rollback_id],
            correlation_id=experiment.experiment_id,
        )

    def _stage_experiment_completed(self, ctx: _Ctx, sequence: int) -> TimelineEvent:
        experiment = ctx.experiment
        if experiment.status == "completed":
            return self._event(
                sequence,
                "experiment_completed",
                "occurred",
                "Experiment completed successfully.",
                wall_clock_time=experiment.ended_at,
                resource_ids=[experiment.experiment_id],
                correlation_id=experiment.experiment_id,
            )
        if experiment.status == "failed":
            return self._event(
                sequence,
                "experiment_completed",
                "failed",
                f"Experiment failed at stage '{experiment.failure_stage}' "
                f"({experiment.failure_code}): {experiment.failure_message}",
                wall_clock_time=experiment.ended_at,
                resource_ids=[experiment.experiment_id],
                correlation_id=experiment.experiment_id,
            )
        return self._event(
            sequence,
            "experiment_completed",
            "skipped_not_applicable",
            f"Experiment has not reached a terminal state yet (status='{experiment.status}').",
            resource_ids=[experiment.experiment_id],
            correlation_id=experiment.experiment_id,
        )


experiment_timeline_service = ExperimentTimelineService()
