from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.rfi.status import RfiStatus

if TYPE_CHECKING:
    from app.models.file import File
    from app.models.rfi import Rfi


class RfiRevision(Base):
    """One submitted revision of a Request for Information."""

    __tablename__ = "rfi_revisions"
    __table_args__ = (
        UniqueConstraint(
            "rfi_id",
            "revision_number",
            name="uq_rfi_revision_rfi_revision_number",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rfi_id: Mapped[int] = mapped_column(
        ForeignKey("rfis.id"),
        index=True,
        nullable=False,
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    submit_file_id: Mapped[int] = mapped_column(
        ForeignKey("files.id"),
        nullable=False,
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    status: Mapped[RfiStatus] = mapped_column(
        Enum(
            RfiStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=RfiStatus.SUBMITTED,
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

    rfi: Mapped["Rfi"] = relationship("Rfi", back_populates="revisions")
    submit_file: Mapped["File"] = relationship(
        "File",
        lazy="selectin",
        foreign_keys=[submit_file_id],
    )
