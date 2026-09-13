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

from app.schemas.simulation import ScenarioStep, SimulationScenario
from app.services.mitre_catalogue_service import CATALOGUE
from app.services.scenario_service import RED_AGENT_SCENARIO_IDS, SCENARIOS

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
