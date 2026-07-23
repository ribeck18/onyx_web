from __future__ import annotations

from httpx import AsyncClient


async def create_library_document(client: AsyncClient) -> dict[str, object]:
    """Create a Library Document with its first PDF version."""
    response = await client.post(
        "/api/library-documents",
        data={"title": "Cover Sheet"},
        files={"file": ("cover-sheet-v1.pdf", b"version one", "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()


async def add_version(
    client: AsyncClient,
    library_document_id: int,
    filename: str = "cover-sheet-v2.pdf",
    content: bytes = b"version two",
    content_type: str = "application/pdf",
    version_note: str | None = "Updated logo",
) -> dict[str, object]:
    """Upload the next Library Document Version and return its response."""
    data = {"version_note": version_note} if version_note else {}
    response = await client.post(
        f"/api/library-documents/{library_document_id}/versions",
        data=data,
        files={"file": (filename, content, content_type)},
    )
    assert response.status_code == 201
    return response.json()


async def test_add_version_assigns_the_next_number_and_updates_current_version(
    client: AsyncClient,
) -> None:
    """Next-version uploads use server numbering and advance the document."""
    document = await create_library_document(client)
    version = await add_version(client, document["id"])
    third_version = await add_version(
        client,
        document["id"],
        filename="cover-sheet-v3.pdf",
    )

    assert version["version_number"] == 2
    assert version["version_note"] == "Updated logo"
    assert version["file"]["original_name"] == "cover-sheet-v2.pdf"
    assert third_version["version_number"] == 3

    document_response = await client.get(f"/api/library-documents/{document['id']}")
    versions_response = await client.get(
        f"/api/library-documents/{document['id']}/versions"
    )

    assert document_response.status_code == 200
    document_body = document_response.json()
    assert document_body["current_version"]["id"] == third_version["id"]
    assert document_body["updated_at"] > document["updated_at"]
    assert [item["version_number"] for item in versions_response.json()] == [1, 2, 3]


async def test_version_upload_requires_a_nonempty_file_and_existing_document(
    client: AsyncClient,
) -> None:
    """Rejected version uploads create neither a version nor useful orphan state."""
    missing_document = await client.post(
        "/api/library-documents/999/versions",
        files={"file": ("new.pdf", b"new", "application/pdf")},
    )
    document = await create_library_document(client)
    empty_file = await client.post(
        f"/api/library-documents/{document['id']}/versions",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    versions_response = await client.get(
        f"/api/library-documents/{document['id']}/versions"
    )

    assert missing_document.status_code == 404
    assert empty_file.status_code == 400
    assert [item["version_number"] for item in versions_response.json()] == [1]


async def test_versions_keep_the_file_service_preview_and_download_rules(
    client: AsyncClient,
) -> None:
    """Every version uses the shared safe inline file-serving behavior."""
    document = await create_library_document(client)
    csv_version = await add_version(
        client,
        document["id"],
        filename="cover-sheet-v2.csv",
        content=b"name,value\ncover,updated\n",
        content_type="text/csv",
    )

    pdf_response = await client.get(
        f"/api/files/{document['current_version']['file']['id']}"
    )
    csv_response = await client.get(f"/api/files/{csv_version['file']['id']}")

    assert pdf_response.headers["content-disposition"].startswith("inline")
    assert csv_response.headers["content-disposition"].startswith("attachment")
    assert csv_response.headers["x-content-type-options"] == "nosniff"
