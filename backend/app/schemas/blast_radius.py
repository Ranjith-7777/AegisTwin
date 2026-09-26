"""Estimated synthetic blast-radius schemas.

See docs/architecture/BLAST_RADIUS.md for the algorithm. This is explicitly
an *estimate over the synthetic graph*, never a production blast-radius
claim.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


class BlastRadiusQuery(BaseModel):
    compromised_asset_ids: Annotated[list[str], Field(min_length=1, max_length=10)]
    simulation_run_id: str | None = None
    through_sequence_number: int | None = None
    max_depth: Annotated[int, Field(ge=1, le=10)] = 6


class BlastRadiusScore(BaseModel):
    """See docs/architecture/BLAST_RADIUS.md "Estimated Synthetic Blast-Radius Score"."""

    total: float
    reachable_contribution: float
    critical_asset_contribution: float
    sensitive_asset_contribution: float
    zone_crossing_contribution: float


class BlastRadiusResult(BaseModel):
    """`mode` distinguishes the two supported analyses:

    * `hypothetical` — no `simulation_run_id` was supplied; a static,
      worst-case what-if estimate over the full permitted graph, not a
      claim that any of `compromised_asset_ids` has actually happened.
    * `evidence_bound` — a `simulation_run_id` was supplied; every id in
      `compromised_asset_ids` was verified to be supported by real
      telemetry evidence (observed or anomalous-observed) through
      `through_sequence_number` before the traversal ran. See
      docs/architecture/BLAST_RADIUS.md "Run/sequence semantics".
    """

    compromised_asset_ids: list[str]
    directly_affected_asset_ids: list[str]
    reachable_asset_ids: list[str]
    dependent_asset_ids: list[str]
    critical_assets_at_risk: list[str]
    trust_zones_reached: list[str]
    representative_paths: list[list[str]]
    reachable_count: int
    dependent_count: int
    critical_count: int
    score: BlastRadiusScore
    mode: Literal["hypothetical", "evidence_bound"]
    through_sequence_number: int | None
    statement: str
    synthetic: Literal[True] = True
