from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.file import service as file_service
from app.file.dependencies import get_storage_root
from app.project import service as project_service
from app.project_doc import service
from app.project_doc.document_type import DocumentType
from app.project_doc.schema import (
    DocVersionRead,
    DocVersionUpdate,
    ProjectDocRead,
    ProjectDocUpdate,
)

router = APIRouter(prefix="/project-docs", tags=["project-docs"])


@router.post("", response_model=ProjectDocRead, status_code=status.HTTP_201_CREATED)
async def create_project_doc(
    project_id: int = Form(...),
    label: str = Form(...),
    type: DocumentType = Form(...),
    file: UploadFile = File(...),
    doc_number: str | None = Form(None),
    description: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    storage_root: Path = Depends(get_storage_root),
) -> ProjectDocRead:
    """Create a project document with its Version 1 and file, atomically.

    The project check runs before the file is saved so a rejected create (404)
    never writes orphaned bytes; save_upload then rejects an empty upload (400).
    """
    project = await project_service.get_project(session, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    stored_file = await file_service.save_upload(session, file, storage_root)
    project_doc = await service.create_project_doc(
        session,
        project_id=project_id,
        label=label,
        document_type=type,
        file=stored_file,
        doc_number=doc_number,
        description=description,
    )
    await session.commit()
    return ProjectDocRead.model_validate(project_doc)


@router.post(
    "/{project_doc_id}/versions",
    response_model=DocVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_version(
    project_doc_id: int,
    file: UploadFile = File(...),
    description: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    storage_root: Path = Depends(get_storage_root),
) -> DocVersionRead:
    """Record the next version of a document with a server-assigned number.

    The document check runs before the file is saved so a rejected add (404)
    never writes orphaned bytes; save_upload then rejects an empty upload (400).
    """
    project_doc = await service.get_project_doc(session, project_doc_id)
    if project_doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project document not found"
        )
    stored_file = await file_service.save_upload(session, file, storage_root)
    doc_version = await service.add_version(
        session, project_doc, stored_file, description
    )
    await session.commit()
    return DocVersionRead.model_validate(doc_version)


@router.get("/{project_doc_id}/versions", response_model=list[DocVersionRead])
async def list_versions(
    project_doc_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[DocVersionRead]:
    """Return a document's versions, oldest first."""
    project_doc = await service.get_project_doc(session, project_doc_id)
    if project_doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project document not found"
        )
    doc_versions = await service.get_versions(session, project_doc_id)
    return [DocVersionRead.model_validate(doc_version) for doc_version in doc_versions]


@router.get("/{project_doc_id}/versions/{version_id}", response_model=DocVersionRead)
async def get_version(
    project_doc_id: int,
    version_id: int,
    session: AsyncSession = Depends(get_session),
) -> DocVersionRead:
    """Return a single version, scoped to its parent document."""
    doc_version = await service.get_version(session, project_doc_id, version_id)
    if doc_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found"
        )
    return DocVersionRead.model_validate(doc_version)


@router.get("", response_model=list[ProjectDocRead])
async def list_project_docs(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[ProjectDocRead]:
    """Return the project documents in one project (project_id is required)."""
    project_docs = await service.get_project_docs(session, project_id)
    return [ProjectDocRead.model_validate(project_doc) for project_doc in project_docs]


@router.get("/{project_doc_id}", response_model=ProjectDocRead)
async def get_project_doc(
    project_doc_id: int,
    session: AsyncSession = Depends(get_session),
) -> ProjectDocRead:
    """Return a single project document with its current version."""
    project_doc = await service.get_project_doc(session, project_doc_id)
    if project_doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project document not found"
        )
    return ProjectDocRead.model_validate(project_doc)


@router.patch("/{project_doc_id}", response_model=ProjectDocRead)
async def update_project_doc(
    project_doc_id: int,
    data: ProjectDocUpdate,
    session: AsyncSession = Depends(get_session),
) -> ProjectDocRead:
    """Partially update a document's metadata (no field-locking)."""
    project_doc = await service.get_project_doc(session, project_doc_id)
    if project_doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project document not found"
        )
    project_doc = await service.update_project_doc(session, project_doc, data)
    await session.commit()
    return ProjectDocRead.model_validate(project_doc)


@router.delete("/{project_doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project_doc(
    project_doc_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete a document; the ORM cascade removes all of its versions."""
    project_doc = await service.get_project_doc(session, project_doc_id)
    if project_doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project document not found"
        )
    await service.delete_project_doc(session, project_doc)
    await session.commit()


@router.patch(
    "/{project_doc_id}/versions/{version_id}", response_model=DocVersionRead
)
async def update_version(
    project_doc_id: int,
    version_id: int,
    data: DocVersionUpdate,
    session: AsyncSession = Depends(get_session),
) -> DocVersionRead:
    """Update a version's description; everything else is immutable."""
    doc_version = await service.get_version(session, project_doc_id, version_id)
    if doc_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found"
        )
    doc_version = await service.update_version(session, doc_version, data)
    await session.commit()
    return DocVersionRead.model_validate(doc_version)


@router.delete(
    "/{project_doc_id}/versions/{version_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_version(
    project_doc_id: int,
    version_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    """Delete one version, unless it is the document's last remaining one.

    Deleting the last version would leave the document with zero versions
    (invalid under ADR 0011), so that is rejected with 409 — the user deletes
    the whole document instead.
    """
    doc_version = await service.get_version(session, project_doc_id, version_id)
    if doc_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found"
        )
    remaining_versions = await service.get_versions(session, project_doc_id)
    if len(remaining_versions) == 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a document's last remaining version; "
            "delete the document instead",
        )
    await service.delete_version(session, doc_version)
    await session.commit()
