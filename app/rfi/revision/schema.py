from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.file.schema import FileRead
from app.rfi.status import RfiStatus


class RfiRevisionRead(BaseModel):
    """Public representation of one submitted RFI revision."""

    id: int
    rfi_id: int
    revision_number: int
    submit_file: FileRead
    submitted_at: datetime
    status: RfiStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
