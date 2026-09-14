# ADR-012: Mission Continuity Index — Trapezoidal AUC Over Event-Driven Timepoints

## Status
Accepted. See "Addendum" below for a correction found and fixed during a
later Phase 5 research-validity pass — the trapezoidal-AUC formula and the
event-driven point selection described below remain unchanged; what changed
is where the curve stops.

## Context

A single end-of-experiment health snapshot cannot distinguish "the mission
was healthy the whole time" from "the mission collapsed for most of the
run and only recovered right at the end" — both would look identical at
the final timestamp, yet a fast recovery should score meaningfully better
than a slow one. Phase 5 needed a metric that rewards the recovery
trajectory itself, not just the final state, without requiring an
expensive fixed-interval sampling pass over every experiment.

## Decision

`app/services/evaluation/mission_continuity_service.py` computes
`MissionHealth(t)` — a criticality-weighted fraction of mission-relevant
resources that are simultaneously (a) not exposed to confirmed attack reach
and (b) still operationally connected to the topology's entry point, with
no partial credit for a single resource — at a small, fixed set of
**event-driven** timepoints: `baseline`, `attack_observed`, `detection`,
`incident_confirmed`, `response_start`, `containment`, `verification`,
`recovery`. Each corresponds to a real state transition the experiment
actually reached (`_build_points`, `compute_curve`), never a synthetic
clock tick.

```
MCI = trapezoidal_AUC(MissionHealth over logical_time_sim) / experiment_duration
```

`None` (not `0.0`/`1.0`) when duration is 0 — fewer than two distinct time
instants, e.g. every reached stage landed on the same simulated moment.

`CriticalMissionHealth` — the snapshot used by the ARS M-pillar — reuses
the identical resource-health definition, restricted to critical/high-
criticality resources, but evaluated once at the experiment's final state.
It is deliberately a separate function
(`final_critical_mission_health`) from the curve/MCI computation, and is
never substituted for MCI or vice versa.

## Alternatives considered

1. **Fixed-interval sampling (e.g. every N simulated seconds).** Rejected:
   would either be far too coarse to capture a fast recovery cleanly, or
   require an arbitrary interval choice and orders of magnitude more
   `MissionHealthPointRecord`s per experiment than the event-driven
   approach needs, for no additional fidelity — every simulated instant
   where `MissionHealth` could plausibly change IS one of the eight
   named stage transitions, because those are the only points at which
   this codebase's evidence (attack anchors, topology exclusions) actually
   changes. Sampling between them would just repeat the same value.
2. **Reuse `MissionHealth`'s time-integral (MCI) directly as the ARS
   M-pillar input, instead of a separate final-state snapshot.**
   Rejected: MCI answers "how much of the experiment's duration was the
   mission healthy" — a run that dipped badly but fully recovered would
   still score a comparatively low MCI, which correctly penalizes slow
   remediation but would unfairly depress the ARS M-pillar (which is meant
   to answer "is the mission healthy NOW, at the end") for an experiment
   that ultimately succeeded. Keeping them separate lets both true facts
   be reported without either one distorting the other.
3. **Reuse `orchestration_service.py`'s private
   `_bystander_isolated_assets` for the connectivity check.** Rejected: it
   is a private, bound method not part of that service's public surface,
   reusing it would require either an invasive refactor or a cross-module
   private-attribute reach-around this codebase's own style avoids
   elsewhere, and it is also a narrower check than Mission Health needs (it
   only asks "does this asset have any edge left", not "is it still
   transitively reachable from the real entry point"). A second, simple
   BFS (`operationally_connected_asset_ids`) was written instead — not a
   duplicated complex algorithm, just the same edge-arithmetic idea at the
   right level of generality for this use.

## Consequences

- Positive: `MissionHealthPointRecord` storage stays small and directly
  interpretable — a UI can render every point's `stage`/`reason` as a
  human-readable label, not an opaque timestamp.
- Positive: `compute_mci` is a pure function of `(logical_time, health)`
  pairs, independently unit-testable without constructing a full
  experiment (`tests/test_mission_continuity.py`).
- Negative: because points are only recorded at reached stage transitions,
  an experiment that never reaches, say, `containment` (e.g.
  `no_active_defence`) has fewer points and a coarser curve than one that
  reaches every stage — this is honest (there genuinely is less state-
  transition evidence for that experiment), but means curve resolution is
  not uniform across defence modes.

## Future reconsideration trigger

Revisit if a future phase introduces genuinely continuous mission-health
telemetry (rather than discrete before/after what-if evidence at stage
transitions) — at which point a denser, telemetry-driven curve could
supersede the current 8-stage event-driven set without changing the
underlying trapezoidal-AUC formula.

## Addendum (Phase 5 research-validity correction pass): missing the horizon
terminal point made `no_active_defence` incomparable to every active mode

**What was wrong.** `_build_points` originally stopped after the last stage
an experiment actually reached, with no final point extending the curve to
the experiment's real duration. For `no_active_defence` — which only ever
reaches `baseline` and `attack_observed`, both at or near t=0 — this meant
the curve spanned zero or near-zero duration, so `compute_mci`'s
duration-based AUC (`None` when duration ≤ 0) returned `None`/N/A for
essentially every `no_active_defence` experiment, regardless of how long the
attack's damage actually persisted afterward.

**Why it mattered.** MCI's entire purpose (per this ADR's "Context") is to
answer "does defence improve continuity, and how does the trajectory differ
from doing nothing." A metric that is systematically undefined for the "do
nothing" control cannot answer that question — every paired comparison
against `no_active_defence` on `mci` was reporting "N/A" instead of the true,
answerable fact that an undefended system stays degraded for the whole
remaining experiment duration. This silently discarded exactly the
comparison the metric exists to make, for exactly the baseline mode where it
matters most.

**What changed.** `_build_points` now always appends one final
`"experiment_horizon"` point at `logical_timeline_json["experiment_horizon_sim"]`
(the real run duration, computed identically for every defence mode) holding
the last reached stage's mission-health value constant out to that horizon —
mission health does not spontaneously change once the experiment stops
generating events. This lets `compute_mci` honestly integrate a sustained
degraded state that never recovers (exactly the `no_active_defence` case, or
an active mode whose response never lands) instead of seeing a degenerate
near-zero-duration curve. It is skipped only when the horizon is unknown, or
already equals the last real stage's own time (the genuine zero-duration
case, where `None`/N/A remains correct).

**Verification and an honest, non-obvious observed result.** Re-running the
real canonical matrix under this fix, `no_active_defence`'s `mci` is now
`applicable` (non-`None`) in 5/5 canonical seeds for all 4 scenario classes
— previously 0/5 in every class. In 3 of the 4 scenario classes, the defined
value is `0.0` (mission health stayed degraded for the observed run), and in
the fourth it is `0.179487`, identical across `no_active_defence` and every
active mode tested for that class. That last point is itself a real,
unexpected finding worth recording here rather than treated as a bug: for
these scenario/topology combinations, the resource-health definition's
requirement of BOTH "not exposed" AND "still operationally connected"
means a response action that isolates the attacker's ingress edge can
simultaneously cut off legitimate downstream connectivity, so the affected
resource remains scored "unhealthy" for a different reason after
containment than before it. See `docs/evaluation/RESULTS.md`'s corrected-
results section for the full numbers.
