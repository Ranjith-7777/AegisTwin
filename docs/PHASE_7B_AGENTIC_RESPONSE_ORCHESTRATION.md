# Phase 7B: Agentic Synthetic Response Orchestration

Phase 7B coordinates Phase 7A recommendations using deterministic, explicitly separated simulation agents. No real action, command, integration, account change, network change, or containment occurs.

## Workflow

```text
Response Recommendation
        ↓
Response Planner Agent
        ↓
Impact Simulation Agent
        ↓
Safety Governor Agent
        ↓
Approval Router Agent
        ↓
Human Decision
        ↓
Synthetic Execution Agent
        ↓
Verification Agent
        ↓
Rollback when required
        ↓
Tamper-Evident Audit Agent
```

The planner retains the explicitly selected ranked recommendation. The impact agent rejects simulations from a different causal sequence. The governor validates synthetic inventory, impact, blast radius, reversibility, and approval tier. The router creates analyst or administrator demonstration gates. The executor writes only persisted synthetic operational state. Verification compares declared and recorded graph mutations. Rollback restores the recorded pre-execution reference for reversible actions.

## States and approval policy

The implemented path uses `planning`, `simulation_validation`, `awaiting_analyst_approval`, `awaiting_administrator_approval`, `approved`, `rejected`, `synthetic_execution_completed`, `synthetic_execution_failed`, `verified`, `rollback_recommended`, and `synthetic_rollback_completed`. Every mutation validates its previous state and emits an audit event. Stale expected-state requests return HTTP 409.

Analyst-tier actions accept analyst or administrator demonstration identities. Administrator-tier actions require the administrator role. Decisions are immutable. Automatic candidates require low impact, single-asset blast radius, reversibility, inventory presence, explicit catalogue eligibility, and a permitting governor decision.

## Execution, verification and rollback

Execution applies only the playbook's declared mutation specification to an execution record. Changed synthetic node and edge identifiers form a live overlay; the base topology remains immutable. Explicit failure modes support deterministic demonstrations without randomness. Verification reports intended mutation application, remaining synthetic paths, affected relationships, disruption, and residual exposure. Rollback is idempotent and available only to reversible playbooks.

## Tamper-evident audit chain

Events use deterministic canonical JSON (`sort_keys`, compact separators, ASCII encoding). The genesis previous hash is 64 zeroes. Each event hash is `SHA-256(previous_event_hash + ":" + canonical_payload)`. Integrity verification recomputes the complete chain and returns the first invalid sequence. Events have no update or delete API.

Tamper-evident means modifications can be detected. It does not prevent database administrators from changing stored data.

## REST contracts

- `POST /api/v1/orchestration/runs/{run_id}/create`
- `GET /api/v1/orchestration`
- `GET /api/v1/orchestration/{id}`
- `GET /api/v1/orchestration/{id}/plan`
- `GET /api/v1/orchestration/{id}/decisions`
- `POST /api/v1/orchestration/{id}/advance`
- `POST /api/v1/orchestration/{id}/approvals/{approval_id}/decide`
- `POST /api/v1/orchestration/{id}/execute`
- `POST /api/v1/orchestration/{id}/verify`
- `POST /api/v1/orchestration/{id}/rollback`
- `GET /api/v1/orchestration/{id}/audit`
- `GET /api/v1/orchestration/{id}/audit/verify`

No WebSocket contract was added; preserving the telemetry playback socket without coupling was preferred.

## Frontend and limitations

Response Centre creates an orchestration from a selected recommendation. Response Operations shows agents, handoffs, approval gates, execution, verification, and rollback. Audit Trail filters and verifies the chain. Digital Twin adds distinct proposed, applied, and restored overlays. Incident Candidates show orchestration state only when one exists.

This is a deterministic hackathon simulation, not a production authentication, SOAR, authorization, distributed locking, or incident-response system. Heuristic ranking values are not probabilities, and successful simulation never implies real containment.
