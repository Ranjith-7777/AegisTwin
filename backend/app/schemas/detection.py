from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Classification(StrEnum):
    NORMAL = "normal"
    ANOMALOUS = "anomalous"


class SeedRange(BaseModel):
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def ordered(self) -> SeedRange:
        if self.end < self.start:
            raise ValueError("seed range end must be greater than or equal to start")
        return self

    def values(self) -> range:
        return range(self.start, self.end + 1)


class DetectionTrainingRequest(BaseModel):
    training_seed_range: SeedRange = SeedRange(start=1, end=20)
    validation_seed_range: SeedRange = SeedRange(start=21, end=30)
    evaluation_seed_range: SeedRange = SeedRange(start=31, end=40)
    random_state: int = 42
    target_false_positive_rate: Annotated[float, Field(gt=0, lt=0.5)] = 0.02

    @model_validator(mode="after")
    def disjoint_splits(self) -> DetectionTrainingRequest:
        ranges = [
            set(self.training_seed_range.values()),
            set(self.validation_seed_range.values()),
            set(self.evaluation_seed_range.values()),
        ]
        if any(ranges[left] & ranges[right] for left in range(3) for right in range(left + 1, 3)):
            raise ValueError("training, validation, and evaluation seed ranges must be disjoint")
        return self


class DetectionModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_id: str
    model_type: str
    model_version: str
    feature_schema_version: str
    calibration_version: str
    artifact_path: str
    configuration_json: dict[str, object]
    dataset_fingerprint: str
    random_state: int
    target_false_positive_rate: float
    calibrated_threshold: float
    threshold_percentile: float
    training_event_count: int
    validation_event_count: int
    created_at: datetime
    synthetic: bool


class DetectionTrainingResult(BaseModel):
    model_id: str
    model_type: str
    feature_schema_version: str
    training_event_count: int
    validation_event_count: int
    dataset_fingerprint: str
    calibrated_threshold: float
    target_false_positive_rate: float
    synthetic: bool


class RunScoringRequest(BaseModel):
    model_id: str
    force_rescore: bool = False


class RunScoringResult(BaseModel):
    model_id: str
    simulation_run_id: str
    assessment_count: int
    anomalous_count: int
    force_rescore: bool
    synthetic: bool


class AnomalyAssessment(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    assessment_id: str
    model_id: str
    simulation_run_id: str
    event_id: str
    sequence_number: int
    event_type: str | None = None
    source_id: str | None = None
    user_id: str | None = None
    raw_score: float
    anomaly_score: float
    threshold: float
    classification: Classification
    contributing_signals: list[str]
    scored_at: datetime
    synthetic: bool


class AnomalyAssessmentPage(BaseModel):
    items: list[AnomalyAssessment]
    page: int
    page_size: int
    total: int
    pages: int


class ModelEvaluation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evaluation_id: str
    model_id: str
    configuration_json: dict[str, object]
    normal_event_count: int
    suspicious_scenario_event_count: int
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    precision: float
    recall: float
    f1_score: float
    false_positive_rate: float
    roc_auc: float | None
    average_precision: float | None
    event_level_detection_coverage: float
    normal_events_incorrectly_flagged: int
    suspicious_scenario_events_flagged: int
    baseline_metrics: dict[str, object]
    created_at: datetime
    synthetic: bool
