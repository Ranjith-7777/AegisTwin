"""Portable resolution of detection-model artifact files.

``MODEL_ARTIFACT_DIR`` is the single authority for where model artifacts
live. The database stores only an artifact's *file name*; the directory is
supplied at runtime. This keeps persisted records valid when the repository
is moved, cloned onto another laptop, or mounted into a container at a
different path.

Legacy records written before this change stored an absolute,
machine-specific path (for example ``D:\\AegisArena\\artifacts\\models\\x.joblib``).
:func:`artifact_file_name` strips any directory component - Windows or POSIX
separators alike - so those records resolve under the current directory too.

The active directory is installed once at application startup (see
``app.main.create_app``), mirroring the process-wide registry pattern used by
``app.events.registry``. Code running outside an application (scripts,
Alembic) falls back to the configured settings value.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import get_settings

_artifact_dir: Path | None = None
_SEPARATORS = re.compile(r"[\\/]")


def set_model_artifact_dir(directory: Path) -> None:
    global _artifact_dir
    _artifact_dir = directory.resolve()


def get_model_artifact_dir() -> Path:
    if _artifact_dir is not None:
        return _artifact_dir
    return get_settings().model_artifact_dir.resolve()


def artifact_file_name(stored_path: str) -> str:
    """Return only the file-name component of a stored artifact path."""

    name = _SEPARATORS.split(stored_path.strip())[-1]
    if not name or name in {".", ".."}:
        raise ValueError("Stored artifact path does not contain a file name")
    return name


def resolve_artifact_path(stored_path: str) -> Path:
    """Resolve a stored artifact reference under the authoritative directory."""

    return get_model_artifact_dir() / artifact_file_name(stored_path)
