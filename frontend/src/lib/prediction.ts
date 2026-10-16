import type { PredictionSnapshot } from '../types/prediction'

/**
 * The most recent prediction snapshot that actually carried hypotheses. At
 * the very end of a replay the predictor emits a final "run concluded"
 * snapshot with none; the last evidence-backed hypothesis remains the
 * meaningful one to show.
 */
export function meaningfulPrediction(timeline: PredictionSnapshot[]): PredictionSnapshot | null {
  for (let index = timeline.length - 1; index >= 0; index -= 1) {
    const snapshot = timeline[index]
    if (snapshot && snapshot.hypotheses.length > 0) return snapshot
  }
  return timeline.at(-1) ?? null
}
