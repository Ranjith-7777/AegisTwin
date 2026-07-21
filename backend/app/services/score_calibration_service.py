from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from math import ceil

CALIBRATION_VERSION = "empirical-normal-cdf-v1"


@dataclass(frozen=True)
class CalibrationResult:
    reference_scores: list[float]
    raw_threshold: float
    normalised_threshold: float
    threshold_percentile: float


class ScoreCalibrationService:
    def calibrate(
        self,
        training_anomaly_values: list[float],
        validation_anomaly_values: list[float],
        target_false_positive_rate: float,
    ) -> CalibrationResult:
        reference = sorted(training_anomaly_values + validation_anomaly_values)
        ordered_validation = sorted(validation_anomaly_values)
        percentile = 1 - target_false_positive_rate
        threshold_index = min(
            len(ordered_validation) - 1,
            ceil(percentile * len(ordered_validation)) - 1,
        )
        raw_threshold = ordered_validation[threshold_index]
        return CalibrationResult(
            reference_scores=reference,
            raw_threshold=raw_threshold,
            normalised_threshold=self.normalise(raw_threshold, reference),
            threshold_percentile=percentile,
        )

    @staticmethod
    def normalise(anomaly_value: float, reference: list[float]) -> float:
        position = bisect_right(reference, anomaly_value)
        return min(1.0, max(0.0, position / max(1, len(reference))))


score_calibration_service = ScoreCalibrationService()
