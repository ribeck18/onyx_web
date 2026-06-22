"""Seed minimal demo data so the Home gallery is demoable.

Run with ``python -m app.seed_data``. This touches several domains (projects,
their VDIs, and the revisions/files those VDIs accrue) so it lives at the app
root rather than in one domain folder. It sets VDI status and writes revisions
directly because it is a demo fixture, not a lifecycle action; the real status
changes still flow only through submit/return in the app. The revisions it
writes are kept consistent with each VDI's status so the file-preview branches,
revision timeline, and historical view are all walkable in a real browser.
"""

from __future__ import annotations

import asyncio
import base64
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from config import file_storage_root
from app.database import AsyncSessionLocal, Base, engine
from app.models.file import File
from app.models.project import Project
from app.models.revision import Revision
from app.models.vdi import VendorDataItem
from app.vdi.approval_type import ApprovalType
from app.vdi.submit_code import SubmitCode
from app.vdi.submit_status import SubmitStatus

# Tiny, valid file payloads so the preview pane can be exercised for real: a
# one-page PDF (iframe branch), a 1x1 PNG (inline-image branch), and a DWG whose
# content type forces the download fallback. Kept inline so the seed needs no
# checked-in binary fixtures and no extra packages.
DEMO_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 200]"
    b"/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
    b"4 0 obj<</Length 52>>stream\n"
    b"BT /F1 18 Tf 30 110 Td (Onyx demo submittal) Tj ET\n"
    b"endstream endobj\n"
    b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF"
)
DEMO_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
DEMO_DWG = b"AC1027 Onyx demo drawing payload (not a real DWG)."

# A file fixture is its bytes, the name shown to the user, and its content type.
PDF_SUBMIT = (DEMO_PDF, "submittal.pdf", "application/pdf")
PDF_RETURN = (DEMO_PDF, "buyer-markup.pdf", "application/pdf")
PNG_SUBMIT = (DEMO_PNG, "shop-drawing.png", "image/png")
DWG_RETURN = (DEMO_DWG, "as-marked.dwg", "application/acad")

SEED_START = datetime(2026, 3, 2, 14, 0, tzinfo=timezone.utc)


def write_seed_file(fixture: tuple[bytes, str, str]) -> File:
    """Write a fixture's bytes under the storage root and return its File row.

    Mirrors the stored_path scheme of the real upload service (a random
    ``<uuid>.<ext>`` name) so seeded files are served by the same file route.
    """
    data, original_name, content_type = fixture
    file_storage_root.mkdir(parents=True, exist_ok=True)
    stored_path = f"{uuid.uuid4()}{Path(original_name).suffix}"
    (file_storage_root / stored_path).write_bytes(data)
    return File(
        stored_path=stored_path,
        original_name=original_name,
        content_type=content_type,
    )


def build_revision(
    vdi: VendorDataItem,
    revision_number: int,
    submit_fixture: tuple[bytes, str, str],
    returned: tuple[tuple[bytes, str, str], SubmitStatus, str | None] | None,
) -> Revision:
    """Build one revision on a VDI from fixtures.

    ``returned`` is ``None`` while the revision still awaits the buyer; otherwise
    it carries the returned-file fixture, the outcome status, and any comments.
    Timestamps are spaced off SEED_START so the timeline reads chronologically.
    """
    submitted_at = SEED_START + timedelta(days=revision_number * 14)
    revision = Revision(
        vendor_data_item=vdi,
        revision_number=revision_number,
        submit_file=write_seed_file(submit_fixture),
        submitted_at=submitted_at,
    )
    if returned is None:
        revision.status = SubmitStatus.SUBMITTED
        return revision
    return_fixture, outcome, comments = returned
    revision.return_file = write_seed_file(return_fixture)
    revision.returned_at = submitted_at + timedelta(days=9)
    revision.comments = comments
    revision.status = outcome
    return revision


# Buyer-return outcomes reused across the seed rows below.
APPROVED = (PDF_RETURN, SubmitStatus.A, "Approved as submitted.")
REJECTED_B = (
    PDF_RETURN,
    SubmitStatus.B,
    "Bolt spacing does not meet spec §3.4 — revise and resubmit.",
)
REJECTED_C_DWG = (
    DWG_RETURN,
    SubmitStatus.C,
    "Coverage gaps at penetrations; see marked drawing.",
)
APPROVED_D = (PDF_RETURN, SubmitStatus.D, "Approved with the noted corrections.")

# Each row is (item_number, name, submittal_number, submit_code, status,
# revision_specs). A revision spec is (submit_fixture, returned_or_none); the set
# exercises every status, every preview branch, and a multi-revision history.
ACME_VDIS = [
    (12, "Concrete Mix Design", "26-131-003", SubmitCode.PS, SubmitStatus.A,
     [(PDF_SUBMIT, APPROVED)]),
    (7, "Structural Steel Shop Drawings", None, SubmitCode.BFS, SubmitStatus.SUBMITTED,
     [(PDF_SUBMIT, None)]),
    (3, "Anchor Bolt Layout", "26-131-001", SubmitCode.PTC, SubmitStatus.B,
     [(PNG_SUBMIT, REJECTED_B)]),
    (15, "Fireproofing Submittal", "26-131-004", SubmitCode.PTI, SubmitStatus.C,
     [(PDF_SUBMIT, REJECTED_C_DWG)]),
    (9, "Electrical Panel Schedules", "26-131-002", SubmitCode.ARO, SubmitStatus.D,
     [(PDF_SUBMIT, REJECTED_B), (PDF_SUBMIT, APPROVED_D)]),
    (21, "O&M Manuals", None, SubmitCode.AFI, SubmitStatus.NOT_STARTED, []),
]

# A small all-approved project demonstrates the ALL CLEAR cue with items present.
NORTH_TERMINAL_VDIS = [
    (1, "HVAC Equipment Data", "26-007-001", SubmitCode.PS, SubmitStatus.A,
     [(PDF_SUBMIT, APPROVED)]),
    (2, "Roofing System Submittal", "26-007-002", SubmitCode.BFA, SubmitStatus.D,
     [(PDF_SUBMIT, APPROVED_D)]),
]


def build_vdi(project: Project, row: tuple) -> VendorDataItem:
    """Build a demo VDI on the project, with its revisions, from a seed row."""
    item_number, name, submittal_number, submit_code, status, revision_specs = row
    vdi = VendorDataItem(
        project=project,
        item_number=item_number,
        name=name,
        submittal_number=submittal_number,
        approval_type=ApprovalType.MANDATORY_APPROVAL,
        submit_code=submit_code,
        status=status,
    )
    for revision_number, (submit_fixture, returned) in enumerate(revision_specs):
        build_revision(vdi, revision_number, submit_fixture, returned)
    return vdi


async def seed() -> None:
    """Create the demo projects and VDIs if the database has no projects yet."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        existing = await session.execute(select(Project.id).limit(1))
        if existing.first() is not None:
            print("Projects already exist; skipping seed.")
            return

        acme = Project(project_number="26-131", name="Acme Plant Expansion")
        for row in ACME_VDIS:
            session.add(build_vdi(acme, row))

        riverside = Project(
            project_number="25-094",
            name="Riverside Pump Station",
            description="No vendor data items logged yet.",
        )

        north_terminal = Project(
            project_number="26-007", name="North Terminal Retrofit"
        )
        for row in NORTH_TERMINAL_VDIS:
            session.add(build_vdi(north_terminal, row))

        session.add_all([acme, riverside, north_terminal])
        await session.commit()
        print("Seeded 3 demo projects.")


if __name__ == "__main__":
    asyncio.run(seed())
