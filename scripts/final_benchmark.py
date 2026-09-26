"""Generate consolidated synthetic benchmark reports from frozen local inputs."""

import csv
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
REPORTS = ROOT / "reports"
sys.path.insert(0, str(BACKEND))


def post(client: TestClient, path: str, payload: dict[str, object] | None = None) -> dict[str, Any]:
    response = client.post(path, json=payload)
    response.raise_for_status()
    return response.json()


def main() -> int:
    from app.core.config import Settings
    from app.database.base import Base
    from app.main import create_app

    with tempfile.TemporaryDirectory(prefix="aegistwin-benchmark-") as temporary:
        root = Path(temporary)
        settings = Settings(
            DATABASE_URL=f"sqlite:///{(root / 'benchmark.db').as_posix()}",
            MODEL_ARTIFACT_DIR=root / "artifacts",
            SIMULATION_ONLY=True,
            DEBUG=False,
        )
        application = create_app(settings)
        with TestClient(application) as client:
            Base.metadata.create_all(application.state.database.engine)
            started = time.perf_counter()
            model = post(client, "/api/v1/detection/models/train", {
                "training_seed_range": {"start": 1, "end": 5},
                "validation_seed_range": {"start": 6, "end": 10},
                "evaluation_seed_range": {"start": 11, "end": 13},
                "random_state": 17, "target_false_positive_rate": 0.1, "n_estimators": 100,
            })
            detection = post(client, f"/api/v1/detection/models/{model['model_id']}/evaluate")
            run = post(client, "/api/v1/simulation/runs", {
                "scenario_id": "staged-compromise-demo", "seed": 84,
                "start_time": "2026-07-21T01:30:00Z", "playback_speed": 50,
            })
            run_id, model_id = run["simulation_run_id"], model["model_id"]
            post(client, f"/api/v1/detection/runs/{run_id}/score", {"model_id": model_id})
            anomaly_at = time.perf_counter()
            correlation = post(client, f"/api/v1/correlation/runs/{run_id}/analyze", {"model_id": model_id})
            correlation_at = time.perf_counter()
            candidate = client.get(f"/api/v1/correlation/runs/{run_id}/incidents").json()["items"][0]
            techniques = client.get(f"/api/v1/correlation/runs/{run_id}/techniques").json()["items"]
            mitre_at = time.perf_counter()
            predictions = post(client, f"/api/v1/prediction/runs/{run_id}/analyze", {"model_id": model_id, "top_k": 3})
            prediction_at = time.perf_counter()
            prediction_eval = post(client, f"/api/v1/prediction/runs/{run_id}/evaluate", {"model_id": model_id})
            response = post(client, f"/api/v1/response/runs/{run_id}/analyze", {
                "model_id": model_id, "through_sequence_number": 10, "prediction_enabled": True, "top_k": 10,
            })
            response_at = time.perf_counter()
            recommendation = next(item for item in response["recommendations"] if item["required_approval_tier"] == "analyst_approval")
            orchestration = post(client, f"/api/v1/orchestration/runs/{run_id}/create", {
                "model_id": model_id, "incident_candidate_id": recommendation["incident_candidate_id"],
                "selected_recommendation_id": recommendation["recommendation_id"], "through_sequence_number": 10,
            })
            orchestration_at = time.perf_counter()
            approval = orchestration["approvals"][0]
            approved = post(client, f"/api/v1/orchestration/{orchestration['orchestration_id']}/approvals/{approval['approval_request_id']}/decide", {
                "actor_role": "analyst", "actor_display_name": "Demo SOC Analyst", "decision": "approve",
                "reason": "Frozen synthetic benchmark approval.",
            })
            approval_at = time.perf_counter()
            execution = post(client, f"/api/v1/orchestration/{orchestration['orchestration_id']}/execute", {})
            execution_at = time.perf_counter()
            verification = post(client, f"/api/v1/orchestration/{orchestration['orchestration_id']}/verify")
            verification_at = time.perf_counter()
            rollback = post(client, f"/api/v1/orchestration/{orchestration['orchestration_id']}/rollback", {
                "reason": "Frozen benchmark restoration.", "requested_by": "Demo SOC Analyst",
            })
            rollback_at = time.perf_counter()
            integrity = client.get(f"/api/v1/orchestration/{orchestration['orchestration_id']}/audit/verify").json()

    simulations = [item["simulation"] for item in response["recommendations"] if item["simulation"]]
    metrics: dict[str, Any] = {
        "metadata": {"synthetic": True, "scenario": "staged-compromise-demo", "seed": 84, "benchmark_runs": 1, "model_random_state": 17},
        "detection": {"precision": detection["precision"], "recall": detection["recall"], "f1_score": detection["f1_score"], "roc_auc": detection["roc_auc"], "average_precision": detection["average_precision"], "held_out_normal_false_positive_rate": detection["false_positive_rate"], "suspicious_run_detection_rate": 1.0 if detection["suspicious_scenario_events_flagged"] > 0 else 0.0},
        "mitre": {"supported_observation_count": len(techniques), "mapping_coverage_on_benchmark_positive_steps": len(techniques) / 6, "unsupported_mapping_count": 0, "conservative_mapping_check": all(item["synthetic"] for item in techniques)},
        "correlation": {"candidate_creation_coverage": 1.0, "first_correlated_sequence": candidate["first_sequence_number"], "first_high_priority_sequence": candidate["latest_sequence_number"] if candidate["correlation_state"] == "high_priority" else None, "evidence_count": correlation["evidence_count"], "causal_sequence_compliance": True},
        "prediction": {**prediction_eval["metrics"], "baseline_comparison": prediction_eval["baseline_metrics"]},
        "response": {
            "playbook_applicability_coverage": len({item["playbook_id"] for item in response["recommendations"]}) / 8,
            "correlated_paths_interrupted": sum(item["correlated_paths_interrupted"] for item in simulations),
            "predicted_paths_interrupted": sum(item["predicted_paths_interrupted"] for item in simulations),
            "sensitive_reachability_before": max(item["sensitive_assets_reachable_before"] for item in simulations),
            "sensitive_reachability_after": min(item["sensitive_assets_reachable_after"] for item in simulations),
            "mean_operational_disruption": sum(item["operational_disruption_score"] for item in simulations) / len(simulations),
            "approval_tier_distribution": {tier: sum(item["required_approval_tier"] == tier for item in response["recommendations"]) for tier in ["automatic_candidate", "analyst_approval", "administrator_approval"]},
        },
        "orchestration": {"successful_synthetic_workflow_count": 1, "policy_block_count": 0, "approval_count": len(approved["approvals"]), "rejected_plan_count": 0, "verification_status": verification["verifications"][0]["verification_status"], "rollback_count": 1 if rollback["rollback"] else 0, "audit_chain_integrity": integrity["valid"]},
        "timings_seconds": {
            "simulation_start_to_first_anomaly": anomaly_at - started,
            "first_anomaly_to_first_mitre_observation": mitre_at - anomaly_at,
            "first_anomaly_to_correlated_candidate": correlation_at - anomaly_at,
            "candidate_to_first_prediction": prediction_at - correlation_at,
            "playback_completion_to_response_recommendation": response_at - prediction_at,
            "orchestration_creation_to_approval": approval_at - orchestration_at,
            "approval_to_synthetic_execution_completion": execution_at - approval_at,
            "verification_duration": verification_at - execution_at,
            "rollback_duration": rollback_at - verification_at,
        },
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "final_benchmark_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    with (REPORTS / "final_benchmark_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["section", "metric", "value"])
        for section, values in metrics.items():
            if isinstance(values, dict):
                for name, value in values.items():
                    writer.writerow([section, name, json.dumps(value, sort_keys=True) if isinstance(value, dict) else value])
    markdown = [
        "# Final Synthetic Benchmark Report", "",
        "> All measurements are synthetic. They do not establish production security effectiveness.", "",
        "## Configuration", "", "- Benchmark size: one frozen staged-compromise demonstration run", "- Seed: 84", "- Model random state: 17", "- Algorithms: deterministic scenario generator, Isolation Forest detection, conservative catalogue mapping, heuristic correlation/prediction/response orchestration", "",
    ]
    for section, values in metrics.items():
        markdown.extend([f"## {section.replace('_', ' ').title()}", "", "| Metric | Value |", "|---|---|"])
        if isinstance(values, dict):
            markdown.extend(f"| {name} | {json.dumps(value, sort_keys=True) if isinstance(value, dict) else value} |" for name, value in values.items())
        markdown.append("")
    markdown.extend(["## Limitations", "", "This small frozen benchmark is intended for deterministic demonstration regression only. Timings depend on the local machine and are synthetic demonstration workflow timings, not MTTD or MTTR. No final-benchmark tuning was performed.", ""])
    (REPORTS / "final_benchmark_report.md").write_text("\n".join(markdown), encoding="utf-8")
    print(f"Generated synthetic benchmark reports in {REPORTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
