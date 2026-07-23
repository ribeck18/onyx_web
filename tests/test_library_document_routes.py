from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def create_form(**overrides: object) -> dict[str, object]:
    """Build valid multipart fields for POST /api/library-documents."""
    form: dict[str, object] = {"title": "Cover Sheet"}
    form.update(overrides)
    return form


async def create_library_document(
    client: AsyncClient,
    **overrides: object,
) -> dict[str, object]:
    """POST a valid Library Document and return its response body."""
    response = await client.post(
        "/api/library-documents",
        data=create_form(**overrides),
        files={"file": ("cover-sheet.pdf", b"template bytes", "application/pdf")},
    )
    assert response.status_code == 201
    return response.json()


async def test_create_makes_version_1_with_optional_metadata(
    client: AsyncClient,
) -> None:
    """A Library Document is created together with its required Version 1."""
    body = await create_library_document(
        client,
        description="Used for every project.",
        version_note="Initial release",
    )

    assert body["title"] == "Cover Sheet"
    assert body["description"] == "Used for every project."
    assert body["current_version"]["version_number"] == 1
    assert body["current_version"]["version_note"] == "Initial release"
    assert body["current_version"]["file"]["original_name"] == "cover-sheet.pdf"
    assert "project_id" not in body
    assert "status" not in body


async def test_create_allows_duplicate_titles(client: AsyncClient) -> None:
    """Library Document titles are descriptive, not a uniqueness constraint."""
    await create_library_document(client)
    second = await create_library_document(client)

    assert second["title"] == "Cover Sheet"


async def test_title_and_file_are_required(client: AsyncClient) -> None:
    """The create API rejects blank titles and a missing initial file."""
    blank_title = await client.post(
        "/api/library-documents",
        data=create_form(title="   "),
        files={"file": ("cover-sheet.pdf", b"template bytes", "application/pdf")},
    )
    missing_file = await client.post(
        "/api/library-documents",
        data=create_form(),
    )

    assert blank_title.status_code == 422
    assert missing_file.status_code == 422


async def test_empty_file_persists_no_document_or_version(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """The file storage seam rejects empty uploads before Library rows exist."""
    response = await client.post(
        "/api/library-documents",
        data=create_form(),
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
    document_count = await session.execute(
        text("SELECT COUNT(*) FROM library_documents")
    )
    version_count = await session.execute(
        text("SELECT COUNT(*) FROM library_document_versions")
    )
    assert document_count.scalar_one() == 0
    assert version_count.scalar_one() == 0


async def test_list_is_alphabetical(client: AsyncClient) -> None:
    """The JSON list shares the Library page's alphabetical ordering."""
    await create_library_document(client, title="Zulu Form")
    await create_library_document(client, title="Alpha Form")

    response = await client.get("/api/library-documents")

    assert response.status_code == 200
    assert [document["title"] for document in response.json()] == [
        "Alpha Form",
        "Zulu Form",
    ]
