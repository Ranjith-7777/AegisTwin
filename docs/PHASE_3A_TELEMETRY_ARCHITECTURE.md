# Phase 3A Telemetry Architecture

Phase 3A introduces a deterministic, simulation-only telemetry domain. It preserves the existing health, system-status, safety, and WebSocket contracts and does not integrate telemetry into the frontend.

```text
Scenario Definition
        ↓
Deterministic Generator
        ↓
Telemetry Service
        ↓
SQLite Persistence
        ↓
REST API
```

## Responsibilities

- **Scenario definition service:** owns the two immutable typed scenario sequences and persists their definitions for provenance.
- **Infrastructure inventory service:** owns eight synthetic assets, documentation-range IP addresses, criticality, and relationships for later digital-twin use.
- **Deterministic generator:** uses only the supplied scenario, random seed, UTC start time, and step offsets. It performs no I/O and returns typed events.
- **Simulation run service:** derives an idempotent run identifier, persists the completed run and events transactionally, and retrieves run metadata.
- **Telemetry service:** maps persistence records into public schemas and applies stable ordering, filters, and pagination.
- **REST routes:** validate inputs, obtain a request-scoped database session, delegate to services, and use the existing structured error handlers.

## Determinism contract

The tuple `(scenario_id, seed, UTC start_time, playback_speed)` identifies a run. Repeating it returns the same persisted run and exact event sequence. Different seeds may change only permitted synthetic features such as failed-attempt counts, unseen-device suffixes, and transfer sizes. Event timestamps are the supplied start time plus fixed scenario offsets.

## Persistence

The additive Alembic migration creates `simulation_scenarios`, `simulation_runs`, and `telemetry_events`. It does not alter or delete existing tables. Events are ordered by timestamp and event ID. Scenario data and all event metadata are explicitly marked synthetic.

## Safety boundary

The generator is a pure local transformation. It cannot execute commands, scan or connect to networks, access credentials, generate malware, contact external systems, or perform containment. All IP addresses are from RFC documentation ranges, all identities are synthetic, and the large-transfer destination is a simulation sink. Suspicious-looking events are not anomaly scores or confirmed attack verdicts.
