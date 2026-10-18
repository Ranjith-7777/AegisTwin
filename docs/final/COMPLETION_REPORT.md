# AegisArena — Completion Report (2026-10-18)

The implementation described here is tracked on `develop`. Phase 1 established
three local baseline commits for the backend/data path, release configuration,
and maintained documentation. Phase 2 verified the browser workflow and the
isolated Windows demo lifecycle. Nothing has been pushed during these phases.

## 1. Architecture

There is a single FastAPI process that holds:

- the Red Agent scenario engine;
- detection (IsolationForest with a hybrid score);
- correlation, MITRE mapping and prediction;
- the digital twin (topology, attack graph, blast radius, what-if evidence);
- the Blue Agent Workflow Coordinator, which chains six deterministic agents
  (Planner → Impact Simulation → Safety Governor → Approval Router →
  Synthetic Execution → Verification) plus rollback;
- evaluation (MCI and ARS);
- the SHA-256 hash-chained audit trail.

Persistence uses SQLAlchemy 2 with Alembic (head `20261013_0019`), on SQLite
or PostgreSQL. The React 19 SPA talks REST and a run-scoped WebSocket. In
containers, nginx serves the SPA and proxies `/api/` and `/api/v1/ws/`. Azure
runs both containers as sidecars in one Container App, with:

- PostgreSQL Flexible Server;
- Key Vault;
- ACR;
- Log Analytics;
- an Azure Files share for model artifacts.

## 2. User workflow

1. Choose an autonomy mode (Autonomous requires confirmation).
2. Launch a scenario and seed in the Red Agent lab.
3. Watch the telemetry, anomalies, incident and prediction build up on the
   Command Centre and the Digital Twin.
4. When the replay completes, the Blue workflow runs automatically. It plans,
   simulates, checks policy, then either waits for approval or executes,
   then verifies.
5. Inspect the candidates and "why this action", expected vs observed, and
   the audit chain.
6. Compare the four strategies under Evaluation.
7. Roll back (ADMIN).

## 3. UI summary

- A dark "midnight operations" design system ([DESIGN_SYSTEM.md](../ui/DESIGN_SYSTEM.md)).
- The header shows the run, the autonomy pill, the role, the environment and backend health.
- The Command Centre shows posture, an 8-step stage rail, KPIs, the twin, the active incident and the Blue decision panel.
- A new Autonomous Workflow page shows 14 stages.
- The twin shows separate evidence, proposed and executed layers, plus a legend and an inspector.
- The Red Agent lab defaults to the demo model.
- The Blue decision panel shows the "why" (derived from the persisted scores), with approve, reject and rollback dialogs.
- The Strategy Comparison page has "Run all four strategies" and logical-time labels.
- The Verification nav item shows a badge while an approval is pending.

## 4. Backend changes

- **Portable model artifacts** (`core/artifacts.py`). Records store file names, saves are atomic, and a missing artifact is rebuilt deterministically (`artifact_available`).
- **Configuration** (`config.py`):
  - CORS defaults cover both loopback origins, and loopback aliases expand outside production;
  - `AEGISARENA_DISABLE_DOTENV`;
  - `MODEL_ARTIFACT_DIR` is anchored to `backend/`.
- **New endpoints:**
  - `GET /api/v1/session`;
  - `GET /api/metrics` (Prometheus text from database counts).
  - `GET /api/v1/workflow/runs/{run_id}/state` restores a persisted workflow
    and returns `null` before a workflow exists, without treating normal empty
    state as an HTTP error.
  - `/api/system/status` now reports the real Alembic revision and the environment.
- **Migration** `20261007_0018` adds 32 ORM-declared indexes and drops one redundant index, so `alembic check` is clean.
- **Migration** `20261013_0019` adds recorded-data sources, normalized network
  flows, import diagnostics, and evaluation records.
- **Recorded-data analysis:** CICIDS2017 and canonical CSV adapters, validation,
  asset mapping, feature extraction, correlation, evaluation, and read-only API
  routes are implemented. This path never performs response execution.
- **Evaluation consistency fix.** Edge cuts are now credited the same way the Verification Agent credits them. For agentic on staged/84, ARS goes from 41.6 to 66.1. See [EVALUATION_CONSISTENCY_FIX.md](../evaluation/EVALUATION_CONSISTENCY_FIX.md).
- **Strategy comparison** now covers `false_positive_rate`, `time_to_incident` and `time_to_response`.
- **Logging.** The Workflow Coordinator logs `workflow_started` and `workflow_finished`. The bypass warning is logged once per role.

## 5. Frontend changes

- The design system was rewritten. There are new UI primitives (Panel, Metric, Dialog, Tip) and workflow components.
- `AutonomyWorkflowProvider`:
  - runs the workflow automatically after replay;
  - polls while an approval is pending;
  - runs approve → execute → verify.
- Stage derivation (`workflowStages.ts`), decision, posture and prediction helpers.
- Rewritten pages: Command Centre, Workflow, Digital Twin, Red Agent, Response Plans, Verification, Audit Trail, Blue Agent overview.
- Per-route API timeouts.
- `lastRun` resume.
- Twin semantics: correlated outranks anomalous, and the edge-cut marker.
- **Dead code removed.** These 20 files were unreferenced, several of them already at HEAD:
  - the old dashboard cards;
  - `PlaceholderPage`, `PageHeader`, `RedAgentPanel`;
  - `ErrorState`, `LoadingState`;
  - `useSystemHealth`, `useSystemStatus`;
  - `telemetryApi`, `websocketClient`.

