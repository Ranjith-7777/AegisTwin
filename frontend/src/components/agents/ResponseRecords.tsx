import {
  CircleCheck,
  CircleDashed,
  Download,
  FileJson,
  FileText,
  RotateCcw,
  ScrollText,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { useAutonomyWorkflow } from '../../hooks/useAutonomyWorkflow'
import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { formatClock } from '../../lib/activity'
import { humanize } from '../../lib/orchestrationState'
import { getIncidentEvidence } from '../../services/correlationApi'
import { getAudit } from '../../services/orchestrationApi'
import type { IncidentEvidence } from '../../types/correlation'
import { Button } from '../ui/button'
import { useDecisionActions } from '../workflow/useDecisionActions'

function outcomeTone(decision: string): string {
  if (/fail|reject|block|broken/.test(decision)) return 'danger'
  if (/await|pending|recommend/.test(decision)) return 'warn'
  if (/complete|success|verified|approved|validated|selected|automatic|restored/.test(decision))
    return 'ok'
  return 'neutral'
}

/** Saves real records as a JSON file in the browser (nothing is uploaded). */
function saveJson(name: string, data: unknown) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }),
  )
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = name
  anchor.click()
  URL.revokeObjectURL(url)
}

/** Agent decisions, execution and rollback of the current orchestration. */
export function ExecutionState() {
  const { orchestration } = useAutonomyWorkflow()
  const rows = [
    ...(orchestration?.decisions.map((item) => ({
      id: item.agent_decision_id,
      at: item.created_at,
      step: humanize(item.decision_type),
      actor: item.agent_name.replace(/ Agent$/, ''),
      outcome: item.decision,
    })) ?? []),
    ...(orchestration?.rollback
      ? [
          {
            id: orchestration.rollback.rollback_id,
            at: orchestration.updated_at,
            step: 'Synthetic rollback',
            actor: orchestration.rollback.requested_by,
            outcome: orchestration.rollback.state,
          },
        ]
      : []),
  ].sort((left, right) => left.at.localeCompare(right.at))
  return (
    <section className="panel" aria-label="Execution state">
      <header className="panel-head">
        <div>
          <h2 className="panel-title">Execution State</h2>
          <p className="panel-subtitle">Agent decisions of this orchestration (UTC)</p>
        </div>
        {orchestration ? (
          <Link
            className="card-link"
            to={`/audit-trail?orchestration=${orchestration.orchestration_id}`}
          >
            Audit trail
          </Link>
        ) : null}
      </header>
      <div className="panel-body is-flush is-scroll">
        {rows.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Step</th>
                <th>Executed by</th>
                <th>Outcome</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="mono">{formatClock(row.at)}</td>
                  <td className="is-primary">{row.step}</td>
                  <td>{row.actor}</td>
                  <td>
                    <span className={`state-pill tone-${outcomeTone(row.outcome)}`}>
                      {humanize(row.outcome)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="empty-state">
            No orchestration yet - nothing has been planned or executed.
          </p>
        )}
      </div>
    </section>
  )
}

/** Reversibility of each planned step and the human-gated rollback. */
export function RollbackStatus() {
  const workflow = useAutonomyWorkflow()
  const actions = useDecisionActions()
  const orchestration = workflow.orchestration
  const execution = orchestration?.executions[0] ?? null
  return (
    <section className="panel" aria-label="Rollback status">
      <header className="panel-head">
        <div>
          <h2 className="panel-title">Rollback Status</h2>
          <p className="panel-subtitle">Restores the twin state captured before execution</p>
        </div>
        {actions.rollbackAvailable ? (
          <Button
            size="sm"
            variant="outline"
            disabled={!actions.canRollback || actions.busy}
            title={actions.canRollback ? undefined : 'Rollback requires the ADMIN role.'}
            onClick={() => {
              actions.open('rollback')
            }}
          >
            <RotateCcw /> Run rollback
          </Button>
        ) : null}
      </header>
      <div className="panel-body is-scroll">
        {orchestration ? (
          <ul className="check-list">
            {orchestration.plan_steps.map((step) => (
              <li key={step.plan_step_id}>
                {step.current_status.includes('completed') ? (
                  <CircleCheck className="text-[var(--ok)]" aria-hidden="true" />
                ) : (
                  <CircleDashed className="text-[var(--text-faint)]" aria-hidden="true" />
                )}
                <span className="label" title={step.rationale}>
                  {humanize(step.playbook_id)}
                </span>
                <span className="meta">{step.reversibility}</span>
                <span className={`state-pill tone-${outcomeTone(step.current_status)}`}>
                  {humanize(step.current_status)}
                </span>
              </li>
            ))}
            <li>
              {orchestration.rollback ? (
                <CircleCheck className="text-[var(--accent)]" aria-hidden="true" />
              ) : (
                <CircleDashed className="text-[var(--text-faint)]" aria-hidden="true" />
              )}
              <span className="label">Twin state restore</span>
              <span className="meta">
                {execution ? (execution.reversible ? 'reversible' : 'irreversible') : '—'}
              </span>
              <span
                className={`state-pill tone-${orchestration.rollback ? 'predicted' : actions.rollbackAvailable ? 'accent' : 'neutral'}`}
              >
                {orchestration.rollback
                  ? 'Rolled back'
                  : actions.rollbackAvailable
                    ? 'Ready'
                    : 'Not applicable'}
              </span>
            </li>
          </ul>
        ) : (
          <p className="empty-state">Rollback becomes available after a verified execution.</p>
        )}
        {orchestration?.rollback ? (
          <p className="m-0 mt-2 text-[0.74rem] text-[var(--text-faint)]">
            Reason: {orchestration.rollback.reason}
          </p>
        ) : null}
      </div>
      {actions.element}
    </section>
  )
}

