from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.file import File
    from app.models.project_doc import ProjectDoc


class DocVersion(Base):
    """One recorded version of a Project Document (ADR 0011).

    Pure internal version control: a server-assigned 1-based version number,
    the attached file, and an optional description. No submit/return cycle,
    no return code, no lifecycle status — that is the VDI Revision's world.
    """

    __tablename__ = "doc_versions"
    __table_args__ = (
        UniqueConstraint(
            "project_doc_id",
            "version_number",
            name="uq_doc_version_doc_version_number",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_doc_id: Mapped[int] = mapped_column(
        ForeignKey("project_docs.id"),
        index=True,
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    file_id: Mapped[int] = mapped_column(
        ForeignKey("files.id"),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    project_doc: Mapped["ProjectDoc"] = relationship(
        "ProjectDoc",
        back_populates="versions",
    )
    # The File is a decoupled leaf with no back-reference (ADR 0003); selectin
    # keeps it loaded eagerly so DocVersionRead can serialize it under async.
    file: Mapped["File"] = relationship(
        "File",
        lazy="selectin",
    )
