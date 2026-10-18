"""Strict field validation shared by the adapters.

Each helper raises `RowRejected` with a stable, countable reason code, so an
import report can say exactly why rows were dropped instead of silently
coercing bad values. Nothing here guesses: a value that is not cleanly
parseable rejects the row.
"""

from __future__ import annotations

import ipaddress
import math


class RowRejected(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


def require_ip(value: str, field: str) -> str:
    candidate = value.strip()
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError as error:
        raise RowRejected(f"invalid_{field}", candidate[:40]) from error


def require_port(value: str, field: str) -> int:
    number = require_int(value, field)
    if not 0 <= number <= 65535:
        raise RowRejected(f"invalid_{field}", str(number))
    return number


def require_int(value: str, field: str, minimum: int = 0) -> int:
    candidate = value.strip()
    try:
        number = int(candidate)
    except ValueError:
        # CIC writes some integer counters as "12.0".
        try:
            as_float = float(candidate)
        except ValueError as error:
            raise RowRejected(f"invalid_{field}", candidate[:40]) from error
        if not math.isfinite(as_float) or not as_float.is_integer():
            raise RowRejected(f"invalid_{field}", candidate[:40]) from None
        number = int(as_float)
    if number < minimum:
        raise RowRejected(f"negative_{field}", str(number))
    return number


def require_float(value: str, field: str, minimum: float = 0.0) -> float:
    candidate = value.strip()
    try:
        number = float(candidate)
    except ValueError as error:
        raise RowRejected(f"invalid_{field}", candidate[:40]) from error
    if not math.isfinite(number):
        raise RowRejected(f"non_finite_{field}", candidate[:40])
    if number < minimum:
        raise RowRejected(f"negative_{field}", candidate[:40])
    return number


def optional_rate(value: str) -> float | None:
    """CIC derived rates are `Infinity`/`NaN` for zero-duration flows. They
    are recomputable from duration/bytes, so a non-finite rate becomes
    None (counted in the report) rather than rejecting an otherwise valid
    flow - and is never replaced by an invented number."""

    candidate = value.strip()
    try:
        number = float(candidate)
    except ValueError:
        return None
    if not math.isfinite(number) or number < 0:
        return None
    return number
