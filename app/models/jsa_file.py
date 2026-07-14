from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.file import File
    from app.models.jsa_revision import JsaRevision


class JsaFileGroup(enum.Enum):
    SUBMITTED = "submitted"
    RETURNED = "returned"


class JsaFile(Base):
    """An ordered file in one submitted or returned JSA package."""

    __tablename__ = "jsa_files"
    __table_args__ = (
        UniqueConstraint(
            "jsa_revision_id",
            "file_group",
            "position",
            name="uq_jsa_file_position",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jsa_revision_id: Mapped[int] = mapped_column(
        ForeignKey("jsa_revisions.id"), index=True, nullable=False
    )
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id"), nullable=False)
    file_group: Mapped[JsaFileGroup] = mapped_column(
        Enum(
            JsaFileGroup,
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    revision: Mapped["JsaRevision"] = relationship("JsaRevision", back_populates="file_links")
    file: Mapped["File"] = relationship("File", lazy="selectin")
