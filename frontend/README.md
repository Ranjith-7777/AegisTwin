# AegisTwin Frontend Dashboard Foundation

Phase 2B provides a React, TypeScript, Vite, Tailwind CSS, shadcn/ui-style component, React Router, Axios, Lucide, and Recharts dashboard foundation. It is dark by default, responsive, and permanently identifies itself as a simulation environment.

The dashboard reads `GET /api/health`, `GET /api/system/status`, and `GET /api/safety`. It remains usable when the backend is offline and does not present fallback values as live data. The typed WebSocket client supports only connection acknowledgement and ping/pong; it does not auto-connect or display telemetry.

## Windows CMD

```bat
cd /d D:\Ranjith\ET_2.0\AegisTwin\frontend
npm install
copy .env.example .env
npm run dev
```

## Windows PowerShell

```powershell
Set-Location 'D:\Ranjith\ET_2.0\AegisTwin\frontend'
npm.cmd install
Copy-Item .env.example .env
npm.cmd run dev
```

If PowerShell script execution prevents `npm`, use `npm.cmd` as shown.

## Configuration

```text
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
```

These are public browser endpoints, not secrets. Copy `.env.example` to `.env`; never add credentials.

## Quality commands

```powershell
npm.cmd run lint
npm.cmd run format:check
npm.cmd run typecheck
npm.cmd run test:run
npm.cmd run build
```

Use `npm.cmd run format` to apply Prettier. `npm.cmd run preview` serves the production build locally.

## Routes

`/` implements the overview. `/digital-twin`, `/telemetry`, `/incidents`, `/mitre`, `/response-centre`, `/audit-trail`, `/model-analytics`, and `/settings` are polished, explicitly deferred placeholders. Unknown paths render a 404 page.

## Open-source foundation

The component approach is adapted from the open-source shadcn/ui conventions and official dashboard patterns. It uses Radix UI Slot and retains project-owned component source for adaptation. Package licences remain available through their respective distributions.

## Current limitations

No attack simulation, real-time event workflow, anomaly detection, incident correlation, MITRE mapping, React Flow topology, prediction, agent, or response orchestration exists. Sample chart and event data are deterministic, isolated in `src/mocks/`, and visibly labelled illustrative.
