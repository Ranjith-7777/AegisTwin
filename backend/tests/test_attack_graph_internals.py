"""Unit-level proofs for attack_graph_service's pure algorithmic core:
cycle safety, max-depth/max-results bounding, and score-decomposition
arithmetic. These exercise the private `_Graph`/`_enumerate_paths`/`_score`
functions directly against small synthetic graphs, independent of the
real 13-asset topology, so the guarantees are provable regardless of
whether the real topology happens to contain a cycle."""

from app.schemas.attack_graph import AttackPathType
from app.schemas.topology import InfrastructureEdge, InfrastructureNode
from app.services.attack_graph_service import _enumerate_paths, _Graph, _score


def _node(
    asset_id: str, criticality: str = "low", sensitivity: str = "standard", zone: str = "z"
) -> InfrastructureNode:
    return InfrastructureNode(
        asset_id=asset_id,
        display_name=asset_id,
        asset_type="service",
        zone=zone,
        sensitivity=sensitivity,
        criticality=criticality,
        description="test",
    )


def _edge(source: str, destination: str, trust_level: str = "standard") -> InfrastructureEdge:
    return InfrastructureEdge(
        edge_id=f"{source}--{destination}",
        source_asset_id=source,
        destination_asset_id=destination,
        relationship_type="expected_relationship",
        permitted=True,
        trust_level=trust_level,
    )


def test_enumerate_paths_is_cycle_safe_and_terminates() -> None:
    # a -> b -> c -> a (a genuine cycle) plus a -> d (a real exit)
    nodes = [_node("a"), _node("b"), _node("c"), _node("d", criticality="critical")]
    edges = [_edge("a", "b"), _edge("b", "c"), _edge("c", "a"), _edge("a", "d")]
    graph = _Graph.build(edges, nodes)

    paths = _enumerate_paths(graph, "a", None, max_depth=10, max_paths=10)

    assert paths, "expected at least one path to the critical asset 'd'"
    for path in paths:
        node_ids = [path[0].source_asset_id] + [edge.destination_asset_id for edge in path]
        assert len(node_ids) == len(set(node_ids)), "a path must never revisit a node"


def test_enumerate_paths_respects_max_depth() -> None:
    nodes = [_node("a"), _node("b"), _node("c", criticality="critical")]
    edges = [_edge("a", "b"), _edge("b", "c")]
    graph = _Graph.build(edges, nodes)

    shallow = _enumerate_paths(graph, "a", "c", max_depth=1, max_paths=10)
    deep = _enumerate_paths(graph, "a", "c", max_depth=5, max_paths=10)

    assert shallow == []
    assert len(deep) == 1
    assert deep[0][-1].destination_asset_id == "c"


def test_enumerate_paths_respects_max_paths() -> None:
    nodes = [_node("a"), _node("t", criticality="critical")]
    edges = [_edge("a", "t"), _edge("a", "t2"), _edge("a", "t3")]
    nodes += [_node("t2", criticality="critical"), _node("t3", criticality="critical")]
    graph = _Graph.build(edges, nodes)

    limited = _enumerate_paths(graph, "a", None, max_depth=5, max_paths=1)
    assert len(limited) == 1


def test_enumerate_paths_excludes_impossible_targets() -> None:
    nodes = [_node("a"), _node("b")]
    edges = [_edge("a", "b")]
    graph = _Graph.build(edges, nodes)

    # 'b' is neither critical nor sensitive and no explicit target was
    # requested, so it must not be treated as a valid destination.
    paths = _enumerate_paths(graph, "a", None, max_depth=5, max_paths=10)
    assert paths == []

    # An explicit, disconnected target must also yield no paths (no
    # exception - an empty result is the correct "impossible path" answer).
    isolated = _node("isolated")
    graph_with_isolated = _Graph.build(edges, [*nodes, isolated])
    unreachable = _enumerate_paths(graph_with_isolated, "a", "isolated", max_depth=5, max_paths=10)
    assert unreachable == []


def test_score_decomposition_sums_to_total_and_is_bounded() -> None:
    nodes = [
        _node("edge-src", zone="edge_zone"),
        _node("mid", zone="mid_zone"),
        _node("target", criticality="critical", sensitivity="highly_restricted", zone="data_zone"),
    ]
    edges = [_edge("edge-src", "mid", trust_level="elevated"), _edge("mid", "target")]
    graph = _Graph.build(edges, nodes)

    score = _score(edges, graph, AttackPathType.POTENTIAL, evidence_assets=set())

    computed_total = (
        score.exposure_contribution
        + score.privilege_contribution
        + score.critical_target_contribution
        + score.boundary_crossing_contribution
        + score.evidence_contribution
        - score.length_penalty
    )
    assert score.total == round(max(0.0, min(100.0, computed_total)), 2)
    assert 0.0 <= score.total <= 100.0
    # source is edge_zone -> exposure applies
    assert score.exposure_contribution == 25.0
    # one elevated-trust edge -> privilege contribution
    assert score.privilege_contribution == 10.0
    # target is critical + highly_restricted -> capped critical-target contribution
    assert score.critical_target_contribution == 30.0


def test_privileged_edges_increase_privilege_contribution_up_to_cap() -> None:
    nodes = [_node("a"), _node("b"), _node("c"), _node("d", criticality="critical")]
    edges_one_elevated = [_edge("a", "b", "elevated"), _edge("b", "c"), _edge("c", "d")]
    edges_two_elevated = [_edge("a", "b", "elevated"), _edge("b", "c", "elevated"), _edge("c", "d")]
    graph = _Graph.build(edges_one_elevated, nodes)

    one = _score(edges_one_elevated, graph, AttackPathType.POTENTIAL, evidence_assets=set())
    two = _score(edges_two_elevated, graph, AttackPathType.POTENTIAL, evidence_assets=set())
    three_elevated = [
        _edge("a", "b", "elevated"),
        _edge("b", "c", "elevated"),
        _edge("c", "d", "elevated"),
    ]
    three = _score(three_elevated, graph, AttackPathType.POTENTIAL, evidence_assets=set())

    assert one.privilege_contribution == 10.0
    assert two.privilege_contribution == 20.0
    assert three.privilege_contribution == 20.0  # capped at 20


def test_trust_boundary_crossings_are_reported() -> None:
    nodes = [
        _node("a", zone="zone-a"),
        _node("b", zone="zone-b"),
        _node("c", criticality="high", zone="zone-c"),
    ]
    edges = [_edge("a", "b"), _edge("b", "c")]
    graph = _Graph.build(edges, nodes)

    score = _score(edges, graph, AttackPathType.POTENTIAL, evidence_assets=set())
    # two hops, two zone changes (zone-a->zone-b, zone-b->zone-c) -> 2 * 5.0
    assert score.boundary_crossing_contribution == 10.0
