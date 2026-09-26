# Phase 5 Evaluation UI

`frontend/src/pages/evaluation/*.tsx`, wired into `frontend/src/lib/routes.ts`
under the "Evaluation" nav section and `frontend/src/app/router.tsx`.

## Routing structure

| Path | Component | 
|---|---|
| `/evaluation` | `EvaluationOverviewPage` |
| `/evaluation/experiments` | `ExperimentListPage` |
| `/evaluation/experiments/:experimentId` | `ExperimentDetailPage` |
| `/evaluation/experiments/:experimentId/report` | `ExperimentReportPage` |
| `/evaluation/compare` | `ComparisonPage` |
| `/evaluation/aggregate` | `AggregatePage` |
| `/evaluation/batches` | `BatchesPage` |

(from `frontend/src/lib/routes.ts`'s `evaluation` nav section and
`frontend/src/app/router.tsx`'s nested `Route` declarations.)

## Charting approach

Uses `recharts` (already a project dependency — no new library added):
`ComparisonPage.tsx` imports `BarChart`/`Bar`/etc. for the side-by-side
mode comparison bars, `ExperimentDetailPage.tsx` imports
`LineChart`/`Line`/etc. to render the Mission Health resilience curve over
logical time.

## The 7 pages

### 1. Overview (`EvaluationOverviewPage.tsx`)

Landing page for the Evaluation section. Surfaces headline aggregate
numbers computed client-side from whatever experiments are loaded: a
verified-recovery rate ("applies (excludes no-active-defence controls)"),
a mean Aegis Resilience Score across completed experiments with a computed
score, and a mean MCI across completed experiments with a computed MCI —
each explicitly labelled with its applicable sample count (`N/A excluded`)
rather than silently averaging in zeros. Links out to the Experiment List.

### 2. Experiment List (`ExperimentListPage.tsx`)

Filterable table of all experiments (`scenario_id`, `defence_mode`, `seed`,
`status`, `batch_id` filters, mirroring the query parameters
`GET /v1/evaluation/experiments` accepts). Numeric cells that are N/A
render literally as `N/A` (`formatMetric`/`formatNumber` helpers), never as
a blank or a `0`. Row click navigates to that experiment's detail page.
Exposes CSV and JSON export links pointing at
`/api/v1/evaluation/experiments/export.csv` /
`/api/v1/evaluation/experiments/export.json`, carrying the same active
filters through as query parameters.

### 3. Experiment Detail (`ExperimentDetailPage.tsx`)

The single-experiment deep dive. Renders the experiment's configuration,
version fields (`metrics_version`/`mci_version`/`ars_version`, each shown
literally or as `N/A`), the ARS total and its 4-pillar breakdown (each
pillar rendered as `N/A` when `applicable=false` rather than a fabricated
number), the MCI value, and the Mission Health resilience curve as a
`recharts` `LineChart` plotted over `logical_time_sim`. A
`no_active_defence` experiment is labelled with a `Badge` reading
**"CONTROL — NO ACTIVE DEFENCE"** (`isControl` check on
`experiment.defence_mode === 'no_active_defence'`) styled with the
project's warning chip class, not an alarming red/destructive one — it is
presented as an intentional baseline, not a failure state. Exposes a
"Re-run experiment" button (`rerunExperiment` API call, navigates to the
new experiment's own detail page on success) and a link to the
print-friendly report page.

### 4. Comparison (`ComparisonPage.tsx`)

Paired mode-vs-mode comparison for one `scenario_id` + `seed`
(`GET /v1/evaluation/compare`). Renders `ModeComparisonResult.rows` as a
metric-by-mode table, each cell `N/A` when inapplicable, plus a `recharts`
`BarChart` for the numeric comparison metrics. Surfaces
`PairedDelta.fairness_reasons` as a visible warning whenever a delta is
`paired=false`, rather than silently presenting a mismatched pair as clean.

### 5. Aggregate (`AggregatePage.tsx`)

Descriptive statistics (`GET /v1/evaluation/aggregate`) filterable by
`scenario_id`/`defence_mode`/`seeds`/`include_failed`. Renders each
`MetricSummaryView` (count, applicable count, mean, median, std, min, max)
and `BooleanOutcomeSummaryView` (success rate over the applicable sample),
with `N/A` shown wherever `n_applicable == 0`.

### 6. Batches (`BatchesPage.tsx`)

Lists and creates evaluation batches (`GET`/`POST /v1/evaluation/batches`).
A batch's `status` badge uses `chip-healthy` for a clean `"completed"` run
and `chip-warn` (not a destructive/red style) for `"completed_with_failures"`
— the batch runner's per-experiment failure tolerance (see
`batch_service.py`) is presented as a normal, expected outcome of a large
matrix run, not an alarm. Each batch links out to its constituent
experiments' detail pages.

### 7. Report (`ExperimentReportPage.tsx`)

Renders `ExperimentReport` (`GET /v1/evaluation/experiments/{id}/report`)
as a single print-friendly page: executive summary, configuration,
detection evidence, incident summary, Attack Graph/Blast Radius before/
after, response/verification/rollback summary, full metrics, ARS
decomposition, paired baseline comparison (when available), stated
limitations, and reproduction fields. A "Print" action calls
`window.print()` directly — no separate PDF generation service.

## Restrained visual design choices

- No neon/gradient styling anywhere in the evaluation pages — consistent
  with the rest of the project's restrained chip/badge system
  (`chip-healthy`, `chip-warn`, `chip-muted`).
- N/A is always rendered as the literal string `N/A`, never a blank cell,
  a dash with no explanation, or a coerced `0`/`false` — every page that
  renders a `Metric`-wrapped or otherwise-optional value checks
  `applicable`/`null` explicitly before formatting.
- `no_active_defence` is labelled **"CONTROL — NO ACTIVE DEFENCE"**, framed
  as an intentional scientific baseline rather than a system failure.
- `completed_with_failures` batches render with a neutral warning chip, not
  an alarmist red/destructive one — matching the batch runner's own design
  intent that individual experiment failures inside a large matrix are
  expected and handled gracefully, not a crash.

## See also

`docs/evaluation/PHASE_5_EVALUATION_FRAMEWORK.md` for the underlying data
model each page renders; `docs/evaluation/AEGIS_RESILIENCE_SCORE.md` /
`MISSION_CONTINUITY_INDEX.md` for the two headline scores shown throughout.
