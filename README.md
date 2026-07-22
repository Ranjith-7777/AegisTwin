# AegisTwin

Phase 7B adds deterministic simulation-agent orchestration, human demonstration approvals, synthetic execution, verification, rollback, and tamper-evident audit. See [the Phase 7B guide](docs/PHASE_7B_AGENTIC_RESPONSE_ORCHESTRATION.md).

Phase 6A adds a versioned interactive synthetic infrastructure topology with causal observed, correlated, and hypothetical predicted path inspection. See [the Phase 6A guide](docs/PHASE_6A_DIGITAL_TWIN_TOPOLOGY.md).

Phase 5B adds causal, auditable next-stage prediction over the synthetic detection and correlation pipeline. See [the Phase 5B guide](docs/PHASE_5B_NEXT_STAGE_PREDICTION.md) for contracts and limits.

**AegisTwin: Agentic Cyber-Resilience Digital Twin for Critical National Infrastructure** is a hackathon prototype for reasoning over synthetic security telemetry and a simulated infrastructure twin.

> **Safety boundary:** AegisTwin operates exclusively on synthetic telemetry, simulated identities, simulated assets, and simulated response state. Real-world actions and external targets are prohibited. The backend refuses to start when `SIMULATION_ONLY=false`.

## Current phase

Phase 4A.1 hardens offline detection with causal behavioural context, separate evaluation-only benchmark truth, calibration comparison, auditable hybrid components, and event-level plus run-level diagnostics. IsolationForest remains the primary detector. Live anomaly streaming and frontend assessment integration remain deferred to Phase 4B; incident correlation, ATT&CK mapping, prediction, agents, and response orchestration remain later-phase work.

## Repository structure

```text
backend/       FastAPI, SQLAlchemy, Alembic, tests, and container files
datasets/      Synthetic/licensed dataset policy placeholder
docs/          Architecture and delivery planning
frontend/      React and TypeScript dashboard foundation
simulator/     Reserved fixtures and simulator-boundary guidance
scripts/       Reserved for safe developer helpers
.github/       Backend and frontend continuous integration
```

## Backend setup

Use Python 3.11 or newer. Detailed Windows CMD and PowerShell instructions are in [backend/README.md](backend/README.md).

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Environment configuration

Copy `backend/.env.example` to `backend/.env`. Configuration uses environment variables: `APP_NAME`, `ENVIRONMENT`, `DEBUG`, `API_PREFIX`, `BACKEND_HOST`, `BACKEND_PORT`, `DATABASE_URL`, `CORS_ORIGINS`, `LOG_LEVEL`, and `SIMULATION_ONLY`. Do not place secrets in either example file. Simulation-only mode cannot be disabled.

The frontend uses `VITE_API_BASE_URL=http://localhost:8000` and `VITE_WS_BASE_URL=ws://localhost:8000`. These are public browser endpoints, not credentials. Detailed frontend setup is in [frontend/README.md](frontend/README.md).

## Frontend setup

The UI uses React, TypeScript, Vite, Tailwind CSS, shadcn/ui-style source components, React Router, Axios, Lucide icons, and Recharts.

```powershell
Set-Location frontend
npm.cmd install
Copy-Item .env.example .env
npm.cmd run dev
```

Run the backend separately on `http://127.0.0.1:8000`. The frontend remains usable and clearly reports `Backend: Disconnected` when it is unavailable.

## Development commands

Run these from `backend/` with the virtual environment active:

```powershell
python -m alembic upgrade head
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m ruff format .
python -m mypy app tests
```

Alembic revisions can later be generated with `python -m alembic revision --autogenerate -m "description"`. Downgrades are intentionally not part of routine setup.

## Docker

```powershell
docker compose build
docker compose up
docker compose config
```

Compose starts the backend on port 8000 and the frontend on port 5173. The frontend waits for backend health; SQLite uses a disposable named volume.

## Current interfaces

Phase 3B adds `GET /api/v1/simulation/runs/{run_id}/playback` and `WS /api/v1/ws/simulation/runs/{run_id}?after_sequence=0` alongside the existing health, safety, simulation, and telemetry interfaces.

Phase 4A adds versioned `/api/v1/detection` model training, model metadata, offline run scoring, paginated assessments, and evaluation endpoints. See [docs/PHASE_4A_ANOMALY_DETECTION.md](docs/PHASE_4A_ANOMALY_DETECTION.md). An anomaly is unusual synthetic behaviour, not a confirmed attack.

