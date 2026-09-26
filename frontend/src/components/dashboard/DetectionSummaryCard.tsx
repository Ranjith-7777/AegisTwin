import { Link } from 'react-router-dom'
import { Activity } from 'lucide-react'

import type { AnomalyAssessment, DetectionModel } from '../../types/detection'
import type { PredictionSnapshot } from '../../types/prediction'

interface DetectionSummaryCardProps {
  model: DetectionModel | null
  assessments: AnomalyAssessment[]
  prediction: PredictionSnapshot | null
}

/** What the platform has actually assessed for the current run — no invented AI claims. */
export function DetectionSummaryCard({
  model,
  assessments,
  prediction,
}: DetectionSummaryCardProps) {
  const anomalous = assessments.filter((item) => item.classification === 'anomalous').length
  return (
    <section className="card" aria-label="Detection status">
      <div className="card-head">
        <h2 className="card-title">
          <Activity className="size-4 shrink-0" aria-hidden="true" />
          Detection
        </h2>
        <Link className="card-link" to="/telemetry">
          Open Threat Analysis
        </Link>
      </div>
      <div className="p-4">
        {model ? (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <dt className="text-slate-500">Model</dt>
            <dd className="technical text-slate-900">{model.model_id.slice(0, 8)}</dd>
            <dt className="text-slate-500">Detector</dt>
            <dd className="text-slate-900">{model.model_type}</dd>
            <dt className="text-slate-500">Telemetry assessed</dt>
            <dd className="text-slate-900">{assessments.length} events</dd>
            <dt className="text-slate-500">Anomalous</dt>
            <dd className="text-slate-900">
              {anomalous} of {assessments.length}
            </dd>
            {prediction ? (
              <>
                <dt className="text-slate-500">Next-stage estimate</dt>
                <dd className="text-slate-900">
                  {prediction.current_stage_estimate.replaceAll('_', ' ')}
                </dd>
              </>
            ) : null}
          </dl>
        ) : (
          <div className="blue-empty">
            <p>No detection model has been selected for the current session.</p>
          </div>
        )}
      </div>
    </section>
  )
}
