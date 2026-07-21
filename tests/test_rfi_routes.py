from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_project


def rfi_payload(project_id: int, **overrides: object) -> dict[str, object]:
    """Build a valid RFI API payload for one project."""
    payload: dict[str, object] = {
        "project_id": project_id,
        "rfi_number": "RFI-001",
        "title": "Clarify foundation elevation",
    }
    payload.update(overrides)
    return payload


async def seed_project(session: AsyncSession, project_number: str = "P-001") -> int:
    """Persist one project and return its ID."""
    project = make_project(project_number=project_number)
    session.add(project)
    await session.flush()
    return project.id


async def test_rfi_crud_and_validation(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """RFIs validate required identity fields and support public CRUD endpoints."""
    project_id = await seed_project(session)

    missing = await client.post("/api/rfis", json={"project_id": project_id})
    assert missing.status_code == 422
    empty = await client.post(
        "/api/rfis", json=rfi_payload(project_id, rfi_number="")
    )
    assert empty.status_code == 422
    for field in ("rfi_number", "title"):
        whitespace = await client.post(
            "/api/rfis", json=rfi_payload(project_id, **{field: "  \t  "})
        )
        assert whitespace.status_code == 422

    created = await client.post(
        "/api/rfis",
        json=rfi_payload(
            project_id,
            spec_drawing_reference="S-101",
            notes="Coordinate with structural engineer",
        ),
    )
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "not_started"
    assert body["rfi_number"] == "RFI-001"
    rfi_id = body["id"]

    read = await client.get(f"/api/rfis/{rfi_id}")
    assert read.status_code == 200
    assert read.json()["title"] == "Clarify foundation elevation"

    updated = await client.patch(
        f"/api/rfis/{rfi_id}",
        json={
            "rfi_number": "RFI-011",
            "title": "Clarify finished floor elevation",
            "notes": "Urgent",
            "status": "approved",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["rfi_number"] == "RFI-011"
    assert updated.json()["title"] == "Clarify finished floor elevation"
    assert updated.json()["notes"] == "Urgent"
    assert updated.json()["status"] == "not_started"

    cleared = await client.patch(
        f"/api/rfis/{rfi_id}", json={"spec_drawing_reference": None}
    )
    assert cleared.status_code == 200
    assert cleared.json()["spec_drawing_reference"] is None

    for field in ("rfi_number", "title"):
        null_update = await client.patch(f"/api/rfis/{rfi_id}", json={field: None})
        assert null_update.status_code == 422

    deleted = await client.delete(f"/api/rfis/{rfi_id}")
    assert deleted.status_code == 204
    assert (await client.get(f"/api/rfis/{rfi_id}")).status_code == 404


async def test_rfi_number_is_project_unique_and_patch_reports_conflicts(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """Duplicate RFI Numbers conflict only within their project on create and edit."""
    first_project_id = await seed_project(session, "P-001")
    second_project_id = await seed_project(session, "P-002")
    first = await client.post("/api/rfis", json=rfi_payload(first_project_id))
    assert first.status_code == 201
    duplicate = await client.post("/api/rfis", json=rfi_payload(first_project_id))
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "RFI number already used in this project"
    assert (
        await client.post("/api/rfis", json=rfi_payload(second_project_id))
    ).status_code == 201

    second = await client.post(
        "/api/rfis", json=rfi_payload(first_project_id, rfi_number="RFI-002")
    )
    conflict = await client.patch(
        f"/api/rfis/{second.json()['id']}", json={"rfi_number": "RFI-001"}
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "RFI number already used in this project"


async def test_rfi_flush_integrity_errors_report_duplicate_conflicts(
    client: AsyncClient,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duplicate constraints raised during a flush return the usual conflict."""
    project_id = await seed_project(session)

    async def raise_integrity_error(
        *arguments: object,
        **keyword_arguments: object,
    ) -> None:
        """Simulate the database uniqueness constraint at the flush boundary."""
        raise IntegrityError("insert", {}, Exception("unique constraint"))

    monkeypatch.setattr("app.rfi.router.service.create_rfi", raise_integrity_error)
    create_response = await client.post("/api/rfis", json=rfi_payload(project_id))
    assert create_response.status_code == 409
    assert create_response.json()["detail"] == "RFI number already used in this project"

    monkeypatch.undo()
    created = await client.post("/api/rfis", json=rfi_payload(project_id))
    assert created.status_code == 201

    monkeypatch.setattr("app.rfi.router.service.update_rfi", raise_integrity_error)
    update_response = await client.patch(
        f"/api/rfis/{created.json()['id']}",
        json={"rfi_number": "RFI-002"},
    )
    assert update_response.status_code == 409
    assert update_response.json()["detail"] == "RFI number already used in this project"


async def test_rfi_list_orders_and_scopes_to_project(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """The collection requires a project and orders its free-form numbers ascending."""
    first_project_id = await seed_project(session, "P-001")
    second_project_id = await seed_project(session, "P-002")
    for rfi_number in ("RFI-010", "RFI-002", "RFI-001"):
        response = await client.post(
            "/api/rfis", json=rfi_payload(first_project_id, rfi_number=rfi_number)
        )
        assert response.status_code == 201
    await client.post("/api/rfis", json=rfi_payload(second_project_id))

    response = await client.get("/api/rfis", params={"project_id": first_project_id})
    assert response.status_code == 200
    assert [rfi["rfi_number"] for rfi in response.json()] == [
        "RFI-001",
        "RFI-002",
        "RFI-010",
    ]
    assert (await client.get("/api/rfis")).status_code == 422


async def test_project_delete_cascades_to_rfis(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """Deleting a project makes every project-owned RFI unreachable."""
    project_id = await seed_project(session)
    created = await client.post("/api/rfis", json=rfi_payload(project_id))
    rfi_id = created.json()["id"]

    response = await client.delete(f"/api/projects/{project_id}")

    assert response.status_code == 204
    assert (await client.get(f"/api/rfis/{rfi_id}")).status_code == 404
