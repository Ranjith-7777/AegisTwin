from fastapi.testclient import TestClient


def test_default_autonomy_mode_is_recommend(client: TestClient) -> None:
    config = client.get("/api/v1/autonomy").json()
    assert config["mode"] == "recommend"
    assert config["updated_by"] == "system-default"


def test_raising_to_autonomous_requires_explicit_confirmation(client: TestClient) -> None:
    blocked = client.put(
        "/api/v1/autonomy",
        json={"mode": "autonomous", "updated_by": "analyst-1", "confirm": False},
    )
    assert blocked.status_code == 422
    assert client.get("/api/v1/autonomy").json()["mode"] == "recommend"

    confirmed = client.put(
        "/api/v1/autonomy",
        json={"mode": "autonomous", "updated_by": "analyst-1", "confirm": True},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["mode"] == "autonomous"


def test_non_autonomous_modes_never_require_confirmation(client: TestClient) -> None:
    for mode in ("observe", "recommend", "approval_required"):
        response = client.put(
            "/api/v1/autonomy",
            json={"mode": mode, "updated_by": "analyst-1", "confirm": False},
        )
        assert response.status_code == 200
        assert response.json()["mode"] == mode


def test_autonomy_mode_persists_across_requests(client: TestClient) -> None:
    client.put(
        "/api/v1/autonomy",
        json={"mode": "approval_required", "updated_by": "analyst-1", "confirm": False},
    )
    reloaded = client.get("/api/v1/autonomy").json()
    assert reloaded["mode"] == "approval_required"
    assert reloaded["updated_by"] == "analyst-1"


def test_every_mode_has_a_distinct_human_readable_description(client: TestClient) -> None:
    descriptions = set()
    for mode in ("observe", "recommend", "approval_required", "autonomous"):
        response = client.put(
            "/api/v1/autonomy",
            json={"mode": mode, "updated_by": "analyst-1", "confirm": True},
        ).json()
        descriptions.add(response["description"])
    assert len(descriptions) == 4
