# Final Synthetic Benchmark Report

> All measurements are synthetic. They do not establish production security effectiveness.

## Configuration

- Benchmark size: one frozen staged-compromise demonstration run
- Seed: 84
- Model random state: 17
- Algorithms: deterministic scenario generator, Isolation Forest detection, conservative catalogue mapping, heuristic correlation/prediction/response orchestration

## Metadata

| Metric | Value |
|---|---|
| synthetic | True |
| scenario | staged-compromise-demo |
| seed | 84 |
| benchmark_runs | 1 |
| model_random_state | 17 |

## Detection

| Metric | Value |
|---|---|
| precision | 1.0 |
| recall | 0.9047619047619048 |
| f1_score | 0.9500000000000001 |
| roc_auc | 1.0 |
| average_precision | 1.0 |
| held_out_normal_false_positive_rate | 0.0 |
| suspicious_run_detection_rate | 1.0 |

## Mitre

| Metric | Value |
|---|---|
| supported_observation_count | 6 |
| mapping_coverage_on_benchmark_positive_steps | 1.0 |
| unsupported_mapping_count | 0 |
| conservative_mapping_check | True |

## Correlation

| Metric | Value |
|---|---|
| candidate_creation_coverage | 1.0 |
| first_correlated_sequence | 1 |
| first_high_priority_sequence | 11 |
| evidence_count | 11 |
| causal_sequence_compliance | True |

## Prediction

| Metric | Value |
|---|---|
| top_1_technique_accuracy | 1.0 |
| top_3_technique_accuracy | 1.0 |
| mean_reciprocal_rank | 1.0 |
| next_tactic_accuracy | 1.0 |
| next_asset_top_1_accuracy | 0.0 |
| next_asset_top_3_accuracy | 0.25 |
| objective_ranking_accuracy | 0.5 |
| prediction_coverage | 1.0 |
| insufficient_evidence_rate | 0.0 |
| mean_prediction_lead_sequences | 1.25 |
| predictions_before_observation | 4 |
| predictions_after_observation | 0 |
| baseline_comparison | {"limitations": "Tiny synthetic manifest; not production performance.", "name": "most-common-valid-transition", "next_asset_top_1_accuracy": 0.0, "top_1_technique_accuracy": 0.25} |

## Response

| Metric | Value |
|---|---|
| playbook_applicability_coverage | 1.0 |
| correlated_paths_interrupted | 5 |
| predicted_paths_interrupted | 0 |
| sensitive_reachability_before | 4 |
| sensitive_reachability_after | 4 |
| mean_operational_disruption | 0.075 |
| approval_tier_distribution | {"administrator_approval": 2, "analyst_approval": 5, "automatic_candidate": 3} |

## Orchestration

| Metric | Value |
|---|---|
| successful_synthetic_workflow_count | 1 |
| policy_block_count | 0 |
| approval_count | 1 |
| rejected_plan_count | 0 |
| verification_status | successful_simulation |
| rollback_count | 1 |
| audit_chain_integrity | True |

## Timings Seconds

| Metric | Value |
|---|---|
| simulation_start_to_first_anomaly | 0.3250065000029281 |
| first_anomaly_to_first_mitre_observation | 0.03881800000090152 |
| first_anomaly_to_correlated_candidate | 0.02888649993110448 |
| candidate_to_first_prediction | 0.0427759001031518 |
| playback_completion_to_response_recommendation | 0.08890249999240041 |
| orchestration_creation_to_approval | 0.014483900042250752 |
| approval_to_synthetic_execution_completion | 0.022246299893595278 |
| verification_duration | 0.021003900095820427 |
| rollback_duration | 0.028018999961204827 |

## Limitations

This small frozen benchmark is intended for deterministic demonstration regression only. Timings depend on the local machine and are synthetic demonstration workflow timings, not MTTD or MTTR. No final-benchmark tuning was performed.
