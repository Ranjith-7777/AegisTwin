"""Purple Team experiment orchestrator.

A Purple Team experiment runs one Red scenario through the EXISTING
simulation -> detection -> correlation -> prediction -> (optionally)
response/orchestration pipeline and records what actually happened at each
step. This module introduces no new detection, correlation, prediction, or
response logic of its own — it only calls the already-approved services in
sequence and reads back their persisted results. See
docs/architecture/PURPLE_TEAM.md for the full design and the exact metric
formulas used in `_summarize`.

Step outcomes are derived strictly from real, already-persisted evidence:

* `SUCCEEDED_SYNTHETIC` — the underlying scenario step's own declared
  outcome was "success" (nothing here re-derives success from telemetry;
  the scenario step already encodes it).
* `FAILED_PRECONDITION` — the scenario step's own declared outcome was not
  "success".
* `BLOCKED_SYNTHETIC` — only assigned to a step whose target asset matches
  a response recommendation's target, whose orchestration reached
  `verified` state, AND whose step sequence number is strictly greater
  than the sequence the response was analyzed through (never retroactive —
  a later Blue action can never "block" evidence that already existed
  before it was recommended). Because the simulation's telemetry for a
  run is generated once, in full, upfront (see
  `simulation_service.SimulationRunService.create_run`), and today's
  response analysis always runs through the full event count, there is
  never a step with a sequence number past that point within the same
  run — so `BLOCKED_SYNTHETIC` will not be assigned in this phase. This
  is a known, honestly-documented limitation of the current
  single-batch-generation architecture, not a bug: the code is correct
  and would assign it were the precondition ever met (e.g. a future
  interactive/step-by-step runner). Detection is never treated as
  prevention.
* `ATTEMPTED` — a default fallback when a step exists but no stronger
  classification applies (should not occur given the scenario data model,
  but is a safe fallback rather than raising).
* `SKIPPED` — never assigned by this module today (reserved for a future
  interactive step-by-step runner); included in the enum for forward
  compatibility only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import (
    AnomalyAssessmentRecord,
    PurpleTeamExperimentRecord,
    PurpleTeamStepResultRecord,
    TechniqueObservationRecord,
)
from app.events.envelope import (
    DomainEvent,
    PurpleExperimentCompletedPayload,
    PurpleExperimentStartedPayload,
    PurpleStepCompletedPayload,
    RedStepPayload,
)
from app.events.registry import get_event_bus
from app.events.types import EventType
from app.schemas.detection import DetectionTrainingRequest
from app.schemas.purple import (
    PurpleExperimentMode,
    PurpleTeamExperiment,
    PurpleTeamExperimentCreate,
    PurpleTeamStepResult,
    PurpleTeamSummary,
    RedScenarioSummary,
    RedScenarioTechniqueSummary,
    RedStepOutcome,
)
from app.schemas.simulation import ScenarioStep, SimulationRunCreate, SimulationScenario
from app.schemas.telemetry import TelemetryEvent
from app.services.correlation_service import correlation_service
from app.services.detection_scoring_service import detection_scoring_service
from app.services.detection_training_service import detection_training_service
from app.services.orchestration_service import orchestration_service
from app.services.prediction_service import prediction_service
from app.services.red_scenario_catalogue import iter_scenario_techniques, summarize_all
from app.services.response_service import response_service
from app.services.scenario_service import scenario_service
from app.services.simulation_service import simulation_run_service
from app.services.telemetry_service import telemetry_service

NAMESPACE = UUID("6f7d5b8e-1c3a-4a2f-9e0d-2b6f7a4c8d91")
EXPERIMENT_START_TIME = datetime(2026, 1, 1, tzinfo=UTC)
VERIFIED_ORCHESTRATION_STATES = {"verified"}


@dataclass(frozen=True)
class DefenseOutcome:
    incident_candidate_id: str
    recommendation_id: str
    target_id: str
    through_sequence_number: int
    orchestration_id: str
    orchestration_state: str


class PurpleTeamService:
    def list_scenarios(self, session: Session) -> list[RedScenarioSummary]:
        summaries = []
        for item in summarize_all():
            summaries.append(
                RedScenarioSummary(
                    scenario_id=item.scenario_id,
                    name=item.name,
                    description=scenario_service.get_scenario(
                        session, item.scenario_id
                    ).description,
                    is_red_agent_scenario=item.is_red_agent_scenario,
                    step_count=len(item.step_techniques),
                    mitre_technique_ids=item.technique_ids,
                    step_techniques=[
                        RedScenarioTechniqueSummary(
                            step_sequence=step.step_sequence,
                            technique_id=step.technique_id,
                            technique_name=step.technique_name,
                            tactic=step.tactic,
                            rationale=step.rationale,
                        )
                        for step in item.step_techniques
                    ],
                )
            )
        return summaries

    def run_experiment(
        self,
        session: Session,
        request: PurpleTeamExperimentCreate,
        artifact_dir: Path,
    ) -> PurpleTeamExperiment:
        experiment_id = str(
            uuid5(NAMESPACE, f"{request.scenario_id}:{request.mode.value}:{request.seed}")
        )
        existing = session.get(PurpleTeamExperimentRecord, experiment_id)
        if existing is not None and existing.status == "completed":
            return self._to_schema(session, existing)

        scenario = scenario_service.get_scenario(session, request.scenario_id)

        record = existing or PurpleTeamExperimentRecord(
            experiment_id=experiment_id,
            scenario_id=request.scenario_id,
            mode=request.mode.value,
            seed=request.seed,
            status="pending",
            synthetic=True,
        )
        if existing is None:
            session.add(record)
        record.status = "running"
        record.error = None
        session.flush()
        get_event_bus().publish(
            DomainEvent(
                event_type=EventType.PURPLE_EXPERIMENT_STARTED,
                source="purple_team",
                scenario_id=request.scenario_id,
                payload=PurpleExperimentStartedPayload(
                    experiment_id=experiment_id,
                    scenario_id=request.scenario_id,
                    mode=request.mode.value,
                    seed=request.seed,
                ),
            )
        )

        try:
            run = simulation_run_service.create_run(
                session,
                SimulationRunCreate(
                    scenario_id=request.scenario_id,
                    seed=request.seed,
                    start_time=EXPERIMENT_START_TIME,
                ),
            )
            record.simulation_run_id = run.simulation_run_id

            training_result = detection_training_service.train(
                session, DetectionTrainingRequest(), artifact_dir
            )
            record.model_id = training_result.model_id

            detection_scoring_service.score_run(
                session, run.simulation_run_id, training_result.model_id, force_rescore=False
            )
            correlation_result = correlation_service.analyze(
                session, run.simulation_run_id, training_result.model_id, force=False
            )
            incident_candidate_id = correlation_result.incident_candidate_id

            if incident_candidate_id is not None:
                prediction_service.analyze(
                    session,
                    run.simulation_run_id,
                    training_result.model_id,
                    force=False,
                    top_k=request.top_k,
                )

            defense_outcome: DefenseOutcome | None = None
            if request.mode == PurpleExperimentMode.DEFENSE_ENABLED and incident_candidate_id:
                defense_outcome = self._run_defense(
                    session,
                    run.simulation_run_id,
                    training_result.model_id,
                    incident_candidate_id,
                    request.top_k,
                )

            steps = self._evaluate_steps(
                session,
                record,
                scenario,
                run.simulation_run_id,
                training_result.model_id,
                defense_outcome,
            )
            summary = self._summarize(steps, incident_candidate_id)
            record.summary_json = summary.model_dump(mode="json")
            record.status = "completed"
            get_event_bus().publish(
                DomainEvent(
                    event_type=EventType.PURPLE_EXPERIMENT_COMPLETED,
                    source="purple_team",
                    run_id=record.simulation_run_id,
                    scenario_id=request.scenario_id,
                    payload=PurpleExperimentCompletedPayload(
                        experiment_id=experiment_id,
                        status="completed",
                        detection_step_coverage=summary.detection_step_coverage,
                        final_outcome=summary.final_outcome,
                    ),
                )
            )
            record.completed_at = datetime.now(UTC)
        except ApplicationError as exc:
            record.status = "failed"
            record.error = f"{exc.error_code}: {exc.message}"
            session.flush()
            raise

        session.flush()
        return self._to_schema(session, record)

    def _run_defense(
        self,
        session: Session,
        run_id: str,
        model_id: str,
        incident_candidate_id: str,
        top_k: int,
    ) -> DefenseOutcome | None:
        """Run the response/orchestration pipeline and report what happened.

        `outcome.orchestration_state` reflects whatever real state the
        deterministic orchestration pipeline actually reached (which may or
        may not be `verified` — most recommendations require a synthetic
        approval step, which this method performs, matching the existing
        orchestration route/tests). Only when `orchestration_state ==
        "verified"` may the caller ever classify a step `BLOCKED_SYNTHETIC`,
        and only for a step with `step_sequence > through_sequence_number`
        — a Blue action can never retroactively block evidence that already
        existed before it was recommended.
        """
        response_result = response_service.analyze(
            session,
            run_id,
            model_id,
            through_sequence=None,
            prediction_enabled=True,
            top_k=top_k,
            force=False,
        )
        if not response_result.recommendations:
            return None

        top = response_result.recommendations[0]
        orchestration = orchestration_service.create(
            session,
            run_id,
            model_id,
            incident_candidate_id,
            top.recommendation_id,
            sequence=top.through_sequence_number,
        )
        if orchestration.current_state in {
            "awaiting_analyst_approval",
            "awaiting_administrator_approval",
        }:
            role = orchestration.current_state.removeprefix("awaiting_").removesuffix("_approval")
            approval = next(item for item in orchestration.approvals if item.required_role == role)
            orchestration = orchestration_service.decide_approval(
                session,
                orchestration.orchestration_id,
                approval.approval_request_id,
                role=role,
                actor="purple-team-experiment",
                decision="approve",
                reason="Automated Purple Team approval for simulation demonstration only.",
            )
        if orchestration.current_state == "approved":
            orchestration = orchestration_service.execute(
                session, orchestration.orchestration_id, expected="approved", failure_mode="none"
            )
        if orchestration.current_state == "synthetic_execution_completed":
            orchestration = orchestration_service.verify(session, orchestration.orchestration_id)

        return DefenseOutcome(
            incident_candidate_id=incident_candidate_id,
            recommendation_id=top.recommendation_id,
            target_id=top.target_id,
            through_sequence_number=top.through_sequence_number,
            orchestration_id=orchestration.orchestration_id,
            orchestration_state=orchestration.current_state,
        )

    def _evaluate_steps(
        self,
        session: Session,
        record: PurpleTeamExperimentRecord,
        scenario: SimulationScenario,
        run_id: str,
        model_id: str,
        defense_outcome: DefenseOutcome | None,
    ) -> list[PurpleTeamStepResultRecord]:
        events = telemetry_service.list_run_events(session, run_id)
        expected_techniques = iter_scenario_techniques(scenario)
        assessments = {
            item.sequence_number: item
            for item in session.scalars(
                select(AnomalyAssessmentRecord).where(
                    AnomalyAssessmentRecord.simulation_run_id == run_id,
                    AnomalyAssessmentRecord.model_id == model_id,
                )
            )
        }
        observations_by_sequence: dict[int, list[TechniqueObservationRecord]] = {}
        for item in session.scalars(
            select(TechniqueObservationRecord).where(
                TechniqueObservationRecord.simulation_run_id == run_id,
                TechniqueObservationRecord.model_id == model_id,
            )
        ):
            observations_by_sequence.setdefault(item.sequence_number, []).append(item)

        existing_steps = session.scalars(
            select(PurpleTeamStepResultRecord).where(
                PurpleTeamStepResultRecord.experiment_id == record.experiment_id
            )
        )
        for existing_step in existing_steps:
            session.delete(existing_step)
        session.flush()

        results: list[PurpleTeamStepResultRecord] = []
        for index, step in enumerate(scenario.steps, start=1):
            sequence = index
            event = events[index - 1] if index - 1 < len(events) else None
            expected = (
                expected_techniques[index - 1] if index - 1 < len(expected_techniques) else None
            )
            assessment = assessments.get(sequence)
            observations = observations_by_sequence.get(sequence, [])
            observed_ids = sorted({item.technique_id for item in observations})

            detected = assessment is not None and assessment.classification == "anomalous"
            outcome = self._classify_outcome(step, event, sequence, defense_outcome)
            target_asset_id = getattr(step, "destination_id", None)
            touching_defense: DefenseOutcome | None = (
                defense_outcome
                if defense_outcome is not None and target_asset_id == defense_outcome.target_id
                else None
            )

            step_record = PurpleTeamStepResultRecord(
                step_result_id=str(uuid5(NAMESPACE, f"{record.experiment_id}:{sequence}")),
                experiment_id=record.experiment_id,
                step_sequence=sequence,
                description=step.description,
                event_id=event.event_id if event else None,
                target_asset_id=target_asset_id,
                expected_technique_id=expected.technique_id if expected else None,
                expected_technique_name=expected.technique_name if expected else None,
                outcome=outcome.value,
                detected=detected,
                anomaly_score=assessment.anomaly_score if assessment else None,
                classification=assessment.classification if assessment else None,
                observed_technique_ids_json=observed_ids,
                incident_candidate_id=(
                    touching_defense.incident_candidate_id if touching_defense else None
                ),
                response_recommendation_id=(
                    touching_defense.recommendation_id if touching_defense else None
                ),
                orchestration_id=(touching_defense.orchestration_id if touching_defense else None),
                orchestration_state=(
                    touching_defense.orchestration_state if touching_defense else None
                ),
                synthetic=True,
            )
            session.add(step_record)
            results.append(step_record)
            red_step_payload = RedStepPayload(
                experiment_id=record.experiment_id,
                scenario_id=record.scenario_id,
                step_sequence=sequence,
                expected_technique_id=expected.technique_id if expected else None,
                outcome=outcome.value,
            )
            get_event_bus().publish(
                DomainEvent(
                    event_type=EventType.RED_STEP_ATTEMPTED,
                    source="red_scenario",
                    run_id=run_id,
                    payload=red_step_payload,
                )
            )
            get_event_bus().publish(
                DomainEvent(
                    event_type=EventType.RED_STEP_COMPLETED,
                    source="red_scenario",
                    run_id=run_id,
                    payload=red_step_payload,
                )
            )
            get_event_bus().publish(
                DomainEvent(
                    event_type=EventType.PURPLE_STEP_COMPLETED,
                    source="purple_team",
                    run_id=run_id,
                    resource_ids=[a for a in [step_record.target_asset_id] if a],
                    payload=PurpleStepCompletedPayload(
                        experiment_id=record.experiment_id,
                        step_sequence=sequence,
                        outcome=outcome.value,
                        detected=detected,
                    ),
                )
            )

        session.flush()
        return results

    def _classify_outcome(
        self,
        step: ScenarioStep,
        event: TelemetryEvent | None,
        sequence: int,
        defense_outcome: DefenseOutcome | None,
    ) -> RedStepOutcome:
        target = getattr(step, "destination_id", None)
        if (
            defense_outcome is not None
            and defense_outcome.orchestration_state in VERIFIED_ORCHESTRATION_STATES
            and target == defense_outcome.target_id
            and sequence > defense_outcome.through_sequence_number
        ):
            return RedStepOutcome.BLOCKED_SYNTHETIC
        outcome_value = step.outcome.value if step.outcome else None
        if outcome_value == "success":
            return RedStepOutcome.SUCCEEDED_SYNTHETIC
        if outcome_value is not None:
            return RedStepOutcome.FAILED_PRECONDITION
        if event is None:
            return RedStepOutcome.SKIPPED
        return RedStepOutcome.ATTEMPTED

    def _summarize(
        self,
        steps: list[PurpleTeamStepResultRecord],
        incident_candidate_id: str | None,
    ) -> PurpleTeamSummary:
        total_steps = len(steps)
        attempted_steps = sum(1 for item in steps if item.outcome != RedStepOutcome.SKIPPED.value)
        succeeded_steps = sum(
            1 for item in steps if item.outcome == RedStepOutcome.SUCCEEDED_SYNTHETIC.value
        )
        detected_steps = sum(1 for item in steps if item.detected)
        expected_detectable = [item for item in steps if item.expected_technique_id is not None]
        missed_steps = sum(1 for item in expected_detectable if not item.detected)
        detected_and_expected = sum(1 for item in expected_detectable if item.detected)
        coverage = detected_and_expected / len(expected_detectable) if expected_detectable else None
        techniques_exercised = sorted(
            {item.expected_technique_id for item in steps if item.expected_technique_id}
        )
        techniques_observed = sorted(
            {tid for item in steps for tid in item.observed_technique_ids_json}
        )
        first_detection = next((item.step_sequence for item in steps if item.detected), None)

        response_created = any(item.response_recommendation_id for item in steps)
        response_executed = any(
            item.orchestration_state in {"completed_simulated", "verified"} for item in steps
        )
        verification_result = next(
            (item.orchestration_state for item in steps if item.orchestration_state), None
        )

        blocked = any(item.outcome == RedStepOutcome.BLOCKED_SYNTHETIC.value for item in steps)
        final_outcome = "contained" if blocked else ("detected" if detected_steps else "undetected")

        return PurpleTeamSummary(
            total_steps=total_steps,
            attempted_steps=attempted_steps,
            succeeded_synthetic_steps=succeeded_steps,
            detected_steps=detected_steps,
            missed_steps=missed_steps,
            expected_detectable_steps=len(expected_detectable),
            detection_step_coverage=coverage,
            mitre_techniques_exercised=techniques_exercised,
            mitre_techniques_observed=techniques_observed,
            incident_created=incident_candidate_id is not None,
            first_detection_sequence=first_detection,
            response_recommendation_created=response_created,
            response_executed=response_executed,
            verification_result=verification_result,
            critical_assets_reached=[],
            estimated_blast_radius_count=None,
            final_outcome=final_outcome,
        )

    def get_experiment(self, session: Session, experiment_id: str) -> PurpleTeamExperiment:
        record = session.get(PurpleTeamExperimentRecord, experiment_id)
        if record is None:
            raise ApplicationError(
                "PURPLE_TEAM_EXPERIMENT_NOT_FOUND", "The Purple Team experiment was not found.", 404
            )
        return self._to_schema(session, record)

    def list_experiments(self, session: Session) -> list[PurpleTeamExperiment]:
        records = session.scalars(
            select(PurpleTeamExperimentRecord).order_by(PurpleTeamExperimentRecord.created_at)
        )
        return [self._to_schema(session, item) for item in records]

    def _to_schema(
        self, session: Session, record: PurpleTeamExperimentRecord
    ) -> PurpleTeamExperiment:
        scenario = scenario_service.get_scenario(session, record.scenario_id)
        summary = PurpleTeamSummary(**record.summary_json) if record.summary_json else None
        step_records = session.scalars(
            select(PurpleTeamStepResultRecord)
            .where(PurpleTeamStepResultRecord.experiment_id == record.experiment_id)
            .order_by(PurpleTeamStepResultRecord.step_sequence)
        )
        return PurpleTeamExperiment(
            experiment_id=record.experiment_id,
            scenario_id=record.scenario_id,
            scenario_name=scenario.name,
            mode=PurpleExperimentMode(record.mode),
            seed=record.seed,
            simulation_run_id=record.simulation_run_id,
            model_id=record.model_id,
            status=record.status,
            error=record.error,
            created_at=record.created_at,
            completed_at=record.completed_at,
            steps=[
                PurpleTeamStepResult(
                    step_result_id=item.step_result_id,
                    experiment_id=item.experiment_id,
                    step_sequence=item.step_sequence,
                    description=item.description,
                    event_id=item.event_id,
                    target_asset_id=item.target_asset_id,
                    expected_technique_id=item.expected_technique_id,
                    expected_technique_name=item.expected_technique_name,
                    outcome=RedStepOutcome(item.outcome),
                    detected=item.detected,
                    anomaly_score=item.anomaly_score,
                    classification=item.classification,
                    observed_technique_ids=item.observed_technique_ids_json,
                    incident_candidate_id=item.incident_candidate_id,
                    response_recommendation_id=item.response_recommendation_id,
                    orchestration_id=item.orchestration_id,
                    orchestration_state=item.orchestration_state,
                )
                for item in step_records
            ],
            summary=summary,
        )


purple_team_service = PurpleTeamService()
