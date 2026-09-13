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
    through_sequence_number: int | None
    statement: str
    synthetic: Literal[True] = True
