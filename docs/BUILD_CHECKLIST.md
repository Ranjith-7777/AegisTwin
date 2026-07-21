# AegisTwin Build Checklist

This checklist turns the blueprint into eight gated phases. Complete and verify one phase before starting work that depends on it. Phase 2 must not begin without explicit instruction.

## Phase 1: Scope and architecture

### Objectives

- Fix the MVP boundary, primary scenario, safety model, architecture, contracts, and success measures.
- Make unresolved choices visible before scaffolding.

### Tasks

- [x] Inspect the repository without overwriting or deleting content.
- [x] Define users, problem, workflow, MVP inclusions/exclusions, and acceptance criteria.
- [x] Define logical agents, module boundaries, data flow, twin graph, and response policy.
- [x] Draft event, API, WebSocket, persistence, audit, and explainability contracts.
- [x] Record initial architectural decisions and risks.
- [x] Define phased delivery and test/evaluation strategy.
- [ ] Review the blueprint with the team and resolve or consciously defer open decisions.
- [ ] Approve Phase 1 and explicitly authorise Phase 2.

### Expected files

- `docs/PROJECT_BLUEPRINT.md`
- `docs/BUILD_CHECKLIST.md`
- `docs/DECISIONS.md`

### Acceptance tests

- All requested blueprint sections and five readable Mermaid diagrams are present.
- The checklist contains eight phases and a dependency gate for each.
- Every required initial technology decision is recorded in the agreed format.
- Documentation states that telemetry and response are simulated only.
- Repository inspection confirms that no application source or dependency manifest was introduced.

### Dependencies on previous phases

None.

### Completion checklist

- [x] Documentation drafted.
- [x] Safety boundary explicit.
- [x] Primary demo path explicit.
- [x] Architecture and contracts proposed.
- [ ] Stakeholder review complete.
- [ ] Open decisions assigned or resolved.
- [ ] Phase 2 authorised.

## Phase 2: Project foundation

### Objectives

- Create reproducible frontend/backend foundations and enforce typed boundaries and quality gates.

### Tasks

- [ ] Create React + TypeScript + Vite frontend and FastAPI backend.
- [ ] Configure Tailwind CSS, shadcn/ui, React Router, Axios, linting, formatting, and tests.
- [ ] Establish backend settings, structured logging, error envelopes, health route, SQLAlchemy session, and migrations.
- [ ] Define initial Pydantic/TypeScript contracts and WebSocket envelope.
- [ ] Add `.env.example`, `.gitignore`, README, licence, and attribution policy without secrets.
- [ ] Add CI for lint, type checks, tests, builds, and secret scanning.
- [ ] Establish accessibility/design tokens and persistent simulated-environment banner.

### Expected files

- `frontend/package.json`, `frontend/vite.config.ts`, `frontend/src/app/`, `frontend/src/api/`
- `backend/pyproject.toml`, `backend/app/main.py`, `backend/app/core/`, `backend/migrations/`
- `.env.example`, `.gitignore`, `README.md`, `LICENSE`
- CI workflow files and contributor/development guidance

### Acceptance tests

- Clean documented setup installs and starts both applications.
- Health endpoint and frontend shell render successfully.
- Lint, type-check, unit-test, and production-build commands pass.
- Temporary database migration upgrade succeeds.
- Contract fixture serialises equivalently in Python and TypeScript.
- Secret scan and simulation-banner test pass.

### Dependencies on previous phases

- Phase 1 approved.
- Runtime/package-manager versions, licence, frontend state/test tools, and migration timing resolved.

### Completion checklist

- [ ] Reproducible setup.
- [ ] Typed contracts established.
- [ ] Quality gates green.
- [ ] Safe configuration documented.
- [ ] Foundation architecture matches decisions.

## Phase 3: Telemetry and attack simulator

### Objectives

- Produce deterministic, schema-valid benign and malicious simulated telemetry for the primary scenario.

### Tasks

- [ ] Implement canonical discriminated event schemas and validation.
- [ ] Build seeded topology, synthetic identities/assets, and documentation-range addresses.
- [ ] Implement benign background generator and primary attack fixture.
- [ ] Add replay clock with start, pause, resume, step, speed, and reset controls.
- [ ] Build ingestion and event-query APIs with idempotent event IDs.
- [ ] Persist simulation runs, raw events, and rejection/audit records.
- [ ] Publish ingestion WebSocket messages.

### Expected files

- `shared/contracts/` and/or generated frontend types
- `simulator/scenarios/compromised_account.*`, `simulator/fixtures/`
- `backend/app/api/events.py`, `backend/app/api/simulation.py`
- `backend/app/domain/events.py`, `backend/app/application/ingestion/`
- models/migrations and Phase 3 tests

