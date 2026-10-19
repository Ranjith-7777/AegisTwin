import { Database, FileWarning, ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'

import { EmptyState } from '../components/common/EmptyState'
import { Badge, type BadgeTone } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader } from '../components/ui/card'
import {
  getDataSources,
  getFlowFindings,
  getLatestFlowEvaluation,
} from '../services/dataSourcesApi'
import type {
  DataSource,
  DataSourceCatalogue,
  FlowFindingsResponse,
  NetworkFlowEvaluation,
  SourceKind,
} from '../types/dataSources'

const KIND_LABEL: Record<SourceKind, string> = {
  synthetic: 'Synthetic',
  replay: 'Recorded replay',
  live_readonly: 'Live · read-only',
}
const KIND_TONE: Record<SourceKind, BadgeTone> = {
  synthetic: 'accent',
  replay: 'proposed',
  live_readonly: 'neutral',
}
const RULE_LABEL: Record<string, string> = {
  brute_force: 'Brute force',
  port_scan: 'Port scan',
  volume: 'Large outbound volume',
  suspicious_remote: 'Non-standard remote port',
}

function KindBadge({ kind }: { kind: SourceKind }) {
  return <Badge tone={KIND_TONE[kind]}>{KIND_LABEL[kind]}</Badge>
}

function fmt(value: number | null | undefined, digits = 3) {
  return value === null || value === undefined ? '—' : value.toFixed(digits)
}

function pct(value: number | null | undefined) {
  return value === null || value === undefined ? '—' : `${(value * 100).toFixed(1)}%`
}

function Counts({ entries, empty }: { entries: Record<string, number>; empty: string }) {
  const rows = Object.entries(entries)
  if (rows.length === 0)
    return <p className="m-0 text-[0.78rem] text-[var(--text-faint)]">{empty}</p>
  return (
    <ul className="m-0 grid gap-1 p-0 text-[0.78rem]">
      {rows.map(([key, value]) => (
        <li key={key} className="flex justify-between gap-3">
          <span className="font-mono">{key}</span>
          <span className="tabular-nums">{value.toLocaleString()}</span>
        </li>
      ))}
    </ul>
  )
}

