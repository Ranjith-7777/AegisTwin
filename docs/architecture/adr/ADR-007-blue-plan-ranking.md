# ADR-007: Blue Response Plan Ranking as an Additive What-If Layer, Not a New Scoring Engine

## Status
Accepted — Phase 4.

## Context

Phase 4 required ranking multiple candidate Blue response plans using a
transparent "Response Utility Score" and comparing them via real
Attack Graph / Blast Radius what-if recomputation — while explicitly
forbidding a second, competing scoring system or any duplication of
Phase 3's existing `response_service.py` candidate generation and
`defense_score` computation. Two existing pure-function graph services
(`attack_graph_service.py`, `blast_radius_service.py`) already implement
exactly the deterministic path/reachability algorithms a what-if
comparison needs; the only genuinely missing capability was a way to
evaluate them against a *hypothetical* topology exclusion without
mutating the real, persisted Digital Twin.

## Decision

1. **`blue_planning_service.py` reuses `response_service.analyze()`'s
   already-ranked recommendations as its only candidate source.** It
   never generates a candidate itself; it only re-evaluates the
   existing top-K list with additional evidence.
2. **`AttackGraphService.analyze()` / `BlastRadiusService.estimate()`
   gained three optional, defaulted parameters** —
   `exclude_edge_ids`, `exclude_node_ids`, `publish_event` — rather than
   a parallel "what-if" service. The exclusion filter is applied to the
   in-memory allowed-edge set for that call only; defaults are empty/
   `True`, so every existing caller (Attack Paths tab, Blast Radius tab,
   Purple Team) is provably unaffected (`tests/test_attack_graph.py`,
   `test_blast_radius.py` unchanged and still passing).
3. **The what-if exclusion set is derived from
   `synthetic_execution_agent.mutation()`** — the exact same function
   the real execution path calls — never a separately-maintained
   mapping of playbook → expected edges. This was not a cosmetic choice:
   during implementation, using `mutation()`'s `changed_nodes` (an audit
   marker, not a topology-exclusion claim) for node exclusion produced a
   real false positive (see `BLUE_RESPONSE_PLANNING.md`, "Bug 1"),
   caught and fixed by switching to `changed_edges` only.
4. **The Response Utility Score and Decision Confidence are new,
   separately-named fields** (`ResponseUtilityScoreBreakdown`,
   `DecisionConfidence`), never merged with or renamed from the existing
   `defense_score` — both are computed and returned side by side, and
   the frontend keeps `defense_score` visibly displayed (collapsed) next
   to the new score.

## Alternatives considered

1. **Build a new, independent candidate-generation and scoring engine
   for Phase 4, replacing `response_service.analyze()`.** Rejected: the
   phase spec explicitly required reusing the existing playbook
   infrastructure and treating this as an *additive* enrichment, and a
   second engine would immediately create two sources of truth for "what
   can Blue do here."
2. **Mutate a real, temporary clone of the persisted topology per
   candidate to compute what-if effects, then discard it.** Rejected as
   unnecessarily expensive and risky (a bug in the discard path could
   leak a hypothetical mutation into real state); an in-memory edge-set
   filter achieves the identical algorithmic result with zero persistence
   risk, since `_Graph.build()` already operates over an in-memory edge
   list, not the database directly.
3. **Root the what-if before/after comparison at every anomalous asset
   and take the best result, rather than picking one anchor.** Rejected
   for this phase as more expensive (N traversals instead of 1) for a
   benefit that a simpler fix already captured: ordering anomalous
   assets so a genuine forward pivot (one with an outgoing observed
   edge) is chosen first is sufficient to make the comparison meaningful
   (see `BLUE_RESPONSE_PLANNING.md`, "Bug 2"), without the added cost.

## Consequences

- Positive: a change to `response_service.py`'s ranking or to the
  playbook catalogue automatically flows through to Blue planning with
  no changes needed here — there is nothing in `blue_planning_service.py`
  that could drift out of sync with candidate generation.
- Positive: the what-if exclusion mechanism is generically useful and
  already reused for both Attack Graph and Blast Radius, with the same
  two parameters, rather than two bespoke implementations.
- Negative: `CandidatePlanAssessment` carries counts and scores, not the
  actual before/after path edge lists, so the frontend's what-if
  visualization is textual rather than a graph overlay this phase (see
  `docs/ui/PHASE_4_BLUE_AGENT.md`, "known limitation").

## Future reconsideration trigger

Revisit if a future phase wants a graph-based what-if overlay: that
would require `SecurityGainEvidence` (or a sibling type) to also carry
the actual before/after `AttackPath` objects, not just counts/scores —
a larger response payload that should be justified by real UI demand
before being added.