### Acceptance tests

- Same seed produces identical ordered event content and IDs.
- Scenario contains every required stage and benign interleaving.
- Missing/false simulation markers, invalid event variants, and duplicates are safely handled.
- Pause/resume/step/reset are deterministic and do not leak state between runs.
- Sustained ingestion meets at least 10 events/second locally.
- No real network scanning, credential action, or external response call exists.

### Dependencies on previous phases

- Phase 2 applications, contracts, persistence, logging, WebSocket envelope, and CI are complete.

### Completion checklist

- [ ] Canonical schema stable.
- [ ] Scenario and benign fixtures reproducible.
- [ ] Controls and ingestion usable.
- [ ] Persistence and stream verified.
- [ ] Safety tests pass.

## Phase 4: Anomaly detection and incident correlation

### Objectives

- Detect behavioural deviations and turn multiple weak signals into one explainable incident.

### Tasks

- [ ] Define versioned feature pipeline and benign training fixture.
- [ ] Train/serialize Isolation Forest baseline with fixed seed.
- [ ] Calibrate threshold and record score semantics and limitations.
- [ ] Implement per-event/window explanations.
- [ ] Implement correlation rules, time windows, entity links, severity, and incident lifecycle.
- [ ] Persist feature vectors, anomaly results, incidents, and evidence.
- [ ] Expose analysis/incident APIs and stream updates.

### Expected files

- `backend/app/application/detection/`, `backend/app/application/correlation/`
- `backend/app/models/anomaly.py`, `backend/app/models/incident.py`
- `backend/app/api/incidents.py`
- versioned model artifact/metadata and fixtures under an approved data path
- unit, golden-scenario, and performance tests

### Acceptance tests

- Fixed inputs generate reproducible scores within defined tolerance.
- Every anomaly result exposes features, threshold, classification, and model version.
- Golden scenario forms exactly the expected incident and ordered evidence chain.
- Out-of-order, duplicate, late, and boundary-window events behave predictably.
- Seeded evaluation meets detection/correlation targets or documents approved variance.

### Dependencies on previous phases

- Stable event schema, seeded telemetry, persistence, and replay controls from Phase 3.
- Threshold and correlation-window decisions resolved.

### Completion checklist

- [ ] Baseline reproducible.
- [ ] Explanations complete.
- [ ] Correlation lifecycle correct.
- [ ] Metrics reported honestly.
- [ ] APIs and streaming verified.

## Phase 5: MITRE ATT&CK mapping and digital twin

### Objectives

- Add evidence-backed ATT&CK context and an interactive, graph-derived view of attack progression.

### Tasks

- [ ] Curate and version only the ATT&CK subset needed for the scenario.
- [ ] Implement deterministic mapping rules with evidence references and confidence.
- [ ] Persist typed twin nodes, edges, dynamic state, and attack steps.
- [ ] Materialise NetworkX graph and implement reachability/path queries.
- [ ] Expose topology snapshot and incident attack-path APIs.
- [ ] Build React Flow view with legend, filters, selection, and accessible detail panel.
- [ ] Distinguish base topology, observed path, predicted path, critical assets, and containment.

### Expected files

- `shared/mitre/`, `backend/app/application/attack_mapping/`
- `backend/app/application/twin/`, twin models/migrations and APIs
- `frontend/src/features/twin/`, `frontend/src/features/incidents/`
- curated mapping fixtures and graph tests

### Acceptance tests

- Each mapping cites evidence and expected curated technique metadata.
- Golden fixture maps to reviewed expected techniques with no unsupported procedural content.
- Graph invariants, shortest/reachable paths, and incident overlays are correct.
- React Flow renders all required states and remains usable at target laptop resolution.
- Mapping and graph state survive reload and stay scoped to the simulation run.

### Dependencies on previous phases

- Stable incidents/evidence from Phase 4.
- ATT&CK version/subset and graph state model approved.

### Completion checklist

- [ ] Mapping catalogue reviewed.
- [ ] Twin persistence and calculations correct.
- [ ] Attack path visually clear.
- [ ] APIs/types synchronised.
- [ ] Accessibility and graph tests pass.

## Phase 6: Agentic response orchestration

### Objectives

- Predict a bounded next action, compare safe containment options, and execute approved simulated state transitions.

### Tasks

- [ ] Implement closed-list transition/ranking rules for next-action prediction.
- [ ] Return confidence, alternatives, evidence, and versioned rationale.
- [ ] Define action registry for no action, credential revocation, endpoint isolation, and combined containment.
- [ ] Clone twin state and calculate security benefit, disruption, residual reachability, and reversibility.
- [ ] Implement explicit weighted recommendation and approval policy.
- [ ] Implement approval lifecycle, optimistic incident version checks, and idempotency.
- [ ] Implement simulated executor with no external adapters and reversible demo reset.
- [ ] Record hash-linked audit entries throughout.

