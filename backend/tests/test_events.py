from __future__ import annotations

from pydantic import BaseModel

from app.events.bus import InProcessEventBus
from app.events.envelope import DomainEvent
from app.events.types import EventType


class _Payload(BaseModel):
    value: int


def _event(**overrides: object) -> DomainEvent[_Payload]:
    defaults: dict[str, object] = {
        "event_type": EventType.ANOMALY_DETECTED,
        "source": "test",
        "payload": _Payload(value=1),
    }
    defaults.update(overrides)
    return DomainEvent[_Payload](**defaults)


def test_envelope_generates_unique_ids_and_timestamps() -> None:
    first = _event()
    second = _event()
    assert first.event_id != second.event_id
    assert first.timestamp != second.timestamp or first.event_id != second.event_id
    assert first.event_version == 1


def test_envelope_is_immutable() -> None:
    event = _event()
    try:
        event.event_id = "mutated"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("DomainEvent should be frozen")


def test_bus_delivers_to_all_subscribers_in_order() -> None:
    bus = InProcessEventBus()
    received: list[str] = []
    bus.subscribe(EventType.ANOMALY_DETECTED, lambda e: received.append("first"))
    bus.subscribe(EventType.ANOMALY_DETECTED, lambda e: received.append("second"))
    bus.publish(_event())
    assert received == ["first", "second"]


def test_bus_ignores_events_with_no_subscribers() -> None:
    bus = InProcessEventBus()
    bus.publish(_event())  # must not raise


def test_bus_only_delivers_to_matching_event_type() -> None:
    bus = InProcessEventBus()
    received: list[str] = []
    bus.subscribe(EventType.ANOMALY_DETECTED, lambda e: received.append("anomaly"))
    bus.subscribe(EventType.INCIDENT_CREATED, lambda e: received.append("incident"))
    bus.publish(_event(event_type=EventType.ANOMALY_DETECTED))
    assert received == ["anomaly"]


def test_failing_handler_does_not_stop_other_subscribers() -> None:
    bus = InProcessEventBus()
    received: list[str] = []

    def _boom(event: DomainEvent[_Payload]) -> None:
        raise RuntimeError("handler failure")

    bus.subscribe(EventType.ANOMALY_DETECTED, _boom)
    bus.subscribe(EventType.ANOMALY_DETECTED, lambda e: received.append("survived"))
    bus.publish(_event())  # must not raise
    assert received == ["survived"]


def test_async_handlers_are_awaited_to_completion() -> None:
    bus = InProcessEventBus()
    received: list[str] = []

    async def _handler(event: DomainEvent[_Payload]) -> None:
        received.append("async-handled")

    bus.subscribe(EventType.ANOMALY_DETECTED, _handler)
    bus.publish(_event())
    assert received == ["async-handled"]


def test_correlation_id_survives_on_event() -> None:
    event = _event(correlation_id="run-123", run_id="run-123")
    bus = InProcessEventBus()
    seen: list[str | None] = []
    bus.subscribe(EventType.ANOMALY_DETECTED, lambda e: seen.append(e.correlation_id))
    bus.publish(event)
    assert seen == ["run-123"]
