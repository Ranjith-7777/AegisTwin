# ADR-003: Keep SQLite for Phase 1

## Status
Accepted — Phase 1.

## Context

Phase 1 explicitly instructed: "Keep SQLite for this phase. DO NOT migrate
to PostgreSQL yet," while asking for an audit of the schema and access
patterns for opportunities to improve consistency, transaction boundaries,
and idempotency.

## Decision

Retain SQLite (`sqlalchemy` + `alembic`, `DATABASE_URL=sqlite:///...`) as
the only datastore. No new migration was introduced (see
`docs/architecture/PERSISTENCE.md`). The existing per-request session
lifecycle (`app/database/session.py:Database.session` — commit on clean
exit, rollback on exception) remains the transaction boundary; the
existing deterministic-id idempotency pattern (documented in
`docs/architecture/PERSISTENCE.md`) remains the mechanism preventing
duplicate writes.

## Alternatives considered

1. **Migrate to PostgreSQL now**, anticipating future concurrent-write or
   cloud-deployment needs. Rejected per explicit Phase 1 instruction, and
   also premature: this is a single-operator local demo/evaluation range
   (`docs/PHASE_0_BASELINE.md`) with no concurrent-writer requirement
   SQLite cannot satisfy today, and no evidence of a SQLite-specific
   limitation (lock contention, missing feature) actually encountered.
2. **Introduce a full repository layer between services and SQLAlchemy
   now**, in anticipation of a future database swap. Rejected — see
   `docs/architecture/PERSISTENCE.md`'s "why no blanket repository layer"
   section: the existing per-domain service-owns-its-tables pattern
   already provides the isolation a repository layer would add, without
   the indirection cost, and introducing one now would be speculative
   generality with no current consumer.

## Consequences

- Positive: zero migration risk in Phase 1 — the 9 existing Alembic
  revisions remain the complete, valid migration history.
- Positive: the local one-click demo (`START_AEGISTWIN_DEMO.bat`) and its
  file-based SQLite database continue to work exactly as before Phase 1;
  this was verified in the Phase 1 end-to-end regression run (see the
  Phase 1 completion report).
- Negative: SQLite's single-writer model remains a real constraint if this
  system ever needs concurrent multi-operator writes; that constraint is
  accepted, not solved, in Phase 1.

## Future reconsideration trigger

Revisit when a genuine concurrent-write or cloud-managed-database need
appears — most plausibly triggered by a real (non-local-demo) Azure
deployment target being defined, at which point Azure Database for
PostgreSQL would be the natural target given the rest of the stack's
Azure-oriented cloud-extension points (see ADR-002). Until that trigger,
introducing PostgreSQL would add operational complexity (a server process,
connection pooling, migration-environment parity) with no corresponding
benefit for the current single-process local-demo deployment target.
