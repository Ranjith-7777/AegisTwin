"""Real-dataset acceptance: CIC-IDS2017 Monday (benign) -> Tuesday (FTP/SSH
brute force). Skipped - and reported as BLOCKED - unless the real labelled-flow
CSVs are present locally. They are never committed (datasets/raw is
git-ignored) and AegisArena does not download them for you.

    datasets/raw/cicids2017/Monday-WorkingHours.pcap_ISCX.csv
    datasets/raw/cicids2017/Tuesday-WorkingHours.pcap_ISCX.csv

Override the folder with CICIDS2017_DIR. Assertions are sanity checks on the
pipeline (layout accepted, labels where the dataset documents them, metrics
computed, better than random ranking) - not performance targets tuned to
the test labels.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ingestion.importer import import_file
from app.services.network_flow.correlation_service import correlate
from app.services.network_flow.evaluation_service import evaluate

DATA_DIR = Path(
    os.environ.get(
        "CICIDS2017_DIR", Path(__file__).resolve().parents[2] / "datasets" / "raw" / "cicids2017"
    )
)
MONDAY = DATA_DIR / "Monday-WorkingHours.pcap_ISCX.csv"
TUESDAY = DATA_DIR / "Tuesday-WorkingHours.pcap_ISCX.csv"

pytestmark = pytest.mark.skipif(
    not (MONDAY.is_file() and TUESDAY.is_file()),
    reason=f"BLOCKED: CIC-IDS2017 labelled-flow CSVs not found in {DATA_DIR}",
)


def test_cicids2017_monday_to_tuesday(client: TestClient, tmp_path: Path) -> None:
    session = cast(Session, cast(FastAPI, client.app).state.database.session_factory())
    try:
        monday = import_file(session, MONDAY, "cicids2017", "acceptance").source
        tuesday = import_file(session, TUESDAY, "cicids2017", "acceptance").source
        for source in (monday, tuesday):
            assert source.rows_accepted > 100_000
            assert source.rows_read == (
                source.rows_accepted + source.rows_rejected + source.rows_duplicate
            )
        assert set(monday.label_counts_json) == {"BENIGN"}
        assert {"FTP-Patator", "SSH-Patator"} <= set(tuesday.label_counts_json)

        record = evaluate(session, monday.source_id, tuesday.source_id, tmp_path)
        metrics = record.metrics_json
        for key in ("roc_auc", "average_precision", "precision", "recall", "f1"):
            assert metrics[key] is not None
        assert cast(float, metrics["roc_auc"]) > 0.5

        findings = correlate(session, tuesday.source_id)
        report = {
            "monday": {
                "accepted": monday.rows_accepted,
                "rejected": monday.rejection_reasons_json,
                "duplicates": monday.rows_duplicate,
                "unmapped": monday.rows_unmapped,
            },
            "tuesday": {
                "accepted": tuesday.rows_accepted,
                "rejected": tuesday.rejection_reasons_json,
                "duplicates": tuesday.rows_duplicate,
                "unmapped": tuesday.rows_unmapped,
                "labels": tuesday.label_counts_json,
            },
            "metrics": metrics,
            "findings_by_rule": {
                rule: sum(1 for item in findings if item.rule == rule)
                for rule in sorted({item.rule for item in findings})
            },
        }
        print("\nCICIDS2017_ACCEPTANCE " + json.dumps(report, default=str))
    finally:
        session.close()
