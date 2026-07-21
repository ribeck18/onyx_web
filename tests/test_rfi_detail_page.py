from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_project


async def test_live_rfi_detail_shows_submission_preview_notes_and_timeline(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """The live RFI page renders its submitted file, notes, and REV 0."""
    project = make_project(project_number="26-131", name="Acme Plant Expansion")
    session.add(project)
    await session.flush()
    created = await client.post(
        "/api/rfis",
        json={
            "project_id": project.id,
            "rfi_number": "RFI-001",
            "title": "Clarify foundation elevation",
            "notes": "Coordinate with structural engineer.",
        },
    )
    rfi_id = created.json()["id"]
    submitted = await client.post(
        f"/api/rfis/{rfi_id}/submit",
        files={"file": ("question.pdf", b"question document", "application/pdf")},
    )
    assert submitted.status_code == 200

    response = await client.get(f"/rfis/{rfi_id}")

    assert response.status_code == 200
    body = response.text
    assert "REQUEST FOR INFORMATION · RFI-001" in body
    assert "Clarify foundation elevation" in body
    assert 'hero-status fam-info' in body
    assert 'class="preview-pdf"' in body
    assert "REV 0" in body
    assert f'data-notes-url="/api/rfis/{rfi_id}"' in body
    assert 'href="/projects/%s/rfis"' % project.id in body
    assert 'name="rfi_number"' not in body
    assert 'data-url="/api/rfis/%s/submit"' % rfi_id not in body


async def test_rfi_detail_topbar_uses_entered_rfi_number(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """The detail topbar identifies an RFI by its entered number, not its ID."""
    project = make_project()
    session.add(project)
    await session.flush()
    created = await client.post(
        "/api/rfis",
        json={
            "project_id": project.id,
            "rfi_number": "FIELD-42",
            "title": "Clarify foundation elevation",
        },
    )
    rfi_id = created.json()["id"]

    response = await client.get(f"/rfis/{rfi_id}")

    assert response.status_code == 200
    assert '<span class="vdi-tag">FIELD-42</span>' in response.text
    assert f'<span class="vdi-tag">RFI-{rfi_id}</span>' not in response.text


async def test_rfi_list_navigates_to_live_detail(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """An RFI list row carries the existing generic detail-navigation contract."""
    project = make_project()
    session.add(project)
    await session.flush()
    created = await client.post(
        "/api/rfis",
        json={
            "project_id": project.id,
            "rfi_number": "RFI-001",
            "title": "Clarify foundation elevation",
        },
    )

    response = await client.get(f"/projects/{project.id}/rfis")

    assert response.status_code == 200
    assert 'data-row-href="/rfis/%s"' % created.json()["id"] in response.text
