from __future__ import annotations

from pathlib import Path

from httpx import AsyncClient


async def create_library_document(client: AsyncClient) -> dict[str, object]:
    """Create one Library Document with a Version 1 note."""
    response = await client.post(
        "/api/library-documents",
        data={
            "title": "Cover Sheet",
            "description": "Original description",
            "version_note": "Initial note",
        },
        files={"file": ("cover-v1.pdf", b"version one", "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()


async def add_version(
    client: AsyncClient,
    library_document_id: int,
) -> dict[str, object]:
    """Create Version 2 so Version 1 becomes historical."""
    response = await client.post(
        f"/api/library-documents/{library_document_id}/versions",
        data={"version_note": "Current note"},
        files={"file": ("cover-v2.pdf", b"version two", "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()


async def test_metadata_update_does_not_create_a_version(client: AsyncClient) -> None:
    """Title and description are independent of file history."""
    document = await create_library_document(client)

    response = await client.patch(
        f"/api/library-documents/{document['id']}",
        json={"title": "Renamed Cover Sheet", "description": "Revised description"},
    )
    versions_response = await client.get(
        f"/api/library-documents/{document['id']}/versions"
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Renamed Cover Sheet"
    assert response.json()["description"] == "Revised description"
    assert response.json()["current_version"]["id"] == document["current_version"]["id"]
    assert [version["version_number"] for version in versions_response.json()] == [1]


async def test_only_current_version_note_can_be_edited(client: AsyncClient) -> None:
    """Historical Version Notes stay immutable after a newer upload."""
    document = await create_library_document(client)
    current_version = await add_version(client, document["id"])

    current_response = await client.patch(
        f"/api/library-documents/{document['id']}/versions/{current_version['id']}",
        json={"version_note": "Corrected current note"},
    )
    historical_response = await client.patch(
        f"/api/library-documents/{document['id']}/versions/"
        f"{document['current_version']['id']}",
        json={"version_note": "Rewrite history"},
    )
    empty_note_response = await client.patch(
        f"/api/library-documents/{document['id']}/versions/{current_version['id']}",
        json={},
    )
    versions_response = await client.get(
        f"/api/library-documents/{document['id']}/versions"
    )

    assert current_response.status_code == 200
    assert current_response.json()["version_note"] == "Corrected current note"
    assert historical_response.status_code == 409
    assert empty_note_response.status_code == 422
    assert versions_response.json()[0]["version_note"] == "Initial note"
    assert versions_response.json()[1]["version_note"] == "Corrected current note"


async def test_delete_removes_document_history_without_version_delete_api(
    client: AsyncClient,
    tmp_path: Path,
) -> None:
    """Only whole-document deletion is exposed to the API."""
    document = await create_library_document(client)
    current_version = await add_version(client, document["id"])

    assert len(list(tmp_path.iterdir())) == 2

    version_delete = await client.delete(
        f"/api/library-documents/{document['id']}/versions/{current_version['id']}"
    )
    delete_response = await client.delete(f"/api/library-documents/{document['id']}")
    document_response = await client.get(f"/api/library-documents/{document['id']}")
    versions_response = await client.get(
        f"/api/library-documents/{document['id']}/versions"
    )
    file_response = await client.get(f"/api/files/{current_version['file']['id']}")

    assert version_delete.status_code == 405
    assert delete_response.status_code == 204
    assert document_response.status_code == 404
    assert versions_response.status_code == 404
    assert file_response.status_code == 404
    assert list(tmp_path.iterdir()) == []