/** Correlation evidence behind the incident plus exportable records. */
export function EvidenceArtifacts() {
  const playback = useSimulationPlayback()
  const { orchestration } = useAutonomyWorkflow()
  const incident = playback.currentIncidentCandidate
  const incidentId = incident?.incident_candidate_id ?? null
  const [evidence, setEvidence] = useState<{ id: string; items: IncidentEvidence[] }>({
    id: '',
    items: [],
  })
  const [auditError, setAuditError] = useState<string | null>(null)
  useEffect(() => {
    if (!incidentId) return
    let cancelled = false
    void getIncidentEvidence(incidentId)
      .then((items) => {
        if (!cancelled) setEvidence({ id: incidentId, items })
      })
      .catch(() => {
        if (!cancelled) setEvidence({ id: incidentId, items: [] })
      })
    return () => {
      cancelled = true
    }
  }, [incidentId])
  const items =
    evidence.id === incidentId
      ? [...evidence.items].sort(
          (left, right) => right.contribution_score - left.contribution_score,
        )
      : []
  return (
    <section className="panel" aria-label="Evidence and artifacts">
      <header className="panel-head">
        <div>
          <h2 className="panel-title">Evidence & Artifacts</h2>
          <p className="panel-subtitle">
            {incident ? `${String(incident.evidence_count)} evidence items` : 'No incident'} ·
            exports are generated in your browser
          </p>
        </div>
      </header>
      <div className="panel-body is-scroll">
        {items.length ? (
          <ul className="evidence-list">
            {items.slice(0, 6).map((item) => (
              <li key={item.evidence_id}>
                <FileText aria-hidden="true" />
                <span className="min-w-0">
                  <p title={item.rationale}>{item.rationale}</p>
                  <small>
                    seq #{item.sequence_number} · contribution {item.contribution_score.toFixed(2)}
                  </small>
                </span>
                <span className="type-pill">{humanize(item.evidence_type)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="m-0 text-[0.78rem] text-[var(--text-faint)]">
            {incident ? 'Loading evidence…' : 'Evidence appears once an incident is correlated.'}
          </p>
        )}
        <div className="download-row mt-2">
          <Button
            size="sm"
            variant="outline"
            disabled={!incident}
            onClick={() => {
              if (incident)
                saveJson(`incident-${incident.incident_candidate_id.slice(0, 8)}.json`, {
                  incident,
                  evidence: items,
                })
            }}
          >
            <FileJson /> Incident evidence
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!orchestration}
            onClick={() => {
              if (!orchestration) return
              setAuditError(null)
              void getAudit(orchestration.orchestration_id)
                .then((events) => {
                  saveJson(`audit-${orchestration.orchestration_id.slice(0, 8)}.json`, events)
                })
                .catch(() => {
                  setAuditError('The audit chain could not be loaded.')
                })
            }}
          >
            <ScrollText /> Audit chain
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!orchestration}
            onClick={() => {
              if (orchestration)
                saveJson(
                  `orchestration-${orchestration.orchestration_id.slice(0, 8)}.json`,
                  orchestration,
                )
            }}
          >
            <Download /> Orchestration
          </Button>
        </div>
        {auditError ? (
          <p className="m-0 mt-1 text-[0.74rem] text-[var(--danger-text)]" role="alert">
            {auditError}
          </p>
        ) : null}
      </div>
    </section>
  )
}
