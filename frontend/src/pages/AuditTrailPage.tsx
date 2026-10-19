import { Info, Link2, Link2Off, ShieldCheck, ShieldX } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { Badge } from '../components/ui/badge'
import { Button } from '../components/ui/button'
import { KeyValue, Panel } from '../components/ui/panel'
import { cn } from '../lib/utils'
import { getAudit, listOrchestrations, verifyAudit } from '../services/orchestrationApi'
import type { AuditEvent, AuditIntegrity, Orchestration } from '../types/orchestration'

function short(hash: string) {
  return hash.length > 14 ? `${hash.slice(0, 8)}…${hash.slice(-4)}` : hash
}

function payloadText(event: AuditEvent, key: string): string | null {
  const value = event.canonical_payload[key]
  return typeof value === 'string' || typeof value === 'number' ? String(value) : null
}

/** What the event acted on, from its canonical payload. */
function objectOf(event: AuditEvent): string {
  return (
    payloadText(event, 'rollback_id') ??
    payloadText(event, 'execution_id') ??
    payloadText(event, 'approval_request_id') ??
    payloadText(event, 'agent_name') ??
    'orchestration'
  )
}

/** The outcome the event recorded, from its canonical payload. */
function resultOf(event: AuditEvent): string {
  return (
    payloadText(event, 'to_state') ??
    payloadText(event, 'decision') ??
    payloadText(event, 'verification_status') ??
    payloadText(event, 'state') ??
    '—'
  )
}

/**
 * Tamper-evident audit chain for one orchestration. Each event stores the
 * hash of the previous event, and its own hash covers that link plus its
 * canonical payload - so editing any stored event breaks verification from
 * that point onward.
 */
