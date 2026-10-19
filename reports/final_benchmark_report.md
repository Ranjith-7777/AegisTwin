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
| evaluated_from_persisted_workflow | True |

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
| evidence_count | 9 |
| causal_sequence_compliance | True |

## Prediction

| Metric | Value |
|---|---|
| top_1_technique_accuracy | 1.0 |
| top_3_technique_accuracy | 1.0 |
| mean_reciprocal_rank | 1.0 |
| next_tactic_accuracy | 1.0 |
| next_asset_top_1_accuracy | 0.0 |
| next_asset_top_3_accuracy | 0.0 |
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
| correlated_paths_interrupted | 6 |
| predicted_paths_interrupted | 0 |
| sensitive_reachability_before | 8 |
| sensitive_reachability_after | 8 |
| mean_operational_disruption | 0.050000100000000006 |
| approval_tier_distribution | {"administrator_approval": 2, "analyst_approval": 6, "automatic_candidate": 2} |

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

## Evaluation

| Metric | Value |
|---|---|
| experiment_id | 19c72c9c-ae40-58ea-8ee4-ac392aa5d045 |
| evaluation_source | completed_workflow |
| source_run_id | 29d9cd0b-9137-5ba2-8b09-b33041c1ba66 |
| source_incident_candidate_id | 87625ce2-fffb-5e1e-954b-47586128f847 |
| source_orchestration_id | 4d48f116-e6e7-54e9-a960-455a94ff4adc |
| workflow_terminal_state | synthetic_rollback_completed |
| metrics_version | aegis-evaluation-metrics-v1 |
| mci | 0.0 |
| mci_version | aegis-mci-v1 |
| ars_total | 44.999995 |
| ars_pillars | {"A": {"applicable": true, "components": {"detection_coverage": {"applicable": true, "effective_weight": 0.6, "raw_value": 1.0, "weight": 0.6}, "detection_timeliness": {"applicable": true, "effective_weight": 0.4, "raw_value": 1.0, "weight": 0.4}}, "value": 1.0}, "M": {"applicable": true, "components": {"critical_mission_health": {"applicable": true, "effective_weight": 0.6, "raw_value": 0.0, "weight": 0.6}, "operational_disruption_inverse": {"applicable": true, "effective_weight": 0.4, "raw_value": 1.0, "weight": 0.4}}, "value": 0.4}, "R": {"applicable": true, "components": {"recovery_timeliness": {"applicable": true, "effective_weight": 0.4, "raw_value": 0.1875, "weight": 0.4}, "verified_recovery_reached": {"applicable": true, "effective_weight": 0.6, "raw_value": 1.0, "weight": 0.6}}, "value": 0.675}, "W": {"applicable": true, "components": {"attack_path_reduction": {"applicable": true, "effective_weight": 0.4, "raw_value": 0.0, "weight": 0.4}, "blast_radius_reduction": {"applicable": true, "effective_weight": 0.3, "raw_value": 0.142857, "weight": 0.3}, "critical_exposure_reduction": {"applicable": true, "effective_weight": 0.3, "raw_value": 0.0, "weight": 0.3}}, "value": 0.042857}, "effective_pillar_weights": {"A": 0.2, "M": 0.25, "R": 0.2, "W": 0.35}} |
| ars_version | aegis-resilience-score-v1 |
| source_evidence | {"execution_id": "5ee560eb-9af1-5475-8cfc-37e87281f9af", "incident_candidate_id": "87625ce2-fffb-5e1e-954b-47586128f847", "orchestration_id": "4d48f116-e6e7-54e9-a960-455a94ff4adc", "rollback_id": "a0151420-db30-521f-a34b-92d4c406427b", "simulation_run_id": "29d9cd0b-9137-5ba2-8b09-b33041c1ba66", "verification_id": "dd213696-16ed-5c80-8a9a-7b4d81dd2002"} |

## Timings Seconds

| Metric | Value |
|---|---|
| simulation_start_to_first_anomaly | 0.21230070001911372 |
| first_anomaly_to_first_mitre_observation | 0.02681529999244958 |
| first_anomaly_to_correlated_candidate | 0.020110699988435954 |
| candidate_to_first_prediction | 0.027394000004278496 |
| playback_completion_to_response_recommendation | 0.05062449999968521 |
| orchestration_creation_to_approval | 0.0067663999798242 |
| approval_to_synthetic_execution_completion | 0.009852999995928258 |
| verification_duration | 0.02766160000464879 |
| rollback_duration | 0.007807400019373745 |

## Limitations

This small frozen benchmark is intended for deterministic demonstration regression only. Timings depend on the local machine and are synthetic demonstration workflow timings, not MTTD or MTTR. No final-benchmark tuning was performed.
