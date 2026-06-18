from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

from starlette.datastructures import Headers, UploadFile

from app.models.file import File
from app.models.project import Project
from app.models.revision import Revision
from app.models.vdi import VendorDataItem
from app.vdi.approval_type import ApprovalType
from app.vdi.submit_code import SubmitCode


def make_upload(
    content: bytes = b"submittal bytes",
    filename: str = "rev0.pdf",
    content_type: str = "application/pdf",
) -> UploadFile:
    """Build a Starlette UploadFile for driving save_upload in tests."""
    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


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


def make_file(
    original_name: str = "rev0.pdf",
    content_type: str = "application/pdf",
) -> File:
    """Build an unsaved File storage record with a unique stored_path."""
    return File(
        stored_path=f"{uuid.uuid4()}.pdf",
        original_name=original_name,
        content_type=content_type,
    )


def make_revision(
    vendor_data_item: VendorDataItem,
    revision_number: int = 0,
    submit_file: File | None = None,
) -> Revision:
    """Build an unsaved Revision representing a real submittal on the given VDI.

    The submit File is cascade-saved through the relationship when the Revision
    is added to a session.
    """
    return Revision(
        vendor_data_item=vendor_data_item,
        revision_number=revision_number,
        submit_file=submit_file if submit_file is not None else make_file(),
        submitted_at=datetime.now(timezone.utc),
    )
