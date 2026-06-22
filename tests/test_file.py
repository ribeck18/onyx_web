from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.file import service
from app.file.schema import FileRead
from tests.factories import make_upload


async def test_save_then_download_round_trip(client, session, tmp_path):
    """A saved upload comes back over HTTP with its original bytes, name, and type."""
    stored_file = await service.save_upload(
        session, make_upload(content=b"the real submittal"), tmp_path
    )
    await session.commit()

    response = await client.get(f"/api/files/{stored_file.id}")

    assert response.status_code == 200
    assert response.content == b"the real submittal"
    assert response.headers["content-type"].startswith("application/pdf")
    assert "rev0.pdf" in response.headers["content-disposition"]


async def test_inline_safe_type_serves_inline_with_filename(client, session, tmp_path):
    """A PDF with no download param is served inline, keeping its original name."""
    stored_file = await service.save_upload(session, make_upload(), tmp_path)
    await session.commit()

    response = await client.get(f"/api/files/{stored_file.id}")

    disposition = response.headers["content-disposition"]
    assert disposition.startswith("inline")
    assert "rev0.pdf" in disposition


async def test_download_param_forces_attachment(client, session, tmp_path):
    """The same inline-safe file is served as an attachment with ?download=1."""
    stored_file = await service.save_upload(session, make_upload(), tmp_path)
    await session.commit()

    response = await client.get(f"/api/files/{stored_file.id}?download=1")

    assert response.headers["content-disposition"].startswith("attachment")


async def test_svg_is_forced_to_attachment(client, session, tmp_path):
    """An SVG is never served inline — it could run script on our origin."""
    stored_file = await service.save_upload(
        session,
        make_upload(filename="drawing.svg", content_type="image/svg+xml"),
        tmp_path,
    )
    await session.commit()

    response = await client.get(f"/api/files/{stored_file.id}")

    assert response.headers["content-disposition"].startswith("attachment")


async def test_non_previewable_type_is_attachment(client, session, tmp_path):
    """A type outside the inline allowlist (e.g. CAD) is served as a download."""
    stored_file = await service.save_upload(
        session,
        make_upload(filename="part.dwg", content_type="application/octet-stream"),
        tmp_path,
    )
    await session.commit()

    response = await client.get(f"/api/files/{stored_file.id}")

    assert response.headers["content-disposition"].startswith("attachment")


async def test_file_response_sends_nosniff(client, session, tmp_path):
    """The file response carries X-Content-Type-Options: nosniff."""
    stored_file = await service.save_upload(session, make_upload(), tmp_path)
    await session.commit()

    response = await client.get(f"/api/files/{stored_file.id}")

    assert response.headers["x-content-type-options"] == "nosniff"


async def test_save_upload_writes_bytes_under_storage_root(session, tmp_path):
    """The bytes land under the storage root with the original extension preserved."""
    stored_file = await service.save_upload(
        session, make_upload(content=b"on disk"), tmp_path
    )

    disk_path = tmp_path / stored_file.stored_path
    assert disk_path.is_file()
    assert disk_path.read_bytes() == b"on disk"
    assert disk_path.suffix == ".pdf"


async def test_save_upload_rejects_empty_file(session, tmp_path):
    """A zero-byte upload is rejected with a 400 and nothing is written."""
    with pytest.raises(HTTPException) as exc_info:
        await service.save_upload(session, make_upload(content=b""), tmp_path)

    assert exc_info.value.status_code == 400
    assert not any(tmp_path.iterdir())


async def test_download_unknown_file_returns_404(client):
    """Downloading an id with no File row returns 404."""
    response = await client.get("/api/files/999")

    assert response.status_code == 404


async def test_file_read_never_exposes_stored_path(session, tmp_path):
    """FileRead must not leak the internal stored_path."""
    stored_file = await service.save_upload(session, make_upload(), tmp_path)

    payload = FileRead.model_validate(stored_file).model_dump()

    assert "stored_path" not in payload
    assert payload["original_name"] == "rev0.pdf"
