"""Phase 4 Workflow Coordinator output. The Coordinator is explicitly NOT an
8th agent - see docs/architecture/AGENT_ARCHITECTURE.md "Workflow
Coordinator". It only sequences calls to the real agents/services in the
same order a human operator would via the API.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.blue_planning import PlanComparisonResult
from app.schemas.orchestration import OrchestrationView


class WorkflowRunResult(BaseModel):
    comparison: PlanComparisonResult
    orchestration: OrchestrationView | None
    autonomy_mode: str
    auto_executed: bool
    auto_verified: bool
    stopped_reason: str
    synthetic: Literal[True] = True
