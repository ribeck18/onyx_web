from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.jsa.status import JsaStatus

if TYPE_CHECKING:
    from app.models.jsa_revision import JsaRevision
    from app.models.project import Project


class JSA(Base):
    """The one Job Safety Analysis owned by a Project."""

    __tablename__ = "jsas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"),
        unique=True,
        index=True,
        nullable=False,
    )
    status: Mapped[JsaStatus] = mapped_column(
        Enum(
            JsaStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=JsaStatus.SUBMITTED,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    project: Mapped["Project"] = relationship("Project", back_populates="jsa")
    revisions: Mapped[list["JsaRevision"]] = relationship(
        "JsaRevision",
        back_populates="jsa",
        cascade="all, delete-orphan",
        order_by="JsaRevision.revision_number",
    )
