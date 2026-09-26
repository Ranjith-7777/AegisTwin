"""Unit/integration tests for Phase 5 Stage 4's aggregate statistics and
paired-comparison services.

`ComparisonService.check_fairness` is tested with plain, unpersisted
`ExperimentRecord`/`ExperimentMetricRecord` objects (it only reads
attributes, never queries the database) - fast and fully deterministic.
`AggregationService.aggregate` and `ComparisonService.compare_modes` need a
real session to query against, so those insert DETERMINISTIC,
hand-constructed `ExperimentRecord`/`ExperimentMetricRecord` rows directly
(never a full end-to-end experiment run) into the test database provided by
the `client` fixture, exactly like Stage 3's `test_resilience_score.py`
constructs its inputs directly.
"""

from __future__ import annotations

import statistics as pystatistics
from datetime import UTC, datetime
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database.models import ExperimentMetricRecord, ExperimentRecord
from app.services.evaluation.aggregation_service import AggregationService
from app.services.evaluation.comparison_service import ComparisonService

aggregation_service = AggregationService()
comparison_service = ComparisonService()


def _experiment(
    experiment_id: str,
    *,
    scenario_id: str = "leaked-api-credential",
    seed: int = 1,
    defence_mode: str = "agentic",
    topology_version: str = "topology-v1",
    status: str = "completed",
) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=experiment_id,
        scenario_id=scenario_id,
        scenario_name="Test Scenario",
        seed=seed,
        defence_mode=defence_mode,
        topology_version=topology_version,
        red_scenario_version="red-scenario-catalogue-v1",
        configuration_json={},
        status=status,
        changed_node_ids_json=[],
        changed_edge_ids_json=[],
        autonomous_action_count=0,
        manual_action_count=0,
        synthetic=True,
        created_at=datetime.now(UTC),
    )


def _metric_record(
    experiment_id: str,
    *,
    ars_total: float | None = None,
    mci: float | None = None,
    raw_metrics_json: dict[str, object] | None = None,
    normalized_metrics_json: dict[str, object] | None = None,
    metrics_version: str = "aegis-evaluation-metrics-v1",
    ars_version: str | None = "aegis-resilience-score-v1",
    mci_version: str | None = "aegis-mci-v1",
) -> ExperimentMetricRecord:
    return ExperimentMetricRecord(
        experiment_id=experiment_id,
        metrics_version=metrics_version,
        logical_timeline_json={},
        computation_latency_json={},
        raw_metrics_json=raw_metrics_json or {},
        normalized_metrics_json=normalized_metrics_json or {},
        computed_at=datetime.now(UTC),
        synthetic=True,
        ars_total=ars_total,
        mci=mci,
        ars_version=ars_version,
        mci_version=mci_version,
    )


def _session(client: TestClient):  # type: ignore[no-untyped-def]
    return cast(FastAPI, client.app).state.database.session_factory()


# ---------------------------------------------------------------------
# AggregationService: numeric summary statistics
# ---------------------------------------------------------------------


def test_mean_median_std_min_max_are_correct_for_a_known_sample(client: TestClient) -> None:
    # ars_total values 10.0, 20.0, 30.0:
    #   mean   = (10+20+30)/3 = 20.0
    #   median = 20.0
    #   pstdev = sqrt(((10-20)^2 + (20-20)^2 + (30-20)^2) / 3)
    #          = sqrt((100 + 0 + 100) / 3) = sqrt(66.666...) = 8.164966...
    #   min = 10.0, max = 30.0
    values = [10.0, 20.0, 30.0]
    session = _session(client)
    try:
        for index, value in enumerate(values):
            experiment_id = f"agg-exp-{index}"
            session.add(_experiment(experiment_id, seed=index))
            session.add(_metric_record(experiment_id, ars_total=value))
        session.commit()

        result = aggregation_service.aggregate(
            session, experiment_ids=[f"agg-exp-{i}" for i in range(len(values))]
        )
        summary = result.metric_summaries["ars_total"]
        assert summary.count == 3
        assert summary.n_applicable == 3
        assert summary.mean == 20.0
        assert summary.median == 20.0
        assert summary.std == round(pystatistics.pstdev(values), 6)
        assert summary.std == round(8.16496580927726, 6)
        assert summary.minimum == 10.0
        assert summary.maximum == 30.0
    finally:
        session.close()


