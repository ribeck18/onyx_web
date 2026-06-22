from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UserRead(BaseModel):
    """Public view of a User — never exposes the Entra ``oid`` binding detail."""

    id: int
    email: str
    display_name: str | None
    is_admin: bool
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None

    model_config = {"from_attributes": True}
