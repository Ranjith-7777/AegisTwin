import { apiClient } from './apiClient'
import type { AuditEvent, AuditIntegrity, Orchestration } from '../types/orchestration'

function valid(value: unknown): Orchestration {
  if (
    !value ||
    typeof value !== 'object' ||
    !('orchestration_id' in value) ||
    !('synthetic' in value)
  )
    throw new Error('Malformed synthetic orchestration response.')
  return value as Orchestration
}
export async function listOrchestrations() {
  const data = (await apiClient.get<{ items: Orchestration[] }>('/api/v1/orchestration')).data
  if (!Array.isArray(data.items)) throw new Error('Malformed synthetic orchestration response.')
  return data.items.map(valid)
}
export async function getOrchestration(oid: string) {
  return valid((await apiClient.get(`/api/v1/orchestration/${oid}`)).data)
}
export async function createOrchestration(
  runId: string,
  body: {
    model_id: string
    incident_candidate_id: string
    selected_recommendation_id: string
    through_sequence_number: number
  },
) {
  return valid(
    (await apiClient.post(`/api/v1/orchestration/runs/${encodeURIComponent(runId)}/create`, body))
      .data,
  )
}
export async function decideApproval(
  oid: string,
  aid: string,
  body: { actor_role: string; actor_display_name: string; decision: string; reason: string },
) {
  return valid(
    (await apiClient.post(`/api/v1/orchestration/${oid}/approvals/${aid}/decide`, body)).data,
  )
}
export async function executeSynthetic(oid: string) {
  return valid((await apiClient.post(`/api/v1/orchestration/${oid}/execute`, {})).data)
}
export async function verifySynthetic(oid: string) {
  return valid((await apiClient.post(`/api/v1/orchestration/${oid}/verify`)).data)
}
export async function rollbackSynthetic(oid: string, reason: string) {
  return valid(
    (
      await apiClient.post(`/api/v1/orchestration/${oid}/rollback`, {
        reason,
        requested_by: 'Demo SOC Analyst',
      })
    ).data,
  )
}
export async function getAudit(oid: string) {
  const data = (await apiClient.get<AuditEvent[]>(`/api/v1/orchestration/${oid}/audit`)).data
  if (!Array.isArray(data)) throw new Error('Malformed audit response.')
  return data
}
export async function verifyAudit(oid: string) {
  return (await apiClient.get<AuditIntegrity>(`/api/v1/orchestration/${oid}/audit/verify`)).data
}
