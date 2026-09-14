# The Aegis Resilience Score (ARS)

`app/services/evaluation/resilience_score_service.py`
(`ARS_VERSION = "aegis-resilience-score-v1"`).

**UI caption (required, always shown alongside the score):**
"Deterministic evaluation score, not a probability."

## Locked formula

```
ARS = 100 * (0.20*A + 0.35*W + 0.25*M + 0.20*R)
```

| Pillar | Weight | Meaning |
|---|---|---|
| A — Threat Awareness | 0.20 | did the system see the attack, and quickly |
| W — Withstand/Containment | 0.35 | how much attacker reach was removed |
| M — Mission Preservation | 0.25 | how healthy is the mission at the end |
| R — Verified Recovery | 0.20 | was the system brought back to a verified-good state, and quickly |

## The 4 pillars

**A = 0.60 × DetectionCoverage + 0.40 × DetectionTimeliness**
(`_threat_awareness`)

**W = 0.40 × AttackPathReduction + 0.30 × BlastRadiusReduction + 0.30 × CriticalExposureReduction**
(`_withstand_containment`)

**M = 0.60 × CriticalMissionHealth + 0.40 × (1 − OperationalDisruption)**
(`_mission_preservation`). `CriticalMissionHealth` comes from
`mission_continuity_service.snapshot()` — a **snapshot**, not the MCI
time-integral; see `MISSION_CONTINUITY_INDEX.md` for why these are
deliberately separate numbers. `OperationalDisruption` is always applicable
(real `0.0` for `no_active_defence`, never N/A), so M can never be wholly
N/A in this codebase's actual metric set.

**R = 0.60 × V + 0.40 × RecoveryTimeliness** (`_verified_recovery`). `V` is
`1.0` iff `verification_success is True` or a completed rollback counts as a
confirmed recovered state, else `0.0` — including `no_active_defence`, which
never attempted recovery at all (`V=0`, per spec Section 27's explicit
case). `V` and `recovery_timeliness` are both always applicable, so R can
never be wholly N/A — confirmed by
`tests/test_resilience_score.py::test_verified_recovery_never_na`.

## N/A redistribution — two levels, never conflated

1. **Within a pillar:** if one submetric is inapplicable, its weight is
   redistributed across the remaining applicable submetric(s) of that SAME
   pillar. If every submetric in a pillar is inapplicable, the whole pillar
   is `None`/inapplicable (never defaulted to 0.0 or 1.0).
2. **Across pillars, at the top level:** only when a WHOLE pillar is
   inapplicable does its weight redistribute across the remaining applicable
   pillars. A pillar is never partially discounted at the top level.

In this codebase's actual metric set, M and R can never be wholly N/A (their
components are always applicable), so only A and W can ever trigger
top-level renormalization. `total` is `None` only if literally every pillar
were N/A, which cannot happen here since R never is — handled anyway, never
assumed impossible.

```python
# resilience_score_service.py::_weighted_pillar
applicable_weight = sum(weight for _, _, applicable, weight in items if applicable)
effective_weight = (weight / applicable_weight) if applicable and applicable_weight > 0 else 0.0
value = sum(raw_value * (weight / applicable_weight) for ... if applicable)
```

## Strategy-neutrality — structurally enforced

`compute_score(metrics: ExperimentMetricRecord, mission_continuity:
MissionContinuitySnapshot) -> ResilienceScoreResult` is the actual scoring
function. Neither input type has a `defence_mode`/`autonomy_mode`/
approval-count/anything-strategy-identifying field, so it is **structurally
impossible** for this function to branch on strategy — not merely "written
not to". `ResilienceScoreService.compute` is the only place that touches
`ExperimentRecord`/`session` at all, purely to load the two inputs and
persist the result.

Proven by two tests in `backend/tests/test_resilience_score.py`:

- `test_signature_has_no_strategy_parameter` — inspects
  `inspect.signature(compute_score)` and asserts the parameter set is
  exactly `{"metrics", "mission_continuity"}`, plus asserts neither
  `ExperimentMetricRecord`'s mapped columns nor
  `MissionContinuitySnapshot`'s dataclass fields contain
  `defence_mode`/`autonomy_mode`.
- `test_identical_metrics_produce_identical_score` — two calls with
  identical metric inputs always produce an identical score, proving there
  is no hidden global state `compute_score` could be reading.

## Worked example (real, from `tests/test_resilience_score.py`)

Fixture defaults: `detection_coverage=0.8`, `detection_timeliness=0.7`,
`attack_path_reduction=0.6`, `blast_radius_reduction=0.5`,
`critical_exposure_reduction=0.5`, `operational_disruption=0.2`,
`critical_mission_health=0.9`, `verification_success=True`,
`recovery_timeliness=0.9`.

**`test_whole_pillar_na_renormalizes_top_level`** — both A submetrics N/A,
so ARS renormalizes across W, M, R only:

```
W = 0.40*0.6 + 0.30*0.5 + 0.30*0.5 = 0.24 + 0.15 + 0.15 = 0.54
M = 0.60*0.9 + 0.40*(1-0.2)        = 0.54 + 0.32       = 0.86
R = 0.60*1.0 + 0.40*0.9            = 0.60 + 0.36       = 0.96
renormalized_total_weight = 0.35 + 0.25 + 0.20 = 0.80
ARS = 100 * (0.35*0.54 + 0.25*0.86 + 0.20*0.96) / 0.80
    = 100 * (0.189 + 0.215 + 0.192) / 0.80
    = 100 * 0.596 / 0.80 = 74.5
```

**`test_within_pillar_na_redistribution_is_correct`** —
`detection_coverage` N/A, `detection_timeliness=0.7`: A's weight fully
redistributes to the one remaining applicable submetric, so
`A = (0.40/0.40) * 0.7 = 0.7` exactly.

Both numbers are asserted directly in the test file and are not
independently re-derived here.

## Results — PENDING

The real ARS distribution across the canonical 80-experiment matrix has not
been computed yet at the time of writing. See `RESULTS.md` for the
methodology and the placeholder for final numbers, and for two genuine
small-batch smoke-test observations already collected during
implementation.

## See also

`MISSION_CONTINUITY_INDEX.md` for the MCI-vs-`CriticalMissionHealth`
distinction; `METRICS_CATALOGUE.md` for every submetric's own formula;
ADR-011 for why these 4 pillars/weights were chosen.
