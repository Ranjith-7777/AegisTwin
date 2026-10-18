"""AegisArena canonical flow format (CSV or JSON Lines/array).

A deliberately boring, documented interchange format so any flow exporter
(Zeek conn.log converters, NetFlow/IPFIX collectors, cloud VPC flow-log
exports) can be brought in with a small conversion script instead of a new
adapter. Field names equal `CanonicalFlow` attributes; see
docs/REAL_DATA_INGESTION.md for the full contract.

Strictness: `observed_at` must be ISO-8601 *with* a UTC offset (no guessed
timezones), every count must be a non-negative integer, and unknown labels
are kept verbatim. `evaluation_label` is optional.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterator, Mapping
from datetime import datetime
from pathlib import Path

from app.ingestion.canonical import CanonicalFlow
from app.ingestion.validation import (
    RowRejected,
    optional_rate,
    require_float,
    require_int,
    require_ip,
    require_port,
)

ADAPTER_NAME = "canonical"
REQUIRED_FIELDS = (
    "observed_at",
    "src_ip",
    "src_port",
    "dst_ip",
    "dst_port",
    "protocol",
    "duration_s",
    "fwd_packets",
    "bwd_packets",
    "fwd_bytes",
    "bwd_bytes",
)
OPTIONAL_COUNTS = ("syn_count", "fin_count", "rst_count", "psh_count", "ack_count")


class UnsupportedCanonicalLayout(ValueError):
    pass


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as error:
        raise RowRejected("invalid_timestamp", value[:40]) from error
    if parsed.tzinfo is None:
        raise RowRejected("timestamp_without_offset", value[:40])
    return parsed


def _text(record: Mapping[str, object], name: str) -> str:
    value = record.get(name)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise RowRejected(f"missing_{name}")
    return str(value)


def to_flow(row_number: int, record: Mapping[str, object]) -> CanonicalFlow:
    counts = {
        name: require_int(str(record[name]), name) if record.get(name) not in (None, "") else 0
        for name in OPTIONAL_COUNTS
    }
    label = record.get("evaluation_label")
    return CanonicalFlow(
        row_number=row_number,
        observed_at=_timestamp(_text(record, "observed_at")),
        src_ip=require_ip(_text(record, "src_ip"), "src_ip"),
        src_port=require_port(_text(record, "src_port"), "src_port"),
        dst_ip=require_ip(_text(record, "dst_ip"), "dst_ip"),
        dst_port=require_port(_text(record, "dst_port"), "dst_port"),
        protocol=require_int(_text(record, "protocol"), "protocol"),
        duration_s=require_float(_text(record, "duration_s"), "duration"),
        fwd_packets=require_int(_text(record, "fwd_packets"), "fwd_packets"),
        bwd_packets=require_int(_text(record, "bwd_packets"), "bwd_packets"),
        fwd_bytes=require_int(_text(record, "fwd_bytes"), "fwd_bytes"),
        bwd_bytes=require_int(_text(record, "bwd_bytes"), "bwd_bytes"),
        syn_count=counts["syn_count"],
        fin_count=counts["fin_count"],
        rst_count=counts["rst_count"],
        psh_count=counts["psh_count"],
        ack_count=counts["ack_count"],
        flow_bytes_per_s=optional_rate(str(record.get("flow_bytes_per_s") or "")),
        flow_packets_per_s=optional_rate(str(record.get("flow_packets_per_s") or "")),
        evaluation_label=" ".join(str(label).split()) or None if label not in (None, "") else None,
    )


def read_rows(path: Path) -> Iterator[CanonicalFlow | RowRejected]:
    if path.suffix.lower() in {".json", ".jsonl", ".ndjson"}:
        yield from _read_json(path)
        return
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [name for name in REQUIRED_FIELDS if name not in (reader.fieldnames or [])]
        if missing:
            raise UnsupportedCanonicalLayout(f"Missing canonical columns: {', '.join(missing)}")
        for row_number, row in enumerate(reader, start=2):
            try:
                yield to_flow(row_number, row)
            except RowRejected as rejected:
                yield rejected


def _read_json(path: Path) -> Iterator[CanonicalFlow | RowRejected]:
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("["):
        try:
            records = json.loads(stripped)
        except json.JSONDecodeError as error:
            raise UnsupportedCanonicalLayout(f"Invalid JSON array: {error}") from error
        lines: list[tuple[int, object]] = list(enumerate(records, start=1))
    else:
        lines = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                lines.append((line_number, json.loads(line)))
            except json.JSONDecodeError:
                lines.append((line_number, None))
    for row_number, record in lines:
        if not isinstance(record, dict):
            yield RowRejected("invalid_json_record", f"record {row_number}")
            continue
        try:
            yield to_flow(row_number, record)
        except RowRejected as rejected:
            yield rejected
