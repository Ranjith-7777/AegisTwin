from collections import deque

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.database.models import (
    IncidentCandidateRecord,
    IncidentEvidenceRecord,
    PredictionHypothesisRecord,
    PredictionSnapshotRecord,
    SimulationRunRecord,
)
from app.schemas.topology import RunTopologyState, TopologyPath
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
        observed_pairs = {
            (event.source_id, event.destination_id)
            for event in events[:limit]
            if event.destination_id
        }
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
            current_sequence_limit=limit,
            synthetic=True,
        )

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
