# Phase 2 Design System

## Design philosophy

AegisArena is a cloud cyber-resilience **product**, not a hacker-movie prop.
Phase 2 moves the interface from a dark, cyan/neon-accented "cyber" theme
toward a clean, light, enterprise security/compliance dashboard — the kind
a professor, auditor, or SOC lead would recognize as a real product in
under 30 seconds.

**Explicit rule: no gradients, no cyberpunk styling, no AI clichés.**
Concretely, this phase removed or never introduced: rainbow/blue-purple
gradients, neon glow borders, glassmorphism, pulsing/glowing animations
(the topology view's `box-shadow` glows and `scale`/`dash-offset` looping
animations were deleted outright), robot/brain/circuit imagery, sparkles,
matrix-style backgrounds, giant hero banners, and decorative icons. The
product communicates intelligence through hierarchy, real evidence, and
precise microcopy — not visual gimmicks.

## Reference interpretation

The supplied reference (light background, dark narrow sidebar, white
cards, semicircular gauges, restrained color, high information density)
was used as a **philosophy**, not a template to clone. AegisArena keeps
its own identity: its five-section navigation (Command Centre / Digital
Twin / Threat Analysis / Defense / Results), its existing chart/topology
components, and its own brand mark — while adopting the reference's
discipline around whitespace, card consistency, and calm color use.

## Navigation structure

Primary sidebar (unchanged set, Command Centre relabeled from "Overview"):

```
Command Centre         →  /
Digital Twin            →  /digital-twin
Threat Analysis         →  /telemetry, /incidents, /mitre, /predictive-analytics
Defense                  →  /response-centre, /response-operations
Results                  →  /model-analytics, /audit-trail, /settings
```

Sub-navigation (section tabs) renders under the page header for any
section with more than one route, using a text-label + underline style —
no pill buttons, no icon-only tabs. No Phase 3+ items (Attack Paths,
Purple Team, Resilience Score) were added as navigation entries.

## Tokens

All tokens live in `frontend/src/index.css` under `:root`. Naming is
intentionally the same as before Phase 2 (`--bg`, `--surface`, `--border`,
`--text`, `--state-*`, etc.) so no component had to be rewritten to
consume new variable names — only the **values** changed.

| Token | Value | Use |
|---|---|---|
| `--bg` | `#f7f8fa` | Page background |
| `--surface` | `#ffffff` | Card/panel background |
| `--surface-2` | `#f3f4f6` | Recessed/secondary surface (inputs, nested panels) |
| `--border` / `--border-strong` | `#e5e7eb` / `#d1d5db` | Card borders, dividers |
| `--text` / `--text-dim` / `--text-faint` | `#111827` / `#4b5563` / `#6b7280` | Primary / secondary / tertiary text |
| `--sidebar-bg` | `#111827` | Sidebar background (deep charcoal, not pure black) |
| `--accent` / `--accent-strong` | `#2563eb` / `#1d4ed8` | Links, active nav/tabs, primary buttons |
| `--state-ok` / `--state-degraded` / `--state-attack` | `#16a34a` / `#d97706` / `#dc2626` | Healthy/success, warning, critical — **semantic only** |
| `--state-healthy` | `#2563eb` | Informational/system state |
| `--radius` / `--radius-sm` | `8px` / `6px` | Card / control corner radius |
| `--shadow-card` | `0 1px 2px rgba(15,23,42,.04)` | The one, consistent card shadow — no floating-glass panels |

No gradient token exists anywhere in the system.

## Typography

Existing font stack retained (`Inter`, falling back to the system UI
stack) — no new font dependency was added. Approximate scale actually
used:

- Page title (`.page-heading h1`): 1.5rem / 600 weight
- Section/card title (`.card-title`): 0.95rem / 600 weight
- Primary metric (`.kpi-value`, `.gauge-value`): 1.6rem–1.9rem / 700 weight
- Body text: 0.85–0.95rem
- Secondary/supporting text (`.kpi-detail`, `.text-faint`): 0.72–0.8rem

## Spacing and layout

- Page content container: `max-width: 108rem`, `padding: 1.5rem` — uses
  the available desktop width rather than a cramped centered column.
- Card gaps standardized to `~1.1rem` in the Command Centre grid rows.
- Sidebar width increased from 13rem to 15.5rem (collapsed: 4rem) to fit
  the brand name/tagline and full-word nav labels without truncation at
  common desktop widths.