def test_boolean_success_rate_excludes_na_from_denominator(client: TestClient) -> None:
    # verification_success = [True, False, None]: N/A (None) must be
    # excluded from the denominator entirely, not counted as a failure.
    # success_count=1, total_applicable=2 (True, False only), rate=0.5.
    outcomes: list[bool | None] = [True, False, None]
    session = _session(client)
    try:
        for index, outcome in enumerate(outcomes):
            experiment_id = f"bool-exp-{index}"
            session.add(_experiment(experiment_id, seed=100 + index))
            session.add(
                _metric_record(experiment_id, raw_metrics_json={"verification_success": outcome})
            )
        session.commit()

        result = aggregation_service.aggregate(
            session, experiment_ids=[f"bool-exp-{i}" for i in range(len(outcomes))]
        )
        summary = result.boolean_summaries["verification_success"]
        assert summary.total_applicable == 2
        assert summary.success_count == 1
        assert summary.success_rate == 0.5
    finally:
        session.close()


def test_failed_experiments_excluded_from_aggregation_by_default(client: TestClient) -> None:
    session = _session(client)
    try:
        session.add(_experiment("ok-exp", seed=1, status="completed"))
        session.add(_metric_record("ok-exp", ars_total=50.0))
        session.add(_experiment("bad-exp", seed=2, status="failed"))
        session.add(_metric_record("bad-exp", ars_total=999.0))
        session.commit()

        result = aggregation_service.aggregate(
            session, experiment_ids=["ok-exp", "bad-exp"], include_failed=False
        )
        assert result.experiment_count == 1
        assert result.metric_summaries["ars_total"].n_applicable == 1
        assert result.metric_summaries["ars_total"].mean == 50.0

        with_failed = aggregation_service.aggregate(
            session, experiment_ids=["ok-exp", "bad-exp"], include_failed=True
        )
        assert with_failed.experiment_count == 2
    finally:
        session.close()


# ---------------------------------------------------------------------
# ComparisonService.check_fairness
# ---------------------------------------------------------------------


def test_check_fairness_confirms_a_genuinely_matched_pair() -> None:
    experiment_a = _experiment("a", scenario_id="s", seed=7, topology_version="t1")
    experiment_b = _experiment("b", scenario_id="s", seed=7, topology_version="t1")
    metrics_a = _metric_record("a")
    metrics_b = _metric_record("b")

    result = comparison_service.check_fairness(experiment_a, experiment_b, metrics_a, metrics_b)
    assert result.paired is True
    assert result.reasons == []


def test_check_fairness_flags_different_seed() -> None:
    experiment_a = _experiment("a", scenario_id="s", seed=7, topology_version="t1")
    experiment_b = _experiment("b", scenario_id="s", seed=8, topology_version="t1")
    metrics_a = _metric_record("a")
    metrics_b = _metric_record("b")

    result = comparison_service.check_fairness(experiment_a, experiment_b, metrics_a, metrics_b)
    assert result.paired is False
    assert any("seed" in reason.lower() for reason in result.reasons)


def test_check_fairness_flags_different_scenario() -> None:
    experiment_a = _experiment("a", scenario_id="s1", seed=7, topology_version="t1")
    experiment_b = _experiment("b", scenario_id="s2", seed=7, topology_version="t1")
    metrics_a = _metric_record("a")
    metrics_b = _metric_record("b")

    result = comparison_service.check_fairness(experiment_a, experiment_b, metrics_a, metrics_b)
    assert result.paired is False
    assert any("scenario" in reason.lower() for reason in result.reasons)


def test_check_fairness_flags_different_topology_version() -> None:
    experiment_a = _experiment("a", scenario_id="s", seed=7, topology_version="t1")
    experiment_b = _experiment("b", scenario_id="s", seed=7, topology_version="t2")
    metrics_a = _metric_record("a")
    metrics_b = _metric_record("b")

    result = comparison_service.check_fairness(experiment_a, experiment_b, metrics_a, metrics_b)
    assert result.paired is False
    assert any("topology_version" in reason for reason in result.reasons)


