"""Canonical network-flow record shared by every ingestion adapter.

Every adapter (CIC-IDS2017 labelled flows, the canonical CSV/JSON format)
normalises its input into `CanonicalFlow`. Detection, correlation and
reporting only ever read canonical fields, so a new source needs an adapter,
never changes downstream.

`evaluation_label` is carried for *evaluation only*. It is never a model
feature (see `app/services/network_flow/features.py`, which has a guard test)
and never drives correlation rules.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SourceKind(StrEnum):
    """Where telemetry comes from. Only `replay` is importable today."""

    # AegisArena's own deterministic scenario engine.
    SYNTHETIC = "synthetic"
    # A recorded, labelled public dataset replayed from files - never live.
    REPLAY = "replay"
    # Read-only live telemetry. Declared so the safety contract is explicit;
    # no live collector is implemented (see docs/REAL_DATA_INGESTION.md).
    LIVE_READONLY = "live_readonly"


BENIGN_LABEL = "BENIGN"


@dataclass(frozen=True)
class CanonicalFlow:
    row_number: int
    observed_at: datetime
    src_ip: str
    src_port: int
    dst_ip: str
    dst_port: int
    protocol: int
    duration_s: float
    fwd_packets: int
    bwd_packets: int
    fwd_bytes: int
    bwd_bytes: int
    syn_count: int
    fin_count: int
    rst_count: int
    psh_count: int
    ack_count: int
    flow_bytes_per_s: float | None
    flow_packets_per_s: float | None
    # Evaluation-only ground truth; None when the source is unlabelled.
    evaluation_label: str | None
    timestamp_adjusted: bool = False

    @property
    def is_attack(self) -> bool | None:
        if self.evaluation_label is None:
            return None
        return self.evaluation_label.upper() != BENIGN_LABEL

    def fingerprint(self) -> str:
        """Content identity used for de-duplication. Deliberately excludes
        `row_number` (CIC files contain byte-identical repeated rows) and
        the label (a relabelled duplicate is still the same flow)."""

        material = "|".join(
            str(value)
            for value in (
                self.observed_at.isoformat(),
                self.src_ip,
                self.src_port,
                self.dst_ip,
                self.dst_port,
                self.protocol,
                repr(self.duration_s),
                self.fwd_packets,
                self.bwd_packets,
                self.fwd_bytes,
                self.bwd_bytes,
                self.syn_count,
                self.fin_count,
                self.rst_count,
                self.psh_count,
                self.ack_count,
            )
        )
        return hashlib.sha256(material.encode()).hexdigest()
