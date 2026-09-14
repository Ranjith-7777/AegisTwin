"""HTTP-level tests for the Phase 5 Stage 6 Evaluation API
(`app.api.routes.evaluation`).

Runs REAL experiments end-to-end through the API itself (not the service
layer directly) - matching `test_batch_runner.py`/`test_experiment_timeline
.py`'s style of exercising the genuine Phase 1-4 pipeline, but this time
through `client.post`/`client.get` so the route wiring, response models,
and error handling are actually exercised.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi.testclient import TestClient

SCENARIO = "leaked-api-credential"
SEED = 7


def _create_experiment(client: TestClient, defence_mode: str, seed: int = SEED) -> dict[str, Any]:
    response = client.post(
        "/api/v1/evaluation/experiments",
        json={"scenario_id": SCENARIO, "seed": seed, "defence_mode": defence_mode},
    )
    assert response.status_code == 200, response.text
    return cast("dict[str, Any]", response.json())


def test_create_experiment_for_each_defence_mode_returns_real_metrics(client: TestClient) -> None:
    for mode in ("no_active_defence", "rule_based", "ml_assisted", "agentic"):
        body = _create_experiment(client, mode)
        assert body["status"] == "completed", body.get("failure_message")
        assert body["defence_mode"] == mode
        metrics = body["metrics"]
        assert metrics is not None
        assert metrics["ars_total"] is not None
        assert body["mission_health_curve"], "expected a non-empty mission health curve"
        assert body["timeline"] is not None
        assert len(body["timeline"]["events"]) > 0

        if mode == "no_active_defence":
            raw = metrics["raw_metrics"]
            # no_active_defence never dispatches a response - these must be
            # honestly N/A, not fabricated. Its mission-health curve also
            # never moves off a single steady state, so MCI (an AUC over
            # elapsed logical time) is honestly None rather than a
            # fabricated number - see MissionContinuityService.compute_mci.
            assert raw.get("containment_success") is None
            assert raw.get("verification_success") is None
            assert body["orchestration_id"] is None
            assert body["verification_status"] is None
        else:
            assert metrics["mci"] is not None


def test_list_experiments_filters_by_scenario_defence_mode_and_status(client: TestClient) -> None:
    _create_experiment(client, "rule_based")
    _create_experiment(client, "agentic")

    by_scenario = client.get(
        "/api/v1/evaluation/experiments", params={"scenario_id": SCENARIO}
    ).json()
    assert len(by_scenario) >= 2
    assert all(item["scenario_id"] == SCENARIO for item in by_scenario)

    by_mode = client.get(
        "/api/v1/evaluation/experiments", params={"defence_mode": "agentic"}
    ).json()
    assert all(item["defence_mode"] == "agentic" for item in by_mode)
    assert len(by_mode) >= 1

    by_status = client.get("/api/v1/evaluation/experiments", params={"status": "completed"}).json()
    assert all(item["status"] == "completed" for item in by_status)


def test_get_experiment_detail_has_full_shape(client: TestClient) -> None:
    created = _create_experiment(client, "agentic")
    experiment_id = created["experiment_id"]

    response = client.get(f"/api/v1/evaluation/experiments/{experiment_id}")
    assert response.status_code == 200
    detail = response.json()
    assert detail["experiment_id"] == experiment_id
    assert detail["metrics"]["ars_pillars"]
    assert detail["metrics"]["ars_total"] is not None
    assert detail["metrics"]["mci"] is not None
    assert detail["mission_health_curve"]
    assert detail["timeline"]["events"]


def test_get_experiment_timeline_matches_stage_order(client: TestClient) -> None:
    created = _create_experiment(client, "agentic")
    experiment_id = created["experiment_id"]

    response = client.get(f"/api/v1/evaluation/experiments/{experiment_id}/timeline")
    assert response.status_code == 200
    body = response.json()
    assert body["experiment_id"] == experiment_id
    stages = [event["stage"] for event in body["events"]]
    assert stages == [
        "experiment_created",
        "red_scenario_started",
        "telemetry_generated",
        "detection",
        "incident_correlated",
        "attack_graph_evaluated",
        "blast_radius_evaluated",
        "response_selected",
        "what_if_planning",
        "policy_evaluated",
        "approval",
        "synthetic_execution",
        "verification",
        "rollback",
        "experiment_completed",
    ]


def test_rerun_experiment_creates_new_experiment_and_leaves_original_untouched(
    client: TestClient,
) -> None:
    original = _create_experiment(client, "rule_based", seed=11)
    original_id = original["experiment_id"]

    response = client.post(f"/api/v1/evaluation/experiments/{original_id}/rerun")
    assert response.status_code == 200, response.text
    rerun = response.json()

    assert rerun["experiment_id"] != original_id
    assert rerun["rerun_of_experiment_id"] == original_id
    assert rerun["scenario_id"] == original["scenario_id"]
    assert rerun["seed"] == original["seed"]
    assert rerun["defence_mode"] == original["defence_mode"]
    assert rerun["status"] == "completed"
    assert rerun["metrics"]["ars_total"] is not None

    refetched_original = client.get(f"/api/v1/evaluation/experiments/{original_id}").json()
    assert refetched_original["rerun_of_experiment_id"] is None


def test_batch_and_compare_and_aggregate(client: TestClient) -> None:
    batch_response = client.post(
        "/api/v1/evaluation/batches",
        json={
            "scenario_ids": [SCENARIO],
            "seeds": [21, 22],
            "defence_modes": ["no_active_defence", "rule_based", "ml_assisted", "agentic"],
        },
    )
    assert batch_response.status_code == 200, batch_response.text
    batch = batch_response.json()
    assert batch["total_experiments"] == 8
    assert len(batch["experiment_ids"]) == 8
    assert batch["status"] in {"completed", "completed_with_failures"}

    fetched_batch = client.get(f"/api/v1/evaluation/batches/{batch['batch_id']}").json()
    assert fetched_batch["experiment_ids"] == batch["experiment_ids"]

    listed_batches = client.get("/api/v1/evaluation/batches").json()
    assert any(item["batch_id"] == batch["batch_id"] for item in listed_batches)

    compare_response = client.get(
        "/api/v1/evaluation/compare", params={"scenario_id": SCENARIO, "seed": 21}
    )
    assert compare_response.status_code == 200
    comparison = compare_response.json()
    assert len(comparison["available_modes"]) == 4
    assert len(comparison["paired_deltas"]) > 0
    ars_row = next(row for row in comparison["rows"] if row["metric"] == "ars_total")
    assert all(cell["applicable"] for cell in ars_row["values"].values())

    aggregate_response = client.get(
        "/api/v1/evaluation/aggregate",
        params={"scenario_id": SCENARIO, "defence_mode": "agentic"},
    )
    assert aggregate_response.status_code == 200
    aggregate = aggregate_response.json()
    assert aggregate["experiment_count"] >= 2
    ars_summary = aggregate["metric_summaries"]["ars_total"]
    assert ars_summary["n_applicable"] >= 2
    assert ars_summary["mean"] is not None


def test_export_csv_has_documented_header_and_one_row_per_experiment(client: TestClient) -> None:
    created = _create_experiment(client, "agentic", seed=31)

    response = client.get(
        "/api/v1/evaluation/experiments/export.csv",
        params={"scenario_id": SCENARIO, "seed": 31},
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]

    lines = response.text.strip().splitlines()
    header = lines[0].split(",")
    assert header == [
        "experiment_id",
        "scenario_id",
        "seed",
        "defence_mode",
        "status",
        "run_id",
        "incident_candidate_id",
        "orchestration_id",
        "verification_status",
        "ars_total",
        "mci",
        "detection_coverage",
        "detection_timeliness",
        "attack_path_reduction",
        "blast_radius_reduction",
        "critical_exposure_reduction",
        "operational_disruption",
        "time_to_first_detection",
        "time_to_incident",
        "time_to_response",
        "time_to_containment",
        "time_to_verified_recovery",
        "containment_success",
        "verification_success",
        "rollback_required",
        "rollback_success",
        "metrics_version",
        "mci_version",
        "ars_version",
        "topology_version",
        "red_scenario_version",
        "created_at",
    ]
    data_rows = lines[1:]
    assert len(data_rows) == 1
    assert created["experiment_id"] in data_rows[0]


def test_export_json_returns_full_experiment_detail_with_provenance(client: TestClient) -> None:
    _create_experiment(client, "ml_assisted", seed=41)

    response = client.get(
        "/api/v1/evaluation/experiments/export.json",
        params={"scenario_id": SCENARIO, "seed": 41},
    )
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    entry = body[0]
    assert entry["metrics"]["metrics_version"]
    assert entry["metrics"]["ars_version"]
    assert entry["metrics"]["mci_version"]
    assert entry["topology_version"]
    assert entry["red_scenario_version"]


def test_experiment_report_has_executive_summary_and_reproduction_metadata(
    client: TestClient,
) -> None:
    created = _create_experiment(client, "agentic", seed=51)
    experiment_id = created["experiment_id"]

    response = client.get(f"/api/v1/evaluation/experiments/{experiment_id}/report")
    assert response.status_code == 200
    report = response.json()

    assert report["experiment_id"] == experiment_id
    summary = report["executive_summary"]
    assert isinstance(summary, str) and summary
    assert SCENARIO in summary or "leaked-api-credential" in report["configuration"]["scenario_id"]
    assert "agentic" in summary
    assert "Aegis Resilience Score" in summary

    reproduction = report["reproduction"]
    for key in (
        "experiment_id",
        "scenario_id",
        "seed",
        "defence_mode",
        "topology_version",
        "red_scenario_version",
        "metrics_version",
        "mci_version",
        "ars_version",
    ):
        assert key in reproduction

    assert report["limitations"]


def test_experiment_not_found_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/evaluation/experiments/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "EXPERIMENT_NOT_FOUND"


def test_batch_not_found_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/evaluation/batches/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "BATCH_NOT_FOUND"


def test_rerun_of_unknown_experiment_returns_404(client: TestClient) -> None:
    response = client.post("/api/v1/evaluation/experiments/does-not-exist/rerun")
    assert response.status_code == 404
