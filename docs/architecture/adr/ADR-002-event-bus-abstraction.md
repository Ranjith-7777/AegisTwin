# ADR-002: EventBus Protocol with an In-Process Implementation

## Status
Accepted — Phase 1.

## Context

Phase 1 required a canonical domain event model and "an internal
abstraction roughly equivalent to `EventBus.publish(event)` /
`.subscribe(event_type, handler)`," explicitly forbidding Kafka, RabbitMQ,
Redis Streams, and Azure Service Bus at this stage, while requiring the
interface be designed so a future networked/durable implementation could
be added "without rewriting business logic."

## Decision

Define `EventBus` as a `typing.Protocol` (`app/events/bus.py`) with
exactly two methods, `publish(event: DomainEvent) -> None` and
`subscribe(event_type: EventType, handler) -> None`. Ship one
implementation, `InProcessEventBus`: synchronous, in-memory,
per-event-type subscriber lists, handler failures logged and isolated
(never propagate to the publisher), async handlers supported via
`asyncio.run(...)` at publish time. A process-wide registry
(`app/events/registry.py`) holds the active bus instance, following the
same singleton pattern this codebase already uses for
`app.core.config.get_settings()`.

## Alternatives considered

1. **A full message broker (Kafka/RabbitMQ/Redis Streams) now.** Rejected
   per explicit Phase 1 instruction, and also disproportionate: the system
   runs as one process today: there is nothing on the other end of a
   network hop yet.
2. **No abstraction — just call subscriber functions directly from each
   service.** Rejected: this is what the codebase already effectively did
   (services calling each other's methods directly), and would not have
   given a testable "publish once, N independent subscribers react"
   seam, nor the single place (the bus) where cross-cutting concerns like
   structured event logging can be added once for every event type.
3. **Thread the bus through every service's constructor / every FastAPI
   route's dependency injection.** Rejected for Phase 1: this codebase's
   services are module-level singletons instantiated at import time and
   called from synchronous route handlers, not built per-request via DI.
   Threading a bus parameter through every constructor and every one of
   the ~35 service modules' call sites would be a much larger, riskier
   change than the goal (publish a handful of events at existing
   transition points) justified. The registry-singleton approach achieves
   the same testability (via `use_event_bus()` context-manager
   substitution in tests) with a far smaller footprint.
4. **A fully async bus requiring `await bus.publish(...)` everywhere.**
   Rejected: every route handler in this codebase today is a synchronous
   `def`, executed in FastAPI's worker thread pool. Forcing an async-only
   publish API would have required converting route handlers to `async def`
   merely to support event publication — an unrelated, much larger
   change. `InProcessEventBus.publish` is synchronous and safe to call
   from these handlers; it still supports `async def` handlers internally
   for symmetry with a future networked implementation's natural async
   client.

## Consequences

- Positive: publishing an event is a two-line addition
  (`get_event_bus().publish(DomainEvent(...))`) at an existing commit
  point — no service needed restructuring to support it.
- Positive: `tests/test_events.py` can fully exercise bus semantics
  (ordering, multi-subscriber delivery, failure isolation, async handlers)
  without any FastAPI/database machinery.
- Negative: the process-wide registry is global mutable state. This is a
  deliberate, scoped tradeoff (see `app/events/registry.py`'s docstring)
  consistent with this codebase's existing `get_settings()` pattern; it is
  not a general license for more global state, and tests must use
  `use_event_bus()` to avoid cross-test leakage.
- Negative: events published via `InProcessEventBus` are lost if the
  process crashes between publish and a subscriber's completion — there is
  no persistence or redelivery. This is acceptable today because the only
  subscriber (logging) has no correctness requirement on delivery, and no
  subscriber currently drives external side effects that would need
  at-least-once guarantees.

## Cloud extension point

A future `AzureServiceBusEventBus` implementing the same `EventBus`
protocol could be installed via `app.events.registry.set_event_bus(...)`
at application startup, serializing `DomainEvent.model_dump_json()` as the
message body. No service that calls `get_event_bus().publish(...)` today
would need to change. See `docs/architecture/EVENT_MODEL.md`'s "Extension
point" section for the concrete mechanism.

## Future reconsideration trigger

Revisit if: a subscriber needs guaranteed delivery across process
restarts (e.g. a durable audit projector that must not miss events), a
domain is extracted into a separate deployable (ADR-001's trigger), or
event volume/handler cost grows enough that synchronous in-process
delivery measurably affects request latency.
