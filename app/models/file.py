from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class File(Base):
    """A stored file on disk, decoupled from any domain concept (see ADR 0003).

    File knows nothing about Revisions or VDIs and carries no foreign key back
    to them; the link runs the other way. stored_path is a `<uuid>.<ext>` name
    resolved against FILE_STORAGE_ROOT — never an absolute path — so the storage
    root can move with a one-line config change and no data migration.
    """

    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stored_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    original_name: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
