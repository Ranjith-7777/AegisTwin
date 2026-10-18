# AegisArena UI design system — "midnight operations"

Source: `frontend/src/index.css` (tokens and component classes) and
`frontend/src/components/ui/` (Button, Card, Badge, Panel, Metric, KeyValue,
Bar, Tip, Dialog). This replaces the light theme described in
`PHASE_2_DESIGN_SYSTEM.md`, which is kept as project history.

## Principles

1. **Colour is state, never decoration.**
   - Cyan is the accent and the "proposed" state.
   - Green means verified or restored.
   - Amber means warning or awaiting approval.
   - Red means danger.
   - Violet means a prediction (a hypothesis).
2. **Proposed is never drawn as executed.**
   - A proposed mitigation is dashed and cyan.
   - An executed mitigation is a cut edge (`×`) with a "mitigated" tag.
   - A rollback is shown as "restored".
3. **Every number shows where it came from.**
   - A missing value is shown as `—`, never as `0`.
   - Scores carry their caption, for example "deterministic evaluation score, not a probability".
   - Timing metrics are labelled as logical time.
4. **Motion only signals change:** evidence arriving, a mitigation applied, a recovery. It respects `prefers-reduced-motion`.
5. **Accessibility.**
   - Every interactive control has a visible focus ring (`--border-focus`).
   - Dialogs move focus inside when they open, close on Escape, and return focus to the control that opened them.
   - Status changes use `role="status"`.
   - Icons are paired with text.
   - Contrast meets WCAG AA for body text on `--surface`.

## Tokens

| Token | Value | Use |
|---|---|---|
| `--bg` / `--bg-elevated` | `#060a13` / `#0a101d` | Canvas, sidebar |
| `--surface`, `-2`, `-3` | `#0d1422` → `#162135` | Panels, nested panels, hover |
| `--border` / `--border-strong` | slate at 11% / 20% | Hairlines |
| `--text` / `--text-dim` / `--text-faint` | `#e8eef7` / `#a3b0c4` / `#6b7a93` | Body / secondary / meta |
| `--accent` | `#38bdf8` | Links, focus, primary action |
| `--ok` · `--warn` · `--danger` | `#34d399` · `#fbbf24` · `#f87171` | Semantic state |
| `--predicted` · `--proposed` | `#a78bfa` · `#22d3ee` | Prediction layer · proposed mitigation |

Older pages use Tailwind utilities written for a light theme, such as
`text-slate-500` and `bg-red-50`. Tailwind v4's `@theme` block remaps those
palettes so each utility keeps its role in the dark theme. New code uses the
semantic classes instead.

## Component classes

- `panel`
- `metric`
- `kv`
- `bar`
- `badge` (with a tone)
- `tabs`
- `data-table`
- `empty`, `error` and `notice` states
- `skeleton` and `spinner`
- `tip` (tooltip)
- `dialog`
- `stage-rail` and `stage-list` (the 14-stage workflow and the 8-step rail)
- `mode-switch` (autonomy)
- `why-panel` (Blue decision rationale)
- `lifecycle`
- `scenario-card`
- `step-timeline`
- `cc-grid` and `cc-kpis` (Command Centre)
- `twin-*`, node overlay tags and `edge-cut`
- `legend`

The stylesheet also includes responsive breakpoints (1280 / 1180 / 900 / 640 px)
and print styles for reports.

## Information architecture

The sidebar groups are defined in `frontend/src/lib/routes.ts`:

- **Command:** Command Centre, Autonomous Workflow
- **Range:** Red Agent, Telemetry, Incidents, Attack Intelligence (MITRE ATT&CK, Attack Prediction)
- **Defence:** Blue Agent (Overview, Agent Decision Trace), Response Plans, Policies, Verification (with a badge while an approval is pending)
- **Twin:** Digital Twin, Attack Paths, Blast Radius
- **Analysis:** Evaluation (Overview, Strategy Comparison, Aggregate, Batches), Experiments & Reports, Audit Trail
- **System:** Detection Models, Settings

The header shows:

- the breadcrumb;
- the current run;
- the autonomy pill;
- the simulation-only notice;
- the environment;
- the role (with a `dev` marker under the development bypass);
- backend health.

## Workflow stages

`frontend/src/lib/workflowStages.ts` derives 14 stages from persisted state:

1. attack
2. telemetry
3. detection
4. correlation
5. prediction
6. response
7. what_if
8. policy
9. approval
10. execution
11. verification
12. rollback
13. twin
14. audit

The rail groups those stages into 8 steps:

- Red
- Detect
- Correlate
- Predict
- Decide
- Execute
- Verify
- Recover

Each stage has one of these statuses: waiting, running, completed, warning,
awaiting, blocked, failed, rolled_back, skipped. Nothing is inferred
optimistically. For example, prediction shows "warning" when the replay ended
without a hypothesis, not "completed".
