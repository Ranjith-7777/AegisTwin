# Blue Response Planning

`app/services/blue_planning_service.py` is a strictly **read-only**
layer that ranks the candidate plans `response_service.analyze()`
already generates (Phase 3's 9-playbook catalogue, unchanged) using real,
recomputed Attack Graph / Blast Radius what-if evidence. It never
invents a new candidate, never duplicates the existing scoring logic in
`response_service.py`, and never mutates the persisted Digital Twin
topology. `orchestration_service.create()` remains the sole entry point
into real (synthetic) execution — this module only helps choose *which*
recommendation to hand it.

## Terminology (read this before reading a number below)

Four scores exist in this system and none of them is a substitute for
another:

| Name | What it measures | Computed by |
|---|---|---|
| Isolation Forest anomaly score | Per-event anomaly likelihood | `detection_service` (Phase 1) |
| `defense_score` | Existing Blue Agent scoring: security improvement − service disruption − resource cost − SLA penalty | `response_service.py` (Phase 3, unchanged) |
| **Response Utility Score** | Ranks *candidate plans* against each other for this incident | `blue_planning_service._utility_score()` (Phase 4, this document) |
| **Decision Confidence** | A deterministic evidence-quality indicator for the *selected* plan | `blue_planning_service._decision_confidence()` (Phase 4) |

Neither of the two new scores is a calibrated probability or an "AI
confidence." `DecisionConfidence.note` says so explicitly and every API
response carries that string verbatim. The frontend keeps `defense_score`
visible (collapsed, per candidate, in Response Plans) specifically so
these four are never visually merged into one number.

## What-if simulation: the technique

`AttackGraphService.analyze()` and `BlastRadiusService.estimate()` both
gained three optional, purely-additive parameters this phase:
`exclude_edge_ids`, `exclude_node_ids`, `publish_event`. Passing a
non-empty exclusion set filters the allowed-edge set *for that call
only* — the persisted topology (`topology_service`) is never touched,
and every pre-Phase-4 caller's behavior is unchanged because the
defaults are empty/`True`. `publish_event=False` is used for every
what-if call so hypothetical planning evaluations never pollute the real
domain-event stream.

For each candidate, `blue_planning_service.compare()`:

1. Calls `synthetic_execution_agent.mutation(record)` — **the exact same
   function the real execution path calls** — and keeps only
   `changed_edges`, discarding `changed_nodes`. This guarantees the
   what-if evaluation and the real execution's effect can never diverge,
   and it is a deliberate fix for a real bug (below).
2. Calls `attack_graph_service.analyze()` and `blast_radius_service.estimate()`
   twice each — once with no exclusion (before) and once with the
   candidate's `changed_edges` excluded (simulated after).
3. Diffs path counts, top-path score, critical-target reachability, and
   blast-radius reachable/critical counts into a `SecurityGainEvidence`.

### Two real bugs found and fixed during implementation

**Bug 1 — an observation-only playbook was credited with a security
effect it never had.** `SyntheticExecutionAgent.mutation()`'s
`changed_nodes` field is an *audit marker* ("this node was touched"),
not a topology-exclusion claim. Early code passed it to
`exclude_node_ids`, so `increase-synthetic-monitoring` (an
`annotate_node` operation with zero real connectivity change) excluded
its entire target node from the what-if graph and scored the *highest*
utility of any candidate — a false positive with real safety
implications (a purely observational action would have looked like the
best containment). Fixed by using only `changed_edges` for exclusion
(see the inline comment at the `compare()` call site); verified the fix
by re-running against a real staged-compromise incident and confirming
`increase-synthetic-monitoring` now shows `security_gain: 0.0`, honestly.

**Bug 2 — every candidate showed zero security gain, including genuine
edge-removing playbooks.** The anchor asset chosen to root the
before/after Attack Graph traversal was "the alphabetically-first
anomalous-observed asset," with no guarantee that asset had any
*outgoing* observed edge. `_enumerate_paths()` walks forward only, so an
anchor that is only ever a destination in this run's telemetry (e.g. an
API gateway that the attacker reached but never pivoted from) produces
zero paths in both the before and after state, masking every
candidate's real effect. Fixed in `_anchor_asset_ids()`: anomalous
assets with a genuine outgoing observed edge are now ordered first, so
`anchors[0]` is a real forward pivot whenever one exists. Verified: for
the same incident, `block-synthetic-route` (removes a specific edge)
now correctly shows `attack_paths: 2 -> 1`, `security_gain: 16.5`, and
is ranked the recommended plan.

