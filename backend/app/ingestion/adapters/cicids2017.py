"""CIC-IDS2017 labelled-flow adapter (CICFlowMeter "TrafficLabelling" CSVs).

Expects the *labelled-flow* CSVs (they carry Flow ID, Source/Destination IP
and port, and Timestamp). The "MachineLearningCVE" CSVs drop those columns
and are rejected with a clear error, because flows without endpoints cannot
be mapped onto the twin or correlated.

Dataset quirks handled explicitly (each counted in the import report):

* Header names carry leading spaces and one duplicate ("Fwd Header Length");
  columns are matched by stripped name, first occurrence wins.
* `Flow Bytes/s` / `Flow Packets/s` are `Infinity`/`NaN` for zero-duration
  flows -> stored as NULL, never replaced with an invented value.
* Timestamps are day/month/year, minute or second resolution, and the
  afternoon hours are written on a 12-hour clock without AM/PM (e.g. 13:05
  appears as "1:05"). Capture ran during the working day (about 08:00-18:00),
  so an hour of 1-7 is read as afternoon (+12h) and flagged
  `timestamp_adjusted`. Explicit AM/PM, when present, is honoured instead.
* Times are testbed-local. The testbed was in New Brunswick, Canada, in July
  (Atlantic Daylight Time, UTC-03:00); that offset is an assumption recorded
  in the source provenance, not a value read from the file.

Reference: Sharafaldin, Lashkari, Ghorbani, "Toward Generating a New
Intrusion Detection Dataset and Intrusion Traffic Characterization",
ICISSP 2018. Dataset terms: https://www.unb.ca/cic/datasets/ids-2017.html
"""

from __future__ import annotations

import csv
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
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

ADAPTER_NAME = "cicids2017"
DATASET_NAME = "CIC-IDS2017"
LICENCE = (
    "Canadian Institute for Cybersecurity (UNB): redistribution, republication and "
    "mirroring are permitted with citation to the dataset and ICISSP 2018 paper. "
    "Not redistributed by AegisArena."
)
CITATION = (
    "Iman Sharafaldin, Arash Habibi Lashkari, Ali A. Ghorbani. Toward Generating a New "
    "Intrusion Detection Dataset and Intrusion Traffic Characterization. ICISSP 2018."
)
ASSUMED_UTC_OFFSET = timezone(timedelta(hours=-3), "ADT")
TIMEZONE_NOTE = "Testbed-local timestamps interpreted as ADT (UTC-03:00) - assumption."

REQUIRED_COLUMNS = (
    "Source IP",
    "Source Port",
    "Destination IP",
    "Destination Port",
    "Protocol",
    "Timestamp",
    "Flow Duration",
    "Total Fwd Packets",
    "Total Backward Packets",
    "Total Length of Fwd Packets",
    "Total Length of Bwd Packets",
    "Flow Bytes/s",
    "Flow Packets/s",
    "FIN Flag Count",
    "SYN Flag Count",
    "RST Flag Count",
    "PSH Flag Count",
    "ACK Flag Count",
    "Label",
)

_FORMATS_24H = ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M")
_FORMATS_12H = ("%d/%m/%Y %I:%M:%S %p", "%d/%m/%Y %I:%M %p")


class UnsupportedLayout(ValueError):
    """The file is not a CIC-IDS2017 labelled-flow CSV."""


def parse_timestamp(value: str) -> tuple[datetime, bool]:
    candidate = " ".join(value.split())
    for pattern in _FORMATS_12H:
        try:
            return datetime.strptime(candidate, pattern).replace(tzinfo=ASSUMED_UTC_OFFSET), False
        except ValueError:
            continue
    for pattern in _FORMATS_24H:
        try:
            parsed = datetime.strptime(candidate, pattern)
        except ValueError:
            continue
        if 1 <= parsed.hour <= 7:
            return (parsed + timedelta(hours=12)).replace(tzinfo=ASSUMED_UTC_OFFSET), True
        return parsed.replace(tzinfo=ASSUMED_UTC_OFFSET), False
    raise RowRejected("invalid_timestamp", candidate[:40])