- The Command Centre no longer forces a fixed, non-scrolling viewport
  height — it scrolls like every other page, since it now holds
  substantially more content than a single topology canvas.

## Card conventions

One shared visual language (`.card` / `.panel-surface`, `ui/card.tsx`):
white surface, `1px solid var(--border)`, `var(--radius)` corners,
`var(--shadow-card)` — the same subtle shadow everywhere, never a
per-card bespoke style. Card headers (`.card-head`) always carry a title
and, where relevant, a single right-aligned link (e.g. "Open Digital
Twin") — never more than one primary action per card header.

## Status / semantic colors

Colors communicate state and are **always paired with text**, never used
alone:

- Green (`--state-ok`) — healthy, mitigated, verified
- Amber (`--state-degraded`) — warning, attention needed
- Red (`--state-attack`) — critical, under attack, error
- Blue (`--state-healthy` / `--accent`) — informational, system, active
  navigation

`StatusBadge`-equivalents in this codebase are the existing `.chip`
family (`chip-healthy`, `chip-warn`, `chip-danger`, `chip-accent`,
`chip-muted`) plus `SeverityBadge` — all retinted to light backgrounds
with a colored border/text pairing (e.g. `border-emerald-200 bg-emerald-50
text-emerald-700`) rather than dark, saturated fills.

## Chart / gauge conventions

- The topology view's animated glow/pulse effects were removed; state is
  now shown with plain border-color and border-width changes.
- The new `Gauge` component (`components/ui/Gauge.tsx`) is a plain SVG
  semicircular arc with one `stroke-dashoffset` CSS transition (300ms) —
  no loop, no glow.
- Existing chart components (Recharts-based `AnomalyActivityChart`,
  `AttackTechniqueTimeline`) were retinted only, not restructured — they
  already met the "readable, sparse, correctly labeled" bar.

## Interaction / motion rules

Transitions are capped at 150–300ms (hover states, the gauge arc, the
sidebar collapse width/transform). No looping animations, no pulsing
borders, no moving backgrounds remain anywhere in the app after this
phase — the topology view's `topology-pulse`/`topology-dash` keyframes
were deleted along with their usages.

## Accessibility decisions

- Focus-visible outline (`outline: 2px solid var(--accent)`) unchanged in
  mechanism, retargeted to the new accent color, which meets contrast
  against both the white page background and the dark sidebar buttons it
  also applies to.
- All retinted text colors were chosen to meet at least WCAG AA contrast
  against their new background (e.g. `text-slate-500` on white ≈ 4.6:1;
  sidebar `--sidebar-text: #cbd5e1` on `--sidebar-bg: #111827` ≈ 9:1).
- Status is never color-only: every chip/badge carries a text label
  (`Healthy`, `Monitoring`, `Active`, etc.) alongside its color.
- `.skip-link` ("Skip to main content") retained and retinted.
- Section tabs and sidebar nav remain real `<a>`/`NavLink` elements — no
  `<div onClick>` pseudo-buttons were introduced.

## Responsive rules

- Below 1180px: the Command Centre's two-column card rows collapse to a
  single column (`.overview-row`, `.overview-risk-row`); the topology
  workspace grid does the same.
- Below 1024px: the sidebar collapses to an overlay (`.is-mobile-open`)
  rather than a permanent column.
- No horizontal scroll is introduced at 1366×768 or wider — verified
  manually (see the Phase 2 completion report for resolutions checked).
- Phase 2 targets desktop/laptop only, per the explicit brief; the
  existing narrow-viewport rules (chip hiding, single-column stacking)
  were preserved and retinted, not rebuilt for mobile-first use.

## What was intentionally deferred

- Deep, feature-level redesign of Digital Twin, Threat Analysis's
  detailed sub-pages, Defense's detailed sub-pages, and Results' detailed
  sub-pages — these received shell/token/card consistency only in Phase 2
  (see `docs/architecture/DATA_FLOW.md` and the Phase 2 completion report
  for exactly what changed vs. what remains for a future phase).
- Any Phase 3+ concept (Attack Path Intelligence, Blast Radius, Purple
  Team, Aegis Resilience Score, LLM Blue Agent, what-if planner, policy-
  as-code, autonomy levels) — none of these appear in navigation, as
  disabled teaser cards, or anywhere else in the UI.