## 6. Infrastructure changes

- **Docker:**
  - The backend image prepares a writable `/data` directory for the non-root user, with `MODEL_ARTIFACT_DIR=/data/models`.
  - The dev compose maps 5173 to nginx's port 8080 and uses same-origin URLs.
  - The prod compose persists model artifacts.
  - nginx upgrades the WebSocket and allows a 300 s API read timeout.
  - The frontend image is built with empty `VITE_*` URLs (same-origin). Before this, Azure browsers called their own `localhost`.
- **Bicep:**
  - The Key Vault name is unique per resource group.
  - The PostgreSQL connection string is URI-encoded.
  - A new `modelstorage.bicep` adds an Azure Files share mounted at `/data`.
- **Demo scripts:** they quote paths containing spaces, set the ADMIN dev role explicitly, and disable `.env`.

## 7. Verification status

| Check | Result |
|---|---|
| `pytest` (backend) | **374 passed, 1 skipped**, 3 dependency deprecation warnings; the skip is the absent local CICIDS2017 corpus |
| `ruff check .` / `ruff format --check .` | All checks passed / 210 files already formatted |
| `mypy app` | Success: no issues found in 147 source files |
| `alembic check` | No new upgrade operations detected |
| `npm run lint` / `typecheck` | 0 problems / clean |
| `vitest run` | **144 passed** (31 files) |
| `prettier --check .` | All matched files use Prettier code style |
| `npm run build` | built successfully |
| `playwright test` | **7 passed** after correcting the empty-workflow-state HTTP contract |
| Windows demo lifecycle | setup, start, health/status, `/app`, session role, and stop verified with isolated ports and storage |
| Docker image build / run | **not run in Phase 2** |
| Bicep compile / Azure deployment | **not run in Phase 2** |

## 8. Limitations

- MCI is 0 for every strategy in the built-in scenarios. This is documented, pinned by a test, and shown with a caveat in the UI.
- All execution is synthetic.
- The agents are deterministic rules, not LLMs or reinforcement-learning policies.
- Timing metrics use logical time.
- The estate is fixed at eight assets.
- The backend runs as a single process.
- Experiments persisted before the evaluation fix keep their old metric rows.
- The full CICIDS2017 labelled-flow corpus is not stored in Git. Its real-data
  acceptance test remains skipped until a user downloads it under
  `datasets/raw/cicids2017/`; fixture-based ingestion tests pass.
- Docker image execution, Bicep compilation, and a live Azure deployment remain
  environment-dependent and were not claimed as verified in Phase 2.
- **Internal identifiers keep the old `aegistwin` naming deliberately:**
  - catalogue versions;
  - the UUID namespace;
  - `AEGISTWIN_*` environment variables;
  - database and volume names;
  - the `*_AEGISTWIN_DEMO.bat` launchers.

  Renaming them would change deterministic IDs and orphan existing data.

## 9. Azure prerequisites

- A subscription with Owner (or Contributor plus User Access Administrator) to run the bootstrap.
- Azure CLI 2.6x or later with Bicep.
- An Entra ID app registration for Easy Auth, configured manually after the first deployment. Then set `TRUST_EASYAUTH_HEADERS=true`.
- A GitHub OIDC federated credential, plus the repository variables listed in [AZURE_DEPLOYMENT.md](../deployment/AZURE_DEPLOYMENT.md).
- A PostgreSQL admin password supplied at deploy time.
- Before the first `create`, run `az bicep build` and `az deployment sub what-if`.

## 10. Professor demo procedure

1. Run `RESET_AEGISTWIN_DEMO.bat -Force`, then `START_AEGISTWIN_DEMO.bat`.
2. Follow the ten steps in the [README](../../README.md#professor-demo-about-10-minutes):
   Autonomous mode → launch staged-compromise-demo with seed 84 → watch it
   contained → Response Plans "why" → Verification → audit chain →
   Detection and Incidents → run all four strategies → roll back to *Restored*.

The current launcher was verified in Development mode with a new temporary
demo root, dedicated ports, one bootstrapped model, an ADMIN demo session, and
simulation-only health. The browser E2E suite separately verified the complete
autonomous workflow, verification, audit integrity, rollback, authentication
entry, and mobile viewport with no console errors.

## 11. Screenshot list (`docs/ui/screenshots/final/`)

These captures are generated local demonstration artifacts and are ignored by
Git. They remain on disk and can be regenerated without affecting source state.

1. `01-command-centre-standby`
2. `02-autonomy-confirmation`
3. `03-red-agent-lab`
4. `04-command-centre-under-attack`
5. `05-digital-twin-attack-replay`
6. `06-command-centre-contained`
7. `07-autonomous-workflow-complete`
8. `08-blue-agent-candidates-and-why`
9. `09-digital-twin-mitigated`
10. `10-verification-expected-vs-observed`
11. `11-audit-chain-verified`
12. `12-detection-explainability`
13. `13-incident-intelligence`
14. `14-strategy-comparison`
15. `15-experiments-reports`
16. `16-command-centre-rolled-back`

## 12. Git baseline

Phase 1 committed all reviewed source, configuration, tests, and maintained
documentation in three logical commits. Raw datasets, databases, logs, caches,
model artifacts, Playwright output, and generated UI captures are excluded.
Phase 2 adds only the launcher-route correction, generated-artifact ignore
rules, the empty-workflow-state contract fix and regression test, and current
documentation. No branch was switched, no history was rewritten, and no commit
was pushed or deployed.
