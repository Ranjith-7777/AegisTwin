# ADR-015: Azure Database for PostgreSQL (Flexible Server) as the Production Database

## Status
Accepted.

## Context

AegisArena has used SQLite since Phase 1 (ADR-003) for local development and
tests, accessed entirely through SQLAlchemy with an env-driven
`DATABASE_URL` (`backend/app/core/config.py`). `docs/DEPLOYMENT_REQUIREMENTS.md`
already notes that SQLite deployments are constrained to a single
application worker (the artifact cache and WebSocket connection manager are
process-local regardless of database choice), which Phase 6's
`maxReplicas=1` Container App satisfies — but SQLite as a *production*
database on Azure Container Apps has its own problem independent of worker
count: Container Apps' filesystem is ephemeral/local to a replica, so a
SQLite file would not reliably survive a redeploy, a scale-to-zero-and-back
cycle in every configuration, or provide a real backup/restore story.

## Decision

Use **Azure Database for PostgreSQL — Flexible Server** (Burstable B1ms
compute tier, no high-availability standby) as the production database,
provisioned by `infra/azure/main.bicep`, with the connection string stored
in Key Vault and injected into the Container App via a native secret
reference (see `docs/security/SECRETS_AND_IDENTITY.md`). SQLite remains the
database for local development and the test suite — unchanged.

Because the application already depends on SQLAlchemy and reads
`DATABASE_URL` from configuration rather than hardcoding a database engine,
this is a **drop-in environment change**: pointing `DATABASE_URL` at the
Postgres Flexible Server connection string is sufficient. No ORM model
changes, no query rewrites, and no application code changes were required
to support this.

## Alternatives considered

1. **Keep SQLite in production, on a persistent Azure Files-backed mount.**
   Rejected: adds an extra Azure resource (storage account + file share)
   and mount complexity to work around a problem (durable, backed-up,
   concurrent-safe storage) that a managed database service solves more
   directly and with less operational surface area.
2. **Azure Cosmos DB or another non-relational store.** Rejected: would
   require an ORM/query-layer rewrite (the application is built on
   SQLAlchemy's relational model throughout its services), which is far
   more invasive than a `DATABASE_URL` change for no corresponding benefit
   at this project's scale.
3. **Azure Database for PostgreSQL Flexible Server, Burstable B1ms, no HA
   (chosen).** Matches the smallest viable relational-database tier to this
   workload's actual usage (a demo/evaluation project, not a
   production-SLA service), while giving SQLAlchemy a real
   managed-service target with backups and durability SQLite on ephemeral
   container storage cannot provide.

## Consequences

- Positive: no application code changes were needed — validated by the
  existing `DATABASE_URL`-driven configuration and SQLAlchemy abstraction
  already in place since ADR-003.
- Positive: managed backups/point-in-time restore are available from the
  Flexible Server service itself, which an ephemeral container filesystem
  never provided.
- Negative: Burstable B1ms with no HA means a single point of failure and
  bursty (not sustained) CPU credit-based performance — acceptable for this
  project's traffic profile but not appropriate to describe as
  production-SLA-grade if this were ever a real production service.
- Negative: introduces a new secret (the Postgres admin password) into the
  deployment pipeline, handled per `docs/security/SECRETS_AND_IDENTITY.md`.

## Future reconsideration trigger

Revisit the HA/tier choice if this project is ever used for anything beyond
demo/evaluation traffic with real availability expectations.
