from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doc_version import DocVersion
from app.models.project_doc import ProjectDoc
from app.project_doc.document_type import DocumentType
from app.project_doc.schema import DocVersionUpdate, ProjectDocUpdate

if TYPE_CHECKING:
    from app.models.file import File


async def create_project_doc(
    session: AsyncSession,
    project_id: int,
    label: str,
    document_type: DocumentType,
    file: File,
    doc_number: str | None = None,
    description: str | None = None,
) -> ProjectDoc:
    """Create a ProjectDoc together with its Version 1 and flush.

    A ProjectDoc can never exist with zero versions (ADR 0011), so the document
    and its first version are added in one flush; the route commits them
    atomically. The version number is always server-assigned, starting at 1.
    """
    project_doc = ProjectDoc(
        project_id=project_id,
        label=label,
        type=document_type,
        doc_number=doc_number,
        description=description,
    )
    project_doc.versions.append(
        DocVersion(
            version_number=1,
            file=file,
        )
    )
    session.add(project_doc)
    await session.flush()
    return project_doc


async def get_project_doc(
    session: AsyncSession, project_doc_id: int
) -> ProjectDoc | None:
    """Return a single project document by ID, or None if not found."""
    result = await session.execute(
        select(ProjectDoc).where(ProjectDoc.id == project_doc_id)
    )
    return result.scalar_one_or_none()


async def get_project_docs(
    session: AsyncSession, project_id: int
) -> list[ProjectDoc]:
    """Return all project documents belonging to one project."""
    result = await session.execute(
        select(ProjectDoc)
        .where(ProjectDoc.project_id == project_id)
        .order_by(ProjectDoc.label)
    )
    return list(result.scalars().all())


async def update_project_doc(
    session: AsyncSession,
    project_doc: ProjectDoc,
    data: ProjectDocUpdate,
) -> ProjectDoc:
    """Apply partial updates to a document's metadata and flush.

    A ProjectDoc has no approval lifecycle, so every metadata field stays
    freely editable with no field-locking (unlike VDI submission fields).
    """
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project_doc, field, value)
    project_doc.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return project_doc


async def delete_project_doc(session: AsyncSession, project_doc: ProjectDoc) -> None:
    """Delete a document; ORM cascade removes all of its versions."""
    await session.delete(project_doc)
    await session.flush()


async def add_version(
    session: AsyncSession,
    project_doc: ProjectDoc,
    file: File,
    description: str | None = None,
) -> DocVersion:
    """Record the next version of a document and flush.

    The version number is always server-assigned as max-existing-plus-one
    (ADR 0002/0011) — callers never hand one in. The parent document's
    updated_at is bumped so it reflects its latest version; both are flushed
    together so the route commits them atomically.
    """
    doc_version = DocVersion(
        version_number=project_doc.current_version.version_number + 1,
        file=file,
        description=description,
    )
    project_doc.versions.append(doc_version)
    project_doc.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return doc_version


async def get_versions(
    session: AsyncSession, project_doc_id: int
) -> list[DocVersion]:
    """Return a document's versions, oldest first."""
    result = await session.execute(
        select(DocVersion)
        .where(DocVersion.project_doc_id == project_doc_id)
        .order_by(DocVersion.version_number)
    )
    return list(result.scalars().all())


async def get_version(
    session: AsyncSession, project_doc_id: int, version_id: int
) -> DocVersion | None:
    """Return one version scoped to its parent document, or None if not found."""
    result = await session.execute(
        select(DocVersion).where(
            DocVersion.id == version_id,
            DocVersion.project_doc_id == project_doc_id,
        )
    )
    return result.scalar_one_or_none()


async def update_version(
    session: AsyncSession,
    doc_version: DocVersion,
    data: DocVersionUpdate,
) -> DocVersion:
    """Apply a partial update to a version's description and flush.

    A version is immutable except for its description — the file and
    server-assigned version number never change (ADR 0011).
    """
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(doc_version, field, value)
    await session.flush()
    return doc_version


async def delete_version(session: AsyncSession, doc_version: DocVersion) -> None:
    """Delete one version; callers must reject deleting the last one first."""
    await session.delete(doc_version)
    await session.flush()
