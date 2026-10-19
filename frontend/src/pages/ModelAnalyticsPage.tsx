import { useEffect, useRef, useState, type SyntheticEvent } from 'react'

import { toClientApiError } from '../services/apiClient'
import {
  evaluateDetectionModel,
  getDetectionModels,
  trainDetectionModel,
} from '../services/detectionApi'
import type { DetectionModel, DetectionTrainingRequest, ModelEvaluation } from '../types/detection'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader } from '../components/ui/card'
import { AnomalyActivityChart } from '../components/dashboard/AnomalyActivityChart'
import { AnomalyExplainer } from '../components/detection/AnomalyExplainer'
import { Badge } from '../components/ui/badge'
import { KeyValue, Panel } from '../components/ui/panel'
import { useSimulationPlayback } from '../hooks/useSimulationPlayback'
import { Cpu } from 'lucide-react'

const defaults: DetectionTrainingRequest = {
  training_seed_range: { start: 1, end: 20 },
  validation_seed_range: { start: 21, end: 30 },
  evaluation_seed_range: { start: 31, end: 40 },
  random_state: 42,
  target_false_positive_rate: 0.02,
}

function displayMetric(value: unknown): string {
  return typeof value === 'number' || typeof value === 'string' ? String(value) : 'unavailable'
}

