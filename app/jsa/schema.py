from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.file.schema import FileRead
from app.jsa.status import JsaStatus
from app.models.jsa_file import JsaFileGroup


class JsaNotesUpdate(BaseModel):
    notes: str | None = None


class JsaFileRead(BaseModel):
    id: int
    file_group: JsaFileGroup
    position: int
    file: FileRead

    model_config = {"from_attributes": True}


class JsaRevisionRead(BaseModel):
    id: int
    revision_number: int
    status: JsaStatus
    submitted_at: datetime
    decided_at: datetime | None
    comments: str | None
    file_links: list[JsaFileRead]

    model_config = {"from_attributes": True}


class JsaRead(BaseModel):
    id: int
    project_id: int
    status: JsaStatus
    notes: str | None
    revisions: list[JsaRevisionRead]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
