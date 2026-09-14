# Phase 5 Results

## ⚠ SUPERSEDED — read this before anything below

This document's **original** canonical-matrix run (dated in the "Original
Results (pre-correction)" section further down) was invalidated by three
research-validity corrections made during a later Phase 5 correction pass
(branch `feature/phase-5-observability-evaluation-reports`):

1. **Rule-Based/ML-Assisted baseline isolation.** The two "simple,
   non-agentic" baselines were found to be indirectly benefiting from Phase
   4's six-agent system via `orchestration_service` — every comparison
   against `agentic` was confounded. Now fixed: both strategies call
   `synthetic_mutation_service.compute_mutation()` directly and persist their
   own `EvaluationSyntheticActionRecord`, never an `AgentDecisionRecord`.
   See `app/services/evaluation/strategies.py` and
   `docs/architecture/adr/ADR-010-evaluation-baseline-isolation.md`'s
   addendum.
2. **Mission Continuity Index horizon bug.** `mci` incorrectly returned N/A
   for `no_active_defence` (and any experiment whose last reached stage
   landed near t=0) because the resilience curve never extended past the
   last reached stage. Now fixed: the curve always integrates out to the
   real `experiment_horizon_sim`. See
   `app/services/evaluation/mission_continuity_service.py` and
   `docs/architecture/adr/ADR-012-mission-continuity-index.md`'s addendum.
3. **Partial-observability robustness test was metrics-only.** The Section
   38 perturbation only filtered `AnomalyAssessmentRecord`s AFTER
   detection/correlation/response had already decided from the full,
   unperturbed evidence — only the reported SCORE changed, never the actual
   DEFENCE DECISION. Now fixed via a genuinely isolated "perturbed model
   identity" that `correlation_service.analyze()`/`response_service.analyze()`/
   `workflow_coordinator.run()` all read evidence through. See
   `app/services/evaluation/perturbation_service.py`.
4. **Correlation-visibility micro-correction (2026-09-14, robustness table
   only).** Even under the corrected "perturbed model identity" mechanism
   (item 3), `CorrelationService._map()` still mapped ATT&CK techniques from
   the FULL, unfiltered event list, and `evidence_events` admitted an event
   on EITHER a technique observation OR an anomalous assessment — so a
   hidden event whose raw telemetry fields matched a mapping rule could
   still re-enter the incident/ATT&CK evidence path even though its anomaly
   assessment was already neutralized. `CorrelationService.analyze()` now
   takes an optional `excluded_event_ids` parameter (default `None`/empty —
   a byte-for-byte no-op for every other caller), which
   `ExperimentService.create_and_run` populates with a perturbed
   experiment's `hidden_event_ids`. See
   `app/services/evaluation/perturbation_service.py`'s module docstring and
   the **"Robustness results, re-verified"** subsection below — re-running
   the same 16-pair/32-experiment robustness set under the fix produced
   **numerically identical results** to the table already below, so only
   that subsection (not the canonical 80-run matrix, which this fix cannot
   affect — see justification there) required a supersession note.

**The corrected results below supersede everything in the original
sections.** The original sections are preserved further down, clearly
marked, for transparency and audit trail — they are pre-correction and
should not be cited as current.

---

# Corrected Results (re-run 2026-09-14, post-correction)

## Methodology confirmation

Same approach as the original run: a standalone script mirroring
`tests/conftest.py`'s `Settings`/`Database` construction, built against a
fresh, persistent scratch sqlite file (not the ephemeral pytest fixture, not
the real dev `aegistwin.db`), using `.venv/Scripts/python.exe`. Executed the
real 4×5×4 = 80-experiment canonical matrix via
`BatchService.create_batch(session, scenario_ids=list(CANONICAL_SCENARIO_MATRIX.values()), seeds=CANONICAL_SEEDS, defence_modes=CANONICAL_DEFENCE_MODES)`,
then the separate 16-pair/32-experiment robustness set via
`run_robustness_experiment(session, scenario_id, seed=42, defence_mode=mode, hidden_fraction=0.3)`
for each of the 4 canonical scenarios × 4 defence modes.

**Run summary:** `batch.status == "completed"`, **80/80 completed, 0
failures**. Internal batch runtime (`time.perf_counter()` inside
`BatchService.create_batch`): **16.410s**. Measured wall-clock for the batch
step: 16.450s. The separate 32-experiment robustness set added 4.033s.
**Total measured wall-clock for all 112 experiments: 20.513s.** No
`failure_stage`/`failure_code`/`failure_message` to report — every
experiment reached `status == "completed"` and every completed experiment
produced a scored `ExperimentMetricRecord`. **No code bug was found or fixed
during this re-run** — the three prior corrections' code ran cleanly against
the full real matrix on the first attempt.

(The three corrections plus normal seed-to-seed/environment variance explain
why absolute runtime differs from the original run's 12.740s/16.223s — both
are real measurements of the same matrix shape on the same machine class;
neither run was tuned for speed and the difference is not evidence of a
regression.)

## Sanity-check results (PM spec Section 7) — run against the real corrected results

Verified with a scratchpad-only script (not committed) against all 80
canonical-matrix `ExperimentMetricRecord`s and the 32 robustness-set records,
freshly computed under the corrected code:

