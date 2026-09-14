"""Phase 5 Experiment lifecycle orchestrator.

Runs identical scenario/telemetry/detection/correlation groundwork for
every defence mode - this is what makes `no_active_defence` a fair
baseline rather than a strawman: it still sees the same incident the other
three modes see, it just never acts on it (see
`app.services.evaluation.strategies`).

Status-transition semantics (corrected alongside the Rule-Based/ML-Assisted
Phase 4 isolation fix): `no_active_defence` and `rule_based`/`ml_assisted`
share the lifecycle `CREATED -> RUNNING_ATTACK -> DETECTING -> RESPONDING ->
COMPLETED` - there is no VERIFYING stage for them, because none of the three
ever produces a Phase 4 `ResponseOrchestrationRecord`/runs the Verification
Agent (`rule_based`/`ml_assisted` execute a real synthetic mutation via
`synthetic_mutation_service` and persist their own `EvaluationSyntheticAction
Record`, but that is not a Phase-4-style verification step). Only `agentic`
(the real `workflow_coordinator.run()` path) passes through VERIFYING, since
it alone produces a real orchestration for `orchestration_service.verify()`
to have run against.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.database.models import ExperimentRecord
from app.events.envelope import (
    DomainEvent,
    EvaluationDefenceCompletedPayload,
    EvaluationExperimentCompletedPayload,
    EvaluationExperimentFailedPayload,
    EvaluationExperimentStartedPayload,
)
from app.events.registry import get_event_bus
from app.events.types import EventType
from app.schemas.detection import DetectionTrainingRequest
from app.schemas.evaluation import DefenceMode, ExperimentCreate, ExperimentStatus
from app.schemas.simulation import SimulationRunCreate
from app.services.correlation_service import correlation_service
from app.services.detection_scoring_service import detection_scoring_service
from app.services.detection_training_service import detection_training_service
from app.services.evaluation.perturbation_service import (
    HIDDEN_EVENT_COUNT_KEY,
    HIDDEN_EVENT_IDS_KEY,
    apply_perturbation,
    materialize_perturbed_model,
    score_visible_events,
)
from app.services.evaluation.strategies import StrategyOutcome, get_strategy
from app.services.scenario_service import scenario_service
from app.services.simulation_service import simulation_run_service
from app.services.topology_service import TOPOLOGY_VERSION

# Fixed across every experiment so that comparisons between defence modes -
# and reproductions of the same experiment - are never confounded by a
# different attack timeline or replay speed. NEVER vary these per-experiment.
CANONICAL_START_TIME = datetime(2026, 1, 1, tzinfo=UTC)
CANONICAL_PLAYBACK_SPEED = 1.0

# A single canonical detection model configuration shared by every
# experiment, for the same fairness reason - the defence modes are being
# compared against each other, not against different detectors. Training is
# idempotent/deterministic (`DetectionTrainingService.train()` derives
# `model_id` from the dataset fingerprint and these parameters and returns
# the existing model unchanged if it already exists), so calling it once per
# experiment is cheap and safe.
CANONICAL_TRAINING_REQUEST = DetectionTrainingRequest()

RED_SCENARIO_VERSION = "red-scenario-catalogue-v1"


class ExperimentService:
    def create_and_run(
        self,
        session: Session,
        request: ExperimentCreate,
        artifact_dir: Path | None = None,
        batch_id: str | None = None,
    ) -> ExperimentRecord:
        resolved_artifact_dir = artifact_dir or get_settings().model_artifact_dir
        scenario = scenario_service.get_scenario(session, request.scenario_id)
        now = datetime.now(UTC)
        record = ExperimentRecord(
            experiment_id=str(uuid4()),
            scenario_id=request.scenario_id,
            scenario_name=scenario.name,
            seed=request.seed,
            defence_mode=request.defence_mode.value,
            detection_model_id=None,
            topology_version=TOPOLOGY_VERSION,
            red_scenario_version=RED_SCENARIO_VERSION,
            autonomy_mode=None,
            configuration_json={
                "scenario_id": request.scenario_id,
                "seed": request.seed,
                "defence_mode": request.defence_mode.value,
                "top_k": request.top_k,
                "through_sequence": request.through_sequence,
                "label": request.label,
                "notes": request.notes,
                "perturbation_id": request.perturbation_id,
                "perturbation_params": request.perturbation_params,
                "start_time": CANONICAL_START_TIME.isoformat(),
                "playback_speed": CANONICAL_PLAYBACK_SPEED,
                "training_request": CANONICAL_TRAINING_REQUEST.model_dump(mode="json"),
            },
            status=ExperimentStatus.CREATED.value,
            batch_id=batch_id,
            synthetic=True,
            created_at=now,
        )
        session.add(record)
        session.commit()

        try:
            record.status = ExperimentStatus.RUNNING_ATTACK.value
            record.started_at = datetime.now(UTC)
            session.commit()
            get_event_bus().publish(
                DomainEvent(
                    event_type=EventType.EVALUATION_EXPERIMENT_STARTED,
                    source="evaluation",
                    scenario_id=request.scenario_id,
                    correlation_id=record.experiment_id,
                    causation_id=batch_id,
                    resource_ids=[record.experiment_id],
                    payload=EvaluationExperimentStartedPayload(
                        experiment_id=record.experiment_id,
                        scenario_id=request.scenario_id,
                        seed=request.seed,
                        defence_mode=request.defence_mode.value,
                    ),
                )
            )
            run = simulation_run_service.create_run(
                session,
                SimulationRunCreate(
                    scenario_id=request.scenario_id,
                    seed=request.seed,
                    start_time=CANONICAL_START_TIME,
                    playback_speed=CANONICAL_PLAYBACK_SPEED,
                ),
            )
            record.run_id = run.simulation_run_id
            session.commit()

            # Phase 5 Section 38 (partial-observability robustness test):
            # compute this experiment's hidden-event-id set (empty unless
            # `request.perturbation_id` is recognised) and persist it onto
            # `configuration_json` for auditability, for
            # `metrics_service`/`mission_continuity_service`'s belt-and-
            # suspenders detection-metrics filtering, and - below - to drive
            # what actually gets (and does not get) real evidence under this
            # experiment's perturbed model identity. See
            # `perturbation_service` module docstring for the full
            # mechanism.
            hidden_event_ids = apply_perturbation(
                session, run.simulation_run_id, request.perturbation_id, request.perturbation_params
            )
            record.configuration_json = {
                **record.configuration_json,
                HIDDEN_EVENT_IDS_KEY: sorted(hidden_event_ids),
                HIDDEN_EVENT_COUNT_KEY: len(hidden_event_ids),
            }
            session.commit()

            record.status = ExperimentStatus.DETECTING.value
            session.commit()
            training_result = detection_training_service.train(
                session, CANONICAL_TRAINING_REQUEST, resolved_artifact_dir
            )
            record.detection_model_id = training_result.model_id
            session.commit()
            detection_scoring_service.score_run(
                session, run.simulation_run_id, training_result.model_id, force_rescore=False
            )

            # Perturbation robustness-test correction (Section 38): for a
            # perturbed experiment, everything downstream of this point -
            # correlation, and whichever defence strategy is dispatched -
            # must read evidence through a SEPARATE, perturbation-scoped
            # model identity whose persisted assessments genuinely omit the
            # hidden events' real signal, not the canonical
            # `training_result.model_id`. The canonical identity above is
            # still trained/scored in full and stays on
            # `record.detection_model_id` untouched, because real-outcome
            # measurement (`metrics_service._security_metrics`) must keep
            # reading real, unperturbed ground truth. See
            # `perturbation_service` module docstring.
            evidence_model_id = training_result.model_id
            if request.perturbation_id is not None:
                derived_model_id = materialize_perturbed_model(
                    session,
                    training_result.model_id,
                    request.perturbation_id,
                    request.perturbation_params or {},
                )
                score_visible_events(
                    session, run.simulation_run_id, derived_model_id, hidden_event_ids
                )
                record.perturbed_model_id = derived_model_id
                evidence_model_id = derived_model_id
                session.commit()

            # Correlation is common groundwork, not a defence decision - it
            # runs identically for all four modes, including
            # `no_active_defence`, so that mode still SEES the incident it
            # chooses not to act on. For a perturbed experiment, this reads
            # `evidence_model_id` (the perturbed identity) so the incident
            # candidate itself is formed from the degraded evidence set.
            correlation_result = correlation_service.analyze(
                session, run.simulation_run_id, evidence_model_id, force=False
            )
            record.incident_candidate_id = correlation_result.incident_candidate_id
            session.commit()

            record.status = ExperimentStatus.RESPONDING.value
            session.commit()
            # Real wall-clock latency of the whole defence-strategy dispatch,
            # measured at the coarsest reliable boundary (see
            # `ExperimentRecord.workflow_latency_ms` docstring and
            # docs/architecture for the granularity actually achieved in this
            # stage - finer-grained per-strategy planning/what-if timing was
            # deliberately not added here to avoid invasive Stage 1 changes).
            workflow_started = perf_counter()
            outcome = get_strategy(request.defence_mode).execute(
                session,
                record,
                run.simulation_run_id,
                evidence_model_id,
                correlation_result.incident_candidate_id,
                request.through_sequence,
            )
            record.workflow_latency_ms = round((perf_counter() - workflow_started) * 1000, 3)
            self._apply_outcome(session, record, request.defence_mode, outcome)
            get_event_bus().publish(
                DomainEvent(
                    event_type=EventType.EVALUATION_DEFENCE_COMPLETED,
                    source="evaluation",
                    run_id=run.simulation_run_id,
                    scenario_id=request.scenario_id,
                    incident_id=record.incident_candidate_id,
                    correlation_id=record.experiment_id,
                    causation_id=batch_id,
                    resource_ids=[
                        record.experiment_id,
                        *([record.orchestration_id] if record.orchestration_id else []),
                    ],
                    payload=EvaluationDefenceCompletedPayload(
                        experiment_id=record.experiment_id,
                        defence_mode=request.defence_mode.value,
                        orchestration_id=record.orchestration_id,
                        verification_status=record.verification_status,
                    ),
                )
            )

            record.status = ExperimentStatus.COMPLETED.value
            record.ended_at = datetime.now(UTC)
            session.commit()
            get_event_bus().publish(
                DomainEvent(
                    event_type=EventType.EVALUATION_EXPERIMENT_COMPLETED,
                    source="evaluation",
                    run_id=run.simulation_run_id,
                    scenario_id=request.scenario_id,
                    correlation_id=record.experiment_id,
                    causation_id=batch_id,
                    resource_ids=[record.experiment_id],
                    payload=EvaluationExperimentCompletedPayload(
                        experiment_id=record.experiment_id, status=record.status
                    ),
                )
            )
            return record
        except Exception as exc:
            session.rollback()
            failed_at_stage = record.status
            record.status = ExperimentStatus.FAILED.value
            record.failure_stage = failed_at_stage
            record.failure_code = type(exc).__name__
            record.failure_message = str(exc)[:1000]
            record.ended_at = datetime.now(UTC)
            session.commit()
            get_event_bus().publish(
                DomainEvent(
                    event_type=EventType.EVALUATION_EXPERIMENT_FAILED,
                    source="evaluation",
                    run_id=record.run_id,
                    scenario_id=request.scenario_id,
                    correlation_id=record.experiment_id,
                    causation_id=batch_id,
                    resource_ids=[record.experiment_id],
                    payload=EvaluationExperimentFailedPayload(
                        experiment_id=record.experiment_id,
                        failure_stage=record.failure_stage,
                        failure_code=record.failure_code,
                    ),
                )
            )
            return record

    @staticmethod
    def _apply_outcome(
        session: Session,
        record: ExperimentRecord,
        defence_mode: DefenceMode,
        outcome: StrategyOutcome,
    ) -> None:
        record.orchestration_id = outcome.orchestration_id
        record.evaluation_action_id = outcome.evaluation_action_id
        record.verification_status = outcome.verification_status
        record.changed_node_ids_json = list(outcome.changed_node_ids)
        record.changed_edge_ids_json = list(outcome.changed_edge_ids)
        record.autonomous_action_count = outcome.autonomous_action_count
        record.manual_action_count = outcome.manual_action_count
        if defence_mode == DefenceMode.AGENTIC:
            record.autonomy_mode = "autonomous"
        # Honest status transitions: only Agentic ever produces a Phase 4
        # `ResponseOrchestrationRecord` to verify, so only Agentic passes
        # through VERIFYING. Rule-Based/ML-Assisted execute a real synthetic
        # mutation (or honestly do nothing) but never run Phase 4's
        # Verification Agent - there is no Phase-4-style verification stage
        # for these two modes by design (see `strategies.py` module
        # docstring and `metrics_service.py`'s `verification_success`
        # handling), so their lifecycle goes straight from RESPONDING to
        # COMPLETED, same as `no_active_defence`.
        if outcome.orchestration_id is not None:
            record.status = ExperimentStatus.VERIFYING.value
        session.commit()

    def get(self, session: Session, experiment_id: str) -> ExperimentRecord:
        record = session.get(ExperimentRecord, experiment_id)
        if record is None:
            raise ApplicationError("EXPERIMENT_NOT_FOUND", "The experiment was not found.", 404)
        return record

    def list(
        self,
        session: Session,
        scenario_id: str | None = None,
        defence_mode: DefenceMode | None = None,
        seed: int | None = None,
        status: ExperimentStatus | None = None,
        batch_id: str | None = None,
    ) -> list[ExperimentRecord]:
        statement = select(ExperimentRecord)
        if scenario_id is not None:
            statement = statement.where(ExperimentRecord.scenario_id == scenario_id)
        if defence_mode is not None:
            statement = statement.where(ExperimentRecord.defence_mode == defence_mode.value)
        if seed is not None:
            statement = statement.where(ExperimentRecord.seed == seed)
        if status is not None:
            statement = statement.where(ExperimentRecord.status == status.value)
        if batch_id is not None:
            statement = statement.where(ExperimentRecord.batch_id == batch_id)
        statement = statement.order_by(ExperimentRecord.created_at.desc())
        return list(session.scalars(statement))


experiment_service = ExperimentService()
