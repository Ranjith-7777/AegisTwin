from typing import Any, cast

from fastapi.testclient import TestClient

from app.schemas.blue_planning import (
    CandidatePlanAssessment,
    ResponseUtilityScoreBreakdown,
    SecurityGainEvidence,
)
from app.services.blue_planning_service import select_recommended


def prepare(client: TestClient) -> tuple[str, str, str]:
    run = client.post(
        "/api/v1/simulation/runs",
        json={
            "scenario_id": "staged-compromise-demo",
            "seed": 84,
            "start_time": "2026-07-21T01:30:00Z",
            "playback_speed": 50,
        },
    ).json()
    trained = client.post(
        "/api/v1/detection/models/train",
        json={
            "training_seed_range": {"start": 1, "end": 1},
            "validation_seed_range": {"start": 2, "end": 2},
            "evaluation_seed_range": {"start": 3, "end": 3},
            "random_state": 17,
            "target_false_positive_rate": 0.1,
            "n_estimators": 100,
        },
    ).json()
    run_id, model_id = str(run["simulation_run_id"]), str(trained["model_id"])
    assert (
        client.post(
            f"/api/v1/detection/runs/{run_id}/score", json={"model_id": model_id}
        ).status_code
        == 200
    )
    analyze = client.post(
        f"/api/v1/correlation/runs/{run_id}/analyze", json={"model_id": model_id}
    ).json()
    return run_id, model_id, str(analyze["incident_candidate_id"])


def compare(
    client: TestClient, run_id: str, model_id: str, candidate_id: str, sequence: int = 10
) -> dict[str, Any]:
    return cast(
        "dict[str, Any]",
        client.post(
            f"/api/v1/blue-planning/runs/{run_id}/compare",
            json={
                "model_id": model_id,
                "incident_candidate_id": candidate_id,
                "through_sequence_number": sequence,
                "top_k": 5,
            },
        ).json(),
    )


def test_comparison_produces_ranked_candidates_with_a_recommended_plan(
    client: TestClient,
) -> None:
    run_id, model_id, candidate_id = prepare(client)
    result = compare(client, run_id, model_id, candidate_id)
    assert len(result["candidates"]) >= 2
    scores = [c["utility_score"]["total"] for c in result["candidates"]]
    assert scores == sorted(scores, reverse=True)
    assert result["recommended_recommendation_id"] is not None
    recommended = [c for c in result["candidates"] if c["recommended"]]
    assert len(recommended) == 1
    assert recommended[0]["recommendation_id"] == result["recommended_recommendation_id"]


def test_observation_only_playbook_never_shows_a_false_security_gain(
    client: TestClient,
) -> None:
    """Regression test for a real bug: an observe-only mutation (annotate_node)
    must never be credited with removing attack paths it never touched."""

    run_id, model_id, candidate_id = prepare(client)
    result = compare(client, run_id, model_id, candidate_id)
    monitoring = next(
        c for c in result["candidates"] if c["playbook_id"] == "increase-synthetic-monitoring"
    )
    assert monitoring["security_gain_evidence"]["security_gain"] == 0.0
    assert (
        monitoring["security_gain_evidence"]["attack_paths_before"]
        == (monitoring["security_gain_evidence"]["attack_paths_after"])
    )


def test_an_edge_removing_playbook_shows_real_nonzero_security_gain(client: TestClient) -> None:
    run_id, model_id, candidate_id = prepare(client)
    result = compare(client, run_id, model_id, candidate_id)
    by_id = {c["playbook_id"]: c for c in result["candidates"]}
    assert "block-synthetic-route" in by_id
    edge_removal = by_id["block-synthetic-route"]
    assert edge_removal["security_gain_evidence"]["security_gain"] > 0.0
    assert (
        edge_removal["security_gain_evidence"]["attack_paths_after"]
        < edge_removal["security_gain_evidence"]["attack_paths_before"]
    )


