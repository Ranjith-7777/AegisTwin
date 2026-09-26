from __future__ import annotations

from dataclasses import dataclass

from app.schemas.telemetry import TelemetryEvent


@dataclass(frozen=True)
class SyntheticBenchmarkLabel:
    scenario_id: str
    scenario_step: int
    anomalous: bool
    rationale: str
    synthetic: bool = True


CREDENTIAL_COMPROMISE_TRUTH: tuple[SyntheticBenchmarkLabel, ...] = (
    SyntheticBenchmarkLabel(
        "credential-compromise", 1, True, "Repeated failed synthetic authentication."
    ),
    SyntheticBenchmarkLabel(
        "credential-compromise", 2, True, "Successful authentication at an unusual hour."
    ),
    SyntheticBenchmarkLabel(
        "credential-compromise", 3, True, "Previously unseen synthetic device activity."
    ),
    SyntheticBenchmarkLabel(
        "credential-compromise", 4, True, "Synthetic privilege-level transition."
    ),
    SyntheticBenchmarkLabel(
        "credential-compromise", 5, False, "Routine application access in scenario context."
    ),
    SyntheticBenchmarkLabel(
        "credential-compromise", 6, True, "Unexpected synthetic infrastructure relationship."
    ),
    SyntheticBenchmarkLabel(
        "credential-compromise", 7, True, "Unusually large transfer to a simulation sink."
    ),
)


class EvaluationTruthService:
    def __init__(self) -> None:
        self._labels = {
            (label.scenario_id, label.scenario_step): label for label in CREDENTIAL_COMPROMISE_TRUTH
        }

    def event_label(self, event: TelemetryEvent) -> int:
        if event.scenario_id == "normal-operations":
            return 0
        step_value = event.metadata.get("scenario_step", 0)
        step = step_value if isinstance(step_value, int) else 0
        label = self._labels.get((event.scenario_id, step))
        return int(label.anomalous) if label else 0

    @staticmethod
    def scenario_membership_label(event: TelemetryEvent) -> int:
        return int(event.scenario_id == "credential-compromise")

    def manifest(self) -> list[SyntheticBenchmarkLabel]:
        return list(CREDENTIAL_COMPROMISE_TRUTH)


evaluation_truth_service = EvaluationTruthService()
