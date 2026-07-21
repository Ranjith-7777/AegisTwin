# Phase 4A.1: Detection Quality and Evaluation Hardening

Phase 4A.1 improves AegisTwin's offline synthetic behavioural detector without changing telemetry, simulation, playback, or WebSocket contracts. Every model input and evaluation event remains repository-generated and synthetic. An anomaly is evidence of deviation from a learned synthetic baseline, never proof of an attack.

## Root-cause diagnosis

The immutable v1 diagnostic is stored in `PHASE_4A1_V1_DIAGNOSTIC.json`. Under the documented seeds, v1 placed its threshold at 0.9333 while credential-compromise scores had a median of 0.5167. Only one of 21 scenario events crossed the threshold and only one of three runs produced any anomaly.

Three issues drove the original low recall:

1. Scenario-wide truth marked all seven steps positive, including routine application access.
2. The v1 schema lacked causal rolling, user-binding, transition, and graph context.
3. Empirical ranks had coarse resolution around tied validation scores and produced a conservative threshold.

## Evaluation-only benchmark truth

Benchmark labels live only in `evaluation_truth_service.py`; they are absent from `TelemetryEvent`, database telemetry rows, feature extraction, fitting, and calibration. They are applied after all scoring.

Credential-compromise steps 1, 2, 3, 4, 6, and 7 are labelled behaviourally anomalous. Step 5—routine application access—is negative even though it occurs in the same scenario. The evaluation exposes both:

- `event_level_metrics`: separate step-manifest truth, 18 positives across three runs;
- `scenario_wide_metrics`: transparent legacy comparison, all 21 scenario events positive.

They differ because scenario membership is broader than event-level behavioural truth. The legacy top-level metric fields remain scenario-wide for response compatibility; the new structured fields are authoritative for Phase 4A.1 analysis.

## Feature schema `synthetic-behaviour-v2`

V2 retains the useful v1 fields and adds:

- seconds since the previous event;
- rolling and cumulative failed attempts;
- distinct destinations and per-user sources observed so far;
- normal-trained user-device and user-source binding frequency;
- source-destination, event-type, and action transition frequency;
- transfer volume relative to learned user and event-type baselines;
- privilege transition and deviation from learned user privilege;
- hour distance from learned user activity;
- inventory relationship validity and graph distance.

Rows are processed in stable run order. State is isolated by run, and position N uses only positions 1 through N. Learned counts, means, categories, transitions, and bindings come only from synthetic normal training runs. Validation and evaluation categories cannot fit the `DictVectorizer`; unseen assets receive explicit `unknown` categories and unseen frequencies remain zero.

Scenario/run/event identifiers, severity, synthetic flags, benchmark labels, verdicts, and future incident/MITRE fields remain excluded.

## Bounded model comparison

V2 uses 300 deterministic IsolationForest estimators with full normal training samples and features. The comparison was intentionally bounded to the v1 configuration and this context-enriched v2 configuration. Selection was based on normal-only stability, deterministic preprocessing, and validation false-positive control—not final evaluation labels. Configuration and reasoning are stored in model metadata.

## Hybrid score

IsolationForest remains the primary detector. The auditable hybrid combines normal-only components with fixed, documented weights:

| Component | Weight |
|---|---:|
| IsolationForest empirical rank | 0.35 |
| Robust numerical/context deviation | 0.25 |
| Categorical and binding rarity | 0.15 |
| Behavioural transition rarity | 0.15 |
| Infrastructure novelty | 0.10 |

Weights are not fitted with attack or benchmark labels. Every assessment persists component values, hybrid raw score, and final normalised score.

## Calibration comparison

All methods use only synthetic normal training and complete held-out normal validation runs:

| Method | Raw threshold | Validation FPR | Held-out normal FPR | Event recall | Event F1 | Threshold ties |
|---|---:|---:|---:|---:|---:|---:|
| Empirical quantile v2 | 0.7221 | 0.10 | 0.00 | 0.8333 | 0.8333 | 1 |
| Interpolated ECDF v2 | 0.7011 | 0.10 | 0.00 | 0.8333 | 0.8333 | 0 |
| Validation FP-count v2 | 0.7221 | 0.10 | 0.00 | 0.8333 | 0.8333 | 1 |

Interpolated ECDF is the default because it respects the configured validation target, is deterministic, has the same normal stability, and provides better resolution around ties. FP-count calibration remains available and deterministically never exceeds the allowed whole-event false-positive count.

## Evaluation results

Results below use training seeds 1–5, validation 6–10, evaluation 11–13, `random_state=17`, and target validation FPR 0.10.

### Evaluation-only event truth

| Detector | Precision | Recall | F1 | ROC-AUC | Average precision |
|---|---:|---:|---:|---:|---:|
| Pure IsolationForest v2 | 1.0000 | 0.1667 | 0.2857 | 0.8254 | 0.7500 |
| Auditable hybrid | 0.8333 | 0.8333 | 0.8333 | 0.9087 | 0.8205 |
| Rule baseline | 0.8000 | 0.6667 | 0.7273 | — | — |

Held-out `normal-operations` false-positive rate is 0.00 for all three calibration candidates. The event-manifest confusion matrix contains three additional negatives from routine step 5 inside credential scenarios; the hybrid flags those three, so its all-negative event FPR is 0.1429. This distinction is reported rather than hidden.

### Scenario-wide comparison

The hybrid scenario-wide recall is 0.8571 with precision 1.0 and F1 0.9231. These values are higher because routine step 5 is counted positive in this legacy view.

### Run-level results

- suspicious runs with at least one anomaly: 100%;
- suspicious runs with at least two anomalies: 100%;
- first anomaly sequence: 1 for all three runs;
- simulated seconds to first anomaly: 0 for all three runs;
- held-out normal runs producing any anomaly: 0;
- average anomalies per normal run: 0;
- average anomalies per suspicious run: 6.

The desirable recall and suspicious-run detection targets are met honestly for this fixed synthetic benchmark, while held-out normal FPR remains below 0.05. These results do not establish production security performance.

## Remaining limitations

The scenario library is small and structurally regular. Hybrid weights are transparent fixed engineering choices rather than learned weights. Step 3 remains below threshold while routine step 5 is flagged, showing that event-level semantic precision still needs broader synthetic development scenarios. Calibration resolution remains limited by small samples. Training is synchronous, artifacts are local, and no live anomaly WebSocket, frontend integration, incident correlation, MITRE mapping, prediction, agents, LLM/RAG, topology visualisation, or response action is present.
