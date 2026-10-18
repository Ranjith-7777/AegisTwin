# AegisArena — Cloud Cyber Defence Range

AegisArena is a **simulation-only cyber range** for a small synthetic cloud estate.
A deterministic Red Agent replays seeded attack scenarios as synthetic telemetry.
An anomaly detector scores that telemetry. A correlation and prediction pipeline
turns the anomalies into incidents. A policy-governed Blue Agent then plans,
simulates, executes, verifies and (if needed) rolls back a mitigation, **only
against the digital twin**. An evaluation framework compares four defence
strategies on the same scenario and seed.

> **Safety boundary.** Every asset, identity, IP address, event, action and
> metric is synthetic. AegisArena never scans, connects to, or changes a real
> system. "Execution" means changing the state of the digital twin. The backend
> refuses to start with `SIMULATION_ONLY=false`.

![Command Centre after a contained attack](docs/ui/screenshots/final/06-command-centre-contained.png)

## The problem

Security teams rarely get to rehearse "detect → decide → act → verify" end to
end. Doing that on real infrastructure is unsafe, and the result can't be
reproduced. AegisArena gives you:

- a fixed synthetic estate;
- replayable, seeded attacks;
- the whole autonomous-defence loop, with every decision explained and audited;
- a fair, reproducible comparison against simpler defences.

## What it is, and what it is not

| It is | It is not |
|---|---|
| Deterministic, seeded scenario replay | Real attack tooling or traffic generation |
| scikit-learn IsolationForest plus a transparent hybrid score | A deep-learning or LLM detector |
| Rule and policy-driven agents with explicit scoring formulas | An LLM agent or a reinforcement-learning policy |
| Synthetic execution against a digital twin, with verification and rollback | Real containment of any system |
| Logical (simulated) time for timing metrics | Wall-clock incident-response benchmarks |

## Architecture

```text
 Browser (React 19 + Vite, nginx in containers)
   │  REST /api/v1/*  ·  WebSocket /api/v1/ws/simulation/runs/{id}
   ▼
 FastAPI backend (single process)
   ├─ Red Agent / Scenario Engine ── synthetic telemetry (seeded)
   ├─ Detection ── feature pipeline → IsolationForest + hybrid score (joblib artifacts)
   ├─ Incident intelligence ── correlation → MITRE ATT&CK subset → next-stage prediction
   ├─ Digital twin ── topology, attack graph, blast radius, what-if evidence
   ├─ Blue Agent (Workflow Coordinator)
   │     Response Planner → Impact Simulation → Safety Governor → Approval Router
   │     → Synthetic Execution → Verification   (+ rollback)
   ├─ Evaluation ── experiments, metrics, MCI, Aegis Resilience Score, comparison
   └─ Audit ── SHA-256 hash-chained events
   ▼
 SQLAlchemy 2 + Alembic ── SQLite (dev/demo) · PostgreSQL (production)
```

There is more detail in [docs/architecture/SYSTEM_OVERVIEW.md](docs/architecture/SYSTEM_OVERVIEW.md),
[AGENT_ARCHITECTURE.md](docs/architecture/AGENT_ARCHITECTURE.md) and
[DATA_FLOW.md](docs/architecture/DATA_FLOW.md).

### Red Agent
`backend/app/services/scenario_service.py` defines six seeded scenarios:

- `normal-operations`
- `credential-compromise`
- `staged-compromise-demo`
- `leaked-api-credential`
- `suspicious-kubernetes-pod`
- `ddos-traffic-spike`

The same scenario with the same seed always produces the same events. Events
stream to the UI over a run-scoped WebSocket, with exact-prefix REST recovery
if the connection drops.

### Detection
A feature pipeline builds causal behavioural features. An **IsolationForest**
plus a weighted hybrid score classifies each event. An *anomaly* means unusual
synthetic behaviour, not a confirmed attack. Model artifacts are saved
atomically to `MODEL_ARTIFACT_DIR`. If an artifact is missing (for example
after a container restart), it is rebuilt deterministically from its
persisted training configuration.

### Incident intelligence
Anomalies are correlated into **incident candidates**. Each candidate is mapped
to a curated local MITRE ATT&CK subset. A causal next-stage prediction then
proposes likely next techniques and target assets, which are clearly labelled
as hypotheses.

### Blue Agent and the autonomous workflow
The Workflow Coordinator chains six deterministic agents:

1. The **Response Planner** ranks the candidate playbooks.
2. The **Impact Simulation** agent runs a what-if on a clone of the twin.
3. The **Safety Governor** enforces policy.
4. The **Approval Router** applies the autonomy mode.
5. **Synthetic Execution** applies the chosen action to the twin.
6. **Verification** compares the expected and observed objectives.

Candidates are ranked by a published Response Utility Score:
security gain, critical-asset protection, blast-radius reduction, evidence
quality and reversibility, minus an operational-impact penalty
([formula](docs/architecture/BLUE_RESPONSE_PLANNING.md)). The UI's
"why this action" panel is derived only from those persisted numbers. No
generated text is involved.

There are four autonomy modes:

