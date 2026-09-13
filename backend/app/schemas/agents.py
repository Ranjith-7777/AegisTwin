"""The Phase 4 agent registry.

AegisArena has exactly 7 functional agents: 1 Red-side (the Synthetic Red
Agent / Scenario Engine) and 6 Blue-side specialists (Response Planner,
Impact Simulation, Safety Governor, Approval Router, Synthetic Execution,
Verification - implemented in `app/services/orchestration_agents.py`).

Detection models (Isolation Forest), incident correlation, MITRE mapping,
the Attack Graph, and Blast Radius are analytical subsystems consumed BY
agents - they never independently decide anything, so they are never
counted as agents. See docs/architecture/AGENT_ARCHITECTURE.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

AgentSide = Literal["red", "blue"]


class AgentDescriptor(BaseModel):
    agent_id: str
    display_name: str
    side: AgentSide
    role: str
    description: str
    implementation_type: str
    version: str
    input_types: list[str]
    decision_type: str
    output_types: list[str]
    next_agent: str | None
    synthetic: Literal[True] = True


class AnalyticalSubsystemDescriptor(BaseModel):
    """Explicitly NOT an agent - never makes an independent decision, only
    produces evidence that an agent consumes."""

    subsystem_id: str
    display_name: str
    description: str
    consumed_by: list[str]
    synthetic: Literal[True] = True


class AgentRegistry(BaseModel):
    agents: list[AgentDescriptor]
    analytical_subsystems: list[AnalyticalSubsystemDescriptor]
    total_agents: int
    red_agent_count: int
    blue_agent_count: int
    synthetic: Literal[True] = True


class AgentTraceEntry(BaseModel):
    agent_id: str
    agent_name: str
    sequence: int
    timestamp: datetime
    input_summary: str
    decision_type: str
    decision: str
    rationale: str
    warnings: list[str]
    resource_ids: list[str]
    score: float | None
    next_agent: str | None
    status: str
    synthetic: Literal[True] = True


class AgentTrace(BaseModel):
    orchestration_id: str
    entries: list[AgentTraceEntry]
    stopped_reason: str | None
    synthetic: Literal[True] = True
