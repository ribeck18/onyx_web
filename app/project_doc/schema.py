from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.file.schema import FileRead
from app.project_doc.document_type import DocumentType


class ProjectDocUpdate(BaseModel):
    label: str | None = None
    type: DocumentType | None = None
    doc_number: str | None = None
    description: str | None = None


class DocVersionUpdate(BaseModel):
    description: str | None = None


class DocVersionRead(BaseModel):
    id: int
    project_doc_id: int
    version_number: int
    file: FileRead
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectDocRead(BaseModel):
    id: int
    project_id: int
    label: str
    type: DocumentType
    doc_number: str | None
    description: str | None
    current_version: DocVersionRead
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
