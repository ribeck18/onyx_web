from __future__ import annotations

from pydantic import BaseModel


class FileRead(BaseModel):
    """Public view of a stored file. Deliberately omits stored_path, which is an
    internal storage detail callers must never see."""

    id: int
    original_name: str
    content_type: str

    model_config = {"from_attributes": True}
