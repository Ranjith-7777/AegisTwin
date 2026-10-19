import type { TwinLayers } from './CyberDigitalTwin'

/** Display options of a twin canvas (layers menu). */
export interface TwinViewOptions {
  layers: TwinLayers
  showProposed: boolean
  reducedMotion: boolean
}

export const DEFAULT_VIEW_OPTIONS: TwinViewOptions = {
  layers: { observed: true, correlated: true, predicted: true },
  showProposed: true,
  reducedMotion: false,
}
