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

from app.database.models import ResponseRecommendationRecord
from app.schemas.attack_graph import AttackPathType
from app.schemas.blue_planning import (
    CandidatePlanAssessment,
    DecisionConfidence,
    PlanComparisonResult,
    ResponseUtilityScoreBreakdown,
    SecurityGainEvidence,
)
from app.schemas.response import ResponseRecommendation
from app.services import policy_service
from app.services.attack_graph_service import attack_graph_service
from app.services.autonomy_service import autonomy_service
from app.services.blast_radius_service import blast_radius_service
from app.services.orchestration_agents import synthetic_execution_agent
from app.services.response_playbook_service import response_playbook_service
from app.services.response_service import response_service
from app.services.topology_path_service import topology_path_service
from app.services.topology_service import topology_service

MAX_CANDIDATES_EVALUATED = 5
WHAT_IF_MAX_DEPTH = 6
WHAT_IF_MAX_PATHS = 3
OPERATIONAL_IMPACT_PENALTY = {"low": 0.0, "medium": 10.0, "high": 25.0}
REVERSIBILITY_BONUS = 10.0


def _anchor_asset_ids(
    session: Session, run_id: str, model_id: str, through_sequence: int
) -> tuple[list[str], bool]:
    """A stable set of assets to root the before/after comparison at, plus
    whether that set is real evidence (safe to pass to evidence-bound
    Blast Radius) or a fallback.

    Real anomalous-observed evidence when it exists (a genuine attacker
    foothold); otherwise the first synthetic topology asset, purely so the
    comparison has a valid, deterministic starting point - the same
    fallback is used for every candidate in one comparison run, so the
    relative ranking between candidates remains meaningful even when no
    evidence exists yet (e.g. a very early sequence). The fallback asset is
    NOT real evidence, so it must never be passed to Blast Radius in
    evidence-bound mode (it would be correctly rejected as unsupported).

    `_security_gain_evidence` roots its OBSERVED-path traversal at
    `anchors[0]` and only walks OBSERVED edges *forward* from there (see
    `purple_team_service`'s identical use of a scenario's
    `initial_access_point` as the Attack Graph source). So the anchor must
    be an asset with at least one OUTGOING observed edge - an anomalous
    asset the attacker was only ever observed arriving *at* (e.g. a
    database with no further observed outbound edges, or an edge-zone
    asset like an API gateway that is itself only ever a destination in
    this run) can never produce a forward path and would silently make
    every candidate look equally (falsely) ineffective. Anomalous assets
    with an outgoing observed edge are ordered first (deterministically),
    so `anchors[0]` is always a genuine forward pivot when one exists.
    """

    state = topology_path_service.run_state(session, run_id, model_id, through_sequence)
    if state.anomalous_observed_asset_ids:
        anomalous = sorted(state.anomalous_observed_asset_ids)
        sources_with_outgoing_edges = {
            edge_id.split("--", 1)[0] for edge_id in state.observed_edge_ids
        }
        pivots = [a for a in anomalous if a in sources_with_outgoing_edges]
        ordered = pivots + [a for a in anomalous if a not in sources_with_outgoing_edges]
        return ordered, True
    nodes = topology_service.nodes(include_sink=False)
    return ([nodes[0].asset_id] if nodes else []), False


def _security_gain_evidence(
    session: Session,
    run_id: str,
    model_id: str,
    through_sequence: int,
    anchors: list[str],
    has_evidence: bool,
    exclude_node_ids: frozenset[str],
    exclude_edge_ids: frozenset[str],
) -> SecurityGainEvidence:
    # OBSERVED (bounded to this run's real telemetry through `through_sequence`)
    # rather than POTENTIAL (the full static graph): a candidate plan is being
    # judged against what THIS incident's evidence actually shows happened, and
    # a redundant topology can otherwise hide a single removed edge's real
    # effect on the specific path this incident's evidence followed. Falls
    # back to POTENTIAL only when there is no real evidence yet to bound to.
    source = anchors[0]
    path_type = AttackPathType.OBSERVED if has_evidence else AttackPathType.POTENTIAL
    graph_run_id = run_id if has_evidence else None
    graph_model_id = model_id if has_evidence else None
    graph_sequence = through_sequence if has_evidence else None
    before = attack_graph_service.analyze(
        session,
        source,
        None,
        path_type,
        graph_run_id,
        graph_model_id,
        graph_sequence,
        WHAT_IF_MAX_DEPTH,
        WHAT_IF_MAX_PATHS,
        publish_event=False,
    )
    after = attack_graph_service.analyze(
        session,
        source,
        None,
        path_type,
        graph_run_id,
        graph_model_id,
        graph_sequence,
        WHAT_IF_MAX_DEPTH,
        WHAT_IF_MAX_PATHS,
        exclude_edge_ids=exclude_edge_ids,
        exclude_node_ids=exclude_node_ids,
        publish_event=False,
    )
    critical_before = sum(1 for p in before.paths if p.target_criticality in {"high", "critical"})
    critical_after = sum(1 for p in after.paths if p.target_criticality in {"high", "critical"})
    top_before = before.paths[0].score.total if before.paths else 0.0
    top_after = after.paths[0].score.total if after.paths else 0.0

    blast_before = blast_radius_service.estimate(
        session, anchors, graph_run_id, graph_sequence, WHAT_IF_MAX_DEPTH, publish_event=False
    )
    blast_after = blast_radius_service.estimate(
        session,
        anchors,
        graph_run_id,
        graph_sequence,
        WHAT_IF_MAX_DEPTH,
        exclude_edge_ids=exclude_edge_ids,
        exclude_node_ids=exclude_node_ids,
        publish_event=False,
    )

    security_gain = (
        max(0, len(before.paths) - len(after.paths)) * 5.0
        + max(0.0, top_before - top_after) * 0.3
        + max(0, critical_before - critical_after) * 10.0
        + max(0, blast_before.reachable_count - blast_after.reachable_count) * 2.0
        + max(0, blast_before.critical_count - blast_after.critical_count) * 5.0
    )

    return SecurityGainEvidence(
        attack_paths_before=len(before.paths),
        attack_paths_after=len(after.paths),
        top_attack_path_score_before=top_before,
        top_attack_path_score_after=top_after,
        critical_targets_reachable_before=critical_before,
        critical_targets_reachable_after=critical_after,
        blast_radius_reachable_before=blast_before.reachable_count,
        blast_radius_reachable_after=blast_after.reachable_count,
        blast_radius_critical_before=blast_before.critical_count,
        blast_radius_critical_after=blast_after.critical_count,
        security_gain=round(security_gain, 2),
    )


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
            _, changed_edges, _ = synthetic_execution_agent.mutation(record)
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
                )
                if anchors
                else SecurityGainEvidence(
                    attack_paths_before=0,
                    attack_paths_after=0,
                    top_attack_path_score_before=0.0,
                    top_attack_path_score_after=0.0,
                    critical_targets_reachable_before=0,
                    critical_targets_reachable_after=0,
                    blast_radius_reachable_before=0,
                    blast_radius_reachable_after=0,
                    blast_radius_critical_before=0,
                    blast_radius_critical_after=0,
                    security_gain=0.0,
                )
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

        return PlanComparisonResult(
            simulation_run_id=run_id,
            model_id=model_id,
            incident_candidate_id=incident_candidate_id,
            through_sequence_number=through_sequence,
            autonomy_mode=autonomy_mode,
            candidates=candidates,
            recommended_recommendation_id=recommended_id,
            decision_confidence=decision_confidence,
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
