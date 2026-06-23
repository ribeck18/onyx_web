from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Session(Base):
    """An Onyx-owned browser session, minted after Entra validates a login (ADR 0007).

    Only the *hash* of the opaque cookie token is stored, so a database leak
    yields no usable live credential. ``expires_at`` is the 7-day absolute cap;
    ``last_seen_at`` drives the 8-hour sliding idle window (touched throttled, not
    on every request). Deleting the row revokes the session server-side instantly.
    """

    __tablename__ = "sessions"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_session_token_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user: Mapped["User"] = relationship("User", back_populates="sessions")
