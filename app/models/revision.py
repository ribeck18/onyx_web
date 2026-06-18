from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Integer, String, Text, DateTime, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.vdi.submit_status import SubmitStatus

if TYPE_CHECKING:
    from app.models.file import File
    from app.models.vdi import VendorDataItem


class Revision(Base):
    """One round-trip with the buyer on a Vendor Data Item.

    A submittal is always sent out (submit_file + submitted_at are required);
    the buyer's return side (return_document, returned_at, comments, A/B/C/D
    outcome) is optional while the revision awaits a response. The submit file
    lives in a decoupled File row this revision points at (ADR 0003).
    """

    __tablename__ = "revisions"
    __table_args__ = (
        UniqueConstraint(
            "vendor_data_item_id",
            "revision_number",
            name="uq_revision_vdi_revision_number",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_data_item_id: Mapped[int] = mapped_column(
        ForeignKey("vendor_data_items.id"),
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
    return_document: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[SubmitStatus] = mapped_column(
        Enum(
            SubmitStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=SubmitStatus.SUBMITTED,
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

    vendor_data_item: Mapped["VendorDataItem"] = relationship(
        "VendorDataItem",
        back_populates="revisions",
    )
    # File is a decoupled leaf with no back-reference (ADR 0003); selectin keeps
    # the file loaded eagerly so RevisionRead can serialize it under async.
    submit_file: Mapped["File"] = relationship(
        "File",
        lazy="selectin",
    )