| # | Check | Result |
|---|-------|--------|
| 1 | `ars_total` ∈ [0,100] wherever non-null | **PASS** — 0 violations across 112 experiments |
| 2 | `mci` ∈ [0,1] wherever non-null | **PASS** — 0 violations |
| 3 | No negative `time_to_*` fields wherever non-null | **PASS** — 0 violations |
| 4 | `recovery_time_sim >= containment_time_sim` wherever both non-null | **PASS** — 0 violations (explicitly re-verified given the MCI horizon fix touched curve construction; the horizon fix only appends a point AFTER the last real stage, it does not alter `containment_time_sim`/`recovery_time_sim` themselves) |
| 5 | `first_detection_time_sim >= attack_start_time_sim` | **PASS** — 0 violations |
| 6 | Each of the 20 scenario×seed cells has exactly 4 experiments (one per mode); each of the 16 robustness scenario×mode cells has exactly one baseline+perturbed pair | **PASS** — 20/20 canonical cells complete, 16/16 robustness cells complete |
| 7 | Every `status=="completed"` experiment has a real, non-null `ExperimentMetricRecord` | **PASS** — 0 missing |
| 8 | `ComparisonService.check_fairness` returns `paired=True` for every same-scenario/same-seed cross-mode pair in the matrix | **PASS** — all pairwise comparisons checked across all 20 scenario/seed cells |
| 9 | **No Active Defence has no active mutation** (`changed_node_ids_json`/`changed_edge_ids_json` empty for all 20 `no_active_defence` experiments) | **PASS** — 0/20 have any mutation |
| 10 | **Rule/ML have zero Phase 4 `AgentDecisionRecord`s**, checked directly against the DB across ALL 40 canonical `rule_based`+`ml_assisted` experiments (not a sample) | **PASS** — 0/40 |
| 11 | **Agentic has the full six-agent trace** where the workflow actually reached execution | **15/20 show the expected 6-agent trace** (`Response Planner Simulation Agent` → `Impact Simulation Agent` → `Safety Governor Agent` → `Approval Router Agent` → `Synthetic Execution Agent` → `Verification Agent`, in order). **5/20 show only 4 agents** (stopping at `Approval Router Agent`) — all 5 are `suspicious-kubernetes-pod`/`workload_service_compromise`, all 5 canonical seeds. This is a real, legitimate outcome, not a bug: the Approval Router never granted automatic execution for this scenario class, so Synthetic Execution/Verification never ran — consistent with this scenario class's Agentic `ars_total` exactly tying `no_active_defence` (see below). |

## Aggregate stats per scenario class × defence mode (mean/std across the 5 canonical seeds)

| Scenario class | Mode | n | ARS mean (min–max) | ARS std | MCI mean (n applicable) |
|---|---|---|---|---|---|
| DDoS service saturation | No Active Defence | 5 | 30.0 (30.0–30.0) | 0.0 | 0.0 (5/5) |
| DDoS service saturation | Rule-Based | 5 | 54.5 (54.5–54.5) | 0.0 | 0.0 (5/5) |
| DDoS service saturation | ML-Assisted | 5 | 54.5 (54.5–54.5) | 0.0 | 0.0 (5/5) |
| DDoS service saturation | Agentic | 5 | 41.6 (41.6–41.6) | 0.0 | 0.0 (5/5) |
| Credential compromise | No Active Defence | 5 | 30.0 (30.0–30.0) | 0.0 | 0.0 (5/5) |
| Credential compromise | Rule-Based | 5 | 56.833345 (56.833345–56.833345) | 0.0 | 0.0 (5/5) |
| Credential compromise | ML-Assisted | 5 | 31.166655 (31.166655–31.166655) | 0.0 | 0.0 (5/5) |
| Credential compromise | Agentic | 5 | 41.6 (41.6–41.6) | 0.0 | 0.0 (5/5) |
| IAM privilege escalation | No Active Defence | 5 | 30.0 (30.0–30.0) | 0.0 | 0.0 (5/5) |
| IAM privilege escalation | Rule-Based | 5 | 54.5 (54.5–54.5) | 0.0 | 0.0 (5/5) |
| IAM privilege escalation | ML-Assisted | 5 | 31.499995 (31.499995–31.499995) | 0.0 | 0.0 (5/5) |
| IAM privilege escalation | Agentic | 5 | 41.6 (41.6–41.6) | 0.0 | 0.0 (5/5) |
| Workload/service compromise | No Active Defence | 5 | 32.5 (32.5–32.5) | 0.0 | 0.179487 (5/5) |
| Workload/service compromise | Rule-Based | 5 | 57.0 (57.0–57.0) | 0.0 | 0.179487 (5/5) |
| Workload/service compromise | ML-Assisted | 5 | 57.0 (57.0–57.0) | 0.0 | 0.179487 (5/5) |
| Workload/service compromise | Agentic | 5 | 32.5 (32.5–32.5) | 0.0 | 0.179487 (5/5) |

**The zero-variance-across-seeds limitation persists unchanged** (same root
cause documented in the "Original Results" section below: event timestamps
are a fixed `step.offset_seconds` from `start_time`, never randomized, so the
seed axis diversifies event *content* — IDs, exact counts/bytes — without
diversifying the *scored outcome* for this scenario catalogue and detector
configuration). This is expected and orthogonal to the three corrections;
reported again here for completeness rather than re-investigated, per the
instruction not to tune anything after seeing results.

