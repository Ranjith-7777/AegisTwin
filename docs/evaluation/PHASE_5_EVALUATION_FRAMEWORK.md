# Phase 5: The Evaluation Framework

## Research question

Does AegisArena's Digital-Twin-driven agentic defence measurably improve
cloud resilience compared with simpler defensive baselines? Phase 5 answers
this by running the SAME synthetic attack (fixed scenario, fixed seed, fixed
topology, fixed detection model) under four different defence strategies and
scoring each run on identical, strategy-neutral metrics — never by asking a
human to eyeball a demo.

## The 8 core deliverables

1. **Experiment model** (`app/services/evaluation/experiment_service.py`) —
   a reproducible unit of "attack scenario + seed + detection groundwork +
   one defence mode", with a persisted `ExperimentRecord` lifecycle.
2. **Four defence-strategy baselines**
   (`app/services/evaluation/strategies.py`) — `no_active_defence`,
   `rule_based`, `ml_assisted`, `agentic`. See `DEFENCE_BASELINES.md`.
3. **Raw and normalized metrics**
   (`app/services/evaluation/metrics_service.py`) — every measure of
   detection, timing, security-graph reduction, response outcome, and human
   involvement, with an explicit applicability/N/A convention. See
   `METRICS_CATALOGUE.md`.
4. **Mission Continuity Index (MCI)** and Mission Health curve
   (`app/services/evaluation/mission_continuity_service.py`) — a
   trapezoidal-AUC time-integral of mission-relevant resource health. See
   `MISSION_CONTINUITY_INDEX.md`.
5. **Aegis Resilience Score (ARS)**
   (`app/services/evaluation/resilience_score_service.py`) — a locked,
   4-pillar, strategy-neutral 0–100 score. See `AEGIS_RESILIENCE_SCORE.md`.
6. **Batch runner and aggregation**
   (`app/services/evaluation/batch_service.py`,
   `aggregation_service.py`, `comparison_service.py`) — the canonical
   scenario x seed x defence_mode matrix, descriptive statistics, and paired
   before/after comparisons.
7. **Unified experiment timeline**
   (`app/services/evaluation/timeline_service.py`) — a reconstructed,
   fixed-stage-order view of one experiment's real, persisted evidence.
8. **REST API, exports, and a full Evaluation dashboard UI**
   (`app/api/routes/evaluation.py`, `frontend/src/pages/evaluation/*.tsx`) —
   7 pages covering overview, experiment list/detail, comparison, aggregate
   statistics, batches, and a print-friendly report. See
   `docs/ui/PHASE_5_EVALUATION_UI.md`.

## Experiment lifecycle

```
CREATED -> RUNNING_ATTACK -> DETECTING -> RESPONDING -> VERIFYING -> COMPLETED
                                                      \-> FAILED (any stage)
```

(`app/schemas/evaluation.py::ExperimentStatus`, driven by
`ExperimentService.create_and_run`.) Every experiment, regardless of
`defence_mode`, runs the same attack replay, the same canonical detection
training/scoring, and the same incident correlation before a defence
strategy is ever dispatched — this is what makes `no_active_defence` a fair
control rather than a strawman: it still sees the incident, it just never
acts on it (`app/services/evaluation/strategies.py`, module docstring).

**Per-mode skip semantics, stated honestly:**

- `no_active_defence` never reaches `RESPONDING` in any meaningful sense —
  its strategy returns immediately with a note and no orchestration.
  `status` still passes through `RESPONDING` structurally, but the strategy
  performs no action; `VERIFYING` is only entered when an orchestration was
  actually produced (`ExperimentService._apply_outcome`: `if
  outcome.orchestration_id is not None`).
- `rule_based` and `ml_assisted` reach `VERIFYING` whenever a target could be
  resolved; a pending human-approval gate is auto-approved by the evaluation
  harness itself (`strategies.py::_advance_to_terminal`) — the Safety
  Governor/Approval Router still ran and made a real decision, the harness
  only supplies the human decision that gate would otherwise block on.
- `agentic` runs the real `workflow_coordinator.run()` production path with
  global autonomy temporarily forced to `AUTONOMOUS` for the duration of the
  call, restored via a `finally` block regardless of outcome
  (`strategies.py::AgenticDefenceStrategy.execute`).
- A hard failure at any stage sets `status=FAILED`, records
  `failure_stage`/`failure_code`/`failure_message`, and never aborts a
  containing batch (see `EXPERIMENT_REPRODUCIBILITY.md` and
  `RESULTS.md`).

## Fairness invariants

Held constant across every experiment and every paired comparison
(`ComparisonService.check_fairness`, `app/services/evaluation/
comparison_service.py`):

- `scenario_id` and `seed` — the identical attack replay.
- `topology_version` — the identical synthetic infrastructure graph.
- The canonical detection model configuration
  (`CANONICAL_TRAINING_REQUEST`, `experiment_service.py`) — every experiment
  trains/reuses the same deterministic detector, so defence modes are
  compared against each other, never against different detectors.
- Timing constants: `CANONICAL_START_TIME` (2026-01-01T00:00:00Z) and
  `CANONICAL_PLAYBACK_SPEED` (1.0) — fixed so comparisons and reproductions
  are never confounded by a different attack timeline or replay speed.
  **Never vary these per-experiment.**
