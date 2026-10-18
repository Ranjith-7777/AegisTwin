"""Train an IsolationForest on a benign recorded window and evaluate it on a
separate, labelled window.

Protocol (`network-flow-isolation-forest-v1`), fixed before any test data is
seen and never tuned against evaluation labels:

1. Training source must be a *different file* from the evaluation source.
   If it is labelled, every label must be BENIGN (e.g. CIC-IDS2017 Monday);
   labels are only checked, never used as features or for filtering.
2. Training flows are split chronologically: the first 80% fit the model,
   the last 20% are a held-out benign calibration window.
3. The alert threshold is the (1 - target_fpr) quantile of calibration
   anomaly scores - i.e. it is set from benign data alone.
4. The evaluation source's labels are used only to compute metrics after
   scoring: ROC-AUC, average precision, precision, recall, F1, FPR, the
   confusion matrix and per-label detection rates.

Very large training windows are deterministically thinned (every k-th flow,
in time order) to at most `MAX_FIT_ROWS`; this is recorded in the protocol.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid5

import joblib
import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, confusion_matrix, roc_auc_score
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import DataSourceRecord, NetworkFlowEvaluationRecord, NetworkFlowRecord
from app.ingestion.canonical import BENIGN_LABEL
from app.services.network_flow.features import (
    FEATURE_NAMES,
    FEATURE_SCHEMA_VERSION,
    FlowLike,
    flow_features,
)

MODEL_VERSION = "network-flow-isolation-forest-v1"
EVALUATION_NAMESPACE = UUID("4f0c1a2e-8f59-4c3c-9d5b-2a7b6e1f0d44")
MAX_FIT_ROWS = 200_000
CALIBRATION_FRACTION = 0.2
_BATCH = 20_000

FEATURE_COLUMNS = (
    NetworkFlowRecord.duration_s,
    NetworkFlowRecord.fwd_packets,
    NetworkFlowRecord.bwd_packets,
    NetworkFlowRecord.fwd_bytes,
    NetworkFlowRecord.bwd_bytes,
    NetworkFlowRecord.syn_count,
    NetworkFlowRecord.fin_count,
    NetworkFlowRecord.rst_count,
    NetworkFlowRecord.psh_count,
    NetworkFlowRecord.ack_count,
    NetworkFlowRecord.protocol,
    NetworkFlowRecord.dst_port,
)


class EvaluationRefused(ValueError):
    pass


@dataclass(frozen=True)
class EvaluationConfig:
    target_fpr: float = 0.01
    n_estimators: int = 200
    max_samples: int = 256
    random_state: int = 42


def _features_for(session: Session, source_id: str) -> NDArray[np.float64]:
    statement = (
        select(*FEATURE_COLUMNS)
        .where(NetworkFlowRecord.source_id == source_id)
        .order_by(NetworkFlowRecord.observed_at, NetworkFlowRecord.row_number)
        .execution_options(yield_per=_BATCH)
    )
    rows = [flow_features(row) for row in session.execute(statement)]
    if not rows:
        return np.zeros((0, len(FEATURE_NAMES)), dtype=np.float64)
    return np.asarray(rows, dtype=np.float64)


def _labels_for(session: Session, source_id: str) -> list[str | None]:
    statement = (
        select(NetworkFlowRecord.evaluation_label)
        .where(NetworkFlowRecord.source_id == source_id)
        .order_by(NetworkFlowRecord.observed_at, NetworkFlowRecord.row_number)
        .execution_options(yield_per=_BATCH)
    )
    return list(session.scalars(statement))


def _anomaly_scores(model: IsolationForest, matrix: NDArray[np.float64]) -> NDArray[np.float64]:
    # score_samples: higher = more normal. Negate so higher = more anomalous.
    return np.asarray(-model.score_samples(matrix), dtype=np.float64)


def binary_metrics(
    y_true: NDArray[np.int_], scores: NDArray[np.float64], threshold: float
) -> dict[str, object]:
    """Threshold-dependent and ranking metrics. Pure; unit-tested by hand."""

    y_pred = (scores >= threshold).astype(int)
    tn, fp, fn, tp = (
        int(value) for value in confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    )
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    both_classes = 0 < int(y_true.sum()) < len(y_true)
    return {
        "roc_auc": float(roc_auc_score(y_true, scores)) if both_classes else None,
        "average_precision": float(average_precision_score(y_true, scores))
        if both_classes
        else None,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": fp / (fp + tn) if fp + tn else None,
        "confusion_matrix": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "support": {"benign": tn + fp, "attack": tp + fn},
    }


def evaluate(
    session: Session,
    train_source_id: str,
    eval_source_id: str,
    artifact_dir: Path,
    config: EvaluationConfig | None = None,
) -> NetworkFlowEvaluationRecord:
    config = config or EvaluationConfig()
    if not 0 < config.target_fpr < 0.5:
        raise EvaluationRefused("target_fpr must be in (0, 0.5).")
    train = session.get(DataSourceRecord, train_source_id)
    test = session.get(DataSourceRecord, eval_source_id)
    if train is None or test is None:
        raise EvaluationRefused("Unknown training or evaluation source.")
    if train.file_sha256 == test.file_sha256:
        raise EvaluationRefused("Training and evaluation must be different recorded windows.")
    non_benign = {label for label in train.label_counts_json if label.upper() != BENIGN_LABEL}
    if non_benign:
        raise EvaluationRefused(
            "Training window must be benign-only; it contains labels: "
            + ", ".join(sorted(non_benign))
        )
    if not test.label_counts_json:
        raise EvaluationRefused("Evaluation window has no ground-truth labels.")

    protocol: dict[str, object] = {
        "model_version": MODEL_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "train_file_sha256": train.file_sha256,
        "eval_file_sha256": test.file_sha256,
        "calibration_fraction": CALIBRATION_FRACTION,
        "max_fit_rows": MAX_FIT_ROWS,
        "threshold_rule": "quantile(calibration_scores, 1 - target_fpr), benign data only",
        "labels_used_for": "metrics only (never features, filtering or thresholding)",
        **config.__dict__,
    }
    evaluation_id = str(
        uuid5(EVALUATION_NAMESPACE, json.dumps(protocol, sort_keys=True, default=str))
    )
    existing = session.get(NetworkFlowEvaluationRecord, evaluation_id)
    if existing is not None:
        return existing

    train_matrix = _features_for(session, train.source_id)
    if len(train_matrix) < 50:
        raise EvaluationRefused("Training window has too few flows (need at least 50).")
    split = int(len(train_matrix) * (1 - CALIBRATION_FRACTION))
    fit_rows, calibration_rows = train_matrix[:split], train_matrix[split:]
    stride = max(1, int(np.ceil(len(fit_rows) / MAX_FIT_ROWS)))
    fit_rows = fit_rows[::stride]

    model = IsolationForest(
        n_estimators=config.n_estimators,
        max_samples=min(config.max_samples, len(fit_rows)),
        random_state=config.random_state,
    ).fit(fit_rows)
    calibration_scores = _anomaly_scores(model, calibration_rows)
    threshold = float(np.quantile(calibration_scores, 1 - config.target_fpr))

    eval_matrix = _features_for(session, test.source_id)
    labels = _labels_for(session, test.source_id)
    labelled = np.asarray([label is not None for label in labels])
    y_true = np.asarray(
        [0 if (label or "").upper() == BENIGN_LABEL else 1 for label in labels], dtype=int
    )[labelled]
    scores = _anomaly_scores(model, eval_matrix)[labelled]
    metrics = binary_metrics(y_true, scores, threshold)

    per_label: dict[str, dict[str, float | int]] = {}
    label_array = np.asarray([label for label in labels if label is not None], dtype=object)
    for label, total in Counter(label_array.tolist()).items():
        flagged = int((scores[label_array == label] >= threshold).sum())
        per_label[str(label)] = {"flows": total, "flagged": flagged, "rate": flagged / total}

    metrics.update(
        {
            "threshold": threshold,
            "calibration_observed_fpr": float((calibration_scores >= threshold).mean()),
            "train_rows_fit": len(fit_rows),
            "train_rows_total": len(train_matrix),
            "calibration_rows": len(calibration_rows),
            "eval_rows": len(scores),
            "fit_stride": stride,
            "per_label": per_label,
        }
    )

    artifact_dir = artifact_dir / "network-flow"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact = artifact_dir / f"{evaluation_id}.joblib"
    joblib.dump({"model": model, "threshold": threshold, "protocol": protocol}, artifact)

    record = NetworkFlowEvaluationRecord(
        evaluation_id=evaluation_id,
        model_version=MODEL_VERSION,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        train_source_id=train.source_id,
        eval_source_id=test.source_id,
        protocol_json=protocol,
        metrics_json=metrics,
        artifact_path=artifact.name,
    )
    session.add(record)
    session.commit()
    return record


__all__ = ["EvaluationConfig", "EvaluationRefused", "FlowLike", "binary_metrics", "evaluate"]
