"""Phase 4 Workflow Coordinator.

This is explicitly NOT an 8th agent (see docs/architecture/
AGENT_ARCHITECTURE.md "Workflow Coordinator" and app/schemas/agents.py). It
makes no independent security, policy, approval, execution or verification
decision of its own - every decision is still made by the named Blue
agents and the policy engine it calls, in exactly the sequence a human
operator would drive through the API one step at a time:

    blue_planning_service.compare()   (Response Planner + Impact Simulation
                                        + Safety Governor evidence, ranked)
        -> orchestration_service.create()   (Safety Governor + Approval
                                              Router decide permit/route)
        -> [only in AUTONOMOUS mode, only if the Approval Router already
            routed the plan to "approved"]
           orchestration_service.execute()  (Synthetic Execution Agent)
        -> orchestration_service.verify()   (Verification Agent, which
                                              itself triggers automatic
                                              rollback on policy failure)

RECOMMEND mode stops after the comparison (never creates an orchestration).
APPROVAL_REQUIRED and a non-automatic AUTONOMOUS routing stop after
orchestration creation, awaiting a human approval decision. Only a plan the
Approval Router already marked "automatic" is auto-executed - the
Coordinator itself never overrides that routing.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ResponseOrchestrationRecord, ResponsePlanAssessmentRecord
from app.schemas.workflow import WorkflowRunResult
from app.services.autonomy_service import autonomy_service
from app.services.blue_planning_service import blue_planning_service
from app.services.orchestration_service import orchestration_service

logger = logging.getLogger(__name__)


class WorkflowCoordinator:
    def run(
        self,
        session: Session,
        run_id: str,
        model_id: str,
        incident_candidate_id: str,
        through_sequence: int,
        top_k: int = 5,
    ) -> WorkflowRunResult:
        logger.info(
            "workflow_started run_id=%s model_id=%s incident_id=%s through_sequence=%d",
            run_id,
            model_id,
            incident_candidate_id,
            through_sequence,
        )
        result = self._run(
            session, run_id, model_id, incident_candidate_id, through_sequence, top_k
        )
        logger.info(
            "workflow_finished run_id=%s autonomy_mode=%s orchestration_id=%s state=%s "
            "auto_executed=%s auto_verified=%s stopped_reason=%r",
            run_id,
            result.autonomy_mode,
            result.orchestration.orchestration_id if result.orchestration else None,
            result.orchestration.current_state if result.orchestration else None,
            result.auto_executed,
            result.auto_verified,
            result.stopped_reason,
        )
        return result

    def _run(
        self,
        session: Session,
        run_id: str,
        model_id: str,
        incident_candidate_id: str,
        through_sequence: int,
        top_k: int,
    ) -> WorkflowRunResult:
        autonomy_mode = autonomy_service.require_mode(session).value
        if autonomy_mode == "observe":
            # OBSERVE means detection/evidence only - candidate plans must
            # never be generated, ranked, or persisted in this mode, so the
            # autonomy check happens BEFORE blue_planning_service.compare()
            # is ever called (a real Phase 4 correction: an earlier version
            # called compare() unconditionally and only checked the mode
            # afterward, which silently generated and persisted a
            # ResponsePlanAssessmentRecord even in OBSERVE mode).
            return WorkflowRunResult(
                comparison=None,
                orchestration=None,
                autonomy_mode=autonomy_mode,
                auto_executed=False,
                auto_verified=False,
                stopped_reason="Autonomy mode is OBSERVE: evidence only, no response plan "
                "is generated or executed.",
            )

        comparison = blue_planning_service.compare(
            session, run_id, model_id, incident_candidate_id, through_sequence, top_k
        )
        if comparison.recommended_recommendation_id is None:
            return WorkflowRunResult(
                comparison=comparison,
                orchestration=None,
                autonomy_mode=autonomy_mode,
                auto_executed=False,
                auto_verified=False,
                stopped_reason="No candidate plan passed every applicable policy - "
                "nothing to recommend.",
            )
        if autonomy_mode == "recommend":
            return WorkflowRunResult(
                comparison=comparison,
                orchestration=None,
                autonomy_mode=autonomy_mode,
                auto_executed=False,
                auto_verified=False,
                stopped_reason="Autonomy mode is RECOMMEND: candidate plans are ranked but "
                "never automatically orchestrated or executed.",
            )

        orchestration = orchestration_service.create(
            session,
            run_id,
            model_id,
            incident_candidate_id,
            comparison.recommended_recommendation_id,
            through_sequence,
        )
        if autonomy_mode == "approval_required" or orchestration.current_state != "approved":
            return WorkflowRunResult(
                comparison=comparison,
                orchestration=orchestration,
                autonomy_mode=autonomy_mode,
                auto_executed=False,
                auto_verified=False,
                stopped_reason=(
                    "Autonomy mode is APPROVAL_REQUIRED: execution requires an explicit "
                    "analyst/administrator approval decision."
                    if autonomy_mode == "approval_required"
                    else "The Approval Router did not route this plan to automatic "
                    f"execution (orchestration state is '{orchestration.current_state}') - "
                    "a human approval decision is required."
                ),
            )

        orchestration = orchestration_service.execute(
            session, orchestration.orchestration_id, None, "none"
        )
        auto_executed = orchestration.current_state == "synthetic_execution_completed"
        if not auto_executed:
            return WorkflowRunResult(
                comparison=comparison,
                orchestration=orchestration,
                autonomy_mode=autonomy_mode,
                auto_executed=False,
                auto_verified=False,
                stopped_reason=f"Synthetic execution did not complete (state is "
                f"'{orchestration.current_state}').",
            )
        orchestration = orchestration_service.verify(session, orchestration.orchestration_id)
        auto_verified = orchestration.current_state == "verified"
        return WorkflowRunResult(
            comparison=comparison,
            orchestration=orchestration,
            autonomy_mode=autonomy_mode,
            auto_executed=True,
            auto_verified=auto_verified,
            stopped_reason=(
                "Self-healing loop complete: executed and verified automatically."
                if auto_verified
                else "Verification did not confirm containment; automatic rollback policy "
                f"was evaluated (orchestration state is '{orchestration.current_state}')."
            ),
        )

    def restore(self, session: Session, run_id: str, model_id: str) -> WorkflowRunResult | None:
        """Rebuild the workflow result for a run purely from persisted records.

        Runs are deterministic, so replaying the same scenario/seed reuses a
        run that may already carry a ranked comparison and an orchestration.
        Restoring both together keeps every lifecycle stage consistent (a
        restored execution is never shown without the plan it executed).
        Nothing is recomputed; returns None when nothing was persisted.
        """

        orchestration_record = session.scalars(
            select(ResponseOrchestrationRecord)
            .where(
                ResponseOrchestrationRecord.simulation_run_id == run_id,
                ResponseOrchestrationRecord.model_id == model_id,
            )
            .order_by(ResponseOrchestrationRecord.updated_at.desc())
            .limit(1)
        ).first()
        if orchestration_record is not None:
            assessment_id = blue_planning_service.assessment_id(
                run_id,
                model_id,
                orchestration_record.incident_candidate_id,
                orchestration_record.through_sequence_number,
            )
        else:
            latest = session.scalars(
                select(ResponsePlanAssessmentRecord)
                .where(
                    ResponsePlanAssessmentRecord.simulation_run_id == run_id,
                    ResponsePlanAssessmentRecord.model_id == model_id,
                )
                .order_by(ResponsePlanAssessmentRecord.through_sequence_number.desc())
                .limit(1)
            ).first()
            if latest is None:
                return None
            assessment_id = latest.assessment_id
        comparison = blue_planning_service.load(session, assessment_id)
        orchestration = (
            orchestration_service.view(session, orchestration_record)
            if orchestration_record is not None
            else None
        )
        if comparison is None and orchestration is None:
            return None
        human_gate = orchestration is not None and any(
            approval.decided_by is not None for approval in orchestration.approvals
        )
        executed = orchestration is not None and bool(orchestration.executions)
        verified = orchestration is not None and any(
            item.verification_status == "successful_simulation"
            for item in orchestration.verifications
        )
        return WorkflowRunResult(
            comparison=comparison,
            orchestration=orchestration,
            autonomy_mode=comparison.autonomy_mode
            if comparison is not None
            else autonomy_service.require_mode(session).value,
            auto_executed=executed and not human_gate,
            auto_verified=verified and not human_gate,
            stopped_reason="Restored from persisted records of an earlier replay of this "
            "deterministic run; nothing was re-planned or re-executed.",
            restored=True,
        )


workflow_coordinator = WorkflowCoordinator()