**The headline MCI change, exactly as the correction predicted:** `mci` is
now `applicable` (non-`None`) for `no_active_defence` in **5/5 seeds of all
4 scenario classes** — previously 0/5 in every class (see "Original
Results" below). This is the real, expected, important change the horizon
fix was built for: a defence mode that never responds now gets a defined
Mission Continuity Index reflecting its sustained degraded state, instead of
a fabricated N/A that silently discarded the comparison.

**An honest, non-obvious observation the corrected numbers themselves
surface:** for 3 of the 4 scenario classes (DDoS, credential compromise, IAM
privilege escalation), the now-defined MCI is **identically `0.0` for every
mode tested, including Agentic**, which did execute a real containment
mutation (see the robustness decision signatures below — Agentic removed the
`external-user-01--api-gateway-01` edge in these scenarios). Only
`workload_service_compromise` shows a non-zero MCI (`0.179487`), and it is
identical across all four modes there too. Investigating why: `resource_health`
requires a node be BOTH not-exposed AND still operationally connected to the
entry point; severing the ingress edge to contain an attacker also severs
legitimate downstream connectivity through that same edge, so an affected
resource can remain scored "unhealthy" for a different reason (disconnected)
after containment than before it (exposed). Under this topology and these
four scenarios, no active-defence response tested here changed the
criticality-weighted Mission Health trajectory relative to doing nothing —
a genuine, reportable limitation of how "operationally connected" is
currently modeled relative to how these playbooks isolate ingress, not a
regression introduced by the horizon fix itself (which only changed where
the curve stops, not the per-point health values along the way).

## Paired comparisons at seed = 42 (real deltas, `ars_total` / `mci`)

Deltas are `compared_mode − reference_mode`. All pairs below are `paired:
true` (same `scenario_id`/`seed`/`topology_version`, matching
`metrics_version`/`ars_version`/`mci_version`), verified directly against the
canonical (non-robustness) seed=42 experiment records.

| Scenario class | No Active Defence → Rule-Based | No Active Defence → ML-Assisted | No Active Defence → Agentic | Rule-Based → Agentic | ML-Assisted → Agentic |
|---|---|---|---|---|---|
| DDoS service saturation | +24.5 | +24.5 | +11.6 | **−12.9** | **−12.9** |
| Credential compromise | +26.833345 | +1.166655 | +11.6 | **−15.233345** | **+10.433345** |
| IAM privilege escalation | +24.5 | +1.499995 | +11.6 | **−12.9** | **+10.100005** |
| Workload/service compromise | +24.5 | +24.5 | +0.0 | **−24.5** | **−24.5** |

`mci` deltas at seed=42: `0.0` for every pair in every scenario class (all
four modes tested land on the identical MCI value within each scenario
class — see the aggregate-stats discussion above for why).

## Robustness results (real, under the corrected perturbation mechanism)

16 scenario×mode pairs (4 canonical scenarios × 4 defence modes), seed=42,
`hidden_fraction=0.3`, run through the corrected `perturbed_model_id`
mechanism (a real, separate `DetectionModelRecord` identity whose scoring
genuinely omits the hidden events' signal, fed into
`correlation_service.analyze()`/`response_service.analyze()`/
`workflow_coordinator.run()`).

| Scenario | Mode | Baseline ARS | Perturbed ARS | Δ ARS | Baseline `detection_coverage` | Perturbed `detection_coverage` | Informative assessments (baseline → perturbed) | **Decision changed?** |
|---|---|---|---|---|---|---|---|---|
| ddos-traffic-spike | No Active Defence | 30.0 | 29.0 | −1.0 | 1.0 | 1.0 | 8 → 7 | No |
| ddos-traffic-spike | Rule-Based | 54.5 | 53.5 | −1.0 | 1.0 | 1.0 | 8 → 7 | No |
| ddos-traffic-spike | ML-Assisted | 54.5 | 53.5 | −1.0 | 1.0 | 1.0 | 8 → 7 | No |
| ddos-traffic-spike | Agentic | 41.6 | 40.6 | −1.0 | 1.0 | 1.0 | 8 → 7 | No |
| credential-compromise | No Active Defence | 30.0 | 28.45162 | −1.54838 | 1.0 | 1.0 | 7 → 6 | No |
| credential-compromise | Rule-Based | 56.833345 | 55.284965 | −1.54838 | 1.0 | 1.0 | 7 → 6 | No |
| credential-compromise | ML-Assisted | 31.166655 | 29.618275 | −1.54838 | 1.0 | 1.0 | 7 → 6 | No |
| credential-compromise | Agentic | 41.6 | 40.05162 | −1.54838 | 1.0 | 1.0 | 7 → 6 | No |
| staged-compromise-demo | No Active Defence | 30.0 | 29.33334 | −0.66666 | 1.0 | 1.0 | 12 → 10 | No |
| staged-compromise-demo | Rule-Based | 54.5 | 53.83334 | −0.66666 | 1.0 | 1.0 | 12 → 10 | No |
| staged-compromise-demo | ML-Assisted | 31.499995 | 30.833335 | −0.66666 | 1.0 | 1.0 | 12 → 10 | No |
| staged-compromise-demo | Agentic | 41.6 | 40.93334 | −0.66666 | 1.0 | 1.0 | 12 → 10 | No |
| suspicious-kubernetes-pod | No Active Defence | 32.5 | 32.5 | 0.0 | 1.0 | 1.0 | 8 → 6 | No |
| suspicious-kubernetes-pod | Rule-Based | 57.0 | 57.0 | 0.0 | 1.0 | 1.0 | 8 → 6 | No |
| suspicious-kubernetes-pod | ML-Assisted | 57.0 | 57.0 | 0.0 | 1.0 | 1.0 | 8 → 6 | No |
| suspicious-kubernetes-pod | Agentic | 32.5 | 32.5 | 0.0 | 1.0 | 1.0 | 8 → 6 | No |

**Decision-change finding, reported exactly as observed:** across all 16
pairs, `informative_assessment_count` (the real, mechanically-verified proof
that hidden evidence is genuinely absent from what
`response_service.analyze()`/`workflow_coordinator.run()` read — see
`perturbation_service.informative_assessment_count`) is strictly smaller
under perturbation in every case, confirming the corrected mechanism is
really operating on the decision inputs, not just the final score. **Despite
that, the DOWNSTREAM DECISION — the selected playbook and target for
Rule-Based/ML-Assisted (`EvaluationSyntheticActionRecord.playbook_id`/
`target_id`), and the orchestration's `changed_node_ids`/`changed_edge_ids`
for Agentic — is identical between baseline and perturbed in all 16 of 16
pairs at this `hidden_fraction=0.3`/`seed=42` configuration.** Only the
detection-coverage-adjacent scoring changed (a small, scenario-dependent ARS
drop for 3 of 4 scenario classes, zero effect for
`suspicious-kubernetes-pod`, matching the pattern already seen in the
pre-correction robustness table below). This is an honest, important
distinction from the OLD (pre-correction) mechanism: under the old
mechanism, the decision literally *could not* change, by construction — the
filtering happened after the decision was made. Under the corrected
mechanism, the decision *could* change (hidden evidence really is absent
from what every strategy reads), but empirically did not, at this specific
fraction and seed, for this scenario/topology combination — for these
scenarios' ground-truth attack steps, the 30%-hidden non-critical-severity
subset never happened to remove the specific evidence any strategy's target
selection actually keys on. This is a genuine, narrow robustness result
(defence *decisions* held up under this specific degraded-observability
perturbation) rather than a general robustness guarantee, and it is a
materially different, stronger claim than the pre-correction table below
could ever have supported — that table's "no change" was guaranteed by
construction; this table's "no change" is an empirical finding that could
have come out differently.

## Robustness results, re-verified after the correlation-visibility fix (2026-09-14)

A narrowly-scoped follow-on fix closed a residual leak in
`CorrelationService.analyze()`: `_map()` and `evidence_events` previously
ran over the FULL, unfiltered event list regardless of the perturbed model
identity, so a hidden event whose raw telemetry matched an ATT&CK mapping
rule could still contribute a real `TechniqueObservationRecord`/
`IncidentEvidenceRecord`, even though its `AnomalyAssessmentRecord` was
already correctly neutralized. `CorrelationService.analyze()` now accepts an
`excluded_event_ids` parameter (default `None`/empty, a byte-for-byte no-op
for the canonical matrix and every other caller); `ExperimentService
.create_and_run` passes it a perturbed experiment's `hidden_event_ids`. See
`app/services/evaluation/perturbation_service.py`'s module docstring and
`backend/tests/test_correlation_perturbation_visibility.py` for the unit-level
proof (a real event that produces a `TechniqueObservationRecord`/
`IncidentEvidenceRecord` under the canonical/visible pass produces neither
once excluded, and visible events keep their true full-run
`sequence_number`).

The same 16-pair/32-experiment robustness set (same methodology, same
`scenario_id` × `defence_mode` axes, same `seed=42`, same
`hidden_fraction=0.3`, same `run_robustness_experiment(...)` entry point, a
fresh standalone scratch-sqlite rerun) was re-run under the fix for direct
comparison to the table above. **Result: all 16 pairs are numerically
identical to the table above** — same baseline/perturbed ARS values (to the
same precision), same `detection_coverage` (1.0 → 1.0 in all 16 cases), same
informative-assessment counts, and `decision_changed == False` in all 16
cases, exactly as before. This means that, for this specific
`seed=42`/`hidden_fraction=0.3` configuration across these four canonical
scenarios, no hidden (LOW/MEDIUM-severity) event ever actually matched one
of `CorrelationService._map()`'s rules in the first place — the leak this
fix closes existed structurally (proven directly by the new unit tests
against a scenario/seed chosen specifically to trigger it,
`staged-compromise-demo` seed 84) but did not happen to fire for any of
these 16 robustness pairs' specific hidden-event sets. The robustness table
above therefore required no numeric changes; this subsection exists to make
that verification explicit rather than silently assumed.

**The canonical 80-run matrix was intentionally NOT re-run for this fix.**
Every canonical-matrix caller of `correlation_service.analyze()` passes no
`excluded_event_ids` (the parameter defaults to `None`/empty), which is
proven byte-for-byte identical to the pre-fix code path by
`test_excluded_event_ids_empty_or_omitted_is_byte_for_byte_identical` (see
the same test file) — comparing persisted `TechniqueObservationRecord`/
`IncidentEvidenceRecord` sets and every `CorrelationAnalysisResult` field for
the identical run/model with vs. without an explicit empty
`excluded_event_ids`. No regression was found in the full backend suite (300
passed, 0 failed) or the Phase 4 regression subset (57 passed) while
verifying this fix, so re-running the 80-run matrix was correctly judged
unnecessary.

## Research Integrity Findings — old vs. new interpretation, reported explicitly

Per the PM's instruction: **did the correction change which mode "wins"
anywhere? Yes, in two of the four scenario classes.**

- **Unchanged ranking pattern (DDoS service saturation, workload/service
  compromise):** Agentic still loses to both Rule-Based and ML-Assisted on
  DDoS (old: −24.9 vs. both; new: −12.9 vs. both — same direction, smaller
  magnitude now that Rule-Based/ML-Assisted can no longer borrow Phase 4's
  machinery). Agentic still exactly ties `no_active_defence` on
  workload/service compromise (old: 32.5 = 32.5; new: 32.5 = 32.5,
  unchanged) — now directly explained by the Section 7 audit's agentic-trace
  check: all 5 Agentic runs for this scenario class stop at 4 agents
  (Approval Router never grants automatic execution), so nothing ever
  executes, in both the old and new runs.
- **Changed ranking (credential compromise, IAM privilege escalation): Agentic
  now beats ML-Assisted where it previously lost.** Old: Agentic (41.6) lost
  to ML-Assisted (43.166655 / 43.499995). New: Agentic (41.6) beats
  ML-Assisted (31.166655 / 31.499995) by roughly +10 points in both classes.
  The mechanism is visible directly in the numbers: ML-Assisted's own score
  *fell* substantially (43.2→31.2, 43.5→31.5) once it could no longer borrow
  Phase 4's six-agent machinery and was restricted to genuinely
  auto-eligible playbooks (both credential-flavoured scenarios fall back to
  the safe default `increase-synthetic-monitoring` rather than a stronger
  targeted playbook, per `strategies.py`'s documented approval-eligibility
  policy) — this is exactly the confound ADR-010's addendum describes:
  ML-Assisted's old, higher score was never really "ML-Assisted," it was
  partly Phase 4's own Verification/rollback machinery credited to the
  wrong mode.
- **Rule-Based rose in the same two classes** (credential compromise:
  42.0→56.833345; IAM privilege escalation: 42.0→54.5) even though it is
  also now isolated from Phase 4 — its own real, isolated target selection
  in these scenarios happens to score higher under the corrected metrics
  pipeline than its old orchestration-routed path did. Both directions
  (ML-Assisted down, Rule-Based up) are real, and reported honestly rather
  than only reporting the direction that looks more dramatic.
- **Agentic still never wins outright against Rule-Based in any scenario
  class** — the −12.9 to −15.2 point gap against Rule-Based persists in
  every class where Rule-Based executes a real action. Whether this reflects
  a genuinely under-tuned Agentic strategy or a legitimate scoring-formula
  preference for Rule-Based's specific target choices remains an open
  question the corrected framework's results alone cannot resolve — exactly
  as the original findings section below already noted, and unchanged by
  this correction pass.
- **Taken together:** the corrected isolation did not manufacture an
  Agentic-always-wins result (a legitimate concern to check for, given the
  correction's author also maintains the Agentic system) — Agentic still
  loses to Rule-Based everywhere and still ties `no_active_defence` on one
  scenario class. What changed is that the ML-Assisted baseline's previously
  inflated numbers were corrected downward, changing its relative ranking
  against Agentic specifically, in exactly the two scenario classes where
  its old path most relied on Phase 4's borrowed machinery.

---

# Original Results (PRE-CORRECTION — SUPERSEDED, kept for audit trail only)

**Everything below this line was produced under the uncorrected
implementation described in the "SUPERSEDED" notice at the top of this
document. Do not cite it as current — see "Corrected Results" above.**

## Methodology: the canonical matrix

Defined in `app/services/evaluation/batch_service.py`:

```python
CANONICAL_SEEDS: list[int] = [17, 42, 84, 99, 123]
CANONICAL_DEFENCE_MODES: list[DefenceMode] = [
    DefenceMode.NO_ACTIVE_DEFENCE, DefenceMode.RULE_BASED,
    DefenceMode.ML_ASSISTED, DefenceMode.AGENTIC,
]
CANONICAL_SCENARIO_MATRIX: dict[str, str] = {
    "ddos_service_saturation": "ddos-traffic-spike",
    "credential_compromise": "credential-compromise",
    "iam_privilege_escalation": "staged-compromise-demo",
    "workload_service_compromise": "suspicious-kubernetes-pod",
}
```

4 scenario classes × 5 seeds × 4 defence modes = **80 experiments**, run
sequentially via `BatchService.create_batch` (per PM spec Section 33, no
distributed job system — a plain nested `for` loop is correct here). An
individual experiment's failure never aborts the batch (`failed_count` is
incremented and the loop continues; see spec Section 88).

**This canonical 80-experiment matrix has now been executed for real** (see
"Results" below). Execution used direct service calls — a standalone script
constructed a real `Settings`/`create_app`/`Database` (mirroring
`tests/conftest.py`'s own construction, but against a persistent sqlite file
rather than the ephemeral pytest fixture) and called
`BatchService.create_batch(...)` directly, rather than driving the FastAPI
`TestClient` through the HTTP layer — simpler, and avoids needing a running
server, at the cost of not exercising `app/api/routes/evaluation.py`'s
request/response layer (which is already covered by the existing test
suite). The separate 16-pair/32-experiment robustness set (Section 38) was
run the same way via `run_robustness_experiment(...)`.

## The scenario-class mapping finding: is `staged-compromise-demo` genuinely distinct from `credential-compromise`?

Documented honestly in `batch_service.py`'s module docstring, reproduced
here because it directly affects how the "IAM privilege escalation" class's
results should be read.

Comparing the two scenarios' `SimulationScenario.steps` directly:

- `credential-compromise` has **3** ground-truth (HIGH/CRITICAL severity)
  steps: step 4 "IAM privilege-level change" (HIGH), step 6 "Internal
  connection toward the cloud database" (HIGH), step 7 "Large synthetic
  outbound transfer" (HIGH). Its analogous "access the application pod"
  step (step 5) is severity MEDIUM — not ground truth.
- `staged-compromise-demo` has **4** ground-truth (HIGH severity) steps:
  step 8 "Explicit IAM permission change" (HIGH, with
  `metadata={"account_manipulation": True, ...}` — `credential-compromise`'s
  analogous step carries no such flag), step 9 "Remote service access
  toward the application pod" (HIGH, `metadata={"remote_service":
  "synthetic-cloud-shell"}` — the directly analogous step in
  `credential-compromise` is severity MEDIUM and NOT ground truth there),
  step 10 "Connection toward the cloud database" (HIGH), step 11 "Large
  outbound transfer..." (HIGH).

**Finding, stated honestly:** the two scenarios are not the same ground
truth wearing a different label — `staged-compromise-demo` promotes its
"application pod access" step to a genuine HIGH-severity ground-truth
attack step with a distinct `remote_service`/cloud-shell technique tag, and
adds an explicit `account_manipulation` flag on its privilege-change step,
giving it one more detectable attack step (4 vs. 3) with real
technique-level differences that `detection_coverage`/`false_positive_rate`
will score differently. This is a genuine, if narrow, distinction — not a
fabricated 4th class — so `staged-compromise-demo` is kept as the
IAM-privilege-escalation mapping.

**Honest limitation:** `staged-compromise-demo` and `credential-compromise`
share the same overall attack narrative (repeated failed auth → off-hours
login → unseen client → IAM change → lateral access → exfiltration) and
reuse the same asset topology, so they are a near-family rather than two
independent attacker archetypes. The distinguishing ground truth is real,
but the four scenario classes are not equally far apart from one another —
this pair is closer to each other than either is to the
DDoS/workload-compromise pair.

## Sanity-check checklist (PM spec Section 94) — run against the real results

Run programmatically (scratchpad-only verification script, not committed)
against all 80 completed canonical-matrix `ExperimentMetricRecord`s plus the
32 robustness-set records. Results:

| # | Check | Result |
|---|-------|--------|
| 1 | No identical results across all 4 defence modes for the same scenario/seed | **PASS** — 0/20 scenario/seed cells identical across all 4 modes |
| 2 | No perfect 100 ARS everywhere | **PASS** — 0/80 experiments scored `ars_total == 100` (observed range ≈ 30.0–69.0) |
| 3 | Agentic is not always exactly 100, and does not always win | **PASS** (not-100) / **honestly not always winning** — Agentic's `ars_total` ranges 32.5–41.6 across the matrix; a non-Agentic mode beats Agentic's `ars_total` in **40 of the 80** scenario/seed/mode comparisons (Rule-Based and/or ML-Assisted outscore Agentic on every one of the 4 scenario classes — see "Research Integrity Findings" below) |
| 4 | No zero variance across all 5 seeds for every metric, for every scenario/mode combination | **FAIL as literally stated — investigated and explained, not a wiring bug.** All 12 active-defence scenario/mode cells (4 scenarios × 3 active modes; `no_active_defence` mostly N/A on `mci`) show **exactly zero** variance in `ars_total`/`mci`/`detection_coverage`/`time_to_first_detection`/`attack_path_reduction` across all 5 canonical seeds. Root cause traced to `app/services/event_generator.py`: `Random(seed)` genuinely produces different values per seed (verified directly — seeds 17/42/84/99/123 produce distinct `unseen_device_id` suffixes 634/754/849/513/153), and those values do flow into `failed_attempts` (5–9 or 6–10) and `bytes_transferred` (18k–64k or 180M–260M) — but every event's **timestamp is a fixed `step.offset_seconds` from `start_time`, never randomized**, and the randomized magnitudes never cross a different detection/scoring threshold within the ranges actually rolled across these 5 seeds. Net effect: the seed axis currently diversifies event *content* (IDs, exact counts/bytes) without diversifying the *scored outcome* for this scenario catalogue and detector configuration. This is a real, reportable limitation of the current evaluation framework's seed sensitivity — not a fabricated or short-circuited RNG — and is called out honestly here rather than patched around in this results-generation stage. |
| 5 | No impossible negative times (`time_to_*` fields all ≥ 0 where non-null) | **PASS** — 0 negative values across all 80 experiments |
| 6 | No detection-before-attack-start (`time_to_first_detection >= 0`) | **PASS** — 0 violations (same check as #5, called out separately per spec) |
| 7 | No recovery-before-execution (`recovery_time_sim >= containment_time_sim`) | **PASS** — 0 violations |
| 8 | `attack_path_reduction`/`blast_radius_reduction`/`critical_exposure_reduction` ∈ [0,1] | **PASS** — 0 out-of-range values |
| 9 | `mci` ∈ [0,1] where non-null | **PASS** — 0 out-of-range values |
| 10 | `ars_total` ∈ [0,100] where non-null | **PASS** — 0 out-of-range values |

The same 5 numeric-range checks (times, reductions, `mci`, `ars_total`) were
also run against the 32 robustness-set experiments — **0 violations**.

## Two real preliminary findings (small-batch smoke tests, NOT the canonical result)

Collected during earlier implementation stages on small ad-hoc batches —
genuine early signals, to be confirmed or revised once the full canonical
matrix actually runs. Neither should be read as a final conclusion.

1. **For `leaked-api-credential` seed 7, Agentic and Rule-Based scored an
   IDENTICAL Aegis Resilience Score (41.6), and both were outperformed by
   ML-Assisted.** This is an honest example of the Agentic mode NOT
   winning — the evaluation framework is not tuned to guarantee the
   headline strategy wins, and this result is reported as-observed rather
   than omitted. Whether it holds up as a real pattern (e.g. a scenario
   where the Digital Twin what-if candidate comparison converges to the
   same target the deterministic rule table would already pick) or was an
   artifact of that particular seed/run will only be clear once the
   canonical matrix's 5-seed sample for this scenario class exists.
2. **`no_active_defence` experiments can have `mci: None`**, rather than a
   fabricated `0.0`. This happens when the experiment's resilience curve
   never leaves a single degraded state — `no_active_defence` never
   responds, so if the attack's effect on `MissionHealth` is constant
   across the whole run, `compute_mci`'s duration-based AUC is genuinely
   undefined (see `MISSION_CONTINUITY_INDEX.md`, "Zero-duration N/A case").
   Reporting `None` here rather than `0.0` is a deliberate honesty choice:
   a `0.0` would falsely claim "MCI was computed and is the worst possible
   value", when the true fact is "the time-integral has no defined
   duration to integrate over".

## Results

**Run summary:** 80/80 canonical-matrix experiments completed, **0
failures** (`batch.status == "completed"`, `failed_count == 0`). Internal
batch runtime (measured with `time.perf_counter()` inside
`BatchService.create_batch`, matching its own convention): **12.740s**.
Measured wall-clock for the batch step: 12.767s. The separate 32-experiment
robustness set added 3.456s. **Total measured wall-clock for all 112
experiments: 16.223s.** No `failure_stage`/`failure_code`/`failure_message`
to report — every experiment reached `status == "completed"` and every
completed experiment produced a scored `ExperimentMetricRecord` (0 cases of
"completed but metrics missing").

### Aggregate stats per scenario class × defence mode (mean/std across the 5 canonical seeds)

Per `aggregation_service.py`'s documented convention, `std` is the
population standard deviation over the 5-seed sample, reported purely as a
descriptive spread — see the zero-variance finding above for why every std
below is 0.0 for `ars_total`.

| Scenario class | Mode | n | ARS mean ± std | MCI mean ± std (n applicable) |
|---|---|---|---|---|
| DDoS service saturation | No Active Defence | 5 | 30.0 ± 0.0 | N/A (0/5 applicable) |
| DDoS service saturation | Rule-Based | 5 | 66.5 ± 0.0 | 0.0 ± 0.0 |
| DDoS service saturation | ML-Assisted | 5 | 66.5 ± 0.0 | 0.0 ± 0.0 |
| DDoS service saturation | Agentic | 5 | 41.6 ± 0.0 | 0.0 ± 0.0 |
| Credential compromise | No Active Defence | 5 | 30.0 ± 0.0 | N/A (0/5 applicable) |
| Credential compromise | Rule-Based | 5 | 42.0 ± 0.0 | 0.0 ± 0.0 |
| Credential compromise | ML-Assisted | 5 | 43.166655 ± 0.0 | 0.0 ± 0.0 |
| Credential compromise | Agentic | 5 | 41.6 ± 0.0 | 0.0 ± 0.0 |
| IAM privilege escalation | No Active Defence | 5 | 30.0 ± 0.0 | N/A (0/5 applicable) |
| IAM privilege escalation | Rule-Based | 5 | 42.0 ± 0.0 | 0.0 ± 0.0 |
| IAM privilege escalation | ML-Assisted | 5 | 43.499995 ± 0.0 | 0.0 ± 0.0 |
| IAM privilege escalation | Agentic | 5 | 41.6 ± 0.0 | 0.0 ± 0.0 |
| Workload/service compromise | No Active Defence | 5 | 32.5 ± 0.0 | N/A (0/5 applicable) |
| Workload/service compromise | Rule-Based | 5 | 52.491655 ± 0.0 | 0.179487 ± 0.0 |
| Workload/service compromise | ML-Assisted | 5 | 69.0 ± 0.0 | 0.179487 ± 0.0 |
| Workload/service compromise | Agentic | 5 | 32.5 ± 0.0 | 0.179487 ± 0.0 |

`no_active_defence`'s `mci` is `None`/N/A for every seed of every scenario —
consistent with the documented "Two real preliminary findings" item 2 above
(a defence mode that never responds gives `MissionHealth` no state change to
integrate over, so `compute_mci`'s duration-based AUC is genuinely
undefined, not a fabricated `0.0`).

### Paired comparisons at seed = 42 (`ComparisonService.compare_modes`, `ars_total`/`mci`)

Deltas are `compared_mode − reference_mode`. All pairs below are `paired:
true` (same `scenario_id`/`seed`/`topology_version`/metrics-and-score
versions on both sides).

| Scenario class | No Active Defence → Rule-Based | No Active Defence → ML-Assisted | No Active Defence → Agentic | Rule-Based → Agentic | ML-Assisted → Agentic |
|---|---|---|---|---|---|
| DDoS service saturation | +36.5 | +36.5 | +11.6 | **−24.9** | **−24.9** |
| Credential compromise | +12.0 | +13.166655 | +11.6 | **−0.4** | **−1.566655** |
| IAM privilege escalation | +12.0 | +13.499995 | +11.6 | **−0.4** | **−1.899995** |
| Workload/service compromise | +19.991655 | +36.5 | **+0.0** | **−19.991655** | **−36.5** |

(`mci` deltas against `no_active_defence` are all `None` — `no_active_defence`'s
`mci` is N/A as noted above, so `ComparisonService` correctly reports no
delta rather than treating N/A as 0. Every other `mci` delta in this matrix
is `0.0` — the 5-seed `mci` values are identical across Rule-Based/
ML-Assisted/Agentic for a given scenario, consistent with the zero-variance
finding above; `workload_service_compromise` is the one class where `mci`
is applicable and non-zero for all three active modes, at an identical
0.179487.)

### Robustness experiment set (Section 38 partial observability, `hidden_fraction=0.3`, seed=42): baseline vs. perturbed

> **Correction notice (post-hoc, methodology only — numbers below NOT yet
> re-run):** the table and "Honest interpretation" below were produced under
> an earlier, since-corrected implementation of the partial-observability
> perturbation that only filtered `AnomalyAssessmentRecord`s AFTER
> detection/correlation/response had already made their decision from the
> full, unperturbed evidence — i.e. only the reported SCORE was recomputed
> differently; the actual defence DECISION was never affected by the
> perturbation. That is exactly why the degradation below is uniform and
> mode-independent within a scenario ("identical in magnitude across all 4
> defence modes"): the hiding mask never had a chance to change what
> Rule-Based/ML-Assisted/Agentic actually decided, only what got counted
> afterward. The mechanism has since been corrected (see
> `app/services/evaluation/perturbation_service.py`'s module docstring and
> `docs/evaluation/EXPERIMENT_REPRODUCIBILITY.md`) to score a genuinely
> separate, perturbation-scoped detection-model identity
> (`ExperimentRecord.perturbed_model_id`) and route correlation/response/
> Agentic planning through it, so hidden evidence is now genuinely absent
> from what those decisions read, not just from the final metric. The
> numbers below are stale under the corrected mechanism and must be
> re-run — a later stage reruns the canonical matrix and this robustness
> set and replaces this table; until then, treat the ARS/coverage figures
> here as historical (old-mechanism) reference only, not as a current
> robustness result.

| Scenario | Mode | Baseline ARS | Perturbed ARS | Δ ARS | Baseline detected/detectable | Perturbed detected/detectable | Baseline `detection_coverage` | Perturbed `detection_coverage` |
|---|---|---|---|---|---|---|---|---|
| ddos-traffic-spike | No Active Defence | 30.0 | 29.0 | −1.0 | 4/4 | 4/4 | 1.0 | 1.0 |
| ddos-traffic-spike | Rule-Based | 42.0 | 41.0 | −1.0 | 4/4 | 4/4 | 1.0 | 1.0 |
| ddos-traffic-spike | ML-Assisted | 42.0 | 41.0 | −1.0 | 4/4 | 4/4 | 1.0 | 1.0 |
| ddos-traffic-spike | Agentic | 41.6 | 40.6 | −1.0 | 4/4 | 4/4 | 1.0 | 1.0 |
| credential-compromise | No Active Defence | 30.0 | 28.45162 | −1.54838 | 3/3 | 3/3 | 1.0 | 1.0 |
| credential-compromise | Rule-Based | 42.0 | 40.45162 | −1.54838 | 3/3 | 3/3 | 1.0 | 1.0 |
| credential-compromise | ML-Assisted | 42.0 | 40.45162 | −1.54838 | 3/3 | 3/3 | 1.0 | 1.0 |
| credential-compromise | Agentic | 41.6 | 40.05162 | −1.54838 | 3/3 | 3/3 | 1.0 | 1.0 |
| staged-compromise-demo | No Active Defence | 30.0 | 29.33334 | −0.66666 | 4/4 | 4/4 | 1.0 | 1.0 |
| staged-compromise-demo | Rule-Based | 42.0 | 41.33334 | −0.66666 | 4/4 | 4/4 | 1.0 | 1.0 |
| staged-compromise-demo | ML-Assisted | 42.0 | 41.33334 | −0.66666 | 4/4 | 4/4 | 1.0 | 1.0 |
| staged-compromise-demo | Agentic | 41.6 | 40.93334 | −0.66666 | 4/4 | 4/4 | 1.0 | 1.0 |
| suspicious-kubernetes-pod | No Active Defence | 32.5 | 32.5 | 0.0 | 3/3 | 3/3 | 1.0 | 1.0 |
| suspicious-kubernetes-pod | Rule-Based | 41.7 | 41.7 | 0.0 | 3/3 | 3/3 | 1.0 | 1.0 |
| suspicious-kubernetes-pod | ML-Assisted | 44.5 | 44.5 | 0.0 | 3/3 | 3/3 | 1.0 | 1.0 |
| suspicious-kubernetes-pod | Agentic | 32.5 | 32.5 | 0.0 | 3/3 | 3/3 | 1.0 | 1.0 |

**Honest interpretation:** for 3 of the 4 scenario classes (DDoS,
credential-compromise, IAM privilege escalation), hiding 30% of the
evidence produces a small, uniform ARS degradation (≈0.67–1.55 points,
identical in magnitude across all 4 defence modes within a scenario, since
the same evidence-hiding mask applies regardless of mode) and **no change
at all** to `detection_coverage` or `detected_attack_steps` — the hidden
evidence apparently never removed the specific events the detector actually
keys on for these 3 scenarios' ground-truth steps. For
`suspicious-kubernetes-pod`, the perturbation had **zero measurable effect**
on any scored metric for any mode — the 30%-hidden-evidence subset for this
particular scenario/seed happened not to include anything load-bearing for
detection or scoring. This is a real, if narrow, robustness result: defence
performance in this framework currently holds up well under this specific
partial-observability perturbation, but that finding is scenario- and
seed-dependent (only `hidden_fraction=0.3`, `seed=42` was tested per
scenario/mode here) rather than a general robustness guarantee, and the
uniform, small-magnitude, mode-independent degradation pattern is itself
worth noting as a limitation of how discriminating this particular
perturbation is at this hidden fraction.

### Research Integrity Findings

Per the PM spec's explicit instruction, every case where Agentic did **not**
win on `ars_total` is reported here, not hidden:

- **Agentic loses to both Rule-Based and ML-Assisted on 3 of the 4 scenario
  classes, every seed, no exceptions.** DDoS service saturation
  (Agentic 41.6 vs. Rule-Based/ML-Assisted 66.5, a 24.9-point gap),
  credential compromise (Agentic 41.6 vs. Rule-Based 42.0 / ML-Assisted
  43.166655), and IAM privilege escalation (Agentic 41.6 vs. Rule-Based 42.0
  / ML-Assisted 43.499995) all show this pattern across all 5 canonical
  seeds — 30 of the 40 "Agentic does not win" cases identified by the
  sanity-check script come from these three classes alone.
- **On `workload_service_compromise` (`suspicious-kubernetes-pod`), Agentic
  ties `no_active_defence` exactly (32.5 = 32.5) and loses to both
  Rule-Based (52.491655) and ML-Assisted (69.0) by a wide margin** — the
  worst single result in the matrix for Agentic relative to the other
  active modes. This is a new, more severe instance of the same pattern
  flagged in the "Two real preliminary findings" section above (where
  Agentic tied Rule-Based on `leaked-api-credential`, seed 7, in an earlier
  ad-hoc smoke test) — with the full canonical 5-seed sample now available,
  the finding is confirmed to be a genuine, reproducible pattern for this
  scenario class rather than a single-seed artifact, and is in fact worse
  than the earlier smoke test suggested (a tie, not just an underperformance).
- **Agentic wins outright only in the sense of beating `no_active_defence`
  on 3 of 4 scenario classes** (DDoS +11.6, credential compromise +11.6, IAM
  privilege escalation +11.6) — it never beats `no_active_defence` by more
  than the smallest active-defence margin in the matrix, and on
  `workload_service_compromise` it does not beat `no_active_defence` at all
  (delta 0.0).
- Taken together: **this evaluation framework does not artificially inflate
  the "headline" Agentic strategy.** Across the 80-experiment canonical
  matrix, Agentic has the *lowest* `ars_total` of the three active defence
  modes in every one of the 4 scenario classes tested. Whether this reflects
  a genuinely under-tuned Agentic strategy, a scoring methodology that
  happens to favor the simpler deterministic/ML strategies for these
  particular scenario classes, or a real and legitimate result (e.g.
  Agentic's Digital Twin what-if comparison converging on the same
  conservative action a rule table would already pick, at extra latency
  cost that this ARS formulation penalizes) is an open question the
  framework's results alone cannot resolve — but it is reported exactly as
  observed, not omitted or downplayed.

## See also

`PHASE_5_EVALUATION_FRAMEWORK.md` for fairness invariants;
`AEGIS_RESILIENCE_SCORE.md` / `MISSION_CONTINUITY_INDEX.md` for the scored
metrics; `docs/evaluation/EXPERIMENT_REPRODUCIBILITY.md` for what the
canonical constants guarantee.
