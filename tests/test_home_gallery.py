from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vdi import VendorDataItem
from app.vdi.approval_type import ApprovalType
from app.vdi.submit_code import SubmitCode
from app.vdi.submit_status import SubmitStatus
from tests.factories import make_project


async def seed_project(session: AsyncSession, **kwargs: str) -> int:
    """Persist a project and return its id."""
    project = make_project(**kwargs)
    session.add(project)
    await session.flush()
    return project.id


async def add_vdi(
    session: AsyncSession,
    project_id: int,
    item_number: int,
    status: SubmitStatus,
) -> None:
    """Persist a VDI in a given status on the project."""
    vdi = VendorDataItem(
        project_id=project_id,
        item_number=item_number,
        name="Concrete Mix Design",
        approval_type=ApprovalType.MANDATORY_APPROVAL,
        submit_code=SubmitCode.PTC,
        status=status,
    )
    session.add(vdi)
    await session.flush()


async def test_gallery_renders_card_per_project(
    client: AsyncClient, session: AsyncSession
) -> None:
    """GET / returns 200 with a card showing number, name, and item counts."""
    project_id = await seed_project(
        session, project_number="26-131", name="Acme Plant Expansion"
    )
    await add_vdi(session, project_id, 1, SubmitStatus.SUBMITTED)
    await add_vdi(session, project_id, 2, SubmitStatus.A)
    await session.commit()

    response = await client.get("/")

    assert response.status_code == 200
    body = response.text
    assert "26-131" in body
    assert "Acme Plant Expansion" in body
    assert "2 ITEMS" in body


async def test_open_count_excludes_approved(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The open cue counts only items whose status is not A or D."""
    project_id = await seed_project(session, project_number="26-131")
    await add_vdi(session, project_id, 1, SubmitStatus.SUBMITTED)
    await add_vdi(session, project_id, 2, SubmitStatus.B)
    await add_vdi(session, project_id, 3, SubmitStatus.A)
    await add_vdi(session, project_id, 4, SubmitStatus.D)
    await session.commit()

    response = await client.get("/")

    assert response.status_code == 200
    assert "2 OPEN" in response.text


async def test_all_clear_when_no_open_items(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A project with only approved items reads ALL CLEAR, not an open count."""
    project_id = await seed_project(session, project_number="26-007")
    await add_vdi(session, project_id, 1, SubmitStatus.A)
    await add_vdi(session, project_id, 2, SubmitStatus.D)
    await session.commit()

    response = await client.get("/")

    assert response.status_code == 200
    assert "ALL CLEAR" in response.text
    assert "OPEN" not in response.text


async def test_empty_state_when_no_projects(client: AsyncClient) -> None:
    """With no projects, the gallery shows the empty state and New Project CTA."""
    response = await client.get("/")

    assert response.status_code == 200
    body = response.text
    assert "No projects yet." in body
    assert "New Project" in body


async def test_default_theme_is_dark(client: AsyncClient) -> None:
    """With no theme cookie the page renders data-theme=\"dark\"."""
    response = await client.get("/")

    assert response.status_code == 200
    assert 'data-theme="dark"' in response.text


async def test_theme_cookie_renders_light(client: AsyncClient) -> None:
    """A theme=light cookie renders data-theme=\"light\" server-side."""
    response = await client.get("/", headers={"Cookie": "theme=light"})

    assert response.status_code == 200
    assert 'data-theme="light"' in response.text


async def test_invalid_theme_cookie_falls_back_to_dark(client: AsyncClient) -> None:
    """An unrecognized theme cookie falls back to the dark default."""
    response = await client.get("/", headers={"Cookie": "theme=neon"})

    assert response.status_code == 200
    assert 'data-theme="dark"' in response.text
