from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path
from threading import RLock

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
    calibration_method: str
    raw_threshold: float
    pure_isolation_reference: list[float]
    pure_isolation_raw_threshold: float
    hybrid_weights: dict[str, float]
    use_hybrid_score: bool
    calibration_candidates: dict[str, dict[str, float | int | str]]


class ModelArtifactService:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[int, DetectionArtifact]] = {}
        self._lock = RLock()

    def save(self, directory: Path, model_id: str, artifact: DetectionArtifact) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{model_id}.joblib"
        # Write to a temporary sibling and atomically replace, so a concurrent
        # reader (or a concurrent deterministic rebuild) never observes a
        # half-written artifact.
        temporary = directory / f".{model_id}.{os.getpid()}.{threading.get_ident()}.tmp"
        with self._lock:
            joblib.dump(artifact, temporary)
            os.replace(temporary, path)
        return path.resolve()

    def load(self, path: str) -> DetectionArtifact:
        resolved = str(Path(path).resolve())
        modified = Path(resolved).stat().st_mtime_ns
        with self._lock:
            cached = self._cache.get(resolved)
            if cached is not None and cached[0] == modified:
                return cached[1]
        artifact = joblib.load(resolved)
        if not isinstance(artifact, DetectionArtifact):
            raise ValueError("Persisted detection artifact has an unexpected type")
        with self._lock:
            self._cache[resolved] = (modified, artifact)
        return artifact

    def clear_cache(self) -> None:
        """Clear the process-local cache; primarily used for test isolation."""
        with self._lock:
            self._cache.clear()


model_artifact_service = ModelArtifactService()
