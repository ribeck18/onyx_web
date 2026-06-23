from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.api_token import ApiToken
    from app.models.session import Session


class User(Base):
    """A person allowed to use Onyx (ADR 0007).

    Keyed canonically on the immutable Entra ``oid``; ``email`` is held only for
    provisioning and display. A provisioned row starts with an email and no
    ``entra_oid`` and binds the ``oid`` on first successful login. ``is_active``
    is the revocation lever — flipping it off immediately invalidates the user's
    sessions and tokens.
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("entra_oid", name="uq_user_entra_oid"),
        UniqueConstraint("email", name="uq_user_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entra_oid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    sessions: Mapped[list["Session"]] = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    api_tokens: Mapped[list["ApiToken"]] = relationship(
        "ApiToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )
