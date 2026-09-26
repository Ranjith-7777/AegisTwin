"""Validates that red_scenario_catalogue's static MITRE mapping never
invents a technique ID and stays internally consistent across all real,
built-in scenarios, and that the structured `RedScenarioDefinition`
projection never references an unknown technique or synthetic asset."""

import pytest

from app.services.red_scenario_catalogue import (
    VALID_TECHNIQUE_IDS,
    StepTechnique,
    _step_definition,
    all_definitions,
    definition_for,
    summarize,
    summarize_all,
)
from app.services.scenario_service import SCENARIOS
from app.services.topology_service import topology_service


def test_every_scenario_summarizes_without_inventing_technique_ids() -> None:
    summaries = summarize_all()
    assert len(summaries) == len(SCENARIOS)
    for summary in summaries:
        for technique_id in summary.technique_ids:
            assert technique_id in VALID_TECHNIQUE_IDS
        for step in summary.step_techniques:
            if step.technique_id is not None:
                assert step.technique_id in VALID_TECHNIQUE_IDS
                assert step.technique_name is not None
                assert step.tactic is not None
            assert step.rationale


def test_normal_operations_scenario_maps_to_no_techniques() -> None:
    summary = summarize("normal-operations")
    assert summary.technique_ids == []
    assert summary.is_red_agent_scenario is False


def test_credential_compromise_scenario_detects_brute_force_then_valid_account() -> None:
    summary = summarize("credential-compromise")
    assert summary.technique_ids == ["T1078", "T1110.001"]
    ordered = [step.technique_id for step in summary.step_techniques if step.technique_id]
    assert ordered[0] == "T1110.001"
    assert "T1078" in ordered


def test_unknown_scenario_id_raises() -> None:
    try:
        summarize("not-a-real-scenario")
    except ValueError as exc:
        assert "Unknown scenario_id" in str(exc)
    else:
        raise AssertionError("expected ValueError for an unknown scenario_id")


def test_all_definitions_expose_the_required_structured_fields() -> None:
    for definition in all_definitions():
        assert definition.scenario_id
        assert definition.display_name
        assert definition.objective
        assert definition.description
        assert definition.initial_access_point
        assert definition.prerequisites
        assert definition.steps
        assert definition.synthetic is True
        for step in definition.steps:
            assert step.step_id
            assert step.sequence >= 1
            assert step.name
            assert step.description
            assert step.action_type
            assert step.source_asset_id
            assert step.expected_event_type
            assert step.success_condition
            assert step.synthetic is True


def test_steps_are_uniquely_and_contiguously_ordered() -> None:
    for definition in all_definitions():
        sequences = [step.sequence for step in definition.steps]
        assert sequences == sorted(sequences)
        assert len(sequences) == len(set(sequences))
        assert sequences == list(range(1, len(sequences) + 1))
        step_ids = [step.step_id for step in definition.steps]
        assert len(step_ids) == len(set(step_ids))


def test_referenced_assets_are_valid_synthetic_topology_assets() -> None:
    known_assets = {node.asset_id for node in topology_service.nodes(include_sink=True)}
    for definition in all_definitions():
        assert definition.initial_access_point in known_assets
        if definition.high_value_objective is not None:
            assert definition.high_value_objective in known_assets
        for step in definition.steps:
            assert step.source_asset_id in known_assets
            if step.target_asset_id is not None:
                assert step.target_asset_id in known_assets


def test_referenced_technique_ids_are_valid() -> None:
    for definition in all_definitions():
        for step in definition.steps:
            for technique_id in step.expected_technique_ids:
                assert technique_id in VALID_TECHNIQUE_IDS


def test_step_prerequisites_chain_to_the_previous_step() -> None:
    definition = definition_for("leaked-api-credential")
    assert definition.steps[0].prerequisites == []
    for previous, current in zip(definition.steps, definition.steps[1:], strict=False):
        assert current.prerequisites == [previous.step_id]


def test_an_injected_unknown_technique_id_fails_validation() -> None:
    scenario = next(item for item in SCENARIOS if item.scenario_id == "credential-compromise")
    step = scenario.steps[0]
    bogus_technique = StepTechnique(
        step_sequence=step.sequence,
        technique_id="T9999",
        technique_name="Not A Real Technique",
        tactic="fabricated-tactic",
        rationale="constructed for this test",
    )
    with pytest.raises(ValueError, match="not in the local MITRE catalogue"):
        _step_definition(scenario.scenario_id, step, bogus_technique, None)


def test_an_injected_unknown_asset_reference_fails_validation() -> None:
    scenario = next(item for item in SCENARIOS if item.scenario_id == "credential-compromise")
    step = scenario.steps[0].model_copy(update={"destination_id": "not-a-real-synthetic-asset"})
    technique = StepTechnique(
        step_sequence=step.sequence,
        technique_id=None,
        technique_name=None,
        tactic=None,
        rationale="no technique needed for this test",
    )
    with pytest.raises(ValueError, match="unknown synthetic asset"):
        _step_definition(scenario.scenario_id, step, technique, None)
