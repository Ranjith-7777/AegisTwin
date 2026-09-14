"""Unit tests for Mission Health `H(t)`, Mission Continuity Index (MCI), and
the operational-connectivity BFS - Phase 5 Stage 3.

These exercise the pure functions in `mission_continuity_service.py`
directly (constructed `MissionResource`/`MissionHealthPointRecord` inputs,
never a full end-to-end experiment), per the Stage 3 brief's requirement
that Mission Health be "easy to unit test independently".
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.database.models import MissionHealthPointRecord
from app.schemas.topology import InfrastructureEdge
from app.services.evaluation.mission_continuity_service import (
    MCI_VERSION,
    MissionContinuityService,
    MissionResource,
    mission_health,
    operationally_connected_asset_ids,
    resource_health,
)

service = MissionContinuityService()


def _point(
    sequence: int, time_: float, health: float, stage: str = "stage"
) -> MissionHealthPointRecord:
    return MissionHealthPointRecord(
        id=f"exp:{sequence}",
        experiment_id="exp",
        sequence=sequence,
        logical_time_sim=time_,
        mission_health=health,
        stage=stage,
        reason="test",
        synthetic=True,
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------
# Mission Health - resource_health / mission_health
# ---------------------------------------------------------------------


def test_exposed_critical_asset_lowers_health() -> None:
    resources = [MissionResource("critical-asset", "critical")]
    healthy = mission_health(
        resources, exposed_asset_ids=frozenset(), connected_asset_ids=frozenset({"critical-asset"})
    )
    exposed = mission_health(
        resources,
        exposed_asset_ids=frozenset({"critical-asset"}),
        connected_asset_ids=frozenset({"critical-asset"}),
    )
    assert healthy == 1.0
    assert exposed == 0.0


def test_isolated_bystander_critical_asset_lowers_health() -> None:
    """Not exposed to attack, but no longer operationally connected
    (cut off as bystander collateral) - still unhealthy."""

    resources = [MissionResource("critical-asset", "critical")]
    isolated = mission_health(
        resources, exposed_asset_ids=frozenset(), connected_asset_ids=frozenset()
    )
    assert isolated == 0.0
    assert resource_health("critical-asset", frozenset(), frozenset()) == 0.0


def test_healthy_connected_asset_contributes_positively() -> None:
    resources = [
        MissionResource("critical-asset", "critical"),
        MissionResource("low-asset", "low"),
    ]
    connected = frozenset({"critical-asset", "low-asset"})
    health = mission_health(resources, exposed_asset_ids=frozenset(), connected_asset_ids=connected)
    assert health == 1.0


def test_lower_criticality_resource_has_proportionally_less_influence() -> None:
    resources = [
        MissionResource("critical-asset", "critical"),
        MissionResource("low-asset", "low"),
    ]
    # low-asset unhealthy: weight 1 of total 5 lost -> health = 4/5 = 0.8
    low_unhealthy = mission_health(
        resources,
        exposed_asset_ids=frozenset({"low-asset"}),
        connected_asset_ids=frozenset({"critical-asset", "low-asset"}),
    )
    # critical-asset unhealthy: weight 4 of total 5 lost -> health = 1/5 = 0.2
    critical_unhealthy = mission_health(
        resources,
        exposed_asset_ids=frozenset({"critical-asset"}),
        connected_asset_ids=frozenset({"critical-asset", "low-asset"}),
    )
    assert low_unhealthy == 0.8
    assert critical_unhealthy == 0.2
    assert low_unhealthy > critical_unhealthy


def test_zero_mission_relevant_resources_handled_safely() -> None:
    # Not reachable via this codebase's fixed, non-empty topology, but the
    # aggregate function itself must not raise or divide by zero.
    assert mission_health([], exposed_asset_ids=frozenset(), connected_asset_ids=frozenset()) == 1.0


# ---------------------------------------------------------------------
# Operational connectivity BFS
# ---------------------------------------------------------------------


def _edge(source: str, destination: str) -> InfrastructureEdge:
    return InfrastructureEdge(
        edge_id=f"{source}--{destination}",
        source_asset_id=source,
        destination_asset_id=destination,
        relationship_type="expected_relationship",
        protocol_label="test",
        permitted=True,
        trust_level="service",
        synthetic=True,
    )


def test_operationally_connected_bfs_excludes_removed_edge_targets() -> None:
    edges = [_edge("entry", "a"), _edge("a", "b"), _edge("b", "c")]
    fully_connected = operationally_connected_asset_ids(edges, "entry", frozenset(), frozenset())
    assert fully_connected == frozenset({"entry", "a", "b", "c"})

    cut_at_a = operationally_connected_asset_ids(
        edges, "entry", frozenset(), frozenset({"entry--a"})
    )
    assert cut_at_a == frozenset({"entry"})


def test_operationally_connected_bfs_excludes_removed_node() -> None:
    edges = [_edge("entry", "a"), _edge("a", "b")]
    result = operationally_connected_asset_ids(edges, "entry", frozenset({"a"}), frozenset())
    assert result == frozenset({"entry"})


# ---------------------------------------------------------------------
# MCI
# ---------------------------------------------------------------------


def test_perfect_health_entire_experiment_gives_mci_1() -> None:
    points = [_point(0, 0.0, 1.0), _point(1, 100.0, 1.0)]
    assert service.compute_mci(points) == 1.0


def test_zero_health_entire_experiment_gives_mci_0() -> None:
    points = [_point(0, 0.0, 0.0), _point(1, 100.0, 0.0)]
    assert service.compute_mci(points) == 0.0


def test_partial_degradation_matches_hand_computed_trapezoidal_auc() -> None:
    """Points: (t=0, h=1.0) -> (t=10, h=1.0) -> (t=10, h=0.0) -> (t=30, h=0.0)
    -> (t=30, h=1.0) -> (t=40, h=1.0).

    Trapezoidal AUC = 10*(1.0+1.0)/2 + 0*(1.0+0.0)/2 + 20*(0.0+0.0)/2 +
    0*(0.0+1.0)/2 + 10*(1.0+1.0)/2 = 10 + 0 + 0 + 0 + 10 = 20.
    Duration = 40 - 0 = 40. MCI = 20/40 = 0.5.
    """

    points = [
        _point(0, 0.0, 1.0),
        _point(1, 10.0, 1.0),
        _point(2, 10.0, 0.0),
        _point(3, 30.0, 0.0),
        _point(4, 30.0, 1.0),
        _point(5, 40.0, 1.0),
    ]
    assert service.compute_mci(points) == 0.5


def test_faster_recovery_gives_higher_mci_than_slower_recovery() -> None:
    # Both dip to 0.0 at t=10 and recover to 1.0 by t=40, but the fast
    # curve recovers at t=15 while the slow curve recovers at t=35.
    fast = [
        _point(0, 0.0, 1.0),
        _point(1, 10.0, 0.0),
        _point(2, 15.0, 1.0),
        _point(3, 40.0, 1.0),
    ]
    slow = [
        _point(0, 0.0, 1.0),
        _point(1, 10.0, 0.0),
        _point(2, 35.0, 1.0),
        _point(3, 40.0, 1.0),
    ]
    fast_mci = service.compute_mci(fast)
    slow_mci = service.compute_mci(slow)
    assert fast_mci is not None
    assert slow_mci is not None
    assert fast_mci > slow_mci


def test_identical_final_state_different_mci_depending_on_path() -> None:
    # Both curves start and end healthy (t=0 and t=40, h=1.0), but one
    # stays healthy throughout while the other dips to 0.0 in the middle.
    steady = [_point(0, 0.0, 1.0), _point(1, 40.0, 1.0)]
    dipped = [_point(0, 0.0, 1.0), _point(1, 20.0, 0.0), _point(2, 40.0, 1.0)]
    steady_mci = service.compute_mci(steady)
    dipped_mci = service.compute_mci(dipped)
    assert steady_mci == 1.0
    assert dipped_mci is not None
    assert dipped_mci < steady_mci


def test_zero_duration_single_point_returns_none() -> None:
    assert service.compute_mci([_point(0, 5.0, 1.0)]) is None


def test_zero_duration_all_points_same_instant_returns_none() -> None:
    points = [_point(0, 5.0, 1.0), _point(1, 5.0, 0.5)]
    assert service.compute_mci(points) is None


def test_points_are_deterministically_ordered_before_integration() -> None:
    out_of_order = [_point(1, 40.0, 1.0), _point(0, 0.0, 1.0)]
    in_order = [_point(0, 0.0, 1.0), _point(1, 40.0, 1.0)]
    assert service.compute_mci(out_of_order) == service.compute_mci(in_order)


def test_mci_version_constant() -> None:
    assert MCI_VERSION == "aegis-mci-v1"
