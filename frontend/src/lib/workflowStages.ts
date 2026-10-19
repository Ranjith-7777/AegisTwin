import type { AutonomyMode } from '../types/autonomy'
import type { IncidentCandidate } from '../types/correlation'
import type { AnomalyAssessment, ScoringStatus } from '../types/detection'
import type { AuditIntegrity, Orchestration } from '../types/orchestration'
import type { PredictionSnapshot } from '../types/prediction'
import type { PlaybackState, SimulationRun } from '../types/simulation'
import type { WorkflowRunResult } from '../types/workflow'

/**
 * Derives the 14-stage AegisArena lifecycle purely from persisted backend
 * state (run, assessments, incident, prediction, the Workflow Coordinator
 * result, the orchestration record and the audit-chain check). Nothing here
 * is simulated client-side: a stage is only "completed" when the backend has
 * produced the corresponding record.
 */

export type StageStatus =
  | 'waiting'
  | 'running'
  | 'completed'
  | 'warning'
  | 'awaiting'
  | 'blocked'
  | 'failed'
  | 'rolled_back'
  | 'skipped'

export type StageId =
  | 'attack'
  | 'telemetry'
  | 'detection'
  | 'correlation'
  | 'prediction'
  | 'response'
  | 'what_if'
  | 'policy'
  | 'approval'
  | 'execution'
  | 'verification'
  | 'rollback'
  | 'twin'
  | 'audit'

export interface WorkflowStage {
  id: StageId
  index: number
  name: string
  /** What this stage does, in one line - shown in the explainer. */
  purpose: string
  status: StageStatus
  detail: string
}

export type WorkflowStatus = 'idle' | 'running' | 'done' | 'error'

export interface StageInputs {
  run: SimulationRun | null
  scenarioName?: string | null
  starting: boolean
  playbackState: PlaybackState
  currentEventIndex: number
  totalEventCount: number
  detectionEnabled: boolean
  scoringStatus: ScoringStatus
  assessments: AnomalyAssessment[]
  correlationEnabled: boolean
  correlationStatus: 'idle' | 'analyzing' | 'ready' | 'error'
  incident: IncidentCandidate | null
  predictionEnabled: boolean
  predictionStatus: 'idle' | 'analyzing' | 'ready' | 'error'
  prediction: PredictionSnapshot | null
  autonomyMode: AutonomyMode | null
  workflowStatus: WorkflowStatus
  workflowError: string | null
  result: WorkflowRunResult | null
  orchestration: Orchestration | null
  audit: AuditIntegrity | null
}

export const STATUS_LABEL: Record<StageStatus, string> = {
  waiting: 'Waiting',
  running: 'Running',
  completed: 'Completed',
  warning: 'Warning',
  awaiting: 'Awaiting approval',
  blocked: 'Blocked',
  failed: 'Failed',
  rolled_back: 'Rolled back',
  skipped: 'Not applicable',
}

const PURPOSE: Record<StageId, [string, string]> = {
  attack: [
    'Attack simulation',
    'The Red Agent replays a deterministic, seeded synthetic scenario.',
  ],
  telemetry: [
    'Telemetry generation',
    'Synthetic cloud events are persisted and replayed in order.',
  ],
  detection: [
    'Anomaly detection',
    'Isolation Forest + hybrid behavioural scoring flags unusual events.',
  ],
  correlation: [
    'Incident correlation',
    'Anomalous evidence is grouped into an incident and mapped to MITRE ATT&CK.',
  ],
  prediction: [
    'Progression prediction',
    'Ranked, evidence-backed hypotheses about the next attack stage.',
  ],
  response: [
    'Blue response analysis',
    'Candidate playbooks are scored by Defense Score and response utility.',
  ],
  what_if: [
    'What-if impact simulation',
    'Each candidate is applied to a cloned twin to measure attack-path reduction.',
  ],
  policy: [
    'Policy & safety gates',
    'POL-001..006 and the Safety Governor permit or block the selected plan.',
  ],
  approval: [
    'Approval',
    'The Approval Router decides between automatic execution and a human gate.',
  ],
  execution: [
    'Synthetic execution',
    'The selected playbook mutates the synthetic twin state - never real infrastructure.',
  ],
  verification: [
    'Verification',
    'Actual post-execution state is recomputed and checked against the expected objective.',
  ],
  rollback: [
    'Rollback',
    'If verification fails (or an administrator requests it) the twin is restored.',
  ],
  twin: [
    'Digital Twin reconciliation',
    'Executed (not proposed) mutations are reflected in the twin.',
  ],
  audit: ['Evaluation & audit', 'Every decision is appended to a SHA-256 hash-chained audit log.'],
}

