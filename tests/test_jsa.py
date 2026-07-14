from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_project


async def seed_project(session: AsyncSession, project_number: str = "P-001"):
    """Persist and return a Project for JSA requests."""
    project = make_project(project_number=project_number)
    session.add(project)
    await session.flush()
    return project


async def create_jsa(client: AsyncClient, project_id: int):
    """Create a two-file JSA package through the public API."""
    return await client.post(
        f"/api/projects/{project_id}/jsa",
        files=[
            ("files", ("jsa.pdf", b"submitted JSA", "application/pdf")),
            ("files", ("roster.pdf", b"competent person roster", "application/pdf")),
        ],
    )


async def test_create_jsa_stores_an_ordered_submitted_package(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The first package creates singleton JSA revision zero in Submitted state."""
    project = await seed_project(session)

    response = await create_jsa(client, project.id)

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "submitted"
    assert body["revisions"][0]["revision_number"] == 0
    assert [link["file"]["original_name"] for link in body["revisions"][0]["file_links"]] == [
        "jsa.pdf",
        "roster.pdf",
    ]
    file_id = body["revisions"][0]["file_links"][0]["file"]["id"]
    assert (await client.get(f"/api/files/{file_id}")).content == b"submitted JSA"


async def test_create_jsa_rejects_duplicate_and_invalid_package_bounds(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A Project gets one JSA, and its first package has one to three files."""
    project = await seed_project(session)

    assert (await client.post(f"/api/projects/{project.id}/jsa")).status_code == 422
    empty = await client.post(
        f"/api/projects/{project.id}/jsa",
        files={"files": ("empty.pdf", b"", "application/pdf")},
    )
    assert empty.status_code == 400
    too_many = await client.post(
        f"/api/projects/{project.id}/jsa",
        files=[
            ("files", (f"{index}.pdf", b"file", "application/pdf"))
            for index in range(4)
        ],
    )
    assert too_many.status_code == 400
    assert (await create_jsa(client, project.id)).status_code == 201
    assert (await create_jsa(client, project.id)).status_code == 409


async def test_jsa_notes_save_on_the_singleton(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Notes are mutable JSA-level context, independent of package files."""
    project = await seed_project(session)
    await create_jsa(client, project.id)

    response = await client.patch(
        f"/api/projects/{project.id}/jsa/notes", json={"notes": "Coordinate with site lead."}
    )

    assert response.status_code == 200
    assert response.json()["notes"] == "Coordinate with site lead."


async def test_project_and_jsa_pages_show_navigation_and_live_package(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Project navigation reaches the empty and submitted JSA page states."""
    project = await seed_project(session)
    await session.commit()

    project_page = await client.get(f"/projects/{project.id}")
    empty_page = await client.get(f"/projects/{project.id}/jsa")
    assert f'href="/projects/{project.id}/jsa"' in project_page.text
    assert 'class="jsa-status-dot jsa-status-not-started"' in project_page.text
    assert "No job safety analysis yet." in empty_page.text

    await create_jsa(client, project.id)
    live_page = await client.get(f"/projects/{project.id}/jsa")
    project_page = await client.get(f"/projects/{project.id}")
    assert 'class="jsa-status-dot jsa-status-submitted"' in project_page.text
    assert "Submitted" in live_page.text
    assert "jsa.pdf" in live_page.text
    assert f'data-notes-url="/api/projects/{project.id}/jsa/notes"' in live_page.text
    assert f'data-url="/api/projects/{project.id}/jsa/revisions/' in live_page.text
    assert f'data-url="/api/projects/{project.id}/jsa"' in live_page.text
    assert "Delete the current JSA revision?" in live_page.text
    assert "Delete this JSA and its full revision history?" in live_page.text
    assert '<template data-jsa-reject-template>' in live_page.text
    assert 'data-jsa-reject-only hidden' not in live_page.text


async def test_approve_jsa_records_comments_and_decision_date(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Approval decides the submitted package without creating returned files."""
    project = await seed_project(session)
    await create_jsa(client, project.id)

    response = await client.post(
        f"/api/projects/{project.id}/jsa/approve",
        json={"comments": "Approved for site work."},
    )

    assert response.status_code == 200
    revision = response.json()["revisions"][0]
    assert response.json()["status"] == "approved"
    assert revision["status"] == "approved"
    assert revision["comments"] == "Approved for site work."
    assert revision["decided_at"] is not None
    assert [link for link in revision["file_links"] if link["file_group"] == "returned"] == []
    page = await client.get(f"/projects/{project.id}/jsa")
    assert ">APPROVED 1</button>" in page.text
    assert ">APPROVED 2</button>" in page.text


async def test_reject_jsa_stores_returned_package_and_defaults_page_to_it(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Rejection stores ordered markups and foregrounds the first returned file."""
    project = await seed_project(session)
    await create_jsa(client, project.id)

    response = await client.post(
        f"/api/projects/{project.id}/jsa/reject",
        data={"comments": "Correct the lift plan."},
        files=[
            ("files", ("markup.pdf", b"first markup", "application/pdf")),
            ("files", ("roster-markup.pdf", b"second markup", "application/pdf")),
        ],
    )

    assert response.status_code == 200
    revision = response.json()["revisions"][0]
    returned_links = [
        link for link in revision["file_links"] if link["file_group"] == "returned"
    ]
    assert response.json()["status"] == "rejected"
    assert revision["comments"] == "Correct the lift plan."
    assert [link["file"]["original_name"] for link in returned_links] == [
        "markup.pdf",
        "roster-markup.pdf",
    ]
    download = await client.get(f"/api/files/{returned_links[0]['file']['id']}")
    assert download.content == b"first markup"

    page = await client.get(f"/projects/{project.id}/jsa")
    assert "BUYER COMMENTS" in page.text
    assert "DEC " in page.text
    assert 'data-preview-tab="file-%s"' % returned_links[0]["id"] in page.text
    assert "RETURNED 1" in page.text


async def test_revise_jsa_creates_next_submitted_revision_from_both_decisions(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Resolved JSAs accept one new package; Submitted JSAs do not."""
    project = await seed_project(session)
    await create_jsa(client, project.id)

    assert (await client.post(f"/api/projects/{project.id}/jsa/approve")).status_code == 200
    response = await client.post(
        f"/api/projects/{project.id}/jsa/submit",
        files={"files": ("scope-change.pdf", b"changed scope", "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "submitted"
    assert [revision["revision_number"] for revision in body["revisions"]] == [0, 1]
    assert body["revisions"][0]["status"] == "approved"
    assert body["revisions"][1]["status"] == "submitted"
    assert (await client.post(f"/api/projects/{project.id}/jsa/submit")).status_code == 422
    assert (
        await client.post(
            f"/api/projects/{project.id}/jsa/submit",
            files={"files": ("another.pdf", b"another", "application/pdf")},
        )
    ).status_code == 409

    assert (
        await client.post(
            f"/api/projects/{project.id}/jsa/reject",
            files={"files": ("markup.pdf", b"markup", "application/pdf")},
        )
    ).status_code == 200
    response = await client.post(
        f"/api/projects/{project.id}/jsa/submit",
        files={"files": ("corrected.pdf", b"corrected", "application/pdf")},
    )
    assert response.status_code == 200
    assert [revision["revision_number"] for revision in response.json()["revisions"]] == [0, 1, 2]


async def test_jsa_history_is_scoped_and_read_only_on_the_page(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Past JSA packages retain their decision context without live controls."""
    project = await seed_project(session)
    other_project = await seed_project(session, "P-002")
    await create_jsa(client, project.id)
    await create_jsa(client, other_project.id)
    await client.post(
        f"/api/projects/{project.id}/jsa/reject",
        data={"comments": "Correct the lift plan."},
        files={"files": ("markup.pdf", b"markup", "application/pdf")},
    )
    revised = await client.post(
        f"/api/projects/{project.id}/jsa/submit",
        files={"files": ("corrected.pdf", b"corrected", "application/pdf")},
    )
    old_revision_id = revised.json()["revisions"][0]["id"]

    assert (await client.get(f"/api/projects/{project.id}/jsa/revisions")).status_code == 200
    assert (
        await client.get(f"/api/projects/{other_project.id}/jsa/revisions/{old_revision_id}")
    ).status_code == 404
    page = await client.get(f"/projects/{project.id}/jsa/revisions/{old_revision_id}")

    assert page.status_code == 200
    assert "VIEWING PAST REVISION" in page.text
    assert "Correct the lift plan." in page.text
    assert 'data-modal-open="approve-modal"' not in page.text
    assert 'data-modal-open="revise-modal"' not in page.text
    assert 'data-notes-url=' not in page.text
    assert "READ-ONLY" in page.text
    assert f'href="/projects/{project.id}/jsa/revisions/{old_revision_id}"' in page.text


@pytest.mark.parametrize("decision", ["submitted", "approved", "rejected"])
async def test_delete_sole_current_revision_removes_jsa_and_keeps_file(
    client: AsyncClient, session: AsyncSession, decision: str
) -> None:
    """Deleting revision zero removes the singleton in every lifecycle status."""
    project = await seed_project(session)
    created = await create_jsa(client, project.id)
    file_id = created.json()["revisions"][0]["file_links"][0]["file"]["id"]
    if decision == "approved":
        await client.post(f"/api/projects/{project.id}/jsa/approve")
    elif decision == "rejected":
        await client.post(
            f"/api/projects/{project.id}/jsa/reject",
            files={"files": ("markup.pdf", b"markup", "application/pdf")},
        )

    revision_id = (await client.get(f"/api/projects/{project.id}/jsa")).json()["revisions"][-1]["id"]
    response = await client.delete(f"/api/projects/{project.id}/jsa/revisions/{revision_id}")

    assert response.status_code == 204
    assert (await client.get(f"/api/projects/{project.id}/jsa")).status_code == 404
    assert (await client.get(f"/api/files/{file_id}")).content == b"submitted JSA"
    assert "No job safety analysis yet." in (await client.get(f"/projects/{project.id}/jsa")).text


async def test_delete_current_revision_restores_previous_and_rejects_history(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Only the newest revision can be deleted, restoring its predecessor."""
    project = await seed_project(session)
    await create_jsa(client, project.id)
    await client.post(f"/api/projects/{project.id}/jsa/approve")
    revised = await client.post(
        f"/api/projects/{project.id}/jsa/submit",
        files={"files": ("scope-change.pdf", b"changed scope", "application/pdf")},
    )
    old_revision_id = revised.json()["revisions"][0]["id"]
    current_revision_id = revised.json()["revisions"][1]["id"]

    assert (
        await client.delete(f"/api/projects/{project.id}/jsa/revisions/{old_revision_id}")
    ).status_code == 409
    assert (
        await client.delete(f"/api/projects/{project.id}/jsa/revisions/{current_revision_id}")
    ).status_code == 204

    restored = (await client.get(f"/api/projects/{project.id}/jsa")).json()
    assert restored["status"] == "approved"
    assert [revision["revision_number"] for revision in restored["revisions"]] == [0]
    assert restored["revisions"][0]["status"] == "approved"


@pytest.mark.parametrize("decision", ["submitted", "approved", "rejected"])
async def test_delete_whole_jsa_removes_history_and_page_returns_to_project(
    client: AsyncClient, session: AsyncSession, decision: str
) -> None:
    """Whole-JSA deletion is available in every status and retains stored files."""
    project = await seed_project(session)
    created = await create_jsa(client, project.id)
    file_id = created.json()["revisions"][0]["file_links"][0]["file"]["id"]
    if decision == "approved":
        await client.post(f"/api/projects/{project.id}/jsa/approve")
    elif decision == "rejected":
        await client.post(
            f"/api/projects/{project.id}/jsa/reject",
            files={"files": ("markup.pdf", b"markup", "application/pdf")},
        )

    assert (await client.delete(f"/api/projects/{project.id}/jsa")).status_code == 204
    assert (await client.get(f"/api/projects/{project.id}/jsa")).status_code == 404
    assert (await client.get(f"/api/files/{file_id}")).content == b"submitted JSA"
    page = await client.get(f"/projects/{project.id}")
    assert page.status_code == 200


async def test_jsa_decisions_enforce_submitted_status_and_return_package_bounds(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Only Submitted packages can be decided and rejection needs non-empty files."""
    project = await seed_project(session)
    await create_jsa(client, project.id)

    approve_url = f"/api/projects/{project.id}/jsa/approve"
    assert (await client.post(approve_url)).status_code == 200
    assert (await client.post(approve_url)).status_code == 409
    assert (
        await client.post(
            f"/api/projects/{project.id}/jsa/reject",
            files={"files": ("markup.pdf", b"markup", "application/pdf")},
        )
    ).status_code == 409

    rejected_project = await seed_project(session, "P-002")
    await create_jsa(client, rejected_project.id)
    assert (
        await client.post(
            f"/api/projects/{rejected_project.id}/jsa/approve",
            files={"files": ("markup.pdf", b"markup", "application/pdf")},
        )
    ).status_code == 422
    assert (
        await client.post(
            f"/api/projects/{rejected_project.id}/jsa/reject",
            files={"files": ("empty.pdf", b"", "application/pdf")},
        )
    ).status_code == 400
    assert (
        await client.post(
            f"/api/projects/{rejected_project.id}/jsa/reject",
            files=[
                ("files", (f"markup-{index}.pdf", b"markup", "application/pdf"))
                for index in range(4)
            ],
        )
    ).status_code == 400
