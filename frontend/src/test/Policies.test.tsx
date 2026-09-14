import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { PoliciesPage } from '../pages/blueAgent/PoliciesPage'
import * as policyApi from '../services/policyApi'
import type { PolicyDefinition } from '../types/policy'

vi.mock('../services/policyApi')

const policies: PolicyDefinition[] = [
  {
    policy_id: 'POL-001',
    name: 'Synthetic-only targets',
    purpose: 'Never permit a plan whose target is not a synthetic resource.',
    applies_to: 'Every candidate plan',
    decision_effect: 'Blocks execution if the recommendation is not marked synthetic.',
    enabled: true,
    synthetic: true,
  },
  {
    policy_id: 'POL-007',
    name: 'Failed verification requires rollback where reversible',
    purpose: 'A response that fails its containment check must be automatically undone.',
    applies_to: 'Post-execution verification',
    decision_effect: 'Triggers automatic synthetic rollback when reversible.',
    enabled: true,
    synthetic: true,
  },
]

beforeEach(() => {
  vi.mocked(policyApi.getPolicyCatalogue).mockResolvedValue(policies)
})

describe('Blue Agent Policies tab', () => {
  it('renders the read-only policy catalogue with id, purpose, and decision effect', async () => {
    render(<PoliciesPage />)
    expect(await screen.findByText('POL-001')).toBeInTheDocument()
    expect(screen.getByText('Synthetic-only targets')).toBeInTheDocument()
    expect(
      screen.getByText(/Never permit a plan whose target is not a synthetic resource\./),
    ).toBeInTheDocument()
    expect(screen.getByText('POL-007')).toBeInTheDocument()
    expect(screen.getAllByText('enabled').length).toBe(2)
  })

  it('surfaces a load failure without crashing', async () => {
    vi.mocked(policyApi.getPolicyCatalogue).mockRejectedValue(new Error('boom'))
    render(<PoliciesPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'The synthetic policy catalogue is unavailable.',
    )
  })
})
