from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, computed_field


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

    @computed_field
    @property
    def has_logged_in(self) -> bool:
        """Whether this person has ever completed a Microsoft login.

        A provisioned-but-never-signed-in row has no ``last_login_at`` yet; that
        is the row an admin may still hard-delete.
        """
        return self.last_login_at is not None


class UserProvision(BaseModel):
    """Admin request to provision a User by email before their first login."""

    email: str
    display_name: str | None = None
    is_admin: bool = False
