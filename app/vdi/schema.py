from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator

from app.vdi.approval_type import ApprovalType
from app.vdi.submit_code import SubmitCode
from app.vdi.submit_status import SubmitStatus

# Approval is not a separate action: a return carries one of these codes
# (A/D approved, B/C rejected). NOT_STARTED and SUBMITTED are lifecycle states,
# never buyer return codes.
RETURN_CODES = frozenset(
    {SubmitStatus.A, SubmitStatus.B, SubmitStatus.C, SubmitStatus.D}
)


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


class VdiSubmit(BaseModel):
    submit_document: str


class VdiReturn(BaseModel):
    return_code: SubmitStatus
    return_document: str
    comments: str | None = None

    @field_validator("return_code")
    @classmethod
    def return_code_must_be_a_return_code(cls, value: SubmitStatus) -> SubmitStatus:
        """Reject lifecycle states (NOT_STARTED/SUBMITTED) as return codes."""
        if value not in RETURN_CODES:
            raise ValueError("return_code must be one of A, B, C, or D")
        return value


class VdiUpdate(BaseModel):
    """Partial update of a VDI's editable fields.

    Deliberately omits status: status is lifecycle-driven (ADR 0002) and can
    never be set through a generic update.
    """

    item_number: int | None = None
    submittal_number: str | None = None
    name: str | None = None
    description: str | None = None
    approval_type: ApprovalType | None = None
    submit_code: SubmitCode | None = None
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
