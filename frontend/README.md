# AegisArena Frontend

The operator console for AegisArena: React 19, TypeScript, Vite 7,
Tailwind CSS v4, React Router 7, Axios, @xyflow/react and Recharts. For the
product overview, see the [root README](../README.md). For the visual
language, see [docs/ui/DESIGN_SYSTEM.md](../docs/ui/DESIGN_SYSTEM.md).

## Structure

```text
src/app/          Router, providers (simulation playback, autonomous workflow)
src/pages/        Command Centre, Workflow, Red Agent, Digital Twin, Blue Agent,
                  Incidents, Evaluation, Audit Trail, Detection Models, ...
src/components/   ui/ (Button, Card, Badge, Panel, Dialog), layout/, workflow/,
                  topology/, detection/, common/
src/lib/          routes, workflowStages, decision, posture, prediction, autonomy
src/services/     typed REST clients (apiClient with per-route timeout policy)
src/test/         Vitest + Testing Library suites
e2e/              Playwright end-to-end tests (isolated test backend)
```

## Run locally

```powershell
Set-Location '<path-to-repo>\frontend'
npm.cmd install
Copy-Item .env.example .env
npm.cmd run dev                 # http://localhost:5173
```

Start the backend on `http://127.0.0.1:8000` with `AUTH_DEV_BYPASS_ROLE=ADMIN`
(see `backend/.env.example`). Without it, the console is read-only. The
header shows the backend health and your resolved role.

## Configuration

```text
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

These are public browser endpoints, not secrets. When they are **empty** (as
in the Docker and Azure image builds), the app uses its own origin, and nginx
proxies `/api/` and `/api/v1/ws/` to the backend.

## Quality commands

```powershell
npm.cmd run lint
npm.cmd run format:check
npm.cmd run typecheck
npm.cmd run test:run
npm.cmd run build
npm.cmd run test:e2e            # needs Playwright Chromium: npx playwright install chromium
```

## Notes

- Every value shown comes from the backend. A missing value is shown as `—`, never invented.
- Proposed mitigations are never drawn as executed ones. The twin keeps the evidence, proposed and executed layers separate.
- The simulation-only notice appears on every route.
