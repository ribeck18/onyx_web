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
from app.library_document.schema import (
    LibraryDocumentRead,
    LibraryDocumentVersionRead,
)

router = APIRouter(prefix="/library-documents", tags=["library-documents"])


@router.post(
    "",
    response_model=LibraryDocumentRead,
    status_code=status.HTTP_201_CREATED,
)
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


@router.post(
    "/{library_document_id}/versions",
    response_model=LibraryDocumentVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_library_document_version(
    library_document_id: int,
    file: UploadFile = File(...),
    version_note: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    storage_root: Path = Depends(get_storage_root),
) -> LibraryDocumentVersionRead:
    """Upload the next file-backed version for a Library Document."""
    library_document = await service.get_library_document_for_update(
        session,
        library_document_id,
    )
    if library_document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Library document not found",
        )
    stored_file = await file_service.save_upload(session, file, storage_root)
    library_document_version = await service.add_version(
        session,
        library_document,
        stored_file,
        version_note,
    )
    await session.commit()
    return LibraryDocumentVersionRead.model_validate(library_document_version)


@router.get(
    "/{library_document_id}/versions",
    response_model=list[LibraryDocumentVersionRead],
)
async def list_library_document_versions(
    library_document_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[LibraryDocumentVersionRead]:
    """Return a Library Document's versions oldest first."""
    library_document = await service.get_library_document(session, library_document_id)
    if library_document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Library document not found",
        )
    library_document_versions = await service.get_versions(session, library_document_id)
    return [
        LibraryDocumentVersionRead.model_validate(library_document_version)
        for library_document_version in library_document_versions
    ]


@router.get(
    "/{library_document_id}/versions/{version_id}",
    response_model=LibraryDocumentVersionRead,
)
async def get_library_document_version(
    library_document_id: int,
    version_id: int,
    session: AsyncSession = Depends(get_session),
) -> LibraryDocumentVersionRead:
    """Return one version scoped to its Library Document."""
    library_document_version = await service.get_version(
        session,
        library_document_id,
        version_id,
    )
    if library_document_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Library document version not found",
        )
    return LibraryDocumentVersionRead.model_validate(library_document_version)


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
