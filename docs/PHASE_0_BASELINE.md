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

## 6. Feature status

Superseded by the full-simulation pass in §11 (Phase 0 finalization). Summary retained here for history; see §11 for the authoritative, evidence-based classification.

| Area | Status | Basis |
|---|---|---|
| Overview / Command Centre | WORKING | Loads live risk score, availability, active incidents, and rendered digital-twin graph; backend/system status both green; no console errors. |
| Digital Twin | WORKING | Renders 13 synthetic assets / 24 relationships, path inspection controls present and interactive; self-labeled "static topology". |
| Threat Analysis → Live Telemetry | WORKING | Started a real synthetic simulation run; WebSocket streamed live events with real IsolationForest-derived anomaly scores (event 2/12, playing state observed). |
| Threat Analysis → Incidents / MITRE / Attack Prediction | NOT VERIFIED (this pass) | Present as tabs; not clicked into in this pass — verified in §11. |
| Defense → Blue Agent | WORKING | Loads causal response analysis UI; explicit banner confirms simulation-only, no real action executed. |
| Defense → Response Operations | NOT VERIFIED (this pass) | Tab present, not exercised in this pass — verified in §11. |
| Results → Detection Models | WORKING | Live anomaly-activity chart with real scored data (12 assessed points) and a persisted model listing table. |
| Results → Audit Trail | WORKING (empty) | Loads and queries correctly; showed "no matching synthetic audit events" because no orchestration run had been triggered yet in this session — UI/query path itself functioned. |
| Results → Settings | NOT VERIFIED (this pass) | Not opened in this pass — verified in §11. |
| Docker / docker-compose | NOT VERIFIED | Docker is not installed in this environment; compose file inspected but not run. |

## 7. Security / secret audit

- Checked all current tracked files for `.env`/credential/key-like filenames: only `.env*.example` templates exist, all containing placeholder values (no real hosts, keys, or credentials).
- Scanned full history (`git log --all -p`) across every branch for common secret patterns (AWS/GCP keys, GitHub tokens, OpenAI-style keys, private-key headers, Slack tokens): **no matches found**.
- Scanned full history for sensitive filenames ever added (`.env`, `.pem`, `.key`, `id_rsa`, `credentials.json`, etc., excluding `.example`): **none found**.
- Conclusion: no genuine secrets appear present in current files or history. Push to the new public repository proceeded.

## 8. Git hygiene

`.gitignore` was inspected and found already comprehensive: Python venv/caches, `.env`/`.env.*` (with `.example` explicitly whitelisted), databases (`*.db`, `*.sqlite`, `*.joblib`, `*.pkl`), `node_modules/`, build output, logs, test artifacts, demo runtime directory (`.aegistwin-demo/`), and editor/OS files. No changes were made — none were needed.

## 9. Technical debt / observations (Phase 0 observations only, not addressed)

- npm install reported 11 vulnerabilities (4 moderate, 7 high) in frontend dependencies — **not remediated**; `npm audit fix`/`--force` were deliberately not run so the baseline reflects the inherited state. Left for later, deliberate remediation.
- Root-level batch launchers and some docs still reference the old "AegisTwin" naming even though UI/copy elsewhere already says "AegisArena" — naming migration is incomplete in the inherited code.
- Reports under `reports/` are static, manually generated artifacts from a single seed/run, not a repeatable benchmark pipeline wired into CI.
- Backend `mypy app tests` fails with 6 pre-existing type errors, all confined to `backend/tests/test_orchestration.py` (lines 26, 38, 39, 58, 95, 148 — `no-any-return`, `index`, `attr-defined` on values typed as `object`/`Callable` returned from a test helper). `mypy app` alone (excluding tests) was not separately re-run, but the errors are visibly scoped to this one test file, not application code. Not fixed — recorded as baseline technical debt per instruction not to perform a broad fix.
- Frontend `npm run format:check` fails across 109 of ~113 source/config files (all of `src/`, config files, `package-lock.json`, `README.md`). Every file is flagged, not a targeted subset — consistent with a Prettier/line-ending (CRLF vs LF) drift from a Windows checkout of a repo likely authored/formatted on Linux/macOS CI, rather than genuine style violations in the code. Not fixed: touching 109 files is not a "trivial, no-behavior-change" edit within the scope of this phase, per instruction. Recorded as baseline technical debt for a deliberate, reviewed formatting pass later.
- Digital Twin page's "Show applied synthetic execution" overlay did not visibly change node state in the topology view immediately after a full-page reload lost the active run selection — the underlying mutation is confirmed at the data/API layer (orchestration execution response explicitly reported "Applied in synthetic twin: 1 nodes and 0 relationships"), but re-associating that mutation with the topology view's run context was not completed in this pass. See §11 for the exact classification.

## 10. Manual verification still required (by project manager / user)

- Re-check the Digital Twin topology overlay against an in-progress (not page-reloaded) run to confirm the applied-execution visualization renders as expected.
- Exercise Docker/docker-compose build and run path (not available in this environment).
- ~~Confirm the branch-naming/consolidation decision for `main`/`develop` before any Phase 1 work begins~~ — resolved in §13 (Phase 0 finalization): `main` and `develop` normalized to the Phase 0 baseline; see §13 for details and preserved historical pointers.