### Expected files

- `backend/app/application/prediction/`, `backend/app/application/response/`
- `backend/app/application/audit/`
- approval, response, prediction, and audit models/migrations/APIs
- `frontend/src/features/response/` and shared explanation components
- policy/config fixtures and safety tests

### Acceptance tests

- Expected next step appears in the top three at each golden checkpoint.
- Every recommendation exposes its weights, metrics, evidence, and alternatives.
- Material action without approval, stale approval, unknown action, or non-simulated target is rejected.
- Duplicate execute calls do not duplicate effects.
- Combined action removes critical-database reachability in the cloned and approved twin states.
- Audit hash chain validates and contains every required decision transition.

### Dependencies on previous phases

- Incident evidence, ATT&CK mappings, and twin reachability from Phases 4-5.
- Ranking weights and approval policy resolved.

### Completion checklist

- [ ] Predictions bounded and explainable.
- [ ] Options compared transparently.
- [ ] Human gate enforced.
- [ ] Simulated actions safe/idempotent.
- [ ] Audit completeness verified.

## Phase 7: Dashboard and end-to-end integration

### Objectives

- Deliver a coherent professional operator experience for the complete scenario.

### Tasks

- [ ] Build overview KPIs, live telemetry, incident list/detail, and ATT&CK evidence views.
- [ ] Integrate the interactive twin, prediction, response, approval, and audit experiences.
- [ ] Implement WebSocket reconnect, REST resynchronisation, loading/empty/error states, and notifications.
- [ ] Add guided demo controls and persistent simulation labels.
- [ ] Apply restrained design tokens, responsive layouts, keyboard flows, and accessible contrast.
- [ ] Create end-to-end tests for approval, rejection, reconnect, reset, and the golden scenario.
- [ ] Measure and tune event-to-dashboard latency.

### Expected files

- feature routes/components across `frontend/src/features/` and `frontend/src/routes/`
- WebSocket client/state synchronisation modules
- frontend component, integration, and E2E tests
- demo runbook/screenshots in `docs/`

### Acceptance tests

- Operator completes the entire primary scenario without developer intervention.
- Dashboard truth matches API/database state after reconnect and reload.
- Approval and rejection branches are clear and audited.
- Keyboard navigation and automated accessibility checks cover the critical flow.
- Event-to-dashboard P95 is under 2 seconds at the target rate.
- Ten consecutive seeded golden runs complete successfully.

### Dependencies on previous phases

- All backend workflow capabilities and stable API/WebSocket contracts from Phases 3-6.

### Completion checklist

- [ ] All routes integrated.
- [ ] Realtime recovery robust.
- [ ] Demo UX polished and professional.
- [ ] Accessibility baseline met.
- [ ] Golden E2E and latency targets pass.

## Phase 8: Evaluation, deployment and submission

### Objectives

- Validate claims, package a reproducible safe demo, and prepare credible submission material.

### Tasks

- [ ] Run the full evaluation matrix and publish methods, fixtures, results, and limitations.
- [ ] Threat-model the prototype and repeat safety/secret/dependency checks.
- [ ] Create production-style builds, containers, Compose configuration, and health checks.
- [ ] Test setup from a clean environment and database reset/backup workflow.
- [ ] Finalise README, architecture links, demo runbook, troubleshooting, licence notices, and attribution.
- [ ] Prepare demo script, fallback recording/screenshots, judging narrative, and acceptance sign-off.
- [ ] Reconcile implementation with decisions and record any superseding ADRs.

### Expected files

- container build files and Compose configuration
- CI release/build workflow
- `docs/EVALUATION.md`, `docs/DEMO_RUNBOOK.md`, `docs/SECURITY.md`
- final README, licence/notice files, submission assets

### Acceptance tests

- Clean-machine/container setup passes documented commands.
- Full test, lint, type, build, migration, secret, and safety suites pass.
- Evaluation results meet targets or clearly disclose approved gaps.
- Demo works offline except for initially obtaining dependencies/images.
- No real integration, secret, personal data, offensive capability, or unsupported claim is present.
- Every finished-prototype acceptance criterion in the blueprint is signed off.

### Dependencies on previous phases

- Integrated and stable Phase 7 prototype.
- Deployment topology, audit export format, and submission/licensing requirements resolved.

### Completion checklist

- [ ] Evidence-based evaluation published.
- [ ] Deployment reproducible.
- [ ] Safety and licences reviewed.
- [ ] Documentation and runbook complete.
- [ ] Submission package and fallback demo ready.

