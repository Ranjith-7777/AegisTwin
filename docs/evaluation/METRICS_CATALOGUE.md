# Metrics Catalogue

Every metric below is computed by `EvaluationMetricsService.compute`
(`app/services/evaluation/metrics_service.py`) and persisted onto one
`ExperimentMetricRecord` per experiment (`metrics_version =
"aegis-evaluation-metrics-v1"`). Two JSON blobs hold them:

- **`raw_metrics_json`** — plain values. A plain JSON `null` unambiguously
  means "not computed / not applicable" (every raw metric's Python type
  already excludes `None` as a legitimate computed value).
- **`normalized_metrics_json`** — every entry wrapped in the `Metric`
  dataclass: `{"value": float | bool | None, "applicable": bool, "note": str
  | None}`. `applicable=False` means "does not apply to this experiment"
  (`value` always `None`); `applicable=True` with `value=0.0`/`False` is a
  real, meaningfully-computed zero, never conflated with "not applicable".

## Organization: MOP vs. MOE (per PM spec Section 10)

**Measures of Performance (MOP)** — how well the mechanics executed
(detection accuracy, timing, response completion), independent of whether
the outcome actually mattered to the mission:

- `detectable_attack_steps`, `detected_attack_steps`, `detection_coverage`,
  `false_positive_count`, `false_positive_rate`
- `time_to_first_detection`, `time_to_incident`, `time_to_response`,
  `time_to_containment`, `time_to_verified_recovery`
- `affected_asset_count`, `affected_relationship_count`,
  `bystander_impact_count`
- `containment_success`, `verification_success`, `rollback_required`,
  `rollback_success`
- `approval_count`, `administrator_approval_count`,
  `analyst_approval_count`, `autonomous_action_count`,
  `manual_action_count`
- Normalized: `detection_timeliness`, `recovery_timeliness`

**Measures of Effectiveness (MOE)** — did the response actually change the
attacker's reach and the mission's exposure:

- `attack_paths_before/after`, `attack_path_reduction`
- `blast_radius_before/after`, `blast_radius_reduction`
- `critical_assets_exposed_before/after`, `critical_exposure_reduction`
- `operational_disruption`, `residual_exposure_score`
- Mission Continuity Index (`mci`) and Aegis Resilience Score (`ars_total`)
  — see their own docs.

## Raw metrics — formulas and applicability

### Detection (`_detection_metrics`)

| Field | Formula | N/A when |
|---|---|---|
| `detectable_attack_steps` | count of scenario steps with severity in `{HIGH, CRITICAL}` (`GROUND_TRUTH_SEVERITIES`) | never (int, 0 is real) |
| `detected_attack_steps` | count of distinct ground-truth step sequences with at least one anomalous detection tracing back to them | never |
| `detection_coverage` | `detected_attack_steps / detectable_attack_steps` | `detectable_attack_steps == 0` |
| `false_positive_count` | anomalous detections NOT traceable to a ground-truth step | `anomalous_total == 0` |
| `false_positive_rate` | `false_positive_count / anomalous_total` — denominator is total anomalous **detections**, not total events, deliberately (a rate against total events would be dominated by background telemetry volume) | `anomalous_total == 0` |

### Logical timing (`_timing_metrics`) — all in seconds since attack start

| Field | Formula |
|---|---|
| `time_to_first_detection` | `first_detection_time_sim - attack_start_time_sim` |
| `time_to_incident` | `incident_confirmed_time_sim - attack_start_time_sim` |
| `time_to_response` | `response_start_time_sim - attack_start_time_sim` |
| `time_to_containment` | `containment_time_sim - attack_start_time_sim` |
| `time_to_verified_recovery` | `recovery_time_sim - attack_start_time_sim` |

Each is `None` if either endpoint was never reached. "Recovery" here means
**verified** recovery (successful rollback, or successful verification that
never needed one) — never merely "execution happened".

### Security graph reduction (`_security_metrics`)

Computed once per experiment via a single call to
`what_if_evidence_service.security_gain_evidence`, using the experiment's
real `changed_node_ids`/`changed_edge_ids` as the exclusion set — one
before/after recomputation, identical methodology for all four defence
modes (including `no_active_defence`, whose exclusion sets are empty, so
before honestly equals after).