def test_what_if_comparison_never_mutates_the_persisted_topology(client: TestClient) -> None:
    before = client.get("/api/v1/topology", params={"include_synthetic_sink": True}).json()
    run_id, model_id, candidate_id = prepare(client)
    compare(client, run_id, model_id, candidate_id)
    after = client.get("/api/v1/topology", params={"include_synthetic_sink": True}).json()
    assert before["nodes"] == after["nodes"]
    assert before["edges"] == after["edges"]


def test_comparison_is_deterministic_for_identical_inputs(client: TestClient) -> None:
    run_id, model_id, candidate_id = prepare(client)
    first = compare(client, run_id, model_id, candidate_id)
    second = compare(client, run_id, model_id, candidate_id)
    assert first["candidates"] == second["candidates"]
    assert first["decision_confidence"] == second["decision_confidence"]


def test_decision_confidence_is_never_called_a_probability(client: TestClient) -> None:
    run_id, model_id, candidate_id = prepare(client)
    result = compare(client, run_id, model_id, candidate_id)
    assert "not a calibrated probability" in result["decision_confidence"]["note"]


def test_assessment_is_reconstructable_after_reload(client: TestClient) -> None:
    from app.services.blue_planning_service import blue_planning_service

    run_id, model_id, candidate_id = prepare(client)
    result = compare(client, run_id, model_id, candidate_id)
    assessment_id = blue_planning_service.assessment_id(run_id, model_id, candidate_id, 10)
    reloaded = client.get(f"/api/v1/blue-planning/assessments/{assessment_id}").json()
    assert reloaded["candidates"] == result["candidates"]
    assert reloaded["recommended_recommendation_id"] == result["recommended_recommendation_id"]


def test_unknown_assessment_id_is_404(client: TestClient) -> None:
    response = client.get("/api/v1/blue-planning/assessments/does-not-exist")
    assert response.status_code == 404


def test_a_policy_failing_candidate_is_never_recommended(client: TestClient) -> None:
    run_id, model_id, candidate_id = prepare(client)
    client.put(
        "/api/v1/autonomy",
        json={"mode": "autonomous", "updated_by": "analyst-1", "confirm": True},
    )
    result = compare(client, run_id, model_id, candidate_id)
    for candidate in result["candidates"]:
        if not candidate["policy_pass"]:
            assert candidate["recommended"] is False


def _assessment(
    recommendation_id: str, *, score: float, policy_pass: bool
) -> CandidatePlanAssessment:
    """Minimal, deterministic CandidatePlanAssessment fixture for unit
    testing select_recommended() in isolation from the full graph/policy
    pipeline."""

    zero_evidence = SecurityGainEvidence(
        attack_paths_before=0,
        attack_paths_after=0,
        top_attack_path_score_before=0.0,
        top_attack_path_score_after=0.0,
        critical_targets_reachable_before=0,
        critical_targets_reachable_after=0,
        blast_radius_reachable_before=0,
        blast_radius_reachable_after=0,
        blast_radius_critical_before=0,
        blast_radius_critical_after=0,
        security_gain=0.0,
    )
    return CandidatePlanAssessment(
        recommendation_id=recommendation_id,
        playbook_id="test-playbook",
        playbook_name="Test playbook",
        action_type="edge_restriction",
        target_type="relationship",
        target_id="a--b",
        required_approval_tier="automatic_candidate",
        reversibility="reversible",
        operational_impact="low",
        security_gain_evidence=zero_evidence,
        utility_score=ResponseUtilityScoreBreakdown(
            security_gain=0.0,
            critical_asset_protection=0.0,
            blast_radius_reduction=0.0,
            evidence_quality=0.0,
            reversibility_bonus=0.0,
            operational_impact_penalty=0.0,
            total=score,
        ),
        policy_pass=policy_pass,
        policy_failed_ids=[] if policy_pass else ["POL-004"],
        recommended=False,
        changed_node_ids=[],
        changed_edge_ids=[],
    )


