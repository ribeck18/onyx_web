from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.project_doc.document_type import DocumentType

if TYPE_CHECKING:
    from app.models.doc_version import DocVersion
    from app.models.project import Project


class ProjectDoc(Base):
    """A document we receive and record for a Project, never submitted for approval.

    Carries our own label (e.g. "E-101"), a document type, and an optional
    external doc number. Version-controlled through DocVersions (ADR 0011);
    a ProjectDoc can never exist with zero versions, so creation always
    records Version 1 atomically.
    """

    __tablename__ = "project_docs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"),
        index=True,
        nullable=False,
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[DocumentType] = mapped_column(
        Enum(
            DocumentType,
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    doc_number: Mapped[str | None] = mapped_column(String(255), nullable=True)
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

    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="project_docs",
    )
    # selectin keeps versions (and their files, in turn) eagerly loaded so
    # ProjectDocRead can serialize current_version under async.
    versions: Mapped[list["DocVersion"]] = relationship(
        "DocVersion",
        back_populates="project_doc",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DocVersion.version_number",
    )

    @property
    def current_version(self) -> DocVersion:
        """The highest-numbered version; always exists (never zero versions)."""
        return self.versions[-1]
