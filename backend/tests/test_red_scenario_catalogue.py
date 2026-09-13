"""Validates that red_scenario_catalogue's static MITRE mapping never
invents a technique ID and stays internally consistent across all real,
built-in scenarios."""

from app.services.red_scenario_catalogue import VALID_TECHNIQUE_IDS, summarize, summarize_all
from app.services.scenario_service import SCENARIOS


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
