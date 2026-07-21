# AegisTwin Frontend Dashboard Foundation

Phase 3B connects the React dashboard foundation to deterministic synthetic simulation runs and controlled real-time playback. It is dark by default, responsive, and permanently identifies itself as a simulation environment.

The dashboard reads health and safety status, loads synthetic scenarios and run history, creates runs over REST, and opens a typed run-scoped WebSocket only after an explicit user action. It renders no fabricated anomaly, incident, MTTD, or MTTR values.

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

Playback streams only persisted synthetic events and keeps at most 200 rendered rows. There is no anomaly detection, incident correlation, MITRE mapping, React Flow topology, prediction, agent, or response orchestration.
