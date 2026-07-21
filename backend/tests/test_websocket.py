from fastapi.testclient import TestClient


def test_websocket_acknowledgement_and_ping(client: TestClient) -> None:
    with client.websocket_connect("/ws/events") as websocket:
        acknowledgement = websocket.receive_json()
        assert acknowledgement["type"] == "connection.ack"
        assert acknowledgement["payload"]["connected"] is True
        assert acknowledgement["payload"]["simulation_only"] is True
        assert acknowledgement["payload"]["connection_id"]

        websocket.send_json({"type": "ping"})
        assert websocket.receive_json() == {
            "type": "pong",
            "payload": {"simulation_only": True},
        }


def test_websocket_rejects_unsupported_message(client: TestClient) -> None:
    with client.websocket_connect("/ws/events") as websocket:
        websocket.receive_json()
        websocket.send_json({"type": "subscribe"})
        response = websocket.receive_json()
        assert response["type"] == "error"
        assert response["payload"]["error_code"] == "UNSUPPORTED_MESSAGE"


def test_websocket_handles_malformed_json(client: TestClient) -> None:
    with client.websocket_connect("/ws/events") as websocket:
        websocket.receive_json()
        websocket.send_text("{invalid")
        response = websocket.receive_json()
        assert response["type"] == "error"
        assert response["payload"]["error_code"] == "MALFORMED_JSON"
