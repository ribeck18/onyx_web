from __future__ import annotations

from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.file import service as file_service
from app.file.dependencies import get_storage_root
from app.library_document import service
from app.library_document.schema import LibraryDocumentRead

router = APIRouter(prefix="/library-documents", tags=["library-documents"])


@router.post("", response_model=LibraryDocumentRead, status_code=status.HTTP_201_CREATED)
async def create_library_document(
    title: str = Form(..., min_length=1),
    file: UploadFile = File(...),
    description: str | None = Form(None),
    version_note: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    storage_root: Path = Depends(get_storage_root),
) -> LibraryDocumentRead:
    """Create a Library Document with its required file-backed Version 1."""
    title = title.strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Title must not be blank",
        )
    stored_file = await file_service.save_upload(session, file, storage_root)
    library_document = await service.create_library_document(
        session,
        title=title,
        file=stored_file,
        description=description,
        version_note=version_note,
    )
    await session.commit()
    return LibraryDocumentRead.model_validate(library_document)


@router.get("", response_model=list[LibraryDocumentRead])
async def list_library_documents(
    session: AsyncSession = Depends(get_session),
) -> list[LibraryDocumentRead]:
    """Return every Library Document alphabetically by title."""
    library_documents = await service.get_library_documents(session)
    return [
        LibraryDocumentRead.model_validate(library_document)
        for library_document in library_documents
    ]


@router.get("/{library_document_id}", response_model=LibraryDocumentRead)
async def get_library_document(
    library_document_id: int,
    session: AsyncSession = Depends(get_session),
) -> LibraryDocumentRead:
    """Return one Library Document with its current version."""
    library_document = await service.get_library_document(session, library_document_id)
    if library_document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Library document not found",
        )
    return LibraryDocumentRead.model_validate(library_document)