const ORDER: StageId[] = [
  'attack',
  'telemetry',
  'detection',
  'correlation',
  'prediction',
  'response',
  'what_if',
  'policy',
  'approval',
  'execution',
  'verification',
  'rollback',
  'twin',
  'audit',
]

function stage(id: StageId, status: StageStatus, detail: string): WorkflowStage {
  const [name, purpose] = PURPOSE[id]
  return { id, index: ORDER.indexOf(id) + 1, name, purpose, status, detail }
}

function plural(count: number, word: string) {
  return `${String(count)} ${word}${count === 1 ? '' : 's'}`
}

export function deriveWorkflowStages(input: StageInputs): WorkflowStage[] {
  const {
    run,
    playbackState,
    orchestration,
    result,
    autonomyMode,
    workflowStatus,
    incident,
    prediction,
  } = input
  const replayDone = playbackState === 'completed'
  const stages: WorkflowStage[] = []

  // 1 Attack
  stages.push(
    run
      ? stage(
          'attack',
          'completed',
          `${input.scenarioName ?? run.scenario_id} · seed ${String(run.seed)} · ${plural(run.event_count, 'step')}`,
        )
      : input.starting
        ? stage('attack', 'running', 'Arming the Red Agent scenario…')
        : stage('attack', 'waiting', 'Select a scenario in the Red Agent lab to begin.'),
  )

  // 2 Telemetry
  const replayed = `${String(input.currentEventIndex)}/${String(input.totalEventCount || run?.event_count || 0)} events replayed`
  stages.push(
    !run
      ? stage('telemetry', 'waiting', 'No synthetic telemetry yet.')
      : playbackState === 'playing'
        ? stage('telemetry', 'running', replayed)
        : playbackState === 'paused'
          ? stage('telemetry', 'warning', `Replay paused · ${replayed}`)
          : replayDone
            ? stage('telemetry', 'completed', `${replayed} · persisted`)
            : playbackState === 'error'
              ? stage('telemetry', 'failed', 'Replay stream interrupted.')
              : stage('telemetry', 'completed', `${plural(run.event_count, 'event')} persisted`),
  )

  // 3 Detection
  const anomalous = input.assessments.filter((item) => item.classification === 'anomalous').length
  stages.push(
    !run
      ? stage('detection', 'waiting', 'Awaiting telemetry.')
      : !input.detectionEnabled
        ? stage('detection', 'skipped', 'Detection disabled for this run.')
        : input.scoringStatus === 'scoring'
          ? stage('detection', 'running', 'Scoring every event with the calibrated model…')
          : input.scoringStatus === 'error'
            ? stage('detection', 'failed', 'Scoring failed - see the Red Agent lab to retry.')
            : anomalous > 0
              ? stage(
                  'detection',
                  'completed',
                  `${String(anomalous)} of ${String(input.assessments.length)} replayed events anomalous`,
                )
              : replayDone
                ? stage('detection', 'warning', 'No event exceeded the calibrated threshold.')
                : stage('detection', 'running', 'Watching replayed events…'),
  )

  // 4 Correlation
  stages.push(
    !run || !input.detectionEnabled
      ? stage(
          'correlation',
          run ? 'skipped' : 'waiting',
          run ? 'Requires detection.' : 'Awaiting evidence.',
        )
      : !input.correlationEnabled
        ? stage('correlation', 'skipped', 'Correlation disabled for this run.')
        : input.correlationStatus === 'analyzing'
          ? stage('correlation', 'running', 'Grouping anomalous evidence…')
          : input.correlationStatus === 'error'
            ? stage('correlation', 'failed', 'Correlation failed.')
            : incident
              ? stage(
                  'correlation',
                  'completed',
                  `${incident.priority} incident · ${plural(incident.evidence_count, 'evidence item')} · ${incident.observed_technique_ids.join(', ') || 'no technique'}`,
                )
              : replayDone
                ? stage('correlation', 'warning', 'No incident was correlated from this run.')
                : stage('correlation', 'running', 'Awaiting correlated evidence in the replay…'),
  )

  // 5 Prediction
  const topHypothesis = prediction?.hypotheses[0]
  stages.push(
    !run || !input.correlationEnabled
      ? stage(
          'prediction',
          run ? 'skipped' : 'waiting',
          run ? 'Requires correlation.' : 'Awaiting incident.',
        )
      : !input.predictionEnabled
        ? stage('prediction', 'skipped', 'Prediction disabled for this run.')
        : input.predictionStatus === 'analyzing'
          ? stage('prediction', 'running', 'Ranking next-stage hypotheses…')
          : input.predictionStatus === 'error'
            ? stage('prediction', 'failed', 'Prediction failed.')
            : topHypothesis
              ? stage(
                  'prediction',
                  'completed',
                  `Top: ${topHypothesis.predicted_technique_id ?? topHypothesis.hypothesis_type}${topHypothesis.predicted_asset_id ? ` → ${topHypothesis.predicted_asset_id}` : ''} (${topHypothesis.prediction_score.toFixed(2)})`,
                )
              : prediction
                ? stage(
                    'prediction',
                    // Early snapshots legitimately lack evidence; only warn
                    // once the replay has ended without any hypothesis.
                    replayDone ? 'warning' : 'running',
                    prediction.insufficient_evidence_reason ?? 'Insufficient evidence.',
                  )
                : stage('prediction', replayDone ? 'warning' : 'waiting', 'Awaiting incident.'),
  )

  // 6-8 Blue reasoning
  const observe = autonomyMode === 'observe' || result?.autonomy_mode === 'observe'
  const comparison = result?.comparison ?? null
  const selected = comparison?.candidates.find((item) => item.recommended) ?? null
  if (observe) {
    const detail = 'Observe mode: evidence only - no response plan is generated.'
    stages.push(stage('response', 'skipped', detail))
    stages.push(stage('what_if', 'skipped', detail))
    stages.push(stage('policy', 'skipped', detail))
  } else if (workflowStatus === 'running' && !comparison) {
    stages.push(stage('response', 'running', 'Scoring candidate playbooks…'))
    stages.push(stage('what_if', 'running', 'Simulating each candidate on a cloned twin…'))
    stages.push(stage('policy', 'waiting', 'Awaiting a selected plan.'))
  } else if (workflowStatus === 'error' && !comparison) {
    const detail = input.workflowError ?? 'The Blue workflow failed.'
    stages.push(stage('response', 'failed', detail))
    stages.push(stage('what_if', 'waiting', 'Not reached.'))
    stages.push(stage('policy', 'waiting', 'Not reached.'))
  } else if (comparison) {
    stages.push(
      stage(
        'response',
        'completed',
        `${plural(comparison.candidates.length, 'candidate')} ranked${selected ? ` · selected ${selected.playbook_name}` : ''}`,
      ),
    )
    stages.push(
      selected
        ? stage(
            'what_if',
            'completed',
            `Attack paths ${String(selected.security_gain_evidence.attack_paths_before)} → ${String(selected.security_gain_evidence.attack_paths_after)} · critical targets ${String(selected.security_gain_evidence.critical_targets_reachable_before)} → ${String(selected.security_gain_evidence.critical_targets_reachable_after)}`,
          )
        : stage('what_if', 'completed', 'Every candidate was simulated on a cloned twin.'),
    )
    const governor = orchestration?.decisions.find(
      (item) => item.agent_name === 'Safety Governor Agent',
    )
    stages.push(
      !selected
        ? stage('policy', 'blocked', 'No candidate passed every applicable policy.')
        : governor?.decision === 'blocked'
          ? stage('policy', 'blocked', governor.output_summary)
          : stage(
              'policy',
              'completed',
              governor ? governor.output_summary : 'Selected plan passed every applicable policy.',
            ),
    )
  } else {
    const waiting = incident
      ? 'Ready - run the Blue workflow for this incident.'
      : 'Awaiting an incident.'
    stages.push(stage('response', 'waiting', waiting))
    stages.push(stage('what_if', 'waiting', 'Awaiting candidate plans.'))
    stages.push(stage('policy', 'waiting', 'Awaiting a selected plan.'))
  }

  // 9 Approval
  const state = orchestration?.current_state ?? null
  const approval = orchestration?.approvals[0] ?? null
  if (observe || autonomyMode === 'recommend' || result?.autonomy_mode === 'recommend') {
    stages.push(
      stage(
        'approval',
        'skipped',
        observe
          ? 'Observe mode never orchestrates a response.'
          : 'Recommend mode ranks plans but never orchestrates or executes them.',
      ),
    )
  } else if (!orchestration) {
    stages.push(
      stage(
        'approval',
        comparison && !selected ? 'blocked' : 'waiting',
        comparison && !selected ? 'Nothing to approve.' : 'Awaiting orchestration.',
      ),
    )
  } else if (state === 'rejected' && !approval) {
    stages.push(stage('approval', 'blocked', 'Blocked by the Safety Governor before approval.'))
  } else if (approval?.approval_state === 'pending') {
    stages.push(
      stage(
        'approval',
        'awaiting',
        `Awaiting synthetic ${approval.required_role} approval (${orchestration.required_approval_tier.replaceAll('_', ' ')}).`,
      ),
    )
  } else if (approval?.approval_state === 'rejected') {
    stages.push(stage('approval', 'blocked', `Rejected by ${approval.decided_by ?? 'operator'}.`))
  } else if (approval) {
    stages.push(stage('approval', 'completed', `Approved by ${approval.decided_by ?? 'operator'}.`))
  } else {
    stages.push(
      stage(
        'approval',
        'completed',
        'Automatic: autonomous mode, automatic-eligible playbook, every policy passed.',
      ),
    )
  }

  // 10 Execution
  const execution = orchestration?.executions[0] ?? null
  stages.push(
    execution
      ? execution.execution_state === 'failed_simulated'
        ? stage(
            'execution',
            'failed',
            `Simulated failure: ${execution.simulated_failure_reason ?? 'unknown'}.`,
          )
        : stage(
            'execution',
            'completed',
            `${execution.playbook_id} on ${execution.target_id} (synthetic state only)`,
          )
      : state === 'approved'
        ? stage('execution', 'waiting', 'Approved - ready for synthetic execution.')
        : stage('execution', 'waiting', 'Not executed.'),
  )

  // 11 Verification
  const verification = orchestration?.verifications[0] ?? null
  stages.push(
    verification
      ? verification.verification_status === 'successful_simulation'
        ? stage(
            'verification',
            'completed',
            'Actual outcome met the expected containment objective.',
          )
        : stage('verification', 'failed', 'Actual outcome fell short of the expected objective.')
      : execution && execution.execution_state !== 'failed_simulated'
        ? stage('verification', 'waiting', 'Executed - awaiting verification.')
        : stage('verification', 'waiting', 'Nothing to verify yet.'),
  )

  // 12 Rollback
  const rollback = orchestration?.rollback ?? null
  stages.push(
    rollback
      ? stage('rollback', 'rolled_back', rollback.reason)
      : state === 'rollback_recommended'
        ? stage('rollback', 'warning', 'Rollback recommended after failed verification.')
        : verification?.verification_status === 'successful_simulation'
          ? stage('rollback', 'skipped', 'Not required - verification succeeded.')
          : stage('rollback', 'waiting', 'Only triggered if verification fails.'),
  )

  // 13 Twin reconciliation
  stages.push(
    execution && execution.execution_state !== 'failed_simulated'
      ? rollback
        ? stage('twin', 'rolled_back', 'Prior twin state restored by synthetic rollback.')
        : stage(
            'twin',
            'completed',
            `${plural(execution.changed_node_ids.length, 'node')}, ${plural(execution.changed_edge_ids.length, 'link')} changed in the twin`,
          )
      : stage('twin', 'waiting', 'The twin shows proposed effects only until execution.'),
  )

  // 14 Evaluation & audit
  stages.push(
    input.audit
      ? input.audit.valid
        ? stage(
            'audit',
            'completed',
            `${plural(input.audit.event_count, 'chained event')} · SHA-256 chain valid`,
          )
        : stage(
            'audit',
            'failed',
            `Chain broken at sequence ${String(input.audit.first_invalid_sequence ?? '?')}.`,
          )
      : orchestration
        ? stage('audit', 'running', 'Verifying the audit chain…')
        : stage('audit', 'waiting', 'No orchestration to audit yet.'),
  )

  return stages
}

