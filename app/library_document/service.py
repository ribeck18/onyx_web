from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.library_document import LibraryDocument
from app.models.library_document_version import LibraryDocumentVersion
from app.models.file import File


async def create_library_document(
    session: AsyncSession,
    title: str,
    file: File,
    description: str | None = None,
    version_note: str | None = None,
) -> LibraryDocument:
    """Create a Library Document and its required Version 1, then flush."""
    library_document = LibraryDocument(title=title, description=description)
    library_document.versions.append(
        LibraryDocumentVersion(
            version_number=1,
            file=file,
            version_note=version_note,
        )
    )
    session.add(library_document)
    await session.flush()
    return library_document


async def get_library_document(
    session: AsyncSession,
    library_document_id: int,
) -> LibraryDocument | None:
    """Return one Library Document by ID, or None when it does not exist."""
    result = await session.execute(
        select(LibraryDocument).where(LibraryDocument.id == library_document_id)
    )
    return result.scalar_one_or_none()


async def get_library_document_for_update(
    session: AsyncSession,
    library_document_id: int,
) -> LibraryDocument | None:
    """Return one Library Document while locking it for a version upload."""
    result = await session.execute(
        select(LibraryDocument)
        .where(LibraryDocument.id == library_document_id)
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def add_version(
    session: AsyncSession,
    library_document: LibraryDocument,
    file: File,
    version_note: str | None = None,
) -> LibraryDocumentVersion:
    """Record the next Library Document Version and update its parent."""
    library_document_version = LibraryDocumentVersion(
        version_number=library_document.current_version.version_number + 1,
        file=file,
        version_note=version_note,
    )
    library_document.versions.append(library_document_version)
    library_document.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return library_document_version


async def update_library_document(
    session: AsyncSession,
    library_document: LibraryDocument,
    title: str | None = None,
    description: str | None = None,
    update_description: bool = False,
) -> LibraryDocument:
    """Apply supplied Library Document metadata and flush."""
    if title is not None:
        library_document.title = title
    if update_description:
        library_document.description = description
    library_document.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return library_document


async def update_current_version_note(
    session: AsyncSession,
    library_document_version: LibraryDocumentVersion,
    version_note: str | None,
) -> LibraryDocumentVersion:
    """Apply an editable Version Note to the current version and flush."""
    library_document_version.version_note = version_note
    await session.flush()
    return library_document_version


async def delete_library_document(
    session: AsyncSession,
    library_document: LibraryDocument,
) -> None:
    """Delete a Library Document, its versions, and their stored file records."""
    for library_document_version in library_document.versions:
        await session.delete(library_document_version.file)
    await session.delete(library_document)
    await session.flush()


async def get_versions(
    session: AsyncSession,
    library_document_id: int,
) -> list[LibraryDocumentVersion]:
    """Return a Library Document's versions oldest first."""
    result = await session.execute(
        select(LibraryDocumentVersion)
        .where(LibraryDocumentVersion.library_document_id == library_document_id)
        .order_by(LibraryDocumentVersion.version_number)
    )
    return list(result.scalars().all())


async def get_version(
    session: AsyncSession,
    library_document_id: int,
    version_id: int,
) -> LibraryDocumentVersion | None:
    """Return one version scoped to its Library Document, if it exists."""
    result = await session.execute(
        select(LibraryDocumentVersion).where(
            LibraryDocumentVersion.id == version_id,
            LibraryDocumentVersion.library_document_id == library_document_id,
        )
    )
    return result.scalar_one_or_none()


async def get_library_documents(session: AsyncSession) -> list[LibraryDocument]:
    """Return all Library Documents alphabetically by title."""
    result = await session.execute(
        select(LibraryDocument).order_by(LibraryDocument.title)
    )
    return list(result.scalars().all())
