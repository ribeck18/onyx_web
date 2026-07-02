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
from app.project_doc.schema import ProjectDocRead

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
