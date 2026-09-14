"""Phase 5 Stage 3: Mission Health `H(t)`, the event-driven resilience curve,
and the Mission Continuity Index (MCI) for one `ExperimentRecord`.

## What "healthy" means (read this before touching anything below)

For a given mission-relevant resource (every topology node - see "Which
resources count" below) at a given point in an experiment:

    A resource is healthy (health = 1.0) at time t if and only if it is
    BOTH (a) not currently exposed to confirmed/admissible attack reach -
    it is neither itself a compromised anchor nor forward-reachable from one
    via the same Attack Graph/Blast Radius evidence this codebase already
    uses for Blue's own what-if evaluations - AND (b) still operationally
    connected - reachable, via the topology's real edges (minus whatever a
    response action has actually removed at that point), from the
    topology's designated external entry point. A resource that fails
    either test is unhealthy (health = 0.0); there is no partial credit for
    a single resource. `MissionHealth(t)` is then the criticality-weighted
    fraction of mission-relevant resources that are healthy at t.

## Which resources count ("mission-relevant")

Every `topology_service.nodes(include_sink=False)` node, regardless of
criticality - per the Phase 5 Stage 3 brief, a `"low"`-criticality resource
still counts (just with less weight), so nothing is silently excluded.
Weights: `critical=4, high=3, medium=2, low=1` - the brief's own suggested
defaults; nothing in this codebase's existing criticality vocabulary
(`app/services/topology_service.py`'s four-value `criticality` field) maps
more cleanly onto a different weighting, so they are used unchanged.

## "Exposed to confirmed/admissible attack reach"

Reuses this codebase's ONE existing before/after evidence primitive
end-to-end - `what_if_evidence_service.anchor_asset_ids` (which anchors are
real, evidence-backed anomalous footholds vs. a non-evidence fallback) and
`blast_radius_service.estimate` (multi-source forward reachability with the
SAME `exclude_node_ids`/`exclude_edge_ids` what-if convention
`metrics_service.py`'s own security evidence computation already uses) -
never a second, parallel implementation of "what can the attacker reach
from here". A resource is "exposed" if it is one of the compromised anchors
themselves OR forward-reachable from them
(`BlastRadiusResult.directly_affected_asset_ids | .reachable_asset_ids`).
When there is no real evidence yet (`anchor_asset_ids` returns
`has_evidence=False`, e.g. before the first anomaly is scored), nothing is
considered exposed - a non-evidence fallback anchor must never be treated
as a real compromise, exactly as `metrics_service.py` already treats it.

## "Operationally connected/available"

`app/services/orchestration_service.py`'s `_bystander_isolated_assets` is a
private, bound method on the `OrchestrationService` singleton (leading
underscore, not part of its public surface, and this module has no other
reason to import that service) - reusing it directly here would mean either
an invasive refactor to make it a shared module-level helper, or a
cross-module private-attribute reach-around that the codebase's own
style avoids everywhere else. It is also a narrower check than what Mission
Health needs: it only asks "does this asset touched by a removal have *any*
edge left at all", not "is it still transitively reachable from the
system's real entry point". So this module writes its own equivalent -
`_operationally_connected_asset_ids` - a second, intentionally SIMPLE
reference to the same edge-arithmetic idea (plain BFS over
`topology_service.edges(...)`, minus whatever a response action excluded),
not a duplicated complex algorithm. The traversal root is
`ENTRY_ASSET_ID = "external-user-01"` - the topology's one node with no
incoming edge anywhere in `topology_service.EDGE_DEFINITIONS`, i.e. its
designated external ingress point; every other node is forward-reachable
from it in the unmodified topology, so anything NOT reachable after a
response action's removals was genuinely cut off by that action (real
bystander collateral, or the intended isolation target).

## Resilience curve

`compute_curve` persists one `MissionHealthPointRecord` per meaningful state
transition the experiment actually reached (never thousands of samples) -
see the stage list in `_build_points`. It is idempotent: re-running it for
the same `experiment_id` replaces the prior points outright.

## MCI

`MCI = trapezoidal_AUC(H over logical_time) / experiment_duration` (ideal
health is always 1.0, so no separate "ideal AUC" term is needed). `None`
when duration is 0 (a single point, or every point at the same instant) -
never a divide-by-zero, never defaulted to 0.0/1.0.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database.models import (
    AnomalyAssessmentRecord,
    ExperimentMetricRecord,
    ExperimentRecord,
    IncidentCandidateRecord,
    MissionHealthPointRecord,
    ResponseOrchestrationRecord,
)
from app.schemas.detection import Classification
from app.schemas.topology import InfrastructureEdge
from app.services.blast_radius_service import blast_radius_service
from app.services.telemetry_service import telemetry_service
from app.services.topology_service import topology_service
from app.services.what_if_evidence_service import WHAT_IF_MAX_DEPTH, anchor_asset_ids

MCI_VERSION = "aegis-mci-v1"

# See `metrics_service.hidden_event_ids_for_experiment`'s docstring/comment
# for why this reader is duplicated locally rather than imported: it avoids
# a circular import (`perturbation_service` imports from `metrics_service`).
_HIDDEN_EVENT_IDS_KEY = "hidden_event_ids"


def _hidden_event_ids_for_experiment(experiment: ExperimentRecord) -> frozenset[str]:
    raw = experiment.configuration_json.get(_HIDDEN_EVENT_IDS_KEY)
    if not isinstance(raw, list):
        return frozenset()
    return frozenset(str(event_id) for event_id in raw)


# The topology's one node with no incoming edge in `EDGE_DEFINITIONS` - its
# designated external entry point. See module docstring.
ENTRY_ASSET_ID = "external-user-01"

CRITICALITY_WEIGHTS: dict[str, float] = {"critical": 4.0, "high": 3.0, "medium": 2.0, "low": 1.0}


@dataclass(frozen=True)
class MissionResource:
    """A minimal, topology-schema-independent view of one mission-relevant
    resource - deliberately narrower than `InfrastructureNode` so the pure
    health functions below are trivially unit-testable without constructing
    a full topology schema object."""

    asset_id: str
    criticality: str


@dataclass(frozen=True)
class MissionContinuitySnapshot:
    """The narrow, strategy-neutral input `ResilienceScoreService` needs
    from Mission Continuity - a single snapshot value, never the full
    curve, never anything defence-mode-identifying. `applicable=False`
    only when the topology has zero critical/high-criticality resources
    (should not occur in this codebase's fixed topology, but handled)."""

    critical_mission_health: float | None
    applicable: bool


def resource_health(
    asset_id: str, exposed_asset_ids: frozenset[str], connected_asset_ids: frozenset[str]
) -> float:
    """1.0 iff NOT exposed to attack reach AND still operationally
    connected; 0.0 otherwise. See module docstring for the exact
    definition - no partial credit."""

    healthy = asset_id not in exposed_asset_ids and asset_id in connected_asset_ids
    return 1.0 if healthy else 0.0


def mission_health(
    resources: list[MissionResource],
    exposed_asset_ids: frozenset[str],
    connected_asset_ids: frozenset[str],
) -> float:
    """Criticality-weighted fraction of healthy resources. Vacuously 1.0
    for an empty resource list (per the Stage 3 brief's "handled safely"
    requirement for zero mission-relevant resources) - nothing exists to be
    unhealthy, so there is nothing at risk. Not currently reachable in this
    codebase, since the topology is fixed and non-empty, but guarded
    anyway."""

    total_weight = sum(CRITICALITY_WEIGHTS[r.criticality] for r in resources)
    if total_weight == 0:
        return 1.0
    healthy_weight = sum(
        CRITICALITY_WEIGHTS[r.criticality]
        for r in resources
        if resource_health(r.asset_id, exposed_asset_ids, connected_asset_ids) == 1.0
    )
    return healthy_weight / total_weight


def operationally_connected_asset_ids(
    edges: list[InfrastructureEdge],
    entry_asset_id: str,
    exclude_node_ids: frozenset[str],
    exclude_edge_ids: frozenset[str],
) -> frozenset[str]:
    """Plain forward BFS from `entry_asset_id` over the topology's real
    edges, minus any a response action removed for this point in time. See
    module docstring, "Operationally connected/available"."""

    if entry_asset_id in exclude_node_ids:
        return frozenset()
    adjacency: dict[str, list[str]] = {}
    for edge in edges:
        if edge.edge_id in exclude_edge_ids:
            continue
        if (
            edge.source_asset_id in exclude_node_ids
            or edge.destination_asset_id in exclude_node_ids
        ):
            continue
        adjacency.setdefault(edge.source_asset_id, []).append(edge.destination_asset_id)

    visited = {entry_asset_id}
    queue: deque[str] = deque([entry_asset_id])
    while queue:
        node = queue.popleft()
        for neighbour in adjacency.get(node, []):
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(neighbour)
    return frozenset(visited)


class MissionContinuityService:
    def compute_curve(self, session: Session, experiment_id: str) -> list[MissionHealthPointRecord]:
        """Idempotent: replaces any existing points for this experiment_id.
        Requires `EvaluationMetricsService.compute()` to have already run
        for this experiment (this module reads its persisted
        `logical_timeline_json`/`raw_metrics_json` rather than re-deriving
        the same reached/not-reached gating a second time)."""

        experiment = session.get(ExperimentRecord, experiment_id)
        if experiment is None:
            raise ValueError(f"Unknown experiment_id: {experiment_id}")
        metric_record = session.get(ExperimentMetricRecord, experiment_id)
        if metric_record is None:
            raise ValueError(
                f"No ExperimentMetricRecord for {experiment_id}; run "
                "EvaluationMetricsService.compute() first."
            )

        points = self._build_points(session, experiment, metric_record)

        session.execute(
            delete(MissionHealthPointRecord).where(
                MissionHealthPointRecord.experiment_id == experiment_id
            )
        )
        now = datetime.now(UTC)
        records = [
            MissionHealthPointRecord(
                id=self._point_id(experiment_id, sequence),
                experiment_id=experiment_id,
                sequence=sequence,
                logical_time_sim=point_time,
                mission_health=round(health, 6),
                stage=stage,
                reason=reason,
                synthetic=True,
                created_at=now,
            )
            for sequence, (stage, point_time, health, reason) in enumerate(points)
        ]
        session.add_all(records)
        session.commit()
        return records

    def compute_mci(self, points: list[MissionHealthPointRecord]) -> float | None:
        """Pure function: trapezoidal AUC of `mission_health` over
        `logical_time_sim`, divided by the total duration spanned by
        `points`. Deterministically sorts by time first (never assumes
        caller ordering). `None` when duration is 0 (fewer than two
        distinct instants) - never a divide-by-zero."""

        if len(points) < 2:
            return None
        ordered = sorted(points, key=lambda p: p.logical_time_sim)
        duration = ordered[-1].logical_time_sim - ordered[0].logical_time_sim
        if duration <= 0:
            return None
        auc = 0.0
        for left, right in pairwise(ordered):
            dt = right.logical_time_sim - left.logical_time_sim
            auc += (left.mission_health + right.mission_health) / 2.0 * dt
        return round(auc / duration, 6)

    def get_curve(self, session: Session, experiment_id: str) -> list[MissionHealthPointRecord]:
        statement = (
            select(MissionHealthPointRecord)
            .where(MissionHealthPointRecord.experiment_id == experiment_id)
            .order_by(MissionHealthPointRecord.sequence)
        )
        return list(session.scalars(statement))

    def final_critical_mission_health(
        self, session: Session, experiment: ExperimentRecord
    ) -> float | None:
        """`CriticalMissionHealth` for `ResilienceScoreService`'s M pillar -
        the SAME resource-health definition as `MissionHealth`, restricted
        to critical/high-criticality resources only, evaluated at the
        experiment's FINAL state (post-rollback if rollback happened,
        post-mutation if verified without rollback, pre-mutation if nothing
        ever executed). A snapshot, not a time-integral - MCI is computed
        separately and never substituted here. `None` only if the topology
        somehow has zero critical/high resources (does not occur in this
        codebase's fixed topology, but handled explicitly)."""

        resources = [
            MissionResource(node.asset_id, node.criticality)
            for node in topology_service.nodes(include_sink=False)
            if node.criticality in {"high", "critical"}
        ]
        if not resources:
            return None

        exclude_node_ids, exclude_edge_ids = self._final_exclude_sets(session, experiment)
        exposed = self._exposed_asset_ids(
            session,
            experiment.run_id,
            experiment.detection_model_id,
            self._final_sequence(session, experiment),
            exclude_node_ids,
            exclude_edge_ids,
        )
        connected = operationally_connected_asset_ids(
            topology_service.edges(include_sink=False),
            ENTRY_ASSET_ID,
            exclude_node_ids,
            exclude_edge_ids,
        )
        return mission_health(resources, exposed, connected)

    def snapshot(self, session: Session, experiment: ExperimentRecord) -> MissionContinuitySnapshot:
        value = self.final_critical_mission_health(session, experiment)
        return MissionContinuitySnapshot(
            critical_mission_health=value, applicable=value is not None
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _point_id(experiment_id: str, sequence: int) -> str:
        return f"{experiment_id}:{sequence}"

    def _build_points(
        self,
        session: Session,
        experiment: ExperimentRecord,
        metric_record: ExperimentMetricRecord,
    ) -> list[tuple[str, float, float, str]]:
        timeline = cast(dict[str, float | None], metric_record.logical_timeline_json)
        raw = metric_record.raw_metrics_json
        resources = [
            MissionResource(node.asset_id, node.criticality)
            for node in topology_service.nodes(include_sink=False)
        ]
        edges = topology_service.edges(include_sink=False)
        changed_nodes = frozenset(experiment.changed_node_ids_json)
        changed_edges = frozenset(experiment.changed_edge_ids_json)

        def health_at(
            sequence: int | None, exclude_node_ids: frozenset[str], exclude_edge_ids: frozenset[str]
        ) -> float:
            exposed = self._exposed_asset_ids(
                session,
                experiment.run_id,
                experiment.detection_model_id,
                sequence,
                exclude_node_ids,
                exclude_edge_ids,
            )
            connected = operationally_connected_asset_ids(
                edges, ENTRY_ASSET_ID, exclude_node_ids, exclude_edge_ids
            )
            return mission_health(resources, exposed, connected)

        candidates: list[tuple[str, float | None, float, str]] = [
            (
                "baseline",
                0.0,
                1.0,
                "Experiment start: no attack or response has occurred yet; every "
                "mission-relevant resource is healthy by construction.",
            )
        ]

        attack_start_time = timeline.get("attack_start_time_sim")
        if attack_start_time is not None:
            health = health_at(1, frozenset(), frozenset())
            candidates.append(
                (
                    "attack_observed",
                    attack_start_time,
                    health,
                    "Attack scenario begins."
                    if health >= 1.0
                    else "Attack Graph/Blast Radius already show exposure at the first event.",
                )
            )

        detection_time = timeline.get("first_detection_time_sim")
        if detection_time is not None:
            sequence = self._detection_sequence(session, experiment)
            health = health_at(sequence, frozenset(), frozenset())
            candidates.append(
                ("detection", detection_time, health, "First anomalous detection recorded.")
            )

        incident_time = timeline.get("incident_confirmed_time_sim")
        if incident_time is not None:
            sequence = self._incident_sequence(session, experiment)
            health = health_at(sequence, frozenset(), frozenset())
            candidates.append(
                ("incident_confirmed", incident_time, health, "Incident candidate confirmed.")
            )

        orchestration_sequence = self._orchestration_sequence(session, experiment)

        response_time = timeline.get("response_start_time_sim")
        if response_time is not None:
            health = health_at(orchestration_sequence, frozenset(), frozenset())
            candidates.append(
                (
                    "response_start",
                    response_time,
                    health,
                    "Blue response orchestration begins; mitigation not yet applied.",
                )
            )

        containment_time = timeline.get("containment_time_sim")
        if containment_time is not None:
            health = health_at(orchestration_sequence, changed_nodes, changed_edges)
            candidates.append(
                (
                    "containment",
                    containment_time,
                    health,
                    "Response action executed; affected connectivity removed.",
                )
            )

        verification_time = timeline.get("verification_time_sim")
        if verification_time is not None:
            health = health_at(orchestration_sequence, changed_nodes, changed_edges)
            candidates.append(
                ("verification", verification_time, health, "Response outcome verified.")
            )

        recovery_time = timeline.get("recovery_time_sim")
        if recovery_time is not None:
            rollback_success = raw.get("rollback_success") is True
            exclude_nodes = frozenset() if rollback_success else changed_nodes
            exclude_edges = frozenset() if rollback_success else changed_edges
            health = health_at(orchestration_sequence, exclude_nodes, exclude_edges)
            reason = (
                "Rollback completed; mutation undone."
                if rollback_success
                else "Verified recovery reached without needing rollback."
            )
            candidates.append(("recovery", recovery_time, health, reason))

        deduplicated: list[tuple[str, float, float, str]] = []
        for stage, point_time, health, reason in candidates:
            assert point_time is not None
            if deduplicated:
                _, last_time, last_health, _ = deduplicated[-1]
                if last_time == point_time and last_health == health:
                    continue
            deduplicated.append((stage, point_time, health, reason))
        return deduplicated

    def _final_exclude_sets(
        self, session: Session, experiment: ExperimentRecord
    ) -> tuple[frozenset[str], frozenset[str]]:
        metric_record = session.get(ExperimentMetricRecord, experiment.experiment_id)
        rollback_success = (
            metric_record is not None
            and metric_record.raw_metrics_json.get("rollback_success") is True
        )
        if rollback_success:
            return frozenset(), frozenset()
        return (
            frozenset(experiment.changed_node_ids_json),
            frozenset(experiment.changed_edge_ids_json),
        )

    def _final_sequence(self, session: Session, experiment: ExperimentRecord) -> int | None:
        if experiment.run_id is None:
            return None
        return len(telemetry_service.list_run_events(session, experiment.run_id))

    @staticmethod
    def _exposed_asset_ids(
        session: Session,
        run_id: str | None,
        model_id: str | None,
        through_sequence: int | None,
        exclude_node_ids: frozenset[str],
        exclude_edge_ids: frozenset[str],
    ) -> frozenset[str]:
        if run_id is None or model_id is None or through_sequence is None:
            return frozenset()
        anchors, has_evidence = anchor_asset_ids(session, run_id, model_id, through_sequence)
        if not has_evidence or not anchors:
            return frozenset()
        result = blast_radius_service.estimate(
            session,
            anchors,
            run_id,
            through_sequence,
            WHAT_IF_MAX_DEPTH,
            exclude_edge_ids=exclude_edge_ids,
            exclude_node_ids=exclude_node_ids,
            publish_event=False,
        )
        return frozenset(result.directly_affected_asset_ids) | frozenset(result.reachable_asset_ids)

    @staticmethod
    def _detection_sequence(session: Session, experiment: ExperimentRecord) -> int | None:
        if experiment.run_id is None or experiment.detection_model_id is None:
            return None
        # Perturbation (Section 38): mirrors
        # `metrics_service.EvaluationMetricsService._first_detection_time` -
        # skip any anomalous event this experiment was configured to hide,
        # so the sequence used for the "detection" Mission Health candidate
        # stays consistent with `first_detection_time_sim` (computed the
        # same way in `metrics_service.py`). Empty `hidden_ids` (the default
        # for every unperturbed experiment) reproduces the previous
        # `.limit(1)` behaviour exactly.
        hidden_ids = _hidden_event_ids_for_experiment(experiment)
        statement = (
            select(AnomalyAssessmentRecord.event_id, AnomalyAssessmentRecord.sequence_number)
            .where(
                AnomalyAssessmentRecord.simulation_run_id == experiment.run_id,
                AnomalyAssessmentRecord.model_id == experiment.detection_model_id,
                AnomalyAssessmentRecord.classification == Classification.ANOMALOUS.value,
            )
            .order_by(AnomalyAssessmentRecord.sequence_number)
        )
        for event_id, sequence_number in session.execute(statement):
            if event_id not in hidden_ids:
                return int(sequence_number)
        return None

    @staticmethod
    def _incident_sequence(session: Session, experiment: ExperimentRecord) -> int | None:
        if experiment.incident_candidate_id is None:
            return None
        incident = session.get(IncidentCandidateRecord, experiment.incident_candidate_id)
        return incident.first_sequence_number if incident is not None else None

    @staticmethod
    def _orchestration_sequence(session: Session, experiment: ExperimentRecord) -> int | None:
        if experiment.orchestration_id is None:
            return None
        orchestration = session.get(ResponseOrchestrationRecord, experiment.orchestration_id)
        return orchestration.through_sequence_number if orchestration is not None else None


mission_continuity_service = MissionContinuityService()
