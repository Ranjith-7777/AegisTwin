"""Structured, security-oriented view of a Red scenario.

This is a *projection*, not a new authoring model or a second execution
path: every field here is derived from the existing `SimulationScenario` /
`ScenarioStep` catalogue (`app/services/scenario_service.py`) plus the
existing static MITRE mapping (`app/services/red_scenario_catalogue.py`).
See `app/services/red_scenario_catalogue.py::build_definition` for the
projection logic and `docs/security/MITRE_SCENARIO_MAPPING.md` for the
mapping rules it reuses.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class RedScenarioStepDefinition(BaseModel):
    step_id: str
    sequence: int
    name: str
    description: str
    action_type: str
    source_asset_id: str
    target_asset_id: str | None
    prerequisites: list[str]
    expected_technique_ids: list[str]
    expected_event_type: str
    success_condition: str
    synthetic: Literal[True] = True


class RedScenarioDefinition(BaseModel):
    scenario_id: str
    display_name: str
    objective: str
    description: str
    initial_access_point: str
    high_value_objective: str | None
    prerequisites: list[str]
    is_red_agent_scenario: bool
    steps: list[RedScenarioStepDefinition]
    synthetic: Literal[True] = True
