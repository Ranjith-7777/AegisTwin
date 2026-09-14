"""Phase 4 Blue response planning: compares multiple already-ranked
candidate plans using real, recomputed Attack Graph / Blast Radius
evidence, without mutating any persisted state. See
docs/architecture/BLUE_RESPONSE_PLANNING.md for the exact formulas.

Candidate generation reuses `response_service.analyze()`'s existing ranked
`ResponseRecommendation`s unchanged - this module adds a what-if security-
gain comparison and a Response Utility Score on top, it never invents new
candidates or duplicates response-scoring logic.
"""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.orm import Session

from app.database.models import ResponsePlanAssessmentRecord, ResponseRecommendationRecord
from app.schemas.blue_planning import (
    CandidatePlanAssessment,
    DecisionConfidence,
    PlanComparisonResult,
    ResponseUtilityScoreBreakdown,
    SecurityGainEvidence,
)
from app.schemas.response import ResponseRecommendation
from app.services import policy_service
from app.services.autonomy_service import autonomy_service
from app.services.orchestration_agents import synthetic_execution_agent
from app.services.response_playbook_service import response_playbook_service
from app.services.response_service import response_service
from app.services.topology_service import topology_service
from app.services.what_if_evidence_service import ZERO_EVIDENCE
from app.services.what_if_evidence_service import anchor_asset_ids as _anchor_asset_ids
from app.services.what_if_evidence_service import (
    best_security_gain_evidence as _security_gain_evidence,
)

MAX_CANDIDATES_EVALUATED = 5
OPERATIONAL_IMPACT_PENALTY = {"low": 0.0, "medium": 10.0, "high": 25.0}
REVERSIBILITY_BONUS = 10.0


def _utility_score(
    evidence: SecurityGainEvidence,
    recommendation: ResponseRecommendation,
    reversible: bool,
    operational_impact: str,
) -> ResponseUtilityScoreBreakdown:
    security_gain = min(40.0, evidence.security_gain)
    if (
        evidence.critical_targets_reachable_before > 0
        and evidence.critical_targets_reachable_after == 0
    ):
        critical_asset_protection = 20.0
    elif evidence.critical_targets_reachable_after < evidence.critical_targets_reachable_before:
        critical_asset_protection = 10.0
    else:
        critical_asset_protection = 0.0
    blast_radius_reduction = min(
        20.0,
        max(0, evidence.blast_radius_reachable_before - evidence.blast_radius_reachable_after)
        * 2.0,
    )
    evidence_quality = min(20.0, recommendation.defense_score * 20.0)
    reversibility_bonus = REVERSIBILITY_BONUS if reversible else 0.0
    operational_impact_penalty = OPERATIONAL_IMPACT_PENALTY.get(operational_impact, 25.0)
    total = max(
        0.0,
        min(
            100.0,
            security_gain
            + critical_asset_protection
            + blast_radius_reduction
            + evidence_quality
            + reversibility_bonus
            - operational_impact_penalty,
        ),
    )
    return ResponseUtilityScoreBreakdown(
        security_gain=round(security_gain, 2),
        critical_asset_protection=critical_asset_protection,
        blast_radius_reduction=round(blast_radius_reduction, 2),
        evidence_quality=round(evidence_quality, 2),
        reversibility_bonus=reversibility_bonus,
        operational_impact_penalty=operational_impact_penalty,
        total=round(total, 2),
    )


def _decision_confidence(
    top: ResponseRecommendation, evidence: SecurityGainEvidence
) -> DecisionConfidence:
    components = top.component_scores
    anomaly_evidence = round(components.get("evidence_applicability", 0.0) * 25.0, 2)
    incident_coherence = round(components.get("correlated_path_interruption", 0.0) * 20.0, 2)
    technique_diversity = round(components.get("technique_tactic_coverage", 0.0) * 20.0, 2)
    attack_path_corroboration = round(
        min(15.0, components.get("predicted_path_interruption", 0.0) * 15.0), 2
    )
    response_simulation_improvement = round(min(20.0, evidence.security_gain), 2)
    total = round(
        min(
            100.0,
            anomaly_evidence
            + incident_coherence
            + technique_diversity
            + attack_path_corroboration
            + response_simulation_improvement,
        ),
        2,
    )
    return DecisionConfidence(
        anomaly_evidence=anomaly_evidence,
        incident_coherence=incident_coherence,
        technique_diversity=technique_diversity,
        attack_path_corroboration=attack_path_corroboration,
        response_simulation_improvement=response_simulation_improvement,
        total=total,
    )