| Mode | Behaviour |
|---|---|
| `observe` | Detection and evidence only. No plan is created. |
| `recommend` | A plan is created. Nothing is executed. |
| `approval_required` | Waits for an operator to approve, then executes and verifies |
| `autonomous` | Executes and verifies automatically within policy; turning it on requires explicit confirmation |

Every state change is written to the hash-chained audit trail. An
administrator can roll back any synthetic execution.

### Digital twin
The interactive topology (`@xyflow/react`) shows three layers, kept visually
distinct:

- **evidence:** observed, anomalous, correlated, predicted;
- **proposed** mitigation: dashed, "fix proposed";
- **executed or restored** state: a cut edge `×`, "mitigated" or "restored".

A proposed action is never drawn as if it had been applied.

### Evaluation
An experiment replays one scenario and seed under one of four strategies:

- `no_active_defence`
- `rule_based`
- `ml_assisted`
- `agentic`

The metrics cover detection coverage and timeliness, attack-path,
blast-radius and critical-exposure reduction, operational disruption, false
positive rate, verification, recovery, the **Mission Continuity Index (MCI)**,
and the **Aegis Resilience Score**:
`ARS = 100 × (0.20·Awareness + 0.35·Containment + 0.25·Mission + 0.20·Recovery)`.
ARS is a deterministic evaluation score, not a probability. Timing metrics use
logical (simulated) time. See [docs/evaluation/](docs/evaluation/).

## Safety model

- `SIMULATION_ONLY` is enforced at startup. No module makes outbound network calls to targets.
- **Authentication.** In production, identity comes from Azure Container Apps Easy Auth (Entra ID) headers, which are trusted only when `TRUST_EASYAUTH_HEADERS=true` (set after Easy Auth is configured; otherwise callers are at most anonymous `VIEWER`), with role mapping (`VIEWER` / `ANALYST` / `ADMIN`; analysts approve, execute and verify, admins roll back). The development role bypass (`AUTH_DEV_BYPASS_ROLE`) is **rejected at startup** when `ENVIRONMENT=production`. See [docs/security/AUTHENTICATION.md](docs/security/AUTHENTICATION.md).
- **CORS** uses an explicit origin list (no wildcard) and the methods GET, POST, PUT and OPTIONS.
- **Autonomous mode** needs an explicit confirmation. Rollback needs the `ADMIN` role.
- **Audit.** Every agent decision, approval, execution, verification and rollback is hash-chained and verifiable from the UI (**Audit Trail → Verify Audit Chain**).

## Technology stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11–3.14, FastAPI, SQLAlchemy 2, Alembic, Pydantic Settings, scikit-learn, joblib |
| Frontend | React 19, TypeScript, Vite 7, Tailwind CSS v4, React Router 7, Axios, @xyflow/react, Recharts |
| Tests | pytest, ruff, mypy, Vitest + Testing Library, Playwright |
| Containers | Docker (non-root backend; nginx frontend on 8080 with `/api` and WebSocket proxy) |
| Cloud | Azure Container Apps, ACR, Key Vault, PostgreSQL Flexible Server, Azure Files, Log Analytics (Bicep) |

## Running locally

### One-click demo (Windows)
1. Run `SETUP_AEGISTWIN_DEMO.bat` once. It creates `backend/.venv` and installs dependencies.
2. Run `START_AEGISTWIN_DEMO.bat`. It:
   - migrates an isolated database in `.aegistwin-demo/`;
   - bootstraps the deterministic demo model;
   - builds the frontend;
   - opens `http://127.0.0.1:5173`.
3. When you're done, run `STOP_AEGISTWIN_DEMO.bat`. `RESET_AEGISTWIN_DEMO.bat -Force` returns the demo to a clean state.

The launcher binds only to `127.0.0.1`, and it runs with the local development
role `ADMIN` (shown in the header as a dev indicator). See
[docs/LOCAL_DEMO_GUIDE.md](docs/LOCAL_DEMO_GUIDE.md).

