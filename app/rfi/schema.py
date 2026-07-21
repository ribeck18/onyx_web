from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.rfi.status import RfiStatus


class RfiCreate(BaseModel):
    """Fields required to create a project-scoped RFI."""

    project_id: int
    rfi_number: str = Field(min_length=1)
    title: str = Field(min_length=1)
    spec_drawing_reference: str | None = None
    notes: str | None = None


class RfiUpdate(BaseModel):
    """Editable RFI metadata; lifecycle status is intentionally omitted."""

    rfi_number: str | None = Field(default=None, min_length=1)
    title: str | None = Field(default=None, min_length=1)
    spec_drawing_reference: str | None = None
    notes: str | None = None


class RfiRead(BaseModel):
    """Public representation of an RFI."""

    id: int
    project_id: int
    rfi_number: str
    title: str
    spec_drawing_reference: str | None
    notes: str | None
    status: RfiStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
