from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.jsa.status import JsaStatus

if TYPE_CHECKING:
    from app.models.jsa import JSA
    from app.models.jsa_file import JsaFile


class JsaRevision(Base):
    """A submitted JSA package and its eventual buyer decision."""

    __tablename__ = "jsa_revisions"
    __table_args__ = (
        UniqueConstraint("jsa_id", "revision_number", name="uq_jsa_revision_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jsa_id: Mapped[int] = mapped_column(ForeignKey("jsas.id"), index=True, nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[JsaStatus] = mapped_column(
        Enum(
            JsaStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=JsaStatus.SUBMITTED,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)

    jsa: Mapped["JSA"] = relationship("JSA", back_populates="revisions")
    file_links: Mapped[list["JsaFile"]] = relationship(
        "JsaFile",
        back_populates="revision",
        cascade="all, delete-orphan",
        order_by="JsaFile.position",
        lazy="selectin",
    )