export function ModelAnalyticsPage() {
  const playback = useSimulationPlayback()
  const [models, setModels] = useState<DetectionModel[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [request, setRequest] = useState(defaults)
  const [evaluation, setEvaluation] = useState<ModelEvaluation | null>(null)
  const [busy, setBusy] = useState<'loading' | 'training' | 'evaluating' | null>('loading')
  const [error, setError] = useState<string | null>(null)
  const statusRef = useRef<HTMLDivElement>(null)

  async function loadModels() {
    const data = (await getDetectionModels()).filter((model) => model.synthetic)
    setModels(data)
    setSelectedId((current) => current || data[0]?.model_id || '')
  }
  useEffect(() => {
    void getDetectionModels()
      .then((data) => {
        const synthetic = data.filter((model) => model.synthetic)
        setModels(synthetic)
        setSelectedId(synthetic[0]?.model_id ?? '')
      })
      .catch((reason: unknown) => {
        setError(toClientApiError(reason).message)
      })
      .finally(() => {
        setBusy(null)
      })
  }, [])
  function rangeField(
    name: 'training_seed_range' | 'validation_seed_range' | 'evaluation_seed_range',
    edge: 'start' | 'end',
    value: number,
  ) {
    setRequest((current) => ({ ...current, [name]: { ...current[name], [edge]: value } }))
  }
  async function train(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy('training')
    setError(null)
    setEvaluation(null)
    try {
      const result = await trainDetectionModel(request)
      await loadModels()
      setSelectedId(result.model_id)
      statusRef.current?.focus()
    } catch (reason) {
      setError(toClientApiError(reason).message)
      statusRef.current?.focus()
    } finally {
      setBusy(null)
    }
  }
  async function evaluate() {
    if (!selectedId) return
    setBusy('evaluating')
    setError(null)
    try {
      setEvaluation(await evaluateDetectionModel(selectedId))
    } catch (reason) {
      setError(toClientApiError(reason).message)
    } finally {
      setBusy(null)
    }
  }
  const activeModel =
    playback.selectedModel ??
    models.find((model) => !('derived_from_model_id' in model.configuration_json)) ??
    null
  return (
    <div className="page-stack">
      <header className="page-heading">
        <div>
          <p className="eyebrow">System · Detection</p>
          <h1>Detection Models</h1>
          <p>
            Isolation Forest plus a calibrated hybrid behavioural score, trained only on synthetic
            normal-operation telemetry. Reproducible from seeds; artifacts are rebuilt
            deterministically if missing.
          </p>
        </div>
      </header>
      <div className="split-2">
        <Panel title="Active model" icon={<Cpu className="size-4" />}>
          {activeModel ? (
            <div className="grid gap-2">
              <div className="flex flex-wrap items-center gap-1.5">
                <Badge tone="accent">{activeModel.model_type}</Badge>
                <Badge tone={activeModel.artifact_available === false ? 'warn' : 'ok'}>
                  {activeModel.artifact_available === false
                    ? 'artifact rebuilds on first use'
                    : 'artifact available'}
                </Badge>
                <Badge tone="neutral">
                  {playback.selectedModel ? 'used by the live run' : 'latest trained'}
                </Badge>
              </div>
              <KeyValue
                rows={[
                  ['Model', <span className="mono">{activeModel.model_id.slice(0, 13)}</span>],
                  ['Feature schema', activeModel.feature_schema_version],
                  ['Calibration', activeModel.calibration_method],
                  [
                    'Target false-positive rate',
                    `${(activeModel.target_false_positive_rate * 100).toFixed(1)}%`,
                  ],
                  ['Calibrated threshold', activeModel.calibrated_threshold.toFixed(3)],
                  [
                    'Training / validation events',
                    `${String(activeModel.training_event_count)} / ${String(activeModel.validation_event_count)}`,
                  ],
                  ['Random state', String(activeModel.random_state)],
                ]}
              />
            </div>
          ) : (
            <p className="m-0 text-[0.8rem] text-[var(--text-faint)]">
              No detection model yet - train one below or from the Red Agent lab.
            </p>
          )}
        </Panel>
        <AnomalyExplainer />
      </div>
      <AnomalyActivityChart />
      <div ref={statusRef} tabIndex={-1} aria-live="polite">
        {error ? (
          <p role="alert" className="text-red-700">
            {error}
          </p>
        ) : busy ? (
          <p className="text-slate-500">{busy}…</p>
        ) : null}
      </div>
      <Card>
        <CardHeader>
          <div>
            <p className="eyebrow">Persisted models</p>
            <h2 className="panel-title">Model listing</h2>
          </div>
        </CardHeader>
        <CardContent>
          {models.length === 0 && !busy ? (
            <p>No synthetic detection model is available.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    {[
                      'Model ID',
                      'Type',
                      'Schema',
                      'Calibration',
                      'Target FPR',
                      'Threshold',
                      'Train / validation',
                      'Fingerprint',
                      'Artifact',
                      'Created',
                    ].map((label) => (
                      <th className="p-2" key={label}>
                        {label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {models.map((model) => (
                    <tr className="border-t border-slate-200" key={model.model_id}>
                      <td className="p-2">
                        <button
                          className="technical text-blue-600"
                          onClick={() => {
                            setSelectedId(model.model_id)
                          }}
                        >
                          {model.model_id.slice(0, 8)}
                        </button>
                      </td>
                      <td>{model.model_type}</td>
                      <td>{model.feature_schema_version}</td>
                      <td>
                        {model.calibration_version}
                        <br />
                        {model.calibration_method}
                      </td>
                      <td>{model.target_false_positive_rate}</td>
                      <td>{model.calibrated_threshold.toFixed(3)}</td>
                      <td>
                        {model.training_event_count} / {model.validation_event_count}
                      </td>
                      <td className="technical">{model.dataset_fingerprint.slice(0, 10)}</td>
                      <td>
                        {'derived_from_model_id' in model.configuration_json ? (
                          <Badge tone="neutral">evaluation identity</Badge>
                        ) : model.artifact_available === false ? (
                          <Badge tone="warn">rebuilds on use</Badge>
                        ) : (
                          <Badge tone="ok">available</Badge>
                        )}
                      </td>
                      <td>{new Date(model.created_at).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <div>
            <p className="eyebrow">Safe demo configuration</p>
            <h2 className="panel-title">Train synthetic model</h2>
          </div>
        </CardHeader>
        <CardContent>
          <p className="mb-4 text-sm text-slate-500">
            Training uses synthetic normal-operation telemetry only.
          </p>
          <form
            className="simulation-form"
            onSubmit={(event) => {
              void train(event)
            }}
          >
            {(
              ['training_seed_range', 'validation_seed_range', 'evaluation_seed_range'] as const
            ).flatMap((name) =>
              (['start', 'end'] as const).map((edge) => (
                <label key={`${name}-${edge}`}>
                  <span>
                    {name.replaceAll('_', ' ')} {edge}
                  </span>
                  <input
                    type="number"
                    min="0"
                    value={request[name][edge]}
                    onChange={(event) => {
                      rangeField(name, edge, event.currentTarget.valueAsNumber)
                    }}
                  />
                </label>
              )),
            )}
            <label>
              <span>Random state</span>
              <input
                type="number"
                value={request.random_state}
                onChange={(event) => {
                  setRequest({ ...request, random_state: event.currentTarget.valueAsNumber })
                }}
              />
            </label>
            <label>
              <span>Target false-positive rate</span>
              <input
                type="number"
                min="0.001"
                max="0.49"
                step="0.001"
                value={request.target_false_positive_rate}
                onChange={(event) => {
                  setRequest({
                    ...request,
                    target_false_positive_rate: event.currentTarget.valueAsNumber,
                  })
                }}
              />
            </label>
            <Button disabled={busy !== null}>Create Synthetic Demo Model</Button>
          </form>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <div>
            <p className="eyebrow">Held-out synthetic data</p>
            <h2 className="panel-title">Evaluate model</h2>
          </div>
        </CardHeader>
        <CardContent>
          <label className="block text-sm text-slate-500">
            Selected model
            <select
              aria-label="Model to evaluate"
              className="ml-3 bg-slate-50 p-2"
              value={selectedId}
              onChange={(event) => {
                setSelectedId(event.target.value)
                setEvaluation(null)
              }}
            >
              {models.map((model) => (
                <option key={model.model_id} value={model.model_id}>
                  {model.model_id}
                </option>
              ))}
            </select>
          </label>
          <Button
            className="mt-4"
            onClick={() => {
              void evaluate()
            }}
            disabled={!selectedId || busy !== null}
          >
            Evaluate Synthetic Model
          </Button>
          {evaluation ? (
            <div className="mt-5">
              <strong>Synthetic benchmark evaluation — not production performance.</strong>
              <dl className="playback-facts">
                <div>
                  <dt>Hybrid precision</dt>
                  <dd>{evaluation.precision.toFixed(3)}</dd>
                </div>
                <div>
                  <dt>Hybrid recall</dt>
                  <dd>{evaluation.recall.toFixed(3)}</dd>
                </div>
                <div>
                  <dt>Hybrid F1</dt>
                  <dd>{evaluation.f1_score.toFixed(3)}</dd>
                </div>
                <div>
                  <dt>Held-out normal FPR</dt>
                  <dd>{evaluation.false_positive_rate.toFixed(3)}</dd>
                </div>
                <div>
                  <dt>Suspicious-run detection rate</dt>
                  <dd>
                    {String(
                      evaluation.run_level_metrics.suspicious_run_detection_rate ?? 'unavailable',
                    )}
                  </dd>
                </div>
                <div>
                  <dt>Pure Isolation Forest F1</dt>
                  <dd>{String(evaluation.pure_isolation_metrics.f1_score ?? 'unavailable')}</dd>
                </div>
                <div>
                  <dt>Rule baseline F1</dt>
                  <dd>{displayMetric(evaluation.baseline_metrics.f1_score)}</dd>
                </div>
                <div>
                  <dt>Event-manifest F1</dt>
                  <dd>{String(evaluation.event_level_metrics.f1_score ?? 'unavailable')}</dd>
                </div>
                <div>
                  <dt>Scenario-wide F1</dt>
                  <dd>{String(evaluation.scenario_wide_metrics.f1_score ?? 'unavailable')}</dd>
                </div>
                <div>
                  <dt>Schema / calibration</dt>
                  <dd>
                    {evaluation.feature_schema_version} / {evaluation.calibration_method}
                  </dd>
                </div>
              </dl>
            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-500">No evaluation has been run in this view.</p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
