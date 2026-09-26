# Phase 7A: Synthetic Response Recommendation and Impact Simulation

Phase 7A provides decision support against the synthetic digital twin. It does not approve, execute, dispatch, or guarantee any defensive action. There are no operating-system, identity-provider, cloud, firewall, endpoint, networking, SOAR, notification, agent-orchestration, LLM, or RAG integrations.

```text
Causal Synthetic Evidence
         ↓
Applicable Defensive Playbooks
         ↓
Policy and Prerequisite Checks
         ↓
Ranked Response Recommendations
         ↓
Cloned Digital-Twin Simulation
         ↓
Path Interruption and Operational Impact
         ↓
Response Centre
```

## Versioned playbook catalogue

`synthetic-defensive-playbooks-v1` contains eight concise defensive options: increased synthetic monitoring, synthetic session revocation, synthetic account restriction, synthetic endpoint isolation, synthetic route blocking, synthetic application quarantine, metadata-only workload snapshot, and sensitive synthetic database protection. Each declares supported target types, evidence prerequisites, disqualifying conditions, a clone mutation, reversibility, operational impact, blast radius, approval tier, and automatic-candidate eligibility.

The tiers are `automatic_candidate`, `analyst_approval`, `administrator_approval`, and `prohibited`. Phase 7A calculates a tier only. High-impact application and database options require administrator approval; none is automatically approved.

## Causal evidence and ranking

Analysis through sequence N reads only incident evidence, telemetry, assessments, technique observations, topology state, and the latest optional prediction snapshot whose sequence is at most N. It never uses later snapshots, final outcomes, run identifiers, seeds, or scenario identity to select a response.

Positive ranking components are evidence applicability (0.25), correlated-path interruption (0.20), predicted-path interruption (0.15), technique/tactic coverage (0.15), target relevance (0.10), reversibility (0.10), and policy compatibility (0.05). Separate persisted penalties cover operational disruption, blast radius, unsupported prerequisites, critical-service impact, contradictory evidence, unavailable targets, and redundancy. Scores are deterministic relative rankings—not probabilities of success or containment.

## Clone-only impact simulation

The simulator copies the current versioned node/edge sets into local collections, applies the playbook mutation to that copy, and compares the before/after graph. The base topology is never mutated. Persisted factual measures include changed nodes and edges, interrupted correlated and predicted paths, sensitive reachability, affected expected relationships, affected asset/edge counts, and residual route summaries. Interruption, residual exposure, and operational disruption are explicitly heuristic relative measures.

Correlated paths are derived from observed incident evidence. Predicted paths remain hypothetical and are counted separately. Path summaries are bounded to 40 compact entries per snapshot.

## Persistence and idempotency

Migration `20260722_0007` adds `response_playbook_catalogue`, `response_analyses`, `response_recommendations`, and `response_impact_simulations`. Synthetic flags are required. Analysis uniqueness is run + model + incident candidate + sequence + engine version; recommendation uniqueness adds playbook and target. Repeated analysis returns the existing deterministic result. Forced analysis deletes and recreates the single analysis tree in one transaction.

## REST workflow

```text
GET  /api/v1/response/playbooks
GET  /api/v1/response/playbooks/{playbook_id}
POST /api/v1/response/runs/{run_id}/analyze
GET  /api/v1/response/runs/{run_id}/recommendations
GET  /api/v1/response/recommendations/{recommendation_id}
GET  /api/v1/response/recommendations/{recommendation_id}/simulation
GET  /api/v1/response/runs/{run_id}/summary
```

The analysis request selects model, optional sequence, optional prediction evidence, result limit, and forced reanalysis. Detection assessments and correlation are mandatory prerequisites. Structured application errors explain missing prerequisites.

## Frontend state flow

The Response Centre loads runs, models, and the local catalogue, then clears recommendations whenever run, model, sequence, or prediction selection changes. Runtime parsing rejects malformed synthetic payloads. Recommendation cards are keyboard buttons and show rank, target, relative score, approval tier, reversibility, blast radius, evidence, rationale, penalties, warnings, and impact measures. Errors receive focus; warnings use a live status region; comparison results include a textual summary.

Incident Candidates can show the highest current response summary. Predictive Analytics displays response context separately from prediction evidence. The Digital Twin may render changed nodes and edges as a distinct `simulated response impact` overlay that never modifies playback and clears when its selection changes.

## Current limitations and safety guarantees

- Phase 7A executes nothing and records no approval decision.
- Topology mutations exist only inside transient graph clones; persisted results are summaries.
- Identity/session playbooks annotate synthetic state and do not call an identity provider.
- Relative graph measures cannot establish containment, business safety, or real-world effectiveness.
- Catalogue applicability is deterministic and deliberately conservative.
- Actual synthetic approvals and execution workflows are deferred to Phase 7B.