def test_select_recommended_falls_back_to_the_next_policy_compliant_candidate() -> None:
    """The exact PM-reported defect: candidate A scores higher but fails
    policy; candidate B scores lower but passes. B must be recommended -
    "highest-scoring policy-compliant candidate," not "highest-scoring
    candidate, or nothing." Candidates are pre-sorted by score, matching
    what compare() does before calling select_recommended()."""

    candidate_a = _assessment("candidate-a", score=90.0, policy_pass=False)
    candidate_b = _assessment("candidate-b", score=40.0, policy_pass=True)
    sorted_candidates = [candidate_a, candidate_b]

    updated, selected_index = select_recommended(sorted_candidates)

    assert selected_index == 1
    assert updated[1].recommendation_id == "candidate-b"
    assert updated[1].recommended is True
    # Exactly one candidate is recommended.
    assert sum(1 for item in updated if item.recommended) == 1
    assert updated[0].recommended is False


def test_select_recommended_returns_none_when_no_candidate_passes_policy() -> None:
    candidate_a = _assessment("candidate-a", score=90.0, policy_pass=False)
    candidate_b = _assessment("candidate-b", score=40.0, policy_pass=False)

    updated, selected_index = select_recommended([candidate_a, candidate_b])

    assert selected_index is None
    assert all(not item.recommended for item in updated)


def test_select_recommended_keeps_the_top_candidate_when_it_already_passes() -> None:
    candidate_a = _assessment("candidate-a", score=90.0, policy_pass=True)
    candidate_b = _assessment("candidate-b", score=40.0, policy_pass=True)

    updated, selected_index = select_recommended([candidate_a, candidate_b])

    assert selected_index == 0
    assert updated[0].recommended is True
    assert updated[1].recommended is False


def test_compare_recommends_second_ranked_candidate_when_top_fails_policy(
    client: TestClient,
) -> None:
    """End-to-end proof through the real compare() pipeline: force the
    top-ranked candidate to fail policy (without weakening any policy rule)
    and confirm the second-ranked, policy-passing candidate is recommended,
    exactly one candidate is recommended, and Decision Confidence is
    derived from the selected candidate, not the rejected top one."""

    from unittest.mock import patch

    from app.schemas.policy import PolicyEvaluationResult
    from app.services import policy_service

    run_id, model_id, candidate_id = prepare(client)
    baseline = compare(client, run_id, model_id, candidate_id)
    assert len(baseline["candidates"]) >= 2
    top_playbook_id = baseline["candidates"][0]["playbook_id"]
    second_playbook_id = baseline["candidates"][1]["playbook_id"]
    assert top_playbook_id != second_playbook_id

    real_evaluate = policy_service.evaluate_response_policies

    def fake_evaluate(*, playbook, **kwargs):  # type: ignore[no-untyped-def]
        if playbook.playbook_id == top_playbook_id:
            return PolicyEvaluationResult(
                evaluations=[],
                overall_pass=False,
                failed_policy_ids=["POL-004"],
            )
        return real_evaluate(playbook=playbook, **kwargs)

    with patch(
        "app.services.blue_planning_service.policy_service.evaluate_response_policies",
        fake_evaluate,
    ):
        result = compare(client, run_id, model_id, candidate_id, sequence=11)

    recommended = [c for c in result["candidates"] if c["recommended"]]
    assert len(recommended) == 1
    assert recommended[0]["playbook_id"] == second_playbook_id
    assert result["recommended_recommendation_id"] == recommended[0]["recommendation_id"]

    top_candidate = next(c for c in result["candidates"] if c["playbook_id"] == top_playbook_id)
    assert top_candidate["policy_pass"] is False
    assert top_candidate["recommended"] is False

    # Decision Confidence must correspond to the SELECTED (second-ranked)
    # candidate's security-gain evidence, not the rejected top candidate's.
    expected_confidence_seed = recommended[0]["security_gain_evidence"]["security_gain"]
    assert result["decision_confidence"]["response_simulation_improvement"] == min(
        20.0, expected_confidence_seed
    )
