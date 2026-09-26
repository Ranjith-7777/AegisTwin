"""Phase 4 human-in-the-loop autonomy modes.

See docs/architecture/AUTONOMY_MODEL.md. AUTONOMOUS never means "execute
everything" - `policy_service.evaluate_response_policies` still gates
every automatic execution.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class AutonomyMode(StrEnum):
    OBSERVE = "observe"
    RECOMMEND = "recommend"
    APPROVAL_REQUIRED = "approval_required"
    AUTONOMOUS = "autonomous"


AUTONOMY_DESCRIPTIONS: dict[AutonomyMode, str] = {
    AutonomyMode.OBSERVE: "Monitor only - detection/evidence only, no response plan is generated.",
    AutonomyMode.RECOMMEND: "Generate and rank candidate plans but never execute automatically.",
    AutonomyMode.APPROVAL_REQUIRED: "Generate and validate a plan; execution requires the "
    "appropriate synthetic analyst/administrator approval.",
    AutonomyMode.AUTONOMOUS: "Eligible low-impact, reversible, policy-passing actions may "
    "execute automatically; everything else still requires approval.",
}


class AutonomyConfig(BaseModel):
    mode: AutonomyMode
    description: str
    updated_by: str
    updated_at: datetime
    synthetic: Literal[True] = True


class AutonomyConfigUpdate(BaseModel):
    mode: AutonomyMode
    updated_by: str = Field(min_length=1, max_length=120)
    confirm: bool = Field(
        description="Must be explicitly true to raise the mode to 'autonomous' - "
        "this is a deliberate, non-hidden safety confirmation, not a dramatic warning."
    )
