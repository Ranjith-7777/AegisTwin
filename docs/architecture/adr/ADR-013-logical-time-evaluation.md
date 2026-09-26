# ADR-013: Logical (Simulation) Time Tracked Separately From Wall-Clock Latency

## Status
Accepted.

## Context

An experiment has two entirely different notions of "time": where an event
falls in the simulated attack/response timeline (useful for asking "how
long, in-story, did detection take"), and how long the real Python process
actually took to compute a decision (useful for asking "is this pipeline
fast enough to run interactively"). Phase 4's response/verification/
rollback machinery has no simulated clock of its own — executing,
verifying, and rolling back a synthetic mutation is modelled as
instantaneous relative to the simulated attack timeline; only real
`datetime.now(UTC)` audit timestamps exist for those stages. Conflating the
two — for example, measuring "time to containment" using wall-clock audit
timestamps — would produce numbers dominated by incidental Python
scheduling/database latency rather than anything about the scenario or
defence strategy being evaluated.

## Decision

`app/services/evaluation/metrics_service.py` establishes the convention,
reused unchanged by `mission_continuity_service.py` and
`timeline_service.py`:

> Every Blue-side event (response start, containment, verification,
> recovery) shares the SAME simulated instant — the timestamp of the
> telemetry event at the orchestration's `through_sequence_number`. They
> differ only in *whether* they were reached at all ... never in *when*.

Concretely: `logical_timeline_json`'s fields
(`attack_start_time_sim`, `first_detection_time_sim`,
`incident_confirmed_time_sim`, `response_start_time_sim`,
`containment_time_sim`, `verification_time_sim`, `recovery_time_sim`,
`experiment_horizon_sim`) are all derived from
`TelemetryEventRecord.timestamp` via `_event_time_at_sequence` — a single
honest function that turns a 1-indexed `through_sequence_number` into a
real simulated instant, using the exact same ordering
(`order_by(timestamp, event_id)`) every `through_sequence_number` in this
codebase already assumes.

Real wall-clock computation cost lives in a completely separate
`computation_latency_json` blob (`workflow_latency_ms`,
`evaluation_what_if_latency_ms`, both from `time.perf_counter()`
measurements), and is never used to compute a `time_to_*` metric.
`timeline_service.py`'s `TimelineEvent` schema carries both
`logical_time_sim` and `wall_clock_time` as independently-nullable fields
for the same reason — a stage's reconstructed timeline event exposes both
notions of time side by side rather than merging them, and `wall_clock_time`
is deliberately left `None` for stages whose only persisted timestamp
column is actually a synthetic-timeline value rather than a genuine audit
stamp (`SimulationRunRecord.created_at`, `TelemetryEventRecord.created_at`
— confirmed by reading `simulation_service.py`/`event_generator.py`'s own
write sites, not assumed).

## Alternatives considered

1. **Model Blue-side stages (containment, verification, recovery) as
   occurring at distinct, separately-computed simulated instants.**
   Rejected: this codebase's Phase 4 machinery genuinely has no simulated
   clock of its own for these stages — inventing distinct simulated
   timestamps for them would fabricate precision the underlying data does
   not support. The honest choice, once this was confirmed by reading
   `orchestration_service.py`/`orchestration_agents.py` end to end, is to
   say they share one instant and differ only in whether they were
   reached.
2. **Use wall-clock timestamps for `time_to_containment`/
   `time_to_verified_recovery` instead of simulated time.** Rejected: wall-
   clock duration between, say, orchestration creation and verification
   completion measures database/Python scheduling overhead, which varies
   with machine load and has nothing to do with the scenario or defence
   strategy under evaluation — exactly the confound this ADR exists to
   avoid.
3. **Instrument per-agent wall-clock latency (`planning_latency_ms`,
   `what_if_latency_ms`) immediately in Stage 2.** Rejected as out of scope
   for the stage that introduced this convention: doing so would require
   invasive changes to `strategies.py`'s call sites that the Stage 2 brief
   explicitly said to avoid. Both fields are left `None` deliberately
   rather than filled with an approximate/misleading value.

## Consequences

- Positive: `time_to_first_detection`, `time_to_containment`,
  `time_to_verified_recovery`, etc. are directly comparable across defence
  modes and across machines/runs — they depend only on the deterministic
  scenario replay and detection scoring, never on incidental compute
  speed.
- Positive: `timeline_service.py` could reuse
  `metrics_service.py`'s exact `_event_time_at_sequence`/
  `_first_detection_time` helpers rather than reimplementing the
  convention, guaranteeing the two stages can never silently drift apart.
- Negative: computation-latency granularity is coarse (one measurement for
  the whole strategy dispatch, not per-agent) — a reader wanting to know
  specifically how much of `workflow_latency_ms` was spent in Digital Twin
  what-if comparison versus policy evaluation versus execution cannot get
  that breakdown from this stage's data alone.

## Future reconsideration trigger

Revisit if a future phase adds genuine per-agent wall-clock instrumentation
(filling in `planning_latency_ms`/`what_if_latency_ms`) — at which point
this ADR's "coarse latency" consequence would be resolved without changing
the logical-time convention itself.
