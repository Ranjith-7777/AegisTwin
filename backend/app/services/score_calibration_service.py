from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from math import floor, nextafter

CALIBRATION_VERSION = "normal-only-comparison-v2"
SUPPORTED_METHODS = (
    "empirical-quantile-v2",
    "interpolated-ecdf-v2",
    "validation-fp-count-v2",
)


@dataclass(frozen=True)
class CalibrationCandidate:
    method: str
    raw_threshold: float
    normalised_threshold: float
    validation_false_positive_count: int
    validation_false_positive_rate: float
    ties_at_threshold: int


@dataclass(frozen=True)
class CalibrationResult:
    reference_scores: list[float]
    selected: CalibrationCandidate
    candidates: dict[str, CalibrationCandidate]


class ScoreCalibrationService:
    def compare(
        self,
        training_values: list[float],
        validation_values: list[float],
        target_false_positive_rate: float,
        selected_method: str,
    ) -> CalibrationResult:
        if selected_method not in SUPPORTED_METHODS:
            raise ValueError(f"Unsupported calibration method: {selected_method}")
        reference = sorted(training_values + validation_values)
        ordered = sorted(validation_values)
        percentile = 1 - target_false_positive_rate
        higher_index = min(len(ordered) - 1, max(0, int(percentile * len(ordered))))
        higher_threshold = ordered[higher_index]
        position = percentile * (len(ordered) - 1)
        lower_index = floor(position)
        upper_index = min(len(ordered) - 1, lower_index + 1)
        fraction = position - lower_index
        interpolated_threshold = (
            ordered[lower_index] * (1 - fraction) + ordered[upper_index] * fraction
        )
        allowed = floor(target_false_positive_rate * len(ordered))
        count_threshold = self._count_threshold(ordered, allowed)
        thresholds = {
            "empirical-quantile-v2": higher_threshold,
            "interpolated-ecdf-v2": interpolated_threshold,
            "validation-fp-count-v2": count_threshold,
        }
        candidates = {
            method: self._candidate(method, threshold, validation_values, reference)
            for method, threshold in thresholds.items()
        }
        return CalibrationResult(
            reference_scores=reference,
            selected=candidates[selected_method],
            candidates=candidates,
        )

    def normalise(self, value: float, reference: list[float]) -> float:
        if not reference:
            return 0.0
        left = bisect_left(reference, value)
        right = bisect_right(reference, value)
        if left != right:
            return min(1.0, max(0.0, ((left + right) / 2) / len(reference)))
        if left == 0:
            return 0.0
        if left == len(reference):
            return 1.0
        low = reference[left - 1]
        high = reference[left]
        fraction = 0.0 if high == low else (value - low) / (high - low)
        return min(1.0, max(0.0, ((left - 0.5) + fraction) / len(reference)))

    @staticmethod
    def _count_threshold(ordered: list[float], allowed: int) -> float:
        if allowed <= 0:
            return nextafter(ordered[-1], float("inf"))
        for threshold in sorted(set(ordered)):
            if sum(value >= threshold for value in ordered) <= allowed:
                return threshold
        return nextafter(ordered[-1], float("inf"))

    def _candidate(
        self, method: str, threshold: float, validation: list[float], reference: list[float]
    ) -> CalibrationCandidate:
        false_positives = sum(value >= threshold for value in validation)
        return CalibrationCandidate(
            method=method,
            raw_threshold=threshold,
            normalised_threshold=self.normalise(threshold, reference),
            validation_false_positive_count=false_positives,
            validation_false_positive_rate=false_positives / len(validation),
            ties_at_threshold=sum(value == threshold for value in validation),
        )


score_calibration_service = ScoreCalibrationService()
