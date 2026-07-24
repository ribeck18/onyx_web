from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.file import File
    from app.models.library_document import LibraryDocument


class LibraryDocumentVersion(Base):
    """One file-backed version of a Library Document."""

    __tablename__ = "library_document_versions"
    __table_args__ = (
        UniqueConstraint(
            "library_document_id",
            "version_number",
            name="uq_library_document_version_number",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    library_document_id: Mapped[int] = mapped_column(
        ForeignKey("library_documents.id"),
        index=True,
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id"), nullable=False)
    version_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    library_document: Mapped["LibraryDocument"] = relationship(
        "LibraryDocument",
        back_populates="versions",
    )
    file: Mapped["File"] = relationship("File", lazy="selectin")
