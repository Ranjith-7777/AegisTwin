from uuid import UUID

from fastapi.testclient import TestClient

from app.core.constants import CORRELATION_HEADER


def test_unknown_route_returns_typed_error(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["error_code"] == "NOT_FOUND"
    assert body["message"] == "The requested resource was not found."
    assert body["correlation_id"] == response.headers[CORRELATION_HEADER]


def test_generated_correlation_id_is_uuid(client: TestClient) -> None:
    response = client.get("/api/safety")
    UUID(response.headers[CORRELATION_HEADER])


def test_correlation_header_is_present(client: TestClient) -> None:
    response = client.get("/api/health")
    assert CORRELATION_HEADER in response.headers


def test_valid_correlation_id_is_preserved(client: TestClient) -> None:
    correlation_id = "demo-request-123"
    response = client.get("/api/safety", headers={CORRELATION_HEADER: correlation_id})
    assert response.headers[CORRELATION_HEADER] == correlation_id


def test_invalid_correlation_id_is_replaced(client: TestClient) -> None:
    response = client.get("/api/safety", headers={CORRELATION_HEADER: "invalid id !!!"})
    replacement = response.headers[CORRELATION_HEADER]
    assert replacement != "invalid id !!!"
    UUID(replacement)
