from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import (
    AnomalyAssessmentRecord,
    DetectionModelRecord,
    IncidentCandidateRecord,
    IncidentEvidenceRecord,
    PredictionHypothesisRecord,
    PredictionSnapshotRecord,
    ResponseAnalysisRecord,
    ResponseImpactSimulationRecord,
    ResponsePlaybookRecord,
    ResponseRecommendationRecord,
    SimulationRunRecord,
    TechniqueObservationRecord,
    TelemetryEventRecord,
)
from app.schemas.response import (
    DefensivePlaybook,
    ResponseAnalysisResult,
    ResponseImpactSimulation,
    ResponseRecommendation,
    ResponseRunSummary,
)
from app.schemas.topology import InfrastructureEdge
from app.services.response_playbook_service import PLAYBOOKS, response_playbook_service
from app.services.topology_path_service import topology_path_service
from app.services.topology_service import TOPOLOGY_VERSION, topology_service

ENGINE_VERSION = "blue-agent-defense-score-v1"
SIMULATION_VERSION = "graph-clone-impact-v1"
BLUE_AGENT_NAME = "Blue Agent"
# Zones that sit on the synthetic request-serving path, where a defensive action
# carries a full service-level penalty rather than a reduced one.
SERVING_ZONES = frozenset({"edge_zone", "cluster_zone", "workload_zone", "data_zone"})
OPERATIONAL_IMPACT_COST = {"low": 0.04, "medium": 0.10, "high": 0.20}
BLAST_RADIUS_COST = {
    "single_identity": 0.01,
    "single_asset": 0.02,
    "single_relationship": 0.02,
    "service": 0.08,
}
WEIGHTS = {
    "evidence_applicability": 0.25,
    "correlated_path_interruption": 0.20,
    "predicted_path_interruption": 0.15,
    "technique_tactic_coverage": 0.15,
    "target_relevance": 0.10,
    "reversibility": 0.10,
    "policy_compatibility": 0.05,
}


"""Defense score, ranking score, playbook, target type, target id, components,
penalties, defense components and the human-readable explanation."""
_RankedAction = tuple[
    float,
    float,
    DefensivePlaybook,
    str,
    str,
    dict[str, float],
    dict[str, float],
    dict[str, float],
    str,
]


