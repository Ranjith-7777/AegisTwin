import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { getRunIncidents } from '../../services/correlationApi'
import { getDetectionModels } from '../../services/detectionApi'
import { getSimulationRuns } from '../../services/simulationApi'
import type { IncidentCandidate } from '../../types/correlation'
import type { DetectionModel } from '../../types/detection'
import type { SimulationRun } from '../../types/simulation'

/**
 * Shared run/model/incident/sequence selection for the Blue Agent tabs,
 * persisted in the URL so switching tabs (Overview / Agent Workflow /
 * Response Plans / Policies / Verification) keeps the same context and the
 * selection survives a reload or a shared link.
 */
export function useBlueAgentSelection() {
  const [params, setParams] = useSearchParams()
  const [runs, setRuns] = useState<SimulationRun[]>([])
  const [models, setModels] = useState<DetectionModel[]>([])
  const [candidates, setCandidates] = useState<IncidentCandidate[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)

  const runId = params.get('run') ?? ''
  const modelId = params.get('model') ?? ''
  const candidateId = params.get('incident') ?? ''
  const sequence = Number(params.get('sequence') ?? '0') || 0
  const orchestrationId = params.get('orchestration') ?? ''

  useEffect(() => {
    void Promise.all([getSimulationRuns(), getDetectionModels()])
      .then(([runItems, modelItems]) => {
        setRuns(runItems)
        setModels(modelItems.filter((item) => item.synthetic))
      })
      .catch(() => {
        setLoadError('Synthetic run/model prerequisites are unavailable.')
      })
  }, [])

  useEffect(() => {
    if (!runId) return
    void getRunIncidents(runId)
      .then((page) => {
        setCandidates(page.items)
      })
      .catch(() => {
        setCandidates([])
      })
  }, [runId])

  interface SelectionParams {
    run: string
    model: string
    incident: string
    sequence: number
    orchestration: string
  }

  function setParam(merged: URLSearchParams, key: keyof SelectionParams, value: string | number) {
    if (value === '' || value === 0) merged.delete(key)
    else merged.set(key, String(value))
  }

  function update(next: Partial<SelectionParams>) {
    setParams(
      (current) => {
        const merged = new URLSearchParams(current)
        if (next.run !== undefined) setParam(merged, 'run', next.run)
        if (next.model !== undefined) setParam(merged, 'model', next.model)
        if (next.incident !== undefined) setParam(merged, 'incident', next.incident)
        if (next.sequence !== undefined) setParam(merged, 'sequence', next.sequence)
        if (next.orchestration !== undefined) setParam(merged, 'orchestration', next.orchestration)
        return merged
      },
      { replace: true },
    )
  }

  return {
    runs,
    models,
    candidates: runId ? candidates : [],
    loadError,
    runId,
    modelId,
    candidateId,
    sequence,
    orchestrationId,
    setRunId: (value: string) => {
      update({ run: value, model: '', incident: '', sequence: 0 })
    },
    setModelId: (value: string) => {
      update({ model: value })
    },
    setCandidateId: (value: string) => {
      const candidate = candidates.find((item) => item.incident_candidate_id === value)
      update({ incident: value, sequence: candidate?.latest_sequence_number ?? 0 })
    },
    setSequence: (value: number) => {
      update({ sequence: value })
    },
    setOrchestrationId: (value: string) => {
      update({ orchestration: value })
    },
  }
}
