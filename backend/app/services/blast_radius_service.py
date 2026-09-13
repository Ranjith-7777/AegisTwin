"""Estimated synthetic blast-radius engine.

Reuses the same canonical topology graph as `attack_graph_service` — see
docs/architecture/BLAST_RADIUS.md for the algorithm.
"""

from __future__ import annotations

from collections import deque

from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.events.envelope import BlastRadiusAssessedPayload, DomainEvent
from app.events.registry import get_event_bus
from app.events.types import EventType
from app.schemas.blast_radius import BlastRadiusResult, BlastRadiusScore
from app.schemas.topology import InfrastructureEdge
from app.services.topology_path_service import topology_path_service
from app.services.topology_service import topology_service

ZONE_WEIGHT = 5.0
CRITICAL_WEIGHT = 10.0
SENSITIVE_WEIGHT = 5.0
REACHABLE_WEIGHT = 2.0


def _forward_reachable(
    adjacency: dict[str, list[InfrastructureEdge]], sources: set[str], max_depth: int
) -> tuple[set[str], list[list[str]]]:
    """BFS forward over directed, permitted edges from every compromised asset.

    Cycle-safe by construction: a node is only enqueued once (via
    `visited`), so a cyclic graph still terminates in O(nodes + edges).
    """

    visited: set[str] = set(sources)
    queue: deque[tuple[str, int, list[str]]] = deque((s, 0, [s]) for s in sources)
    representative_paths: dict[str, list[str]] = {}
    while queue:
        node, depth, path = queue.popleft()
        if depth >= max_depth:
            continue
        for edge in adjacency.get(node, []):
            if not edge.permitted:
                continue
            nxt = edge.destination_asset_id
            if nxt in visited:
                continue
            visited.add(nxt)
            representative_paths[nxt] = [*path, nxt]
            queue.append((nxt, depth + 1, [*path, nxt]))
    return visited, list(representative_paths.values())


class BlastRadiusService:
    def estimate(
        self,
        session: Session,
        compromised_asset_ids: list[str],
        run_id: str | None,
        through_sequence: int | None,
        max_depth: int,
    ) -> BlastRadiusResult:
        include_sink = run_id is not None
        nodes = topology_service.nodes(include_sink)
        edges = topology_service.edges(include_sink)
        node_by_id = {node.asset_id: node for node in nodes}
        unknown = [a for a in compromised_asset_ids if a not in node_by_id]
        if unknown:
            raise ApplicationError(
                "BLAST_RADIUS_ASSET_NOT_FOUND", f"Unknown asset(s): {', '.join(unknown)}.", 404
            )

        # Sequence-bounded evidence, when a run is given, is used only to
        # confirm the requested assets are consistent with what has actually
        # been observed - it does not change the graph traversal itself,
        # which always uses the full permitted static graph (a conservative,
        # worst-case reachability estimate, not a claim of what has already
        # happened).
        if run_id is not None:
            topology_path_service.run_state(session, run_id, None, through_sequence)

        forward_adjacency: dict[str, list[InfrastructureEdge]] = {}
        reverse_adjacency: dict[str, list[InfrastructureEdge]] = {}
        for edge in edges:
            forward_adjacency.setdefault(edge.source_asset_id, []).append(edge)
            reverse_adjacency.setdefault(edge.destination_asset_id, []).append(edge)

        compromised = set(compromised_asset_ids)
        reachable_all, representative_paths = _forward_reachable(
            forward_adjacency, compromised, max_depth
        )
        reachable = sorted(reachable_all - compromised)

        # Dependent services: assets with a permitted edge *into* the
        # affected/reachable set that are not themselves already in it -
        # i.e. things that call/depend on what's compromised or reachable
        # and would be operationally impacted, even though they are not
        # themselves attacker-reachable.
        affected_or_reachable = compromised | set(reachable)
        dependents: set[str] = set()
        for asset_id in affected_or_reachable:
            for edge in reverse_adjacency.get(asset_id, []):
                if edge.permitted and edge.source_asset_id not in affected_or_reachable:
                    dependents.add(edge.source_asset_id)
        dependent_ids = sorted(dependents)

        all_involved = affected_or_reachable | dependents
        critical = sorted(
            a for a in all_involved if node_by_id[a].criticality in {"high", "critical"}
        )
        zones = sorted({node_by_id[a].zone for a in all_involved})

        critical_count = len(critical)
        sensitive_count = sum(
            1
            for a in all_involved
            if node_by_id[a].sensitivity in {"restricted", "highly_restricted"}
        )
        score_total = min(
            100.0,
            len(reachable) * REACHABLE_WEIGHT
            + critical_count * CRITICAL_WEIGHT
            + sensitive_count * SENSITIVE_WEIGHT
            + len(zones) * ZONE_WEIGHT,
        )
        score = BlastRadiusScore(
            total=round(score_total, 2),
            reachable_contribution=len(reachable) * REACHABLE_WEIGHT,
            critical_asset_contribution=critical_count * CRITICAL_WEIGHT,
            sensitive_asset_contribution=sensitive_count * SENSITIVE_WEIGHT,
            zone_crossing_contribution=len(zones) * ZONE_WEIGHT,
        )
        statement = (
            f"From {len(compromised)} compromised synthetic asset(s), "
            f"{len(reachable)} additional asset(s) are reachable and "
            f"{len(dependent_ids)} dependent service(s) would be operationally affected; "
            f"{critical_count} critical asset(s) are at risk across {len(zones)} trust zone(s)."
        )
        get_event_bus().publish(
            DomainEvent(
                event_type=EventType.BLAST_RADIUS_ASSESSED,
                source="blast_radius",
                run_id=run_id,
                resource_ids=sorted(all_involved),
                payload=BlastRadiusAssessedPayload(
                    compromised_asset_ids=sorted(compromised),
                    reachable_count=len(reachable),
                    critical_count=critical_count,
                    score=score.total,
                ),
            )
        )
        return BlastRadiusResult(
            compromised_asset_ids=sorted(compromised),
            directly_affected_asset_ids=sorted(compromised),
            reachable_asset_ids=reachable,
            dependent_asset_ids=dependent_ids,
            critical_assets_at_risk=critical,
            trust_zones_reached=zones,
            representative_paths=sorted(representative_paths, key=lambda p: (len(p), p)),
            reachable_count=len(reachable),
            dependent_count=len(dependent_ids),
            critical_count=critical_count,
            score=score,
            through_sequence_number=through_sequence,
            statement=statement,
            synthetic=True,
        )


blast_radius_service = BlastRadiusService()