class BluePlanningService:
    def compare(
        self,
        session: Session,
        run_id: str,
        model_id: str,
        incident_candidate_id: str,
        through_sequence: int,
        top_k: int,
    ) -> PlanComparisonResult:
        analysis = response_service.analyze(
            session,
            run_id,
            model_id,
            through_sequence=through_sequence,
            prediction_enabled=True,
            top_k=top_k,
            force=False,
        )
        autonomy_mode = autonomy_service.require_mode(session).value
        anchors, has_evidence = _anchor_asset_ids(session, run_id, model_id, through_sequence)
        candidates: list[CandidatePlanAssessment] = []
        for recommendation in analysis.recommendations[:MAX_CANDIDATES_EVALUATED]:
            playbook = response_playbook_service.get(recommendation.playbook_id)
            record = session.get(ResponseRecommendationRecord, recommendation.recommendation_id)
            assert record is not None
            changed_nodes, changed_edges, _ = synthetic_execution_agent.mutation(record)
            # Only genuinely connectivity-removing operations (remove_edge,
            # remove_inbound_edges, remove_incident_edges) populate
            # changed_edges - excluding those edges alone correctly
            # disconnects an isolated node too (every edge touching it is
            # already included), without needing to also exclude the node
            # itself. A purely observational mutation (annotate_node,
            # no_connectivity_change) never removes connectivity, so its
            # changed_edges is empty and its security_gain is honestly 0 -
            # `synthetic_execution_agent.mutation()`'s own `changed_nodes`
            # for that case is an audit marker ("this node was annotated"),
            # not a claim that it should vanish from the attack graph, so
            # it is deliberately never used for what-if exclusion here.
            edge_source_asset_id = (
                recommendation.target_id.split("--", 1)[0]
                if recommendation.target_type == "relationship" and "--" in recommendation.target_id
                else None
            )
            evidence = (
                _security_gain_evidence(
                    session,
                    run_id,
                    model_id,
                    through_sequence,
                    anchors,
                    has_evidence,
                    frozenset(),
                    frozenset(changed_edges),
                    edge_source_asset_id,
                )
                if anchors
                else ZERO_EVIDENCE
            )
            target_node = next(
                (
                    node
                    for node in topology_service.nodes(include_sink=False)
                    if node.asset_id == recommendation.target_id
                ),
                None,
            )
            policy_result = policy_service.evaluate_response_policies(
                synthetic=recommendation.synthetic,
                playbook=playbook,
                autonomy_mode=autonomy_mode,
                target_criticality=target_node.criticality if target_node else None,
                target_asset_type=target_node.asset_type if target_node else None,
            )
            utility = _utility_score(
                evidence,
                recommendation,
                playbook.reversibility == "reversible",
                playbook.default_operational_impact,
            )
            candidates.append(
                CandidatePlanAssessment(
                    recommendation_id=recommendation.recommendation_id,
                    playbook_id=playbook.playbook_id,
                    playbook_name=playbook.name,
                    action_type=playbook.action_type,
                    target_type=recommendation.target_type,
                    target_id=recommendation.target_id,
                    required_approval_tier=recommendation.required_approval_tier,
                    reversibility=playbook.reversibility,
                    operational_impact=playbook.default_operational_impact,
                    security_gain_evidence=evidence,
                    utility_score=utility,
                    policy_pass=policy_result.overall_pass,
                    policy_failed_ids=policy_result.failed_policy_ids,
                    recommended=False,
                    changed_node_ids=changed_nodes,
                    changed_edge_ids=changed_edges,
                )
            )

        candidates.sort(key=lambda item: (-item.utility_score.total, item.recommendation_id))
        recommended_id = None
        for index, candidate in enumerate(candidates):
            if index == 0 and candidate.policy_pass:
                candidates[index] = candidate.model_copy(update={"recommended": True})
                recommended_id = candidate.recommendation_id
                break

        decision_confidence = None
        if candidates:
            top_recommendation = next(
                item
                for item in analysis.recommendations
                if item.recommendation_id == candidates[0].recommendation_id
            )
            decision_confidence = _decision_confidence(
                top_recommendation, candidates[0].security_gain_evidence
            )

        result = PlanComparisonResult(
            simulation_run_id=run_id,
            model_id=model_id,
            incident_candidate_id=incident_candidate_id,
            through_sequence_number=through_sequence,
            autonomy_mode=autonomy_mode,
            candidates=candidates,
            recommended_recommendation_id=recommended_id,
            decision_confidence=decision_confidence,
        )
        self._persist(session, result)
        return result

    def _persist(self, session: Session, result: PlanComparisonResult) -> None:
        """Persists the comparison so it is reconstructable after a reload
        without re-deriving it from raw evidence (docs/architecture/
        BLUE_RESPONSE_PLANNING.md "Persistence"). Idempotent per
        (run, model, incident, sequence) - a later call with the same
        identity overwrites the earlier assessment rather than duplicating
        it, since the underlying evidence for that identity is immutable."""

        assessment_id = self.assessment_id(
            result.simulation_run_id,
            result.model_id,
            result.incident_candidate_id,
            result.through_sequence_number,
        )
        record = session.get(ResponsePlanAssessmentRecord, assessment_id)
        candidates_json = [candidate.model_dump(mode="json") for candidate in result.candidates]
        decision_confidence_json = (
            result.decision_confidence.model_dump(mode="json") if result.decision_confidence else {}
        )
        if record is None:
            session.add(
                ResponsePlanAssessmentRecord(
                    assessment_id=assessment_id,
                    simulation_run_id=result.simulation_run_id,
                    model_id=result.model_id,
                    incident_candidate_id=result.incident_candidate_id,
                    through_sequence_number=result.through_sequence_number,
                    autonomy_mode=result.autonomy_mode,
                    candidates_json=candidates_json,
                    selected_recommendation_id=result.recommended_recommendation_id,
                    decision_confidence_json=decision_confidence_json,
                )
            )
        else:
            record.autonomy_mode = result.autonomy_mode
            record.candidates_json = candidates_json
            record.selected_recommendation_id = result.recommended_recommendation_id
            record.decision_confidence_json = decision_confidence_json
        session.commit()

    def load(self, session: Session, assessment_id: str) -> PlanComparisonResult | None:
        """Reconstructs a previously computed comparison from persisted
        state only - never recomputes."""

        record = session.get(ResponsePlanAssessmentRecord, assessment_id)
        if record is None:
            return None
        return PlanComparisonResult(
            simulation_run_id=record.simulation_run_id,
            model_id=record.model_id,
            incident_candidate_id=record.incident_candidate_id,
            through_sequence_number=record.through_sequence_number,
            autonomy_mode=record.autonomy_mode,
            candidates=[
                CandidatePlanAssessment.model_validate(item) for item in record.candidates_json
            ],
            recommended_recommendation_id=record.selected_recommendation_id,
            decision_confidence=(
                DecisionConfidence.model_validate(record.decision_confidence_json)
                if record.decision_confidence_json
                else None
            ),
        )

    @staticmethod
    def assessment_id(run_id: str, model_id: str, incident_candidate_id: str, sequence: int) -> str:
        return str(
            uuid5(
                NAMESPACE_URL,
                f"aegisarena-plan-assessment:{run_id}:{model_id}:{incident_candidate_id}:{sequence}",
            )
        )


blue_planning_service = BluePlanningService()
