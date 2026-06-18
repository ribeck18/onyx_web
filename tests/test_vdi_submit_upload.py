from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_project, make_vdi


async def seed_vdi(session: AsyncSession) -> int:
    """Persist a project + VDI and return the VDI id."""
    project = make_project()
    vendor_data_item = make_vdi(project)
    session.add(vendor_data_item)
    await session.flush()
    return vendor_data_item.id


async def test_submit_stores_file_and_serves_it_back(
    client: AsyncClient, session: AsyncSession, tmp_path
) -> None:
    """Submitting attaches a stored File whose bytes download intact."""
    vdi_id = await seed_vdi(session)

    response = await client.post(
        f"/vdi/{vdi_id}/submit",
        files={"file": ("rev0.pdf", b"the real submittal", "application/pdf")},
    )

    assert response.status_code == 200
    revision = (await client.get(f"/vdi/{vdi_id}/revisions/latest")).json()
    submit_file = revision["submit_file"]
    assert submit_file["original_name"] == "rev0.pdf"
    assert submit_file["content_type"] == "application/pdf"
    assert "stored_path" not in submit_file

    # The bytes are reachable through the stable download URL and on disk.
    download = await client.get(f"/files/{submit_file['id']}")
    assert download.status_code == 200
    assert download.content == b"the real submittal"
    assert any(tmp_path.iterdir())


async def test_submit_without_file_returns_422(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The file part is required; omitting it is a 422."""
    vdi_id = await seed_vdi(session)

    response = await client.post(f"/vdi/{vdi_id}/submit")

    assert response.status_code == 422


async def test_submit_empty_file_returns_400(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A zero-byte upload is rejected with a 400."""
    vdi_id = await seed_vdi(session)

    response = await client.post(
        f"/vdi/{vdi_id}/submit",
        files={"file": ("rev0.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
