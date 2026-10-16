import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { renderApp } from './test-utils'
import * as dataSourcesApi from '../services/dataSourcesApi'
import * as simulationApi from '../services/simulationApi'
import type { DataSource, DataSourceCatalogue, NetworkFlowEvaluation } from '../types/dataSources'

vi.mock('../services/dataSourcesApi')
vi.mock('../services/simulationApi')

const builtIn: DataSourceCatalogue['built_in'] = [
  {
    source_kind: 'synthetic',
    name: 'AegisArena scenario engine',
    status: 'active',
    description: 'Deterministic synthetic telemetry.',
  },
  {
    source_kind: 'live_readonly',
    name: 'Live telemetry (read-only)',
    status: 'not_implemented',
    description: 'No live collector exists.',
  },
]

// Fixture values for rendering only - not dataset results.
const source: DataSource = {
  source_id: 'src-tue',
  source_kind: 'replay',
  adapter: 'cicids2017',
  dataset_name: 'CIC-IDS2017',
  file_name: 'Tuesday-WorkingHours.pcap_ISCX.csv',
  file_sha256: 'a'.repeat(64),
  file_bytes: 1000,
  licence: 'Research use; cite ICISSP 2018.',
  citation: 'Sharafaldin et al.',
  provenance_notes_json: ['Testbed-local timestamps interpreted as ADT (UTC-03:00) - assumption.'],
  window_start: '2017-07-04T08:54:00-03:00',
  window_end: '2017-07-04T17:00:00-03:00',
  rows_read: 12,
  rows_accepted: 9,
  rows_rejected: 2,
  rows_duplicate: 1,
  rows_unmapped: 1,
  rows_timestamp_adjusted: 3,
  rows_rate_missing: 1,
  rejection_reasons_json: { negative_duration: 2 },
  unmapped_endpoints_json: { '192.168.10.200': 1 },
  label_counts_json: { BENIGN: 6, 'SSH-Patator': 3 },
  imported_by: 'test',
  imported_at: '2026-10-13T00:00:00Z',
}

const evaluation: NetworkFlowEvaluation = {
  evaluation_id: 'eval-1',
  model_version: 'network-flow-isolation-forest-v1',
  feature_schema_version: 'network-flow-v1',
  train_source_id: 'src-mon',
  eval_source_id: 'src-tue',
  protocol_json: {},
  metrics_json: {
    roc_auc: 0.5,
    average_precision: 0.25,
    precision: 0.5,
    recall: 0.5,
    f1: 0.5,
    false_positive_rate: 0.1,
    confusion_matrix: { tn: 5, fp: 1, fn: 1, tp: 2 },
    support: { benign: 6, attack: 3 },
    threshold: 0.6,
    calibration_observed_fpr: 0.01,
    train_rows_fit: 80,
    train_rows_total: 100,
    calibration_rows: 20,
    eval_rows: 9,
    per_label: { 'SSH-Patator': { flows: 3, flagged: 2, rate: 2 / 3 } },
  },
  created_at: '2026-10-13T00:00:00Z',
}

beforeEach(() => {
  vi.mocked(simulationApi.getScenarios).mockResolvedValue([])
  vi.mocked(simulationApi.getSimulationRuns).mockResolvedValue([])
})

describe('Data Sources page', () => {
  it('shows the blocked state with import instructions and invents no metrics', async () => {
    vi.mocked(dataSourcesApi.getDataSources).mockResolvedValue({
      simulation_only: true,
      built_in: builtIn,
      imported: [],
      import_instructions: 'Download the CIC-IDS2017 labelled-flow CSVs into datasets/raw.',
    })
    vi.mocked(dataSourcesApi.getLatestFlowEvaluation).mockResolvedValue(null)
    renderApp('/data-sources')
    expect(await screen.findByText('No recorded dataset imported')).toBeInTheDocument()
    expect(screen.getByText(/labelled-flow CSVs into datasets\/raw/)).toBeInTheDocument()
    expect(screen.getByText('No recorded-dataset evaluation yet')).toBeInTheDocument()
    expect(screen.queryByLabelText('Confusion matrix')).not.toBeInTheDocument()
    expect(screen.getByText('Live · read-only')).toBeInTheDocument()
    expect(screen.getByText(/Not implemented\./)).toBeInTheDocument()
  })

  it('labels recorded data as a replay and loads correlation findings on demand', async () => {
    vi.mocked(dataSourcesApi.getDataSources).mockResolvedValue({
      simulation_only: true,
      built_in: builtIn,
      imported: [source],
      import_instructions: '',
    })
    vi.mocked(dataSourcesApi.getLatestFlowEvaluation).mockResolvedValue(evaluation)
    vi.mocked(dataSourcesApi.getFlowFindings).mockResolvedValue({
      source_id: 'src-tue',
      ruleset_version: 'network-flow-rules-v1',
      window_minutes: 5,
      total_findings: 1,
      counts_by_rule: { brute_force: 1 },
      labels_note: 'Rules never read labels.',
      findings: [
        {
          rule: 'brute_force',
          window_start: '2017-07-04T10:00:00-03:00',
          window_end: '2017-07-04T10:05:00-03:00',
          src_ip: '172.16.0.1',
          dst_ip: '192.168.10.50',
          src_asset_id: 'external-user-01',
          dst_asset_id: 'api-gateway-01',
          summary: '60 connections to SSH (port 22) within 5 min.',
          flow_count: 60,
          dst_ports: [22],
          total_bytes: 1,
          mitre: { technique_id: 'T1110', name: 'Brute Force', rationale: 'Repeated connections.' },
          label_agreement: 1,
        },
      ],
    })
    renderApp('/data-sources')
    const card = await screen.findByLabelText(`Data source ${source.file_name}`)
    expect(within(card).getByText('Recorded replay')).toBeInTheDocument()
    expect(within(card).getByText(/evaluation only/)).toBeInTheDocument()
    expect(within(card).getByText('negative_duration')).toBeInTheDocument()
    expect(dataSourcesApi.getFlowFindings).not.toHaveBeenCalled()

    await userEvent.click(within(card).getByRole('button', { name: 'Run correlation rules' }))
    const findings = await within(card).findByLabelText('Correlation findings')
    expect(within(findings).getByText('T1110 Brute Force')).toBeInTheDocument()
    expect(
      within(findings).getByText(/projected: external-user-01 → api-gateway-01/),
    ).toBeInTheDocument()

    const panel = screen.getByLabelText('Recorded-dataset evaluation')
    expect(within(panel).getByLabelText('Confusion matrix')).toBeInTheDocument()
    expect(within(panel).getByText(/2 \/ 3/)).toBeInTheDocument()
  })
})
