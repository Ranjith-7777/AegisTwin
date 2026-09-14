"""Phase 5 Stage 2: computes and persists real evaluation metrics for one
`ExperimentRecord`.

THIS MODULE OWNS THE FOUNDATION EVERY LATER PHASE-5 STAGE (Mission
Continuity/ARS, API, UI, aggregation) BUILDS ON. Two conventions matter more
than anything else here:

## 1. Logical (simulation) time vs. wall-clock latency

The synthetic attack/detection/response timeline advances entirely through
`TelemetryEventRecord.timestamp` (assigned once at generation time as
`CANONICAL_START_TIME + step.offset_seconds`, see `event_generator.py`) and
the ordinal position of an event within
`order_by(TelemetryEventRecord.timestamp, TelemetryEventRecord.event_id)` -
the same ordering `telemetry_service.list_run_events` and
`AnomalyAssessmentRecord.sequence_number` both already use. A
"through_sequence_number" anywhere in this codebase (recommendations,
orchestrations, impact simulations) is a 1-indexed position in that exact
ordering, so `_event_time_at_sequence` below is the one honest way to turn
any of those into a *simulated* instant.

Phase 4's response/verification/rollback machinery has NO simulated clock of
its own - `ResponseOrchestrationRecord`, `SyntheticExecutionRecord`,
`ResponseVerificationRecord` and `RollbackRecord` only carry wall-clock
`datetime.now(UTC)` audit timestamps, because executing/verifying/rolling
back a synthetic mutation is modelled as instantaneous relative to the
simulated attack timeline. The honest measurement convention adopted here,
confirmed by reading `orchestration_service.py`/`orchestration_agents.py`
end to end, is: **every Blue-side event (response start, containment,
verification, recovery) shares the SAME simulated instant** - the timestamp
of the telemetry event at the orchestration's `through_sequence_number`.
They differ only in *whether* they were reached at all (containment did/did
not complete, verification did/did not run, recovery did/did not
happen) - never in *when*, because Phase 4 does not model separate wall
durations for those stages against the simulated clock. Real wall-clock
computation cost (how long the Python code actually took) is tracked
completely separately, in `computation_latency_json`, populated from
`time.perf_counter()` measurements taken during the actual run
(`ExperimentRecord.workflow_latency_ms`, measured in
`ExperimentService.create_and_run`) and during this module's own
measurement-phase Attack Graph/Blast Radius recomputation
(`evaluation_what_if_latency_ms`). The granularity actually achieved is
coarse: one wall-clock measurement for the whole strategy dispatch
(`workflow_latency_ms`), not per-agent. `planning_latency_ms` and the
decision-time `what_if_latency_ms` are intentionally left `None` in this
stage - see the module docstring note in `experiment_service.py` for why
(measuring them individually would require invasive changes to Stage 1's
`strategies.py`, which the Stage 2 brief explicitly says to avoid).

## 2. Applicability / N/A representation

`normalized_metrics_json` uses one typed wrapper, `Metric`, everywhere:

    {"value": float | bool | None, "applicable": bool, "note": str | None}

`applicable=False` means "this metric does not apply to this experiment"
(e.g. every response/verification/rollback metric for `no_active_defence`,
or a reduction ratio when the "before" count was already zero) - `value` is
always `None` in that case, and `note` explains why. `applicable=True` with
`value=0.0`/`value=False` is a real, meaningfully-computed zero/false, never
conflated with "not applicable". Every normalized metric in this module is
computed through the `Metric` dataclass so a caller can never accidentally
read a missing value as a real 0.0/1.0/False.

`raw_metrics_json`, by contrast, does NOT use the `Metric` wrapper (per the
Phase 5 Stage 2 brief) - every raw metric's Python type already excludes
`None` as a legitimate computed value (a percentage, a count, a boolean
outcome), so a plain JSON `null` unambiguously means "not computed / not
applicable" there.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    AnomalyAssessmentRecord,
    ApprovalRequestRecord,
    EvaluationSyntheticActionRecord,
    ExperimentMetricRecord,
    ExperimentRecord,
    IncidentCandidateRecord,
    ResponseOrchestrationRecord,
    ResponseVerificationRecord,
    RollbackRecord,
    SyntheticExecutionRecord,
    TelemetryEventRecord,
)
from app.schemas.detection import Classification
from app.schemas.telemetry import Severity
from app.services import what_if_evidence_service
from app.services.orchestration_service import orchestration_service
from app.services.scenario_service import scenario_service
from app.services.telemetry_service import telemetry_service
from app.services.topology_service import topology_service

METRICS_VERSION = "aegis-evaluation-metrics-v1"

# Severities that represent a genuine attacker action in a scenario's
# ground-truth step definitions, as opposed to normal/background synthetic
# activity - the only ground-truth label this codebase's scenario catalogue
# carries (see `app/services/scenario_service.py`; there is no separate
# "is_attack_step" flag). `event_generator.py` stamps each generated
# event's `metadata["scenario_step"]` with the originating `ScenarioStep.sequence`,
# which is what lets us walk back from a real `AnomalyAssessmentRecord` to
# "was this actually a ground-truth attack step".
GROUND_TRUTH_SEVERITIES = frozenset({Severity.HIGH, Severity.CRITICAL})

# The configuration_json key `perturbation_service.apply_perturbation`'s
# result is persisted under by `ExperimentService.create_and_run` (Phase 5
# Section 38, partial-observability robustness test). Read back here (and by
# `mission_continuity_service._detection_sequence`) to disregard hidden
# events' `AnomalyAssessmentRecord`s as if the detector never scored them,
# for THIS experiment's metrics only. Duplicated as a tiny local helper
# (rather than imported from `perturbation_service`) to avoid a circular
# import: `perturbation_service` itself imports `GROUND_TRUTH_SEVERITIES`
# from this module.
_HIDDEN_EVENT_IDS_KEY = "hidden_event_ids"


def hidden_event_ids_for_experiment(experiment: ExperimentRecord) -> frozenset[str]:
    raw = experiment.configuration_json.get(_HIDDEN_EVENT_IDS_KEY)
    if not isinstance(raw, list):
        return frozenset()
    return frozenset(str(event_id) for event_id in raw)


@dataclass
class Metric:
    """One normalized-metric slot. See the module docstring, section 2."""

    value: float | bool | None
    applicable: bool
    note: str | None = None

    def to_json(self) -> dict[str, object]:
        return {"value": self.value, "applicable": self.applicable, "note": self.note}


def _na(note: str) -> Metric:
    return Metric(value=None, applicable=False, note=note)


def _ok(value: float | bool, note: str | None = None) -> Metric:
    return Metric(value=value, applicable=True, note=note)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _as_float(value: object) -> float:
    """Narrows a `dict[str, object]` JSON value (already known, by the
    caller's own guard, to be numeric) to `float` for mypy - every call site
    reads from a JSON blob this codebase already writes as numeric."""

    assert isinstance(value, (int, float))
    return float(value)


def _as_int(value: object) -> int:
    assert isinstance(value, (int, float))
    return int(value)


def _reduction(before: int, after: int) -> tuple[float | None, bool]:
    """Shared formula for attack-path/blast-radius/critical-exposure
    reduction: `clamp((before - after) / max(1, before), 0, 1)`, N/A when
    `before == 0` (nothing to reduce, so a ratio would be meaningless rather
    than a real 0.0)."""

    if before == 0:
        return None, False
    return round(_clamp01((before - after) / max(1, before)), 6), True


class EvaluationMetricsService:
    def compute(self, session: Session, experiment_id: str) -> ExperimentMetricRecord:
        """Idempotent: replaces any existing `ExperimentMetricRecord` for
        this `experiment_id`. Never raises on missing/partial evidence
        (`no_active_defence`, or a `failed` experiment stopped mid-way) -
        every metric that cannot be honestly computed becomes N/A/None
        rather than raising or guessing."""

        experiment = session.get(ExperimentRecord, experiment_id)
        if experiment is None:
            raise ValueError(f"Unknown experiment_id: {experiment_id}")

        # Phase 5 Section 38 (partial-observability robustness test): empty
        # for every experiment except one created with a recognised
        # `perturbation_id` (see `perturbation_service` module docstring for
        # why this is read back here rather than recomputed, and why
        # filtering happens at this metrics-read layer).
        hidden_ids = hidden_event_ids_for_experiment(experiment)

        logical_timeline = self._logical_timeline(session, experiment, hidden_ids)
        security = self._security_metrics(session, experiment)
        evaluation_what_if_latency_ms = security.pop("_evaluation_what_if_latency_ms", None)
        raw_metrics = self._raw_metrics(session, experiment, logical_timeline, security, hidden_ids)
        normalized_metrics = self._normalized_metrics(logical_timeline, raw_metrics)
        computation_latency = {
            "planning_latency_ms": None,
            "what_if_latency_ms": None,
            "workflow_latency_ms": experiment.workflow_latency_ms,
            "evaluation_what_if_latency_ms": evaluation_what_if_latency_ms,
        }

        logical_timeline_json = cast(dict[str, object], logical_timeline)
        computation_latency_json = computation_latency

        existing = session.get(ExperimentMetricRecord, experiment_id)
        now = datetime.now(UTC)
        if existing is not None:
            existing.metrics_version = METRICS_VERSION
            existing.logical_timeline_json = logical_timeline_json
            existing.computation_latency_json = computation_latency_json
            existing.raw_metrics_json = raw_metrics
            existing.normalized_metrics_json = normalized_metrics
            existing.computed_at = now
            record = existing
        else:
            record = ExperimentMetricRecord(
                experiment_id=experiment_id,
                metrics_version=METRICS_VERSION,
                logical_timeline_json=logical_timeline_json,
                computation_latency_json=computation_latency_json,
                raw_metrics_json=raw_metrics,
                normalized_metrics_json=normalized_metrics,
                computed_at=now,
                synthetic=True,
            )
            session.add(record)
        session.commit()
        return record

    def get(self, session: Session, experiment_id: str) -> ExperimentMetricRecord | None:
        return session.get(ExperimentMetricRecord, experiment_id)

    # ------------------------------------------------------------------
    # Logical (simulation) timeline
    # ------------------------------------------------------------------

    def _logical_timeline(
        self, session: Session, experiment: ExperimentRecord, hidden_ids: frozenset[str]
    ) -> dict[str, float | None]:
        run_id = experiment.run_id
        if run_id is None:
            return {
                "attack_start_time_sim": None,
                "first_detection_time_sim": None,
                "incident_confirmed_time_sim": None,
                "response_start_time_sim": None,
                "containment_time_sim": None,
                "verification_time_sim": None,
                "recovery_time_sim": None,
                "experiment_horizon_sim": None,
            }

        attack_start = self._event_time_at_sequence(session, run_id, 1)
        last_event = self._last_event_time(session, run_id)
        experiment_horizon = (
            (last_event - attack_start).total_seconds()
            if attack_start is not None and last_event is not None
            else None
        )

        first_detection = self._first_detection_time(
            session, run_id, experiment.detection_model_id, hidden_ids
        )

        incident_confirmed = None
        if experiment.incident_candidate_id is not None:
            incident = session.get(IncidentCandidateRecord, experiment.incident_candidate_id)
            if incident is not None:
                incident_confirmed = _aware(incident.first_observed_at)

        response_instant = None
        orchestration = None
        evaluation_action = None
        if experiment.orchestration_id is not None:
            orchestration = session.get(ResponseOrchestrationRecord, experiment.orchestration_id)
            if orchestration is not None:
                response_instant = self._event_time_at_sequence(
                    session, run_id, orchestration.through_sequence_number
                )
        elif experiment.evaluation_action_id is not None:
            # `rule_based`/`ml_assisted` never produce a
            # `ResponseOrchestrationRecord` - their own decision instant is
            # `EvaluationSyntheticActionRecord.through_sequence_number`,
            # the same `through_sequence_number` convention.
            evaluation_action = session.get(
                EvaluationSyntheticActionRecord, experiment.evaluation_action_id
            )
            if (
                evaluation_action is not None
                and evaluation_action.through_sequence_number is not None
            ):
                response_instant = self._event_time_at_sequence(
                    session, run_id, evaluation_action.through_sequence_number
                )

        containment_time = None
        execution = None
        if orchestration is not None:
            execution = session.scalar(
                select(SyntheticExecutionRecord).where(
                    SyntheticExecutionRecord.orchestration_id == orchestration.orchestration_id
                )
            )
            if execution is not None and execution.execution_state == "completed_simulated":
                containment_time = response_instant
        elif evaluation_action is not None and evaluation_action.executed:
            # `rule_based`/`ml_assisted` share Phase 4's own "every Blue-side
            # event happens at the same simulated instant" convention (see
            # module docstring): a successfully executed synthetic mutation
            # is contained at the same instant the response was decided.
            containment_time = response_instant

        verification = None
        verification_time = None
        if orchestration is not None:
            verification = session.scalar(
                select(ResponseVerificationRecord).where(
                    ResponseVerificationRecord.orchestration_id == orchestration.orchestration_id
                )
            )
            if verification is not None:
                # Verification OCCURRED at this simulated instant regardless of
                # its outcome - success/failure is a separate metric
                # (`verification_success`), not a timing question.
                verification_time = response_instant

        recovery_time = None
        if verification is not None and orchestration is not None:
            rollback = session.scalar(
                select(RollbackRecord).where(
                    RollbackRecord.orchestration_id == orchestration.orchestration_id
                )
            )
            rollback_recovered = (
                rollback is not None and rollback.state == "synthetic_rollback_completed"
            )
            verified_without_rollback = (
                rollback is None and verification.verification_status == "successful_simulation"
            )
            if rollback_recovered or verified_without_rollback:
                recovery_time = response_instant

        return {
            "attack_start_time_sim": self._seconds_since(attack_start, attack_start),
            "first_detection_time_sim": self._seconds_since(first_detection, attack_start),
            "incident_confirmed_time_sim": self._seconds_since(incident_confirmed, attack_start),
            "response_start_time_sim": self._seconds_since(response_instant, attack_start),
            "containment_time_sim": self._seconds_since(containment_time, attack_start),
            "verification_time_sim": self._seconds_since(verification_time, attack_start),
            "recovery_time_sim": self._seconds_since(recovery_time, attack_start),
            "experiment_horizon_sim": experiment_horizon,
        }

    @staticmethod
    def _seconds_since(value: datetime | None, origin: datetime | None) -> float | None:
        if value is None or origin is None:
            return None
        return (value - origin).total_seconds()

    @staticmethod
    def _event_time_at_sequence(session: Session, run_id: str, sequence: int) -> datetime | None:
        """`sequence` is a 1-indexed position in
        `order_by(TelemetryEventRecord.timestamp, TelemetryEventRecord.event_id)`
        - the same ordinal every `through_sequence_number` in this codebase
        already uses (see module docstring)."""

        if sequence < 1:
            return None
        statement = (
            select(TelemetryEventRecord.timestamp)
            .where(TelemetryEventRecord.simulation_run_id == run_id)
            .order_by(TelemetryEventRecord.timestamp, TelemetryEventRecord.event_id)
            .offset(sequence - 1)
            .limit(1)
        )
        result = session.scalar(statement)
        return _aware(result)

    @staticmethod
    def _last_event_time(session: Session, run_id: str) -> datetime | None:
        statement = (
            select(TelemetryEventRecord.timestamp)
            .where(TelemetryEventRecord.simulation_run_id == run_id)
            .order_by(TelemetryEventRecord.timestamp.desc(), TelemetryEventRecord.event_id.desc())
            .limit(1)
        )
        return _aware(session.scalar(statement))

    @staticmethod
    def _first_detection_time(
        session: Session, run_id: str, model_id: str | None, hidden_ids: frozenset[str]
    ) -> datetime | None:
        if model_id is None:
            return None
        statement = (
            select(AnomalyAssessmentRecord.event_id)
            .where(
                AnomalyAssessmentRecord.simulation_run_id == run_id,
                AnomalyAssessmentRecord.model_id == model_id,
                AnomalyAssessmentRecord.classification == Classification.ANOMALOUS.value,
            )
            .order_by(AnomalyAssessmentRecord.sequence_number)
        )
        # Perturbation (Section 38): skip any anomalous event this
        # experiment was configured to hide - the detector's real output is
        # unchanged (still persisted), this experiment simply disregards it,
        # exactly as if it had never been scored. Empty `hidden_ids` (the
        # default for every unperturbed experiment) makes this identical to
        # the previous `.limit(1)` behaviour.
        event_id = None
        for candidate_event_id in session.scalars(statement):
            if candidate_event_id not in hidden_ids:
                event_id = candidate_event_id
                break
        if event_id is None:
            return None
        event = session.get(TelemetryEventRecord, event_id)
        return _aware(event.timestamp) if event is not None else None

    # ------------------------------------------------------------------
    # Raw metrics
    # ------------------------------------------------------------------

    def _raw_metrics(
        self,
        session: Session,
        experiment: ExperimentRecord,
        timeline: dict[str, float | None],
        security: dict[str, object],
        hidden_ids: frozenset[str],
    ) -> dict[str, object]:
        detection = self._detection_metrics(session, experiment, hidden_ids)
        timing = self._timing_metrics(timeline)
        ops, verification, rollback = self._response_metrics(session, experiment, security)
        human = self._human_involvement_metrics(session, experiment)
        return {**detection, **timing, **security, **ops, **verification, **rollback, **human}

    def _detection_metrics(
        self, session: Session, experiment: ExperimentRecord, hidden_ids: frozenset[str]
    ) -> dict[str, object]:
        if experiment.run_id is None:
            return {
                "detectable_attack_steps": 0,
                "detected_attack_steps": 0,
                "detection_coverage": None,
                "false_positive_count": None,
                "false_positive_rate": None,
            }
        scenario = scenario_service.get_scenario(session, experiment.scenario_id)
        ground_truth_steps = {
            step.sequence for step in scenario.steps if step.severity in GROUND_TRUTH_SEVERITIES
        }
        detectable = len(ground_truth_steps)

        events = telemetry_service.list_run_events(session, experiment.run_id)
        step_by_event_id = {event.event_id: event.metadata.get("scenario_step") for event in events}

        detected_steps: set[int] = set()
        false_positive_count = 0
        anomalous_total = 0
        if experiment.detection_model_id is not None:
            statement = select(AnomalyAssessmentRecord.event_id).where(
                AnomalyAssessmentRecord.simulation_run_id == experiment.run_id,
                AnomalyAssessmentRecord.model_id == experiment.detection_model_id,
                AnomalyAssessmentRecord.classification == Classification.ANOMALOUS.value,
            )
            # Perturbation (Section 38): hidden events' assessments are
            # disregarded entirely for THIS experiment's detection metrics -
            # as if the detector never scored them. Empty `hidden_ids` (the
            # default for every unperturbed experiment) leaves this
            # identical to the previous unfiltered behaviour.
            anomalous_event_ids = [
                event_id for event_id in session.scalars(statement) if event_id not in hidden_ids
            ]
            anomalous_total = len(anomalous_event_ids)
            for event_id in anomalous_event_ids:
                step_sequence = step_by_event_id.get(event_id)
                if isinstance(step_sequence, int) and step_sequence in ground_truth_steps:
                    detected_steps.add(step_sequence)
                else:
                    # Anomalous detection whose originating scenario step is
                    # NOT a ground-truth attack step (either background
                    # synthetic activity, or an event we can't trace back to
                    # a step at all): a real false positive against this
                    # scenario's ground truth.
                    false_positive_count += 1

        detection_coverage = round(len(detected_steps) / detectable, 6) if detectable > 0 else None
        # Denominator choice: total anomalous DETECTIONS (not total events),
        # documented per the Stage 2 brief - a false-positive rate against
        # total events would be dominated by the (usually large) count of
        # normal background telemetry and would not answer "of what the
        # detector flagged, how much was wrong".
        false_positive_rate = (
            round(false_positive_count / anomalous_total, 6) if anomalous_total > 0 else None
        )

        return {
            "detectable_attack_steps": detectable,
            "detected_attack_steps": len(detected_steps),
            "detection_coverage": detection_coverage,
            "false_positive_count": false_positive_count if anomalous_total > 0 else None,
            "false_positive_rate": false_positive_rate,
        }

    def _timing_metrics(self, timeline: dict[str, float | None]) -> dict[str, object]:
        def delta(end_key: str, start_key: str = "attack_start_time_sim") -> float | None:
            end = timeline.get(end_key)
            start = timeline.get(start_key)
            if end is None or start is None:
                return None
            return round(float(end) - float(start), 6)

        return {
            "time_to_first_detection": delta("first_detection_time_sim"),
            "time_to_incident": delta("incident_confirmed_time_sim"),
            "time_to_response": delta("response_start_time_sim"),
            "time_to_containment": delta("containment_time_sim"),
            # Recovery is defined as "verified recovery" throughout this
            # module (successful rollback, or successful verification that
            # never needed one) - see `_logical_timeline`'s `recovery_time`
            # derivation and the `recovery_success`-equivalent note on
            # `verification_success`/`rollback_success` below.
            "time_to_verified_recovery": delta("recovery_time_sim"),
        }

    def _security_metrics(
        self, session: Session, experiment: ExperimentRecord
    ) -> dict[str, object]:
        if experiment.run_id is None or experiment.detection_model_id is None:
            return {
                "attack_paths_before": None,
                "attack_paths_after": None,
                "attack_path_reduction": None,
                "blast_radius_before": None,
                "blast_radius_after": None,
                "blast_radius_reduction": None,
                "critical_assets_exposed_before": None,
                "critical_assets_exposed_after": None,
                "critical_exposure_reduction": None,
                "security_improved": None,
                "_evaluation_what_if_latency_ms": None,
            }
        total_sequence = len(telemetry_service.list_run_events(session, experiment.run_id))
        started = perf_counter()
        anchors, has_evidence = what_if_evidence_service.anchor_asset_ids(
            session, experiment.run_id, experiment.detection_model_id, total_sequence
        )
        if anchors:
            # One call: `security_gain_evidence`'s own "before" traversal
            # never applies an exclusion, so passing the experiment's real
            # changed node/edge ids as the exclude sets already yields a
            # true before/after pair in a single recomputation - see
            # `what_if_evidence_service.security_gain_evidence`. This is
            # computed identically for every defence mode, including
            # `no_active_defence` (whose changed-node/edge sets are empty,
            # so before == after honestly).
            evidence = what_if_evidence_service.security_gain_evidence(
                session,
                experiment.run_id,
                experiment.detection_model_id,
                total_sequence,
                anchors,
                has_evidence,
                frozenset(experiment.changed_node_ids_json),
                frozenset(experiment.changed_edge_ids_json),
            )
        else:
            evidence = what_if_evidence_service.ZERO_EVIDENCE
        latency_ms = round((perf_counter() - started) * 1000, 3)

        attack_path_reduction, _ = _reduction(
            evidence.attack_paths_before, evidence.attack_paths_after
        )
        blast_radius_reduction, _ = _reduction(
            evidence.blast_radius_reachable_before, evidence.blast_radius_reachable_after
        )
        # `critical_targets_reachable_before/after` from `SecurityGainEvidence`
        # already counts both "high" and "critical" criticality targets (see
        # `attack_graph_service`'s `target_criticality in {"high", "critical"}`
        # filter, reused unchanged here) - not "critical" alone.
        critical_exposure_reduction, _ = _reduction(
            evidence.critical_targets_reachable_before, evidence.critical_targets_reachable_after
        )

        return {
            "attack_paths_before": evidence.attack_paths_before,
            "attack_paths_after": evidence.attack_paths_after,
            "attack_path_reduction": attack_path_reduction,
            "blast_radius_before": evidence.blast_radius_reachable_before,
            "blast_radius_after": evidence.blast_radius_reachable_after,
            "blast_radius_reduction": blast_radius_reduction,
            "critical_assets_exposed_before": evidence.critical_targets_reachable_before,
            "critical_assets_exposed_after": evidence.critical_targets_reachable_after,
            "critical_exposure_reduction": critical_exposure_reduction,
            # Mode-agnostic "did a genuine measured security improvement
            # occur" check, shared with `orchestration_agents.
            # VerificationAgent` via `what_if_evidence_service
            # .security_improved` - see `_response_metrics`'s
            # `containment_success` derivation below, which is the ONLY
            # consumer of this key across every defence mode (including
            # `rule_based`/`ml_assisted`, which never run Phase 4's
            # Verification Agent at all).
            "security_improved": what_if_evidence_service.security_improved(evidence),
            "_evaluation_what_if_latency_ms": latency_ms,
        }

    @staticmethod
    def _action_executed(session: Session, evaluation_action_id: str) -> bool:
        """Whether a `rule_based`/`ml_assisted` experiment's evaluation
        action actually executed a safe response, as opposed to honestly
        recording that nothing auto-eligible was found (see
        `EvaluationSyntheticActionRecord.executed` /
        `app.services.evaluation.strategies`)."""

        action = session.get(EvaluationSyntheticActionRecord, evaluation_action_id)
        return action is not None and action.executed

    def _response_metrics(
        self,
        session: Session,
        experiment: ExperimentRecord,
        security: dict[str, object],
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        affected_asset_count = len(experiment.changed_node_ids_json)
        affected_relationship_count = len(experiment.changed_edge_ids_json)

        orchestration_id = experiment.orchestration_id
        verification_record = None
        rollback_record = None
        if orchestration_id is not None:
            verification_record = session.scalar(
                select(ResponseVerificationRecord).where(
                    ResponseVerificationRecord.orchestration_id == orchestration_id
                )
            )
            rollback_record = session.scalar(
                select(RollbackRecord).where(RollbackRecord.orchestration_id == orchestration_id)
            )

        metrics_json = verification_record.metrics_json if verification_record else None

        # operational_disruption: reuse Phase 4's own real value when it
        # exists; otherwise fall back to the identical formula
        # `orchestration_agents.VerificationAgent`/rule-based strategy both
        # already use (`len(changed_edges) / max(1, len(topology_edges))`),
        # never a second, different formula. Genuinely 0.0 (not N/A) for
        # `no_active_defence`, since no mutation ever happened. This
        # fallback formula never needed a `ResponseVerificationRecord` in
        # the first place - only the shortcut of reading a cached value -
        # so it applies unchanged to `rule_based`/`ml_assisted`, which now
        # never produce one.
        if metrics_json is not None and "operational_disruption_score" in metrics_json:
            operational_disruption = _as_float(metrics_json["operational_disruption_score"])
        elif affected_relationship_count > 0:
            total_edges = len(topology_service.edges(True))
            operational_disruption = round(affected_relationship_count / max(1, total_edges), 6)
        else:
            operational_disruption = 0.0

        # bystander_impact_count: Phase 4's bystander-isolation check
        # (`orchestration_service._bystander_isolated_assets`) is pure
        # topology/edge-set arithmetic, not an agent decision - it is safe
        # to call directly for `rule_based`/`ml_assisted`, which have no
        # `ResponseVerificationRecord` (and hence no cached
        # `bystander_isolated_asset_ids`) to read back, unlike `agentic`.
        if metrics_json is not None:
            bystander_ids = metrics_json.get("bystander_isolated_asset_ids", [])
            bystander_impact_count = len(bystander_ids) if isinstance(bystander_ids, list) else 0
        elif experiment.evaluation_action_id is not None and affected_relationship_count > 0:
            action = session.get(EvaluationSyntheticActionRecord, experiment.evaluation_action_id)
            intended_target_id = action.target_id if action is not None else None
            bystander_impact_count = (
                len(
                    orchestration_service.bystander_isolated_assets(
                        intended_target_id, experiment.changed_edge_ids_json
                    )
                )
                if intended_target_id is not None
                else 0
            )
        else:
            bystander_impact_count = 0

        attack_path_reduction = security.get("attack_path_reduction")
        if metrics_json is not None and "residual_exposure_score" in metrics_json:
            residual_exposure_score = _as_float(metrics_json["residual_exposure_score"])
        elif attack_path_reduction is not None:
            residual_exposure_score = round(1.0 - _as_float(attack_path_reduction), 6)
        else:
            residual_exposure_score = None

        ops = {
            "affected_asset_count": affected_asset_count,
            "affected_relationship_count": affected_relationship_count,
            "operational_disruption": operational_disruption,
            "bystander_impact_count": bystander_impact_count,
            "residual_exposure_score": residual_exposure_score,
        }

        # containment_success: was a response attempted at all (either a
        # Phase 4 orchestration - `agentic` - or an
        # `EvaluationSyntheticActionRecord` - `rule_based`/`ml_assisted`),
        # and did a genuine, independently-measured security improvement
        # occur? N/A only when nothing was attempted at all
        # (`no_active_defence`, or no recommendation/eligible playbook was
        # ever produced). This is deliberately NOT
        # `experiment.verification_status == "successful_simulation"` any
        # more - that read Phase 4's Verification Agent output, which
        # `rule_based`/`ml_assisted` never produce - and NOT merely "an
        # action record exists", since a `rule_based`/`ml_assisted` run
        # that found nothing auto-eligible still persists an
        # `EvaluationSyntheticActionRecord` with `executed=False`. Instead
        # it reuses `_security_metrics()`'s uniformly-computed
        # `security_improved` (see `what_if_evidence_service
        # .security_improved`), the same real before/after Attack
        # Graph/Blast Radius evidence every mode's metrics are built from -
        # making `containment_success` genuinely comparable across all four
        # modes on identical evidence, rather than four different
        # methodologies.
        action_attempted = orchestration_id is not None or (
            experiment.evaluation_action_id is not None
            and self._action_executed(session, experiment.evaluation_action_id)
        )
        security_improved = security.get("security_improved")
        if not action_attempted or security_improved is None:
            containment_success = None
        else:
            containment_success = bool(security_improved)

        # verification_success: N/A unless verification actually ran. This
        # remains a Phase-4-specific measurement, distinct from
        # `containment_success` above: `rule_based`/`ml_assisted` never run
        # Phase 4's dedicated post-execution Verification Agent step at
        # all - by design, not merely because evidence is missing - so this
        # stays honestly N/A for those two modes, never False and never
        # equal to `containment_success`.
        if verification_record is None:
            verification_success = None
        else:
            verification_success = verification_record.verification_status == (
                "successful_simulation"
            )

        verification = {
            "containment_success": containment_success,
            "verification_success": verification_success,
        }

        # rollback_required/rollback_success: only meaningful once
        # verification actually failed - otherwise rollback was never
        # eligible to happen (a genuine N/A, never conflated with False).
        verification_failed = (
            verification_record is not None
            and verification_record.verification_status != "successful_simulation"
        )
        if not verification_failed:
            rollback_required = None
            rollback_success = None
        else:
            rollback_required = rollback_record is not None
            rollback_success = (
                rollback_record.state == "synthetic_rollback_completed"
                if rollback_record is not None
                else False
            )

        rollback = {
            "rollback_required": rollback_required,
            "rollback_success": rollback_success,
        }

        return (
            cast(dict[str, object], ops),
            cast(dict[str, object], verification),
            cast(dict[str, object], rollback),
        )

    def _human_involvement_metrics(
        self, session: Session, experiment: ExperimentRecord
    ) -> dict[str, object]:
        approval_count = 0
        administrator_approval_count = 0
        analyst_approval_count = 0
        if experiment.orchestration_id is not None:
            statement = select(ApprovalRequestRecord).where(
                ApprovalRequestRecord.orchestration_id == experiment.orchestration_id,
                ApprovalRequestRecord.approval_state == "approved",
            )
            for approval in session.scalars(statement):
                approval_count += 1
                if approval.required_role == "administrator":
                    administrator_approval_count += 1
                elif approval.required_role == "analyst":
                    analyst_approval_count += 1

        return {
            "approval_count": approval_count,
            "administrator_approval_count": administrator_approval_count,
            "analyst_approval_count": analyst_approval_count,
            "autonomous_action_count": experiment.autonomous_action_count,
            "manual_action_count": experiment.manual_action_count,
        }

    # ------------------------------------------------------------------
    # Normalized metrics
    # ------------------------------------------------------------------

    def _normalized_metrics(
        self, timeline: dict[str, float | None], raw: dict[str, object]
    ) -> dict[str, object]:
        metrics: dict[str, Metric] = {}

        detection_coverage = raw["detection_coverage"]
        metrics["detection_coverage"] = (
            _na("Scenario declares zero ground-truth (high/critical severity) attack steps.")
            if detection_coverage is None
            else _ok(_as_float(detection_coverage))
        )

        false_positive_rate = raw["false_positive_rate"]
        metrics["false_positive_rate"] = (
            _na("No anomalous detections were produced for this run.")
            if false_positive_rate is None
            else _ok(_as_float(false_positive_rate))
        )

        for key, before_key, after_key in (
            ("attack_path_reduction", "attack_paths_before", "attack_paths_after"),
            ("blast_radius_reduction", "blast_radius_before", "blast_radius_after"),
            (
                "critical_exposure_reduction",
                "critical_assets_exposed_before",
                "critical_assets_exposed_after",
            ),
        ):
            before = raw.get(before_key)
            after = raw.get(after_key)
            if before is None or after is None:
                metrics[key] = _na("Security evidence could not be computed for this run.")
                continue
            value, applicable = _reduction(_as_int(before), _as_int(after))
            metrics[key] = (
                _ok(value) if applicable and value is not None else _na("Before-count was zero.")
            )

        # DetectionTimeliness: per spec Section 17, a defined 0.0 when never
        # detected - always applicable, never N/A.
        horizon = timeline.get("experiment_horizon_sim")
        time_to_first_detection = raw.get("time_to_first_detection")
        if time_to_first_detection is None or not horizon:
            metrics["detection_timeliness"] = _ok(0.0, "Never detected within this experiment.")
        else:
            metrics["detection_timeliness"] = _ok(
                round(1 - min(1.0, _as_float(time_to_first_detection) / horizon), 6)
            )

        # RecoveryTimeliness: per spec Section 18, a defined 0.0 unless a
        # verified recovery was actually reached - always applicable.
        time_to_verified_recovery = raw.get("time_to_verified_recovery")
        recovery_verified = raw.get("verification_success") is True or (
            raw.get("rollback_success") is True
        )
        if not recovery_verified or time_to_verified_recovery is None or not horizon:
            metrics["recovery_timeliness"] = _ok(0.0, "No verified recovery was reached.")
        else:
            metrics["recovery_timeliness"] = _ok(
                round(1 - min(1.0, _as_float(time_to_verified_recovery) / horizon), 6)
            )

        return {name: metric.to_json() for name, metric in metrics.items()}


evaluation_metrics_service = EvaluationMetricsService()
