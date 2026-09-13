# Phase 0 Baseline — AegisArena (migrated from AegisTwin)

Date: 2026-09-13

## 1. Migration

- Source repository (read-only, `upstream`): https://github.com/Ranjith-7777/AegisTwin (public)
- Destination repository (`origin`): https://github.com/git-hima-bling/AegisArena (public)
- Local path: `D:\AegisArena`
- Clone method: full `git clone` (complete history, all branches, all refs preserved). No Git LFS objects and no submodules were present in the source repository.

## 2. Branch structure discovered

All branches in the inherited repository form a single linear ancestor chain — there is **no branch divergence or conflicting implementation** to reconcile. Verified with `git merge-base --is-ancestor` for every branch against `feature/local-demo-packaging`, the tip of the chain.

Chain order (commit count on each branch, tip SHA):

1. `main` (1 commit, `897dfa6`) — only a Phase 1 architecture blueprint doc.
2. `feature/project-foundation` (2, `73dd309`)
3. `develop` (3, `e47f9f2`) — merge of Phase 2A backend foundation
4. `feature/frontend-foundation` (4, `18293a4`)
5. `feature/telemetry-foundation` (6, `4e15ef6`)
6. `feature/anomaly-detection` (7, `6171671`)
7. `feature/detection-quality-hardening` (8, `3c4f95b`)
8. `feature/live-anomaly-integration` (9, `17671d8`)
9. `feature/incident-correlation-mitre` (10, `53bb13f`)
10. `feature/next-stage-prediction` (11, `d5b164a`)
11. `feature/cyber-digital-twin` (12, `f3cecbf`)
12. `feature/live-digital-twin-animation` (13, `76a6540`)
13. `feature/response-simulation` (14, `4296421`)
14. `feature/agentic-response-orchestration` (15, `c3218fe`)
15. `feature/final-submission-hardening` (16, `99366ee`)
16. `feature/local-demo-packaging` (18, `37aa565`) — **most complete/current implementation**, dated 2026-09-01.

Important: the GitHub default branch (`main`) is **not** representative of the working application — it contains only one documentation commit. The actual functioning codebase lives at the tip of `feature/local-demo-packaging`. This is flagged for project-manager awareness; no branches were merged, deleted, or rewritten to correct this — all are preserved exactly as inherited.

`feature/phase-0-baseline` was created from `feature/local-demo-packaging` (same commit, `37aa565`) to hold Phase 0 documentation work, per the required workflow.

`professor-review-baseline` (annotated tag) points to commit `37aa565` (tip of `feature/local-demo-packaging`), representing the actual project state at the start of Phase 0.

## 3. Development environment (recorded versions)

- Git: 2.55.0.windows.3
- GitHub CLI: 2.100.0 (installed via winget during this phase; was not previously present)
- GitHub auth: `git-hima-bling` (browser device-code login, scopes: gist, read:org, repo)
- Python: 3.14.2 (system); backend declares support for Python >=3.11 (CI pins 3.11)
- Node.js: v24.12.0
- npm: 11.12.1
- Docker: not installed in this environment (Dockerfiles/compose exist in repo but were not exercised)

## 4. Architecture discovered (factual, verified against code)

### Frontend (`frontend/`)
- React 19.2.0 + TypeScript 5.9.3, Vite 7.2.0. Router: react-router-dom 7.9.0.
- Pages: Overview, Digital Twin, Telemetry, Incidents, MITRE, Predictive Analytics, Response Centre, Response Operations, Model Analytics, Audit Trail, Settings.
- State: React Context + custom hooks (no Redux/Zustand).
- REST: axios client (`src/services/apiClient.ts`) hitting `VITE_API_BASE_URL`.
- WebSocket: `src/services/websocketClient.ts` → `/ws/events`; separate playback WS channel for scenario replay.
- Topology visualization: `@xyflow/react`. Charts: `recharts`.
- Tests: Vitest + Testing Library + Playwright.
- Dev/build: `npm run dev`, `npm run build`, `npm run test:run`, `npm run test:e2e`.

### Backend (`backend/`)
- FastAPI (>=0.115) + SQLAlchemy (>=2.0.36) + Alembic + Uvicorn, Python >=3.11.
- Entry point: `app/main.py`. Hard-enforced startup gate: `ensure_simulation_only()` raises if `SIMULATION_ONLY` != true — a real code-level guard, not just documentation.
- Routes: health, telemetry, detection, correlation, mitre, prediction, response, orchestration, safety, simulation, system, topology.
- WebSocket: `app/websocket/manager.py`, `/ws/events`, plus dedicated playback routes.
- Config: pydantic-settings, `.env`-driven; CORS wildcard explicitly disallowed.
- Error handling: `ApplicationError`/`ConfigurationError` with centralized exception handlers.
- Logging: `app/core/logging.py` with a correlation-ID middleware.

