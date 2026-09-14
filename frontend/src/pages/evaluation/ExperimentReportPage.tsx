import { Fragment, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Badge } from '../../components/ui/badge'
import { Button } from '../../components/ui/button'
import { toClientApiError } from '../../services/apiClient'
import { getExperimentReport } from '../../services/evaluationApi'
import {
  DEFENCE_MODE_LABELS,
  type DefenceMode,
  type ExperimentReport,
} from '../../types/evaluation'

function label(key: string): string {
  return key.replaceAll('_', ' ')
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return 'N/A'
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3)
  if (typeof value === 'string') return value
  if (Array.isArray(value)) return value.length === 0 ? 'none' : value.map(String).join(', ')
  return JSON.stringify(value)
}

function KeyValueSection({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data)
  if (entries.length === 0) return <p className="text-sm text-slate-500">No data.</p>
  return (
    <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-sm">
      {entries.map(([key, value]) => (
        <Fragment key={key}>
          <dt className="text-slate-600">{label(key)}</dt>
          <dd className="text-right font-medium">{formatValue(value)}</dd>
        </Fragment>
      ))}
    </dl>
  )
}

export function ExperimentReportPage() {
  const { experimentId } = useParams<{ experimentId: string }>()
  const [report, setReport] = useState<ExperimentReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!experimentId) return
    void getExperimentReport(experimentId)
      .then((data) => {
        setReport(data)
        setError(null)
      })
      .catch((cause: unknown) => {
        setError(toClientApiError(cause).message)
      })
      .finally(() => {
        setLoading(false)
      })
  }, [experimentId])

  if (loading) {
    return (
      <section aria-labelledby="experiment-report-title">
        <p role="status">Loading report…</p>
      </section>
    )
  }

  if (error || !report) {
    return (
      <section aria-labelledby="experiment-report-title">
        <p role="alert" className="text-red-700">
          {error ?? 'This report could not be found.'}
        </p>
        <Link to="/evaluation/experiments" className="card-link">
          Back to Experiments
        </Link>
      </section>
    )
  }

  const ars = report.ars_decomposition

  return (
    <>
      <style>{`
        @media print {
          .print-hidden { display: none !important; }
          .print-report { max-width: none !important; padding: 0 !important; }
          body { background: white !important; }
        }
      `}</style>
      <section
        className="print-report mx-auto max-w-3xl space-y-8 leading-relaxed"
        aria-labelledby="experiment-report-title"
      >
        <header className="print-hidden flex flex-wrap items-center justify-between gap-3">
          <Link to={`/evaluation/experiments/${report.experiment_id}`} className="card-link">
            Back to experiment
          </Link>
          <Button
            type="button"
            onClick={() => {
              window.print()
            }}
          >
            Print / Save as PDF
          </Button>
        </header>

        <header>
          <p className="eyebrow">Faculty report</p>
          <h1 id="experiment-report-title" className="text-2xl font-semibold">
            Experiment {report.experiment_id}
          </h1>
        </header>

        <section>
          <h2 className="text-lg font-semibold">Executive summary</h2>
          <p className="mt-2">{report.executive_summary}</p>
        </section>

        <section>
          <h2 className="text-lg font-semibold">Configuration</h2>
          <KeyValueSection data={report.configuration} />
        </section>

        <section>
          <h2 className="text-lg font-semibold">ATT&amp;CK techniques observed</h2>
          {report.attack_techniques_observed.length === 0 ? (
            <p className="text-sm text-slate-500">None observed.</p>
          ) : (
            <div className="mt-2 flex flex-wrap gap-2">
              {report.attack_techniques_observed.map((technique) => (
                <Badge key={technique} className="chip-muted">
                  {technique}
                </Badge>
              ))}
            </div>
          )}
        </section>

        <section>
          <h2 className="text-lg font-semibold">Detection evidence summary</h2>
          <KeyValueSection data={report.detection_evidence_summary} />
        </section>

        <section>
          <h2 className="text-lg font-semibold">Incident summary</h2>
          {report.incident_summary ? (
            <KeyValueSection data={report.incident_summary} />
          ) : (
            <p className="text-sm text-slate-500">No incident candidate was generated.</p>
          )}
        </section>

        <section>
          <h2 className="text-lg font-semibold">Attack graph &amp; blast radius</h2>
          <KeyValueSection data={report.attack_graph_and_blast_radius} />
        </section>

        <section>
          <h2 className="text-lg font-semibold">Response, verification &amp; rollback summary</h2>
          <KeyValueSection data={report.response_verification_rollback_summary} />
        </section>

        <section>
          <h2 className="text-lg font-semibold">MOP / MOE metrics</h2>
          {report.metrics ? (
            <div className="grid gap-6 sm:grid-cols-2">
              <div>
                <h3 className="text-sm font-semibold">Raw metrics</h3>
                <KeyValueSection data={report.metrics.raw_metrics} />
              </div>
              <div>
                <h3 className="text-sm font-semibold">Normalized metrics</h3>
                <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-sm">
                  {Object.entries(report.metrics.normalized_metrics).map(([key, metric]) => (
                    <Fragment key={key}>
                      <dt className="text-slate-600">{label(key)}</dt>
                      <dd className="text-right font-medium">
                        {metric.applicable ? formatValue(metric.value) : 'N/A'}
                      </dd>
                    </Fragment>
                  ))}
                </dl>
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">No computed metrics are available.</p>
          )}
        </section>

        <section>
          <h2 className="text-lg font-semibold">Mission Continuity Index</h2>
          <p className="mt-2 text-2xl font-semibold">
            {report.mission_continuity_index === null
              ? 'N/A'
              : report.mission_continuity_index.toFixed(3)}
          </p>
        </section>

        <section>
          <h2 className="text-lg font-semibold">Aegis Resilience Score decomposition</h2>
          {ars ? <KeyValueSection data={ars} /> : <p className="text-sm text-slate-500">N/A</p>}
        </section>

        {report.paired_baseline_comparison ? (
          <section>
            <h2 className="text-lg font-semibold">Paired baseline comparison</h2>
            <table className="mt-2 w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-300 text-xs uppercase tracking-wide">
                  <th className="py-1 pr-3">Metric</th>
                  {report.paired_baseline_comparison.available_modes.map((mode) => (
                    <th key={mode} className="py-1 pr-3">
                      {DEFENCE_MODE_LABELS[mode as DefenceMode]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {report.paired_baseline_comparison.rows.map((row) => (
                  <tr key={row.metric} className="border-b border-slate-100">
                    <td className="py-1 pr-3 font-medium">{label(row.metric)}</td>
                    {report.paired_baseline_comparison?.available_modes.map((mode) => {
                      const cell = row.values[mode]
                      return (
                        <td key={mode} className="py-1 pr-3">
                          {!cell
                            ? 'No experiment'
                            : cell.applicable
                              ? formatValue(cell.value)
                              : 'N/A'}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ) : null}

        <section>
          <h2 className="text-lg font-semibold">Limitations</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {report.limitations.map((limitation) => (
              <li key={limitation}>{limitation}</li>
            ))}
          </ul>
        </section>

        <section>
          <h2 className="text-lg font-semibold">Reproduction metadata</h2>
          <KeyValueSection data={report.reproduction} />
        </section>
      </section>
    </>
  )
}
