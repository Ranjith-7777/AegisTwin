# Phase 3B: Real-Time Synthetic Telemetry Playback

Phase 3B turns persisted Phase 3A events into a controlled dashboard stream. It remains entirely simulation-only: no message is an attack verdict, no external target is contacted, and no response action is available.

## Flow

1. The dashboard loads scenarios and persisted run history over REST.
2. An explicit start action creates a deterministic run with scenario, seed, UTC start time, and playback speed.
3. The browser connects to `WS /api/v1/ws/simulation/runs/{run_id}?after_sequence=0`.
4. The server sends `connection_ack` and `playback_snapshot`; the browser sends `start`.
5. Persisted events arrive in stable sequence order. Delay equals the timestamp delta from the preceding event divided by playback speed.
6. Pause, resume, and stop are client control messages. Completion and errors are explicit server states.
7. Retry reconnects with `after_sequence` set to the last rendered event index.

Every server envelope includes `message_type`, `run_id`, `sequence_number`, `server_timestamp`, `synthetic: true`, and a typed payload. Malformed client messages receive structured errors. Missing runs and invalid resume positions are rejected explicitly. Playback controllers are per connection, so concurrent clients do not share pause or stop state.

## Dashboard behavior

The overview and telemetry pages expose scenario selection, seed, UTC start time, playback speed, connection status, playback state, position, simulated elapsed time, bounded incremental rendering, optional auto-scroll, and factual run history. The UI never labels suspicious-looking exercise data as a confirmed attack and leaves unrelated metrics unavailable.

## Validation

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy app tests
.\.venv\Scripts\python.exe -m pytest
```

From `frontend/`:

```powershell
npm.cmd run lint
npm.cmd run format:check
npm.cmd run typecheck
npm.cmd run test:run
npm.cmd run build
```

Backend tests cover ordering, controls, malformed input, missing runs, completion, resume, heartbeat, stop, and client isolation. Frontend tests cover disconnected-by-default behavior, scenario loading, run creation, acknowledgement, incremental rendering, controls, errors, retry, cleanup, and the absence of fabricated detection or response values.
