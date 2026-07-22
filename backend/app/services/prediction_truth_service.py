"""Evaluation-only truth; never imported by the predictor."""

from typing import TypedDict


class PredictionTruth(TypedDict):
    technique: str
    tactic: str
    asset: str
    objective: str
    observed_sequence: int


TRUTH_MANIFEST_VERSION = "staged-demo-next-step-v1"
STAGED_DEMO_TRUTH: dict[int, PredictionTruth] = {
    5: {
        "technique": "T1078",
        "tactic": "Initial Access",
        "asset": "authentication-server-01",
        "objective": "maintain_access",
        "observed_sequence": 6,
    },
    6: {
        "technique": "T1098",
        "tactic": "Persistence",
        "asset": "examination-portal-01",
        "objective": "expand_access",
        "observed_sequence": 8,
    },
    8: {
        "technique": "T1021",
        "tactic": "Lateral Movement",
        "asset": "application-server-01",
        "objective": "reach_sensitive_resource",
        "observed_sequence": 9,
    },
    10: {
        "technique": "T1567",
        "tactic": "Exfiltration",
        "asset": "simulation-egress-sink-01",
        "objective": "transfer_data",
        "observed_sequence": 11,
    },
}
