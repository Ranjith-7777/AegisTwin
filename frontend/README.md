# AegisTwin Frontend Dashboard Foundation

Phase 8A adds explicit Demo Mode, Playwright Chromium E2E coverage, same-origin-safe production URL fallbacks, and lazy/vendor chunk splitting. Run `npm run test:e2e` after installing the pinned Playwright Chromium runtime.

Phase 7B adds Response Operations, a functional Audit Trail, incident workflow context, and distinct applied/rollback synthetic-twin overlays.

Phase 6A replaces the Digital Twin placeholder with a reusable React Flow topology, asset and relationship inspectors, layer controls, and cautious path inspection.

Phase 6B drives that topology from ordered playback messages. The Overview card and full Digital Twin share reducer state, expose event history and evidence details, separate observed/correlated/predicted semantics, and recover an exact sequence prefix before WebSocket resume. See `../docs/PHASE_6B_LIVE_DIGITAL_TWIN.md`.

Phase 7A replaces the Response Centre placeholder with sequence-bounded recommendation ranking, approval-tier display, component/penalty inspection, and baseline-versus-cloned-topology impact comparison. Incident, prediction, and topology views expose qualified response context without implying execution. See `../docs/PHASE_7A_RESPONSE_RECOMMENDATION_SIMULATION.md`.

Phase 5B adds opt-in prediction controls, a live ranked-hypothesis panel, and `/predictive-analytics` for snapshot and outcome review.

Phase 3B connects the React dashboard foundation to deterministic synthetic simulation runs and controlled real-time playback. It is dark by default, responsive, and permanently identifies itself as a simulation environment.

The dashboard reads health and safety status, loads synthetic scenarios, run history and detection models, scores a run before optional assessment playback, and opens a typed run-scoped WebSocket only after an explicit user action. It renders persisted synthetic anomaly values but no fabricated incident, MTTD, MTTR or confirmed-attack values.

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

`/` implements simulation controls, live telemetry and anomaly assessment views. `/model-analytics` implements model listing, synthetic training and benchmark evaluation. The remaining named routes are explicitly deferred placeholders. Unknown paths render a 404 page.

## Open-source foundation

The component approach is adapted from the open-source shadcn/ui conventions and official dashboard patterns. It uses Radix UI Slot and retains project-owned component source for adaptation. Package licences remain available through their respective distributions.

## Current limitations

The overview can optionally prepare and stream causal correlation after detection scoring. `/incidents` is the Incident Candidates workspace and `/mitre` separates the local catalogue from actual persisted observations. All values are synthetic evidence heuristics, not attack probabilities or confirmed incidents.

Playback keeps at most 200 rendered telemetry rows. Detection is optional and uses only offline persisted assessments. Topology animation is a synthetic evidence projection, not infrastructure discovery or confirmed compromise. There is no agent or response orchestration.