def test_check_fairness_flags_mismatched_metrics_version() -> None:
    experiment_a = _experiment("a", scenario_id="s", seed=7, topology_version="t1")
    experiment_b = _experiment("b", scenario_id="s", seed=7, topology_version="t1")
    metrics_a = _metric_record("a", metrics_version="aegis-evaluation-metrics-v1")
    metrics_b = _metric_record("b", metrics_version="aegis-evaluation-metrics-v2")

    result = comparison_service.check_fairness(experiment_a, experiment_b, metrics_a, metrics_b)
    assert result.paired is False
    assert any("metrics_version" in reason for reason in result.reasons)


def test_check_fairness_flags_missing_metrics_as_unconfirmed() -> None:
    experiment_a = _experiment("a", scenario_id="s", seed=7, topology_version="t1")
    experiment_b = _experiment("b", scenario_id="s", seed=7, topology_version="t1")

    result = comparison_service.check_fairness(experiment_a, experiment_b, None, None)
    assert result.paired is False
    assert result.reasons


# ---------------------------------------------------------------------
# ComparisonService.compare_modes: paired delta arithmetic
# ---------------------------------------------------------------------


def test_paired_delta_arithmetic_is_correct(client: TestClient) -> None:
    # agentic ars_total=80.0, rule_based ars_total=60.0, no_active_defence=40.0.
    # Baseline is no_active_defence (present) so:
    #   ars_total delta (agentic - no_active_defence) = 80 - 40 = 40.0
    #   ars_total delta (rule_based - no_active_defence) = 60 - 40 = 20.0
    # Plus the explicit rule_based-vs-agentic pair: 80 - 60 = 20.0
    session = _session(client)
    try:
        for mode, value in (("no_active_defence", 40.0), ("rule_based", 60.0), ("agentic", 80.0)):
            experiment_id = f"cmp-{mode}"
            session.add(
                _experiment(
                    experiment_id,
                    scenario_id="leaked-api-credential",
                    seed=7,
                    defence_mode=mode,
                    topology_version="topology-v1",
                )
            )
            session.add(_metric_record(experiment_id, ars_total=value))
        session.commit()

        result = comparison_service.compare_modes(session, "leaked-api-credential", seed=7)
        assert result.baseline_mode == "no_active_defence"
        assert set(result.available_modes) == {"no_active_defence", "rule_based", "agentic"}
        assert "ml_assisted" in result.missing_modes

        deltas_by_pair = {
            (delta.reference_mode, delta.compared_mode, delta.metric): delta
            for delta in result.paired_deltas
        }
        baseline_agentic = deltas_by_pair[("no_active_defence", "agentic", "ars_total")]
        assert baseline_agentic.delta == 40.0
        assert baseline_agentic.paired is True

        baseline_rule = deltas_by_pair[("no_active_defence", "rule_based", "ars_total")]
        assert baseline_rule.delta == 20.0

        rule_vs_agentic = deltas_by_pair[("rule_based", "agentic", "ars_total")]
        assert rule_vs_agentic.delta == 20.0
        assert rule_vs_agentic.paired is True
    finally:
        session.close()


def test_compare_modes_reports_unpaired_delta_with_reasons(client: TestClient) -> None:
    session = _session(client)
    try:
        session.add(
            _experiment(
                "cmp-baseline",
                scenario_id="leaked-api-credential",
                seed=9,
                defence_mode="no_active_defence",
                topology_version="topology-v1",
            )
        )
        session.add(_metric_record("cmp-baseline", ars_total=10.0))
        session.add(
            _experiment(
                "cmp-agentic",
                scenario_id="leaked-api-credential",
                seed=9,
                defence_mode="agentic",
                topology_version="topology-v2",
            )
        )
        session.add(
            _metric_record(
                "cmp-agentic", ars_total=90.0, metrics_version="aegis-evaluation-metrics-v2"
            )
        )
        session.commit()

        result = comparison_service.compare_modes(session, "leaked-api-credential", seed=9)
        deltas_by_pair = {
            (delta.reference_mode, delta.compared_mode, delta.metric): delta
            for delta in result.paired_deltas
        }
        unpaired = deltas_by_pair[("no_active_defence", "agentic", "ars_total")]
        assert unpaired.delta == 80.0
        assert unpaired.paired is False
        assert unpaired.fairness_reasons
    finally:
        session.close()
