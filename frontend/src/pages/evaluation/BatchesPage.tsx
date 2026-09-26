import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { Card, CardContent, CardHeader } from '../../components/ui/card'
import { toClientApiError } from '../../services/apiClient'
import { createBatch, getBatch, listBatches } from '../../services/evaluationApi'
import { listRedScenarios } from '../../services/purpleTeamApi'
import type { RedScenarioSummary } from '../../types/purpleTeam'
import {
  ALL_DEFENCE_MODES,
  CANONICAL_SCENARIO_IDS,
  CANONICAL_SEEDS,
  DEFENCE_MODE_LABELS,
  type BatchView,
  type DefenceMode,
} from '../../types/evaluation'

/** Extrapolated from an earlier backend stage's measured ~46s / 8
 * experiments. Deliberately conservative and rounded up, never presented as
 * instant. */
const SECONDS_PER_EXPERIMENT = 46 / 8

function estimateSeconds(count: number): number {
  return Math.ceil(count * SECONDS_PER_EXPERIMENT)
}

function formatEstimate(count: number): string {
  const seconds = estimateSeconds(count)
  if (seconds < 60) return `about ${String(seconds)}s`
  const minutes = Math.ceil(seconds / 60)
  return `under ${String(minutes)} minute${minutes === 1 ? '' : 's'}`
}

