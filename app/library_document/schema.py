from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.file.schema import FileRead


class LibraryDocumentVersionRead(BaseModel):
    """Public representation of a Library Document Version."""

    id: int
    library_document_id: int
    version_number: int
    file: FileRead
    version_note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LibraryDocumentRead(BaseModel):
    """Public representation of a Library Document and its current version."""

    id: int
    title: str
    description: str | None
    current_version: LibraryDocumentVersionRead
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
