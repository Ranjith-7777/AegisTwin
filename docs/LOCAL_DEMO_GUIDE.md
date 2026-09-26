# Local Judge Demo

All data, analytics, recommendations, approvals, executions, and evidence are synthetic. The launcher binds only to `127.0.0.1` and uses `.aegistwin-demo`; it never reuses `backend/aegistwin.db`.

## Prerequisites and first use

- Windows 10/11 with PowerShell 5.1 or newer
- Python 3.11-3.14
- Node.js 20-24 with npm
- At least 1 GB free space

Run `SETUP_AEGISTWIN_DEMO.bat` once. It creates `backend/.venv` and installs project dependencies. Add `-InstallPlaywright` only when browser-test Chromium is wanted; setup never silently installs it.

## One-click production launch

Run `START_AEGISTWIN_DEMO.bat`. It validates prerequisites and ports, migrates an isolated database, creates or reuses one deterministic model, builds the frontend, starts both services, verifies readiness, and opens `http://127.0.0.1:5173`.

PowerShell options include `-Mode Development|Production`, `-BackendPort`, `-FrontendPort`, `-NoBrowser`, `-Reset`, `-SkipModelBootstrap`, and `-OpenPage overview|digital-twin|response-centre|response-operations|audit-trail`. Production is the default.

Use `STATUS_AEGISTWIN_DEMO.bat`, `STOP_AEGISTWIN_DEMO.bat`, and `RESET_AEGISTWIN_DEMO.bat -Force`. Reset deletes only `.aegistwin-demo`; `-KeepLogs`, `-KeepReports`, and `-SkipModelBootstrap` are supported.

Runtime layout contains `data/aegistwin-demo.db`, `model-artifacts/`, `reports/`, separate service and launcher logs, and `runtime/processes.json`.

Judge Demo Mode prepares deterministic seed 84, staged-compromise configuration, scoring, correlation, and top-three prediction. It never starts automatically and never bypasses policy or human approval.
