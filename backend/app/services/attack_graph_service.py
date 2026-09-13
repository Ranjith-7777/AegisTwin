"""Deterministic, explainable attack-path engine over the synthetic Digital Twin.

This module does not introduce a second graph model: it reads the existing
canonical topology (`topology_service.nodes/edges`) and the existing
sequence-bounded evidence (`topology_path_service.run_state`) — the same
data every other Digital Twin feature already uses. See
docs/architecture/ATTACK_GRAPH.md for the algorithm and scoring rationale.
"""

from __future__ import annotations

import itertools
from collections import deque
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.events.envelope import AttackPathDiscoveredPayload, DomainEvent
from app.events.registry import get_event_bus
from app.events.types import EventType
from app.schemas.attack_graph import (
    AttackPath,
    AttackPathAnalysisResult,
    AttackPathScore,
    AttackPathStep,
    AttackPathType,
)
from app.schemas.topology import InfrastructureEdge, InfrastructureNode
from app.services.topology_path_service import topology_path_service
from app.services.topology_service import topology_service

CRITICALITY_WEIGHT = {"low": 0.0, "medium": 10.0, "high": 20.0, "critical": 30.0}
SENSITIVITY_BONUS = {"highly_restricted": 10.0, "restricted": 5.0}
PATH_NAMESPACE_LABEL = "attack-path"


def _attack_semantics(
    source: InfrastructureNode, destination: InfrastructureNode, edge: InfrastructureEdge
) -> str:
    """A short, deterministic relationship label for explanation text.

    Derived purely from the existing node asset_type/zone and edge
    relationship_type/protocol fields — no new data is invented. See
    docs/architecture/ATTACK_GRAPH.md "Relationship semantics".
    """

    dst_type = destination.asset_type
    protocol = (edge.protocol_label or "").lower()
    if dst_type in {"identity_service"}:
        return "uses_identity"
    if dst_type in {"admin_service"}:
        return "can_administer" if edge.trust_level == "elevated" else "calls"
    if dst_type == "database":
        return "writes_to" if protocol in {"database", "restore"} else "reads_from"
    if dst_type == "object_storage":
        return "writes_to"
    if dst_type == "backup_service":
        return "manages_backup_of" if source.asset_type == "database" else "reads_from"
    if dst_type == "monitoring_service":
        return "reports_to"
    if dst_type in {"kubernetes_control_plane", "kubernetes_node"}:
        return "deployed_on"
    if dst_type == "kubernetes_pod":
        return (
            "routes_to"
            if source.asset_type in {"api_gateway", "load_balancer"}
            else "network_reachable"
        )
    if dst_type in {"api_gateway", "load_balancer"}:
        return "routes_to"
    return "network_reachable"


def _is_privileged(edge: InfrastructureEdge) -> bool:
    return edge.trust_level == "elevated"


@dataclass(frozen=True)
class _Graph:
    nodes: dict[str, InfrastructureNode]
    edges: list[InfrastructureEdge]
    adjacency: dict[str, list[InfrastructureEdge]]

    @staticmethod
    def build(edges: list[InfrastructureEdge], nodes: list[InfrastructureNode]) -> _Graph:
        adjacency: dict[str, list[InfrastructureEdge]] = {}
        for edge in edges:
            adjacency.setdefault(edge.source_asset_id, []).append(edge)
        for bucket in adjacency.values():
            bucket.sort(key=lambda item: item.edge_id)
        return _Graph(nodes={n.asset_id: n for n in nodes}, edges=edges, adjacency=adjacency)


def _enumerate_paths(
    graph: _Graph, source: str, target: str | None, max_depth: int, max_paths: int
) -> list[list[InfrastructureEdge]]:
    """Bounded, deterministic enumeration of simple (no-revisit) paths.

    Breadth-first over path *prefixes* so shorter paths are discovered
    before longer ones; a path is only cycle-free by construction (a node
    already on the path is never re-added), which also guarantees
    termination regardless of cycles in the underlying graph. Stops once
    `max_paths` paths have been found or no path can be extended further
    within `max_depth` hops - this bounds an otherwise combinatorial search
    on a graph this small (see docs/architecture/ATTACK_GRAPH.md
    "Complexity").
    """

    if source not in graph.nodes:
        raise ApplicationError("ATTACK_GRAPH_ASSET_NOT_FOUND", f"Unknown asset '{source}'.", 404)
    if target is not None and target not in graph.nodes:
        raise ApplicationError("ATTACK_GRAPH_ASSET_NOT_FOUND", f"Unknown asset '{target}'.", 404)

    found: list[list[InfrastructureEdge]] = []
    queue: deque[tuple[str, list[InfrastructureEdge], set[str]]] = deque([(source, [], {source})])
    while queue and len(found) < max_paths:
        node, path, visited = queue.popleft()
        if path and (target is None or node == target):
            if target is None:
                target_node = graph.nodes[node]
                is_candidate = target_node.criticality in {
                    "high",
                    "critical",
                } or target_node.sensitivity in {
                    "restricted",
                    "highly_restricted",
                }
                if is_candidate:
                    found.append(path)
            else:
                found.append(path)
                continue
        if len(path) >= max_depth:
            continue
        for edge in graph.adjacency.get(node, []):
            if edge.destination_asset_id in visited:
                continue
            queue.append(
                (edge.destination_asset_id, [*path, edge], visited | {edge.destination_asset_id})
            )
    return found[:max_paths]


