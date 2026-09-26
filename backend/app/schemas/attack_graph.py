"""Attack graph / attack-path schemas.

The attack graph is computed on demand from the existing synthetic topology
(`app.services.topology_service`) plus the existing sequence-bounded run
evidence (`app.services.topology_path_service.run_state`) — it introduces no
second, competing graph model and no new detection logic. See
docs/architecture/ATTACK_GRAPH.md for the full algorithm and scoring
rationale.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class AttackPathType(StrEnum):
    """How a path's traversability is justified — never blur these.

    POTENTIAL: derived purely from the static/synthetic cloud graph
    (permitted relationships), independent of any run.
    OBSERVED: every edge was actually observed (per
    ``RunTopologyState.observed_edge_ids``) up to the requested sequence.
    INFERRED: extends observed evidence one hop further using the static
    graph, starting only from assets already flagged anomalous-observed —
    "what could plausibly follow from what we've already seen", not a claim
    that it happened.
    PREDICTED: uses the existing next-stage prediction's predicted edges;
    explicitly hypothetical, never presented as established compromise.
    """

    POTENTIAL = "potential"
    OBSERVED = "observed"
    INFERRED = "inferred"
    PREDICTED = "predicted"


class AttackPathStep(BaseModel):
    sequence: int
    source_asset_id: str
    destination_asset_id: str
    edge_id: str
    relationship_type: str
    attack_semantics: str
    reason: str
    trust_boundary_crossed: bool
    source_zone: str
    destination_zone: str
    privileged: bool
    synthetic: Literal[True] = True


class AttackPathScore(BaseModel):
    """See docs/architecture/ATTACK_GRAPH.md "Attack Path Priority Score"."""

    total: float
    exposure_contribution: float
    privilege_contribution: float
    critical_target_contribution: float
    boundary_crossing_contribution: float
    evidence_contribution: float
    length_penalty: float


class AttackPath(BaseModel):
    path_id: str
    path_type: AttackPathType
    source_asset_id: str
    target_asset_id: str
    ordered_asset_ids: list[str]
    steps: list[AttackPathStep]
    hop_count: int
    trust_boundaries_crossed: list[str]
    privilege_escalation: bool
    target_criticality: str
    target_sensitivity: str
    evidence_asset_ids: list[str]
    score: AttackPathScore
    statement: str
    through_sequence_number: int | None
    synthetic: Literal[True] = True


class AttackPathAnalysisResult(BaseModel):
    source_asset_id: str
    target_asset_id: str | None
    path_type: AttackPathType
    simulation_run_id: str | None
    model_id: str | None
    through_sequence_number: int | None
    max_depth: int
    max_paths: int
    paths: list[AttackPath]
    total_candidates_considered: int
    synthetic: Literal[True] = True


class AttackPathQuery(BaseModel):
    source_asset_id: str
    target_asset_id: str | None = None
    path_type: AttackPathType = AttackPathType.POTENTIAL
    simulation_run_id: str | None = None
    model_id: str | None = None
    through_sequence_number: int | None = None
    max_depth: Annotated[int, Field(ge=1, le=10)] = 6
    max_paths: Annotated[int, Field(ge=1, le=10)] = 5
