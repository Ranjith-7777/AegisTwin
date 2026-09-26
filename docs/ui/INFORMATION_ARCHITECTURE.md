# Information Architecture (Phase 2)

## Primary navigation (sidebar)

| Section | Landing route | Purpose |
|---|---|---|
| Command Centre | `/` | Operational overview: health, risk, incidents, twin, detection, defense status |
| Digital Twin | `/digital-twin` | Synthetic cloud topology, path inspection, run/model context |
| Threat Analysis | `/telemetry` | Telemetry replay, incidents, MITRE mapping, prediction |
| Defense | `/response-centre` | Blue Agent recommendation ranking and orchestration lifecycle |
| Results | `/model-analytics` | Detection model management, audit trail, settings |

## Secondary navigation (section tabs)

| Section | Sub-pages |
|---|---|
| Threat Analysis | Live Telemetry (`/telemetry`) · Incidents (`/incidents`) · MITRE ATT&CK (`/mitre`) · Attack Prediction (`/predictive-analytics`) |
| Defense | Blue Agent (`/response-centre`) · Response Operations (`/response-operations`) |
| Results | Detection Models (`/model-analytics`) · Audit Trail (`/audit-trail`) · Settings (`/settings`) |

Every route that existed before Phase 2 is preserved and reachable
exactly as before — the redesign is a presentation-layer and Command
Centre content change, not a re-routing.

## Explicitly excluded (not implemented, not planned as active nav)

Attack Path Intelligence, Blast Radius, Purple Team Mode, Aegis
Resilience Score, and any other Phase 3+ concept do **not** appear as
navigation items, disabled/teaser cards, or placeholder routes. They are
documented only in architecture-planning material, never presented as a
working (or soon-working) feature in the UI itself.

## Command Centre content map

Top to bottom, everything sourced from real, already-available frontend
state (`useSimulationPlayback`, `useTopology`) — nothing hardcoded:

1. **Page header** — title, one-line positioning subtitle.
2. **Mission progress** — Simulate → Detect → Predict → Defend → Recover,
   derived from whether a run/assessments/predictions/recommendation/
   rollback exist.
3. **Current Risk gauge + Operational Summary (Cloud Health, Risk Score,
   Availability, Active Incidents)** — the existing `deriveCommandCentreState`
   computation, now visualized with a primary gauge instead of a single
   small KPI tile.
4. **Active Incident** — the current correlated incident candidate's
   priority, evidence count, MITRE technique count, and affected-asset
   count, with a link to the full Incidents page; a calm empty state when
   none exists.
5. **Digital Twin summary** — the live/static topology render plus a
   real asset/relationship count line, with a link to the full Digital
   Twin page.
6. **Detection summary** — selected model id/type, telemetry-assessed
   count, anomalous count, and the latest next-stage prediction if one
   exists.
7. **Blue Agent recommendation** — the top-ranked mitigation (if any) with
   its Defense Score breakdown and an Approve action, or a prompt to rank
   mitigations.
8. **Red Agent panel + Recent Activity** — the existing scenario-control
   panel, and a new compact "what has happened so far" checklist (five
   pipeline milestones) derived from state already on the page.

## Page-header pattern

Every top-level page uses the same `PageHeader` shape: an `<h1>` title, an
optional one-line subtitle, and an optional right-aligned actions slot —
introduced in Phase 2 (`components/layout/PageHeader.tsx`) and applied to
Command Centre. Other pages retain their existing inline `.page-heading`
markup (same CSS class, same visual result) since converting every page's
heading markup to the new component is a mechanical follow-up with no
visual difference, left for a later cleanup pass rather than done
speculatively here.

## Depth of redesign by area (Phase 2 vs. deferred)

| Area | What Phase 2 did |
|---|---|
| Global shell (sidebar, header, page container, tabs) | Fully redesigned |
| Command Centre | Fully redesigned (content + layout) |
| Digital Twin | Shell/token/card consistency only, plus the run-context URL fix; the topology canvas and its controls are visually retinted, not restructured |
| Threat Analysis (Live Telemetry, Incidents, MITRE, Prediction) | Shell/token/card consistency only |
| Defense (Blue Agent, Response Operations) | Shell/token/card consistency only |
| Results (Detection Models, Audit Trail, Settings) | Shell/token/card consistency only |

Deep functional/visual redesign of Digital Twin, Threat Analysis, Defense,
and Results detail pages is explicitly deferred to a future phase, per
the Phase 2 brief.
