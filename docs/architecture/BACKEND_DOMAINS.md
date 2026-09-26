# Backend Domain Boundaries

This document maps the conceptual domains required by Phase 1 onto the
codebase as it actually exists. AegisArena's `backend/app/services/`
directory was already organized by domain via file naming (a flat
directory with domain-prefixed filenames) rather than nested packages.
Phase 1 deliberately did **not** physically relocate these files into
`app/domains/<name>/` packages: the codebase is well-organized already
(each file has one clear responsibility, and cross-domain calls are
explicit imports, not hidden coupling), and a large-scale file move across
~35 service modules and every importer would carry substantial regression
risk for a purely cosmetic reorganization — contrary to Phase 1's explicit
goal of preserving working behaviour. Instead, this document is the
authoritative map of "which files constitute which domain," and the new
event model (`docs/architecture/EVENT_MODEL.md`) is the mechanism that
makes the boundaries observable at runtime, not just in documentation.

## Telemetry

**Responsibility**: generate/ingest scenario telemetry, normalize it into
the canonical `TelemetryEvent` schema, persist it, and mark the start of a
scenario run.

- `app/services/event_generator.py` — deterministic, seeded synthetic
  telemetry generation from a scenario definition.
- `app/services/simulation_service.py` — creates/looks up a
  `SimulationRunRecord`, persists its `TelemetryEventRecord`s, publishes
  `scenario.started` and `telemetry.generated`.
- `app/services/telemetry_service.py` — read access to persisted events.
- `app/schemas/telemetry.py`, `app/api/routes/telemetry.py`,
  `app/api/routes/simulation.py`.

**Depends on**: Red/Scenario (for the scenario definition being replayed).

## Detection

**Responsibility**: train/persist the Isolation-Forest-based hybrid
anomaly model, score telemetry against it, and expose detection results
and model metadata.

- `app/services/detection_dataset_service.py`,
  `feature_pipeline_service.py`, `score_calibration_service.py`,
  `detection_training_service.py` — dataset construction, feature
  extraction, calibration, and model training/persistence.
- `app/services/model_artifact_service.py` — joblib artifact load/cache.
- `app/services/detection_scoring_service.py` — scores a run's telemetry
  against a trained model; publishes `anomaly.detected`.
- `app/services/detection_evaluation_service.py`,
  `evaluation_truth_service.py` — offline evaluation against staged truth.
- `app/services/assessment_query_service.py` — filtered/paginated read
  access to persisted assessments.
- `app/schemas/detection.py`, `app/api/routes/detection.py`.

**Depends on**: Telemetry (input events), nothing downstream depends on
Detection's internals — only on its persisted `AnomalyAssessmentRecord`s.

## Incident (correlation + MITRE)

**Responsibility**: correlate anomalous/technique-mapped telemetry into an
incident candidate, maintain its lifecycle state and causal snapshots, and
map individual events to MITRE ATT&CK techniques.

- `app/services/correlation_service.py` — the correlation engine; creates
  `IncidentCandidateRecord`s and `IncidentCandidateSnapshotRecord`s;
  publishes `incident.created`.
- `app/services/mitre_catalogue_service.py` — the local, versioned
  technique/tactic catalogue.
- `app/schemas/correlation.py`, `app/api/routes/correlation.py`,
  `app/api/routes/mitre.py`.

**Depends on**: Telemetry, Detection (assessments must be complete before
correlation runs — enforced with `ASSESSMENTS_INCOMPLETE`).

## Prediction

**Responsibility**: generate next-stage attack-progression hypotheses from
an incident's evidence so far, without leaking future events.

- `app/services/prediction_service.py` — the causal hypothesis generator;
  publishes `prediction.generated`.
- `app/services/prediction_evaluation_service.py`, `prediction_truth_service.py`,
  `progression_catalogue_service.py`.
- `app/schemas/prediction.py`, `app/api/routes/prediction.py`.

**Depends on**: Incident (technique observations), Detection (assessments).

## Digital Twin

**Responsibility**: the synthetic cloud resource inventory, its
relationships, path/reachability queries, and the mutable state that
response execution changes.

- `app/services/topology_service.py` — the static synthetic asset/edge
  inventory (`NODE_DETAILS`, `TOPOLOGY_VERSION`).
- `app/services/topology_path_service.py` — path/reachability queries used
  by both the frontend topology view and the Blue/Response safety checks.
