# ADR-005: Additive, Component-Transparent Attack Path Scoring

## Status
Accepted — Phase 3.

## Context

Ranking multiple candidate attack paths requires a single priority
number, but Phase 3 explicitly required every claimed score to be
"traceable to real graph data and real evidence" — an opaque ML-derived
or randomly-perturbed score would fail that bar even if it produced
plausible-looking rankings, because a reviewer could not verify it.

## Decision

Score each path as five independently-named, independently-reported
contributions summed together and clamped to `[0, 100]`: exposure,
privilege, critical-target, boundary-crossing, and evidence, minus a
length penalty (see `docs/architecture/ATTACK_GRAPH.md` for the exact
formula). Every contribution is a deterministic function of data already
computed earlier in the same request (graph zone/criticality/sensitivity
fields, `trust_level`, and — for `observed`/`inferred`/`predicted` paths
— the sequence-bounded evidence set), and `AttackPathScore` exposes each
contribution as its own field alongside the total, not just the sum.

## Alternatives considered

1. **A trained ML ranking model.** Rejected: there is no labeled
   "ground truth priority" dataset for synthetic attack paths to train
   against, and a learned model's score cannot be verified by a reviewer
   from the returned fields alone — it would be exactly the kind of
   unexplainable "intelligence" the phase instructions forbade.
2. **A single opaque heuristic score with no component breakdown.**
   Rejected: even a fully deterministic formula is not *explainable* to
   a reviewer if only the final number is returned. Reporting each of
   the five contributions separately lets anyone recompute the total by
   hand from the same `AttackPath` payload, which is the actual bar this
   phase needed to clear.
3. **Multiplicative combination of factors (e.g. exposure × privilege ×
   criticality) instead of additive.** Rejected: multiplicative scoring
   makes a `0.0` in any single factor (e.g. no privilege escalation on
   an otherwise very dangerous path) collapse the entire score to zero,
   which does not match how a human analyst would prioritize a
   long, high-value, non-privileged path to a critical database. Additive
   scoring with per-factor caps avoids this while still bounding the
   total to a sane 0-100 range.
4. **Score paths using the existing prediction/response engines'
   confidence machinery.** Rejected: those engines answer a different
   question (what happens next in a specific run, and what should Blue
   do about it) and are causal/sequence-bounded by design; attack-path
   scoring needs to work even for `potential` paths where no run exists
   at all. Reusing them would have coupled two independent concerns for
   no benefit.

## Consequences

- Positive: fully reviewable — `docs/architecture/ATTACK_GRAPH.md`'s
  scoring table is the complete specification; there is no hidden
  constant or model weight anywhere else.
- Positive: sorting is a pure function of already-returned data
  (`(-score.total, hop_count, path_id)`), so results are byte-identical
  across repeated identical requests — verified by
  `tests/test_attack_graph.py::test_potential_paths_are_deterministic_and_ranked`.
- Negative: the weights (25/20/30/20/30/length-penalty-3-per-hop) are
  hand-chosen, not empirically calibrated against real incident data —
  appropriate for a synthetic, explainability-first demo, not a claim
  of production-calibrated risk scoring.

## Future reconsideration trigger

Revisit if a future phase introduces a real (non-synthetic) incident
outcome dataset that could calibrate these weights, or if stakeholders
need to tune the relative importance of the five factors per deployment
— at which point the weights should become configuration, not hardcoded
constants.
