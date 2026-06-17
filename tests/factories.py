from __future__ import annotations

from datetime import datetime, timezone

from app.models.project import Project
from app.models.revision import Revision
from app.models.vdi import VendorDataItem
from app.vdi.approval_type import ApprovalType
from app.vdi.submit_code import SubmitCode


def make_project(project_number: str = "P-001", name: str = "Test Job") -> Project:
    """Build an unsaved Project with sensible defaults for tests."""
    return Project(project_number=project_number, name=name)


def make_vdi(
    project: Project,
    item_number: int = 1,
    name: str = "Concrete Mix Design",
    approval_type: ApprovalType = ApprovalType.MANDATORY_APPROVAL,
    submit_code: SubmitCode = SubmitCode.PTC,
) -> VendorDataItem:
    """Build an unsaved VendorDataItem attached to the given project."""
    return VendorDataItem(
        project=project,
        item_number=item_number,
        name=name,
        approval_type=approval_type,
        submit_code=submit_code,
    )


def make_revision(
    vendor_data_item: VendorDataItem,
    revision_number: int = 0,
    submit_document: str = "uploads/rev0.pdf",
) -> Revision:
    """Build an unsaved Revision representing a real submittal on the given VDI."""
    return Revision(
        vendor_data_item=vendor_data_item,
        revision_number=revision_number,
        submit_document=submit_document,
        submitted_at=datetime.now(timezone.utc),
    )