def _allowed_edges(
    session: Session,
    path_type: AttackPathType,
    all_edges: list[InfrastructureEdge],
    run_id: str | None,
    model_id: str | None,
    through_sequence: int | None,
) -> tuple[list[InfrastructureEdge], list[str], str]:
    """Resolve the edge set + evidence-supporting asset ids for a path type.

    Reuses `topology_path_service.run_state`, the exact same sequence-bounded
    evidence computation the existing Digital Twin path/observed-state views
    already use — no parallel detection logic is introduced here.
    """

    permitted = [edge for edge in all_edges if edge.permitted]
    if path_type is AttackPathType.POTENTIAL:
        return permitted, [], "versioned synthetic architecture (static graph)"

    if not run_id:
        raise ApplicationError(
            "ATTACK_GRAPH_RUN_REQUIRED",
            "A simulation_run_id is required for observed/inferred/predicted attack paths.",
            422,
        )
    state = topology_path_service.run_state(session, run_id, model_id, through_sequence)
    by_id = {edge.edge_id: edge for edge in all_edges}

    if path_type is AttackPathType.OBSERVED:
        allowed = [by_id[eid] for eid in state.observed_edge_ids if eid in by_id]
        return (
            allowed,
            state.anomalous_observed_asset_ids,
            (f"telemetry actually observed through sequence {state.current_sequence_limit}"),
        )

    if path_type is AttackPathType.INFERRED:
        observed_ids = set(state.observed_edge_ids)
        anomalous = set(state.anomalous_observed_asset_ids)
        inferred_extra = [
            edge
            for edge in permitted
            if edge.source_asset_id in anomalous and edge.edge_id not in observed_ids
        ]
        allowed = [by_id[eid] for eid in observed_ids if eid in by_id] + inferred_extra
        return (
            allowed,
            state.anomalous_observed_asset_ids,
            (
                "observed evidence extended one hop via the static graph from "
                "assets already flagged anomalous-observed"
            ),
        )

    # PREDICTED
    observed_ids = set(state.observed_edge_ids)
    predicted_ids = set(state.predicted_edge_ids)
    allowed = [by_id[eid] for eid in observed_ids | predicted_ids if eid in by_id]
    return (
        allowed,
        state.anomalous_observed_asset_ids,
        ("observed evidence plus the existing next-stage prediction's predicted relationships"),
    )


def _score(
    path: list[InfrastructureEdge],
    graph: _Graph,
    path_type: AttackPathType,
    evidence_assets: set[str],
) -> AttackPathScore:
    """See docs/architecture/ATTACK_GRAPH.md "Attack Path Priority Score" for
    the full formula and rationale. Every factor here is a deterministic
    function of graph/evidence data already computed above - nothing is
    randomly generated."""

    source_node = graph.nodes[path[0].source_asset_id]
    target_node = graph.nodes[path[-1].destination_asset_id]

    exposure = (
        25.0
        if source_node.zone == "edge_zone" or source_node.asset_type == "external_client"
        else 0.0
    )
    privilege = min(20.0, sum(10.0 for edge in path if _is_privileged(edge)))
    critical_target = CRITICALITY_WEIGHT.get(target_node.criticality, 0.0) + SENSITIVITY_BONUS.get(
        target_node.sensitivity, 0.0
    )
    critical_target = min(30.0, critical_target)
    zones = [graph.nodes[path[0].source_asset_id].zone] + [
        graph.nodes[edge.destination_asset_id].zone for edge in path
    ]
    crossings = sum(1 for a, b in itertools.pairwise(zones) if a != b)
    boundary = min(20.0, crossings * 5.0)
    touched = {edge.source_asset_id for edge in path} | {edge.destination_asset_id for edge in path}
    evidence_hits = len(touched & evidence_assets)
    evidence = 5.0 if path_type is AttackPathType.PREDICTED else min(30.0, evidence_hits * 10.0)
    length_penalty = max(0.0, (len(path) - 3)) * 3.0
    total = max(
        0.0,
        min(100.0, exposure + privilege + critical_target + boundary + evidence - length_penalty),
    )
    return AttackPathScore(
        total=round(total, 2),
        exposure_contribution=exposure,
        privilege_contribution=privilege,
        critical_target_contribution=critical_target,
        boundary_crossing_contribution=boundary,
        evidence_contribution=evidence,
        length_penalty=length_penalty,
    )


