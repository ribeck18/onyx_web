from __future__ import annotations

import pytest

from app.web.file_preview import is_inline_safe


@pytest.mark.parametrize(
    "content_type",
    [
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/bmp",
        "IMAGE/PNG",
    ],
)
def test_is_inline_safe_allows_pdf_and_raster(content_type):
    """PDFs and raster images are safe to hand the browser inline."""
    assert is_inline_safe(content_type) is True


@pytest.mark.parametrize(
    "content_type",
    [
        "image/svg+xml",
        "application/octet-stream",
        "text/html",
        "unknown",
        "",
    ],
)
def test_is_inline_safe_rejects_svg_and_unknown(content_type):
    """SVG and anything outside the allowlist must not be served inline."""
    assert is_inline_safe(content_type) is False
