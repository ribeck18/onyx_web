from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.file.schema import FileRead
from app.vdi.submit_status import SubmitStatus


class RevisionRead(BaseModel):
    id: int
    vendor_data_item_id: int
    revision_number: int
    submit_file: FileRead
    submitted_at: datetime
    return_document: str | None
    returned_at: datetime | None
    comments: str | None
    status: SubmitStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
