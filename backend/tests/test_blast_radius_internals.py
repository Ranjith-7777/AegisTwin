"""Unit-level proofs for blast_radius_service's pure `_forward_reachable`
core: cycle safety and max-depth bounding, against small synthetic graphs
independent of the real topology."""

from app.schemas.topology import InfrastructureEdge
from app.services.blast_radius_service import _forward_reachable


def _edge(source: str, destination: str, permitted: bool = True) -> InfrastructureEdge:
    return InfrastructureEdge(
        edge_id=f"{source}--{destination}",
        source_asset_id=source,
        destination_asset_id=destination,
        relationship_type="expected_relationship",
        permitted=permitted,
        trust_level="standard",
    )


def _adjacency(edges: list[InfrastructureEdge]) -> dict[str, list[InfrastructureEdge]]:
    adjacency: dict[str, list[InfrastructureEdge]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source_asset_id, []).append(edge)
    return adjacency


def test_forward_reachable_is_cycle_safe_and_terminates() -> None:
    # a -> b -> c -> a (cycle) plus a -> d (real exit)
    edges = [_edge("a", "b"), _edge("b", "c"), _edge("c", "a"), _edge("a", "d")]
    reachable, _ = _forward_reachable(_adjacency(edges), {"a"}, max_depth=50)
    assert reachable == {"a", "b", "c", "d"}


def test_forward_reachable_respects_max_depth() -> None:
    edges = [_edge("a", "b"), _edge("b", "c"), _edge("c", "d")]
    shallow, _ = _forward_reachable(_adjacency(edges), {"a"}, max_depth=1)
    deep, _ = _forward_reachable(_adjacency(edges), {"a"}, max_depth=5)
    assert shallow == {"a", "b"}
    assert deep == {"a", "b", "c", "d"}


def test_forward_reachable_ignores_non_permitted_edges() -> None:
    edges = [_edge("a", "b", permitted=False), _edge("a", "c", permitted=True)]
    reachable, _ = _forward_reachable(_adjacency(edges), {"a"}, max_depth=5)
    assert reachable == {"a", "c"}


def test_forward_reachable_is_deterministic_across_calls() -> None:
    edges = [_edge("a", "b"), _edge("a", "c"), _edge("b", "d"), _edge("c", "d")]
    first, _ = _forward_reachable(_adjacency(edges), {"a"}, max_depth=5)
    second, _ = _forward_reachable(_adjacency(edges), {"a"}, max_depth=5)
    assert first == second == {"a", "b", "c", "d"}
