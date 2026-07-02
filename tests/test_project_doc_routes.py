from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_project


async def seed_project(session: AsyncSession, **kwargs: str) -> int:
    """Persist a project for the route tests and return its id."""
    project = make_project(**kwargs)
    session.add(project)
    await session.flush()
    return project.id


def create_form(project_id: int, **overrides: object) -> dict[str, object]:
    """Build valid multipart form fields for POST /api/project-docs."""
    form: dict[str, object] = {
        "project_id": str(project_id),
        "label": "E-101",
        "type": "drawing",
    }
    form.update(overrides)
    return form


async def create_doc(
    client: AsyncClient,
    project_id: int,
    content: bytes = b"drawing bytes",
    **overrides: object,
) -> dict[str, object]:
    """POST a valid project document and return the response body."""
    response = await client.post(
        "/api/project-docs",
        data=create_form(project_id, **overrides),
        files={"file": ("e101.pdf", content, "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()


async def test_create_returns_201_with_version_1(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A valid POST creates the document plus Version 1 and echoes both back."""
    project_id = await seed_project(session)

    body = await create_doc(client, project_id, doc_number="DWG-7")

    assert body["project_id"] == project_id
    assert body["label"] == "E-101"
    assert body["type"] == "drawing"
    assert body["doc_number"] == "DWG-7"
    assert body["current_version"]["version_number"] == 1
    assert body["current_version"]["file"]["original_name"] == "e101.pdf"


async def test_create_unknown_project_returns_404(client: AsyncClient) -> None:
    """Creating against a non-existent project is a 404."""
    response = await client.post(
        "/api/project-docs",
        data=create_form(999),
        files={"file": ("e101.pdf", b"bytes", "application/pdf")},
    )
    assert response.status_code == 404


async def test_create_missing_file_returns_422(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A POST without a file part is rejected by validation."""
    project_id = await seed_project(session)

    response = await client.post("/api/project-docs", data=create_form(project_id))

    assert response.status_code == 422


async def test_create_empty_file_returns_400_and_persists_nothing(
    client: AsyncClient, session: AsyncSession
) -> None:
    """An empty upload is a 400 and neither document nor version is persisted."""
    project_id = await seed_project(session)

    response = await client.post(
        "/api/project-docs",
        data=create_form(project_id),
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
    doc_count = await session.execute(text("SELECT COUNT(*) FROM project_docs"))
    assert doc_count.scalar_one() == 0
    version_count = await session.execute(text("SELECT COUNT(*) FROM doc_versions"))
    assert version_count.scalar_one() == 0


async def test_list_returns_only_that_projects_docs(
    client: AsyncClient, session: AsyncSession
) -> None:
    """GET with project_id returns just that project's documents."""
    first_project = await seed_project(session)
    second_project = await seed_project(session, project_number="P-002")
    await create_doc(client, first_project)
    await create_doc(client, second_project, label="C-1", type="contract")

    response = await client.get(
        "/api/project-docs", params={"project_id": first_project}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["label"] == "E-101"


async def test_list_without_project_id_returns_422(client: AsyncClient) -> None:
    """project_id is a required query parameter."""
    response = await client.get("/api/project-docs")

    assert response.status_code == 422


async def test_get_returns_doc_with_current_version(
    client: AsyncClient, session: AsyncSession
) -> None:
    """GET by id returns the document with its current version."""
    project_id = await seed_project(session)
    created = await create_doc(client, project_id)

    response = await client.get(f"/api/project-docs/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["current_version"]["version_number"] == 1


async def test_get_unknown_id_returns_404(client: AsyncClient) -> None:
    """GET for a non-existent document is a 404."""
    response = await client.get("/api/project-docs/999")

    assert response.status_code == 404


async def test_version_file_round_trips_through_file_route(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The uploaded bytes come back via /api/files/{id} without leaking the
    stored path, and a non-PDF type is accepted."""
    project_id = await seed_project(session)
    content = b"col_a,col_b\n1,2\n"
    response = await client.post(
        "/api/project-docs",
        data=create_form(project_id, type="vendor_data_schedule"),
        files={"file": ("schedule.csv", content, "text/csv")},
    )
    assert response.status_code == 201

    file_info = response.json()["current_version"]["file"]
    assert "stored_path" not in file_info
    assert file_info["content_type"] == "text/csv"

    download = await client.get(f"/api/files/{file_info['id']}")
    assert download.status_code == 200
    assert download.content == content


async def test_patch_edits_metadata_with_no_field_locking(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Every metadata field is freely editable at any time (no lifecycle)."""
    project_id = await seed_project(session)
    created = await create_doc(client, project_id, doc_number="DWG-7")

    response = await client.patch(
        f"/api/project-docs/{created['id']}",
        json={
            "label": "E-102",
            "type": "specification",
            "doc_number": "SPEC-1",
            "description": "renumbered by the buyer",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "E-102"
    assert body["type"] == "specification"
    assert body["doc_number"] == "SPEC-1"
    assert body["description"] == "renumbered by the buyer"
    assert body["current_version"]["version_number"] == 1


async def test_patch_unknown_id_returns_404(client: AsyncClient) -> None:
    """PATCH for a non-existent document is a 404."""
    response = await client.patch("/api/project-docs/999", json={"label": "E-102"})

    assert response.status_code == 404


async def test_delete_document_cascades_to_versions(
    client: AsyncClient, session: AsyncSession
) -> None:
    """DELETE removes the document row and every one of its version rows."""
    project_id = await seed_project(session)
    doc = await create_doc(client, project_id)
    await client.post(
        f"/api/project-docs/{doc['id']}/versions",
        files={"file": ("v2.pdf", b"newer bytes", "application/pdf")},
    )

    response = await client.delete(f"/api/project-docs/{doc['id']}")

    assert response.status_code == 204
    doc_count = await session.execute(text("SELECT COUNT(*) FROM project_docs"))
    assert doc_count.scalar_one() == 0
    version_count = await session.execute(text("SELECT COUNT(*) FROM doc_versions"))
    assert version_count.scalar_one() == 0


async def test_delete_unknown_id_returns_404(client: AsyncClient) -> None:
    """DELETE for a non-existent document is a 404."""
    response = await client.delete("/api/project-docs/999")

    assert response.status_code == 404
