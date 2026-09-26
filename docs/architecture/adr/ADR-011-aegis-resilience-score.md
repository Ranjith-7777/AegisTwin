# ADR-011: The Aegis Resilience Score — Four Pillars, Locked Weights, Structural Strategy-Neutrality

## Status
Accepted.

## Context

Comparing four defence strategies needed a single headline number, but a
single number that could be gamed by whichever strategy happened to produce
favorable inputs — or worse, a scoring function that could itself branch on
"which strategy produced this" — would make the comparison meaningless.
Phase 5 also needed to handle genuinely inapplicable metrics (e.g.
`no_active_defence` never attempts recovery) without either crashing or
silently defaulting a missing value to something that looks like a real
measurement.

## Decision

`app/services/evaluation/resilience_score_service.py` locks:

```
ARS = 100 * (0.20*A + 0.35*W + 0.25*M + 0.20*R)
```

- **A — Threat Awareness (0.20):** `0.60*DetectionCoverage +
  0.40*DetectionTimeliness`.
- **W — Withstand/Containment (0.35):** `0.40*AttackPathReduction +
  0.30*BlastRadiusReduction + 0.30*CriticalExposureReduction`. Given the
  highest weight because withstand/containment is the most direct evidence
  that a response action actually reduced attacker reach.
- **M — Mission Preservation (0.25):** `0.60*CriticalMissionHealth +
  0.40*(1-OperationalDisruption)` — balances "is the mission healthy" against
  "did the response itself cause collateral damage".
- **R — Verified Recovery (0.20):** `0.60*V + 0.40*RecoveryTimeliness` —
  `V` is a hard confirmed-recovery boolean derived from
  `verification_success`/`rollback_success`, not any softer proxy.

N/A handling is two-level and never conflated: within a pillar, an
inapplicable submetric's weight redistributes across the pillar's remaining
applicable submetric(s); if every submetric in a pillar is inapplicable,
the whole pillar is `None` and only THEN does its weight redistribute
across the remaining applicable pillars at the top level.

`compute_score(metrics: ExperimentMetricRecord, mission_continuity:
MissionContinuitySnapshot) -> ResilienceScoreResult` takes only these two
inputs — neither carries a `defence_mode`/`autonomy_mode`/strategy-
identifying field anywhere in its schema — so it is structurally impossible
for the scoring function to branch on which strategy produced its inputs.

## Alternatives considered

1. **Equal pillar weights (0.25 each).** Rejected: containment
   (Withstand) is the most direct, hardest-to-game evidence of an actual
   defensive effect on the attacker's position, and the PM spec's own
   design intent was to weight it highest; equal weighting would understate
   that a response mode that merely "looks active" (approvals, timing)
   without genuinely reducing attacker reach should not score as well as
   one that does.
2. **Pass `ExperimentRecord`/`defence_mode` into the scoring function and
   trust code review to keep it unused.** Rejected: "written not to branch
   on strategy" is a much weaker guarantee than "cannot possibly branch on
   strategy" — a future edit could add a conditional without anyone
   noticing during review. Keeping the strategy-identifying data entirely
   out of the function's own type signature makes the guarantee structural,
   not just a matter of discipline, and lets it be proven by a signature-
   inspection test
   (`test_signature_has_no_strategy_parameter`) rather than only by
   reading the function body.
3. **Default an inapplicable submetric/pillar to 0.0 (worst case) or skip
   it silently (as if it were never weighted at all).** Rejected: 0.0
   would unfairly punish an experiment for a metric that genuinely could
   not be computed (e.g. `detection_coverage` when a scenario declares zero
   ground-truth steps), and silently reducing total weight without
   renormalizing would produce a score on an inconsistent 0-N scale across
   experiments. The chosen two-level redistribution keeps every score on
   the same true 0-100 scale.

## Consequences

- Positive: `test_identical_metrics_produce_identical_score` and
  `test_signature_has_no_strategy_parameter` in
  `backend/tests/test_resilience_score.py` give a durable, automatically
  re-checked proof of strategy-neutrality — any future change that
  reintroduces a strategy dependency (even indirectly, via a new field on
  either input type) would need to change one of those two types in a way
  the tests would catch.
- Positive: the two-level N/A redistribution means every completed
  experiment gets a real, comparable 0-100 score except in the
  (unreachable in this codebase's fixed topology) case where literally
  every pillar is N/A.
- Negative: because M and R can never be wholly N/A in this codebase's
  actual metric set (`operational_disruption` and `V`/`recovery_timeliness`
  are always applicable), the top-level redistribution path is only ever
  exercised for A and/or W in practice — the "all four pillars renormalize"
  code path is defensive, not something the canonical matrix will actually
  demonstrate.

## Future reconsideration trigger

Revisit the pillar weights (0.20/0.35/0.25/0.20) if the canonical
80-experiment matrix (see `docs/evaluation/RESULTS.md`) shows the score is
insensitive to a pillar that should matter, or oversensitive to one that
shouldn't — that empirical check has not yet happened at the time of
writing, since the matrix has not run.