class ResponseService:
    def analyze(
        self,
        session: Session,
        run_id: str,
        model_id: str,
        through_sequence: int | None,
        prediction_enabled: bool,
        top_k: int,
        force: bool,
    ) -> ResponseAnalysisResult:
        run = session.get(SimulationRunRecord, run_id)
        if run is None:
            raise ApplicationError(
                "SIMULATION_RUN_NOT_FOUND", "The simulation run was not found.", 404
            )
        if session.get(DetectionModelRecord, model_id) is None:
            raise ApplicationError(
                "DETECTION_MODEL_NOT_FOUND", "The detection model was not found.", 404
            )
        candidate = session.scalar(
            select(IncidentCandidateRecord).where(
                IncidentCandidateRecord.simulation_run_id == run_id,
                IncidentCandidateRecord.model_id == model_id,
            )
        )
        if candidate is None:
            raise ApplicationError(
                "RESPONSE_CORRELATION_REQUIRED",
                "Synthetic correlation analysis is required first.",
                422,
            )
        event_total = int(
            session.scalar(
                select(func.count())
                .select_from(TelemetryEventRecord)
                .where(TelemetryEventRecord.simulation_run_id == run_id)
            )
            or 0
        )
        limit = min(through_sequence or event_total, event_total)
        if limit < 1:
            raise ApplicationError(
                "RESPONSE_EVIDENCE_REQUIRED", "Causal synthetic evidence is required.", 422
            )
        assessment_count = int(
            session.scalar(
                select(func.count())
                .select_from(AnomalyAssessmentRecord)
                .where(
                    AnomalyAssessmentRecord.simulation_run_id == run_id,
                    AnomalyAssessmentRecord.model_id == model_id,
                    AnomalyAssessmentRecord.sequence_number <= limit,
                )
            )
            or 0
        )
        if assessment_count < limit:
            raise ApplicationError(
                "RESPONSE_ASSESSMENTS_REQUIRED",
                "Complete synthetic assessments through the requested sequence are required.",
                422,
            )

        existing = session.scalar(
            select(ResponseAnalysisRecord).where(
                ResponseAnalysisRecord.simulation_run_id == run_id,
                ResponseAnalysisRecord.model_id == model_id,
                ResponseAnalysisRecord.incident_candidate_id == candidate.incident_candidate_id,
                ResponseAnalysisRecord.through_sequence_number == limit,
                ResponseAnalysisRecord.response_engine_version == ENGINE_VERSION,
            )
        )
        if existing is not None and not force:
            return self.analysis_schema(session, existing, False)
        if existing is not None:
            self._delete_analysis(session, existing.response_analysis_id)

        evidence_rows = list(
            session.execute(
                select(IncidentEvidenceRecord, TelemetryEventRecord)
                .join(
                    TelemetryEventRecord,
                    TelemetryEventRecord.event_id == IncidentEvidenceRecord.event_id,
                )
                .where(
                    IncidentEvidenceRecord.incident_candidate_id == candidate.incident_candidate_id,
                    IncidentEvidenceRecord.sequence_number <= limit,
                )
                .order_by(IncidentEvidenceRecord.sequence_number)
            )
        )
        if not evidence_rows:
            raise ApplicationError(
                "RESPONSE_EVIDENCE_REQUIRED",
                "Incident evidence is unavailable through the requested sequence.",
                422,
            )
        observations = list(
            session.scalars(
                select(TechniqueObservationRecord).where(
                    TechniqueObservationRecord.simulation_run_id == run_id,
                    TechniqueObservationRecord.model_id == model_id,
                    TechniqueObservationRecord.sequence_number <= limit,
                )
            )
        )
        prediction = None
        hypotheses: list[PredictionHypothesisRecord] = []
        if prediction_enabled:
            prediction = session.scalar(
                select(PredictionSnapshotRecord)
                .where(
                    PredictionSnapshotRecord.simulation_run_id == run_id,
                    PredictionSnapshotRecord.model_id == model_id,
                    PredictionSnapshotRecord.through_sequence_number <= limit,
                )
                .order_by(PredictionSnapshotRecord.through_sequence_number.desc())
            )
            if prediction is not None:
                hypotheses = list(
                    session.scalars(
                        select(PredictionHypothesisRecord)
                        .where(
                            PredictionHypothesisRecord.prediction_snapshot_id
                            == prediction.prediction_snapshot_id
                        )
                        .order_by(PredictionHypothesisRecord.rank)
                        .limit(top_k * 3)
                    )
                )

        topology_state = topology_path_service.run_state(session, run_id, model_id, limit)
        include_sink = "simulation-egress-sink-01" in set(topology_state.observed_asset_ids)
        analysis_id = self._id(
            "analysis", run_id, model_id, candidate.incident_candidate_id, str(limit)
        )
        now = datetime.now(UTC)
        analysis = ResponseAnalysisRecord(
            response_analysis_id=analysis_id,
            simulation_run_id=run_id,
            model_id=model_id,
            incident_candidate_id=candidate.incident_candidate_id,
            prediction_snapshot_id=prediction.prediction_snapshot_id if prediction else None,
            through_sequence_number=limit,
            response_engine_version=ENGINE_VERSION,
            recommendation_count=0,
            synthetic=True,
            created_at=now,
        )
        session.add(analysis)
        self._seed_catalogue(session)

        events = [event for _, event in evidence_rows]
        known_nodes = {item.asset_id: item for item in topology_service.nodes(include_sink)}
        assets = sorted(
            {
                item
                for event in events
                for item in (event.source_id, event.destination_id)
                if item in known_nodes
            }
        )
        users = sorted({event.user_id for event in events if event.user_id})
        predicted_assets = sorted(
            {
                item.predicted_asset_id
                for item in hypotheses
                if item.predicted_asset_id in known_nodes
            }
        )
        edge_ids = sorted(
            set(topology_state.observed_edge_ids)
            | set(topology_state.correlated_edge_ids)
            | set(topology_state.predicted_edge_ids)
            | {
                f"{event.source_id}--{event.destination_id}"
                for event in events
                if event.destination_id is not None
            }
        )
        causal_correlated_edge_ids = {
            f"{event.source_id}--{event.destination_id}"
            for event in events
            if event.destination_id is not None
        }
        technique_ids = sorted({item.technique_id for item in observations})
        targets: list[tuple[DefensivePlaybook, str, str]] = []
        for asset_id in assets:
            targets.extend([(PLAYBOOKS[0], "asset", asset_id), (PLAYBOOKS[6], "asset", asset_id)])
            asset_type = known_nodes[asset_id].asset_type
            if asset_type == "external_client":
                targets.append((PLAYBOOKS[3], "external_client", asset_id))
            if asset_type == "kubernetes_pod":
                targets.append((PLAYBOOKS[5], "kubernetes_pod", asset_id))
            if asset_type in {"database", "object_storage"}:
                targets.append((PLAYBOOKS[7], asset_type, asset_id))
            if asset_type in {"api_gateway", "load_balancer"}:
                targets.append((PLAYBOOKS[8], asset_type, asset_id))
        for asset_id in predicted_assets:
            predicted_type = known_nodes[asset_id].asset_type
            if predicted_type in {"database", "object_storage"}:
                targets.append((PLAYBOOKS[7], predicted_type, asset_id))
        for user_id in users:
            targets.append((PLAYBOOKS[1], "user", user_id))
            if any(
                event.privilege_level or event.event_type == "privilege_change" for event in events
            ):
                targets.append((PLAYBOOKS[2], "user", user_id))
        base_edges_by_id = {item.edge_id: item for item in topology_service.edges(include_sink)}
        anomalous_ingress_edges = set(topology_state.anomalous_observed_edge_ids)
        for edge_id in edge_ids:
            edge = base_edges_by_id.get(edge_id)
            if edge is None:
                continue
            targets.append((PLAYBOOKS[4], "relationship", edge_id))
            source_node = known_nodes.get(edge.source_asset_id)
            if (
                edge_id in anomalous_ingress_edges
                and source_node is not None
                and source_node.asset_type == "external_client"
            ):
                # The one narrowly-scoped, evidence-backed ingress relationship
                # eligible for full automation - see PLAYBOOKS[9]'s docstring.
                targets.append((PLAYBOOKS[9], "relationship", edge_id))

        unique = {(p.playbook_id, kind, target): (p, kind, target) for p, kind, target in targets}
        ranked: list[_RankedAction] = []
        for playbook, kind, target in unique.values():
            components, penalties = self._score(
                playbook, target, assets, predicted_assets, technique_ids, topology_state
            )
            score = round(max(0.0, min(1.0, sum(components.values()) - sum(penalties.values()))), 6)
            defense, explanation = self._defense_score(
                playbook, kind, target, components, known_nodes
            )
            ranked.append(
                (
                    defense["defense_score"],
                    score,
                    playbook,
                    kind,
                    target,
                    components,
                    penalties,
                    defense,
                    explanation,
                )
            )
        # The Blue Agent ranks on Defense Score, highest net defensive value first.
        ranked.sort(key=lambda item: (-item[0], item[2].playbook_id, item[4]))
        selected: list[_RankedAction] = []
        selected_playbooks: set[str] = set()
        for item in ranked:
            if item[2].playbook_id not in selected_playbooks:
                selected.append(item)
                selected_playbooks.add(item[2].playbook_id)
            if len(selected) == top_k:
                break
        for item in ranked:
            if len(selected) == top_k:
                break
            if item not in selected:
                selected.append(item)

        for rank, (
            _defense_value,
            score,
            playbook,
            kind,
            target,
            components,
            penalties,
            defense,
            explanation,
        ) in enumerate(selected, 1):
            recommendation_id = self._id(
                "recommendation", analysis_id, playbook.playbook_id, target
            )
            record = ResponseRecommendationRecord(
                recommendation_id=recommendation_id,
                response_analysis_id=analysis_id,
                simulation_run_id=run_id,
                model_id=model_id,
                incident_candidate_id=candidate.incident_candidate_id,
                prediction_snapshot_id=prediction.prediction_snapshot_id if prediction else None,
                through_sequence_number=limit,
                playbook_id=playbook.playbook_id,
                target_type=kind,
                target_id=target,
                rank=rank,
                recommendation_score=score,
                component_scores_json=components,
                penalties_json=penalties,
                defense_score=defense["defense_score"],
                defense_components_json=defense,
                defense_explanation=explanation,
                required_approval_tier=playbook.approval_tier,
                recommendation_state="simulation_complete",
                evidence_summary_json=self._evidence_summary(events, technique_ids, target),
                rationale=(
                    f"{BLUE_AGENT_NAME}: {playbook.name} applies to causally available synthetic "
                    f"evidence for {target}; scores are relative ranking measures."
                ),
                warnings_json=[
                    "No real defensive action has been approved or performed.",
                    "Simulated interruption does not guarantee containment.",
                ],
                synthetic=True,
                created_at=now,
            )
            session.add(record)
            session.flush()
            session.add(
                self._simulate(
                    record,
                    playbook,
                    topology_state,
                    causal_correlated_edge_ids,
                    include_sink,
                    now,
                )
            )
        analysis.recommendation_count = len(selected)
        session.commit()
        return self.analysis_schema(session, analysis, force)

    def _score(
        self,
        playbook: DefensivePlaybook,
        target: str,
        assets: list[str],
        predicted_assets: list[str],
        techniques: list[str],
        state: object,
    ) -> tuple[dict[str, float], dict[str, float]]:
        correlated = target in getattr(state, "correlated_asset_ids", []) or target in getattr(
            state, "correlated_edge_ids", []
        )
        correlated = correlated or target in getattr(state, "observed_edge_ids", [])
        predicted = target in predicted_assets or target in getattr(state, "predicted_edge_ids", [])
        components = {
            "evidence_applicability": WEIGHTS["evidence_applicability"],
            "correlated_path_interruption": WEIGHTS["correlated_path_interruption"]
            if correlated
            else 0.0,
            "predicted_path_interruption": WEIGHTS["predicted_path_interruption"]
            if predicted
            else 0.0,
            "technique_tactic_coverage": WEIGHTS["technique_tactic_coverage"]
            * min(1.0, len(techniques) / 3),
            "target_relevance": WEIGHTS["target_relevance"]
            if target in assets or predicted or correlated
            else 0.0,
            "reversibility": WEIGHTS["reversibility"]
            if playbook.reversibility == "reversible"
            else 0.0,
            "policy_compatibility": WEIGHTS["policy_compatibility"]
            if playbook.approval_tier != "prohibited"
            else 0.0,
        }
        impact_penalty = {"low": 0.0, "medium": 0.05, "high": 0.12}[
            playbook.default_operational_impact
        ]
        penalties = {
            "operational_disruption": impact_penalty,
            "blast_radius": 0.04 if playbook.default_blast_radius == "service" else 0.0,
            "unsupported_prerequisites": 0.0,
            "critical_service_impact": 0.08
            if "database" in playbook.supported_target_types
            else 0.0,
            "contradictory_evidence": 0.0,
            "unavailable_target": 0.0,
            "action_redundancy": 0.0,
        }
        return components, penalties

    @staticmethod
    def _defense_score(
        playbook: DefensivePlaybook,
        kind: str,
        target: str,
        components: dict[str, float],
        nodes: Mapping[str, object],
    ) -> tuple[dict[str, float], str]:
        """Blue Agent objective.

        Defense Score = Security Improvement - Service Disruption - Resource Cost - SLA Penalty.
        """
        security_improvement = round(min(1.0, sum(components.values())), 6)
        service_disruption = round(
            OPERATIONAL_IMPACT_COST[playbook.default_operational_impact]
            + BLAST_RADIUS_COST.get(playbook.default_blast_radius, 0.04),
            6,
        )
        resource_cost = round(playbook.resource_cost_weight, 6)
        if kind == "user":
            serving_factor = 0.5
        elif kind == "relationship":
            endpoints = [nodes.get(part) for part in target.split("--")]
            serving_factor = (
                1.0
                if any(getattr(item, "zone", None) in SERVING_ZONES for item in endpoints)
                else 0.5
            )
        else:
            serving_factor = (
                1.0 if getattr(nodes.get(target), "zone", None) in SERVING_ZONES else 0.5
            )
        sla_penalty = round(playbook.sla_sensitivity_weight * serving_factor, 6)
        score = round(
            max(
                -1.0,
                min(
                    1.0,
                    security_improvement - service_disruption - resource_cost - sla_penalty,
                ),
            ),
            6,
        )
        explanation = (
            f"{playbook.name} on {target}: security improvement {security_improvement:.2f} "
            f"less service disruption {service_disruption:.2f}, resource cost "
            f"{resource_cost:.2f} and SLA penalty {sla_penalty:.2f} gives a Defense Score of "
            f"{score:.2f}."
        )
        return (
            {
                "security_improvement": security_improvement,
                "service_disruption": service_disruption,
                "resource_cost": resource_cost,
                "sla_penalty": sla_penalty,
                "defense_score": score,
            },
            explanation,
        )

    def _simulate(
        self,
        recommendation: ResponseRecommendationRecord,
        playbook: DefensivePlaybook,
        state: object,
        causal_correlated_edge_ids: set[str],
        include_sink: bool,
        now: datetime,
    ) -> ResponseImpactSimulationRecord:
        base_edges = {item.edge_id: item for item in topology_service.edges(include_sink)}
        base_nodes = {item.asset_id: item for item in topology_service.nodes(include_sink)}
        changed_edges: set[str] = set()
        changed_nodes: set[str] = set()
        operation = playbook.topology_mutation_specification["operation"]
        if operation == "remove_edge" and recommendation.target_id in base_edges:
            changed_edges.add(recommendation.target_id)
        elif operation == "remove_inbound_edges":
            changed_nodes.add(recommendation.target_id)
            changed_edges = {
                eid
                for eid, edge in base_edges.items()
                if edge.destination_asset_id == recommendation.target_id
            }
        elif operation == "remove_incident_edges":
            changed_nodes.add(recommendation.target_id)
            changed_edges = {
                eid
                for eid, edge in base_edges.items()
                if recommendation.target_id in {edge.source_asset_id, edge.destination_asset_id}
            }
        elif recommendation.target_type != "user":
            changed_nodes.add(recommendation.target_id)
        correlated = set(getattr(state, "correlated_edge_ids", [])) | causal_correlated_edge_ids
        predicted = set(getattr(state, "predicted_edge_ids", []))
        after_edges = set(base_edges) - changed_edges
        sources = set(getattr(state, "observed_asset_ids", []))
        sensitive = {
            node.asset_id
            for node in base_nodes.values()
            if node.sensitivity in {"restricted", "highly_restricted"}
        }
        before_reachable = self._reachable_count(sources, sensitive, set(base_edges), base_edges)
        after_reachable = self._reachable_count(sources, sensitive, after_edges, base_edges)
        corr_interrupted = len(correlated & changed_edges)
        pred_interrupted = len(predicted & changed_edges)
        opportunity = max(1, len(correlated | predicted))
        interruption = round(min(1.0, (corr_interrupted + pred_interrupted) / opportunity), 6)
        disruption = round(min(1.0, len(changed_edges) / max(1, len(base_edges))), 6)
        return ResponseImpactSimulationRecord(
            simulation_id=self._id("simulation", recommendation.recommendation_id),
            recommendation_id=recommendation.recommendation_id,
            simulation_run_id=recommendation.simulation_run_id,
            through_sequence_number=recommendation.through_sequence_number,
            base_topology_version=TOPOLOGY_VERSION,
            simulation_engine_version=SIMULATION_VERSION,
            target_type=recommendation.target_type,
            target_id=recommendation.target_id,
            changed_node_ids_json=sorted(changed_nodes),
            changed_edge_ids_json=sorted(changed_edges),
            paths_before_json=self._paths(correlated, predicted),
            paths_after_json=self._paths(correlated - changed_edges, predicted - changed_edges),
            correlated_paths_interrupted=corr_interrupted,
            predicted_paths_interrupted=pred_interrupted,
            sensitive_assets_reachable_before=before_reachable,
            sensitive_assets_reachable_after=after_reachable,
            expected_relationships_affected=len(changed_edges & set(base_edges)),
            affected_asset_count=len(
                changed_nodes | {part for edge in changed_edges for part in edge.split("--")}
            ),
            affected_edge_count=len(changed_edges),
            interruption_score=interruption,
            residual_exposure_score=round(after_reachable / max(1, before_reachable), 6),
            operational_disruption_score=disruption,
            blast_radius=playbook.default_blast_radius,
            reversibility=playbook.reversibility,
            warnings_json=[
                "Clone-only graph result; the base topology is unchanged.",
                "Relative heuristic measures are not probabilities.",
            ],
            synthetic=True,
            created_at=now,
        )

    @staticmethod
    def _reachable_count(
        sources: set[str],
        sensitive: set[str],
        allowed: set[str],
        edges: dict[str, InfrastructureEdge],
    ) -> int:
        seen = set(sources)
        queue = deque(sources)
        while queue:
            current = queue.popleft()
            for edge_id in allowed:
                edge = edges[edge_id]
                if edge.source_asset_id == current and edge.destination_asset_id not in seen:
                    seen.add(edge.destination_asset_id)
                    queue.append(edge.destination_asset_id)
        return len(seen & sensitive)

    @staticmethod
    def _paths(correlated: set[str], predicted: set[str]) -> list[dict[str, object]]:
        paths: list[dict[str, object]] = [
            {"path_type": "correlated", "edge_id": item} for item in sorted(correlated)[:20]
        ]
        paths.extend(
            {"path_type": "predicted", "edge_id": item, "hypothetical": True}
            for item in sorted(predicted)[:20]
        )
        return paths

    @staticmethod
    def _evidence_summary(
        events: list[TelemetryEventRecord], techniques: list[str], target: str
    ) -> list[str]:
        sequences = [
            str(index + 1)
            for index, event in enumerate(events)
            if target
            in {
                event.source_id,
                event.destination_id,
                event.user_id,
                f"{event.source_id}--{event.destination_id}",
            }
        ]
        return [
            "Target supported by causal sequences: "
            f"{', '.join(sequences) or 'indirect path evidence'}",
            f"Observed synthetic techniques: {', '.join(techniques) or 'none mapped'}",
        ]

    def analysis_schema(
        self, session: Session, record: ResponseAnalysisRecord, force: bool
    ) -> ResponseAnalysisResult:
        recommendations = list(
            session.scalars(
                select(ResponseRecommendationRecord)
                .where(
                    ResponseRecommendationRecord.response_analysis_id == record.response_analysis_id
                )
                .order_by(ResponseRecommendationRecord.rank)
            )
        )
        return ResponseAnalysisResult(
            response_analysis_id=record.response_analysis_id,
            run_id=record.simulation_run_id,
            model_id=record.model_id,
            incident_candidate_id=record.incident_candidate_id,
            prediction_snapshot_id=record.prediction_snapshot_id,
            through_sequence_number=record.through_sequence_number,
            response_engine_version=record.response_engine_version,
            recommendation_count=record.recommendation_count,
            recommendations=[self.recommendation_schema(session, item) for item in recommendations],
            force_reanalyze=force,
            synthetic=True,
            created_at=self._utc(record.created_at),
        )

    def recommendation_schema(
        self, session: Session, record: ResponseRecommendationRecord
    ) -> ResponseRecommendation:
        simulation = session.scalar(
            select(ResponseImpactSimulationRecord).where(
                ResponseImpactSimulationRecord.recommendation_id == record.recommendation_id
            )
        )
        playbook = response_playbook_service.get(record.playbook_id)
        return ResponseRecommendation(
            recommendation_id=record.recommendation_id,
            response_analysis_id=record.response_analysis_id,
            run_id=record.simulation_run_id,
            model_id=record.model_id,
            incident_candidate_id=record.incident_candidate_id,
            prediction_snapshot_id=record.prediction_snapshot_id,
            through_sequence_number=record.through_sequence_number,
            playbook_id=record.playbook_id,
            playbook_name=playbook.name,
            target_type=record.target_type,
            target_id=record.target_id,
            rank=record.rank,
            recommendation_score=record.recommendation_score,
            component_scores=record.component_scores_json,
            penalties=record.penalties_json,
            defense_score=record.defense_score,
            defense_components=record.defense_components_json,
            defense_explanation=record.defense_explanation,
            required_approval_tier=record.required_approval_tier,
            recommendation_state=record.recommendation_state,
            evidence_summary=record.evidence_summary_json,
            rationale=record.rationale,
            warnings=record.warnings_json,
            synthetic=True,
            created_at=self._utc(record.created_at),
            simulation=self.simulation_schema(record, simulation) if simulation else None,
        )

    def simulation_schema(
        self, recommendation: ResponseRecommendationRecord, record: ResponseImpactSimulationRecord
    ) -> ResponseImpactSimulation:
        return ResponseImpactSimulation(
            simulation_id=record.simulation_id,
            recommendation_id=record.recommendation_id,
            run_id=record.simulation_run_id,
            through_sequence_number=record.through_sequence_number,
            base_topology_version=record.base_topology_version,
            simulation_engine_version=record.simulation_engine_version,
            target_type=record.target_type,
            target_id=record.target_id,
            changed_node_ids=record.changed_node_ids_json,
            changed_edge_ids=record.changed_edge_ids_json,
            paths_before=record.paths_before_json,
            paths_after=record.paths_after_json,
            correlated_paths_interrupted=record.correlated_paths_interrupted,
            predicted_paths_interrupted=record.predicted_paths_interrupted,
            sensitive_assets_reachable_before=record.sensitive_assets_reachable_before,
            sensitive_assets_reachable_after=record.sensitive_assets_reachable_after,
            expected_relationships_affected=record.expected_relationships_affected,
            affected_asset_count=record.affected_asset_count,
            affected_edge_count=record.affected_edge_count,
            interruption_score=record.interruption_score,
            residual_exposure_score=record.residual_exposure_score,
            operational_disruption_score=record.operational_disruption_score,
            blast_radius=record.blast_radius,
            reversibility=record.reversibility,
            approval_tier=recommendation.required_approval_tier,
            warnings=record.warnings_json,
            synthetic=True,
            created_at=self._utc(record.created_at),
        )

    def summary(self, session: Session, run_id: str, model_id: str) -> ResponseRunSummary:
        analysis = session.scalar(
            select(ResponseAnalysisRecord)
            .where(
                ResponseAnalysisRecord.simulation_run_id == run_id,
                ResponseAnalysisRecord.model_id == model_id,
            )
            .order_by(ResponseAnalysisRecord.through_sequence_number.desc())
        )
        if analysis is None:
            raise ApplicationError(
                "RESPONSE_ANALYSIS_NOT_FOUND", "No synthetic response analysis was found.", 404
            )
        top = session.scalar(
            select(ResponseRecommendationRecord)
            .where(
                ResponseRecommendationRecord.response_analysis_id == analysis.response_analysis_id
            )
            .order_by(ResponseRecommendationRecord.rank)
        )
        return ResponseRunSummary(
            run_id=run_id,
            model_id=model_id,
            through_sequence_number=analysis.through_sequence_number,
            recommendation_count=analysis.recommendation_count,
            top_recommendation=self.recommendation_schema(session, top) if top else None,
            analysis_sequence=analysis.through_sequence_number,
            synthetic=True,
        )

    @staticmethod
    def _delete_analysis(session: Session, analysis_id: str) -> None:
        ids = list(
            session.scalars(
                select(ResponseRecommendationRecord.recommendation_id).where(
                    ResponseRecommendationRecord.response_analysis_id == analysis_id
                )
            )
        )
        if ids:
            session.execute(
                delete(ResponseImpactSimulationRecord).where(
                    ResponseImpactSimulationRecord.recommendation_id.in_(ids)
                )
            )
        session.execute(
            delete(ResponseRecommendationRecord).where(
                ResponseRecommendationRecord.response_analysis_id == analysis_id
            )
        )
        session.execute(
            delete(ResponseAnalysisRecord).where(
                ResponseAnalysisRecord.response_analysis_id == analysis_id
            )
        )

    @staticmethod
    def _seed_catalogue(session: Session) -> None:
        for playbook in PLAYBOOKS:
            if session.get(ResponsePlaybookRecord, playbook.playbook_id) is None:
                session.add(
                    ResponsePlaybookRecord(
                        playbook_id=playbook.playbook_id,
                        playbook_version=playbook.playbook_version,
                        catalogue_version=playbook.catalogue_version,
                        definition_json=playbook.model_dump(mode="json"),
                        synthetic=True,
                    )
                )

    @staticmethod
    def _id(*parts: str) -> str:
        return str(uuid5(NAMESPACE_URL, "aegisarena-response:" + ":".join(parts)))

    @staticmethod
    def _utc(value: datetime) -> datetime:
        return value.replace(tzinfo=value.tzinfo or UTC)


response_service = ResponseService()
