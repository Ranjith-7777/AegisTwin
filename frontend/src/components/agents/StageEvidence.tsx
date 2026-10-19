import { ExternalLink } from 'lucide-react'
import { useMemo, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { useAutonomyWorkflow } from '../../hooks/useAutonomyWorkflow'
import { useSimulationPlayback } from '../../hooks/useSimulationPlayback'
import { humanize, orchestrationState } from '../../lib/orchestrationState'
import { meaningfulPrediction } from '../../lib/prediction'
import type { StageId } from '../../lib/workflowStages'
import { Badge } from '../ui/badge'
import { KeyValue } from '../ui/panel'

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="inspector-section">
      <h3>{title}</h3>
      {children}
    </div>
  )
}

/** The persisted records behind one lifecycle stage. */
export function StageEvidence({ id }: { id: StageId }) {
  const playback = useSimulationPlayback()
  const workflow = useAutonomyWorkflow()
  const run = playback.activeRun
  const scenario = playback.scenarios.find((item) => item.scenario_id === run?.scenario_id)
  const orchestration = workflow.orchestration
  const topAnomalies = useMemo(
    () =>
      playback.assessmentTimeline
        .filter((item) => item.classification === 'anomalous')
        .sort((left, right) => right.hybrid_anomaly_score - left.hybrid_anomaly_score)
        .slice(0, 4),
    [playback.assessmentTimeline],
  )

  if (id === 'attack' || id === 'telemetry') {
    return run ? (
      <>
        <KeyValue
          rows={[
            ['Scenario', scenario?.name ?? run.scenario_id],
            ['Seed', <span className="mono">{run.seed}</span>],
            ['Run', <span className="mono">{run.simulation_run_id.slice(0, 13)}</span>],
            [
              'Events',
              `${String(playback.currentEventIndex)} / ${String(run.event_count)} replayed`,
            ],
            ['Replay', playback.playbackState],
          ]}
        />
        {scenario ? (
          <p className="m-0 mt-2 text-[0.76rem] text-[var(--text-dim)]">{scenario.description}</p>
        ) : null}
        <Link className="card-link mt-2 inline-flex items-center gap-1" to="/telemetry">
          Open live telemetry <ExternalLink className="size-3" />
        </Link>
      </>
    ) : (
      <Link className="card-link" to="/red-agent">
        Open the Red Agent lab to launch a scenario
      </Link>
    )
  }
  if (id === 'detection') {
    return (
      <>
        <KeyValue
          rows={[
            ['Model', playback.selectedModel?.model_type ?? '—'],
            [
              'Model id',
              <span className="mono">{playback.selectedModel?.model_id.slice(0, 8) ?? '—'}</span>,
            ],
            ['Calibration', playback.selectedModel?.calibration_method ?? '—'],
            [
              'Target FPR',
              playback.selectedModel
                ? `${(playback.selectedModel.target_false_positive_rate * 100).toFixed(1)}%`
                : '—',
            ],
          ]}
        />
        {topAnomalies.length > 0 ? (
          <Section title="Highest-scoring anomalies">
            <ul className="m-0 grid list-none gap-1.5 p-0 text-[0.76rem]">
              {topAnomalies.map((item) => (
                <li key={item.assessment_id} className="inset">
                  <span className="mono text-[var(--warn-text)]">
                    #{item.sequence_number} · {item.hybrid_anomaly_score.toFixed(3)}
                  </span>{' '}
                  <span className="text-[var(--text-faint)]">
                    (threshold {item.threshold.toFixed(3)})
                  </span>
                  <br />
                  <span className="text-[var(--text-dim)]">
                    {item.contributing_signals.slice(0, 3).join(' · ') || 'no dominant signal'}
                  </span>
                </li>
              ))}
            </ul>
          </Section>
        ) : null}
      </>
    )
  }
  if (id === 'correlation') {
    const incident = playback.currentIncidentCandidate
    return incident ? (
      <KeyValue
        rows={[
          ['Title', incident.title],
          ['Priority', incident.priority],
          ['Correlation score', incident.correlation_score.toFixed(2)],
          ['Evidence', String(incident.evidence_count)],
          ['Techniques', incident.observed_technique_ids.join(', ') || '—'],
          ['Assets', incident.involved_asset_ids.join(', ') || '—'],
        ]}
      />
    ) : (
      <p className="m-0 text-[0.78rem] text-[var(--text-faint)]">No incident yet.</p>
    )
  }
  if (id === 'prediction') {
    const hypotheses =
      meaningfulPrediction(playback.predictionTimeline)?.hypotheses.slice(0, 3) ?? []
    return hypotheses.length > 0 ? (
      <ul className="m-0 grid list-none gap-1.5 p-0 text-[0.76rem]">
        {hypotheses.map((item) => (
          <li key={item.hypothesis_id} className="inset">
            <span className="mono text-[var(--predicted-text)]">
              #{item.rank} {item.predicted_technique_id ?? item.hypothesis_type}
            </span>{' '}
            {item.predicted_asset_id ? `→ ${item.predicted_asset_id}` : ''}{' '}
            <span className="text-[var(--text-faint)]">
              score {item.prediction_score.toFixed(2)}
            </span>
            <p className="m-0 mt-0.5 text-[var(--text-dim)]">{item.rationale}</p>
          </li>
        ))}
      </ul>
    ) : (
      <p className="m-0 text-[0.78rem] text-[var(--text-faint)]">No hypotheses yet.</p>
    )
  }
  if (['response', 'what_if', 'policy', 'approval'].includes(id)) {
    const candidates = workflow.result?.comparison?.candidates ?? []
    return candidates.length > 0 ? (
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Candidate</th>
              <th className="num">Utility</th>
              <th className="num">Paths</th>
              <th>Policy</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((item) => (
              <tr
                key={item.recommendation_id}
                className={
                  item.recommended ? 'candidate-row is-recommended is-selected' : 'candidate-row'
                }
              >
                <td className="is-primary">
                  {item.playbook_name}
                  <span className="block text-[0.7rem] text-[var(--text-faint)]">
                    {item.target_id}
                  </span>
                </td>
                <td className="num">{item.utility_score.total.toFixed(1)}</td>
                <td className="num">
                  {item.security_gain_evidence.attack_paths_before}→
                  {item.security_gain_evidence.attack_paths_after}
                </td>
                <td>
                  <Badge tone={item.policy_pass ? 'ok' : 'danger'}>
                    {item.policy_pass ? 'pass' : item.policy_failed_ids.join(', ')}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <Link className="card-link mt-2 inline-block" to="/blue-agent/response-plans">
          Full candidate comparison
        </Link>
      </div>
    ) : (
      <p className="m-0 text-[0.78rem] text-[var(--text-faint)]">
        Candidate plans appear once the Blue workflow runs.
      </p>
    )
  }
  if (id === 'execution' || id === 'twin') {
    const execution = orchestration?.executions[0]
    return execution ? (
      <KeyValue
        rows={[
          ['Playbook', execution.playbook_id],
          ['Target', <span className="mono">{execution.target_id}</span>],
          ['State', humanize(execution.execution_state)],
          ['Changed nodes', execution.changed_node_ids.join(', ') || '—'],
          ['Changed links', execution.changed_edge_ids.join(', ') || '—'],
          ['Scope', 'Synthetic twin state only'],
        ]}
      />
    ) : (
      <p className="m-0 text-[0.78rem] text-[var(--text-faint)]">
        Nothing executed. Proposed effects are shown on the twin as dashed outlines only.
      </p>
    )
  }
  if (id === 'verification' || id === 'rollback') {
    const verification = orchestration?.verifications[0]
    const metrics = verification?.metrics ?? {}
    const pick = (key: string) => {
      const value = metrics[key]
      return typeof value === 'number' || typeof value === 'boolean' ? String(value) : '—'
    }
    return (
      <>
        {verification ? (
          <KeyValue
            rows={[
              ['Status', humanize(verification.verification_status)],
              [
                'Attack paths after',
                `${pick('actual_attack_paths_after')} (expected ${pick('expected_attack_paths_after')})`,
              ],
              [
                'Critical targets after',
                `${pick('actual_critical_targets_after')} (expected ${pick('expected_critical_targets_after')})`,
              ],
              [
                'Blast radius after',
                `${pick('actual_blast_radius_after')} (expected ${pick('expected_blast_radius_after')})`,
              ],
              ['Operational health', pick('operational_health_ok')],
            ]}
          />
        ) : (
          <p className="m-0 text-[0.78rem] text-[var(--text-faint)]">Not verified yet.</p>
        )}
        {orchestration?.rollback ? (
          <Section title="Rollback">
            <KeyValue
              rows={[
                ['State', humanize(orchestration.rollback.state)],
                ['Reason', orchestration.rollback.reason],
                ['Requested by', orchestration.rollback.requested_by],
              ]}
            />
          </Section>
        ) : null}
        <Link className="card-link mt-2 inline-block" to="/blue-agent/verification">
          Open verification & recovery
        </Link>
      </>
    )
  }
  // audit
  return orchestration ? (
    <>
      <KeyValue
        rows={[
          [
            'Orchestration',
            <span className="mono">{orchestration.orchestration_id.slice(0, 13)}</span>,
          ],
          ['State', orchestrationState(orchestration.current_state).label],
          ['Chained events', String(workflow.audit?.event_count ?? '—')],
          ['Integrity', workflow.audit ? (workflow.audit.valid ? 'valid' : 'BROKEN') : '—'],
          ['Algorithm', workflow.audit?.algorithm ?? '—'],
        ]}
      />
      <Section title="Agent decision trace">
        <ol className="m-0 grid list-none gap-1.5 p-0 text-[0.76rem]">
          {orchestration.decisions.map((decision) => (
            <li key={decision.agent_decision_id} className="inset">
              <strong className="text-[var(--text)]">{decision.agent_name}</strong>{' '}
              <Badge tone="neutral">{humanize(decision.decision)}</Badge>
              <p className="m-0 mt-0.5 text-[var(--text-dim)]">{decision.output_summary}</p>
            </li>
          ))}
        </ol>
      </Section>
      <Link
        className="card-link mt-2 inline-block"
        to={`/audit-trail?orchestration=${orchestration.orchestration_id}`}
      >
        Open the audit trail
      </Link>
    </>
  ) : (
    <p className="m-0 text-[0.78rem] text-[var(--text-faint)]">No orchestration to audit yet.</p>
  )
}