### Manual development setup
```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env        # set AUTH_DEV_BYPASS_ROLE=ADMIN for local use
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
```powershell
cd frontend
npm.cmd install
Copy-Item .env.example .env
npm.cmd run dev                     # http://localhost:5173
```

### Docker
```powershell
docker compose up --build           # frontend http://localhost:5173, backend http://localhost:8000
```
The frontend container's nginx proxies `/api/` and the playback WebSocket
(`/api/v1/ws/`) to the backend, so the browser uses same-origin URLs. The
SQLite database and model artifacts are kept on the `/data` volume.
`docker-compose.prod.yml` runs the same images with `ENVIRONMENT=production`
and no development bypass.

### Azure
`infra/azure/main.bicep` handles the one-time bootstrap, and `app.bicep`
handles each release. Together they provision:

- a Container App with the frontend and backend as sidecars;
- ACR;
- Key Vault, for the database URL secret;
- PostgreSQL Flexible Server;
- Log Analytics;
- an Azure Files share mounted at `/data`, for model artifacts.

The prerequisites are an Azure subscription with permission to create
resource groups and role assignments, Azure CLI with Bicep, an Entra ID app
registration for Easy Auth, and a GitHub OIDC federated credential for CI
releases. Nothing is deployed automatically. See
[docs/deployment/AZURE_DEPLOYMENT.md](docs/deployment/AZURE_DEPLOYMENT.md).

## Observability

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Liveness and database connectivity |
| `GET /api/system/status` | Environment, applied Alembic revision, counts |
| `GET /api/metrics` | Prometheus text: database-derived gauges (runs, anomalies, incidents, orchestrations, executions, verifications, rollbacks, audit events, experiments) and uptime |
| `GET /api/v1/session` | The caller's resolved role and auth mode |

Logs are structured. Every request is logged with its duration, and the
Workflow Coordinator logs `workflow_started` and `workflow_finished`. On Azure,
logs flow to Log Analytics.

## Tests

| Suite | Command | Last result |
|---|---|---|
| Backend unit/integration | `cd backend; python -m pytest` | 354 passed |
| Backend lint / format / types | `ruff check .` · `ruff format --check .` · `mypy app` | clean |
| Migrations | `alembic upgrade head` · `alembic check` | head `20261013_0019`, no drift |
| Frontend | `npm run lint` · `npm run typecheck` · `npx vitest run` · `npm run build` | 125 passed, build OK |
| End-to-end | `npx playwright test` (starts an isolated test backend) | 4 passed |

## Professor demo (about 10 minutes)

The screenshots are in [docs/ui/screenshots/final/](docs/ui/screenshots/final/).

1. **Command Centre** (`01`). Posture is *Standby*, and the stage rail is idle.
2. **Autonomous Workflow** → choose **Autonomous** → confirm (`02`).
3. **Red Agent**. Keep the defaults, `staged-compromise-demo` with seed 84, and select **Launch scenario** (`03`).
4. **Command Centre** (`04`) and **Digital Twin** (`05`). Watch the anomalies and the incident build on the twin as the replay plays.
5. When the replay finishes, the Blue workflow runs by itself. Posture moves to **Contained** (`06`), and the stage rail completes (`07`).
6. **Response Plans** (`08`) shows the candidates, the selected action and why it was chosen. **Digital Twin** (`09`) shows the executed edge cut.
7. **Verification** (`10`) shows expected vs observed. **Audit Trail → Verify Audit Chain** (`11`).
8. **Detection Models** (`12`) and **Incidents** (`13`) show the explainability.
9. **Evaluation → Strategy Comparison → Run all four strategies** (`14`), then **Experiments & Reports** (`15`).
10. **Command Centre → Roll back → Confirm**. Posture becomes **Restored** (`16`).

## Repository structure

```text
backend/    FastAPI app, services, Alembic migrations, tests
frontend/   React app, Vitest tests, Playwright e2e, nginx template
infra/      Azure Bicep (main.bicep bootstrap, app.bicep release, modules/)
scripts/    Demo launcher (PowerShell), bootstrap and benchmark helpers
docs/       Architecture, evaluation, security, deployment, UI, screenshots
simulator/  Simulator boundary notes and fixtures
```

## Limitations

- **The Mission Continuity Index is 0 for every strategy in the built-in scenarios.**
  - Exposure saturates the small estate before any response lands at the end of the replay.
  - This is documented and pinned by a test. The UI shows a caveat next to MCI.
  - ARS and the containment metrics are what differ between the strategies.
- **Execution is synthetic.** A "mitigated" asset is a state in the twin, not a changed system.
- **Agents are deterministic rules and formulas,** not learned policies or LLMs. Prediction is a causal hypothesis over a curated ATT&CK subset.
- **Timing metrics are in logical (simulated) time.**
- **The estate is small and fixed (eight assets).** Results don't generalise to real networks.
- **The backend is single-process.** Playback state and the model cache are per-process.
- **The Bicep templates haven't been compiled or deployed in this workspace,** because the Azure CLI and Bicep CLI are not installed here.

## Further documentation

- [docs/final/PROJECT_OVERVIEW.md](docs/final/PROJECT_OVERVIEW.md)
- [docs/final/FACULTY_DEMO.md](docs/final/FACULTY_DEMO.md)
- [docs/architecture/AUTONOMY_MODEL.md](docs/architecture/AUTONOMY_MODEL.md)
- [docs/architecture/VERIFICATION_AND_ROLLBACK.md](docs/architecture/VERIFICATION_AND_ROLLBACK.md)
- [docs/evaluation/AEGIS_RESILIENCE_SCORE.md](docs/evaluation/AEGIS_RESILIENCE_SCORE.md)
- [docs/evaluation/MISSION_CONTINUITY_INDEX.md](docs/evaluation/MISSION_CONTINUITY_INDEX.md)
- [docs/evaluation/EVALUATION_CONSISTENCY_FIX.md](docs/evaluation/EVALUATION_CONSISTENCY_FIX.md)
- [docs/ui/DESIGN_SYSTEM.md](docs/ui/DESIGN_SYSTEM.md)
- Historical phase notes: `docs/PHASE_*.md`. These are kept as project history and may describe earlier states.