export function AuditTrailPage() {
  const requested =
    typeof window === 'undefined'
      ? ''
      : (new URLSearchParams(window.location.search).get('orchestration') ?? '')
  const [items, setItems] = useState<Orchestration[]>([])
  const [selected, setSelected] = useState('')
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [integrity, setIntegrity] = useState<AuditIntegrity | null>(null)
  const [actor, setActor] = useState('')
  const [eventType, setEventType] = useState('')
  const [inspected, setInspected] = useState<string | null>(null)
  const [verifying, setVerifying] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    void listOrchestrations()
      .then((rows) => {
        setItems(rows)
        const match = rows.find((row) => row.orchestration_id === requested)
        setSelected(match?.orchestration_id ?? rows[0]?.orchestration_id ?? '')
      })
      .catch(() => {
        setError('Audit trail is unavailable.')
      })
  }, [requested])

  useEffect(() => {
    if (!selected) return
    void getAudit(selected)
      .then(setEvents)
      .catch(() => {
        setError('Audit events are unavailable.')
      })
  }, [selected])

  // Client-side link check: does each event point at its predecessor's hash?
  // (Full re-hashing of payloads is done server-side by "Verify".)
  const linked = useMemo(() => {
    const ordered = [...events].sort((left, right) => left.sequence_number - right.sequence_number)
    const result = new Map<string, boolean>()
    ordered.forEach((event, index) => {
      const previous = ordered[index - 1]
      result.set(
        event.audit_event_id,
        previous ? event.previous_event_hash === previous.event_hash : true,
      )
    })
    return result
  }, [events])

  const filtered = events.filter(
    (event) =>
      (!actor || event.actor_type === actor) && (!eventType || event.event_type === eventType),
  )
  const detail = events.find((event) => event.audit_event_id === inspected) ?? null

  function verify() {
    setVerifying(true)
    void verifyAudit(selected)
      .then(setIntegrity)
      .catch(() => {
        setError('Audit verification failed.')
      })
      .finally(() => {
        setVerifying(false)
      })
  }

  return (
    <section className="page-stack" aria-labelledby="audit-title">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Analysis · tamper-evident synthetic provenance</p>
          <h1 id="audit-title">Audit Trail</h1>
          <p>
            Every agent decision, human approval, execution, verification and rollback is appended
            to a SHA-256 hash chain.
          </p>
        </div>
        <Button size="lg" disabled={!selected || verifying} onClick={verify}>
          <ShieldCheck /> {verifying ? 'Verifying…' : 'Verify Audit Chain'}
        </Button>
      </header>
      {error ? (
        <p role="alert" className="error-state">
          {error}
        </p>
      ) : null}
      {integrity ? (
        <div
          role="status"
          className={cn('notice', !integrity.valid && 'is-warn')}
          aria-label="Chain integrity"
        >
          {integrity.valid ? (
            <ShieldCheck className="size-4 text-[var(--ok)]" />
          ) : (
            <ShieldX className="size-4" />
          )}
          <span>
            Chain integrity:{' '}
            <strong className={integrity.valid ? 'chain-valid' : 'chain-broken'}>
              {integrity.valid
                ? 'valid'
                : `invalid at sequence ${String(integrity.first_invalid_sequence)}`}
            </strong>{' '}
            · {integrity.event_count} events re-hashed server-side · {integrity.algorithm}
          </span>
        </div>
      ) : null}

      <div className="split-main">
        <Panel title="Append-only events" flush>
          <div className="flex flex-wrap items-end gap-3 border-b border-[var(--border)] p-3">
            <label className="field min-w-[14rem]">
              <span>Orchestration</span>
              <select
                value={selected}
                onChange={(event) => {
                  setEvents([])
                  setIntegrity(null)
                  setInspected(null)
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
            <label className="field">
              <span>Actor filter</span>
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
            <label className="field">
              <span>Event filter</span>
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
          </div>
          {filtered.length ? (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Time</th>
                    <th>Actor</th>
                    <th>Action</th>
                    <th>Object</th>
                    <th>Result</th>
                    <th>Previous hash</th>
                    <th>Hash</th>
                    <th>Link</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((event) => {
                    const ok = linked.get(event.audit_event_id) ?? true
                    return (
                      <tr
                        key={event.audit_event_id}
                        className={cn(
                          'cursor-pointer',
                          inspected === event.audit_event_id && 'is-selected',
                        )}
                        onClick={() => {
                          setInspected(event.audit_event_id)
                        }}
                      >
                        <td className="mono">{event.sequence_number}</td>
                        <td className="whitespace-nowrap">
                          {new Date(event.created_at).toLocaleTimeString()}
                        </td>
                        <td className="is-primary">
                          {event.actor_display_name}
                          <span className="block">
                            <Badge tone={event.actor_type === 'human' ? 'warn' : 'accent'}>
                              {event.actor_type.replaceAll('_', ' ')}
                            </Badge>
                          </span>
                        </td>
                        <td>
                          #{event.sequence_number} {event.event_type.replaceAll('_', ' ')}
                        </td>
                        <td className="mono text-[0.72rem]">{objectOf(event)}</td>
                        <td>{resultOf(event).replaceAll('_', ' ')}</td>
                        <td className="hash">{short(event.previous_event_hash)}</td>
                        <td className="hash">{short(event.event_hash)}</td>
                        <td>
                          {ok ? (
                            <Link2
                              className="size-4 chain-valid"
                              aria-label="Linked to previous event"
                            />
                          ) : (
                            <Link2Off className="size-4 chain-broken" aria-label="Link broken" />
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="m-0 p-4 text-[0.8rem] text-[var(--text-faint)]">
              No matching synthetic audit events.
            </p>
          )}
        </Panel>
        <div className="grid content-start gap-3">
          <Panel title="How the hash chain works" icon={<Info className="size-4" />}>
            <ol className="m-0 grid gap-1.5 pl-4 text-[0.78rem] leading-relaxed text-[var(--text-dim)]">
              <li>Each event is serialised to canonical JSON.</li>
              <li>
                Its hash is <span className="mono">SHA-256(previous_hash : payload)</span>; the
                first event links to a fixed genesis hash.
              </li>
              <li>
                Changing any stored event changes its hash, so every later link stops matching and
                verification reports the first invalid sequence.
              </li>
            </ol>
            <p className="m-0 mt-2 text-[0.74rem] text-[var(--warn-text)]">
              Tamper-evident means modifications can be detected. It does not prevent database
              administrators from changing stored data.
            </p>
          </Panel>
          <Panel title="Event detail">
            {detail ? (
              <div className="grid gap-2">
                <KeyValue
                  rows={[
                    ['Sequence', String(detail.sequence_number)],
                    ['Event', detail.event_type.replaceAll('_', ' ')],
                    ['Actor', `${detail.actor_display_name} (${detail.actor_id})`],
                    ['Recorded', new Date(detail.created_at).toLocaleString()],
                  ]}
                />
                <p className="hash m-0 break-all">previous: {detail.previous_event_hash}</p>
                <p className="hash m-0 break-all">hash: {detail.event_hash}</p>
                <pre className="inset m-0 max-h-56 overflow-auto text-[0.7rem]">
                  {JSON.stringify(detail.canonical_payload, null, 2)}
                </pre>
              </div>
            ) : (
              <p className="m-0 text-[0.78rem] text-[var(--text-faint)]">
                Select an event to inspect its hashes and canonical payload.
              </p>
            )}
          </Panel>
        </div>
      </div>
    </section>
  )
}
