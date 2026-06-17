from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Integer, String, Text, DateTime, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.vdi.approval_type import ApprovalType
from app.vdi.submit_code import SubmitCode
from app.vdi.submit_status import SubmitStatus

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.revision import Revision


class VendorDataItem(Base):
    """A single piece of required vendor documentation belonging to a Project.

    Carries the buyer-facing Item Number and our internal Submittal Number,
    its classification (Approval Type, Submit Code), lifecycle status, and its
    history of Revisions with the buyer.
    """

    __tablename__ = "vendor_data_items"
    __table_args__ = (
        UniqueConstraint("project_id", "item_number", name="uq_vdi_project_item_number"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"),
        index=True,
        nullable=False,
    )
    item_number: Mapped[int] = mapped_column(Integer, nullable=False)
    submittal_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_type: Mapped[ApprovalType] = mapped_column(
        Enum(
            ApprovalType,
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    submit_code: Mapped[SubmitCode] = mapped_column(
        Enum(
            SubmitCode,
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    spec_drawing_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[SubmitStatus] = mapped_column(
        Enum(
            SubmitStatus,
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=SubmitStatus.NOT_STARTED,
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

    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="vendor_data_items",
    )
    revisions: Mapped[list["Revision"]] = relationship(
        "Revision",
        back_populates="vendor_data_item",
        cascade="all, delete-orphan",
    )
