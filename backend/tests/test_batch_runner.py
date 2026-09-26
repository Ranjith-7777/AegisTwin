"""Integration tests for the Phase 5 Stage 4 batch runner
(`app.services.evaluation.batch_service.BatchService`).

These run REAL (small) experiment matrices end-to-end through
`experiment_service.create_and_run`/`evaluate_experiment` - unlike
`test_aggregation.py`'s hand-constructed fixtures - because the batch
runner's own job (sequencing, failure isolation, progress bookkeeping) is
only meaningfully exercised against the real pipeline. Matrices are kept
small (2-8 experiments) to stay fast.
"""

from __future__ import annotations

from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.models import ExperimentRecord
from app.schemas.evaluation import DefenceMode
from app.services.evaluation.batch_service import BatchService

batch_service = BatchService()


def _session(client: TestClient):  # type: ignore[no-untyped-def]
    return cast(FastAPI, client.app).state.database.session_factory()


def test_batch_creates_the_requested_experiment_matrix(client: TestClient) -> None:
    session = _session(client)
    try:
        batch = batch_service.create_batch(
            session,
            scenario_ids=["leaked-api-credential"],
            seeds=[7, 11],
            defence_modes=[DefenceMode.NO_ACTIVE_DEFENCE, DefenceMode.RULE_BASED],
        )
        assert batch.total_experiments == 4
        assert len(batch.experiment_ids_json) == 4
        assert len(set(batch.experiment_ids_json)) == 4, "no duplicate experiment ids"

        combos = set()
        for experiment_id in batch.experiment_ids_json:
            experiment = session.get(ExperimentRecord, experiment_id)
            assert experiment is not None
            combos.add((experiment.scenario_id, experiment.seed, experiment.defence_mode))
        assert combos == {
            ("leaked-api-credential", 7, "no_active_defence"),
            ("leaked-api-credential", 7, "rule_based"),
            ("leaked-api-credential", 11, "no_active_defence"),
            ("leaked-api-credential", 11, "rule_based"),
        }
    finally:
        session.close()


def test_max_experiments_truncates_and_is_documented_on_the_record(client: TestClient) -> None:
    session = _session(client)
    try:
        batch = batch_service.create_batch(
            session,
            scenario_ids=["leaked-api-credential"],
            seeds=[7, 11],
            defence_modes=[
                DefenceMode.NO_ACTIVE_DEFENCE,
                DefenceMode.RULE_BASED,
                DefenceMode.ML_ASSISTED,
                DefenceMode.AGENTIC,
            ],
            max_experiments=3,
        )
        # Full matrix would be 2 seeds x 4 modes = 8; capped to 3.
        assert batch.total_experiments == 3
        assert batch.truncated is True
        assert len(batch.experiment_ids_json) == 3

        # Stable documented order: scenario -> seed -> mode, so the first 3
        # combinations are seed=7 with the first 3 modes in
        # CANONICAL_DEFENCE_MODES-equivalent request order.
        combos = []
        for experiment_id in batch.experiment_ids_json:
            experiment = session.get(ExperimentRecord, experiment_id)
            assert experiment is not None
            combos.append((experiment.seed, experiment.defence_mode))
        assert combos == [
            (7, "no_active_defence"),
            (7, "rule_based"),
            (7, "ml_assisted"),
        ]
    finally:
        session.close()


def test_max_experiments_not_exceeding_matrix_is_not_flagged_truncated(
    client: TestClient,
) -> None:
    session = _session(client)
    try:
        batch = batch_service.create_batch(
            session,
            scenario_ids=["leaked-api-credential"],
            seeds=[7],
            defence_modes=[DefenceMode.NO_ACTIVE_DEFENCE],
            max_experiments=5,
        )
        assert batch.total_experiments == 1
        assert batch.truncated is False
    finally:
        session.close()


def test_progress_and_status_fields_are_correct_for_an_all_success_batch(
    client: TestClient,
) -> None:
    session = _session(client)
    try:
        batch = batch_service.create_batch(
            session,
            scenario_ids=["leaked-api-credential"],
            seeds=[7],
            defence_modes=[DefenceMode.NO_ACTIVE_DEFENCE, DefenceMode.RULE_BASED],
        )
        assert batch.completed_count == 2
        assert batch.failed_count == 0
        assert batch.status == "completed"
        assert batch.started_at is not None
        assert batch.ended_at is not None
        assert batch.runtime_seconds is not None
        assert batch.runtime_seconds >= 0.0
    finally:
        session.close()


def test_individual_experiment_failure_does_not_abort_the_rest_of_the_batch(
    client: TestClient,
) -> None:
    """Mixes one unsupported scenario_id (guaranteed to fail before an
    ExperimentRecord can even be created - see
    `scenario_service.get_scenario`) into an otherwise-valid matrix and
    confirms the rest of the batch still reaches `completed` with real
    persisted metrics."""

    from app.services.evaluation.metrics_service import evaluation_metrics_service

    session = _session(client)
    try:
        batch = batch_service.create_batch(
            session,
            scenario_ids=["no-such-scenario", "leaked-api-credential"],
            seeds=[7],
            defence_modes=[DefenceMode.NO_ACTIVE_DEFENCE],
        )
        assert batch.total_experiments == 2
        assert batch.failed_count == 1
        assert batch.completed_count == 1
        assert batch.status == "completed_with_failures"
        # Only the successful experiment ever got an ExperimentRecord.
        assert len(batch.experiment_ids_json) == 1

        surviving_experiment = session.get(ExperimentRecord, batch.experiment_ids_json[0])
        assert surviving_experiment is not None
        assert surviving_experiment.scenario_id == "leaked-api-credential"
        assert surviving_experiment.status == "completed"

        metrics = evaluation_metrics_service.get(session, surviving_experiment.experiment_id)
        assert metrics is not None
        assert metrics.ars_total is not None
    finally:
        session.close()


def test_rerunning_the_same_matrix_produces_new_batch_and_experiment_ids(
    client: TestClient,
) -> None:
    session = _session(client)
    try:
        kwargs = {
            "scenario_ids": ["leaked-api-credential"],
            "seeds": [7],
            "defence_modes": [DefenceMode.NO_ACTIVE_DEFENCE],
        }
        first = batch_service.create_batch(session, **kwargs)  # type: ignore[arg-type]
        second = batch_service.create_batch(session, **kwargs)  # type: ignore[arg-type]

        assert first.batch_id != second.batch_id
        assert set(first.experiment_ids_json).isdisjoint(set(second.experiment_ids_json))
    finally:
        session.close()


def test_get_and_list(client: TestClient) -> None:
    session = _session(client)
    try:
        batch = batch_service.create_batch(
            session,
            scenario_ids=["leaked-api-credential"],
            seeds=[7],
            defence_modes=[DefenceMode.NO_ACTIVE_DEFENCE],
        )
        fetched = batch_service.get(session, batch.batch_id)
        assert fetched.batch_id == batch.batch_id

        listed = batch_service.list(session)
        assert any(item.batch_id == batch.batch_id for item in listed)
    finally:
        session.close()
