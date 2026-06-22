from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.vdi.submit_status import SubmitStatus
from tests.factories import make_project, make_revision, make_vdi
from tests.test_vdi_detail_page import (
    add_returned_revision,
    add_submitted_revision,
    make_vdi_row,
)


async def test_unknown_revision_returns_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A missing revision id under a real VDI is a 404."""
    vdi_id = await make_vdi_row(session, status=SubmitStatus.SUBMITTED)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}/revisions/9999")
    assert response.status_code == 404


async def test_revision_must_belong_to_vdi(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A revision belonging to another VDI is a 404 under this VDI's path."""
    project = make_project(project_number="26-131")
    vdi_one = make_vdi(project, item_number=1)
    vdi_two = make_vdi(project, item_number=2)
    session.add(project)
    session.add(vdi_one)
    session.add(vdi_two)
    await session.flush()
    revision = make_revision(vdi_two, revision_number=0)
    session.add(revision)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_one.id}/revisions/{revision.id}")
    assert response.status_code == 404


async def test_renders_layout_with_warning_banner(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The historical view returns 200 with the warning banner and return link."""
    vdi_id = await make_vdi_row(session, status=SubmitStatus.SUBMITTED)
    revision = await add_submitted_revision(session, vdi_id)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}/revisions/{revision.id}")

    assert response.status_code == 200
    body = response.text
    assert "hist-banner" in body
    assert "VIEWING PAST REVISION — NOT THE CURRENT STATE OF THIS VDI." in body
    assert f'class="hist-banner-link" href="/vdi/{vdi_id}"' in body


async def test_lifecycle_disabled_and_notes_read_only(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The historical view disables the lifecycle button and the notes box."""
    vdi_id = await make_vdi_row(session, status=SubmitStatus.SUBMITTED, notes="kept")
    revision = await add_submitted_revision(session, vdi_id)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}/revisions/{revision.id}")

    body = response.text
    assert '<button type="button" class="lifecycle-btn" disabled>Submit</button>' in body
    assert "ACTIONS AVAILABLE ONLY ON CURRENT VDI." in body
    assert "READ-ONLY" in body
    assert "disabled>kept</textarea>" in body
    # No lifecycle modals / save control in a read-only view.
    assert "data-modal=\"submit-modal\"" not in body
    assert "data-notes-save" not in body


async def test_hero_reflects_chosen_revision_not_current_vdi(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The hero shows the chosen revision's status, not the live VDI status.

    Viewing the rejected rev 0 of a VDI that is now back to SUBMITTED should read
    Rejected /B, not Submitted.
    """
    vdi_id = await make_vdi_row(session, status=SubmitStatus.SUBMITTED)
    rev0 = await add_returned_revision(
        session, vdi_id, revision_number=0, return_code=SubmitStatus.B
    )
    await add_submitted_revision(session, vdi_id, revision_number=1)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}/revisions/{rev0.id}")

    body = response.text
    assert "hero-status fam-bad" in body
    assert '<span class="hero-code">/B</span>' in body
    assert "REVISION FILE" in body
    # The buyer comments on the chosen revision are shown.
    assert "See markups on sheet 3." in body


async def test_timeline_marks_chosen_and_links_latest_to_live(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The chosen revision is marked current; the true-latest links to live."""
    vdi_id = await make_vdi_row(session, status=SubmitStatus.SUBMITTED)
    rev0 = await add_returned_revision(
        session, vdi_id, revision_number=0, return_code=SubmitStatus.B
    )
    rev1 = await add_submitted_revision(session, vdi_id, revision_number=1)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}/revisions/{rev0.id}")

    body = response.text
    # The viewed (chosen) entry carries the current marker.
    assert "CURRENT" in body
    # The true-latest entry returns to the live page, not its own history URL.
    assert f'href="/vdi/{vdi_id}"' in body
    assert f"/revisions/{rev1.id}" not in body
