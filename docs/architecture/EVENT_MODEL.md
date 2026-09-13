# Canonical Domain Event Model

## The envelope

Every domain event is a `DomainEvent[TPayload]` (Pydantic generic model,
`app/events/envelope.py`), frozen (immutable) once constructed:

```python
class DomainEvent(BaseModel, Generic[TPayload]):
    event_id: str            # uuid4, auto-generated
    event_type: EventType    # e.g. EventType.ANOMALY_DETECTED
    event_version: int = 1
    timestamp: datetime      # UTC, auto-generated
    source: str              # publishing domain, e.g. "detection"
    run_id: str | None
    scenario_id: str | None
    incident_id: str | None
    correlation_id: str | None
    causation_id: str | None
    resource_ids: list[str] = []
    payload: TPayload         # typed per event type, see below
```

`TPayload` is bound to `pydantic.BaseModel`, so every event type gets its
own concrete, typed payload model instead of a bare `dict[str, Any]` —
e.g. `AnomalyDetectedPayload(run_id, model_id, assessment_count,
anomalous_count)`, `IncidentCreatedPayload(incident_candidate_id, run_id,
model_id, priority, evidence_count, technique_ids)`. See
`app/events/envelope.py` for the full set of payload models actually used.

## Event types

`app/events/types.py` defines `EventType`, a `StrEnum` covering the full
vocabulary agreed for the canonical event model (`scenario.started`,
`telemetry.generated`, `anomaly.detected`, `incident.created`,
`incident.updated`, `incident.contained`, `mitre.observation.created`,
`prediction.generated`, `response.proposed/approved/rejected`,
`response.execution.started`, `response.executed/failed`,
`resource.state.changed`, `verification.completed`,
`rollback.started/completed`, plus `attack.started` /
`attack.step.executed` / `telemetry.received` reserved for later use).

Each member is annotated `# published` in the source if this codebase
actually publishes it today. The rest are reserved names, not
implemented features — reserving a name is not a claim that the
corresponding capability exists yet (e.g. `incident.contained` is not
published anywhere; there is no containment feature in Phase 1).

## What is actually published today

| Event type | Publisher | When |
|---|---|---|
| `scenario.started` | `simulation_service.create_run` | A new (not previously seen) run is created |
| `telemetry.generated` | `simulation_service.create_run` | Same moment, once, summarizing event count |
| `anomaly.detected` | `detection_scoring_service.score_run` | A run is freshly scored (not returning a cached count) |
| `incident.created` | `correlation_service.analyze` | A new incident candidate is persisted |
| `prediction.generated` | `prediction_service.analyze` | New prediction snapshots/hypotheses are persisted |
| `response.proposed` / `response.approved` / `response.rejected` | `orchestration_service.create` | Based on the deterministic agent chain's resulting state |
| `response.execution.started` | `orchestration_service.execute` | Immediately before the synthetic mutation is computed |
| `response.executed` / `response.failed` | `orchestration_service.execute` | After the synthetic mutation completes |
| `resource.state.changed` | `orchestration_service.execute` | Once per mutated node, only on success |
| `verification.completed` | `orchestration_service.verify` | After comparing declared vs. persisted mutation |
| `rollback.started` / `rollback.completed` | `orchestration_service.rollback` | Bracketing the rollback record's creation |

Deliberately **not** published in Phase 1: `mitre.observation.created`
(technique observations are a byproduct of correlation, already covered by
`incident.created`'s `technique_ids`; publishing one event per observation
would be excessive per-operation logging for no current subscriber),
`incident.updated`/`incident.contained` (no update/containment lifecycle
exists yet), `attack.*` (Red/Scenario has no per-step event hook — the
scenario is generated as a whole by `event_generator`, not stepped through
imperatively).

## Correlation and causation

Every published event sets `correlation_id` to the `run_id` (or, for
orchestration events, `record.simulation_run_id`) that the underlying
scenario run identifies with — see `docs/architecture/DATA_FLOW.md` for the
full identifier lineage. `causation_id` is defined on the envelope for
future use (e.g. a response event caused by a specific incident event) but
is not populated in Phase 1: nothing downstream consumes it yet, and
guessing at a causation chain without a consumer would be speculative.
`incident_id` is populated on every event from `incident.created` onward.

`tests/test_correlation_identity.py` proves, against a real running
FastAPI app, that: the same `run_id` appears as both `run_id` and
`correlation_id` on every event across scenario → telemetry → detection →
incident → prediction; the `incident_id` set by `incident.created`
reappears unchanged on the later `response.*` decision events; and a
duplicate scenario-start request does not re-publish `scenario.started`.

## The bus

`app/events/bus.py` defines the `EventBus` protocol (`publish`,
`subscribe`) and its Phase 1 implementation, `InProcessEventBus`:

- Handlers are invoked synchronously, in subscription order.
- A handler may be a plain function or an `async def`; async handlers are
  run to completion via `asyncio.run(...)` at publish time (safe because
  this backend's route handlers are synchronous `def`s executing in
  FastAPI's worker thread pool, off the main event loop).
- **Failure isolation**: if a handler raises, the exception is logged
  (`logger.exception`, including the failing handler's name and the
  event's `event_type`/`event_id`/`correlation_id`) and swallowed — one
  broken subscriber can never break another subscriber or the publishing
  code path. `tests/test_events.py::test_failing_handler_does_not_stop_other_subscribers`
  proves this.
- **No silent drops**: every `publish` call is logged at DEBUG with the
  subscriber count for that event type, so an event published to zero
  subscribers is still observable in logs, not silently discarded.
- A default logging subscriber (`app/events/logging_subscriber.py`) is
  registered for every `EventType` at application startup, so every
  published event produces one structured log line even with no other
  consumer configured.

### Where the bus instance lives

Domain services in this codebase are module-level singletons
(`simulation_run_service = SimulationRunService()`, etc.), constructed at
import time and called directly from synchronous route handlers — not
built per-request through FastAPI dependency injection. `app/events/registry.py`
holds one process-wide `EventBus` instance (the same singleton pattern this
codebase already uses for settings — `app.core.config.get_settings`, an
`lru_cache`-backed singleton). `app.main.create_app` fetches it, registers
the logging subscriber, and exposes it on `app.state.event_bus` for the
`/health/ready` check. Tests install an isolated bus via
`app.events.registry.use_event_bus(bus)` as a context manager.

## Extension point for a future cloud event bus

Business logic depends only on the `EventBus` protocol — `publish()` and
`subscribe()` — never on `InProcessEventBus` directly, and always
constructs and consumes `DomainEvent` envelopes, never bus-specific
message types. A future `AzureServiceBusEventBus` (or any other
durable/networked implementation) would:

1. Implement the same `EventBus` protocol.
2. Serialize `DomainEvent.model_dump_json()` as the message body (the
   envelope is already a stable, versioned, JSON-serializable contract).
3. Be installed once, at application wiring time
   (`app.events.registry.set_event_bus(...)` during `create_app`), with
   zero changes to any of the service call sites listed above.

This is the concrete mechanism referenced in
`docs/architecture/adr/ADR-002-event-bus-abstraction.md`.