| Field | Formula | N/A when |
|---|---|---|
| `attack_paths_before/after` | Attack Graph path counts | `run_id`/`detection_model_id` missing |
| `blast_radius_before/after` | Blast Radius reachable-asset counts | same |
| `critical_assets_exposed_before/after` | targets with `criticality in {"high","critical"}` reachable | same |
| `*_reduction` | shared `_reduction(before, after) = clamp((before - after) / max(1, before), 0, 1)` | `before == 0` (nothing to reduce) |

### Response/verification/rollback (`_response_metrics`)

| Field | Formula | N/A when |
|---|---|---|
| `affected_asset_count` / `affected_relationship_count` | `len(changed_node_ids)` / `len(changed_edge_ids)` | never (0 is real) |
| `operational_disruption` | reuses Phase 4's real `operational_disruption_score` when present; else `len(changed_edges) / max(1, total_topology_edges)`; else `0.0` for `no_active_defence` (genuinely 0, not N/A — no mutation ever happened) | never |
| `bystander_impact_count` | `len(metrics_json["bystander_isolated_asset_ids"])` | never (0 is real) |
| `residual_exposure_score` | reuses Phase 4's real score when present; else `1.0 - attack_path_reduction` | `attack_path_reduction` unavailable |
| `containment_success` | `verification_status == "successful_simulation"` | `orchestration_id is None` |
| `verification_success` | verification record's status `== "successful_simulation"` | no verification record |
| `rollback_required` / `rollback_success` | only meaningful once verification actually failed | verification never failed |

### Human involvement (`_human_involvement_metrics`)

`approval_count`, `administrator_approval_count`, `analyst_approval_count`
(counted from approved `ApprovalRequestRecord`s), `autonomous_action_count`,
`manual_action_count` (copied from `ExperimentRecord`). All always
applicable (0 is real).

## Normalized metrics (`_normalized_metrics`)

| Field | Formula | Applicability |
|---|---|---|
| `detection_coverage` | copies the raw value | N/A if raw is `None` (zero ground-truth steps) |
| `false_positive_rate` | copies the raw value | N/A if raw is `None` |
| `attack_path_reduction`, `blast_radius_reduction`, `critical_exposure_reduction` | shared `_reduction` | N/A if evidence missing or before-count is 0 |
| `detection_timeliness` | `1 - min(1, time_to_first_detection / experiment_horizon_sim)` | **always applicable** — `0.0` with a note when never detected (per spec Section 17, never N/A) |
| `recovery_timeliness` | `1 - min(1, time_to_verified_recovery / experiment_horizon_sim)` | **always applicable** — `0.0` with a note when no verified recovery was reached (per spec Section 18, never N/A) |

## Logical-time field list (`logical_timeline_json`, seconds since attack start unless noted)

`attack_start_time_sim` (always `0.0` once a run exists), `first_detection_time_sim`,
`incident_confirmed_time_sim`, `response_start_time_sim`,
`containment_time_sim`, `verification_time_sim`, `recovery_time_sim`,
`experiment_horizon_sim` (total simulated duration, last event minus first
event). These are the simulated-clock family — see
`PHASE_5_EVALUATION_FRAMEWORK.md` for the "shared instant" convention.

## Computation-latency field list (`computation_latency_json`, milliseconds, real wall clock)

`workflow_latency_ms` (whole defence-strategy dispatch, measured in
`ExperimentService.create_and_run` with `time.perf_counter()`),
`evaluation_what_if_latency_ms` (the metrics stage's own Attack
Graph/Blast Radius recomputation). `planning_latency_ms` and
`what_if_latency_ms` are always `None` in this stage — deliberately, to
avoid invasive per-agent instrumentation changes to `strategies.py`. This
family is the wall-clock family — never conflated with the logical-time
family above.

## Aggregation-only field families

`aggregation_service.RAW_NUMERIC_METRICS` (every numeric raw field above,
aggregated with mean/median/population-stdev/min/max over applicable
samples only), `NORMALIZED_ONLY_METRICS = (detection_timeliness,
recovery_timeliness)`, and `BOOLEAN_OUTCOME_METRICS = (containment_success,
verification_success, rollback_success)` (aggregated as success rate over
applicable samples). See `RESULTS.md` for the sample-size caveat on
`std`.