- `app/services/infrastructure_service.py` — asset lookups used by
  prediction/topology.
- `app/schemas/topology.py`, `app/api/routes/topology.py` (including
  `GET /topology/runs/{run_id}/state`, the endpoint that reconstructs a
  run's topology state from just its `run_id` — see
  `docs/architecture/DATA_FLOW.md`'s note on the Digital Twin run-context
  investigation).

**Depends on**: nothing upstream for its static inventory; reads
`SyntheticExecutionRecord`s (owned by Blue/Response) to know what has
mutated.

**Explicitly out of scope for Phase 1**: the Phase 3 attack-path/blast-radius
engine. `topology_path_service.py` answers "is there a path/edge between
X and Y" today; it does not compute blast radius or attack-path ranking.

## Red / Scenario

**Responsibility**: the fixed, scripted attack/normal scenario catalogue
that Telemetry replays.

- `app/services/scenario_service.py` — the `SCENARIOS` catalogue (6 fixed
  scenarios: normal operations, credential compromise, staged compromise
  demo, leaked API credential, suspicious Kubernetes pod, DDoS-like spike).
- `app/schemas/simulation.py` (scenario schemas), `app/api/routes/simulation.py`
  (`/scenarios` endpoints).

**Explicitly out of scope for Phase 1**: turning this into an adaptive
agent. It remains a deterministic, seeded script.

## Blue / Response

**Responsibility**: recommend, rank, orchestrate, execute, verify, and
roll back a synthetic response to an incident.

- `app/services/response_service.py`, `response_playbook_service.py` —
  recommendation ranking (Defense Score) and the fixed playbook catalogue.
- `app/services/orchestration_agents.py` — the deterministic
  `ResponsePlannerAgent` / `ImpactSimulationAgent` / `SafetyGovernorAgent` /
  `ApprovalRouterAgent` / `SyntheticExecutionAgent` / `VerificationAgent`
  chain (`AGENT_VERSION = "deterministic-simulation-agent-v1"`).
- `app/services/orchestration_service.py` — orchestration lifecycle
  (`create`/`decide_approval`/`execute`/`verify`/`rollback`/`audit`);
  publishes the full `response.*`, `resource.state.changed`,
  `verification.completed`, and `rollback.*` event set.
- `app/schemas/orchestration.py`, `app/schemas/response.py`,
  `app/schemas/safety.py`, `app/api/routes/orchestration.py`,
  `app/api/routes/response.py`, `app/api/routes/safety.py`.

**Depends on**: Incident (candidate + evidence), Prediction (optional
evidence for ranking), Digital Twin (mutation target validation).

**Explicitly out of scope for Phase 1**: an LLM-based or learned response
planner. The chain remains explicit, versioned, deterministic Python logic.

## Audit / Evaluation foundation

**Responsibility**: an append-only, hash-chained record of every
orchestration decision/execution/verification/rollback, and the
run/experiment identity that makes a stored record reconstructable later.

- `AuditEventRecord` and the `_audit`/`audit`/`verify_audit` methods inside
  `app/services/orchestration_service.py` (this was not split into a
  separate service module in Phase 1 — it is small, has exactly one
  caller, and splitting it would add an indirection layer without a
  behavioural benefit).
- `app/database/models.py` — the 27-table schema, including every audit,
  run, and evidence table (see `docs/architecture/PERSISTENCE.md`).

**Explicitly out of scope for Phase 1**: the Phase 5 resilience-score /
evaluation-metrics system. `reports/final_benchmark_*` remain static,
manually generated artifacts, not a live evaluation pipeline.

## Cross-cutting

- **API Layer**: `app/api/router.py` + `app/api/routes/*.py` — thin FastAPI
  routers; all contain request validation and delegate to exactly one
  domain service.
- **Core**: `app/core/config.py` (settings), `app/core/exceptions.py`
  (structured errors), `app/core/logging.py` / `app/core/middleware.py`
  (correlation ID), `app/core/constants.py`.
- **Database**: `app/database/session.py` (connection/session lifecycle),
  `app/database/models.py` (ORM), `app/database/base.py` (declarative base).
- **WebSocket**: `app/websocket/manager.py` (connection registry),
  `app/websocket/routes.py` / `playback_routes.py` / `playback.py`
  (live and playback event streaming to the frontend).
- **Events** (new in Phase 1): `app/events/` — see
  `docs/architecture/EVENT_MODEL.md`.
