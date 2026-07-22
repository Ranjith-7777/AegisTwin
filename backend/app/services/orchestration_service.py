import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import (
    AgentDecisionRecord,
    ApprovalRequestRecord,
    AuditEventRecord,
    ResponseImpactSimulationRecord,
    ResponseOrchestrationRecord,
    ResponsePlanStepRecord,
    ResponseRecommendationRecord,
    ResponseVerificationRecord,
    RollbackRecord,
    SyntheticExecutionRecord,
)
from app.schemas.orchestration import (
    AgentDecision,
    ApprovalRequestView,
    AuditEventView,
    AuditIntegrity,
    OrchestrationView,
    PlanStep,
    RollbackView,
    SyntheticExecutionView,
    VerificationView,
)
from app.services.orchestration_agents import (
    AGENT_VERSION,
    AgentResult,
    approval_router_agent,
    impact_simulation_agent,
    response_planner_agent,
    safety_governor_agent,
    synthetic_execution_agent,
    verification_agent,
)
from app.services.response_playbook_service import response_playbook_service

VERSION = "synthetic-response-orchestration-v1"
GENESIS_HASH = "0" * 64


class OrchestrationService:
    def _id(self, *parts: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, "aegistwin:" + ":".join(parts)))

    def _get(self, session: Session, oid: str) -> ResponseOrchestrationRecord:
        record = session.get(ResponseOrchestrationRecord, oid)
        if record is None:
            raise ApplicationError(
                "ORCHESTRATION_NOT_FOUND", "The synthetic orchestration was not found.", 404
            )
        return record

    def _require_state(
        self, record: ResponseOrchestrationRecord, allowed: set[str], expected: str | None = None
    ) -> None:
        if expected is not None and record.current_state != expected:
            raise ApplicationError(
                "STALE_ORCHESTRATION_STATE", "The synthetic orchestration state has changed.", 409
            )
        if record.current_state not in allowed:
            raise ApplicationError(
                "INVALID_ORCHESTRATION_TRANSITION",
                f"State {record.current_state} does not allow this transition.",
                409,
            )

    def _audit(
        self,
        session: Session,
        oid: str,
        event_type: str,
        actor_type: str,
        actor_id: str,
        display: str,
        payload: dict[str, object],
    ) -> AuditEventRecord:
        previous = session.scalar(
            select(AuditEventRecord)
            .where(AuditEventRecord.orchestration_id == oid)
            .order_by(AuditEventRecord.sequence_number.desc())
        )
        sequence = 1 if previous is None else previous.sequence_number + 1
        previous_hash = GENESIS_HASH if previous is None else previous.event_hash
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        event_hash = hashlib.sha256(f"{previous_hash}:{canonical}".encode()).hexdigest()
        event = AuditEventRecord(
            audit_event_id=self._id("audit", oid, str(sequence)),
            orchestration_id=oid,
            sequence_number=sequence,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_display_name=display,
            previous_event_hash=previous_hash,
            event_hash=event_hash,
            canonical_payload_json=payload,
            created_at=datetime.now(UTC),
            synthetic=True,
        )
        session.add(event)
        session.flush()
        return event

    def _decision(
        self, session: Session, oid: str, index: int, result: AgentResult, refs: list[str]
    ) -> AgentDecisionRecord:
        decision = AgentDecisionRecord(
            agent_decision_id=self._id("decision", oid, str(index), result.agent_name),
            orchestration_id=oid,
            agent_name=result.agent_name,
            agent_version=AGENT_VERSION,
            decision_type=result.decision_type,
            input_reference_ids_json=refs,
            output_summary=result.summary,
            decision=result.decision,
            ranking_score=result.score,
            rationale=result.rationale,
            warnings_json=result.warnings,
            next_agent=result.next_agent,
            created_at=datetime.now(UTC),
            synthetic=True,
        )
        session.add(decision)
        self._audit(
            session,
            oid,
            "agent_decision",
            "simulation_agent",
            result.agent_name,
            result.agent_name,
            {
                "decision": result.decision,
                "decision_type": result.decision_type,
                "next_agent": result.next_agent or "none",
                "summary": result.summary,
            },
        )
        return decision

    def create(
        self,
        session: Session,
        run_id: str,
        model_id: str,
        candidate_id: str,
        recommendation_id: str,
        sequence: int,
    ) -> OrchestrationView:
        recommendation = session.get(ResponseRecommendationRecord, recommendation_id)
        if (
            recommendation is None
            or recommendation.simulation_run_id != run_id
            or recommendation.model_id != model_id
            or recommendation.incident_candidate_id != candidate_id
        ):
            raise ApplicationError(
                "ORCHESTRATION_INPUT_MISMATCH",
                "The recommendation does not match the synthetic incident inputs.",
                422,
            )
        if recommendation.through_sequence_number != sequence:
            raise ApplicationError(
                "STALE_RESPONSE_SIMULATION",
                "The selected recommendation is from a different evidence sequence.",
                409,
            )
        oid = self._id(
            "orchestration", run_id, model_id, candidate_id, recommendation_id, str(sequence)
        )
        existing = session.get(ResponseOrchestrationRecord, oid)
        if existing is not None:
            return self.view(session, existing)
        now = datetime.now(UTC)
        record = ResponseOrchestrationRecord(
            orchestration_id=oid,
            simulation_run_id=run_id,
            model_id=model_id,
            incident_candidate_id=candidate_id,
            through_sequence_number=sequence,
            orchestration_version=VERSION,
            current_state="planning",
            selected_recommendation_id=recommendation_id,
            required_approval_tier=recommendation.required_approval_tier,
            created_by="Demo Orchestration Console (synthetic)",
            created_at=now,
            updated_at=now,
            synthetic=True,
        )
        session.add(record)
        playbook = response_playbook_service.get(recommendation.playbook_id)
        step = ResponsePlanStepRecord(
            plan_step_id=self._id("step", oid, "1"),
            orchestration_id=oid,
            step_number=1,
            playbook_id=recommendation.playbook_id,
            recommendation_id=recommendation_id,
            target_type=recommendation.target_type,
            target_id=recommendation.target_id,
            required_approval_tier=recommendation.required_approval_tier,
            reversibility=playbook.reversibility,
            rationale=recommendation.rationale,
            expected_mutation_json=playbook.topology_mutation_specification,
            current_status="planned",
            synthetic=True,
        )
        session.add(step)
        self._audit(
            session,
            oid,
            "orchestration_created",
            "human",
            "demo-operator",
            "Demo Operator (synthetic)",
            {
                "from_state": "draft",
                "to_state": "planning",
                "reason": "Created from selected Phase 7A recommendation.",
            },
        )
        simulation = session.scalar(
            select(ResponseImpactSimulationRecord).where(
                ResponseImpactSimulationRecord.recommendation_id == recommendation_id
            )
        )
        results = [
            response_planner_agent.decide(recommendation),
            impact_simulation_agent.decide(recommendation, simulation, sequence),
        ]
        if results[-1].decision == "stale":
            record.current_state = "simulation_validation"
        else:
            governor = safety_governor_agent.decide(recommendation, playbook)
            results.append(governor)
            if governor.decision == "blocked":
                record.current_state = "rejected"
            else:
                router = approval_router_agent.decide(recommendation.required_approval_tier)
                results.append(router)
                if router.decision == "automatic":
                    record.current_state = "approved"
                else:
                    role = (
                        "administrator"
                        if recommendation.required_approval_tier == "administrator_approval"
                        else "analyst"
                    )
                    record.current_state = f"awaiting_{role}_approval"
                    session.add(
                        ApprovalRequestRecord(
                            approval_request_id=self._id("approval", oid, role),
                            orchestration_id=oid,
                            plan_step_id=step.plan_step_id,
                            required_role=role,
                            approval_state="pending",
                            requested_at=now,
                            expires_at=None,
                            decided_at=None,
                            decided_by=None,
                            decision_reason=None,
                            synthetic=True,
                        )
                    )
        for index, result in enumerate(results, 1):
            self._decision(session, oid, index, result, [recommendation_id])
        self._audit(
            session,
            oid,
            "state_transition",
            "simulation_agent",
            "orchestrator",
            "Orchestration State Machine",
            {
                "from_state": "planning",
                "to_state": record.current_state,
                "reason": "Deterministic planning, simulation and policy workflow completed.",
            },
        )
        session.commit()
        return self.view(session, record)

    def advance(self, session: Session, oid: str, expected: str | None) -> OrchestrationView:
        record = self._get(session, oid)
        self._require_state(record, {"simulation_validation", "policy_review"}, expected)
        raise ApplicationError(
            "ORCHESTRATION_REANALYSIS_REQUIRED",
            "Re-run Phase 7A analysis before advancing this synthetic orchestration.",
            409,
        )

    def decide_approval(
        self,
        session: Session,
        oid: str,
        approval_id: str,
        role: str,
        actor: str,
        decision: str,
        reason: str,
    ) -> OrchestrationView:
        record = self._get(session, oid)
        approval = session.get(ApprovalRequestRecord, approval_id)
        if approval is None or approval.orchestration_id != oid:
            raise ApplicationError(
                "APPROVAL_NOT_FOUND", "The synthetic approval request was not found.", 404
            )
        self._require_state(
            record, {"awaiting_analyst_approval", "awaiting_administrator_approval"}
        )
        if approval.approval_state != "pending":
            raise ApplicationError(
                "APPROVAL_FINALISED", "The approval decision is immutable after finalisation.", 409
            )
        if approval.expires_at is not None and approval.expires_at <= datetime.now(UTC):
            raise ApplicationError(
                "APPROVAL_EXPIRED", "The synthetic approval request has expired.", 409
            )
        if approval.required_role == "administrator" and role != "administrator":
            raise ApplicationError(
                "INSUFFICIENT_APPROVAL_ROLE",
                "Administrator demonstration approval is required.",
                403,
            )
        approval.approval_state = "approved" if decision == "approve" else "rejected"
        approval.decided_at = datetime.now(UTC)
        approval.decided_by = f"{actor} (synthetic demonstration identity)"
        approval.decision_reason = reason
        old = record.current_state
        record.current_state = "approved" if decision == "approve" else "rejected"
        record.updated_at = datetime.now(UTC)
        self._audit(
            session,
            oid,
            "approval_decided",
            "human",
            role,
            approval.decided_by,
            {
                "approval_id": approval_id,
                "decision": decision,
                "from_state": old,
                "to_state": record.current_state,
                "reason": reason,
            },
        )
        session.commit()
        return self.view(session, record)

    def execute(
        self, session: Session, oid: str, expected: str | None, failure_mode: str
    ) -> OrchestrationView:
        record = self._get(session, oid)
        existing = session.scalar(
            select(SyntheticExecutionRecord).where(SyntheticExecutionRecord.orchestration_id == oid)
        )
        if existing is not None:
            return self.view(session, record)
        self._require_state(record, {"approved"}, expected)
        recommendation = session.get(
            ResponseRecommendationRecord, record.selected_recommendation_id
        )
        step = session.scalar(
            select(ResponsePlanStepRecord).where(ResponsePlanStepRecord.orchestration_id == oid)
        )
        assert recommendation is not None and step is not None
        now = datetime.now(UTC)
        changed_nodes, changed_edges, summary = synthetic_execution_agent.mutation(recommendation)
        failed = failure_mode != "none"
        execution = SyntheticExecutionRecord(
            execution_id=self._id("execution", oid, step.plan_step_id),
            orchestration_id=oid,
            plan_step_id=step.plan_step_id,
            playbook_id=step.playbook_id,
            target_type=step.target_type,
            target_id=step.target_id,
            execution_state="failed_simulated" if failed else "completed_simulated",
            started_at=now,
            completed_at=now,
            mutation_summary_json=summary,
            changed_node_ids_json=[] if failed else changed_nodes,
            changed_edge_ids_json=[] if failed else changed_edges,
            pre_execution_state_reference=f"synthetic-state:{oid}:pre",
            post_execution_state_reference=f"synthetic-state:{oid}:post" if not failed else None,
            simulated_failure_reason=failure_mode if failed else None,
            reversible=step.reversibility == "reversible",
            synthetic=True,
        )
        session.add(execution)
        step.current_status = execution.execution_state
        record.current_state = (
            "synthetic_execution_failed" if failed else "synthetic_execution_completed"
        )
        record.updated_at = now
        result = AgentResult(
            synthetic_execution_agent.name,
            "synthetic_execution",
            execution.execution_state,
            "Synthetic mutation failed deterministically."
            if failed
            else "Declared mutation applied only to persisted synthetic operational state.",
            "No external command, integration or base-topology mutation is used.",
            [failure_mode] if failed else [],
            "Verification Agent" if not failed else None,
        )
        count = int(
            session.scalar(
                select(func.count())
                .select_from(AgentDecisionRecord)
                .where(AgentDecisionRecord.orchestration_id == oid)
            )
            or 0
        )
        self._decision(session, oid, count + 1, result, [step.plan_step_id])
        self._audit(
            session,
            oid,
            "synthetic_execution_failed" if failed else "synthetic_execution_completed",
            "simulation_agent",
            "synthetic-executor",
            synthetic_execution_agent.name,
            {
                "execution_id": execution.execution_id,
                "to_state": record.current_state,
                "reason": failure_mode
                if failed
                else "Declared playbook mutation applied in synthetic state.",
            },
        )
        session.commit()
        return self.view(session, record)

    def verify(self, session: Session, oid: str) -> OrchestrationView:
        record = self._get(session, oid)
        existing = session.scalar(
            select(ResponseVerificationRecord).where(
                ResponseVerificationRecord.orchestration_id == oid
            )
        )
        if existing is not None:
            return self.view(session, record)
        self._require_state(record, {"synthetic_execution_completed"})
        execution = session.scalar(
            select(SyntheticExecutionRecord).where(SyntheticExecutionRecord.orchestration_id == oid)
        )
        simulation = session.scalar(
            select(ResponseImpactSimulationRecord).where(
                ResponseImpactSimulationRecord.recommendation_id
                == record.selected_recommendation_id
            )
        )
        assert execution is not None and simulation is not None
        now = datetime.now(UTC)
        status, metrics = verification_agent.verify(
            execution.changed_node_ids_json,
            execution.changed_edge_ids_json,
            simulation.expected_relationships_affected,
        )
        verification = ResponseVerificationRecord(
            verification_id=self._id("verification", execution.execution_id),
            orchestration_id=oid,
            execution_id=execution.execution_id,
            verification_status=status,
            metrics_json=metrics,
            unintended_effects_json=[],
            started_at=now,
            completed_at=now,
            synthetic=True,
        )
        session.add(verification)
        record.current_state = (
            "verified" if status == "successful_simulation" else "rollback_recommended"
        )
        record.updated_at = now
        self._audit(
            session,
            oid,
            "verification_completed",
            "simulation_agent",
            "verification-agent",
            verification_agent.name,
            {
                "verification_status": status,
                "to_state": record.current_state,
                "reason": "Compared declared and persisted synthetic mutations.",
            },
        )
        session.commit()
        return self.view(session, record)

    def rollback(
        self, session: Session, oid: str, reason: str, requested_by: str
    ) -> OrchestrationView:
        record = self._get(session, oid)
        existing = session.scalar(
            select(RollbackRecord).where(RollbackRecord.orchestration_id == oid)
        )
        if existing is not None:
            return self.view(session, record)
        self._require_state(record, {"verified", "rollback_recommended"})
        execution = session.scalar(
            select(SyntheticExecutionRecord).where(SyntheticExecutionRecord.orchestration_id == oid)
        )
        if execution is None or not execution.reversible:
            raise ApplicationError(
                "ROLLBACK_NOT_REVERSIBLE", "This synthetic playbook cannot be rolled back.", 409
            )
        now = datetime.now(UTC)
        rollback = RollbackRecord(
            rollback_id=self._id("rollback", oid),
            orchestration_id=oid,
            execution_id=execution.execution_id,
            reason=reason,
            requested_by=f"{requested_by} (synthetic demonstration identity)",
            approval_request_id=None,
            state="synthetic_rollback_completed",
            restored_state_reference=execution.pre_execution_state_reference,
            started_at=now,
            completed_at=now,
            verification_summary_json={
                "restored": True,
                "changed_node_ids": [],
                "changed_edge_ids": [],
            },
            synthetic=True,
        )
        session.add(rollback)
        execution.execution_state = "rolled_back_simulated"
        record.current_state = "synthetic_rollback_completed"
        record.updated_at = now
        self._audit(
            session,
            oid,
            "synthetic_rollback_completed",
            "human",
            "demo-operator",
            rollback.requested_by,
            {
                "rollback_id": rollback.rollback_id,
                "to_state": record.current_state,
                "reason": reason,
            },
        )
        session.commit()
        return self.view(session, record)

    def audit(self, session: Session, oid: str) -> list[AuditEventView]:
        self._get(session, oid)
        rows = list(
            session.scalars(
                select(AuditEventRecord)
                .where(AuditEventRecord.orchestration_id == oid)
                .order_by(AuditEventRecord.sequence_number)
            )
        )
        return [
            AuditEventView(
                audit_event_id=x.audit_event_id,
                sequence_number=x.sequence_number,
                event_type=x.event_type,
                actor_type=x.actor_type,
                actor_id=x.actor_id,
                actor_display_name=x.actor_display_name,
                previous_event_hash=x.previous_event_hash,
                event_hash=x.event_hash,
                canonical_payload=x.canonical_payload_json,
                created_at=x.created_at,
                synthetic=x.synthetic,
            )
            for x in rows
        ]

    def verify_audit(self, session: Session, oid: str) -> AuditIntegrity:
        events = self.audit(session, oid)
        previous = GENESIS_HASH
        for event in events:
            canonical = json.dumps(
                event.canonical_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            )
            expected = hashlib.sha256(f"{previous}:{canonical}".encode()).hexdigest()
            if event.previous_event_hash != previous or event.event_hash != expected:
                return AuditIntegrity(
                    valid=False,
                    event_count=len(events),
                    first_invalid_sequence=event.sequence_number,
                )
            previous = event.event_hash
        return AuditIntegrity(valid=True, event_count=len(events))

    def view(self, session: Session, record: ResponseOrchestrationRecord) -> OrchestrationView:
        steps = list(
            session.scalars(
                select(ResponsePlanStepRecord)
                .where(ResponsePlanStepRecord.orchestration_id == record.orchestration_id)
                .order_by(ResponsePlanStepRecord.step_number)
            )
        )
        decisions = list(
            session.scalars(
                select(AgentDecisionRecord)
                .where(AgentDecisionRecord.orchestration_id == record.orchestration_id)
                .order_by(AgentDecisionRecord.created_at)
            )
        )
        approvals = list(
            session.scalars(
                select(ApprovalRequestRecord).where(
                    ApprovalRequestRecord.orchestration_id == record.orchestration_id
                )
            )
        )
        executions = list(
            session.scalars(
                select(SyntheticExecutionRecord).where(
                    SyntheticExecutionRecord.orchestration_id == record.orchestration_id
                )
            )
        )
        verifications = list(
            session.scalars(
                select(ResponseVerificationRecord).where(
                    ResponseVerificationRecord.orchestration_id == record.orchestration_id
                )
            )
        )
        rollback = session.scalar(
            select(RollbackRecord).where(RollbackRecord.orchestration_id == record.orchestration_id)
        )
        return OrchestrationView(
            orchestration_id=record.orchestration_id,
            simulation_run_id=record.simulation_run_id,
            model_id=record.model_id,
            incident_candidate_id=record.incident_candidate_id,
            through_sequence_number=record.through_sequence_number,
            orchestration_version=record.orchestration_version,
            current_state=record.current_state,
            selected_recommendation_id=record.selected_recommendation_id,
            required_approval_tier=record.required_approval_tier,
            created_by=record.created_by,
            created_at=record.created_at,
            updated_at=record.updated_at,
            plan_steps=[
                PlanStep(
                    plan_step_id=x.plan_step_id,
                    step_number=x.step_number,
                    playbook_id=x.playbook_id,
                    recommendation_id=x.recommendation_id,
                    target_type=x.target_type,
                    target_id=x.target_id,
                    required_approval_tier=x.required_approval_tier,
                    reversibility=x.reversibility,
                    rationale=x.rationale,
                    expected_mutation=x.expected_mutation_json,
                    current_status=x.current_status,
                    synthetic=x.synthetic,
                )
                for x in steps
            ],
            decisions=[
                AgentDecision(
                    agent_decision_id=x.agent_decision_id,
                    agent_name=x.agent_name,
                    agent_version=x.agent_version,
                    decision_type=x.decision_type,
                    input_reference_ids=x.input_reference_ids_json,
                    output_summary=x.output_summary,
                    decision=x.decision,
                    ranking_score=x.ranking_score,
                    rationale=x.rationale,
                    warnings=x.warnings_json,
                    next_agent=x.next_agent,
                    created_at=x.created_at,
                    synthetic=x.synthetic,
                )
                for x in decisions
            ],
            approvals=[
                ApprovalRequestView(
                    approval_request_id=x.approval_request_id,
                    plan_step_id=x.plan_step_id,
                    required_role=x.required_role,
                    approval_state=x.approval_state,
                    requested_at=x.requested_at,
                    expires_at=x.expires_at,
                    decided_at=x.decided_at,
                    decided_by=x.decided_by,
                    decision_reason=x.decision_reason,
                    synthetic=x.synthetic,
                )
                for x in approvals
            ],
            executions=[
                SyntheticExecutionView(
                    execution_id=x.execution_id,
                    plan_step_id=x.plan_step_id,
                    playbook_id=x.playbook_id,
                    target_type=x.target_type,
                    target_id=x.target_id,
                    execution_state=x.execution_state,
                    started_at=x.started_at,
                    completed_at=x.completed_at,
                    mutation_summary=x.mutation_summary_json,
                    changed_node_ids=x.changed_node_ids_json,
                    changed_edge_ids=x.changed_edge_ids_json,
                    simulated_failure_reason=x.simulated_failure_reason,
                    reversible=x.reversible,
                    synthetic=x.synthetic,
                )
                for x in executions
            ],
            verifications=[
                VerificationView(
                    verification_id=x.verification_id,
                    execution_id=x.execution_id,
                    verification_status=x.verification_status,
                    metrics=x.metrics_json,
                    unintended_effects=x.unintended_effects_json,
                    started_at=x.started_at,
                    completed_at=x.completed_at,
                    synthetic=x.synthetic,
                )
                for x in verifications
            ],
            rollback=None
            if rollback is None
            else RollbackView(
                rollback_id=rollback.rollback_id,
                execution_id=rollback.execution_id,
                reason=rollback.reason,
                requested_by=rollback.requested_by,
                state=rollback.state,
                restored_state_reference=rollback.restored_state_reference,
                verification_summary=rollback.verification_summary_json,
                synthetic=rollback.synthetic,
            ),
            synthetic=record.synthetic,
        )


orchestration_service = OrchestrationService()
