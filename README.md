# AegisTwin

**AegisTwin: Agentic Cyber-Resilience Digital Twin for Critical National Infrastructure** is a hackathon prototype for reasoning over synthetic security telemetry and a simulated infrastructure twin.

> **Safety boundary:** AegisTwin operates exclusively on synthetic telemetry, simulated identities, simulated assets, and simulated response state. Real-world actions and external targets are prohibited. The backend refuses to start when `SIMULATION_ONLY=false`.

## Current phase

Phase 3A adds typed telemetry contracts and a deterministic synthetic simulation engine to the Phase 2A backend and Phase 2B dashboard foundation. Two seeded scenarios, a synthetic infrastructure inventory, SQLite persistence, and versioned query APIs are implemented. Anomaly detection, incident correlation, ATT&CK mapping, prediction, agents, and response orchestration remain intentionally deferred.

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

## Phase 3A quick start

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

All returned identities, assets, IP addresses, relationships, and events are synthetic. IP addresses use documentation-only ranges. The simulator never executes commands, scans networks, connects to devices, or performs containment.

## Current frontend routes

- `/` — implemented operational overview.
- `/digital-twin`, `/telemetry`, `/incidents`, `/mitre` — capability placeholders for Phases 3–5.
- `/response-centre`, `/audit-trail` — safe orchestration and audit placeholders for Phase 6.
- `/model-analytics`, `/settings` — later-phase placeholders.

The UI integrates the three current REST endpoints. Its WebSocket client is a disconnected-by-default foundation supporting only acknowledgement and ping/pong.

> **Simulation-only UI:** A non-dismissible safety banner is visible on every route. Static fallback wording remains in place if the backend safety endpoint cannot be reached.

## Git workflow

Create focused feature branches, review `git status` before and after work, run all backend quality checks, and commit intentionally. Do not commit `.env`, virtual environments, SQLite files, generated logs, or test output.

## Current limitations

The backend remains single-process and SQLite-backed. Scenario execution currently generates the full sequence immediately rather than replaying events over wall-clock time. WebSocket connections are unchanged and do not stream telemetry. The frontend is unchanged and does not query the new telemetry APIs. Authentication, production observability, anomaly detection, incident correlation, MITRE mapping, interactive topology, prediction, agents, and response orchestration remain out of scope.

