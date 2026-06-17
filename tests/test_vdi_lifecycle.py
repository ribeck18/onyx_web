from __future__ import annotations

import ast
import inspect

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.vdi import service as vdi_service
from app.vdi.revision import service as revision_service
from app.vdi.submit_status import SubmitStatus
from tests.factories import make_project, make_vdi


async def seed_vdi(session: AsyncSession, project_number: str = "P-001") -> int:
    """Persist a project + VDI and return the VDI id."""
    project = make_project(project_number=project_number)
    vendor_data_item = make_vdi(project)
    session.add(vendor_data_item)
    await session.flush()
    return vendor_data_item.id


async def force_status(
    session: AsyncSession, vdi_id: int, new_status: SubmitStatus
) -> None:
    """Set a VDI's status directly (stands in for the not-yet-built return flow)."""
    vendor_data_item = await vdi_service.get_vdi(session, vdi_id)
    vendor_data_item.status = new_status
    await session.flush()


async def test_submit_from_not_started_opens_revision_zero(
    client: AsyncClient, session: AsyncSession
) -> None:
    """First submit creates Revision 0, sets SUBMITTED, and records submitted_at."""
    vdi_id = await seed_vdi(session)

    response = await client.post(
        f"/vdi/{vdi_id}/submit", json={"submit_document": "uploads/rev0.pdf"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "submitted"

    revisions = (await client.get(f"/vdi/{vdi_id}/revisions")).json()
    assert len(revisions) == 1
    assert revisions[0]["revision_number"] == 0
    assert revisions[0]["status"] == "submitted"
    assert revisions[0]["submitted_at"] is not None
    assert revisions[0]["submit_document"] == "uploads/rev0.pdf"


@pytest.mark.parametrize("rejected_status", [SubmitStatus.B, SubmitStatus.C])
async def test_resubmit_from_rejected_opens_next_revision(
    client: AsyncClient, session: AsyncSession, rejected_status: SubmitStatus
) -> None:
    """Resubmitting a rejected VDI opens the next revision and returns to SUBMITTED."""
    vdi_id = await seed_vdi(session)
    await client.post(f"/vdi/{vdi_id}/submit", json={"submit_document": "rev0.pdf"})
    await force_status(session, vdi_id, rejected_status)

    response = await client.post(
        f"/vdi/{vdi_id}/submit", json={"submit_document": "rev1.pdf"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "submitted"
    revisions = (await client.get(f"/vdi/{vdi_id}/revisions")).json()
    assert [revision["revision_number"] for revision in revisions] == [0, 1]


async def test_submit_already_submitted_returns_409(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A VDI already out for review cannot be submitted again."""
    vdi_id = await seed_vdi(session)
    await client.post(f"/vdi/{vdi_id}/submit", json={"submit_document": "rev0.pdf"})

    response = await client.post(
        f"/vdi/{vdi_id}/submit", json={"submit_document": "rev0-again.pdf"}
    )

    assert response.status_code == 409


@pytest.mark.parametrize("terminal_status", [SubmitStatus.A, SubmitStatus.D])
async def test_submit_terminal_status_returns_409(
    client: AsyncClient, session: AsyncSession, terminal_status: SubmitStatus
) -> None:
    """An approved (A/D) VDI is terminal and cannot be submitted."""
    vdi_id = await seed_vdi(session)
    await force_status(session, vdi_id, terminal_status)

    response = await client.post(
        f"/vdi/{vdi_id}/submit", json={"submit_document": "rev0.pdf"}
    )

    assert response.status_code == 409


async def test_submit_unknown_vdi_returns_404(client: AsyncClient) -> None:
    """Submitting an unknown VDI is a 404."""
    response = await client.post(
        "/vdi/999/submit", json={"submit_document": "rev0.pdf"}
    )

    assert response.status_code == 404


async def test_rejected_submit_is_atomic(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A guarded-out submit (409) writes no revision and leaves status unchanged."""
    vdi_id = await seed_vdi(session)
    await force_status(session, vdi_id, SubmitStatus.A)

    await client.post(f"/vdi/{vdi_id}/submit", json={"submit_document": "rev0.pdf"})

    revision_count = await session.execute(
        text("SELECT COUNT(*) FROM revisions WHERE vendor_data_item_id = :id"),
        {"id": vdi_id},
    )
    assert revision_count.scalar_one() == 0
    vendor_data_item = await vdi_service.get_vdi(session, vdi_id)
    assert vendor_data_item.status is SubmitStatus.A


async def test_list_revisions_unknown_vdi_returns_404(client: AsyncClient) -> None:
    """Listing revisions for an unknown VDI is a 404."""
    response = await client.get("/vdi/999/revisions")

    assert response.status_code == 404


async def test_get_single_revision(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A single-revision read returns that revision's persisted fields."""
    vdi_id = await seed_vdi(session)
    await client.post(f"/vdi/{vdi_id}/submit", json={"submit_document": "rev0.pdf"})
    revision_id = (await client.get(f"/vdi/{vdi_id}/revisions")).json()[0]["id"]

    response = await client.get(f"/vdi/{vdi_id}/revisions/{revision_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == revision_id
    assert body["vendor_data_item_id"] == vdi_id


async def test_get_revision_wrong_vdi_returns_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A revision read scoped to the wrong VDI is a 404."""
    vdi_id = await seed_vdi(session, project_number="P-001")
    other_vdi_id = await seed_vdi(session, project_number="P-002")
    await client.post(f"/vdi/{vdi_id}/submit", json={"submit_document": "rev0.pdf"})
    revision_id = (await client.get(f"/vdi/{vdi_id}/revisions")).json()[0]["id"]

    response = await client.get(f"/vdi/{other_vdi_id}/revisions/{revision_id}")

    assert response.status_code == 404


async def test_get_unknown_revision_returns_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    """An unknown revision id is a 404."""
    vdi_id = await seed_vdi(session)

    response = await client.get(f"/vdi/{vdi_id}/revisions/999")

    assert response.status_code == 404


async def test_get_latest_revision_returns_highest_number(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The latest read returns the most recent revision after a resubmittal."""
    vdi_id = await seed_vdi(session)
    await client.post(f"/vdi/{vdi_id}/submit", json={"submit_document": "rev0.pdf"})
    await force_status(session, vdi_id, SubmitStatus.B)
    await client.post(f"/vdi/{vdi_id}/submit", json={"submit_document": "rev1.pdf"})

    response = await client.get(f"/vdi/{vdi_id}/revisions/latest")

    assert response.status_code == 200
    assert response.json()["revision_number"] == 1


async def test_get_latest_revision_without_history_returns_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A VDI that has never been submitted has no latest revision."""
    vdi_id = await seed_vdi(session)

    response = await client.get(f"/vdi/{vdi_id}/revisions/latest")

    assert response.status_code == 404


def test_revision_service_does_not_import_vdi_service() -> None:
    """ADR 0002: the dependency runs vdi.service -> revision.service only."""
    tree = ast.parse(inspect.getsource(revision_service))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        elif isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)

    assert "app.vdi.service" not in imported_modules
