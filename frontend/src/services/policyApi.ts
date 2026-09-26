import { apiClient } from './apiClient'
import type { PolicyDefinition } from '../types/policy'

export async function getPolicyCatalogue(): Promise<PolicyDefinition[]> {
  const data = (await apiClient.get<PolicyDefinition[]>('/api/v1/policies')).data
  if (!Array.isArray(data)) throw new Error('Malformed synthetic policy catalogue.')
  return data
}