---

# Phase 0 Finalization (addendum)

Date: 2026-09-13 (same day, second pass)

## 11. Validation suite results

Commands were read directly from `.github/workflows/backend-ci.yml`, `.github/workflows/frontend-ci.yml`, and `backend/pyproject.toml` — no commands were invented.

### Backend (from `backend/`, using the venv created in §Setup)

| Command | Result | Notes |
|---|---|---|
| `python -m ruff check .` | PASS | "All checks passed!" |
| `python -m ruff format --check .` | PASS | "106 files already formatted" |
| `python -m mypy app tests` | **FAIL** | 6 errors, all in `tests/test_orchestration.py` (lines 26, 38, 39, 58, 95, 148). See §9 for detail. Not fixed — genuine pre-existing typing debt in test code, out of scope for a trivial/no-behavior-change fix. |
| `python -m pytest` | PASS | 78 passed, 0 failed, 3 warnings, 70.82s |

### Frontend (from `frontend/`)

| Command | Result | Notes |
|---|---|---|
| `npm run lint` (eslint) | PASS | No output/errors |
| `npm run format:check` (prettier --check) | **FAIL** | 109 files flagged, uniformly — consistent with CRLF/line-ending drift on this Windows checkout rather than real style violations. Not fixed (not a trivial, single-file, no-behavior-change edit). See §9. |
| `npm run typecheck` (tsc -b) | PASS | No output/errors |
| `npm run test:run` (vitest run) | PASS | 8 test files, 43 tests, all passed |
| `npm run build` (tsc -b && vite build) | PASS | Built in 7.87s, 2517 modules transformed, no errors |

`npm audit fix` / `npm audit fix --force` were **not** run, per instruction. The 11 previously observed vulnerabilities (4 moderate, 7 high) remain present and undocumented-as-fixed — they are baseline technical debt for future remediation.

No dependency upgrades were performed.

## 12. Full simulation verification

The demo app was started via `START_AEGISTWIN_DEMO.bat -NoBrowser` and driven manually in-browser through a complete run:

1. **Threat Analysis → Live Telemetry**: selected scenario `Staged Cloud Compromise Demonstration` (seed 84, the same frozen judge-demo scenario), clicked "Start Synthetic Simulation" at 50× playback speed. The run streamed 12/12 events over WebSocket to completion (`Playback state: completed`, `Event position: 12/12`, `Simulated elapsed: 720s`, run id `31208de6-3573-57f5-a315-0e09eaacef95`), each event carrying a real IsolationForest-derived anomaly assessment (score/threshold/signal count).
2. **Threat Analysis → Incidents**: a real incident candidate was generated from the run: "Related unusual synthetic activity", priority high, coherence score 0.785, 9 evidence items across sequence 1–11, mapped to MITRE tactics (Credential Access, Defense Evasion, Exfiltration, Lateral Movement, Persistence) and techniques (T1021, T1078, T1098, T1110.001, T1567).
3. **Threat Analysis → MITRE ATT&CK**: the technique timeline rendered the same techniques in sequence order (T1110.001 Password Guessing → T1078 Valid Accounts → T1098 Account Manipulation → T1021 Remote Services ×2), derived from the run's evidence — not a static/hardcoded list.
4. **Threat Analysis → Attack Prediction**: selecting the run + trained model (`aa978c01-bbb7-5dde-910c-b189caaff69a`) and clicking "Analyze predictions" produced a real next-stage hypothesis: "Current estimate: session_conclusion · Exfiltration · through sequence 12".
5. **Defense → Blue Agent**: selecting the same run/model and clicking "Rank Mitigations" produced 4+ candidate mitigations, each with a genuinely computed Defense Score (Security Improvement − Service Disruption − Resource Cost − SLA Penalty), e.g. Rank 1 "Increase telemetry on the cloud asset" on `api-gateway-01`, Defense Score 0.750 (0.85 − 0.06 − 0.04 − 0.00).
6. Clicked "Create Synthetic Response Orchestration" — this created orchestration `58689cb0`, and the agent pipeline auto-progressed: **Response Planner** (completed — selected rank-1 recommendation), **Safety Governor** (completed — auto-approved by policy), **Approval Router** (completed — no human gate required for this tier).
7. **Defense → Response Operations**: clicked "Execute in Synthetic Twin" — execution state became "completed simulated", explicitly reporting "Applied in synthetic twin: 1 nodes and 0 relationships". Clicked "Verify Simulated Outcome" — orchestration state advanced to "verified", "Verification: successful simulation. Residual exposure score: 0".
8. **Results → Audit Trail**: querying the orchestration `58689cb0` returned 9 tamper-evident, hash-chained, timestamped events in order — `orchestration_created` → 4× `agent_decision` → `state_transition` → `agent_decision` (execution) → `synthetic_execution_completed` → `verification_completed` — each attributed to the correct actor (Demo Operator / named simulation agent), each with an "Inspect hashes and canonical payload" affordance.
9. **Results → Settings**: loaded correctly, showing live backend/database connectivity, environment "Demo", version "0.9.0", and — notably — the exact running git commit `e3640fa` (matching the Phase 0 commit at the time this run was performed), confirming the running build was in fact built from this repository state.
10. **Digital Twin**: after a full page reload the topology view lost the active run selection (`Run: none`) and all 13 assets showed "normal" state; the "Show applied synthetic execution" overlay did not visibly re-render the specific mutation without re-selecting the run context in that view. The mutation itself is confirmed to have happened at the data/API layer (step 7's explicit "Applied in synthetic twin: 1 nodes" response) — this is a UI state-restoration gap on hard reload, not evidence the mutation didn't occur. Not fixed (would require code changes, out of scope for Phase 0).

**Conclusion**: the inherited baseline's full detection → correlation → prediction → response → orchestration → audit pipeline is genuinely functional end-to-end against synthetic data, with real computation at every stage (ML scoring, MITRE mapping, defense-score arithmetic, hash-chained audit log). No fake/hardcoded results were observed anywhere in this run.

## 13. Final feature verification matrix

| Feature | Status | Evidence |
|---|---|---|
| Overview / Command Centre | WORKING | Live KPIs, twin graph, backend/system status green (§6, prior pass) |
| Digital Twin (topology render, path inspection) | WORKING | 13 assets / 24 relationships rendered, path controls interactive (§6, prior pass) |
| Digital Twin (applied-execution overlay after mutation) | PARTIALLY WORKING | Backend mutation confirmed (§12 step 7); UI overlay lost run context after a hard reload and did not re-render the specific change in this pass |
| Threat Analysis → Live Telemetry | WORKING | Full 12/12 event run streamed live via WebSocket with real anomaly scores (§12 step 1) |
| Threat Analysis → Incidents | WORKING | Real correlated incident candidate generated from run evidence (§12 step 2) |
| Threat Analysis → MITRE ATT&CK | WORKING | Real technique timeline derived from run evidence, not static (§12 step 3) |
| Threat Analysis → Attack Prediction | WORKING | Real next-stage hypothesis computed from run + model (§12 step 4) |
| Defense → Blue Agent (mitigation ranking) | WORKING | Real, arithmetically-derived Defense Scores for multiple candidates (§12 step 5) |
| Defense → Blue Agent (orchestration creation) | WORKING | Orchestration created and auto-progressed through planner/governor/approval stages (§12 step 6) |
| Defense → Response Operations (execute/verify) | WORKING | Execution + verification both completed successfully against the synthetic twin (§12 step 7) |
| Results → Detection Models | WORKING | Live scored-event chart + persisted model listing (§6, prior pass) |
| Results → Audit Trail | WORKING | 9 correctly ordered, hash-chained, attributed events for the full run (§12 step 8) |
| Results → Settings | WORKING | Live connectivity status + correct running build/commit info (§12 step 9) |
| Docker / docker-compose | NOT VERIFIED | Docker unavailable in this environment (not installed for this task, per instruction) |
| Red Agent (attack scenarios) | WORKING (as scripted/deterministic, not adaptive) | 6 fixed scenarios selectable and runnable; not a learning/adaptive agent — this is by design, not a defect (§4 architecture notes) |

Distinction made explicit per instruction: **real computation** occurs at every stage above (IsolationForest scoring, MITRE technique mapping from actual evidence, Defense Score arithmetic, hash-chained audit records); the **simulation/determinism** is in the input telemetry (scripted, seeded) and in the Blue Agent's rule-based (not ML/LLM) decision logic; the only **static/UI-only** gap found is the Digital Twin's post-reload overlay re-rendering (above).

## 14. Branch normalization (final)

- Ancestry verified before any branch changes: `git merge-base --is-ancestor main feature/phase-0-baseline` → exit 0 (true); `git merge-base --is-ancestor develop feature/phase-0-baseline` → exit 0 (true). Both old branches are strict ancestors — safe to fast-forward.
- Historical pointers preserved before moving anything:
  - `legacy-source-main` → `897dfa61f4181059cc41be886917f1de597343dc` (old `main`)
  - `legacy-source-develop` → `e47f9f2f543c14703ca06f63859e6a0ffd7b4fef` (old `develop`)
  - `professor-review-baseline` left untouched at `37aa5657d33b5250aa684f0aa353343f1a066aa7`.
- `main` fast-forwarded (no merge/rebase/reset) to the completed `feature/phase-0-baseline` commit.
- `develop` fast-forwarded (no merge/rebase/reset) to the same commit as `main`.
- `phase-0-complete` tag created at the same final commit, marking the reviewed, normalized Phase 0 state — distinct from `professor-review-baseline`, which marks the inherited pre-documentation state.
- All 15 original inherited feature branches remain untouched and preserved; nothing was deleted.
- Pushes for `main`/`develop`/tags were made only to `origin` (`git-hima-bling/AegisArena`), never to `upstream` (`Ranjith-7777/AegisTwin`). See the completion report for the exact resulting SHAs and the safeguard configured against accidental upstream pushes.
