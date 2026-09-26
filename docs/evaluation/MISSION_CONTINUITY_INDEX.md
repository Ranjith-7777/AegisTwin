# Mission Continuity Index (MCI)

`app/services/evaluation/mission_continuity_service.py`
(`MCI_VERSION = "aegis-mci-v1"`).

## What "healthy" means (verbatim from the module docstring)

> A resource is healthy (health = 1.0) at time t if and only if it is BOTH
> (a) not currently exposed to confirmed/admissible attack reach — it is
> neither itself a compromised anchor nor forward-reachable from one via the
> same Attack Graph/Blast Radius evidence this codebase already uses for
> Blue's own what-if evaluations — AND (b) still operationally connected —
> reachable, via the topology's real edges (minus whatever a response action
> has actually removed at that point), from the topology's designated
> external entry point. A resource that fails either test is unhealthy
> (health = 0.0); there is no partial credit for a single resource.
> `MissionHealth(t)` is then the criticality-weighted fraction of
> mission-relevant resources that are healthy at t.

Every `topology_service.nodes(include_sink=False)` node counts as
mission-relevant, regardless of criticality — a `"low"`-criticality resource
still counts, just with less weight. Weights:
`critical=4.0, high=3.0, medium=2.0, low=1.0` (`CRITICALITY_WEIGHTS`).

"Exposed to confirmed/admissible attack reach" reuses the codebase's one
existing before/after evidence primitive end-to-end —
`what_if_evidence_service.anchor_asset_ids` and `blast_radius_service
.estimate` — never a second, parallel implementation. When there is no real
evidence yet (`has_evidence=False`), nothing is considered exposed — a
non-evidence fallback anchor is never treated as a real compromise.

"Operationally connected" is a plain forward BFS from `ENTRY_ASSET_ID =
"external-user-01"` (the topology's one node with no incoming edge) over
`topology_service.edges(...)`, minus whatever a response action excluded at
that point (`operationally_connected_asset_ids`).

## Resilience curve

`compute_curve` persists one `MissionHealthPointRecord` per meaningful state
transition an experiment actually reached — `baseline`, `attack_observed`,
`detection`, `incident_confirmed`, `response_start`, `containment`,
`verification`, `recovery` — never thousands of uniform samples. Each point
is evaluated at the real sequence number for that event, with the real
exclude-node/edge sets active at that point (empty before containment, the
experiment's real `changed_node_ids`/`changed_edge_ids` from containment
onward, or reverted to empty again if a rollback succeeded). Adjacent points
with identical `(time, health)` are deduplicated. The method is idempotent:
re-running it for the same `experiment_id` replaces the prior points
outright.

For `rule_based`/`ml_assisted` specifically, `verification`/`recovery` are
never reached (those baselines never run Phase 4's Verification/Rollback
machinery — see `strategies.py`), and their `response_start`/`containment`
timing/exclude-sets are derived from `EvaluationSyntheticActionRecord
.through_sequence_number`/`changed_node_ids_json`/`changed_edge_ids_json`
rather than a `ResponseOrchestrationRecord`, via
`_orchestration_sequence`'s `evaluation_action_id` branch.

### Terminal `"experiment_horizon"` point (correction pass)

After all reached-stage points, `compute_curve` **always appends one final
point** at `logical_timeline_json["experiment_horizon_sim"]` (the
experiment's real run duration — last telemetry event minus the first,
computed identically for every defence mode, including
`no_active_defence`), holding the *last real stage's* `mission_health` value
constant out to that horizon:

```
sequence = <next after the last real stage point>
logical_time_sim = experiment_horizon_sim
mission_health = <same value as the last real stage>
stage = "experiment_horizon"
reason = "Experiment horizon reached; mission health at this point reflects
          the final persisted state."
```

Mission health does not spontaneously change once the experiment stops
generating events, so this point is never recomputed with a different
exclude-set — it is exactly the last real stage's own value, just extended
in time. It is skipped when the horizon is unknown, or when it already
equals the last real stage's own time (no-op — including the true
zero-duration case, a single telemetry event, where nothing is added and
`compute_mci` correctly stays `None`; see `test_mission_continuity.py::
test_zero_duration_single_point_returns_none`). Adjacent-point deduplication
still applies, so this never produces a meaningless duplicate sample.

**Why this exists.** Before this fix, `compute_curve` only emitted a point
per reached stage. Two consequences were wrong:

1. `no_active_defence` only ever reaches `baseline`/`attack_observed`, both
   at/near `t=0`, so the curve had ~zero duration and `compute_mci`
   returned `None` — even though the experiment's real horizon is
   `experiment_horizon_sim` (> 0 for any real multi-event run) and mission
   health stayed at whatever it degraded to for the entire remaining
   duration. That sustained degraded interval was silently dropped instead
   of being integrated into MCI.
