"""Correction pass: proves `rule_based`/`ml_assisted` are genuinely
non-agentic baselines that never touch Phase 4's six-agent orchestration
pipeline, and that `agentic`/`no_active_defence` are unaffected.

Runs REAL experiments end-to-end through `experiment_service.create_and_run`
(never hand-constructed fixtures), matching the style of
`test_batch_runner.py`/`test_experiment_timeline.py`, because the bug this
corrects (`rule_based`/`ml_assisted` secretly running all six Blue agents via
`orchestration_service.create()/.execute()/.verify()`) is only meaningfully
provable against the genuine pipeline, not a mock of it.

The single most important test in this file is
`test_cross_mode_agent_decision_record_counts_on_one_paired_run`: it runs the
identical scenario/seed through all four defence modes and asserts the exact
`AgentDecisionRecord` counts side by side.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import (
    AgentDecisionRecord,
    EvaluationSyntheticActionRecord,
    ExperimentRecord,
    ResponseAnalysisRecord,
    ResponsePlanAssessmentRecord,
)
from app.schemas.evaluation import DefenceMode, ExperimentCreate
from app.services.evaluation.evaluation_pipeline import evaluate_experiment
from app.services.evaluation.experiment_service import experiment_service
from app.services.response_playbook_service import response_playbook_service

SCENARIO = "leaked-api-credential"
SEED = 7


def _session(client: TestClient) -> Session:
    return cast(Session, cast(FastAPI, client.app).state.database.session_factory())


def _run(session: Session, defence_mode: DefenceMode, seed: int = SEED) -> ExperimentRecord:
    request = ExperimentCreate(scenario_id=SCENARIO, seed=seed, defence_mode=defence_mode)
    experiment = experiment_service.create_and_run(session, request)
    assert experiment.status == "completed", experiment.failure_message
    return experiment


def _agent_decision_count(session: Session, experiment: ExperimentRecord) -> int:
    if experiment.orchestration_id is None:
        return 0
    statement = select(AgentDecisionRecord).where(
        AgentDecisionRecord.orchestration_id == experiment.orchestration_id
    )
    return len(list(session.scalars(statement)))


# ----------------------------------------------------------------------
# RULE_BASED
# ----------------------------------------------------------------------


def test_rule_based_never_creates_a_phase4_orchestration(client: TestClient) -> None:
    session = _session(client)
    try:
        with (
            patch("app.services.evaluation.strategies.workflow_coordinator") as mock_coordinator,
            patch("app.services.evaluation.strategies.response_service") as mock_response_service,
        ):
            experiment = _run(session, DefenceMode.RULE_BASED)
            mock_coordinator.run.assert_not_called()
            mock_response_service.analyze.assert_not_called()

        assert experiment.orchestration_id is None
        assert experiment.evaluation_action_id is not None
        assert _agent_decision_count(session, experiment) == 0
    finally:
        session.close()


def test_rule_based_produces_zero_agent_decision_records(client: TestClient) -> None:
    session = _session(client)
    try:
        experiment = _run(session, DefenceMode.RULE_BASED)
        total = session.scalar(select(AgentDecisionRecord.agent_decision_id).limit(1))
        assert total is None, "no AgentDecisionRecord should exist anywhere for this test run"
        assert _agent_decision_count(session, experiment) == 0
    finally:
        session.close()


def test_rule_based_selection_is_the_documented_deterministic_rule(client: TestClient) -> None:
    session = _session(client)
    try:
        # leaked-api-credential seed 7 is known (from prior Phase 4/5 smoke
        # tests) to observe an anomalous external ingress edge, so
        # RULE-INGRESS-01 (an auto-eligible playbook already, no fallback
        # needed) should fire.
        experiment = _run(session, DefenceMode.RULE_BASED)
        assert experiment.evaluation_action_id is not None
        action = session.get(EvaluationSyntheticActionRecord, experiment.evaluation_action_id)
        assert action is not None
        assert action.defence_mode == "rule_based"
        assert action.rule_id == "RULE-INGRESS-01"
        assert action.executed is True
        assert action.playbook_id == "quarantine-synthetic-ingress-edge"
    finally:
        session.close()


def test_rule_based_still_executes_a_real_synthetic_mutation_and_metrics(
    client: TestClient,
) -> None:
    session = _session(client)
    try:
        experiment = _run(session, DefenceMode.RULE_BASED)
        assert experiment.changed_node_ids_json or experiment.changed_edge_ids_json

        metric_record, _points = evaluate_experiment(session, experiment.experiment_id)
        raw = metric_record.raw_metrics_json
        assert raw["attack_path_reduction"] is not None
        assert raw["operational_disruption"] is not None
        assert raw["containment_success"] is not None
        # verification_success is N/A by design - rule_based never runs
        # Phase 4's dedicated Verification Agent.
        assert raw["verification_success"] is None
    finally:
        session.close()


# ----------------------------------------------------------------------
# ML_ASSISTED
# ----------------------------------------------------------------------


def test_ml_assisted_calls_response_service_analyze_but_never_orchestration(
    client: TestClient,
) -> None:
    session = _session(client)
    try:
        with patch("app.services.evaluation.strategies.workflow_coordinator") as mock_coordinator:
            experiment = _run(session, DefenceMode.ML_ASSISTED)
            mock_coordinator.run.assert_not_called()

        assert experiment.orchestration_id is None
        assert experiment.evaluation_action_id is not None
        assert _agent_decision_count(session, experiment) == 0

        # response_service.analyze() persists its own real analysis
        # records regardless of what the caller does with the result.
        analyses = list(
            session.scalars(
                select(ResponseAnalysisRecord).where(
                    ResponseAnalysisRecord.incident_candidate_id == experiment.incident_candidate_id
                )
            )
        )
        assert analyses, "response_service.analyze() should have persisted a real analysis"
    finally:
        session.close()


def test_ml_assisted_never_produces_a_response_plan_assessment(client: TestClient) -> None:
    """ml_assisted never constructs a `CandidatePlanAssessment`/
    `ResponsePlanAssessmentRecord` - that is the Agentic-only Response
    Utility Score machinery."""

    session = _session(client)
    try:
        experiment = _run(session, DefenceMode.ML_ASSISTED)
        assessments = list(
            session.scalars(
                select(ResponsePlanAssessmentRecord).where(
                    ResponsePlanAssessmentRecord.incident_candidate_id
                    == experiment.incident_candidate_id
                )
            )
        )
        assert assessments == []
    finally:
        session.close()


def test_ml_assisted_selects_exactly_one_auto_eligible_recommendation(
    client: TestClient,
) -> None:
    session = _session(client)
    try:
        experiment = _run(session, DefenceMode.ML_ASSISTED)
        assert experiment.evaluation_action_id is not None
        actions = list(
            session.scalars(
                select(EvaluationSyntheticActionRecord).where(
                    EvaluationSyntheticActionRecord.experiment_id == experiment.experiment_id
                )
            )
        )
        assert len(actions) == 1
        action = actions[0]
        assert action.defence_mode == "ml_assisted"
        assert action.executed is True
        assert action.recommendation_rank is not None
        assert action.defense_score is not None
        assert action.playbook_id is not None
        assert response_playbook_service.get(action.playbook_id).automatic_eligibility is True
    finally:
        session.close()


def test_ml_assisted_still_executes_a_real_synthetic_mutation_and_metrics(
    client: TestClient,
) -> None:
    session = _session(client)
    try:
        experiment = _run(session, DefenceMode.ML_ASSISTED)
        assert experiment.changed_node_ids_json or experiment.changed_edge_ids_json

        metric_record, _points = evaluate_experiment(session, experiment.experiment_id)
        raw = metric_record.raw_metrics_json
        assert raw["attack_path_reduction"] is not None
        assert raw["operational_disruption"] is not None
        assert raw["verification_success"] is None
    finally:
        session.close()


# ----------------------------------------------------------------------
# AGENTIC (no regression)
# ----------------------------------------------------------------------


def test_agentic_still_uses_the_real_workflow_coordinator(client: TestClient) -> None:
    session = _session(client)
    try:
        with patch(
            "app.services.evaluation.strategies.workflow_coordinator",
        ) as mock_coordinator:
            mock_coordinator.run.side_effect = AssertionError(
                "workflow_coordinator.run should really be called for agentic mode"
            )
            request = ExperimentCreate(
                scenario_id=SCENARIO, seed=SEED, defence_mode=DefenceMode.AGENTIC
            )
            experiment = experiment_service.create_and_run(session, request)
            # The strategy dispatch raised inside `workflow_coordinator.run`
            # (via the mock), so the experiment should have failed - proving
            # the call really happened.
            assert experiment.status == "failed"
            mock_coordinator.run.assert_called_once()
    finally:
        session.close()


def test_agentic_full_six_agent_order_is_unaffected(client: TestClient) -> None:
    session = _session(client)
    try:
        experiment = _run(session, DefenceMode.AGENTIC)
        assert experiment.orchestration_id is not None
        statement = (
            select(AgentDecisionRecord)
            .where(AgentDecisionRecord.orchestration_id == experiment.orchestration_id)
            .order_by(AgentDecisionRecord.created_at)
        )
        decisions = list(session.scalars(statement))
        assert [d.agent_name for d in decisions] == [
            "Response Planner Simulation Agent",
            "Impact Simulation Agent",
            "Safety Governor Agent",
            "Approval Router Agent",
            "Synthetic Execution Agent",
            "Verification Agent",
        ]
    finally:
        session.close()


# ----------------------------------------------------------------------
# NO_ACTIVE_DEFENCE (no regression)
# ----------------------------------------------------------------------


def test_no_active_defence_never_mutates_or_orchestrates(client: TestClient) -> None:
    session = _session(client)
    try:
        experiment = _run(session, DefenceMode.NO_ACTIVE_DEFENCE)
        assert experiment.changed_node_ids_json == []
        assert experiment.changed_edge_ids_json == []
        assert experiment.orchestration_id is None
        assert experiment.evaluation_action_id is None
        assert _agent_decision_count(session, experiment) == 0
    finally:
        session.close()


# ----------------------------------------------------------------------
# THE cross-mode comparison
# ----------------------------------------------------------------------


def test_cross_mode_agent_decision_record_counts_on_one_paired_run(client: TestClient) -> None:
    """The single most important test in this correction pass: the same
    scenario/seed (`leaked-api-credential`, seed 7 - confirmed by prior
    Phase 4/5 stages to reach a clean `successful_simulation` completion for
    agentic mode) run through all four defence modes must show EXACTLY:

        no_active_defence: 0
        rule_based: 0
        ml_assisted: 0
        agentic: 6
    """

    session = _session(client)
    try:
        counts: dict[str, int] = {}
        for mode in (
            DefenceMode.NO_ACTIVE_DEFENCE,
            DefenceMode.RULE_BASED,
            DefenceMode.ML_ASSISTED,
            DefenceMode.AGENTIC,
        ):
            experiment = _run(session, mode)
            counts[mode.value] = _agent_decision_count(session, experiment)

        assert counts == {
            "no_active_defence": 0,
            "rule_based": 0,
            "ml_assisted": 0,
            "agentic": 6,
        }
    finally:
        session.close()
