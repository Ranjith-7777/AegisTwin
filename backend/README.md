# AegisTwin Backend and Synthetic Telemetry Foundation

The Windows judge launcher runs this API in non-debug simulation-only mode against `.aegistwin-demo/data/aegistwin-demo.db`; it never reuses the developer database.

Phase 8A validates artifact-directory availability at startup, defaults debug mode off, and supplies isolated bootstrap, benchmark, migration, and release-validation tooling. SQLite remains a documented single-worker prototype constraint.

Phase 7B adds deterministic simulation agents, approval gates, persisted synthetic execution, verification, rollback, and SHA-256 audit-chain verification. It performs no real action.

Phase 6A exposes the repository-defined infrastructure as a versioned directed topology under `/api/v1/topology`, including sequence-bounded path and run-state queries.

Phase 5B exposes versioned prediction snapshots, ranked hypotheses, staged-demo evaluation, and causally ordered playback under `/api/v1/prediction`.

Python 3.11+ is required. The service refuses to start unless simulation-only mode is enabled. Run commands from the `backend` directory.

Phase 4A.1 hardens offline IsolationForest detection with causal context features, a separate synthetic benchmark manifest, three normal-only calibration methods, auditable hybrid scoring, and run-level diagnostics. Anomalous means unusual relative to synthetic normal training; it never means a confirmed attack. Live anomaly streaming, incident correlation, ATT&CK mapping, commands, device contact, scanning, and response actions are absent.

## Windows CMD

```bat
cd backend
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
copy .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another activated CMD session:

```bat
cd backend
.venv\Scripts\activate.bat
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m ruff format .
python -m mypy app tests
```

## Windows PowerShell

```powershell
Set-Location backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In another activated PowerShell session:

```powershell
Set-Location backend
.\.venv\Scripts\Activate.ps1
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m ruff format .
python -m mypy app tests
```

If PowerShell blocks activation, use `Set-ExecutionPolicy -Scope Process RemoteSigned` for the current process only, or invoke `.venv\Scripts\python.exe -m ...` directly.

## Migrations

Apply committed migrations with `python -m alembic upgrade head`. Generate a future reviewed migration with `python -m alembic revision --autogenerate -m "description"`. Do not perform destructive downgrades as part of normal setup.

## Configuration

Settings are read from environment variables and an optional local `.env`. `CORS_ORIGINS` accepts a comma-separated string or JSON array. Never commit `.env`. `SIMULATION_ONLY=false` is prohibited and prevents startup.

## Telemetry event contract

Every event contains `event_id`, `scenario_id`, `simulation_run_id`, UTC `timestamp`, `event_type`, `action`, `outcome`, `severity`, source/destination identifiers and documentation-range IPs, optional synthetic user/device/process context, privilege level, failed-attempt and byte counts, typed metadata, and `created_at`. Metadata always contains `synthetic: true` and the scenario-step number. There is no anomaly score, attack verdict, or real target information.

## Available scenarios

- `normal-operations`: office-hours login, portal access, application request, database query, small transfer, and logout.
- `credential-compromise`: suspicious-looking synthetic failures, unusual-hour login, unseen synthetic device, privilege change, internal access, and large transfer to a simulation sink. This is exercise data, not a confirmed attack.

The same scenario, seed, UTC start time, and playback speed produce the same run ID and exact event sequence. Repeating an identical request returns the already persisted deterministic run.

## Phase 3A API

```text
GET  /api/v1/simulation/infrastructure
GET  /api/v1/simulation/scenarios
GET  /api/v1/simulation/scenarios/{scenario_id}
POST /api/v1/simulation/runs
GET  /api/v1/simulation/runs
GET  /api/v1/simulation/runs/{run_id}
GET  /api/v1/simulation/runs/{run_id}/playback
GET  /api/v1/telemetry/events
GET  /api/v1/telemetry/events/{event_id}
WS   /api/v1/ws/simulation/runs/{run_id}?after_sequence=0
POST /api/v1/detection/models/train
GET  /api/v1/detection/models
GET  /api/v1/detection/models/{model_id}
POST /api/v1/detection/runs/{run_id}/score
GET  /api/v1/detection/runs/{run_id}/assessments
POST /api/v1/detection/models/{model_id}/evaluate
GET  /api/v1/detection/evaluations/{evaluation_id}
```