### AI/ML — real vs. synthetic (key finding)
- **Real, trained ML**: `sklearn.ensemble.IsolationForest` inside a `DictVectorizer` pipeline is genuinely fit (`pipeline.fit`) and scored (`decision_function`) in `backend/app/services/detection_training_service.py`. This is not hardcoded output.
- Final anomaly score is a **hybrid**: 35% weight on the isolation-forest rank, blended with rule-based heuristics (numerical deviation, categorical rarity, behavioural-transition rarity, infrastructure novelty).
- Thresholds are calibrated from a validation-set false-positive target.
- Trained pipelines are persisted via `joblib` to `MODEL_ARTIFACT_DIR` and reloaded for scoring.
- "Synthetic" refers to the **input telemetry**, not fabricated outputs: a deterministic, seeded event generator (`event_generator.py`) produces telemetry from scripted attack/normal scenarios and explicitly tags each record `synthetic: true`. The model itself computes real scores against this synthetic data.
- No hardcoded/fake ML predictions were found in the detection path.

### Red Agent / attack simulation
- No adaptive/learning red-team agent. Attacks are fixed, scripted scenario definitions (`backend/app/services/scenario_service.py`, 6 scenarios including `staged-compromise-demo`, `credential-compromise`, `ddos-traffic-spike`), replayed deterministically by seed. The frontend "Red Agent" panel is a passive UI view of this scripted playback.

### Blue Agent / response
- A deterministic, explicitly-versioned (`deterministic-simulation-agent-v1`) chain of rule-based agent classes (`ResponsePlannerAgent`, `ImpactSimulationAgent`, `SafetyGovernorAgent`, `ApprovalRouterAgent`, `SyntheticExecutionAgent`, `VerificationAgent`) in `orchestration_agents.py`. Not ML/LLM-based.
- Real, working audit trail: each stage persists DB records (decisions, approvals, executions, verifications, rollbacks).
- Actions only mutate the persisted synthetic topology state — no real infrastructure, cloud SDK, or subprocess/exec calls exist anywhere in the codebase. The UI explicitly discloses "No real defensive action has been executed."

### Digital Twin / Topology
- Static, hardcoded inventory of ~13 synthetic assets (`topology_service.py`, `NODE_DETAILS`), each labeled "Synthetic..." in its description.
- Dynamic layer computes attack paths/reachability over this static graph (`topology_path_service.py`) and is mutated at runtime by response execution — so the twin state is a live, mutable, in-app graph, not fed by real infrastructure telemetry.

### Reports
- `reports/final_benchmark_metrics.csv/json` and `final_benchmark_report.md` are pre-generated, checked-in artifacts from a single frozen scenario run (seed 84), not regenerated automatically at runtime or in CI. The report explicitly states its measurements are synthetic and do not establish production security effectiveness.

### Cloud/DevOps
- `docker-compose.yml`: backend (SQLite volume, health check on `/api/health`) + frontend (multi-stage Node build served via `serve`), not exercised in this phase (Docker not installed in this environment).
- CI: `.github/workflows/backend-ci.yml` (ruff, mypy, pytest), `frontend-ci.yml` (eslint, prettier, tsc, vitest, build), `release-validation.yml`. No Kubernetes manifests or cloud (Azure/AWS) deployment assets exist in the repository.
- Local demo harness: `SETUP_/START_/STOP_/STATUS_/RESET_AEGISTWIN_DEMO.bat` wrapping PowerShell scripts under `scripts/demo/`.

### Storage
- SQLite via SQLAlchemy + Alembic (9 migration revisions, 2026-07-21 through 2026-08-17). No Postgres/MySQL config present.
- 27 ORM tables (`backend/app/database/models.py`) covering scenarios, telemetry, detection models/assessments, MITRE observations, incidents, predictions, response/orchestration records, and audit events.
- Model artifacts persisted to disk via `joblib`; reports are static files, not DB-backed.

### Data flow (as it exists today)
Frontend (axios + WebSocket) → FastAPI routes/`/ws/events` → service layer chain: event generator → detection dataset/training/scoring (IsolationForest) → correlation (MITRE) → prediction → response/playbook recommendation → orchestration agents (plan/simulate/govern/approve/execute/verify/rollback) → topology mutation → WebSocket broadcast back to frontend. Each stage persists its own DB records.

## 5. Local startup — verified working