/** Compact eight-step rail used on the Command Centre. */
export interface RailStep {
  id: 'red' | 'detect' | 'correlate' | 'predict' | 'decide' | 'execute' | 'verify' | 'recover'
  label: string
  status: StageStatus
  detail: string
  stageIds: StageId[]
}

const RAIL: { id: RailStep['id']; label: string; stageIds: StageId[] }[] = [
  { id: 'red', label: 'Red', stageIds: ['attack', 'telemetry'] },
  { id: 'detect', label: 'Detect', stageIds: ['detection'] },
  { id: 'correlate', label: 'Correlate', stageIds: ['correlation'] },
  { id: 'predict', label: 'Predict', stageIds: ['prediction'] },
  { id: 'decide', label: 'Decide', stageIds: ['response', 'what_if', 'policy', 'approval'] },
  { id: 'execute', label: 'Execute', stageIds: ['execution'] },
  { id: 'verify', label: 'Verify', stageIds: ['verification'] },
  { id: 'recover', label: 'Recover', stageIds: ['rollback', 'twin', 'audit'] },
]

const PRIORITY: StageStatus[] = [
  'failed',
  'blocked',
  'awaiting',
  'running',
  'rolled_back',
  'warning',
]

export function aggregateStatus(statuses: StageStatus[]): StageStatus {
  for (const candidate of PRIORITY) if (statuses.includes(candidate)) return candidate
  if (statuses.every((item) => item === 'skipped')) return 'skipped'
  if (statuses.every((item) => item === 'completed' || item === 'skipped')) return 'completed'
  return 'waiting'
}

export function deriveRail(stages: WorkflowStage[]): RailStep[] {
  return RAIL.map((step) => {
    const members = stages.filter((item) => step.stageIds.includes(item.id))
    const status = aggregateStatus(members.map((item) => item.status))
    const focus =
      members.find((item) => item.status === status) ?? members[members.length - 1] ?? null
    return { ...step, status, detail: focus?.detail ?? '' }
  })
}

/** The first stage that still needs something to happen. */
export function currentStage(stages: WorkflowStage[]): WorkflowStage | null {
  return (
    stages.find((item) =>
      ['running', 'awaiting', 'blocked', 'failed', 'warning'].includes(item.status),
    ) ??
    stages.find((item) => item.status === 'waiting') ??
    null
  )
}
