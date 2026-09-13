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

from sqlalchemy.orm import Session

from app.schemas.workflow import WorkflowRunResult
from app.services.blue_planning_service import blue_planning_service
from app.services.orchestration_service import orchestration_service


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
        comparison = blue_planning_service.compare(
            session, run_id, model_id, incident_candidate_id, through_sequence, top_k
        )
        autonomy_mode = comparison.autonomy_mode

        if autonomy_mode == "observe":
            return WorkflowRunResult(
                comparison=comparison,
                orchestration=None,
                autonomy_mode=autonomy_mode,
                auto_executed=False,
                auto_verified=False,
                stopped_reason="Autonomy mode is OBSERVE: evidence only, no response plan "
                "is generated or executed.",
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


workflow_coordinator = WorkflowCoordinator()