Commands run, in order:
```
SETUP_AEGISTWIN_DEMO.bat   (creates backend/.venv, installs backend + frontend deps)
START_AEGISTWIN_DEMO.bat -NoBrowser
```
- Backend: `http://127.0.0.1:8000`, health endpoint `GET /api/health` returned `{"status":"healthy","service":"AegisArena API","environment":"demo","simulation_only":true,"database":"connected"}`.
- Frontend: `http://127.0.0.1:5173` (Judge Demo Mode), HTTP 200.
- WebSocket: connected and streaming live synthetic telemetry/scoring events during a manual "Start Synthetic Simulation" run (verified in-browser).
- ML loading: detection model listing and live anomaly-score chart rendered real persisted model data (12 assessed events).
- No console errors observed on any page. No dependency or startup-script failures encountered — setup and startup both completed with the documented one-click flow, exactly as described in `docs/LOCAL_DEMO_GUIDE.md`. The historical `npm notice` startup failure referenced in prior notes did **not** reproduce in this environment/branch.
- Stopped cleanly via `STOP_AEGISTWIN_DEMO.bat` equivalent script; demo data/logs preserved under `.aegistwin-demo/`.

## 6. Feature status (manually verified in running app)

| Area | Status | Basis |
|---|---|---|
| Overview / Command Centre | WORKING | Loads live risk score, availability, active incidents, and rendered digital-twin graph; backend/system status both green; no console errors. |
| Digital Twin | WORKING | Renders 13 synthetic assets / 24 relationships, path inspection controls present and interactive; self-labeled "static topology". |
| Threat Analysis → Live Telemetry | WORKING | Started a real synthetic simulation run; WebSocket streamed live events with real IsolationForest-derived anomaly scores (event 2/12, playing state observed). |
| Threat Analysis → Incidents / MITRE / Attack Prediction | NOT VERIFIED | Present as tabs; not clicked into in this pass (would require a completed simulation run to populate). |
| Defense → Blue Agent | WORKING | Loads causal response analysis UI; explicit banner confirms simulation-only, no real action executed. |
| Defense → Response Operations | NOT VERIFIED | Tab present, not exercised in this pass. |
| Results → Detection Models | WORKING | Live anomaly-activity chart with real scored data (12 assessed points) and a persisted model listing table. |
| Results → Audit Trail | WORKING (empty) | Loads and queries correctly; showed "no matching synthetic audit events" because no orchestration run had been triggered yet in this session — UI/query path itself functioned. |
| Results → Settings | NOT VERIFIED | Not opened in this pass. |
| Docker / docker-compose | NOT VERIFIED | Docker is not installed in this environment; compose file inspected but not run. |

## 7. Security / secret audit

- Checked all current tracked files for `.env`/credential/key-like filenames: only `.env*.example` templates exist, all containing placeholder values (no real hosts, keys, or credentials).
- Scanned full history (`git log --all -p`) across every branch for common secret patterns (AWS/GCP keys, GitHub tokens, OpenAI-style keys, private-key headers, Slack tokens): **no matches found**.
- Scanned full history for sensitive filenames ever added (`.env`, `.pem`, `.key`, `id_rsa`, `credentials.json`, etc., excluding `.example`): **none found**.
- Conclusion: no genuine secrets appear present in current files or history. Push to the new public repository proceeded.

## 8. Git hygiene

`.gitignore` was inspected and found already comprehensive: Python venv/caches, `.env`/`.env.*` (with `.example` explicitly whitelisted), databases (`*.db`, `*.sqlite`, `*.joblib`, `*.pkl`), `node_modules/`, build output, logs, test artifacts, demo runtime directory (`.aegistwin-demo/`), and editor/OS files. No changes were made — none were needed.

## 9. Technical debt / observations (Phase 0 observations only, not addressed)

- `main` and `develop` are far behind the actual implementation (1 and 3 commits respectively vs. 18 on `feature/local-demo-packaging`) — the branching workflow never merged feature work back upward. Reconciling this is a Phase 1+ decision, not performed here.
- npm install reported 11 vulnerabilities (4 moderate, 7 high) in frontend dependencies — not remediated in this phase.
- Root-level batch launchers and some docs still reference the old "AegisTwin" naming even though UI/copy elsewhere already says "AegisArena" — naming migration is incomplete in the inherited code.
- Reports under `reports/` are static, manually generated artifacts from a single seed/run, not a repeatable benchmark pipeline wired into CI.

## 10. Manual verification still required (by project manager / user)

- Exercise the full Threat Analysis → Incidents / MITRE / Attack Prediction tabs and Defense → Response Operations tab through a complete simulation run.
- Exercise Docker/docker-compose build and run path (not available in this environment).
- Confirm the branch-naming/consolidation decision for `main`/`develop` before any Phase 1 work begins.
