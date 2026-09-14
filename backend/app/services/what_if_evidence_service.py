"""Shared what-if evidence computation, reused by both pre-execution candidate
comparison (`blue_planning_service.py`) and post-execution verification
(`orchestration_service.verify()`). There is exactly one implementation of
"recompute Attack Graph / Blast Radius against a hypothetical edge/node
exclusion" in this codebase - this module - so the two call sites can never
drift apart on methodology. Neither call site mutates persisted state; both
pass `publish_event=False` so hypothetical evaluations never pollute the
real domain-event stream. See docs/architecture/BLUE_RESPONSE_PLANNING.md
and docs/architecture/VERIFICATION_AND_ROLLBACK.md.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.attack_graph import AttackPathType
from app.schemas.blue_planning import SecurityGainEvidence
from app.services.attack_graph_service import attack_graph_service
from app.services.blast_radius_service import blast_radius_service
from app.services.topology_path_service import topology_path_service
from app.services.topology_service import topology_service

WHAT_IF_MAX_DEPTH = 6
WHAT_IF_MAX_PATHS = 3

ZERO_EVIDENCE = SecurityGainEvidence(
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


def security_improved(evidence: SecurityGainEvidence) -> bool:
    """Pure, stateless "did a genuine measured security improvement occur"
    check over one before/after `SecurityGainEvidence` pair: true if ANY of
    Attack Graph reachable paths, Blast Radius reachable assets, or critical
    targets reachable dropped from before to after. This is exactly the
    "IMPROVED" half of `orchestration_agents.VerificationAgent.verify()`'s
    containment check (see docs/architecture/VERIFICATION_AND_ROLLBACK.md,
    "IMPROVED vs VERIFIED AGAINST EXPECTED OBJECTIVE"), extracted here so it
    is exactly one implementation, reused both by that agent (Phase 4's
    post-execution verification step) and by
    `app.services.evaluation.metrics_service` (Phase 5's mode-agnostic
    `containment_success` measurement, which has no expected/actual pair to
    compare against - only a single real before/after evidence
    recomputation - so it uses this half alone)."""

    return (
        evidence.attack_paths_after < evidence.attack_paths_before
        or evidence.blast_radius_reachable_after < evidence.blast_radius_reachable_before
        or evidence.critical_targets_reachable_after < evidence.critical_targets_reachable_before
    )


def anchor_asset_ids(
    session: Session, run_id: str, model_id: str, through_sequence: int
) -> tuple[list[str], bool]:
    """A stable set of assets to root a before/after comparison at, plus
    whether that set is real evidence (safe to pass to evidence-bound
    Blast Radius) or a fallback.

    Real anomalous-observed evidence when it exists (a genuine attacker
    foothold); otherwise the first synthetic topology asset, purely so the
    comparison has a valid, deterministic starting point. The fallback
    asset is NOT real evidence, so it must never be passed to Blast Radius
    in evidence-bound mode (it would be correctly rejected as unsupported).

    `security_gain_evidence` roots its OBSERVED-path traversal at
    `anchors[0]` and only walks OBSERVED edges *forward* from there, so the
    anchor must be an asset with at least one OUTGOING observed edge - an
    anomalous asset the attacker was only ever observed arriving *at* can
    never produce a forward path and would silently make every candidate
    look equally (falsely) ineffective. Anomalous assets with an outgoing
    observed edge are ordered first (deterministically), so `anchors[0]`
    is always a genuine forward pivot when one exists.
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


def security_gain_evidence(
    session: Session,
    run_id: str,
    model_id: str,
    through_sequence: int,
    anchors: list[str],
    has_evidence: bool,
    exclude_node_ids: frozenset[str],
    exclude_edge_ids: frozenset[str],
    traversal_source: str | None = None,
) -> SecurityGainEvidence:
    """Recomputes real Attack Graph / Blast Radius before/after evidence for
    a hypothetical topology exclusion. `exclude_edge_ids`/`exclude_node_ids`
    represent "this connectivity no longer exists" for this call only -
    nothing is persisted or mutated. Returns `ZERO_EVIDENCE` semantics are
    the caller's responsibility when `anchors` is empty.

    The Attack Graph traversal is rooted at `traversal_source` when given
    (falling back to `anchors[0]`) - Blast Radius always uses the full
    `anchors` list as its multi-source reachability set regardless, since it
    is not directional the way a single attack-path traversal is. A single
    global anchor cannot fairly evaluate every candidate: a candidate that
    removes an edge upstream of `anchors[0]` (e.g. the attacker's own
    ingress edge, behind an already-anomalous internal pivot) would show a
    false zero effect if forced through `anchors[0]` alone, so callers with
    an edge-restriction candidate should pass that edge's own source asset
    as `traversal_source` and keep whichever evaluation shows the real,
    defensible effect - see `blue_planning_service.compare()`."""

    # OBSERVED (bounded to this run's real telemetry through `through_sequence`)
    # rather than POTENTIAL (the full static graph): a candidate/execution is
    # being judged against what THIS incident's evidence actually shows
    # happened, and a redundant static topology can otherwise hide a single
    # removed edge's real effect on the specific path this incident's
    # evidence followed. Falls back to POTENTIAL only when there is no real
    # evidence yet to bound to.
    source = traversal_source or anchors[0]
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


def best_security_gain_evidence(
    session: Session,
    run_id: str,
    model_id: str,
    through_sequence: int,
    anchors: list[str],
    has_evidence: bool,
    exclude_node_ids: frozenset[str],
    exclude_edge_ids: frozenset[str],
    edge_source_asset_id: str | None,
) -> SecurityGainEvidence:
    """Evaluates from `anchors[0]` (the default heuristic pivot) and, when an
    edge-restriction candidate's own edge starts at a *different* known
    anomalous asset, also evaluates rooted there - keeping whichever
    genuinely shows the larger, real security gain. A single global anchor
    cannot fairly judge every candidate: a candidate that removes an edge
    upstream of `anchors[0]` (e.g. the attacker's own ingress edge, behind
    an already-anomalous internal pivot) would otherwise show a false zero
    effect. Bounded to at most 2 traversals per candidate, never all
    anchors, to keep recomputation cost small."""

    if not anchors:
        return ZERO_EVIDENCE
    default_evidence = security_gain_evidence(
        session,
        run_id,
        model_id,
        through_sequence,
        anchors,
        has_evidence,
        exclude_node_ids,
        exclude_edge_ids,
    )
    if (
        edge_source_asset_id is None
        or edge_source_asset_id == anchors[0]
        or edge_source_asset_id not in anchors
    ):
        return default_evidence
    alternate_evidence = security_gain_evidence(
        session,
        run_id,
        model_id,
        through_sequence,
        anchors,
        has_evidence,
        exclude_node_ids,
        exclude_edge_ids,
        traversal_source=edge_source_asset_id,
    )
    return (
        alternate_evidence
        if alternate_evidence.security_gain > default_evidence.security_gain
        else default_evidence
    )
