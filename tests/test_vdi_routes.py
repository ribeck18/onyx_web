from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import text

from app.vdi.approval_type import ApprovalType
from app.vdi.submit_status import SubmitStatus
from tests.factories import make_project, make_revision, make_vdi


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

    response = await client.post("/api/vdi", json=vdi_payload(project_id))

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
    response = await client.post("/api/vdi", json=vdi_payload(999))

    assert response.status_code == 404


async def test_duplicate_item_number_in_project_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A second VDI with the same item number in the project is rejected."""
    project_id = await seed_project(session)

    first = await client.post("/api/vdi", json=vdi_payload(project_id, item_number=5))
    assert first.status_code == 201

    second = await client.post("/api/vdi", json=vdi_payload(project_id, item_number=5))
    assert second.status_code == 409


async def test_same_item_number_allowed_across_projects(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The same item number can be reused on a different project."""
    project_one = await seed_project(session, project_number="P-001")
    project_two = await seed_project(session, project_number="P-002")

    first = await client.post("/api/vdi", json=vdi_payload(project_one, item_number=7))
    second = await client.post("/api/vdi", json=vdi_payload(project_two, item_number=7))

    assert first.status_code == 201
    assert second.status_code == 201


async def test_get_vdi_returns_the_vdi(
    client: AsyncClient, session: AsyncSession
) -> None:
    """GET /vdi/{id} returns the created vendor data item."""
    project_id = await seed_project(session)
    created = await client.post("/api/vdi", json=vdi_payload(project_id))
    vdi_id = created.json()["id"]

    response = await client.get(f"/api/vdi/{vdi_id}")

    assert response.status_code == 200
    assert response.json()["id"] == vdi_id


async def test_get_unknown_vdi_returns_404(client: AsyncClient) -> None:
    """An unknown VDI id is a 404."""
    response = await client.get("/api/vdi/999")

    assert response.status_code == 404


async def test_list_vdis_scoped_to_project(
    client: AsyncClient, session: AsyncSession
) -> None:
    """GET /vdi?project_id= returns only that project's VDIs."""
    project_one = await seed_project(session, project_number="P-001")
    project_two = await seed_project(session, project_number="P-002")
    await client.post("/api/vdi", json=vdi_payload(project_one, item_number=1))
    await client.post("/api/vdi", json=vdi_payload(project_one, item_number=2))
    await client.post("/api/vdi", json=vdi_payload(project_two, item_number=1))

    response = await client.get("/api/vdi", params={"project_id": project_one})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert all(item["project_id"] == project_one for item in body)


async def test_list_vdis_requires_project_id(client: AsyncClient) -> None:
    """A missing project_id is a client error."""
    response = await client.get("/api/vdi")

    assert response.status_code == 422


async def test_patch_updates_only_supplied_fields(
    client: AsyncClient, session: AsyncSession
) -> None:
    """PATCH changes the supplied fields and leaves the rest untouched."""
    project_id = await seed_project(session)
    created = await client.post(
        "/api/vdi", json=vdi_payload(project_id, name="Original", notes="keep me")
    )
    vdi_id = created.json()["id"]

    response = await client.patch(f"/api/vdi/{vdi_id}", json={"name": "Renamed"})

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed"
    assert body["notes"] == "keep me"
    assert body["submit_code"] == "ptc"


