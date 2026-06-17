from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_project


def vdi_payload(project_id: int, **overrides: object) -> dict[str, object]:
    """Build a valid POST /vdi body for the given project."""
    payload: dict[str, object] = {
        "project_id": project_id,
        "item_number": 1,
        "name": "Concrete Mix Design",
        "approval_type": "mandatory_approval",
        "submit_code": "ptc",
    }
    payload.update(overrides)
    return payload


async def seed_project(session: AsyncSession, **kwargs: str) -> int:
    """Persist a project for the route tests and return its id."""
    project = make_project(**kwargs)
    session.add(project)
    await session.flush()
    return project.id


async def test_create_vdi_returns_201_with_not_started(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A valid POST creates the VDI in NOT_STARTED and echoes it back."""
    project_id = await seed_project(session)

    response = await client.post("/vdi", json=vdi_payload(project_id))

    assert response.status_code == 201
    body = response.json()
    assert body["project_id"] == project_id
    assert body["item_number"] == 1
    assert body["status"] == "not_started"
    assert body["approval_type"] == "mandatory_approval"
    assert body["submit_code"] == "ptc"


async def test_create_vdi_unknown_project_returns_404(
    client: AsyncClient,
) -> None:
    """Creating against a non-existent project is a 404."""
    response = await client.post("/vdi", json=vdi_payload(999))

    assert response.status_code == 404


async def test_duplicate_item_number_in_project_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A second VDI with the same item number in the project is rejected."""
    project_id = await seed_project(session)

    first = await client.post("/vdi", json=vdi_payload(project_id, item_number=5))
    assert first.status_code == 201

    second = await client.post("/vdi", json=vdi_payload(project_id, item_number=5))
    assert second.status_code == 409


async def test_same_item_number_allowed_across_projects(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The same item number can be reused on a different project."""
    project_one = await seed_project(session, project_number="P-001")
    project_two = await seed_project(session, project_number="P-002")

    first = await client.post("/vdi", json=vdi_payload(project_one, item_number=7))
    second = await client.post("/vdi", json=vdi_payload(project_two, item_number=7))

    assert first.status_code == 201
    assert second.status_code == 201


async def test_get_vdi_returns_the_vdi(
    client: AsyncClient, session: AsyncSession
) -> None:
    """GET /vdi/{id} returns the created vendor data item."""
    project_id = await seed_project(session)
    created = await client.post("/vdi", json=vdi_payload(project_id))
    vdi_id = created.json()["id"]

    response = await client.get(f"/vdi/{vdi_id}")

    assert response.status_code == 200
    assert response.json()["id"] == vdi_id


async def test_get_unknown_vdi_returns_404(client: AsyncClient) -> None:
    """An unknown VDI id is a 404."""
    response = await client.get("/vdi/999")

    assert response.status_code == 404
