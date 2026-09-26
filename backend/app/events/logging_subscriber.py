"""Default subscriber: structured logging for every published domain event.

Registered once at application startup (see ``app.main.create_app``) so
every event publication is observable without each service having to log
it individually.
"""

from __future__ import annotations

import logging
from typing import Any

from app.events.bus import EventBus
from app.events.envelope import DomainEvent
from app.events.types import EventType

logger = logging.getLogger("aegisarena.events")


def _log_event(event: DomainEvent[Any]) -> None:
    logger.info(
        "domain_event event_type=%s event_id=%s correlation_id=%s run_id=%s "
        "scenario_id=%s incident_id=%s resource_ids=%s",
        event.event_type,
        event.event_id,
        event.correlation_id,
        event.run_id,
        event.scenario_id,
        event.incident_id,
        event.resource_ids,
    )


def register_logging_subscriber(bus: EventBus) -> None:
    for event_type in EventType:
        bus.subscribe(event_type, _log_event)
