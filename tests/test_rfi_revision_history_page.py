from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_project


async def create_submitted_rfi(client: AsyncClient, session: AsyncSession, number: str) -> int:
    """Create an RFI and submit its first revision."""
    project = make_project(project_number=f"P-{number}")
    session.add(project)
    await session.flush()
    created = await client.post(
        "/api/rfis",
        json={
            "project_id": project.id,
            "rfi_number": number,
            "title": f"Question {number}",
            "notes": "Keep this note.",
        },
    )
    rfi_id = created.json()["id"]
    submitted = await client.post(
        f"/api/rfis/{rfi_id}/submit",
        files={"file": ("submitted.pdf", b"submitted document", "application/pdf")},
    )
    assert submitted.status_code == 200
    return rfi_id


async def test_live_rfi_return_previews_show_both_files_or_comments_without_file(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """Live RFI pages render both return files and fileless buyer comments."""
    returned_rfi_id = await create_submitted_rfi(client, session, "RFI-001")
    pending = await client.get(f"/rfis/{returned_rfi_id}")
    assert pending.status_code == 200
    assert f'data-url="/api/rfis/{returned_rfi_id}/return"' in pending.text

    returned = await client.post(
        f"/api/rfis/{returned_rfi_id}/return",
        data={"decision": "rejected", "comments": "Revise sheet S-101."},
        files={"file": ("marked-up.pdf", b"markups", "application/pdf")},
    )
    assert returned.status_code == 200

    response = await client.get(f"/rfis/{returned_rfi_id}")

    assert response.status_code == 200
    body = response.text
    assert "Revise sheet S-101." in body
    assert 'data-preview-tab="submitted"' in body
    assert 'data-preview-tab="returned"' in body
    assert "submitted.pdf" in body
    assert "marked-up.pdf" in body
    assert 'data-url="/api/rfis/%s/submit"' % returned_rfi_id in body

    fileless_rfi_id = await create_submitted_rfi(client, session, "RFI-002")
    fileless = await client.post(
        f"/api/rfis/{fileless_rfi_id}/return",
        data={"decision": "approved", "comments": "Approved as submitted."},
    )
    assert fileless.status_code == 200

    response = await client.get(f"/rfis/{fileless_rfi_id}")

    assert response.status_code == 200
    body = response.text
    assert "Approved as submitted." in body
    assert 'data-preview-tab="submitted"' not in body
    assert 'data-preview-tab="returned"' not in body
    assert "submitted.pdf" in body


async def test_historical_rfi_page_scopes_revision_and_is_read_only(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """A selected RFI revision is scoped, historical, and has no mutable controls."""
    rfi_id = await create_submitted_rfi(client, session, "RFI-001")
    returned = await client.post(
        f"/api/rfis/{rfi_id}/return",
        data={"decision": "rejected", "comments": "Revise sheet S-101."},
        files={"file": ("marked-up.pdf", b"markups", "application/pdf")},
    )
    assert returned.status_code == 200
    revision_id = (await client.get(f"/api/rfis/{rfi_id}/revisions/latest")).json()["id"]
    resubmitted = await client.post(
        f"/api/rfis/{rfi_id}/submit",
        files={"file": ("revision-1.pdf", b"revision one", "application/pdf")},
    )
    assert resubmitted.status_code == 200

    rfi = (await client.get(f"/api/rfis/{rfi_id}")).json()
    response = await client.get(f"/rfis/{rfi_id}/revisions/{revision_id}")

    assert response.status_code == 200
    body = response.text
    assert "VIEWING PAST REVISION — NOT THE CURRENT STATE OF THIS RFI." in body
    assert f'href="/rfis/{rfi_id}"' in body
    assert f'href="/projects/{rfi["project_id"]}/rfis"' in body
    assert "hero-status fam-bad" in body
    assert "Revise sheet S-101." in body
    assert "REVISION FILE" in body
    assert 'data-preview-tab="submitted"' in body
    assert 'data-preview-tab="returned"' in body
    assert "READ-ONLY" in body
    assert "disabled>Keep this note.</textarea>" in body
    assert "data-notes-save" not in body
    assert 'data-modal="submit-modal"' not in body
    assert f'data-url="/api/rfis/{rfi_id}/return"' not in body
    assert f'href="/rfis/{rfi_id}"' in body

    other_rfi_id = await create_submitted_rfi(client, session, "RFI-002")
    assert (
        await client.get(f"/rfis/{other_rfi_id}/revisions/{revision_id}")
    ).status_code == 404
    assert (await client.get(f"/rfis/{rfi_id}/revisions/9999")).status_code == 404
