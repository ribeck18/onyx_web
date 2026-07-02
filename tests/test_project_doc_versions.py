from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_project_doc_routes import create_doc, seed_project


async def add_version(
    client: AsyncClient,
    project_doc_id: int,
    content: bytes = b"newer bytes",
    filename: str = "e101_rev.pdf",
    data: dict[str, object] | None = None,
) -> dict[str, object]:
    """POST a valid new version and return the response body."""
    response = await client.post(
        f"/api/project-docs/{project_doc_id}/versions",
        data=data or {},
        files={"file": (filename, content, "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()


async def test_version_numbers_increment_across_versions(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Each added version gets the next server-assigned number (2, 3, ...)."""
    project_id = await seed_project(session)
    doc = await create_doc(client, project_id)

    second = await add_version(client, doc["id"])
    third = await add_version(client, doc["id"])

    assert second["version_number"] == 2
    assert third["version_number"] == 3


async def test_client_supplied_version_number_is_ignored(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A hand-typed version_number in the form has no effect (ADR 0002/0011)."""
    project_id = await seed_project(session)
    doc = await create_doc(client, project_id)

    body = await add_version(client, doc["id"], data={"version_number": "99"})

    assert body["version_number"] == 2


async def test_latest_version_becomes_current_and_bumps_updated_at(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The document's current version tracks the newest one and updated_at moves."""
    project_id = await seed_project(session)
    doc = await create_doc(client, project_id)

    await add_version(
        client, doc["id"], data={"description": "issued for construction"}
    )

    response = await client.get(f"/api/project-docs/{doc['id']}")
    body = response.json()
    assert body["current_version"]["version_number"] == 2
    assert body["current_version"]["description"] == "issued for construction"
    assert body["updated_at"] > doc["updated_at"]


async def test_add_version_unknown_document_returns_404(
    client: AsyncClient,
) -> None:
    """Adding a version to a non-existent document is a 404."""
    response = await client.post(
        "/api/project-docs/999/versions",
        files={"file": ("v2.pdf", b"bytes", "application/pdf")},
    )
    assert response.status_code == 404


async def test_add_version_missing_or_empty_file_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A missing file part is a 422 and an empty upload is a 400."""
    project_id = await seed_project(session)
    doc = await create_doc(client, project_id)

    missing = await client.post(f"/api/project-docs/{doc['id']}/versions")
    assert missing.status_code == 422

    empty = await client.post(
        f"/api/project-docs/{doc['id']}/versions",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert empty.status_code == 400

    versions = await client.get(f"/api/project-docs/{doc['id']}/versions")
    assert len(versions.json()) == 1


async def test_list_versions_returns_history_oldest_first(
    client: AsyncClient, session: AsyncSession
) -> None:
    """GET /versions lists the full history in version order; unknown doc is 404."""
    project_id = await seed_project(session)
    doc = await create_doc(client, project_id)
    await add_version(client, doc["id"])

    response = await client.get(f"/api/project-docs/{doc['id']}/versions")

    assert response.status_code == 200
    numbers = [version["version_number"] for version in response.json()]
    assert numbers == [1, 2]

    missing = await client.get("/api/project-docs/999/versions")
    assert missing.status_code == 404


async def test_get_version_scoped_to_parent_document(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A version is fetchable under its own document and 404 under another."""
    project_id = await seed_project(session)
    first_doc = await create_doc(client, project_id)
    second_doc = await create_doc(client, project_id, label="E-102")
    version = await add_version(client, first_doc["id"])

    owned = await client.get(
        f"/api/project-docs/{first_doc['id']}/versions/{version['id']}"
    )
    assert owned.status_code == 200
    assert owned.json()["id"] == version["id"]

    foreign = await client.get(
        f"/api/project-docs/{second_doc['id']}/versions/{version['id']}"
    )
    assert foreign.status_code == 404


async def test_new_version_file_round_trips_and_old_version_immutable(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The new version's file downloads intact and Version 1 keeps its own file."""
    project_id = await seed_project(session)
    original_content = b"version one bytes"
    doc = await create_doc(client, project_id, content=original_content)
    original_file_id = doc["current_version"]["file"]["id"]

    new_content = b"version two bytes"
    version = await add_version(client, doc["id"], content=new_content)

    assert "stored_path" not in version["file"]
    assert version["file"]["id"] != original_file_id

    new_download = await client.get(f"/api/files/{version['file']['id']}")
    assert new_download.content == new_content
    old_download = await client.get(f"/api/files/{original_file_id}")
    assert old_download.content == original_content
