"""Process-wide event bus registry.

Domain services in this codebase are module-level singletons instantiated
at import time (e.g. ``simulation_run_service = SimulationRunService()``)
and are called directly from synchronous route handlers, not constructed
per-request via FastAPI dependency injection. Threading an ``EventBus``
through every service constructor and every call site would touch a very
large surface area for Phase 1's stated goal ("preserve working behaviour
while creating clear domain boundaries").

Instead, this module holds a single process-wide bus, set once during
application startup (see ``app.main.create_app``) — the same pattern this
codebase already uses for settings (``app.core.config.get_settings``, an
``lru_cache``-backed singleton). Tests use :func:`use_event_bus` to install
an isolated bus for the duration of a test.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from app.events.bus import EventBus, InProcessEventBus

_bus: EventBus = InProcessEventBus()


def get_event_bus() -> EventBus:
    return _bus


def set_event_bus(bus: EventBus) -> None:
    global _bus
    _bus = bus


@contextmanager
def use_event_bus(bus: EventBus) -> Iterator[EventBus]:
    """Install ``bus`` as the process-wide bus for the duration of the block."""
    global _bus
    previous = _bus
    _bus = bus
    try:
        yield bus
    finally:
        _bus = previous
