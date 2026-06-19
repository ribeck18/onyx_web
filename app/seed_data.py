"""Seed minimal demo data so the Home gallery is demoable.

Run with ``python -m app.seed_data``. This touches several domains (projects and
their VDIs) so it lives at the app root rather than in one domain folder. It sets
VDI status directly because it is a demo fixture, not a lifecycle action; the
real status changes still flow only through submit/return in the app.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.database import AsyncSessionLocal, Base, engine
from app.models.project import Project
from app.models.vdi import VendorDataItem
from app.vdi.approval_type import ApprovalType
from app.vdi.submit_code import SubmitCode
from app.vdi.submit_status import SubmitStatus

# Each row is (item_number, name, submittal_number, submit_code, status). The set
# exercises every status so the gallery's OPEN / ALL CLEAR cues are visible.
ACME_VDIS = [
    (12, "Concrete Mix Design", "26-131-003", SubmitCode.PS, SubmitStatus.A),
    (7, "Structural Steel Shop Drawings", None, SubmitCode.BFS, SubmitStatus.SUBMITTED),
    (3, "Anchor Bolt Layout", "26-131-001", SubmitCode.PTC, SubmitStatus.B),
    (15, "Fireproofing Submittal", "26-131-004", SubmitCode.PTI, SubmitStatus.C),
    (9, "Electrical Panel Schedules", "26-131-002", SubmitCode.ARO, SubmitStatus.D),
    (21, "O&M Manuals", None, SubmitCode.AFI, SubmitStatus.NOT_STARTED),
]

# A small all-approved project demonstrates the ALL CLEAR cue with items present.
NORTH_TERMINAL_VDIS = [
    (1, "HVAC Equipment Data", "26-007-001", SubmitCode.PS, SubmitStatus.A),
    (2, "Roofing System Submittal", "26-007-002", SubmitCode.BFA, SubmitStatus.D),
]


def build_vdi(project: Project, row: tuple) -> VendorDataItem:
    """Build a demo VDI on the project from a seed row."""
    item_number, name, submittal_number, submit_code, status = row
    return VendorDataItem(
        project=project,
        item_number=item_number,
        name=name,
        submittal_number=submittal_number,
        approval_type=ApprovalType.MANDATORY_APPROVAL,
        submit_code=submit_code,
        status=status,
    )


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