2. Even when a mode recovers *before* the horizon, the interval between
   recovery and the horizon was never integrated — so a fast recovery
   followed by a long healthy remainder could score no differently from a
   fast recovery immediately followed by the experiment ending, and could
   look no better than never recovering at all.

The terminal point fixes both: a never-recovering run now gets an honest,
non-`None` MCI that integrates its real sustained-degraded duration, and a
recovering run gets real credit for the healthy time between recovery and
the horizon — proven end to end (real `experiment_service.create_and_run` +
`evaluate_experiment` runs, real persisted `MissionHealthPointRecord`s, real
`ExperimentMetricRecord.mci`) in `tests/test_mission_continuity_horizon.py`.

## MCI formula

```
MCI = trapezoidal_AUC(MissionHealth over logical_time_sim) / experiment_duration
```

Ideal health is always 1.0, so no separate "ideal AUC" term is needed.
`None` when duration is 0 (a single point, or every point at the same
instant) — never a divide-by-zero, never defaulted to 0.0/1.0.

```python
# mission_continuity_service.py::compute_mci
ordered = sorted(points, key=lambda p: p.logical_time_sim)
duration = ordered[-1].logical_time_sim - ordered[0].logical_time_sim
auc = sum((left.mission_health + right.mission_health) / 2.0 * (right.t - left.t)
          for left, right in pairwise(ordered))
return auc / duration
```

## Worked example (real, from `tests/test_mission_continuity.py::
test_partial_degradation_matches_hand_computed_trapezoidal_auc`)

Points: `(t=0, h=1.0) → (t=10, h=1.0) → (t=10, h=0.0) → (t=30, h=0.0) →
(t=30, h=1.0) → (t=40, h=1.0)`.

```
Trapezoidal AUC = 10*(1.0+1.0)/2 + 0*(1.0+0.0)/2 + 20*(0.0+0.0)/2
                + 0*(0.0+1.0)/2 + 10*(1.0+1.0)/2
                = 10 + 0 + 0 + 0 + 10 = 20
Duration = 40 - 0 = 40
MCI = 20 / 40 = 0.5
```

Additional real, asserted properties from the same test file:

- All-healthy throughout → `MCI = 1.0`
  (`test_perfect_health_entire_experiment_gives_mci_1`).
- All-unhealthy throughout → `MCI = 0.0`
  (`test_zero_health_entire_experiment_gives_mci_0`).
- Same start/end health but a mid-experiment dip scores strictly lower than
  a curve that stayed healthy throughout, even though both begin and end at
  `h=1.0` (`test_identical_final_state_different_mci_depending_on_path`) —
  MCI rewards time spent healthy, not just the final state.
- Recovering faster after an identical dip scores strictly higher
  (`test_faster_recovery_gives_higher_mci_than_slower_recovery`).

## Zero-duration N/A case

`compute_mci` returns `None` for fewer than two distinct time instants
(`test_zero_duration_single_point_returns_none`,
`test_zero_duration_all_points_same_instant_returns_none`). This is a
genuine, honest "undefined", not a fabricated `0.0` — but it is now reserved
for the true zero-duration case (a single telemetry event, so
`attack_start_time_sim == experiment_horizon_sim`), not for
`no_active_defence` runs in general. With the terminal `"experiment_horizon"`
point (see above), a `no_active_defence` run with a real multi-event
scenario now gets a defined MCI (`test_mission_continuity_horizon.py::
test_no_active_defence_has_defined_mci_when_horizon_positive`) — the
`mci: None` observed for such runs in earlier smoke tests (see `RESULTS.md`
preliminary finding #2) was itself the bug this correction pass fixes, not
correct behaviour. No shipped scenario currently has exactly one telemetry
event, so the true zero-duration case is covered only at the pure-function
level today.

## MCI is never substituted for `CriticalMissionHealth` in the ARS M-pillar

`final_critical_mission_health` (used by `mission_continuity_service
.snapshot()`, which feeds `resilience_score_service._mission_preservation`)
is **the same resource-health definition as `MissionHealth`, restricted to
critical/high-criticality resources only, evaluated at the experiment's
FINAL state** — a snapshot, not a time-integral. From the module docstring:

> A snapshot, not a time-integral - MCI is computed separately and never
> substituted here.

These are deliberately two separate numbers: MCI answers "how much of the
experiment's duration was the mission healthy" (rewards fast recovery, not
just eventual recovery); `CriticalMissionHealth` answers "is the mission
healthy right now, at the end" (feeds directly into the 0-100 ARS). A run
that dipped badly mid-experiment but fully recovered gets a low MCI and a
high `CriticalMissionHealth` — both numbers are true and both are surfaced,
never merged into one.

## See also

`AEGIS_RESILIENCE_SCORE.md` for the M-pillar's full formula;
`METRICS_CATALOGUE.md` for the raw/normalized metrics MCI consumes.
