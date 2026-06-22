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

# Content types we are willing to serve at a navigable URL with
# Content-Disposition: inline. Deliberately narrower than preview_kind — it
# excludes image/svg+xml, whose script executes on our origin if the browser
# navigates straight to it as the top document (stored XSS). See ADR 0006.
INLINE_SAFE_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/bmp",
    }
)


def is_inline_safe(content_type: str) -> bool:
    """Return whether these bytes are safe to serve inline at a navigable URL.

    Narrower than preview_kind on purpose: it answers "can the browser be handed
    these bytes inline" rather than "how does the pane embed them", and so
    excludes image/svg+xml even though an <img>-referenced SVG is previewable.
    """
    return (content_type or "").lower() in INLINE_SAFE_CONTENT_TYPES


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
