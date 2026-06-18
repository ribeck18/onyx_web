from __future__ import annotations

from pathlib import Path

from config import file_storage_root


def get_storage_root() -> Path:
    """FastAPI dependency yielding the configured file storage root.

    A seam mirroring get_session: tests override it to redirect uploads into a
    temp directory so they never touch the real storage root.
    """
    return file_storage_root