def _column_index(header: list[str]) -> dict[str, int]:
    index: dict[str, int] = {}
    for position, raw in enumerate(header):
        name = raw.strip().lstrip("﻿")
        index.setdefault(name, position)
    missing = [column for column in REQUIRED_COLUMNS if column not in index]
    if missing:
        hint = (
            " This looks like a MachineLearningCVE file; use the labelled-flow "
            "(TrafficLabelling / GeneratedLabelledFlows) CSVs, which keep IPs and timestamps."
            if "Source IP" in missing and "Flow Duration" in index
            else ""
        )
        raise UnsupportedLayout(f"Missing CIC-IDS2017 columns: {', '.join(missing)}.{hint}")
    return index


def _label(value: str) -> str:
    # Thursday's web-attack labels contain a mis-encoded dash; normalise
    # whitespace and the replacement character so labels compare cleanly.
    cleaned = value.replace("�", "-").replace("\x96", "-")
    return " ".join(cleaned.split()) or "UNLABELLED"


def read_rows(path: Path) -> Iterator[CanonicalFlow | RowRejected]:
    """Yield one canonical flow, or the reason it was rejected, per data row.
    Raises `UnsupportedLayout` before yielding anything if the header is not
    a labelled-flow layout."""

    # latin-1 never fails to decode, so an odd byte becomes a visible label
    # problem rather than aborting a 500k-row import.
    with path.open(newline="", encoding="latin-1") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as error:
            raise UnsupportedLayout("The file is empty.") from error
        columns = _column_index(header)
        width = len(header)
        for row_number, row in enumerate(reader, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue
            if len(row) < width:
                yield RowRejected("truncated_row", f"row {row_number}")
                continue
            try:
                yield _flow(row_number, row, columns)
            except RowRejected as rejected:
                yield rejected


def _flow(row_number: int, row: list[str], columns: dict[str, int]) -> CanonicalFlow:
    def cell(name: str) -> str:
        return row[columns[name]]

    observed_at, adjusted = parse_timestamp(cell("Timestamp"))
    # Flow Duration is in microseconds.
    duration_s = require_float(cell("Flow Duration"), "duration") / 1_000_000
    return CanonicalFlow(
        row_number=row_number,
        observed_at=observed_at,
        src_ip=require_ip(cell("Source IP"), "src_ip"),
        src_port=require_port(cell("Source Port"), "src_port"),
        dst_ip=require_ip(cell("Destination IP"), "dst_ip"),
        dst_port=require_port(cell("Destination Port"), "dst_port"),
        protocol=require_int(cell("Protocol"), "protocol"),
        duration_s=duration_s,
        fwd_packets=require_int(cell("Total Fwd Packets"), "fwd_packets"),
        bwd_packets=require_int(cell("Total Backward Packets"), "bwd_packets"),
        fwd_bytes=require_int(cell("Total Length of Fwd Packets"), "fwd_bytes"),
        bwd_bytes=require_int(cell("Total Length of Bwd Packets"), "bwd_bytes"),
        syn_count=require_int(cell("SYN Flag Count"), "syn_count"),
        fin_count=require_int(cell("FIN Flag Count"), "fin_count"),
        rst_count=require_int(cell("RST Flag Count"), "rst_count"),
        psh_count=require_int(cell("PSH Flag Count"), "psh_count"),
        ack_count=require_int(cell("ACK Flag Count"), "ack_count"),
        flow_bytes_per_s=optional_rate(cell("Flow Bytes/s")),
        flow_packets_per_s=optional_rate(cell("Flow Packets/s")),
        evaluation_label=_label(cell("Label")),
        timestamp_adjusted=adjusted,
    )
