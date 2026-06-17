from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.vdi.approval_type import ApprovalType
from app.vdi.submit_code import SubmitCode
from app.vdi.submit_status import SubmitStatus


class VdiCreate(BaseModel):
    project_id: int
    item_number: int
    name: str
    approval_type: ApprovalType
    submit_code: SubmitCode
    submittal_number: str | None = None
    description: str | None = None
    spec_drawing_reference: str | None = None
    notes: str | None = None


class VdiRead(BaseModel):
    id: int
    project_id: int
    item_number: int
    submittal_number: str | None
    name: str
    description: str | None
    approval_type: ApprovalType
    submit_code: SubmitCode
    spec_drawing_reference: str | None
    notes: str | None
    status: SubmitStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