function SourceCard({ source }: { source: DataSource }) {
  const [findings, setFindings] = useState<FlowFindingsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const runRules = () => {
    setLoading(true)
    setError(null)
    getFlowFindings(source.source_id)
      .then(setFindings)
      .catch(() => {
        setError('Correlation rules could not be evaluated for this source.')
      })
      .finally(() => {
        setLoading(false)
      })
  }
  const stats: [string, number][] = [
    ['Rows read', source.rows_read],
    ['Accepted', source.rows_accepted],
    ['Rejected', source.rows_rejected],
    ['Duplicates', source.rows_duplicate],
    ['Unmapped endpoints', source.rows_unmapped],
    ['Hour adjusted (no AM/PM)', source.rows_timestamp_adjusted],
    ['Rate missing (Infinity/NaN)', source.rows_rate_missing],
  ]
  return (
    <Card aria-label={`Data source ${source.file_name}`}>
      <CardHeader className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="panel-title m-0">
            {source.dataset_name} · {source.file_name}
          </h3>
          <p className="m-0 text-[0.75rem] text-[var(--text-faint)]">
            {source.window_start ? new Date(source.window_start).toLocaleString() : '—'} →{' '}
            {source.window_end ? new Date(source.window_end).toLocaleString() : '—'} · sha256{' '}
            <span className="font-mono">{source.file_sha256.slice(0, 12)}</span>
          </p>
        </div>
        <KindBadge kind={source.source_kind} />
      </CardHeader>
      <CardContent className="grid gap-4 lg:grid-cols-3">
        <dl className="m-0 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-[0.78rem]">
          {stats.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-[var(--text-dim)]">{label}</dt>
              <dd className="m-0 text-right tabular-nums">{value.toLocaleString()}</dd>
            </div>
          ))}
        </dl>
        <div className="grid gap-3">
          <div>
            <h4 className="m-0 mb-1 text-[0.78rem] font-semibold">Rejection reasons</h4>
            <Counts entries={source.rejection_reasons_json} empty="No rows rejected." />
          </div>
          <div>
            <h4 className="m-0 mb-1 text-[0.78rem] font-semibold">Top unmapped endpoints</h4>
            <Counts entries={source.unmapped_endpoints_json} empty="Every endpoint mapped." />
          </div>
        </div>
        <div className="grid gap-3">
          <div>
            <h4 className="m-0 mb-1 text-[0.78rem] font-semibold">
              Ground-truth labels <span className="font-normal">(evaluation only)</span>
            </h4>
            <Counts entries={source.label_counts_json} empty="Unlabelled source." />
          </div>
          <p className="m-0 text-[0.72rem] text-[var(--text-faint)]">{source.licence}</p>
          {source.provenance_notes_json.map((note) => (
            <p key={note} className="m-0 text-[0.72rem] text-[var(--text-faint)]">
              {note}
            </p>
          ))}
        </div>
      </CardContent>
      <CardContent className="grid gap-3 border-t border-[var(--border)] pt-4">
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onClick={runRules} disabled={loading}>
            {loading ? 'Evaluating rules…' : 'Run correlation rules'}
          </Button>
          <span className="text-[0.75rem] text-[var(--text-faint)]">
            Analysis only - findings can never trigger a response action.
          </span>
        </div>
        {error ? <p role="alert">{error}</p> : null}
        {findings ? (
          <section aria-label="Correlation findings" className="grid gap-2">
            <p className="m-0 text-[0.78rem]">
              {findings.total_findings.toLocaleString()} findings ·{' '}
              {Object.entries(findings.counts_by_rule)
                .map(([rule, count]) => `${RULE_LABEL[rule] ?? rule}: ${String(count)}`)
                .join(' · ') || 'none'}
            </p>
            <p className="m-0 text-[0.72rem] text-[var(--text-faint)]">{findings.labels_note}</p>
            {findings.findings.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="data-table w-full text-[0.76rem]">
                  <thead>
                    <tr>
                      <th>Window</th>
                      <th>Rule</th>
                      <th>Source → destination</th>
                      <th>Evidence</th>
                      <th>MITRE</th>
                      <th>Label agreement</th>
                    </tr>
                  </thead>
                  <tbody>
                    {findings.findings.map((finding) => (
                      <tr
                        key={`${finding.rule}-${finding.src_ip}-${finding.dst_ip}-${finding.window_start}`}
                      >
                        <td>{new Date(finding.window_start).toLocaleTimeString()}</td>
                        <td>{RULE_LABEL[finding.rule] ?? finding.rule}</td>
                        <td className="font-mono">
                          {finding.src_ip} → {finding.dst_ip}
                          {finding.dst_asset_id ? (
                            <span className="block font-sans text-[var(--text-faint)]">
                              projected: {finding.src_asset_id ?? '—'} → {finding.dst_asset_id}
                            </span>
                          ) : null}
                        </td>
                        <td>{finding.summary}</td>
                        <td title={finding.mitre?.rationale}>
                          {finding.mitre
                            ? `${finding.mitre.technique_id} ${finding.mitre.name}`
                            : 'Not mapped'}
                        </td>
                        <td>{pct(finding.label_agreement)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </section>
        ) : null}
      </CardContent>
    </Card>
  )
}

function EvaluationPanel({
  evaluation,
  sources,
}: {
  evaluation: NetworkFlowEvaluation
  sources: DataSource[]
}) {
  const metrics = evaluation.metrics_json
  const name = (id: string) => sources.find((item) => item.source_id === id)?.file_name ?? id
  const cm = metrics.confusion_matrix
  const headline: [string, string][] = [
    ['ROC-AUC', fmt(metrics.roc_auc)],
    ['Average precision', fmt(metrics.average_precision)],
    ['Precision', fmt(metrics.precision)],
    ['Recall', fmt(metrics.recall)],
    ['F1', fmt(metrics.f1)],
    ['False-positive rate', pct(metrics.false_positive_rate)],
  ]
  return (
    <Card aria-label="Recorded-dataset evaluation">
      <CardHeader>
        <h2 className="panel-title m-0">Network-flow detector evaluation</h2>
        <p className="m-0 text-[0.75rem] text-[var(--text-faint)]">
          {evaluation.model_version} · trained on benign {name(evaluation.train_source_id)} ·
          evaluated on {name(evaluation.eval_source_id)}. Threshold set from held-out benign flows
          only; labels used for these metrics alone.
        </p>
      </CardHeader>
      <CardContent className="grid gap-4 lg:grid-cols-3">
        <dl className="m-0 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-[0.8rem]">
          {headline.map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-[var(--text-dim)]">{label}</dt>
              <dd className="m-0 text-right font-semibold tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
        <table className="data-table text-[0.78rem]" aria-label="Confusion matrix">
          <thead>
            <tr>
              <th />
              <th>Predicted benign</th>
              <th>Predicted attack</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">Benign</th>
              <td>{cm.tn.toLocaleString()}</td>
              <td>{cm.fp.toLocaleString()}</td>
            </tr>
            <tr>
              <th scope="row">Attack</th>
              <td>{cm.fn.toLocaleString()}</td>
              <td>{cm.tp.toLocaleString()}</td>
            </tr>
          </tbody>
        </table>
        <div>
          <h3 className="m-0 mb-1 text-[0.78rem] font-semibold">Detection rate by label</h3>
          <ul className="m-0 grid gap-1 p-0 text-[0.78rem]">
            {Object.entries(metrics.per_label).map(([label, item]) => (
              <li key={label} className="flex justify-between gap-3">
                <span>{label}</span>
                <span className="tabular-nums">
                  {item.flagged.toLocaleString()} / {item.flows.toLocaleString()} ({pct(item.rate)})
                </span>
              </li>
            ))}
          </ul>
          <p className="m-0 mt-2 text-[0.72rem] text-[var(--text-faint)]">
            Fit on {metrics.train_rows_fit.toLocaleString()} benign flows, calibrated on{' '}
            {metrics.calibration_rows.toLocaleString()} (observed calibration FPR{' '}
            {pct(metrics.calibration_observed_fpr)}).
          </p>
        </div>
      </CardContent>
    </Card>
  )
}

export function DataSourcesPage() {
  const [catalogue, setCatalogue] = useState<DataSourceCatalogue | null>(null)
  const [evaluation, setEvaluation] = useState<NetworkFlowEvaluation | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void Promise.all([getDataSources(), getLatestFlowEvaluation()])
      .then(([sources, latest]) => {
        setCatalogue(sources)
        setEvaluation(latest)
      })
      .catch(() => {
        setError('Data sources are unavailable.')
      })
  }, [])

  return (
    <div className="space-y-5">
      <header className="page-heading">
        <h1>Data Sources</h1>
        <p>
          Where telemetry comes from. Recorded datasets are replays of past captures - never live
          traffic - and every source is analysis-only.
        </p>
      </header>
      {error ? <p role="alert">{error}</p> : null}
      {catalogue ? (
        <>
          <Card aria-label="Source types">
            <CardContent className="grid gap-3 pt-4 md:grid-cols-3">
              <div className="flex items-start gap-2">
                <ShieldCheck className="mt-0.5 size-4 text-[var(--shell-selected)]" aria-hidden />
                <p className="m-0 text-[0.8rem]">
                  SIMULATION_ONLY is <strong>{catalogue.simulation_only ? 'on' : 'off'}</strong>.
                  Recorded or live data can only inform recommendations; it never triggers real
                  firewall, IAM, Kubernetes or cloud changes.
                </p>
              </div>
              {catalogue.built_in.map((source) => (
                <div key={source.source_kind} className="grid gap-1">
                  <div className="flex items-center gap-2">
                    <KindBadge kind={source.source_kind} />
                    <span className="text-[0.8rem] font-semibold">{source.name}</span>
                  </div>
                  <p className="m-0 text-[0.76rem] text-[var(--text-dim)]">
                    {source.status === 'active' ? 'Active. ' : 'Not implemented. '}
                    {source.description}
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>

          <section aria-label="Imported recorded datasets" className="space-y-3">
            <h2 className="panel-title">Recorded datasets</h2>
            {catalogue.imported.length === 0 ? (
              <EmptyState
                icon={Database}
                title="No recorded dataset imported"
                detail={catalogue.import_instructions}
              />
            ) : (
              catalogue.imported.map((source) => (
                <SourceCard key={source.source_id} source={source} />
              ))
            )}
          </section>

          {evaluation ? (
            <EvaluationPanel evaluation={evaluation} sources={catalogue.imported} />
          ) : (
            <EmptyState
              icon={FileWarning}
              title="No recorded-dataset evaluation yet"
              detail="Metrics appear here only after a real benign window and a separate labelled window have been imported and evaluated. Nothing is estimated in the meantime."
            />
          )}
        </>
      ) : null}
    </div>
  )
}
