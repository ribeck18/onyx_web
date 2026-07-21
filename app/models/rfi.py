from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.rfi.status import RfiStatus

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.rfi_revision import RfiRevision


class Rfi(Base):
    """A project-scoped Request for Information before its first submission."""

    __tablename__ = "rfis"
    __table_args__ = (
        UniqueConstraint("project_id", "rfi_number", name="uq_rfi_project_rfi_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"),
        index=True,
        nullable=False,
    )
    rfi_number: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    spec_drawing_reference: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[RfiStatus] = mapped_column(
        Enum(
            RfiStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=RfiStatus.NOT_STARTED,
    )
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

    project: Mapped["Project"] = relationship("Project", back_populates="rfis")
    revisions: Mapped[list["RfiRevision"]] = relationship(
        "RfiRevision",
        back_populates="rfi",
        cascade="all, delete-orphan",
    )
