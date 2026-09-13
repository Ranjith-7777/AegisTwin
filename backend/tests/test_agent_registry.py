from fastapi.testclient import TestClient

from tests.test_orchestration import approve, create


def test_registry_has_exactly_seven_agents_split_one_red_six_blue(client: TestClient) -> None:
    registry = client.get("/api/v1/agents").json()
    assert registry["total_agents"] == 7
    assert registry["red_agent_count"] == 1
    assert registry["blue_agent_count"] == 6
    assert len(registry["agents"]) == 7
    red = [a for a in registry["agents"] if a["side"] == "red"]
    blue = [a for a in registry["agents"] if a["side"] == "blue"]
    assert len(red) == 1
    assert len(blue) == 6
    assert {a["agent_id"] for a in blue} == {
        "response_planner",
        "impact_simulation",
        "safety_governor",
        "approval_router",
        "synthetic_execution",
        "verification",
    }


def test_analytical_subsystems_are_never_counted_as_agents(client: TestClient) -> None:
    registry = client.get("/api/v1/agents").json()
    subsystem_ids = {s["subsystem_id"] for s in registry["analytical_subsystems"]}
    assert subsystem_ids == {
        "telemetry",
        "detection",
        "incident_correlation",
        "mitre_mapping",
        "attack_graph",
        "blast_radius",
        "prediction",
    }
    agent_ids = {a["agent_id"] for a in registry["agents"]}
    assert subsystem_ids.isdisjoint(agent_ids)
    assert registry["total_agents"] == 7


def test_registry_is_deterministic_across_calls(client: TestClient) -> None:
    first = client.get("/api/v1/agents").json()
    second = client.get("/api/v1/agents").json()
    assert first == second


def test_trace_reflects_a_real_orchestration_run_in_causal_order(client: TestClient) -> None:
    orchestration = approve(client, create(client))
    client.post(f"/api/v1/orchestration/{orchestration['orchestration_id']}/execute", json={})
    client.post(f"/api/v1/orchestration/{orchestration['orchestration_id']}/verify")
    trace = client.get(
        f"/api/v1/agents/orchestrations/{orchestration['orchestration_id']}/trace"
    ).json()
    assert [entry["sequence"] for entry in trace["entries"]] == list(
        range(1, len(trace["entries"]) + 1)
    )
    assert trace["entries"][0]["agent_id"] == "response_planner"
    assert trace["entries"][-1]["status"] == "reached"
    assert all(entry["decision"] for entry in trace["entries"])


def test_trace_for_unknown_orchestration_is_a_404_not_a_fabricated_trace(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/agents/orchestrations/does-not-exist/trace")
    assert response.status_code == 404