Phase 4A.1 keeps those endpoints backward-compatible while enriching model artifacts, assessments, and evaluations. See [docs/PHASE_4A1_DETECTION_HARDENING.md](docs/PHASE_4A1_DETECTION_HARDENING.md) and the frozen [v1 diagnostic](docs/PHASE_4A1_V1_DIAGNOSTIC.json).

- `GET /api/health` — application and real database connectivity.
- `GET /api/system/status` — static foundation status; incident and agent counts remain zero.
- `GET /api/safety` — explicit simulation-only safety posture.
- `WS /ws/events` — connection acknowledgement and `ping`/`pong` only.
- OpenAPI UI: `GET /docs`.
- `GET /api/v1/simulation/infrastructure` — eight synthetic infrastructure assets and relationships.
- `GET /api/v1/simulation/scenarios` — deterministic scenario definitions.
- `POST /api/v1/simulation/runs` — generate and persist a complete seeded run.
- `GET /api/v1/simulation/runs` and `GET /api/v1/simulation/runs/{run_id}` — persisted runs.
- `GET /api/v1/telemetry/events` and `GET /api/v1/telemetry/events/{event_id}` — paginated synthetic telemetry.

## Phase 3B quick start

Start the migrated backend using the existing backend setup, then create a deterministic run:

```powershell
$request = @{
  scenario_id = 'credential-compromise'
  seed = 42
  start_time = '2026-07-21T01:30:00Z'
  playback_speed = 1.0
} | ConvertTo-Json

$run = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v1/simulation/runs' -ContentType 'application/json' -Body $request
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/telemetry/events?simulation_run_id=$($run.simulation_run_id)"
```

Open the dashboard and choose a scenario, seed, UTC start time, and speed. The browser creates the run over REST and opens the run-scoped WebSocket only after the user presses **Start Synthetic Simulation**. Protocol and test details are in [docs/PHASE_3B_REALTIME_PLAYBACK.md](docs/PHASE_3B_REALTIME_PLAYBACK.md).

All returned identities, assets, IP addresses, relationships, and events are synthetic. IP addresses use documentation-only ranges. The simulator never executes commands, scans networks, connects to devices, or performs containment.

## Current frontend routes

- `/` — implemented operational overview.
- `/digital-twin`, `/telemetry`, `/incidents`, `/mitre` — capability placeholders for Phases 3–5.
- `/response-centre`, `/audit-trail` — safe orchestration and audit placeholders for Phase 6.
- `/model-analytics` — synthetic model listing, training and benchmark evaluation; `/settings` remains a placeholder.

The UI integrates the three current REST endpoints. Its WebSocket client is a disconnected-by-default foundation supporting only acknowledgement and ping/pong.

> **Simulation-only UI:** A non-dismissible safety banner is visible on every route. Static fallback wording remains in place if the backend safety endpoint cannot be reached.

## Git workflow

Create focused feature branches, review `git status` before and after work, run all backend quality checks, and commit intentionally. Do not commit `.env`, virtual environments, SQLite files, generated logs, or test output.

## Current limitations

Phase 7A adds evidence-grounded synthetic defensive recommendations and clone-only digital-twin impact simulation. It calculates approval tiers but never approves or executes an action, and simulation scores are not containment probabilities. See [docs/PHASE_7A_RESPONSE_RECOMMENDATION_SIMULATION.md](docs/PHASE_7A_RESPONSE_RECOMMENDATION_SIMULATION.md).

Phase 6B animates the curated synthetic topology from ordered playback envelopes and provides exact-prefix REST recovery before WebSocket resume. Observed, anomalous, correlated, and predicted layers remain distinct evidence qualifications; none means confirmed compromise. See [docs/PHASE_6B_LIVE_DIGITAL_TWIN.md](docs/PHASE_6B_LIVE_DIGITAL_TWIN.md).

Phase 5A adds optional, causal incident-candidate correlation and a curated local MITRE ATT&CK subset. The two detection benchmark scenarios remain frozen; `staged-compromise-demo` is independent. Correlation streams only persisted synthetic evidence and never confirms an attack. See [docs/PHASE_5A_INCIDENT_CORRELATION_MITRE.md](docs/PHASE_5A_INCIDENT_CORRELATION_MITRE.md).

The backend remains synchronous, single-process, and SQLite-backed; model artifacts and their cache are process-local. Phase 4B optionally streams persisted synthetic assessments immediately after matching telemetry without changing telemetry-only clients. See [docs/PHASE_4B_LIVE_ANOMALY_INTEGRATION.md](docs/PHASE_4B_LIVE_ANOMALY_INTEGRATION.md). Authentication, production observability, incident correlation, MITRE mapping, interactive topology, prediction, agents, and response orchestration remain out of scope.