async def test_patch_descriptive_field_succeeds_after_submission(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A descriptive field (spec/drawing ref) is editable even once submitted."""
    project = make_project()
    vdi = make_vdi(project, item_number=3, name="Concrete Mix Design")
    vdi.status = SubmitStatus.SUBMITTED
    session.add(vdi)
    await session.flush()
    vdi_id = vdi.id
    await session.commit()

    response = await client.patch(
        f"/api/vdi/{vdi_id}", json={"spec_drawing_reference": "Spec §9.1"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["spec_drawing_reference"] == "Spec §9.1"
    assert body["status"] == "submitted"


async def test_patch_submission_field_succeeds_while_not_started(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A NOT_STARTED VDI's submission fields are freely editable."""
    project_id = await seed_project(session)
    created = await client.post("/api/vdi", json=vdi_payload(project_id, item_number=4))
    vdi_id = created.json()["id"]

    response = await client.patch(
        f"/api/vdi/{vdi_id}",
        json={
            "item_number": 9,
            "approval_type": "information_only",
            "submit_code": "afi",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["item_number"] == 9
    assert body["approval_type"] == "information_only"
    assert body["submit_code"] == "afi"


async def test_patch_locked_field_on_submitted_returns_409(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Changing a submission field once submitted is a 409 conflict."""
    project = make_project()
    vdi = make_vdi(project, item_number=4, name="Concrete Mix Design")
    vdi.status = SubmitStatus.SUBMITTED
    session.add(vdi)
    await session.flush()
    vdi_id = vdi.id
    await session.commit()

    response = await client.patch(f"/api/vdi/{vdi_id}", json={"item_number": 99})

    assert response.status_code == 409


async def test_patch_locked_field_unchanged_value_on_submitted_succeeds(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Resubmitting a locked field with its current value is a no-op, not a 409."""
    project = make_project()
    vdi = make_vdi(project, item_number=4, name="Concrete Mix Design")
    vdi.status = SubmitStatus.SUBMITTED
    vdi.approval_type = ApprovalType.MANDATORY_APPROVAL
    session.add(vdi)
    await session.flush()
    vdi_id = vdi.id
    await session.commit()

    response = await client.patch(
        f"/api/vdi/{vdi_id}",
        json={"item_number": 4, "approval_type": "mandatory_approval", "name": "Renamed"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed"
    assert body["item_number"] == 4


async def test_patch_item_number_collision_returns_409(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Editing item_number onto a sibling's number is rejected like create."""
    project_id = await seed_project(session)
    await client.post("/api/vdi", json=vdi_payload(project_id, item_number=1))
    second = await client.post("/api/vdi", json=vdi_payload(project_id, item_number=2))
    second_id = second.json()["id"]

    response = await client.patch(f"/api/vdi/{second_id}", json={"item_number": 1})

    assert response.status_code == 409
    assert response.json()["detail"] == "Item number already used in this project"


async def test_patch_item_number_unchanged_skips_collision_check(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Resubmitting item_number with its current value is a no-op, not a 409."""
    project_id = await seed_project(session)
    created = await client.post("/api/vdi", json=vdi_payload(project_id, item_number=3))
    vdi_id = created.json()["id"]

    response = await client.patch(
        f"/api/vdi/{vdi_id}", json={"item_number": 3, "name": "Renamed"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["item_number"] == 3
    assert body["name"] == "Renamed"


async def test_patch_item_number_to_free_number_succeeds(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Editing item_number to a number no sibling holds succeeds."""
    project_id = await seed_project(session)
    created = await client.post("/api/vdi", json=vdi_payload(project_id, item_number=3))
    vdi_id = created.json()["id"]

    response = await client.patch(f"/api/vdi/{vdi_id}", json={"item_number": 8})

    assert response.status_code == 200
    assert response.json()["item_number"] == 8


async def test_patch_cannot_set_status(
    client: AsyncClient, session: AsyncSession
) -> None:
    """status is not an editable field; PATCH cannot change it."""
    project_id = await seed_project(session)
    created = await client.post("/api/vdi", json=vdi_payload(project_id))
    vdi_id = created.json()["id"]

    response = await client.patch(f"/api/vdi/{vdi_id}", json={"status": "a"})

    assert response.status_code == 200
    assert response.json()["status"] == "not_started"


async def test_patch_unknown_vdi_returns_404(client: AsyncClient) -> None:
    """Updating an unknown VDI is a 404."""
    response = await client.patch("/api/vdi/999", json={"name": "Nope"})

    assert response.status_code == 404


async def test_delete_returns_204_and_cascades_to_revisions(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DELETE removes the VDI and, through the cascade, its revisions."""
    project = make_project()
    vdi = make_vdi(project)
    revision = make_revision(vdi)
    session.add(revision)
    await session.flush()
    vdi_id = vdi.id

    response = await client.delete(f"/api/vdi/{vdi_id}")

    assert response.status_code == 204
    vdi_count = await session.execute(
        text("SELECT COUNT(*) FROM vendor_data_items WHERE id = :id"), {"id": vdi_id}
    )
    revision_count = await session.execute(text("SELECT COUNT(*) FROM revisions"))
    assert vdi_count.scalar_one() == 0
    assert revision_count.scalar_one() == 0


async def test_delete_unknown_vdi_returns_404(client: AsyncClient) -> None:
    """Deleting an unknown VDI is a 404."""
    response = await client.delete("/api/vdi/999")

    assert response.status_code == 404
