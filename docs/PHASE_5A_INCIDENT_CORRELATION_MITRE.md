# Phase 5A: Auditable Incident Correlation and MITRE Mapping

Phase 5A adds deterministic, evidence-based correlation to AegisTwin's entirely synthetic pipeline. An incident candidate is a cautious grouping of related unusual exercise activity. It is not a confirmed attack or breach, and its correlation score measures evidence coherence rather than attack probability.

## Scenario and benchmark protection

`normal-operations` and `credential-compromise` remain unchanged: six and seven deterministic steps respectively, with the existing evaluation truth intact. `staged-compromise-demo` is an independent twelve-step visual scenario. It provides four routine events over three simulated minutes before repeated failures begin, then a causally related unusual login, unseen device, explicit account manipulation, metadata-qualified remote services, a metadata-qualified synthetic web-service transfer, and a final observation.

## Local catalogue and conservative rules

The versioned `aegistwin-mitre-v1` catalogue contains T1110, T1110.001, T1078, T1098, T1021, T1041 and T1567. It is locally maintained from concise MITRE ATT&CK references dated 2026-07-22 and requires no runtime network access.

- T1110.001 requires at least five failed attempts or an explicit repeated-attempt pattern.
- T1078 requires a successful login causally preceded by failures for the same synthetic user. It does not assert stolen credentials.
- T1098 requires `account_manipulation=true`. A privilege value alone never maps T1068.
- T1021 requires explicit `remote_service` metadata. An internal connection alone is unsupported.
- T1041 requires `channel_type=synthetic_c2`.
- T1567 requires `channel_type=synthetic_web_service` and an identified web service.
- Transfer size without channel evidence receives no unsupported technique ID.

Every observation persists its event/run/model/sequence identity, evidence fields, rationale, tactic, mapper version, heuristic confidence, and `synthetic=true`.

## Causal correlation and fixed weights

Correlation is isolated by run and model. At sequence N, snapshots use only telemetry, assessments and mappings through N. Fixed initial weights are: temporal proximity 0.15, entity continuity 0.20, anomaly evidence 0.20, technique diversity 0.15, tactic progression 0.15 and infrastructure continuity 0.15. These weights are explicit design choices, not learned parameters.

One anomaly cannot create a high-priority candidate. `correlated` requires at least three related evidence items and two techniques. `high_priority` requires at least five evidence items, four techniques, three tactics and sufficient combined coherence. Evidence links are persisted separately, and sequence snapshots make state evolution replayable without future leakage. Analysis is idempotent for run, model and `causal-correlation-v1`; forced analysis replaces only that isolated result.

## REST workflow

```text
POST /api/v1/correlation/runs/{run_id}/analyze
GET  /api/v1/correlation/runs/{run_id}/incidents
GET  /api/v1/correlation/incidents/{candidate_id}
GET  /api/v1/correlation/incidents/{candidate_id}/evidence
GET  /api/v1/correlation/runs/{run_id}/techniques
GET  /api/v1/mitre/techniques
GET  /api/v1/mitre/techniques/{technique_id}
```

The frontend preparation order is run creation, persisted detection scoring, correlation analysis, WebSocket connection, then playback. Failures preserve the run and offer retry or detection-only fallback.

## WebSocket ordering and reconnection

Correlation is optional and requires detection plus a model. For sequence N the order is telemetry event, anomaly assessment, zero or more technique observations, then an optional candidate update. New readiness, warning and error envelopes remain synthetic and typed. Pause, stop and resume gate the entire sequence. `after_sequence=N` skips all earlier event, assessment, mapping and update messages.

## Frontend and limitations

The overview incrementally shows the current candidate, observed-technique timeline, fixed component breakdown and causal evidence trail. Incident Candidates supports run/state selection, candidate details and evidence. MITRE ATT&CK Observations separates catalogue coverage from actual persisted mappings and explicitly identifies unsupported events.

The catalogue is intentionally small, heuristic confidence is not probability, correlation is single-run and deterministic, and there is no prediction, attribution, external intelligence, agents, topology, response recommendation or containment.