- Once both experiments are scored, `metrics_version`/`ars_version`/
  `mci_version` must also match — a comparison across incompatible scoring
  versions is refused as "paired" and surfaced with a warning instead
  (`FairnessCheckResult.reasons`), never silently presented as fair.

## Why strict baseline-agent isolation matters scientifically

A Phase 5 correction pass (feature/phase-5-observability-evaluation-reports)
found that `RuleBasedDefenceStrategy`/`MLAssistedDefenceStrategy` had been
calling `orchestration_service.create()`/`.execute()`/`.verify()` internally
— which runs ALL SIX of Phase 4's Blue agents (Response Planner, Impact
Simulation, Safety Governor, Approval Router, Synthetic Execution,
Verification) and persists an `AgentDecisionRecord` for each. This is not a
cosmetic bug: it means the two "simple, non-agentic" baselines were secretly
benefiting from the exact sophisticated system (`agentic`) they exist to be
compared against.

The reason this invalidates the whole exercise, not just one row of a table:
Phase 5's entire research question is "does the six-agent Agentic system add
real value over simpler defence strategies?" If Rule-Based/ML-Assisted can
silently reach into the same six-agent orchestration pipeline, every
downstream comparison is confounded — a high Rule-Based/ML-Assisted score no
longer distinguishes "a simple heuristic did well" from "Phase 4's own
machinery did the real work, credited to a baseline." No amount of
statistical rigor in the aggregation/comparison layer can rescue a result
built on an unfair input; the corruption happens upstream of every metric
this framework computes. This is why `strategies.py` now calls
`synthetic_mutation_service.compute_mutation()` directly and persists an
`EvaluationSyntheticActionRecord` instead — see
`app/services/evaluation/strategies.py`'s module docstring and
`docs/architecture/adr/ADR-010-evaluation-baseline-isolation.md`'s addendum
for the full correction and its verification (zero `AgentDecisionRecord`s
across all 40 canonical Rule-Based/ML-Assisted experiments, re-confirmed
against the real re-run — see `RESULTS.md`).

The same principle applies to the Section 38 partial-observability
robustness test. An earlier revision of `perturbation_service.py` hid
evidence only from the FINAL REPORTED SCORE — detection/correlation/response
still made every decision from the full, unperturbed evidence set, and only
the metrics layer recomputed a different number afterward. That answers a
different, much weaker question ("does the SCORE change if we discount some
evidence after the fact") than the one Section 38 actually asks ("does the
DEFENCE ITSELF degrade when the defender genuinely observes less"). A
robustness test that only ever perturbs the score, never the decision input,
cannot distinguish a genuinely robust defender from a defender whose
decisions were never actually tested under degraded observability at all.
The corrected mechanism (a real, isolated "perturbed model identity" fed
into `correlation_service.analyze()`/`response_service.analyze()`/
`workflow_coordinator.run()`) fixes this by making the hidden evidence
genuinely invisible to the decision itself, not just to the scoring pass —
see `perturbation_service.py`'s module docstring for the full mechanism.

## Logical time vs. wall-clock latency

Copied verbatim from the convention `metrics_service.py`'s module docstring
establishes and every later stage (Mission Continuity, timeline
reconstruction) reuses unchanged:

> The synthetic attack/detection/response timeline advances entirely through
> `TelemetryEventRecord.timestamp` ... and the ordinal position of an event
> within `order_by(TelemetryEventRecord.timestamp, TelemetryEventRecord.event_id)`
> ... A "through_sequence_number" anywhere in this codebase ... is a
> 1-indexed position in that exact ordering.
>
> Phase 4's response/verification/rollback machinery has NO simulated clock
> of its own ... The honest measurement convention adopted here ... is:
> **every Blue-side event (response start, containment, verification,
> recovery) shares the SAME simulated instant** — the timestamp of the
> telemetry event at the orchestration's `through_sequence_number`. They
> differ only in *whether* they were reached at all ... never in *when*.

Real wall-clock computation cost (how long the Python code actually took) is
tracked completely separately, in `computation_latency_json`
(`workflow_latency_ms`, `evaluation_what_if_latency_ms`), populated from
`time.perf_counter()` measurements — never conflated with simulated time.
`planning_latency_ms` and `what_if_latency_ms` are intentionally `None` in
this stage (measuring them individually would require invasive changes to
`strategies.py` that the Stage 2 brief explicitly avoided).

## See also

- `DEFENCE_BASELINES.md` — the four strategies in detail.
- `METRICS_CATALOGUE.md` — every raw/normalized metric.
- `AEGIS_RESILIENCE_SCORE.md` / `MISSION_CONTINUITY_INDEX.md` — the two
  headline scores.
- `EXPERIMENT_REPRODUCIBILITY.md` — versioning, re-run, immutability.
- `RESULTS.md` — the canonical matrix and (pending) results.
- `docs/ui/PHASE_5_EVALUATION_UI.md` — the dashboard.
- `docs/research/PHASE_5_RESEARCH_FOUNDATIONS.md` — conceptual grounding.
- ADR-010 through ADR-013 in `docs/architecture/adr/`.
