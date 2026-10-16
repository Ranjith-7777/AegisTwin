import type { IncidentCandidate } from '../types/correlation'
import type { AnomalyAssessment } from '../types/detection'
import type { LiveTopologyOverlay } from '../types/liveTopology'
import type { Orchestration } from '../types/orchestration'
import type { PlaybackState, SimulationRun } from '../types/simulation'
import type { WorkflowRunResult } from '../types/workflow'

export type PostureTone = 'neutral' | 'danger' | 'warn' | 'ok' | 'predicted' | 'accent'

export interface Posture {
  label: string
  tone: PostureTone
  /** One sentence answering "what is happening and is it safe now?". */
  summary: string
  live: boolean
}

export interface PostureInput {
  run: SimulationRun | null
  playbackState: PlaybackState
  assessments: AnomalyAssessment[]
  incident: IncidentCandidate | null
  orchestration: Orchestration | null
  result: WorkflowRunResult | null
}

/** Derives the Command Centre headline strictly from persisted evidence. */
export function derivePosture(input: PostureInput): Posture {
  const { run, orchestration, incident } = input
  const anomalies = input.assessments.filter((item) => item.classification === 'anomalous').length
  if (!run) {
    return {
      label: 'Standby',
      tone: 'neutral',
      summary: 'No scenario is running. The synthetic cyber range is idle.',
      live: false,
    }
  }
  const state = orchestration?.current_state ?? null
  if (state === 'synthetic_rollback_completed') {
    return {
      label: 'Restored',
      tone: 'predicted',
      summary: 'The executed mitigation was rolled back and the prior twin state restored.',
      live: false,
    }
  }
  if (state === 'verified') {
    return {
      label: 'Contained',
      tone: 'ok',
      summary:
        'The Blue Agent executed a mitigation in the twin and verification confirmed the expected containment.',
      live: false,
    }
  }
  if (state === 'rollback_recommended' || state === 'synthetic_execution_failed') {
    return {
      label: 'Response failed',
      tone: 'danger',
      summary: 'The executed mitigation did not meet its objective - rollback is required.',
      live: false,
    }
  }
  if (state?.startsWith('awaiting_')) {
    return {
      label: 'Awaiting approval',
      tone: 'warn',
      summary: 'A validated response is ready and waits for a human decision.',
      live: false,
    }
  }
  if (state === 'synthetic_execution_completed') {
    return {
      label: 'Verifying',
      tone: 'accent',
      summary: 'The mitigation was executed in the twin and is being verified.',
      live: true,
    }
  }
  if (input.playbackState === 'playing' && anomalies > 0) {
    return {
      label: 'Under attack',
      tone: 'danger',
      summary: `${String(anomalies)} anomalous events detected so far${incident ? ` · ${incident.priority} incident correlated` : ''}.`,
      live: true,
    }
  }
  if (input.playbackState === 'playing') {
    return {
      label: 'Monitoring',
      tone: 'accent',
      summary: 'Attack replay in progress - no anomaly has crossed the threshold yet.',
      live: true,
    }
  }
  if (incident) {
    const recommendOnly = input.result && !orchestration && input.result.comparison
    return {
      label: 'Incident open',
      tone: 'warn',
      summary: recommendOnly
        ? 'Response plans are ranked; Recommend mode does not execute them.'
        : `A ${incident.priority} incident is correlated and not yet contained.`,
      live: false,
    }
  }
  if (anomalies > 0) {
    return {
      label: 'Anomalies',
      tone: 'warn',
      summary: `${String(anomalies)} anomalous events, no correlated incident.`,
      live: false,
    }
  }
  return {
    label: 'No threat detected',
    tone: 'ok',
    summary: 'The replay finished without anomalous evidence.',
    live: false,
  }
}

/** Assets currently carrying anomalous or incident evidence in the live twin. */
export function affectedAssetIds(live: LiveTopologyOverlay): string[] {
  return Object.values(live.nodes)
    .filter((node) => node.anomalous_observed || node.correlated)
    .map((node) => node.asset_id)
    .sort()
}
