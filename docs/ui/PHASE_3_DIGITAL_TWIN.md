# Phase 3 Digital Twin UI

The Digital Twin page (`frontend/src/pages/DigitalTwinPage.tsx`) gained a
four-tab structure this phase, preserving the Phase 2 light design
language (`docs/ui/PHASE_2_DESIGN_SYSTEM.md`) — the existing `Card`,
`Button`, `chip` primitives, and page-heading conventions are reused
unchanged; no new design tokens or CSS were introduced.

## Tabs

| Tab | Contents | Backing service |
|---|---|---|
| Topology | Everything that existed before this phase — the graph canvas, run/model/sequence controls, layer toggles, asset/relationship inspectors, path inspection, topology history. Unchanged. | `topologyApi.ts` (existing) |
| Attack Paths | `AttackPathsPanel.tsx` — source/target/path-type selectors, calls `attackGraphApi.analyzeAttackPaths`, renders each returned path's statement, ordered steps (with semantics, privilege, and trust-boundary-crossing flags), and the full score breakdown. | `attackGraphApi.ts` (new) |
| Blast Radius | `BlastRadiusPanel.tsx` — checkbox multi-select of compromised assets, calls `blastRadiusApi.estimateBlastRadius`, renders the statement, summary counts, and the four asset-id lists (reachable/dependent/critical/zones). | `blastRadiusApi.ts` (new) |
| Purple Team | `PurpleTeamPanel.tsx` — scenario/mode/seed selectors (scenario list from `purpleTeamApi.listRedScenarios`), calls `purpleTeamApi.runPurpleTeamExperiment`, renders the summary metrics and a per-step outcome table. | `purpleTeamApi.ts` (new) |

Switching tabs never triggers a new topology/run fetch — the existing
`runId` / `modelId` / `sequence` state (already URL-persisted from Phase
2) is passed down to the Attack Paths and Blast Radius tabs so they can
optionally scope their queries to the same run context the Topology tab
is showing, without owning a second copy of that state.

## Why no separate route

Each new capability is a tab within `/digital-twin`, not a new route,
because all three are views *over the same Digital Twin data* the
Topology tab already fetches (or, for Purple Team, views over a
pipeline run whose backing run/model IDs belong in the same run-context
model) — matching the phase instruction that Command Centre gets only
small additive integrations while the Digital Twin page itself absorbs
the bulk of the new UI.

## Command Centre

Per the phase's "small additive integrations only" instruction, the
Command Centre was not restructured. (A future pass could surface a
"Top attack path" or "Latest Purple Team result" summary card there,
sourced from the same new services — not done in this phase to avoid
scope creep beyond what was requested.)

## New frontend files

- `src/types/attackGraph.ts`, `blastRadius.ts`, `purpleTeam.ts` — typed
  response shapes mirroring the backend Pydantic schemas field-for-field.
- `src/services/attackGraphApi.ts`, `blastRadiusApi.ts`,
  `purpleTeamApi.ts` — thin, validated API clients following this
  codebase's existing `record()`-guard + typed-cast convention (see
  `responseApi.ts` for the established pattern).
- `src/components/topology/AttackPathsPanel.tsx`, `BlastRadiusPanel.tsx`,
  `PurpleTeamPanel.tsx` — self-contained panels, each owning its own
  query state and loading/error handling, matching how the existing
  Topology sub-panels (`TopologyPanels.tsx`) are structured.

## Verification

Manually exercised end-to-end against a live backend in the browser
(all three new tabs, including a `defense_enabled` Purple Team
experiment that genuinely reached `response_executed: true`) — see
`docs/ui/screenshots/phase-3/`. `npm run typecheck`, `npm run lint`,
`npm run format:check`, and `npm run test:run` (47 tests) all pass; the
production build (`npm run build`) completes cleanly.
