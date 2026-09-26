from fastapi.testclient import TestClient

from app.core.constants import SAFETY_MESSAGE


def test_safety_posture_is_explicit(client: TestClient) -> None:
    response = client.get("/api/safety")
    assert response.status_code == 200
    assert response.json() == {
        "simulation_only": True,
        "real_world_actions_enabled": False,
        "external_targets_allowed": False,
        "message": SAFETY_MESSAGE,
    }


def test_safety_never_enables_real_world_actions(client: TestClient) -> None:
    body = client.get("/api/safety").json()
    assert body["real_world_actions_enabled"] is False
    assert body["external_targets_allowed"] is False