Both fixes are covered by regression tests in `tests/test_blue_planning.py`.

## Response Utility Score — exact formula

```
security_gain              = min(40, SecurityGainEvidence.security_gain)
critical_asset_protection  = 20 if a critical target became unreachable,
                              10 if critical-target reachability merely
                              decreased, else 0
blast_radius_reduction     = min(20, max(0, reachable_before - reachable_after) * 2)
evidence_quality           = min(20, recommendation.defense_score * 20)
reversibility_bonus        = 10 if the playbook is reversible, else 0
operational_impact_penalty = {low: 0, medium: 10, high: 25}[playbook.default_operational_impact]

total = clamp(0, 100,
    security_gain + critical_asset_protection + blast_radius_reduction
    + evidence_quality + reversibility_bonus - operational_impact_penalty)
```

`SecurityGainEvidence.security_gain` itself is:

```
max(0, paths_before - paths_after) * 5.0
+ max(0, top_path_score_before - top_path_score_after) * 0.3
+ max(0, critical_targets_before - critical_targets_after) * 10.0
+ max(0, blast_reachable_before - blast_reachable_after) * 2.0
+ max(0, blast_critical_before - blast_critical_after) * 5.0
```

Every term is a plain, reviewable arithmetic function of already-computed
graph/evidence values — nothing here is a trained weight or a
model-guessed number. Weights were chosen so a single confirmed
containment of a critical target (critical_asset_protection = 20)
outweighs a merely-plausible one, and so operational impact can only
ever be a bounded penalty (max 25), never able to zero out a genuinely
high-security-value plan on its own.

## Decision Confidence — exact formula

Reuses `response_service`'s already-computed `component_scores` (no new
queries):

```
anomaly_evidence                 = component_scores['evidence_applicability'] * 25
incident_coherence               = component_scores['correlated_path_interruption'] * 20
technique_diversity              = component_scores['technique_tactic_coverage'] * 20
attack_path_corroboration        = min(15, component_scores['predicted_path_interruption'] * 15)
response_simulation_improvement  = min(20, evidence.security_gain)
total = clamp(0, 100, sum of the above)
```

`note` is always the literal string `"This is a deterministic
evidence-quality score, not a calibrated probability."` — returned in
every `DecisionConfidence` object, not just shown once in the UI.

## Candidate selection

Up to `MAX_CANDIDATES_EVALUATED = 5` of `response_service.analyze()`'s
top-K recommendations are evaluated per call (bounding what-if
recomputation cost — see "Performance" in the Phase 4 completion
report). Candidates are sorted by `(-utility_score.total,
recommendation_id)` for a fully deterministic tie-break. The top-sorted
candidate is marked `recommended=True` **only if it also passed every
applicable policy** (`policy_service.evaluate_response_policies()`,
called once per candidate with the target's real criticality/asset type)
— a policy-failing candidate is never recommended even if it would have
scored highest, and `PlanComparisonResult.recommended_recommendation_id`
is `None` when no candidate passes.

## Persistence

Every `compare()` call upserts a `ResponsePlanAssessmentRecord` keyed by
`(simulation_run_id, model_id, incident_candidate_id,
through_sequence_number)` — the identity is immutable for that tuple, so
a later call with the same identity overwrites rather than duplicates.
`GET /api/v1/blue-planning/assessments/{assessment_id}` reconstructs a
`PlanComparisonResult` from this persisted row alone, never
recomputing — this is what makes a comparison "reconstructable after
reload" per the Phase 4 persistence requirement.
