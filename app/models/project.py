from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, DateTime, UniqueConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.vdi import VendorDataItem


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("project_number", name="uq_project_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_number: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
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

    vendor_data_items: Mapped[list["VendorDataItem"]] = relationship(
        "VendorDataItem",
        back_populates="project",
        cascade="all, delete-orphan",
    )
