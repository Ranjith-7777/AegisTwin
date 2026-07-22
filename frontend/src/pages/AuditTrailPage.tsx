import { useEffect, useState } from 'react'
import { Button } from '../components/ui/button'
import { Card, CardContent, CardHeader } from '../components/ui/card'
import { getAudit, listOrchestrations, verifyAudit } from '../services/orchestrationApi'
import type { AuditEvent, AuditIntegrity, Orchestration } from '../types/orchestration'

export function AuditTrailPage() {
  const [items, setItems] = useState<Orchestration[]>([])
  const [selected, setSelected] = useState('')
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [integrity, setIntegrity] = useState<AuditIntegrity | null>(null)
  const [actor, setActor] = useState('')
  const [eventType, setEventType] = useState('')
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    void listOrchestrations()
      .then((rows) => {
        setItems(rows)
        setSelected(rows[0]?.orchestration_id ?? '')
      })
      .catch(() => {
        setError('Audit trail is unavailable.')
      })
  }, [])
  useEffect(() => {
    if (!selected) return
    void getAudit(selected)
      .then(setEvents)
      .catch(() => {
        setError('Audit events are unavailable.')
      })
  }, [selected])
  const filtered = events.filter(
    (event) =>
      (!actor || event.actor_type === actor) && (!eventType || event.event_type === eventType),
  )
  return (
    <section className="page-stack" aria-labelledby="audit-title">
      <header>
        <p className="eyebrow">Tamper-evident synthetic provenance</p>
        <h1 id="audit-title">Audit Trail</h1>
        <p>
          Tamper-evident means modifications can be detected. It does not prevent database
          administrators from changing stored data.
        </p>
      </header>
      {error ? <p role="alert">{error}</p> : null}
      <Card>
        <CardHeader>
          <h2>Chain controls</h2>
        </CardHeader>
        <CardContent>
          <label>
            Orchestration
            <select
              value={selected}
              onChange={(event) => {
                setEvents([])
                setIntegrity(null)
                setSelected(event.target.value)
              }}
            >
              <option value="">No orchestration</option>
              {items.map((item) => (
                <option key={item.orchestration_id} value={item.orchestration_id}>
                  {item.orchestration_id.slice(0, 8)} · {item.current_state}
                </option>
              ))}
            </select>
          </label>
          <div className="button-row">
            <label>
              Actor filter
              <select
                value={actor}
                onChange={(event) => {
                  setActor(event.target.value)
                }}
              >
                <option value="">All actors</option>
                <option value="human">Human</option>
                <option value="simulation_agent">Simulation agent</option>
              </select>
            </label>
            <label>
              Event filter
              <select
                value={eventType}
                onChange={(event) => {
                  setEventType(event.target.value)
                }}
              >
                <option value="">All events</option>
                {[...new Set(events.map((event) => event.event_type))].map((type) => (
                  <option key={type}>{type}</option>
                ))}
              </select>
            </label>
            <Button
              disabled={!selected}
              onClick={() =>
                void verifyAudit(selected)
                  .then(setIntegrity)
                  .catch(() => {
                    setError('Audit verification failed.')
                  })
              }
            >
              Verify Audit Chain
            </Button>
          </div>
          {integrity ? (
            <p role="status">
              Chain integrity:{' '}
              <strong>
                {integrity.valid
                  ? 'valid'
                  : `invalid at sequence ${String(integrity.first_invalid_sequence)}`}
              </strong>{' '}
              · {integrity.event_count} events · {integrity.algorithm}
            </p>
          ) : null}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <h2>Append-only events</h2>
        </CardHeader>
        <CardContent>
          {filtered.length ? (
            <ol className="audit-events">
              {filtered.map((event) => (
                <li key={event.audit_event_id}>
                  <h3>
                    #{event.sequence_number} {event.event_type.replaceAll('_', ' ')}
                  </h3>
                  <p>
                    {new Date(event.created_at).toLocaleString()} · {event.actor_display_name} (
                    {event.actor_type})
                  </p>
                  <details>
                    <summary>Inspect hashes and canonical payload</summary>
                    <code>Previous: {event.previous_event_hash}</code>
                    <br />
                    <code>Event: {event.event_hash}</code>
                    <pre>{JSON.stringify(event.canonical_payload, null, 2)}</pre>
                  </details>
                </li>
              ))}
            </ol>
          ) : (
            <p>No matching synthetic audit events.</p>
          )}
        </CardContent>
      </Card>
    </section>
  )
}