export function BatchesPage() {
  const [scenarios, setScenarios] = useState<RedScenarioSummary[]>([])
  const [scenarioIds, setScenarioIds] = useState<string[]>([])
  const [seeds, setSeeds] = useState<number[]>(CANONICAL_SEEDS)
  const [defenceModes, setDefenceModes] = useState<DefenceMode[]>(ALL_DEFENCE_MODES)
  const [maxExperiments, setMaxExperiments] = useState('')

  const [running, setRunning] = useState(false)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [runError, setRunError] = useState<string | null>(null)
  const [runResult, setRunResult] = useState<BatchView | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const [batches, setBatches] = useState<BatchView[]>([])
  const [batchesLoading, setBatchesLoading] = useState(true)
  const [batchesError, setBatchesError] = useState<string | null>(null)
  const [selectedBatch, setSelectedBatch] = useState<BatchView | null>(null)

  function refreshBatches() {
    setBatchesLoading(true)
    void listBatches()
      .then((rows) => {
        setBatches(rows)
        setBatchesError(null)
      })
      .catch((cause: unknown) => {
        setBatchesError(toClientApiError(cause).message)
      })
      .finally(() => {
        setBatchesLoading(false)
      })
  }

  useEffect(() => {
    void listRedScenarios()
      .then(setScenarios)
      .catch(() => {
        // Optional convenience list only.
      })
    // Defer to a microtask so the initial setState calls happen outside the
    // synchronous effect body (react-hooks/set-state-in-effect).
    void Promise.resolve().then(() => {
      refreshBatches()
    })
  }, [])

  useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current)
    },
    [],
  )

  function toggleScenario(id: string) {
    setScenarioIds((current) =>
      current.includes(id) ? current.filter((value) => value !== id) : [...current, id],
    )
  }

  function toggleSeed(seed: number) {
    setSeeds((current) =>
      current.includes(seed) ? current.filter((value) => value !== seed) : [...current, seed],
    )
  }

  function toggleMode(mode: DefenceMode) {
    setDefenceModes((current) =>
      current.includes(mode) ? current.filter((value) => value !== mode) : [...current, mode],
    )
  }

  function fillCanonicalMatrix() {
    setScenarioIds(CANONICAL_SCENARIO_IDS)
    setSeeds(CANONICAL_SEEDS)
    setDefenceModes(ALL_DEFENCE_MODES)
    setMaxExperiments('')
  }

  const experimentCount = scenarioIds.length * seeds.length * defenceModes.length

  function runBatch() {
    setRunning(true)
    setRunError(null)
    setRunResult(null)
    setElapsedSeconds(0)
    timerRef.current = setInterval(() => {
      setElapsedSeconds((value) => value + 1)
    }, 1000)
    void createBatch({
      scenario_ids: scenarioIds,
      seeds,
      defence_modes: defenceModes,
      max_experiments: maxExperiments ? Number(maxExperiments) : undefined,
    })
      .then((batch) => {
        setRunResult(batch)
        refreshBatches()
      })
      .catch((cause: unknown) => {
        setRunError(toClientApiError(cause).message)
      })
      .finally(() => {
        setRunning(false)
        if (timerRef.current) clearInterval(timerRef.current)
      })
  }

  function handleSubmit() {
    if (scenarioIds.length === 0 || seeds.length === 0 || defenceModes.length === 0) return
    if (experimentCount >= 20) {
      const confirmed = window.confirm(
        `This will run ${String(experimentCount)} experiments sequentially and may take ${formatEstimate(experimentCount)}. Continue?`,
      )
      if (!confirmed) return
    }
    runBatch()
  }

  function handleViewBatch(batchId: string) {
    void getBatch(batchId)
      .then(setSelectedBatch)
      .catch((cause: unknown) => {
        setBatchesError(toClientApiError(cause).message)
      })
  }

  return (
    <section className="space-y-6" aria-labelledby="batches-title">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Evaluation · Batches</p>
          <h1 id="batches-title">Run a batch</h1>
          <p>
            Runs the scenario × seed × defence-mode matrix sequentially, server-side. This request
            blocks until the whole batch has completed - there is no background job or progress
            endpoint to poll.
          </p>
        </div>
      </header>

      <Card>
        <CardHeader>
          <div>
            <h2 className="panel-title">Create batch</h2>
          </div>
          <Button type="button" variant="outline" onClick={fillCanonicalMatrix}>
            Run canonical 4×5×4 matrix
          </Button>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault()
              handleSubmit()
            }}
          >
            <fieldset>
              <legend className="text-xs font-semibold text-slate-600">Scenarios</legend>
              <div className="mt-1 flex flex-wrap gap-3">
                {(scenarios.length > 0
                  ? scenarios.map((scenario) => scenario.scenario_id)
                  : CANONICAL_SCENARIO_IDS
                ).map((id) => (
                  <label key={id} className="flex items-center gap-1 text-sm">
                    <input
                      type="checkbox"
                      aria-label={`Scenario ${id}`}
                      checked={scenarioIds.includes(id)}
                      onChange={() => {
                        toggleScenario(id)
                      }}
                    />
                    {scenarios.find((scenario) => scenario.scenario_id === id)?.name ?? id}
                  </label>
                ))}
              </div>
            </fieldset>
            <fieldset>
              <legend className="text-xs font-semibold text-slate-600">Seeds</legend>
              <div className="mt-1 flex flex-wrap gap-3">
                {CANONICAL_SEEDS.map((seed) => (
                  <label key={seed} className="flex items-center gap-1 text-sm">
                    <input
                      type="checkbox"
                      aria-label={`Seed ${String(seed)}`}
                      checked={seeds.includes(seed)}
                      onChange={() => {
                        toggleSeed(seed)
                      }}
                    />
                    {seed}
                  </label>
                ))}
              </div>
            </fieldset>
            <fieldset>
              <legend className="text-xs font-semibold text-slate-600">Defence modes</legend>
              <div className="mt-1 flex flex-wrap gap-3">
                {ALL_DEFENCE_MODES.map((mode) => (
                  <label key={mode} className="flex items-center gap-1 text-sm">
                    <input
                      type="checkbox"
                      aria-label={DEFENCE_MODE_LABELS[mode]}
                      checked={defenceModes.includes(mode)}
                      onChange={() => {
                        toggleMode(mode)
                      }}
                    />
                    {DEFENCE_MODE_LABELS[mode]}
                  </label>
                ))}
              </div>
            </fieldset>
            <label className="flex flex-col text-xs text-slate-600">
              Max experiments (optional cap)
              <input
                aria-label="Max experiments"
                value={maxExperiments}
                onChange={(event) => {
                  setMaxExperiments(event.target.value.replace(/[^0-9]/g, ''))
                }}
                className="mt-1 w-32 rounded-md border border-slate-300 px-2 py-1 text-sm"
                placeholder="no cap"
              />
            </label>
            <p className="text-sm text-slate-600">
              This will run <strong>{experimentCount}</strong> experiment(s), estimated{' '}
              {formatEstimate(experimentCount)}.
            </p>
            <Button
              type="submit"
              disabled={
                running ||
                scenarioIds.length === 0 ||
                seeds.length === 0 ||
                defenceModes.length === 0
              }
            >
              {running ? 'Running…' : 'Run batch'}
            </Button>
          </form>
        </CardContent>
      </Card>

      {running ? (
        <Card>
          <CardContent>
            <p role="status">
              Running batch — {experimentCount} experiment(s) queued, please wait. Elapsed:{' '}
              {elapsedSeconds}s
            </p>
          </CardContent>
        </Card>
      ) : null}

      {runError ? (
        <p role="alert" className="text-red-700">
          {runError}
        </p>
      ) : null}

      {!running && runResult ? <BatchSummary batch={runResult} title="Batch complete" /> : null}

      <Card>
        <CardHeader>
          <h2 className="panel-title">Past batches</h2>
        </CardHeader>
        <CardContent>
          {batchesError ? (
            <p role="alert" className="text-red-700">
              {batchesError}
            </p>
          ) : null}
          {batchesLoading ? <p role="status">Loading batches…</p> : null}
          {!batchesLoading && batches.length === 0 && !batchesError ? (
            <p>No batches have been run yet.</p>
          ) : null}
          {!batchesLoading && batches.length > 0 ? (
            <ul className="space-y-2">
              {batches.map((batch) => (
                <li key={batch.batch_id}>
                  <button
                    type="button"
                    className="w-full rounded-md border border-slate-200 p-3 text-left text-sm hover:bg-slate-50"
                    onClick={() => {
                      handleViewBatch(batch.batch_id)
                    }}
                  >
                    Batch {batch.batch_id.slice(0, 8)} · {batch.completed_count}/
                    {batch.total_experiments} completed
                    {batch.failed_count > 0 ? `, ${String(batch.failed_count)} failed` : ''} ·{' '}
                    {batch.status}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </CardContent>
      </Card>

      {selectedBatch ? <BatchSummary batch={selectedBatch} title="Batch summary" /> : null}
    </section>
  )
}

function BatchSummary({ batch, title }: { batch: BatchView; title: string }) {
  const hasFailures = batch.failed_count > 0
  return (
    <Card>
      <CardHeader>
        <div>
          <h2 className="panel-title">{title}</h2>
          <p className="text-xs text-slate-500">Batch {batch.batch_id}</p>
        </div>
        <Badge className={hasFailures ? 'chip-warn' : 'chip-healthy'}>{batch.status}</Badge>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <dt className="text-xs text-slate-500">Completed</dt>
          <dd>
            {batch.completed_count} / {batch.total_experiments}
          </dd>
          <dt className="text-xs text-slate-500">Failed</dt>
          <dd>{batch.failed_count}</dd>
          <dt className="text-xs text-slate-500">Runtime</dt>
          <dd>{batch.runtime_seconds === null ? 'N/A' : `${batch.runtime_seconds.toFixed(1)}s`}</dd>
          <dt className="text-xs text-slate-500">Truncated</dt>
          <dd>{batch.truncated ? 'yes' : 'no'}</dd>
        </dl>
        {hasFailures ? (
          <p className="text-sm text-amber-700">
            {batch.failed_count} experiment(s) in this batch failed. This does not indicate the
            batch itself is broken - individual experiment failures (e.g. a scenario/seed
            combination hitting a precondition issue) are expected occasionally and are shown here
            transparently.
          </p>
        ) : null}
        <div>
          <h3 className="text-sm font-semibold">Experiments</h3>
          <ul className="mt-1 flex flex-wrap gap-2">
            {batch.experiment_ids.map((id) => (
              <li key={id}>
                <Link to={`/evaluation/experiments/${id}`} className="card-link text-xs">
                  {id.slice(0, 8)}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  )
}
