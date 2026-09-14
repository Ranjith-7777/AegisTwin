# Phase 4 Blue Agent UI

The Phase 3 `ResponseCentrePage` (`/response-centre`) and
`ResponseOperationsPage` (`/response-operations`) are replaced this phase
by 5 tabs under one "Defense" sidebar section, matching the Phase 4 spec's
required structure exactly and reusing the Phase 2 light design system
unchanged (`Card`, `Button`, `Badge`, `chip`/`eyebrow`/`panel-title`
primitives — no new design tokens or CSS were introduced,
`docs/ui/PHASE_2_DESIGN_SYSTEM.md`).

## Tabs (`frontend/src/pages/blueAgent/`)

| Tab | Route | Contents |
|---|---|---|
| Overview | `/blue-agent/overview` | Real autonomy mode + description, and — if an orchestration is selected — its incident, selected plan, orchestration state, approval/execution/verification status. No fake "AI thinking" animation; an honest empty state when nothing is selected. |
| Agent Workflow | `/blue-agent/agent-workflow` | The professor-facing 7-agent architecture: 1 Red agent card, then a visually distinct "Analytical subsystems (not agents)" section, then the 6 Blue agent cards. Clicking a card opens its detail panel (role, description, implementation type, version, input/decision/output types, next handoff). Below that, a real live agent trace for a selected orchestration, or an honest "No agent execution selected." |
| Response Plans | `/blue-agent/response-plans` | Run/model/incident/sequence selector, then candidate cards ranked by Response Utility Score, each showing the full score breakdown, what-if before/after evidence, policy pass/fail, the collapsed existing Defense Score (kept visible as a distinct signal), and a "Create Synthetic Response Orchestration" button (disabled when the candidate fails policy). |
| Policies | `/blue-agent/policies` | Read-only cards for the 7-policy catalogue: ID, name, enabled state, purpose, applies-to, decision effect. |
| Verification | `/blue-agent/verification` | The autonomy-mode control (with explicit AUTONOMOUS confirmation), the selected orchestration's real agent decisions, the human approval gate, and execute/verify/rollback controls — carried over from `ResponseOperationsPage`, now also showing the dual-check verification metrics (`security_effect_confirmed`, `operational_health_ok`) and the rollback reason/requester when one has occurred. |

## Shared selection state lives in the URL, not a context provider

`useBlueAgentSelection()` (`pages/blueAgent/useBlueAgentSelection.ts`)
reads/writes `run`, `model`, `incident`, `sequence`, and `orchestration`
as query parameters via `useSearchParams`. This means:

- Switching tabs keeps the same incident/orchestration in view.
- The exact state is shareable/reloadable via a plain URL — useful for a
  professor demo link that jumps straight to a specific comparison or
  trace.
- No new React context was introduced; every tab is an independent route
  that happens to read/write the same URL keys.

## Why the Defense Score stays visible, not merged

Per the Phase 4 "confidence terminology precision" requirement, the
existing `defense_score` (Phase 3) and the new Response Utility Score
must never be presented as one number. `ResponsePlansPage.tsx` fetches
both `blue-planning/compare` and the existing `response/analyze`
endpoint, and renders `DefenseScoreBreakdown` (Phase 3's unchanged
component) inside a `<details>` disclosure per candidate, explicitly
labeled "Existing Blue Agent Defense Score (distinct signal, feeds
evidence quality above)."

## What-if visualization is textual, not a graph overlay, in this phase

The spec asked for a graph-based before/simulated-after view reusing
Phase 3's focused-path `CyberDigitalTwin` highlight design
(`AttackPathsPanel.tsx`'s pattern). This phase ships the *evidence*
(attack-path counts, critical-target reachability, blast-radius
reachable/critical counts, before → after) as a structured textual
panel per candidate — the same numbers a graph overlay would need to
justify, and the same ones `SecurityGainEvidence` returns from the API.
A literal graph overlay would need the backend to also return the
actual before/after path edge lists (not just counts), which
`CandidatePlanAssessment` deliberately does not carry today to keep the
what-if response small and the recomputation bounded (see "Performance"
in the Phase 4 completion report). This is recorded as a known
limitation, not a silent gap — see the completion report.

## Command Centre

Per the Phase 4 instruction to not redesign Command Centre again, no
new panel was added there this phase; `BlueAgentCard.tsx`'s "View
Details" link was retargeted from the deleted `/response-centre` to
`/blue-agent/response-plans` so it keeps working.

## New frontend files

- `src/types/agents.ts`, `policy.ts`, `autonomy.ts`, `bluePlanning.ts`,
  `workflow.ts` — typed response shapes mirroring the backend Pydantic
  schemas field-for-field.
- `src/services/agentsApi.ts`, `policyApi.ts`, `autonomyApi.ts`,
  `bluePlanningApi.ts`, `workflowApi.ts` — thin, validated API clients
  following this codebase's existing convention.
- `src/pages/blueAgent/*.tsx` — the 5 tab pages plus
  `useBlueAgentSelection.ts` and the shared `IncidentContextSelector.tsx`.

## Verification

Verified end-to-end against a live backend in a real browser: run a
scenario → train/score a model → correlate an incident → compare
candidate plans → create an orchestration → approve → execute → verify
→ roll back, with the Agent Workflow tab's live trace reflecting the
real orchestration throughout. See the Phase 4 completion report's demo
section and `docs/ui/screenshots/phase-4/`.
