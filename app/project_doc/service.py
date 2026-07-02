from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doc_version import DocVersion
from app.models.project_doc import ProjectDoc
from app.project_doc.document_type import DocumentType

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
