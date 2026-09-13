# System Overview — AegisArena (Phase 1)

## What this document is

A factual description of the backend architecture as it exists after
Phase 1 (architecture/event-model foundation). It describes what was
**preserved** from the inherited Phase 0 baseline and what was **added**.
It does not describe unimplemented future phases.

## Architecture style: modular event-driven monolith

AegisArena's backend is a single deployable FastAPI application
(`backend/app/main.py:create_app`) organized into domain-oriented service
modules that communicate through two channels:

1. **Direct calls** — a route handler calls a domain service, which calls
   other domain services synchronously when it needs their data (e.g.
   `correlation_service.analyze` reads persisted anomaly assessments from
   `detection_scoring_service`'s output). This is unchanged from Phase 0 and
   remains the primary way data flows through a single request.
2. **Domain events** — a service publishes a canonical `DomainEvent` (see
   `docs/architecture/EVENT_MODEL.md`) after completing a meaningful state
   transition (a run started, an anomaly was scored, an incident was
   correlated, a response was executed). Any number of subscribers can react
   without the publisher knowing they exist. Phase 1 ships exactly one
   subscriber (structured logging); this is the seam a future WebSocket
   broadcaster or audit projector would attach to.

```mermaid
flowchart TB
    subgraph API["API Layer (FastAPI routes)"]
        R1[simulation]
        R2[detection]
        R3[correlation / mitre]
        R4[prediction]
        R5[response / orchestration]
        R6[topology]
        R7[health]
    end

    subgraph Bus["Event Backbone (InProcessEventBus)"]
        EB((publish / subscribe))
    end

    subgraph Domains["Domain Services"]
        Telemetry[Telemetry]
        Detection[Detection]
        Incident[Incident / MITRE]
        Prediction[Prediction]
        Twin[Digital Twin]
        Red[Red / Scenario]
        Blue[Blue / Response]
        Audit[Audit]
    end

    Persistence[(SQLite via SQLAlchemy)]

    R1 --> Red --> Telemetry
    R2 --> Detection
    R3 --> Incident
    R4 --> Prediction
    R5 --> Blue
    R6 --> Twin

    Telemetry -. publishes .-> EB
    Detection -. publishes .-> EB
    Incident -. publishes .-> EB
    Prediction -. publishes .-> EB
    Blue -. publishes .-> EB
    Twin -. resource.state.changed .-> EB
    EB -. subscribes .-> Audit

    Telemetry --> Persistence
    Detection --> Persistence
    Incident --> Persistence
    Prediction --> Persistence
    Twin --> Persistence
    Blue --> Persistence
    Audit --> Persistence
```

## Why a modular monolith, not microservices (yet)

See `docs/architecture/adr/ADR-001-modular-monolith.md` for the full
decision record. In short: the whole system today serves one purpose (a
single-operator local demonstration and evaluation range), runs as one
process on one machine, and every "service" shares one SQLite database and
one Python process's memory space. Splitting it into network services now
would add deployment complexity, network failure modes, and distributed
transaction problems with no corresponding benefit — there is no
independent scaling, ownership, or deployment-cadence need yet. What Phase 1
adds instead is the internal seam (canonical events + a bus abstraction)
that would let a genuinely independent domain (most plausibly Detection,
given its distinct ML/compute profile) be extracted later without
rewriting its business logic — see `docs/architecture/EVENT_MODEL.md`'s
"cloud extension point" section.

## What changed in Phase 1 vs. Phase 0

- Added: `app/events/` (canonical envelope, event types, in-process bus,
  logging subscriber, process-wide registry).
- Added: event publication calls in `simulation_service`,
  `detection_scoring_service`, `correlation_service`, `prediction_service`,
  and `orchestration_service`, at their existing natural transition points
  (no service was rewritten; each publish call was inserted immediately
  before/after an already-existing `session.commit()`/`session.flush()`).
- Added: `/health/live` and `/health/ready`.
- Added: `details` field on the structured error envelope (`ApiError`).
- Fixed: the 6 pre-existing mypy errors in `tests/test_orchestration.py`.
- Fixed: frontend Prettier/CRLF drift via `.gitattributes` (`eol=lf`).
- Fixed: 11 npm dependency vulnerabilities via safe, non-breaking updates.
- Not changed: the FastAPI app structure, the database schema (no new
  migration was required — see `docs/architecture/PERSISTENCE.md`), the
  ML/detection algorithm, the Red/Blue agent decision logic, or any
  frontend UI.

## Domains

See `docs/architecture/BACKEND_DOMAINS.md` for the full per-domain
responsibility, file, and dependency breakdown.
