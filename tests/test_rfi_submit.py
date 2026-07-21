from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import AsyncClient

from app.models.file import File
from tests.factories import make_project


async def seed_rfi(client: AsyncClient, session: AsyncSession) -> int:
    """Create a Not Started RFI and return its ID."""
    project = make_project()
    session.add(project)
    await session.flush()
    response = await client.post(
        "/api/rfis",
        json={
            "project_id": project.id,
            "rfi_number": "RFI-001",
            "title": "Clarify foundation elevation",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_rfi_submit_requires_non_empty_file(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """Submission rejects both an omitted file part and a zero-byte upload."""
    rfi_id = await seed_rfi(client, session)

    assert (await client.post(f"/api/rfis/{rfi_id}/submit")).status_code == 422
    empty = await client.post(
        f"/api/rfis/{rfi_id}/submit",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert empty.status_code == 400
    assert empty.json()["detail"] == "Uploaded file is empty."
    assert (await client.get(f"/api/rfis/{rfi_id}/revisions")).json() == []


async def test_rfi_submit_creates_revision_and_file(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """A non-empty first submission creates REV 0 and exposes its file."""
    rfi_id = await seed_rfi(client, session)

    response = await client.post(
        f"/api/rfis/{rfi_id}/submit",
        files={"file": ("question.pdf", b"question document", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "submitted"
    revisions = await client.get(f"/api/rfis/{rfi_id}/revisions")
    assert revisions.status_code == 200
    assert revisions.json()[0]["revision_number"] == 0
    assert revisions.json()[0]["status"] == "submitted"
    submit_file = revisions.json()[0]["submit_file"]
    assert submit_file["original_name"] == "question.pdf"
    assert "stored_path" not in submit_file
    assert (await client.get(f"/api/files/{submit_file['id']}")).content == b"question document"
    latest = await client.get(f"/api/rfis/{rfi_id}/revisions/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == revisions.json()[0]["id"]


async def test_rfi_submit_rejects_invalid_state_without_writing_file(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """A second submit is rejected before a File row is saved."""
    rfi_id = await seed_rfi(client, session)
    assert (
        await client.post(
            f"/api/rfis/{rfi_id}/submit",
            files={"file": ("rev0.pdf", b"revision zero", "application/pdf")},
        )
    ).status_code == 200
    files_before = await session.scalar(select(func.count()).select_from(File))

    response = await client.post(
        f"/api/rfis/{rfi_id}/submit",
        files={"file": ("orphan.pdf", b"must not save", "application/pdf")},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "RFI cannot be submitted from its current status"
    assert await session.scalar(select(func.count()).select_from(File)) == files_before
    assert len((await client.get(f"/api/rfis/{rfi_id}/revisions")).json()) == 1


async def test_rfi_number_locks_after_submission_but_metadata_remains_editable(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """Submission locks only the buyer-facing RFI Number."""
    rfi_id = await seed_rfi(client, session)
    assert (
        await client.post(
            f"/api/rfis/{rfi_id}/submit",
            files={"file": ("rev0.pdf", b"revision zero", "application/pdf")},
        )
    ).status_code == 200

    locked = await client.patch(f"/api/rfis/{rfi_id}", json={"rfi_number": "RFI-002"})
    assert locked.status_code == 409
    updated = await client.patch(
        f"/api/rfis/{rfi_id}",
        json={
            "title": "Updated question",
            "spec_drawing_reference": "S-101",
            "notes": "Save this in place.",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Updated question"
    assert updated.json()["spec_drawing_reference"] == "S-101"
    assert updated.json()["notes"] == "Save this in place."
