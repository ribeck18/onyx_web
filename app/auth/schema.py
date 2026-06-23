from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, computed_field

from app.auth import service as auth_service


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


class ApiTokenCreate(BaseModel):
    """Request to create a named per-user API token."""

    name: str


class ApiTokenRead(BaseModel):
    """PAT metadata shown after creation; never includes the raw secret."""

    id: int
    name: str
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def is_revoked(self) -> bool:
        """Whether this token has been explicitly revoked."""
        return self.revoked_at is not None

    @computed_field
    @property
    def is_expired(self) -> bool:
        """Whether this token is past its fixed 90-day lifetime."""
        expires_at = auth_service._as_utc(self.expires_at)
        return datetime.now(timezone.utc) >= expires_at

    @computed_field
    @property
    def expires_soon(self) -> bool:
        """Whether an active token is close enough to expiry to warn the user."""
        if self.is_revoked or self.is_expired:
            return False
        expires_at = auth_service._as_utc(self.expires_at)
        return (
            expires_at - datetime.now(timezone.utc)
            <= auth_service.API_TOKEN_EXPIRY_WARNING
        )


class ApiTokenCreated(ApiTokenRead):
    """Creation response that includes the raw secret once."""

    secret: str
