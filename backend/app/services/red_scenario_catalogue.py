"""Structured, MITRE-validated view of the existing scripted Red scenarios.

This module does NOT change scenario behavior, generate telemetry, or add a
second MITRE-mapping engine. It mirrors the exact same, already-approved
condition logic `correlation_service.CorrelationService._map` uses at
runtime (see that method) so that every scenario step's *expected* technique
is derivable statically, before any telemetry is generated, and is
guaranteed to agree with what correlation will actually observe at runtime.
See docs/security/MITRE_SCENARIO_MAPPING.md for the full mapping table and
docs/architecture/adr/ADR-004-attack-graph-model.md for why this mirrors
rather than reuses the runtime function directly (the runtime function
needs generated `TelemetryEvent`/`user_id` state; this needs only the
static `ScenarioStep` definitions).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.red_scenario import RedScenarioDefinition, RedScenarioStepDefinition
from app.schemas.simulation import ScenarioStep, SimulationScenario
from app.services.mitre_catalogue_service import CATALOGUE
from app.services.scenario_service import RED_AGENT_SCENARIO_IDS, SCENARIOS
from app.services.topology_service import topology_service

VALID_TECHNIQUE_IDS = frozenset(item[0] for item in CATALOGUE)
TECHNIQUE_NAME = {item[0]: item[1] for item in CATALOGUE}
TECHNIQUE_TACTIC = {item[0]: item[2][0] for item in CATALOGUE}


@dataclass(frozen=True)
class StepTechnique:
    step_sequence: int
    technique_id: str | None
    technique_name: str | None
    tactic: str | None
    rationale: str


@dataclass(frozen=True)
class ScenarioMitreSummary:
    scenario_id: str
    name: str
    is_red_agent_scenario: bool
    step_techniques: list[StepTechnique]
    technique_ids: list[str]


def expected_technique_for_step(step: ScenarioStep, failed_users: set[str]) -> StepTechnique:
    """Mirrors `CorrelationService._map`'s condition chain exactly (first match wins).

    `failed_users` must be threaded across steps by the caller in scenario
    order, exactly as `correlation_service._map` accumulates it across events
    - see `iter_scenario_techniques` below.
    """

    metadata = step.metadata
    raw_failed_attempts = metadata.get("failed_attempts", 0) if isinstance(metadata, dict) else 0
    failed_attempts = raw_failed_attempts if isinstance(raw_failed_attempts, int) else 0

    if failed_attempts >= 5 or metadata.get("attempt_pattern") == "repeated":
        if step.user_id:
            failed_users.add(step.user_id)
        return StepTechnique(
            step.sequence,
            "T1110.001",
            TECHNIQUE_NAME["T1110.001"],
            TECHNIQUE_TACTIC["T1110.001"],
            "At least five repeated synthetic authentication failures (or an explicit "
            "repeated-attempt pattern) are declared for this step.",
        )
    if (
        step.outcome.value == "success"
        and step.user_id in failed_users
        and step.event_type.value == "authentication"
    ):
        return StepTechnique(
            step.sequence,
            "T1078",
            TECHNIQUE_NAME["T1078"],
            TECHNIQUE_TACTIC["T1078"],
            "A successful synthetic login follows repeated failures for the same user "
            "earlier in this scenario.",
        )
    if metadata.get("account_manipulation") is True:
        return StepTechnique(
            step.sequence,
            "T1098",
            TECHNIQUE_NAME["T1098"],
            TECHNIQUE_TACTIC["T1098"],
            "The step explicitly declares synthetic account permission manipulation.",
        )
    if isinstance(metadata.get("remote_service"), str):
        return StepTechnique(
            step.sequence,
            "T1021",
            TECHNIQUE_NAME["T1021"],
            TECHNIQUE_TACTIC["T1021"],
            "The step explicitly identifies a synthetic remote service channel.",
        )
    if metadata.get("channel_type") == "synthetic_c2":
        return StepTechnique(
            step.sequence,
            "T1041",
            TECHNIQUE_NAME["T1041"],
            TECHNIQUE_TACTIC["T1041"],
            "The step explicitly uses a synthetic C2 channel for transfer.",
        )
    if metadata.get("channel_type") == "synthetic_web_service" and isinstance(
        metadata.get("web_service"), str
    ):
        return StepTechnique(
            step.sequence,
            "T1567",
            TECHNIQUE_NAME["T1567"],
            TECHNIQUE_TACTIC["T1567"],
            "The step explicitly uses an identified synthetic web service for transfer.",
        )
    return StepTechnique(
        step.sequence, None, None, None, "No declared indicator matches a catalogued technique."
    )


def iter_scenario_techniques(scenario: SimulationScenario) -> list[StepTechnique]:
    failed_users: set[str] = set()
    results: list[StepTechnique] = []
    for step in scenario.steps:
        # Mirror correlation_service's failed-attempts heuristic, which in
        # the real event pipeline comes from TelemetryEvent.failed_attempts
        # (a generated field, not authored on the step). ScenarioStep does
        # not carry a failed_attempts count, so we conservatively derive the
        # same signal from the step's own declared metadata/description
        # instead of guessing an event-generation-time number.
        metadata = dict(step.metadata)
        if metadata.get("attempt_pattern") != "repeated" and "repeated" in step.description.lower():
            metadata["attempt_pattern"] = "repeated"
        mirrored = ScenarioStep(**{**step.model_dump(), "metadata": metadata})
        results.append(expected_technique_for_step(mirrored, failed_users))
    return results


def summarize(scenario_id: str) -> ScenarioMitreSummary:
    scenario = next((item for item in SCENARIOS if item.scenario_id == scenario_id), None)
    if scenario is None:
        raise ValueError(f"Unknown scenario_id '{scenario_id}'.")
    step_techniques = iter_scenario_techniques(scenario)
    technique_ids = sorted({item.technique_id for item in step_techniques if item.technique_id})
    for technique_id in technique_ids:
        if technique_id not in VALID_TECHNIQUE_IDS:
            raise ValueError(
                f"Scenario '{scenario_id}' step maps to technique '{technique_id}', which is not "
                "in the local MITRE catalogue. Unknown technique IDs are never invented — extend "
                "the catalogue explicitly if this is intentional."
            )
    return ScenarioMitreSummary(
        scenario_id=scenario.scenario_id,
        name=scenario.name,
        is_red_agent_scenario=scenario_id in RED_AGENT_SCENARIO_IDS,
        step_techniques=step_techniques,
        technique_ids=technique_ids,
    )


def summarize_all() -> list[ScenarioMitreSummary]:
    return [summarize(scenario.scenario_id) for scenario in SCENARIOS]


def _known_asset_ids() -> frozenset[str]:
    return frozenset(node.asset_id for node in topology_service.nodes(include_sink=True))


def _validate_asset(scenario_id: str, sequence: int, field: str, asset_id: str | None) -> None:
    if asset_id is None:
        return
    if asset_id not in _known_asset_ids():
        raise ValueError(
            f"Scenario '{scenario_id}' step {sequence}'s {field} references unknown synthetic "
            f"asset '{asset_id}'. Structured Red steps may only reference assets that exist in "
            "the synthetic topology (topology_service)."
        )


def _step_definition(
    scenario_id: str, step: ScenarioStep, technique: StepTechnique, previous_step_id: str | None
) -> RedScenarioStepDefinition:
    _validate_asset(scenario_id, step.sequence, "source_asset_id", step.source_id)
    _validate_asset(scenario_id, step.sequence, "target_asset_id", step.destination_id)
    step_id = f"{scenario_id}:step-{step.sequence}"
    technique_ids = [technique.technique_id] if technique.technique_id else []
    for technique_id in technique_ids:
        if technique_id not in VALID_TECHNIQUE_IDS:
            raise ValueError(
                f"Scenario '{scenario_id}' step {step.sequence} maps to technique "
                f"'{technique_id}', which is not in the local MITRE catalogue."
            )
    return RedScenarioStepDefinition(
        step_id=step_id,
        sequence=step.sequence,
        name=step.description,
        description=(
            f"{step.description} (telemetry: {step.event_type.value}/{step.action.value}, "
            f"declared outcome: {step.outcome.value})."
        ),
        action_type=step.action.value,
        source_asset_id=step.source_id,
        target_asset_id=step.destination_id,
        prerequisites=[previous_step_id] if previous_step_id else [],
        expected_technique_ids=technique_ids,
        expected_event_type=step.event_type.value,
        success_condition=f"telemetry event outcome == '{step.outcome.value}'",
        synthetic=True,
    )


CRITICALITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
SENSITIVITY_RANK = {"standard": 0, "restricted": 1, "highly_restricted": 2}


def _highest_value_target(scenario: SimulationScenario) -> str | None:
    """The scenario's actual high-value objective, not merely its last step's
    target (which for several scenarios is a session-teardown step, not the
    real objective). Picks the destination asset with the highest declared
    topology criticality/sensitivity among all steps - the same criteria
    `attack_graph_service._enumerate_paths` uses to decide a valid attack
    target, so this stays consistent with the Attack Graph engine's own
    notion of "high value" rather than inventing a separate one.
    """

    best_id: str | None = None
    best_rank = (-1, -1)
    for step in scenario.steps:
        if step.destination_id is None:
            continue
        node = topology_service.node(step.destination_id, include_sink=True)
        rank = (
            CRITICALITY_RANK.get(node.criticality, 0),
            SENSITIVITY_RANK.get(node.sensitivity, 0),
        )
        if rank > best_rank:
            best_rank = rank
            best_id = step.destination_id
    return best_id


def build_definition(scenario: SimulationScenario) -> RedScenarioDefinition:
    """Project the existing scenario/step catalogue into the richer,
    security-oriented `RedScenarioDefinition` view the Phase 3 Red
    adversary-emulation contract requires. Does not duplicate scenario
    execution or MITRE-mapping logic - see `iter_scenario_techniques` above,
    which this reuses unchanged.
    """

    techniques = iter_scenario_techniques(scenario)
    step_definitions: list[RedScenarioStepDefinition] = []
    previous_step_id: str | None = None
    for step, technique in zip(scenario.steps, techniques, strict=True):
        definition = _step_definition(scenario.scenario_id, step, technique, previous_step_id)
        step_definitions.append(definition)
        previous_step_id = definition.step_id

    first_step = scenario.steps[0]
    initial_access_point = first_step.source_id
    high_value_objective = _highest_value_target(scenario)
    technique_ids = sorted({tid for sd in step_definitions for tid in sd.expected_technique_ids})
    description = (
        f"{len(scenario.steps)}-step deterministic scenario exercising technique(s): "
        f"{', '.join(technique_ids) if technique_ids else 'none'}."
    )
    return RedScenarioDefinition(
        scenario_id=scenario.scenario_id,
        display_name=scenario.name,
        objective=scenario.description,
        description=description,
        initial_access_point=initial_access_point,
        high_value_objective=high_value_objective,
        prerequisites=[f"attacker-controlled foothold at {initial_access_point}"],
        is_red_agent_scenario=scenario.scenario_id in RED_AGENT_SCENARIO_IDS,
        steps=step_definitions,
        synthetic=True,
    )


def definition_for(scenario_id: str) -> RedScenarioDefinition:
    scenario = next((item for item in SCENARIOS if item.scenario_id == scenario_id), None)
    if scenario is None:
        raise ValueError(f"Unknown scenario_id '{scenario_id}'.")
    return build_definition(scenario)


def all_definitions() -> list[RedScenarioDefinition]:
    return [build_definition(scenario) for scenario in SCENARIOS]
