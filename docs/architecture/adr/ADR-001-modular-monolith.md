# ADR-001: Modular Event-Driven Monolith (not microservices)

## Status
Accepted — Phase 1.

## Context

AegisArena's backend already had clear domain-oriented service modules
(telemetry, detection, correlation/incident, prediction, topology,
response/orchestration) before Phase 1, all deployed as a single FastAPI
process sharing one SQLite database. Phase 1 was asked to establish "clear
internal domain boundaries so selected domains can later be extracted if
justified" while explicitly not creating unnecessary microservices.

## Decision

Keep AegisArena as a single deployable FastAPI application organized into
domain modules (documented in `docs/architecture/BACKEND_DOMAINS.md`),
communicating via direct calls for synchronous request/response needs and
via a new canonical domain-event bus (`docs/architecture/EVENT_MODEL.md`)
for the "something happened, who else cares" concern.

## Alternatives considered

1. **Split into microservices now** (e.g. a separate Detection service,
   a separate Orchestration service). Rejected: there is exactly one
   deployment target (a local Windows demo / judge environment, per
   `docs/PHASE_0_BASELINE.md`), one database, one team, and no observed
   need for independent scaling or independent deployment cadence between
   domains. Splitting now would introduce network calls, partial-failure
   handling, and distributed-transaction problems (e.g. correlation and
   response both need detection's assessments in the same logical
   transaction as their own writes) purely to satisfy an architectural
   ideal with no corresponding requirement.
2. **A single undifferentiated service layer with no domain boundaries**
   (the risk if Phase 1 did nothing). Rejected: the codebase already had
   real domain boundaries; doing nothing would have left them implicit and
   undocumented, and would not have delivered the observability (event
   log) or extension seam (event bus) Phase 1 was asked to add.
3. **Physically move every service file into `app/domains/<name>/`
   packages.** Considered and rejected for Phase 1 specifically — see
   `docs/architecture/BACKEND_DOMAINS.md`'s introduction for the full
   reasoning (high regression risk, `~35` modules and every importer
   touched, for a purely cosmetic reorganization of a codebase whose
   domain boundaries are already legible from file naming).

## Consequences

- Positive: Phase 1's event model and domain documentation give a
  concrete, testable definition of "which domain owns what" without
  touching working code, satisfying "preserve working behaviour while
  creating clear domain boundaries."
- Positive: the event bus abstraction (ADR-002) means a future extraction
  decision is a wiring change (swap the bus implementation), not a
  business-logic rewrite.
- Negative: domains still share one Python process and one database
  transaction scope; a bug in one domain's service can still affect
  request latency for another domain's endpoint in the same process. This
  is an accepted tradeoff at current scale.

## Future reconsideration trigger

Revisit this decision if: (a) Detection's compute profile (model
training/scoring) becomes heavy enough to need independent scaling or a
different runtime (e.g. GPU-backed), (b) multiple independent teams need
to deploy different domains on different cadences, or (c) the system moves
from a single-operator demo to a multi-tenant service with per-tenant
isolation requirements. Any of these would justify extracting exactly the
domain under pressure (most plausibly Detection) behind the existing
`EventBus` seam, not a wholesale microservices rewrite.
