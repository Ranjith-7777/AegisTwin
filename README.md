# AegisTwin

**AegisTwin: Agentic Cyber-Resilience Digital Twin for Critical National Infrastructure** is a hackathon prototype for reasoning over synthetic security telemetry and a simulated infrastructure twin.

> **Safety boundary:** AegisTwin operates exclusively on synthetic telemetry, simulated identities, simulated assets, and simulated response state. Real-world actions and external targets are prohibited. The backend refuses to start when `SIMULATION_ONLY=false`.

## Current phase

Phase 2A implements the backend and repository foundation only. There is no dashboard, telemetry generator, anomaly detection, incident correlation, MITRE ATT&CK mapping, digital twin, prediction, agent, or response implementation yet.

## Repository structure

```text
backend/       FastAPI, SQLAlchemy, Alembic, tests, and container files
datasets/      Synthetic/licensed dataset policy placeholder
docs/          Architecture and delivery planning
frontend/      Phase 2B placeholder
simulator/     Phase 3 placeholder
scripts/       Reserved for safe developer helpers
.github/       Backend continuous integration
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
docker compose build backend
docker compose up backend
docker compose config
```

Compose currently defines only the backend and uses a disposable named volume for SQLite data.

## Current interfaces

- `GET /api/health` — application and real database connectivity.
- `GET /api/system/status` — static foundation status; incident and agent counts remain zero.
- `GET /api/safety` — explicit simulation-only safety posture.
- `WS /ws/events` — connection acknowledgement and `ping`/`pong` only.
- OpenAPI UI: `GET /docs`.

## Git workflow

Create focused feature branches, review `git status` before and after work, run all backend quality checks, and commit intentionally. Do not commit `.env`, virtual environments, SQLite files, generated logs, or test output.

## Current limitations

This foundation is single-process and SQLite-backed. WebSocket connections are in-memory and have no durable replay. Authentication, authorisation, production observability, frontend functionality, security-event ingestion, analytics, twin state, and response capabilities are out of scope for Phase 2A.

