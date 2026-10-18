"""Regression: replaying a deterministic run restores a *consistent* workflow.

Runs are deterministic (same scenario/seed/start/speed -> same run id), so a
second replay of the same scenario reuses a run that already carries a ranked
comparison and an orchestration. The UI used to restore only the
orchestration, which produced impossible lifecycles (execution "completed"
while the decision stage was still "waiting") and an empty candidate list.
`GET /api/v1/workflow/runs/{run_id}/state` restores both from persisted
records, without re-planning or re-executing anything.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from httpx import Response

from tests.test_blue_planning import prepare
from tests.test_workflow_coordinator import run_workflow


def _state(client: TestClient, run_id: str, model_id: str) -> Response:
    response: Response = client.get(
        f"/api/v1/workflow/runs/{run_id}/state", params={"model_id": model_id}
    )
    return response


def test_state_is_404_before_any_workflow_has_run(client: TestClient) -> None:
    run_id, model_id, _ = prepare(client)
    response = _state(client, run_id, model_id)
    assert response.status_code == 404
    assert response.json()["error_code"] == "WORKFLOW_STATE_NOT_FOUND"


def test_recommend_mode_state_restores_the_ranked_comparison(client: TestClient) -> None:
    run_id, model_id, candidate_id = prepare(client)
    produced = run_workflow(client, run_id, model_id, candidate_id)
    restored = _state(client, run_id, model_id).json()
    assert restored["restored"] is True
    assert restored["orchestration"] is None
    assert restored["comparison"]["candidates"] == produced["comparison"]["candidates"]
    assert (
        restored["comparison"]["recommended_recommendation_id"]
        == produced["comparison"]["recommended_recommendation_id"]
    )


def test_autonomous_state_restores_comparison_and_execution_together(
    client: TestClient,
) -> None:
    run_id, model_id, candidate_id = prepare(client)
    client.put(
        "/api/v1/autonomy",
        json={"mode": "autonomous", "updated_by": "test", "confirm": True},
    )
    produced = run_workflow(client, run_id, model_id, candidate_id)
    assert produced["orchestration"] is not None

    # A second replay of the identical deterministic scenario reuses the run.
    restored = _state(client, run_id, model_id).json()
    orchestration = restored["orchestration"]
    comparison = restored["comparison"]
    assert orchestration["orchestration_id"] == produced["orchestration"]["orchestration_id"]
    assert orchestration["current_state"] == produced["orchestration"]["current_state"]
    # Consistency: the executed plan is the plan the restored comparison selected,
    # and the comparison was made at the same evidence horizon.
    assert comparison is not None and len(comparison["candidates"]) > 0
    assert (
        orchestration["selected_recommendation_id"] == (comparison["recommended_recommendation_id"])
    )
    assert comparison["through_sequence_number"] == orchestration["through_sequence_number"]
    assert restored["auto_executed"] == produced["auto_executed"]
    assert restored["auto_verified"] == produced["auto_verified"]


def test_restoring_state_never_creates_new_records(client: TestClient) -> None:
    run_id, model_id, candidate_id = prepare(client)
    run_workflow(client, run_id, model_id, candidate_id)
    before = client.get("/api/v1/orchestration").json()["items"]
    for _ in range(3):
        assert _state(client, run_id, model_id).status_code == 200
    after = client.get("/api/v1/orchestration").json()["items"]
    assert len(after) == len(before)
