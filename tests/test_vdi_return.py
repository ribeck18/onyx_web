from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.vdi import service as vdi_service
from app.vdi.submit_status import SubmitStatus
from tests.factories import make_project, make_vdi


async def seed_submitted_vdi(session: AsyncSession) -> int:
    """Persist a project + VDI and submit it so it is out for review."""
    project = make_project()
    vendor_data_item = make_vdi(project)
    session.add(vendor_data_item)
    await session.flush()
    await vdi_service.submit_vdi(session, vendor_data_item, "uploads/rev0.pdf")
    await session.flush()
    return vendor_data_item.id


@pytest.mark.parametrize("return_code", ["a", "b", "c", "d"])
async def test_return_records_response_on_latest_revision(
    client: AsyncClient, session: AsyncSession, return_code: str
) -> None:
    """A return writes the code, document, comments, and returned_at, and sets status."""
    vdi_id = await seed_submitted_vdi(session)

    response = await client.post(
        f"/vdi/{vdi_id}/return",
        json={
            "return_code": return_code,
            "return_document": "uploads/rev0-returned.pdf",
            "comments": "see markups",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == return_code

    revision = (await client.get(f"/vdi/{vdi_id}/revisions/latest")).json()
    assert revision["status"] == return_code
    assert revision["return_document"] == "uploads/rev0-returned.pdf"
    assert revision["comments"] == "see markups"
    assert revision["returned_at"] is not None


@pytest.mark.parametrize("rejecting_code", ["b", "c"])
async def test_rejecting_return_is_resubmittable(
    client: AsyncClient, session: AsyncSession, rejecting_code: str
) -> None:
    """After a B/C return the VDI can be submitted again, opening the next revision."""
    vdi_id = await seed_submitted_vdi(session)
    await client.post(
        f"/vdi/{vdi_id}/return",
        json={"return_code": rejecting_code, "return_document": "r0.pdf"},
    )

    resubmit = await client.post(
        f"/vdi/{vdi_id}/submit", json={"submit_document": "rev1.pdf"}
    )

    assert resubmit.status_code == 200
    assert resubmit.json()["status"] == "submitted"
    revisions = (await client.get(f"/vdi/{vdi_id}/revisions")).json()
    assert [revision["revision_number"] for revision in revisions] == [0, 1]


@pytest.mark.parametrize("approving_code", ["a", "d"])
async def test_approving_return_is_terminal(
    client: AsyncClient, session: AsyncSession, approving_code: str
) -> None:
    """After an A/D return neither submit nor return is allowed."""
    vdi_id = await seed_submitted_vdi(session)
    await client.post(
        f"/vdi/{vdi_id}/return",
        json={"return_code": approving_code, "return_document": "r0.pdf"},
    )

    resubmit = await client.post(
        f"/vdi/{vdi_id}/submit", json={"submit_document": "rev1.pdf"}
    )
    rereturn = await client.post(
        f"/vdi/{vdi_id}/return",
        json={"return_code": "b", "return_document": "r1.pdf"},
    )

    assert resubmit.status_code == 409
    assert rereturn.status_code == 409


async def test_return_on_not_started_returns_409(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A VDI that was never submitted cannot be returned."""
    project = make_project()
    vendor_data_item = make_vdi(project)
    session.add(vendor_data_item)
    await session.flush()

    response = await client.post(
        f"/vdi/{vendor_data_item.id}/return",
        json={"return_code": "a", "return_document": "r0.pdf"},
    )

    assert response.status_code == 409


async def test_return_unknown_vdi_returns_404(client: AsyncClient) -> None:
    """Returning an unknown VDI is a 404."""
    response = await client.post(
        "/vdi/999/return", json={"return_code": "a", "return_document": "r0.pdf"}
    )

    assert response.status_code == 404


async def test_return_rejects_non_return_code(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A lifecycle state (e.g. submitted) is not a valid return code."""
    vdi_id = await seed_submitted_vdi(session)

    response = await client.post(
        f"/vdi/{vdi_id}/return",
        json={"return_code": "submitted", "return_document": "r0.pdf"},
    )

    assert response.status_code == 422


async def test_invalid_return_is_atomic(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A guarded-out return (409) writes nothing and leaves the revision open."""
    project = make_project()
    vendor_data_item = make_vdi(project)
    session.add(vendor_data_item)
    await session.flush()
    vdi_id = vendor_data_item.id

    await client.post(
        f"/vdi/{vdi_id}/return",
        json={"return_code": "a", "return_document": "r0.pdf"},
    )

    returned = await session.execute(
        text("SELECT COUNT(*) FROM revisions WHERE returned_at IS NOT NULL")
    )
    assert returned.scalar_one() == 0
    refreshed = await vdi_service.get_vdi(session, vdi_id)
    assert refreshed.status is SubmitStatus.NOT_STARTED
