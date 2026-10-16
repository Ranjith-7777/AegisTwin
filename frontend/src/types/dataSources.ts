export type SourceKind = 'synthetic' | 'replay' | 'live_readonly'

export interface DataSource {
  source_id: string
  source_kind: SourceKind
  adapter: string
  dataset_name: string
  file_name: string
  file_sha256: string
  file_bytes: number
  licence: string
  citation: string | null
  provenance_notes_json: string[]
  window_start: string | null
  window_end: string | null
  rows_read: number
  rows_accepted: number
  rows_rejected: number
  rows_duplicate: number
  rows_unmapped: number
  rows_timestamp_adjusted: number
  rows_rate_missing: number
  rejection_reasons_json: Record<string, number>
  unmapped_endpoints_json: Record<string, number>
  /** Ground truth for evaluation only - never a detection feature. */
  label_counts_json: Record<string, number>
  imported_by: string
  imported_at: string
}

export interface BuiltInSource {
  source_kind: SourceKind
  name: string
  status: 'active' | 'not_implemented'
  description: string
}

export interface DataSourceCatalogue {
  simulation_only: boolean
  built_in: BuiltInSource[]
  imported: DataSource[]
  import_instructions: string
}

export interface ConfusionMatrix {
  tn: number
  fp: number
  fn: number
  tp: number
}

export interface NetworkFlowMetrics {
  roc_auc: number | null
  average_precision: number | null
  precision: number | null
  recall: number | null
  f1: number | null
  false_positive_rate: number | null
  confusion_matrix: ConfusionMatrix
  support: { benign: number; attack: number }
  threshold: number
  calibration_observed_fpr: number
  train_rows_fit: number
  train_rows_total: number
  calibration_rows: number
  eval_rows: number
  per_label: Record<string, { flows: number; flagged: number; rate: number }>
}

export interface NetworkFlowEvaluation {
  evaluation_id: string
  model_version: string
  feature_schema_version: string
  train_source_id: string
  eval_source_id: string
  protocol_json: Record<string, unknown>
  metrics_json: NetworkFlowMetrics
  created_at: string
}

export interface FlowFinding {
  rule: 'brute_force' | 'port_scan' | 'volume' | 'suspicious_remote'
  window_start: string
  window_end: string
  src_ip: string
  dst_ip: string
  src_asset_id: string | null
  dst_asset_id: string | null
  summary: string
  flow_count: number
  dst_ports: number[]
  total_bytes: number
  mitre: { technique_id: string; name: string; rationale: string } | null
  label_agreement: number | null
}

export interface FlowFindingsResponse {
  source_id: string
  ruleset_version: string
  window_minutes: number
  total_findings: number
  counts_by_rule: Record<string, number>
  findings: FlowFinding[]
  labels_note: string
}
