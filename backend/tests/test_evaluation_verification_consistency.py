"""Regression: evaluation metrics and the Verification Agent must score the
same executed action the same way.

Before the fix, `metrics_service` measured attack-path / critical-exposure
reduction with a single-anchor traversal while the Verification Agent (and
the Blue planner) used the edge-aware `best_security_gain_evidence`. For an
edge cut upstream of the default anchor - e.g. quarantining the attacker's
ingress route - evaluation reported zero reduction and `containment_success
= False` for an agentic run whose own verification had confirmed attack
paths 1 -> 0.
"""

from __future__ import annotations

from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.schemas.evaluation import DefenceMode, ExperimentCreate
from app.services.evaluation.evaluation_pipeline import evaluate_experiment
from app.services.evaluation.experiment_service import experiment_service


def _session(client: TestClient) -> Session:
    return cast(Session, cast(FastAPI, client.app).state.database.session_factory())


@pytest.mark.parametrize("scenario", ["staged-compromise-demo", "ddos-traffic-spike"])
def test_agentic_containment_agrees_with_its_own_verification(
    client: TestClient, scenario: str
) -> None:
    session = _session(client)
    try:
        experiment = experiment_service.create_and_run(
            session,
            ExperimentCreate(scenario_id=scenario, seed=84, defence_mode=DefenceMode.AGENTIC),
        )
        assert experiment.status == "completed", experiment.failure_message
        metric_record, _ = evaluate_experiment(session, experiment.experiment_id)
        raw = metric_record.raw_metrics_json
        # The playbook cuts the attacker's ingress relationship.
        assert experiment.changed_edge_ids_json == ["external-user-01--api-gateway-01"]
        assert raw["verification_success"] is True
        assert raw["containment_success"] is True
        assert raw["attack_path_reduction"] == 1.0
        assert raw["critical_exposure_reduction"] == 1.0
    finally:
        session.close()


def test_edge_cut_by_rule_based_baseline_is_credited_the_same_way(client: TestClient) -> None:
    session = _session(client)
    try:
        experiment = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="leaked-api-credential", seed=84, defence_mode=DefenceMode.RULE_BASED
            ),
        )
        assert experiment.status == "completed", experiment.failure_message
        metric_record, _ = evaluate_experiment(session, experiment.experiment_id)
        raw = metric_record.raw_metrics_json
        if experiment.changed_edge_ids_json:
            assert raw["attack_path_reduction"] == 1.0
            assert raw["containment_success"] is True
    finally:
        session.close()


def test_no_active_defence_is_never_credited(client: TestClient) -> None:
    session = _session(client)
    try:
        experiment = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="staged-compromise-demo",
                seed=84,
                defence_mode=DefenceMode.NO_ACTIVE_DEFENCE,
            ),
        )
        metric_record, _ = evaluate_experiment(session, experiment.experiment_id)
        raw = metric_record.raw_metrics_json
        assert raw["attack_path_reduction"] == 0.0
        assert raw["containment_success"] is None
    finally:
        session.close()
