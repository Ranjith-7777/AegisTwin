# Demo Troubleshooting

- **Python missing/unsupported:** install Python 3.11-3.14 and rerun setup.
- **Node/npm missing:** install Node.js 20-24 and reopen the terminal.
- **Dependency error:** rerun setup; use `-ForceReinstall` only after reviewing its prompt.
- **Port occupied:** select alternative ports. The launcher never kills unknown processes.
- **Backend unavailable:** inspect `backend-error.log`; migrations and artifact checks must pass.
- **Frontend unavailable:** inspect `frontend-error.log` and `frontend-build.log`.
- **Stale process record:** stop is idempotent and cleans metadata.
- **Model absent:** restart without `-SkipModelBootstrap` or perform a safe reset.
- **Browser did not open:** use the printed URL.

Do not share environment files or logs publicly without reviewing them, although launchers never write credentials.