The playback socket first emits `connection_ack` and `playback_snapshot`. Clients then send `start`, `pause`, `resume`, `stop`, or `ping`. Server envelopes are ordered and explicitly marked `synthetic: true`. Timing uses persisted timestamp deltas divided by run speed. Each connection owns its controller, so one client cannot pause another.

Detection artifacts default to `artifacts/models` and can be relocated with `MODEL_ARTIFACT_DIR`. Training seed ranges, validation seed ranges, evaluation seed ranges, model random state, and target false-positive rate are request-configurable and reproducible. Apply Alembic before using detection APIs. Full feature, calibration, evaluation, and REST documentation is in `docs/PHASE_4A_ANOMALY_DETECTION.md`.

The default feature schema is `synthetic-behaviour-v2` and the default calibration is `interpolated-ecdf-v2`. Training also accepts bounded estimator, sample-fraction, feature-fraction, calibration-method, and hybrid-score settings. Migration `20260721_0004` adds component-score audit fields and structured evaluation diagnostics. See `docs/PHASE_4A1_DETECTION_HARDENING.md`.

Phase 4B extends the start control with optional `detection_enabled` and `model_id` fields. Detection mode validates already-persisted assessments and emits each `anomaly_assessment` immediately after its `telemetry_event`; the original start control remains telemetry-only. Artifacts are cached per process by resolved path and modification time, with explicit test isolation. Missing artifacts or incomplete assessments produce structured detection errors or warnings and never fabricated scores. See `docs/PHASE_4B_LIVE_ANOMALY_INTEGRATION.md`.

Phase 5A adds `POST /api/v1/correlation/runs/{run_id}/analyze`, incident/evidence queries, local MITRE catalogue endpoints, and optional correlation playback. Causal ordering is telemetry, assessment, technique observations, then candidate update. Mapping and correlation require persisted synthetic evidence; see `docs/PHASE_5A_INCIDENT_CORRELATION_MITRE.md`.

Telemetry query parameters are `page`, `page_size`, `simulation_run_id`, `event_type`, `source_id`, `user_id`, and `minimum_severity`.

Phase 7A adds `/api/v1/response` catalogue, analysis, recommendation, simulation, and summary endpoints. All results are causal, persisted, synthetic, and evaluated against a cloned topology only; no response is approved or executed. See `docs/PHASE_7A_RESPONSE_RECOMMENDATION_SIMULATION.md`.

Phase 6B extends run topology recovery with causal event mappings and observed, anomalous, unexpected, correlated, and hypothetical predicted layers. Recovery is derived from persisted synthetic evidence through an explicit sequence limit; it performs no discovery or real-world action. See `docs/PHASE_6B_LIVE_DIGITAL_TWIN.md`.

### Windows CMD example

```bat
cd /d D:\Ranjith\ET_2.0\AegisTwin\backend
.venv\Scripts\activate.bat
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
curl.exe -X POST http://127.0.0.1:8000/api/v1/simulation/runs -H "Content-Type: application/json" -d "{\"scenario_id\":\"normal-operations\",\"seed\":7,\"start_time\":\"2026-07-21T09:00:00Z\",\"playback_speed\":1.0}"
```

### PowerShell example

```powershell
Set-Location 'D:\Ranjith\ET_2.0\AegisTwin\backend'
.\.venv\Scripts\Activate.ps1
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

$body = @{ scenario_id = 'normal-operations'; seed = 7; start_time = '2026-07-21T09:00:00Z'; playback_speed = 1.0 } | ConvertTo-Json
$run = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v1/simulation/runs' -ContentType 'application/json' -Body $body
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/telemetry/events?simulation_run_id=$($run.simulation_run_id)&page=1&page_size=50"
```

All generated data is synthetic and confined to the local application database.

