"""Decide how a stored file is previewed in the VDI detail pane.

The pane has three live branches keyed off the file's content type: PDFs embed
in an iframe, images render inline, and everything else falls back to a download
link. Kept here (not in labels.py) because it is preview presentation, not an
enum label.
"""

from __future__ import annotations

PREVIEW_PDF = "pdf"
PREVIEW_IMAGE = "image"
PREVIEW_DOWNLOAD = "download"


def preview_kind(content_type: str) -> str:
    """Return the preview branch (pdf/image/download) for a content type."""
    normalized = (content_type or "").lower()
    if normalized == "application/pdf" or normalized.endswith("/pdf"):
        return PREVIEW_PDF
    if normalized.startswith("image/"):
        return PREVIEW_IMAGE
    return PREVIEW_DOWNLOAD


def file_extension(original_name: str) -> str:
    """Return an UPPERCASE extension chip for the download fallback (e.g. DWG)."""
    _, _, extension = (original_name or "").rpartition(".")
    return extension.upper() if extension else "FILE"
