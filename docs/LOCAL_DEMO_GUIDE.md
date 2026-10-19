# Local Demo Guide (AegisArena)

All data, analytics, recommendations, approvals, executions, and evidence are
synthetic. The launcher binds only to `127.0.0.1` and uses `.aegistwin-demo/`; it
never reuses `backend/aegistwin.db`. (The `AEGISTWIN` file names are kept from the
project's earlier name so existing shortcuts keep working.)

## Prerequisites and first use

- Windows 10/11 with PowerShell 5.1 or newer
- Python 3.11-3.14
- Node.js 20-24 with npm
- At least 1 GB free space

Run `SETUP_AEGISTWIN_DEMO.bat` once. It creates `backend/.venv` and installs the
project's dependencies. Add `-InstallPlaywright` only if you want the Chromium
browser for browser tests. Setup never installs it silently. Paths that contain
spaces are supported.

## One-click production launch

Run `START_AEGISTWIN_DEMO.bat`. It runs these steps in order:

1. Validates prerequisites and ports.
2. Migrates an isolated database.
3. Creates or reuses the deterministic demo detection model.
4. Builds the frontend.
5. Starts both services and verifies they are ready.
6. Opens `http://127.0.0.1:5173/app`.

The launcher runs the backend with:

- `ENVIRONMENT=demo`
- `AUTH_DEV_BYPASS_ROLE=ADMIN`
- `AEGISARENA_DISABLE_DOTENV=1`

So every Blue Agent action is available, and the header shows **ADMIN · dev**.
A personal `backend/.env` is never read. This role exists only on localhost.
The production compose file and Azure never set it.

PowerShell options:

- `-Mode Development|Production` (Production is the default)
- `-BackendPort`
- `-FrontendPort`
- `-NoBrowser`
- `-Reset`
- `-SkipModelBootstrap`
- `-OpenPage overview|digital-twin|blue-agent|response-plans|verification|audit-trail`

The page names resolve to the current React routes: `overview` opens `/app`,
`blue-agent` opens `/blue-agent/overview`, `response-plans` opens
`/blue-agent/response-plans`, and `verification` opens
`/blue-agent/verification`.

To manage the demo:

- `STATUS_AEGISTWIN_DEMO.bat` shows its status.
- `STOP_AEGISTWIN_DEMO.bat` stops it.
- `RESET_AEGISTWIN_DEMO.bat -Force` deletes only `.aegistwin-demo`. It accepts `-KeepLogs`, `-KeepReports` and `-SkipModelBootstrap`.

The runtime directory contains:

- `data/aegistwin-demo.db`
- `model-artifacts/`
- `reports/`
- separate service and launcher logs
- `runtime/processes.json`

## Demo flow

The full ten-step walkthrough with screenshots is in the
[README](../README.md#professor-demo-about-10-minutes). In short:

1. Turn on **Autonomous** mode (it asks for confirmation).
2. Launch `staged-compromise-demo` with seed 84 from **Red Agent**.
3. Watch the Command Centre and the Digital Twin. When the replay finishes,
   the Blue workflow plans, executes and verifies a synthetic edge cut.
4. Inspect Response Plans, Verification and Audit Trail.
5. Run all four strategies under Evaluation.
6. Roll back from the Command Centre.

If you choose **Approval required** instead of Autonomous, the workflow stops
at *Awaiting approval*. The Verification nav item then shows a badge, and you
can approve from the Command Centre decision panel.

The deterministic demo detection model (`random_state` 17, the same configuration the launcher bootstraps) is selected by
default in the Red Agent lab. If it is missing, select **Train the demo model**.
Nothing ever starts automatically, and nothing bypasses policy.
