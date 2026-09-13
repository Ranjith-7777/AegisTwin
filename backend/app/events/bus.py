"""In-process event bus abstraction.

``EventBus`` is the seam between business logic and event delivery. The
only implementation shipped in Phase 1 is :class:`InProcessEventBus`, which
delivers events synchronously, in-memory, within the same process — this is
sufficient for the current single-process FastAPI deployment and for
deterministic tests.

Extension point for cloud deployment
-------------------------------------
Business logic depends only on the ``EventBus`` protocol (``publish`` /
``subscribe``), never on ``InProcessEventBus`` directly. A future
``AzureServiceBusEventBus`` (or any other durable/networked implementation)
can be substituted at application wiring time (see ``app.main.create_app``)
without changing a single call site in the services that publish or
consume domain events. That future implementation would still accept and
return the same ``DomainEvent`` envelopes defined in
``app.events.envelope``, so payload contracts, correlation IDs and typed
models carry over unchanged.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from app.events.envelope import DomainEvent
from app.events.types import EventType

logger = logging.getLogger(__name__)

EventHandler = Callable[[DomainEvent[Any]], None] | Callable[[DomainEvent[Any]], Awaitable[None]]


class EventBus(Protocol):
    """Publish/subscribe seam for canonical domain events."""

    def publish(self, event: DomainEvent[Any]) -> None:
        """Deliver ``event`` to every subscriber of its event type.

        A handler failure must never prevent other handlers from running,
        and must never raise back into the caller — see
        :class:`InProcessEventBus` for the concrete failure-isolation
        behaviour used in this phase.
        """
        ...

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register ``handler`` to be invoked for every event of ``event_type``."""
        ...


class InProcessEventBus:
    """Synchronous, in-memory :class:`EventBus` implementation.

    Handlers are invoked in subscription order. A handler may be a plain
    callable or an ``async def`` coroutine function; async handlers are run
    to completion via a dedicated event loop for the call (safe to use from
    the synchronous FastAPI route handlers this backend uses today, which
    execute off the main event loop in a worker thread).

    Failure isolation: if a handler raises, the exception is logged with the
    event's correlation/event IDs and swallowed so that (a) other
    subscribers still run and (b) the publishing code path is never broken
    by a misbehaving subscriber. Events are never silently dropped — every
    publish is logged at DEBUG, and every handler failure is logged at
    ERROR with the offending handler's name.
    """

    def __init__(self) -> None:
        self._subscribers: dict[EventType, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        self._subscribers[event_type].append(handler)

    def publish(self, event: DomainEvent[Any]) -> None:
        handlers = list(self._subscribers.get(event.event_type, ()))
        logger.debug(
            "Publishing event event_type=%s event_id=%s correlation_id=%s "
            "run_id=%s incident_id=%s subscriber_count=%d",
            event.event_type,
            event.event_id,
            event.correlation_id,
            event.run_id,
            event.incident_id,
            len(handlers),
        )
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    asyncio.run(result)
            except Exception:
                logger.exception(
                    "Event handler failed handler=%s event_type=%s event_id=%s correlation_id=%s",
                    getattr(handler, "__qualname__", repr(handler)),
                    event.event_type,
                    event.event_id,
                    event.correlation_id,
                )

    def subscriber_count(self, event_type: EventType) -> int:
        return len(self._subscribers.get(event_type, ()))
