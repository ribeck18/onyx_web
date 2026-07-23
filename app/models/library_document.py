from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.library_document_version import LibraryDocumentVersion


class LibraryDocument(Base):
    """A company-wide reusable document with a complete file history."""

    __tablename__ = "library_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    versions: Mapped[list["LibraryDocumentVersion"]] = relationship(
        "LibraryDocumentVersion",
        back_populates="library_document",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="LibraryDocumentVersion.version_number",
    )

    @property
    def current_version(self) -> LibraryDocumentVersion:
        """Return the newest version, which exists after valid creation."""
        return self.versions[-1]
