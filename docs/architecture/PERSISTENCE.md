# Persistence Architecture

## Phase 1 scope

**No schema change and no new Alembic migration were required in Phase 1.**
The 9 existing migrations (`20260721_0001` through `20260817_0009`) remain
valid and untouched; the latest is `20260817_0009_add_blue_agent_defense_score`.
The event model, health endpoints, and error-envelope `details` field are
all in-memory/API-layer additions with no persisted representation.

## Storage

SQLite via SQLAlchemy 2.x + Alembic, unchanged from Phase 0:
`DATABASE_URL=sqlite:///./aegistwin.db` (default) / `sqlite:////data/aegistwin.db`
(Docker). `app/database/session.py:Database` wraps the engine/sessionmaker;
`get_database_session` is the FastAPI dependency that yields one
transactional, request-scoped `Session` per request (commits on clean
exit, rolls back on exception — this transaction boundary was already
correct and is unchanged).

27 ORM tables (`app/database/models.py`) span every domain: scenario/run
identity, telemetry events, detection models/assessments/evaluations,
MITRE technique observations, incident candidates/evidence/snapshots,
prediction snapshots/hypotheses, response recommendations/playbooks,
orchestration records (decisions, approvals, executions, verifications,
rollbacks), and the append-only audit log.

## Access pattern: why no blanket repository layer was introduced

Phase 1 was asked to "prefer separation such as API → domain/use case →
repository → SQLAlchemy... focus on areas that currently have tightly
coupled direct DB access" and explicitly **not** to "create repository
classes for absolutely everything merely to satisfy a pattern."

Having audited every service in `app/services/`, the existing pattern is
already a reasonable middle ground for this codebase's size and team: each
service method is a self-contained use case (e.g.
`CorrelationService.analyze`) that both queries and writes through
SQLAlchemy directly, using the injected, request-scoped `Session`. This is
not "scattered" access in the sense the audit was checking for — access is
still centralized per domain (one service module per domain owns all
reads/writes for its own tables), transaction boundaries are still the
request-scoped session (a single commit per top-level use case), and there
is no evidence of two different services writing to the same table through
inconsistent paths. Introducing a repository interface on top of this
would add an indirection layer that forwards calls 1:1 to SQLAlchemy
without changing behavior or removing duplication — exactly the
"repository for its own sake" pattern Phase 1 was told to avoid.

**What Phase 1 did instead**: verified and documented (this file, and
`docs/architecture/DATA_FLOW.md`) that the existing deterministic-ID +
existence-check pattern already used throughout (see "Idempotency" below)
is the codebase's real persistence-consistency mechanism, and added tests
(`tests/test_correlation_identity.py`) that exercise it end-to-end through
the API rather than re-implementing it behind a new abstraction.

## Idempotency

Every write path that could plausibly receive a duplicate request already
computes a **deterministic id** from its logical inputs (`uuid5` of a
namespace + stable fields, e.g. `simulation_service.create_run`'s
`uuid5(RUN_NAMESPACE, f"{scenario_id}:{seed}:{start_time}:{speed}")`) and
checks for an existing row with that id before doing any work:

- `SimulationRunService.create_run` — duplicate run request returns the
  existing `SimulationRun` unchanged; no telemetry is regenerated, no
  `scenario.started` event is re-published (`test_duplicate_scenario_start_is_idempotent_and_does_not_republish`).
- `OrchestrationService.create` — duplicate creation request (same run,
  model, candidate, recommendation, sequence) returns the existing
  orchestration view; the agent chain does not re-run
  (`test_deterministic_agents_approval_execution_verification_and_rollback`
  asserts `repeated["orchestration_id"] == first["orchestration_id"]`).
- `OrchestrationService.execute` / `.verify` / `.rollback` — each checks
  for an existing `SyntheticExecutionRecord` / `ResponseVerificationRecord`
  / `RollbackRecord` for the orchestration before acting, and returns the
  existing view untouched if one is already present (same test file
  asserts a second `execute` call returns the identical `execution_id`).
- `DetectionScoringService.score_run` and `CorrelationService.analyze` —
  both check for existing assessments/candidates and short-circuit unless
  `force_rescore`/`force` is explicitly requested.

This pattern predates Phase 1 (it was already present in the Phase 0
baseline); Phase 1's contribution is (a) confirming it holds by adding
explicit tests that assert no duplicate event is published on a repeated
request, and (b) documenting it here as the project's standing idempotency
mechanism so future domains follow the same convention rather than
inventing a new one.

## Retries / failure semantics / timeouts

The orchestration lifecycle already models an explicit state machine on
`ResponseOrchestrationRecord.current_state`
(`planning → simulation_validation|policy_review → approved|rejected|awaiting_*_approval → synthetic_execution_completed|failed → verified|rollback_recommended → synthetic_rollback_completed`),
which is a domain-appropriate subset of the
`PENDING/RUNNING/SUCCEEDED/FAILED/CANCELLED/ROLLED_BACK` lifecycle Phase 1
was asked to consider — introducing a second, generic state enum on top of
this domain-specific one would create two sources of truth for the same
concept. No operation in this codebase performs a real network call or
long-running background work (every "execution" is a synthetic, in-process
mutation completing in milliseconds), so there is no transient-failure
class to retry against and no operation that can remain "running"
indefinitely — bounded retries and timeouts were evaluated and found to
have no current call site that needs them. This is documented here rather
than added speculatively; `docs/architecture/adr/ADR-003-sqlite-phase-1.md`
and `EVENT_MODEL.md`'s extension-point section describe where this would
change if response execution ever called a real external system.
