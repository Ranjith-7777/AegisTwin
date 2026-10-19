"""Evaluate one terminal synthetic workflow from its persisted evidence.

This adapter creates an evaluation envelope around the original run; it
never invokes simulation, detection, correlation, planning or execution.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import (
    AnomalyAssessmentRecord,
    ApprovalRequestRecord,
    DetectionModelRecord,
    ExperimentMetricRecord,
    ExperimentRecord,
    IncidentCandidateRecord,
    ResponseOrchestrationRecord,
    ResponsePlanAssessmentRecord,
    ResponseRecommendationRecord,
    ResponseVerificationRecord,
    RollbackRecord,
    SimulationRunRecord,
    SyntheticExecutionRecord,
)
from app.services.evaluation.evaluation_pipeline import evaluate_experiment
from app.services.evaluation.experiment_service import RED_SCENARIO_VERSION
from app.services.scenario_service import scenario_service
from app.services.topology_service import TOPOLOGY_VERSION

TERMINAL_STATES = frozenset(
    {"verified", "synthetic_execution_failed", "synthetic_rollback_completed"}
)


class CompletedWorkflowEvaluationService:
    @staticmethod
    def _id(orchestration_id: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"aegisarena:completed-workflow:{orchestration_id}"))

    @staticmethod
    def _error(code: str, message: str) -> ApplicationError:
        return ApplicationError(code, message, 409)

    def evaluate(self, session: Session, orchestration_id: str) -> ExperimentRecord:
        orchestration = session.get(ResponseOrchestrationRecord, orchestration_id)
        if orchestration is None:
            raise ApplicationError(
                "ORCHESTRATION_NOT_FOUND", "The synthetic orchestration was not found.", 404
            )
        if orchestration.current_state not in TERMINAL_STATES:
            raise self._error(
                "WORKFLOW_EVALUATION_NOT_READY",
                "Evaluation requires a verified, rolled-back, or terminal failed-execution "
                f"workflow; current state is '{orchestration.current_state}'.",
            )

        run = session.get(SimulationRunRecord, orchestration.simulation_run_id)
        incident = session.get(IncidentCandidateRecord, orchestration.incident_candidate_id)
        model = session.get(DetectionModelRecord, orchestration.model_id)
        recommendation = session.get(
            ResponseRecommendationRecord, orchestration.selected_recommendation_id
        )
        if run is None or incident is None or model is None or recommendation is None:
            raise self._error(
                "WORKFLOW_EVIDENCE_INCOMPLETE",
                "The workflow is missing its persisted run, incident, model, or recommendation.",
            )
        if run.status != "completed":
            raise self._error(
                "WORKFLOW_EVALUATION_NOT_READY",
                f"Simulation run '{run.simulation_run_id}' is not completed.",
            )
        if (
            incident.simulation_run_id != run.simulation_run_id
            or incident.model_id != orchestration.model_id
            or recommendation.simulation_run_id != run.simulation_run_id
            or recommendation.model_id != orchestration.model_id
            or recommendation.incident_candidate_id != incident.incident_candidate_id
            or recommendation.through_sequence_number != orchestration.through_sequence_number
        ):
            raise self._error(
                "WORKFLOW_EVIDENCE_MISMATCH",
                "The run, incident, model, recommendation and orchestration associations "
                "do not match.",
            )
        if not 1 <= orchestration.through_sequence_number <= run.event_count:
            raise self._error(
                "WORKFLOW_EVIDENCE_MISMATCH",
                "The orchestration evidence sequence is outside the persisted run.",
            )
        assessment_count = session.scalar(
            select(func.count(AnomalyAssessmentRecord.assessment_id)).where(
                AnomalyAssessmentRecord.simulation_run_id == run.simulation_run_id,
                AnomalyAssessmentRecord.model_id == orchestration.model_id,
            )
        )
        if not assessment_count:
            raise self._error(
                "WORKFLOW_EVIDENCE_INCOMPLETE",
                "No persisted anomaly assessments support this workflow evaluation.",
            )

        executions = list(
            session.scalars(
                select(SyntheticExecutionRecord).where(
                    SyntheticExecutionRecord.orchestration_id == orchestration_id
                )
            )
        )
        verifications = list(
            session.scalars(
                select(ResponseVerificationRecord).where(
                    ResponseVerificationRecord.orchestration_id == orchestration_id
                )
            )
        )
        rollbacks = list(
            session.scalars(
                select(RollbackRecord).where(RollbackRecord.orchestration_id == orchestration_id)
            )
        )
        if len(executions) != 1 or len(verifications) > 1 or len(rollbacks) > 1:
            raise self._error(
                "WORKFLOW_EVIDENCE_INCOMPLETE",
                "A terminal workflow must have exactly one execution and at most one "
                "verification and rollback.",
            )
        execution = executions[0]
        verification = verifications[0] if verifications else None
        rollback = rollbacks[0] if rollbacks else None
        self._validate_terminal_evidence(orchestration, execution, verification, rollback)

        existing = list(
            session.scalars(
                select(ExperimentRecord)
                .where(
                    ExperimentRecord.orchestration_id == orchestration_id,
                    ExperimentRecord.status == "completed",
                )
                .order_by(ExperimentRecord.created_at.desc())
            )
        )
        if existing:
            for record in existing:
                self._validate_existing(record, orchestration)
            record = existing[0]
            if session.get(ExperimentMetricRecord, record.experiment_id) is None:
                evaluate_experiment(session, record.experiment_id)
            return record

        assessment = session.scalar(
            select(ResponsePlanAssessmentRecord).where(
                ResponsePlanAssessmentRecord.simulation_run_id == run.simulation_run_id,
                ResponsePlanAssessmentRecord.model_id == orchestration.model_id,
                ResponsePlanAssessmentRecord.incident_candidate_id
                == incident.incident_candidate_id,
                ResponsePlanAssessmentRecord.through_sequence_number
                == orchestration.through_sequence_number,
            )
        )
        approved_count = int(
            session.scalar(
                select(func.count(ApprovalRequestRecord.approval_request_id)).where(
                    ApprovalRequestRecord.orchestration_id == orchestration_id,
                    ApprovalRequestRecord.approval_state == "approved",
                )
            )
            or 0
        )
        terminal_at = (
            rollback.completed_at
            if rollback is not None
            else verification.completed_at
            if verification is not None
            else execution.completed_at
        )
        evidence_ids = {
            "simulation_run_id": run.simulation_run_id,
            "incident_candidate_id": incident.incident_candidate_id,
            "orchestration_id": orchestration_id,
            "execution_id": execution.execution_id,
            "verification_id": verification.verification_id if verification else None,
            "rollback_id": rollback.rollback_id if rollback else None,
        }
        now = datetime.now(UTC)
        record = ExperimentRecord(
            experiment_id=self._id(orchestration_id),
            evaluation_source="completed_workflow",
            scenario_id=run.scenario_id,
            scenario_name=scenario_service.get_scenario(session, run.scenario_id).name,
            seed=run.seed,
            defence_mode="agentic",
            detection_model_id=orchestration.model_id,
            topology_version=TOPOLOGY_VERSION,
            red_scenario_version=RED_SCENARIO_VERSION,
            autonomy_mode=assessment.autonomy_mode if assessment is not None else None,
            configuration_json={
                "evaluation_source": "completed_workflow",
                "workflow_terminal_state": orchestration.current_state,
                "through_sequence": orchestration.through_sequence_number,
                "source_evidence": evidence_ids,
                "measurement_note": "Computed from persisted workflow evidence; no attack replay.",
            },
            started_at=orchestration.created_at,
            ended_at=terminal_at or orchestration.updated_at,
            run_id=run.simulation_run_id,
            incident_candidate_id=incident.incident_candidate_id,
            orchestration_id=orchestration_id,
            status="completed",
            failure_stage=None,
            failure_code=None,
            failure_message=None,
            verification_status=(
                verification.verification_status if verification is not None else None
            ),
            batch_id=None,
            rerun_of_experiment_id=None,
            changed_node_ids_json=list(execution.changed_node_ids_json),
            changed_edge_ids_json=list(execution.changed_edge_ids_json),
            autonomous_action_count=1 if approved_count == 0 else 0,
            manual_action_count=1 if approved_count > 0 else 0,
            workflow_latency_ms=None,
            synthetic=True,
            created_at=now,
            evaluation_action_id=None,
            perturbed_model_id=None,
        )
        session.add(record)
        session.commit()
        evaluate_experiment(session, record.experiment_id)
        session.refresh(record)
        return record

    def _validate_terminal_evidence(
        self,
        orchestration: ResponseOrchestrationRecord,
        execution: SyntheticExecutionRecord,
        verification: ResponseVerificationRecord | None,
        rollback: RollbackRecord | None,
    ) -> None:
        state = orchestration.current_state
        if verification is not None and verification.execution_id != execution.execution_id:
            raise self._error(
                "WORKFLOW_EVIDENCE_MISMATCH",
                "Verification belongs to a different synthetic execution.",
            )
        if rollback is not None and rollback.execution_id != execution.execution_id:
            raise self._error(
                "WORKFLOW_EVIDENCE_MISMATCH", "Rollback belongs to a different synthetic execution."
            )
        if state == "verified" and (
            execution.execution_state != "completed_simulated"
            or verification is None
            or verification.verification_status != "successful_simulation"
            or rollback is not None
        ):
            raise self._error(
                "WORKFLOW_EVIDENCE_INCOMPLETE",
                "Verified workflow state is not supported by a successful execution and "
                "verification.",
            )
        if state == "synthetic_execution_failed" and (
            execution.execution_state != "failed_simulated"
            or verification is not None
            or rollback is not None
        ):
            raise self._error(
                "WORKFLOW_EVIDENCE_INCOMPLETE",
                "Failed-execution state contains inconsistent verification or rollback evidence.",
            )
        if state == "synthetic_rollback_completed" and (
            execution.execution_state != "rolled_back_simulated"
            or verification is None
            or rollback is None
            or rollback.state != "synthetic_rollback_completed"
        ):
            raise self._error(
                "WORKFLOW_EVIDENCE_INCOMPLETE",
                "Rolled-back workflow state is missing completed verification or rollback "
                "evidence.",
            )

    def _validate_existing(
        self, record: ExperimentRecord, orchestration: ResponseOrchestrationRecord
    ) -> None:
        if (
            record.run_id != orchestration.simulation_run_id
            or record.incident_candidate_id != orchestration.incident_candidate_id
            or orchestration.model_id not in {record.detection_model_id, record.perturbed_model_id}
            or record.orchestration_id != orchestration.orchestration_id
        ):
            raise self._error(
                "WORKFLOW_EVALUATION_ASSOCIATION_MISMATCH",
                "An existing evaluation record is attributed to different workflow evidence.",
            )


completed_workflow_evaluation_service = CompletedWorkflowEvaluationService()
