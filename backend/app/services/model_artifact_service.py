from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import joblib
from sklearn.pipeline import Pipeline

from app.services.feature_pipeline_service import FeatureBaselines


@dataclass
class DetectionArtifact:
    pipeline: Pipeline
    baselines: FeatureBaselines
    calibration_scores: list[float]
    calibrated_threshold: float
    feature_schema_version: str
    calibration_version: str


class ModelArtifactService:
    def save(self, directory: Path, model_id: str, artifact: DetectionArtifact) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{model_id}.joblib"
        joblib.dump(artifact, path)
        return path.resolve()

    def load(self, path: str) -> DetectionArtifact:
        artifact = joblib.load(path)
        if not isinstance(artifact, DetectionArtifact):
            raise ValueError("Persisted detection artifact has an unexpected type")
        return artifact


model_artifact_service = ModelArtifactService()
