"""Tests for the Phase 5 Section 38 partial-observability robustness
perturbation (`app.services.evaluation.perturbation_service`).

Uses the same real `leaked-api-credential` seed 7 pattern already
established in `test_batch_runner.py` - a real, small, end-to-end run
through `experiment_service.create_and_run`/`evaluate_experiment`, not a
hand-constructed fixture, because the whole point of this feature is
"does defence performance actually degrade" against genuinely computed
data.
"""

from __future__ import annotations

from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.models import TelemetryEventRecord
from app.schemas.evaluation import DefenceMode, ExperimentCreate, ExperimentStatus
from app.schemas.simulation import SimulationRunCreate
from app.services.evaluation.evaluation_pipeline import evaluate_experiment
from app.services.evaluation.experiment_service import (
    CANONICAL_PLAYBACK_SPEED,
    CANONICAL_START_TIME,
    experiment_service,
)
from app.services.evaluation.metrics_service import GROUND_TRUTH_SEVERITIES
from app.services.evaluation.perturbation_service import (
    PARTIAL_OBSERVABILITY_PERTURBATION_ID,
    apply_perturbation,
)
from app.services.simulation_service import simulation_run_service


def _session(client: TestClient):  # type: ignore[no-untyped-def]
    return cast(FastAPI, client.app).state.database.session_factory()


def _ensure_run(session, scenario_id: str, seed: int) -> str:  # type: ignore[no-untyped-def]
    run = simulation_run_service.create_run(
        session,
        SimulationRunCreate(
            scenario_id=scenario_id,
            seed=seed,
            start_time=CANONICAL_START_TIME,
            playback_speed=CANONICAL_PLAYBACK_SPEED,
        ),
    )
    return run.simulation_run_id


def test_apply_perturbation_is_deterministic(client: TestClient) -> None:
    session = _session(client)
    try:
        run_id = _ensure_run(session, "leaked-api-credential", 7)
        params: dict[str, object] = {"hidden_fraction": 0.3}
        first = apply_perturbation(session, run_id, PARTIAL_OBSERVABILITY_PERTURBATION_ID, params)
        second = apply_perturbation(session, run_id, PARTIAL_OBSERVABILITY_PERTURBATION_ID, params)
        assert first == second
        assert len(first) > 0, "the leaked-api-credential scenario has non-critical events to hide"
    finally:
        session.close()


def test_apply_perturbation_never_hides_a_ground_truth_event(client: TestClient) -> None:
    session = _session(client)
    try:
        run_id = _ensure_run(session, "leaked-api-credential", 7)
        hidden = apply_perturbation(
            session, run_id, PARTIAL_OBSERVABILITY_PERTURBATION_ID, {"hidden_fraction": 0.9}
        )
        assert len(hidden) > 0

        ground_truth_values = {severity.value for severity in GROUND_TRUTH_SEVERITIES}
        rows = session.execute(
            TelemetryEventRecord.__table__.select().where(
                TelemetryEventRecord.simulation_run_id == run_id
            )
        ).all()
        severity_by_id = {row.event_id: row.severity for row in rows}
        for event_id in hidden:
            severity = severity_by_id[event_id]
            assert severity not in ground_truth_values, (
                f"event {event_id} has severity {severity!r} and must never be hidden"
            )
    finally:
        session.close()


def test_apply_perturbation_with_no_perturbation_id_hides_nothing(client: TestClient) -> None:
    session = _session(client)
    try:
        run_id = _ensure_run(session, "leaked-api-credential", 7)
        assert apply_perturbation(session, run_id, None, None) == frozenset()
        assert (
            apply_perturbation(session, run_id, "some-unrecognised-id", {"hidden_fraction": 0.5})
            == frozenset()
        )
    finally:
        session.close()


def test_perturbed_experiment_detects_no_more_than_baseline(client: TestClient) -> None:
    """Hiding non-critical evidence can only reduce or maintain detection,
    never improve it - assert the real relationship on real computed data
    for the SAME scenario/seed/mode."""

    session = _session(client)
    try:
        baseline = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="leaked-api-credential",
                seed=7,
                defence_mode=DefenceMode.RULE_BASED,
                label="baseline",
            ),
        )
        assert baseline.status == ExperimentStatus.COMPLETED.value
        baseline_metrics, _ = evaluate_experiment(session, baseline.experiment_id)

        perturbed = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="leaked-api-credential",
                seed=7,
                defence_mode=DefenceMode.RULE_BASED,
                label="perturbed",
                perturbation_id=PARTIAL_OBSERVABILITY_PERTURBATION_ID,
                perturbation_params={"hidden_fraction": 0.5},
            ),
        )
        assert perturbed.status == ExperimentStatus.COMPLETED.value
        perturbed_metrics, _ = evaluate_experiment(session, perturbed.experiment_id)

        # Same shared deterministic run/model - a genuine paired comparison.
        assert baseline.run_id == perturbed.run_id
        assert baseline.detection_model_id == perturbed.detection_model_id

        hidden_count = perturbed.configuration_json.get("hidden_event_count")
        assert isinstance(hidden_count, int) and hidden_count > 0

        baseline_detected = baseline_metrics.raw_metrics_json["detected_attack_steps"]
        perturbed_detected = perturbed_metrics.raw_metrics_json["detected_attack_steps"]
        assert isinstance(baseline_detected, int) and isinstance(perturbed_detected, int)
        assert perturbed_detected <= baseline_detected

        baseline_coverage = baseline_metrics.raw_metrics_json["detection_coverage"]
        perturbed_coverage = perturbed_metrics.raw_metrics_json["detection_coverage"]
        if isinstance(baseline_coverage, (int, float)) and isinstance(
            perturbed_coverage, (int, float)
        ):
            assert perturbed_coverage <= baseline_coverage
    finally:
        session.close()


def test_full_pre_existing_suite_is_unaffected_by_an_unperturbed_experiment(
    client: TestClient,
) -> None:
    """A sanity check that an experiment with no perturbation_id produces
    configuration_json with an empty hidden_event set, exercising the exact
    default path every pre-existing (Phase 0-4 / Stage 1-9) experiment and
    test takes."""

    session = _session(client)
    try:
        experiment = experiment_service.create_and_run(
            session,
            ExperimentCreate(
                scenario_id="leaked-api-credential",
                seed=7,
                defence_mode=DefenceMode.NO_ACTIVE_DEFENCE,
            ),
        )
        assert experiment.status == ExperimentStatus.COMPLETED.value
        assert experiment.configuration_json.get("hidden_event_ids") == []
        assert experiment.configuration_json.get("hidden_event_count") == 0
    finally:
        session.close()