def _explain_step(
    graph: _Graph, edge: InfrastructureEdge, semantics: str, sequence: int
) -> AttackPathStep:
    source = graph.nodes[edge.source_asset_id]
    destination = graph.nodes[edge.destination_asset_id]
    reason_by_semantics = {
        "uses_identity": "the destination is the identity service this workload authenticates with",
        "can_administer": "an elevated administrative relationship permits control of this asset",
        "writes_to": "the source has a declared write/backup relationship to this data asset",
        "reads_from": "the source has a declared read relationship to this asset",
        "routes_to": "the source routes requests to this destination",
        "network_reachable": "the destination is network-reachable from the source",
        "deployed_on": "the workload is deployed on this compute asset",
        "reports_to": "the source reports telemetry to this asset",
        "manages_backup_of": "the destination manages backups for the source",
    }
    reason = reason_by_semantics.get(
        semantics, "a permitted synthetic relationship connects these assets"
    )
    if source.zone == "edge_zone" and sequence == 1:
        reason = "internet-exposed entry point; " + reason
    return AttackPathStep(
        sequence=sequence,
        source_asset_id=edge.source_asset_id,
        destination_asset_id=edge.destination_asset_id,
        edge_id=edge.edge_id,
        relationship_type=edge.relationship_type,
        attack_semantics=semantics,
        reason=reason,
        trust_boundary_crossed=source.zone != destination.zone,
        source_zone=source.zone,
        destination_zone=destination.zone,
        privileged=_is_privileged(edge),
        synthetic=True,
    )


class AttackGraphService:
    def analyze(
        self,
        session: Session,
        source_asset_id: str,
        target_asset_id: str | None,
        path_type: AttackPathType,
        run_id: str | None,
        model_id: str | None,
        through_sequence: int | None,
        max_depth: int,
        max_paths: int,
        correlation_id: str | None = None,
    ) -> AttackPathAnalysisResult:
        include_sink = run_id is not None
        all_nodes = topology_service.nodes(include_sink)
        all_edges = topology_service.edges(include_sink)
        allowed_edges, evidence_list, evidence_source = _allowed_edges(
            session, path_type, all_edges, run_id, model_id, through_sequence
        )
        graph_full = _Graph.build(all_edges, all_nodes)
        graph_allowed = _Graph.build(allowed_edges, all_nodes)
        evidence_assets = set(evidence_list)

        candidates = _enumerate_paths(
            graph_allowed, source_asset_id, target_asset_id, max_depth, max_paths * 3
        )
        scored: list[AttackPath] = []
        for edge_path in candidates:
            target_id = edge_path[-1].destination_asset_id
            target_node = graph_full.nodes[target_id]
            steps = [
                _explain_step(
                    graph_full,
                    edge,
                    _attack_semantics(
                        graph_full.nodes[edge.source_asset_id],
                        graph_full.nodes[edge.destination_asset_id],
                        edge,
                    ),
                    index,
                )
                for index, edge in enumerate(edge_path, 1)
            ]
            score = _score(edge_path, graph_full, path_type, evidence_assets)
            ordered_ids = [edge_path[0].source_asset_id] + [
                edge.destination_asset_id for edge in edge_path
            ]
            boundaries = sorted(
                {
                    f"{s.source_zone}->{s.destination_zone}"
                    for s in steps
                    if s.trust_boundary_crossed
                }
            )
            statement = (
                f"{path_type.value} path: "
                + " -> ".join(ordered_ids)
                + f" ({len(edge_path)} hop{'s' if len(edge_path) != 1 else ''}), "
                f"evidence: {evidence_source}."
            )
            path_id = "-".join(ordered_ids) + f":{path_type.value}"
            scored.append(
                AttackPath(
                    path_id=path_id,
                    path_type=path_type,
                    source_asset_id=source_asset_id,
                    target_asset_id=target_id,
                    ordered_asset_ids=ordered_ids,
                    steps=steps,
                    hop_count=len(edge_path),
                    trust_boundaries_crossed=boundaries,
                    privilege_escalation=any(step.privileged for step in steps),
                    target_criticality=target_node.criticality,
                    target_sensitivity=target_node.sensitivity,
                    evidence_asset_ids=sorted(set(ordered_ids) & evidence_assets),
                    score=score,
                    statement=statement,
                    through_sequence_number=through_sequence,
                    synthetic=True,
                )
            )
        scored.sort(key=lambda item: (-item.score.total, item.hop_count, item.path_id))
        top_paths = scored[:max_paths]
        if top_paths:
            top = top_paths[0]
            get_event_bus().publish(
                DomainEvent(
                    event_type=EventType.ATTACK_PATH_DISCOVERED,
                    source="attack_graph",
                    run_id=run_id,
                    correlation_id=correlation_id,
                    resource_ids=top.ordered_asset_ids,
                    payload=AttackPathDiscoveredPayload(
                        path_id=top.path_id,
                        path_type=top.path_type.value,
                        source_asset_id=top.source_asset_id,
                        target_asset_id=top.target_asset_id,
                        hop_count=top.hop_count,
                        score=top.score.total,
                    ),
                )
            )
        return AttackPathAnalysisResult(
            source_asset_id=source_asset_id,
            target_asset_id=target_asset_id,
            path_type=path_type,
            simulation_run_id=run_id,
            model_id=model_id,
            through_sequence_number=through_sequence,
            max_depth=max_depth,
            max_paths=max_paths,
            paths=top_paths,
            total_candidates_considered=len(candidates),
            synthetic=True,
        )


attack_graph_service = AttackGraphService()
