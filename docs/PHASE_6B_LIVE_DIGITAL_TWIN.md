# Phase 6B: Sequence-Driven Live Digital Twin

Phase 6B turns the Phase 6A topology into a causal playback view. It remains a visualization of persisted, synthetic exercise evidence: it does not discover infrastructure, inspect a host, scan a network, execute a command, contain anything, or claim that compromise is confirmed.

## State architecture

`liveTopologyReducer` is the single state transition boundary. The provider translates ordered playback envelopes into reducer actions; React Flow only renders the resulting overlay. Static topology identifiers form an allowlist, so an unknown event identifier never creates an arbitrary node. A relationship between two known assets that is absent from the static graph is represented as an explicitly unexpected observed edge.

The overlay vocabulary is deliberately evidence-scoped:

- **Observed** means a persisted telemetry event has reached the asset or relationship.
- **Anomalous observed** means the matching persisted assessment classified that event as anomalous.
- **Correlated** means persisted evidence has entered the current incident-candidate snapshot.
- **Predicted** means the current model snapshot ranks a hypothetical next asset; it is visually separate from observed evidence.
- **Current focus** is the latest delivered event and is transient.

The reducer records first/latest sequence numbers, event identifiers, assessment details and observed technique identifiers for inspectors and history. Precedence is current focus, anomalous observed, correlated, predicted, then observed. Animations pause with playback and are disabled by the reduced-motion control or operating-system preference.

## Ordering and recovery

Telemetry sequence numbers are the causal clock. Duplicate or out-of-order telemetry is ignored, and assessment or technique messages only update the path already associated with their matching event. Correlation and prediction messages replace their model-dependent snapshot layers rather than accumulating stale hypotheses. Starting or replaying another run clears the previous overlay.

On reconnect, the client first clears transient focus and requests:

```text
GET /api/v1/topology/runs/{run_id}/state?through_sequence={last_rendered_sequence}&model_id={model_id}
```

The server reconstructs state only through that exact persisted prefix and returns `event_mappings` plus observed, anomalous, correlated and predicted identifiers. The client replays those mappings from sequence zero, applies the authoritative aggregate layers, and then reconnects the WebSocket with the same sequence offset. If recovery fails, the socket can still resume from the offset, but no future evidence is inferred or fabricated.

## Backend contract

The existing Phase 6A endpoint remains backward-compatible. Phase 6B adds `state_version`, anomalous/unexpected observed identifiers, causal event mappings, and explicitly hypothetical predicted paths. The static topology endpoint accepts the existing optional synthetic-sink flag used by active playback. No database migration is required because all recovery data is derived from persisted telemetry, assessments, technique observations, candidate evidence and prediction snapshots.

## UI and accessibility

The full Digital Twin provides live/static status, run/model/sequence context, follow-live and reduced-animation controls, reset, keyboard-operable event history, and evidence-rich asset/relationship inspectors. The Overview card uses the same reducer state. Routes for the heavier Digital Twin and analytics pages are lazy-loaded behind an accessible loading status.

## Validation workflow

Use `staged-compromise-demo` with detection, correlation and prediction enabled. Train or select a compatible synthetic model, start playback, and verify that node/edge focus follows sequence order; anomaly and technique evidence attaches only to its event; candidate and prediction layers remain qualified; pause freezes motion and messages; resume continues; reset clears the overlay; and reconnect restores the exact prefix before continuing.

## Known limitations

- The topology is curated synthetic infrastructure, not live discovery.
- Recovery is an on-demand derived projection rather than a persisted materialized view.
- Follow-live keeps the latest evidence selected; the graph does not perform disruptive automatic camera movement.
- Predictions are ranked exercise hypotheses and may be absent when there is insufficient evidence.
- The frontend bounds rendered telemetry separately; topology history follows the current playback session/recovery prefix.
