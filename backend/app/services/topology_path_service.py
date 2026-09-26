from collections import deque

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import (
    AnomalyAssessmentRecord,
    IncidentCandidateRecord,
    IncidentEvidenceRecord,
    PredictionHypothesisRecord,
    PredictionSnapshotRecord,
    SimulationRunRecord,
    TechniqueObservationRecord,
)
from app.schemas.topology import RunTopologyState, TopologyEventMapping, TopologyPath
from app.services.telemetry_service import telemetry_service
from app.services.topology_service import topology_service


class TopologyPathService:
    def paths(
        self,
        session: Session,
        source: str,
        destination: str,
        path_type: str,
        run_id: str | None,
        model_id: str | None,
        through_sequence: int | None,
        maximum_paths: int,
    ) -> list[TopologyPath]:
        include_sink = self._include_sink(session, run_id)
        topology_service.node(source, include_sink)
        topology_service.node(destination, include_sink)
        allowed, evidence, limit = self._allowed_edges(
            session, path_type, run_id, model_id, through_sequence
        )
        results = self._find_paths(source, destination, allowed, maximum_paths)
        if not results:
            raise ApplicationError(
                "TOPOLOGY_PATH_UNREACHABLE",
                "No path exists for the requested synthetic path semantics.",
                404,
            )
        hypothetical = path_type == "predicted"
        statement = (
            "Hypothetical path derived from synthetic ranked predictions."
            if hypothetical
            else f"{path_type.capitalize()} path derived from {evidence}."
        )
        return [
            TopologyPath(
                path_type=path_type,
                ordered_node_ids=nodes,
                ordered_edge_ids=[
                    f"{nodes[index]}--{nodes[index + 1]}" for index in range(len(nodes) - 1)
                ],
                path_length=len(nodes) - 1,
                evidence_source=evidence,
                through_sequence_number=limit,
                hypothetical=hypothetical,
                statement=statement,
                synthetic=True,
            )
            for nodes in results
        ]

    def run_state(
        self,
        session: Session,
        run_id: str,
        model_id: str | None,
        through_sequence: int | None,
    ) -> RunTopologyState:
        run = session.get(SimulationRunRecord, run_id)
        if run is None:
            raise ApplicationError(
                "SIMULATION_RUN_NOT_FOUND", "The simulation run was not found.", 404
            )
        events = telemetry_service.list_run_events(session, run_id)
        limit = min(through_sequence or len(events), len(events))
        include_sink = run.scenario_id == "staged-compromise-demo"
        known_assets = {item.asset_id for item in topology_service.nodes(include_sink)}
        topology_edges = {
            (item.source_asset_id, item.destination_asset_id): item.edge_id
            for item in topology_service.edges(include_sink)
        }
        observed_pairs = {
            (event.source_id, event.destination_id)
            for event in events[:limit]
            if event.source_id in known_assets and event.destination_id in known_assets
        }
        assessments = (
            {
                item.event_id: item
                for item in session.scalars(
                    select(AnomalyAssessmentRecord).where(
                        AnomalyAssessmentRecord.simulation_run_id == run_id,
                        AnomalyAssessmentRecord.model_id == model_id,
                        AnomalyAssessmentRecord.sequence_number <= limit,
                    )
                )
            }
            if model_id
            else {}
        )
        techniques_by_event: dict[str, list[str]] = {}
        if model_id:
            for item in session.scalars(
                select(TechniqueObservationRecord).where(
                    TechniqueObservationRecord.simulation_run_id == run_id,
                    TechniqueObservationRecord.model_id == model_id,
                    TechniqueObservationRecord.sequence_number <= limit,
                )
            ):
                techniques_by_event.setdefault(item.event_id, []).append(item.technique_id)
        mappings: list[TopologyEventMapping] = []
        anomalous_pairs: set[tuple[str, str]] = set()
        unexpected_pairs: set[tuple[str, str]] = set()
        for sequence, event in enumerate(events[:limit], 1):
            source = event.source_id if event.source_id in known_assets else None
            destination = event.destination_id if event.destination_id in known_assets else None
            pair = (source, destination) if source and destination else None
            assessment = assessments.get(event.event_id)
            anomalous = bool(assessment and assessment.classification == "anomalous")
            unexpected = bool(pair and pair not in topology_edges)
            if pair and anomalous:
                anomalous_pairs.add(pair)
            if pair and unexpected:
                unexpected_pairs.add(pair)
            mappings.append(
                TopologyEventMapping(
                    event_id=event.event_id,
                    sequence_number=sequence,
                    source_asset_id=source,
                    destination_asset_id=destination,
                    edge_id=topology_edges.get(pair) if pair else None,
                    unexpected_observed=unexpected,
                    anomalous_observed=anomalous,
                    anomaly_score=assessment.anomaly_score if assessment else None,
                    classification=assessment.classification if assessment else None,
                    technique_ids=sorted(techniques_by_event.get(event.event_id, [])),
                    synthetic=True,
                )
            )
        correlated_pairs: set[tuple[str, str]] = set()
        predicted_pairs: set[tuple[str, str]] = set()
        if model_id:
            candidate = session.scalar(
                select(IncidentCandidateRecord).where(
                    IncidentCandidateRecord.simulation_run_id == run_id,
                    IncidentCandidateRecord.model_id == model_id,
                )
            )
            if candidate:
                evidence_ids = set(
                    session.scalars(
                        select(IncidentEvidenceRecord.event_id).where(
                            IncidentEvidenceRecord.incident_candidate_id
                            == candidate.incident_candidate_id,
                            IncidentEvidenceRecord.sequence_number <= limit,
                        )
                    )
                )
                correlated_pairs = {
                    (event.source_id, event.destination_id)
                    for event in events[:limit]
                    if event.event_id in evidence_ids and event.destination_id
                }
            snapshot = session.scalar(
                select(PredictionSnapshotRecord)
                .where(
                    PredictionSnapshotRecord.simulation_run_id == run_id,
                    PredictionSnapshotRecord.model_id == model_id,
                    PredictionSnapshotRecord.through_sequence_number <= limit,
                )
                .order_by(PredictionSnapshotRecord.through_sequence_number.desc())
            )
            if snapshot and events[:limit]:
                current = events[limit - 1].destination_id or events[limit - 1].source_id
                predicted_assets = session.scalars(
                    select(PredictionHypothesisRecord.predicted_asset_id).where(
                        PredictionHypothesisRecord.prediction_snapshot_id
                        == snapshot.prediction_snapshot_id,
                        PredictionHypothesisRecord.predicted_asset_id.is_not(None),
                    )
                )
                predicted_pairs = {(current, asset) for asset in predicted_assets if asset}
        return RunTopologyState(
            simulation_run_id=run_id,
            model_id=model_id,
            observed_asset_ids=self._assets(observed_pairs),
            observed_edge_ids=self._edge_ids(observed_pairs),
            correlated_asset_ids=self._assets(correlated_pairs),
            correlated_edge_ids=self._edge_ids(correlated_pairs),
            predicted_asset_ids=self._assets(predicted_pairs),
            predicted_edge_ids=self._edge_ids(predicted_pairs),
            anomalous_observed_asset_ids=self._assets(anomalous_pairs),
            anomalous_observed_edge_ids=self._edge_ids(anomalous_pairs),
            unexpected_observed_edge_ids=self._edge_ids(unexpected_pairs),
            event_mappings=mappings,
            predicted_paths=self._predicted_paths(predicted_pairs, limit),
            current_sequence_limit=limit,
            synthetic=True,
        )

    @staticmethod
    def _predicted_paths(pairs: set[tuple[str, str]], limit: int) -> list[TopologyPath]:
        return [
            TopologyPath(
                path_type="predicted",
                ordered_node_ids=[source, destination],
                ordered_edge_ids=[f"{source}--{destination}"],
                path_length=1,
                evidence_source="persisted synthetic ranked prediction",
                through_sequence_number=limit,
                hypothetical=True,
                statement="Hypothetical path derived from synthetic ranked predictions.",
                synthetic=True,
            )
            for source, destination in sorted(pairs)
        ]

    def _allowed_edges(
        self,
        session: Session,
        path_type: str,
        run_id: str | None,
        model_id: str | None,
        through_sequence: int | None,
    ) -> tuple[set[tuple[str, str]], str, int | None]:
        if path_type == "expected":
            return (
                {
                    (edge.source_asset_id, edge.destination_asset_id)
                    for edge in topology_service.edges(self._include_sink(session, run_id))
                },
                "versioned synthetic architecture",
                through_sequence,
            )
        if not run_id:
            raise ApplicationError(
                "TOPOLOGY_RUN_REQUIRED", "A simulation run is required for this path type.", 422
            )
        state = self.run_state(session, run_id, model_id, through_sequence)
        ids = getattr(state, f"{path_type}_edge_ids")
        if path_type in {"correlated", "predicted"} and not model_id:
            raise ApplicationError(
                "TOPOLOGY_MODEL_REQUIRED", "A model is required for this path type.", 422
            )
        return (
            {tuple(edge_id.split("--", 1)) for edge_id in ids},
            f"persisted synthetic {path_type} evidence",
            state.current_sequence_limit,
        )

    @staticmethod
    def _find_paths(
        source: str, destination: str, edges: set[tuple[str, str]], maximum: int
    ) -> list[list[str]]:
        queue = deque([[source]])
        found: list[list[str]] = []
        shortest: int | None = None
        while queue and len(found) < maximum:
            path = queue.popleft()
            if shortest is not None and len(path) - 1 > shortest:
                break
            if path[-1] == destination:
                shortest = len(path) - 1
                found.append(path)
                continue
            for left, right in sorted(edges):
                if left == path[-1] and right not in path:
                    queue.append([*path, right])
        return found

    @staticmethod
    def _assets(pairs: set[tuple[str, str]]) -> list[str]:
        return sorted({asset for pair in pairs for asset in pair})

    @staticmethod
    def _edge_ids(pairs: set[tuple[str, str]]) -> list[str]:
        return sorted(f"{source}--{destination}" for source, destination in pairs)

    @staticmethod
    def _include_sink(session: Session, run_id: str | None) -> bool:
        run = session.get(SimulationRunRecord, run_id) if run_id else None
        return bool(run and run.scenario_id == "staged-compromise-demo")


topology_path_service = TopologyPathService()
