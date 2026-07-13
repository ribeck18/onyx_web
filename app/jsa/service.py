from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.jsa import JSA
from app.models.jsa_file import JsaFile, JsaFileGroup
from app.models.jsa_revision import JsaRevision

if TYPE_CHECKING:
    from app.models.file import File


async def get_jsa(session: AsyncSession, project_id: int) -> JSA | None:
    """Return the Project's singleton JSA, if it has been submitted."""
    result = await session.execute(
        select(JSA)
        .where(JSA.project_id == project_id)
        .options(
            selectinload(JSA.revisions)
            .selectinload(JsaRevision.file_links)
            .selectinload(JsaFile.file)
        )
    )
    return result.scalar_one_or_none()


async def create_jsa(
    session: AsyncSession,
    project_id: int,
    submitted_files: list[File],
) -> JSA:
    """Create a JSA and its first submitted package, then flush."""
    jsa = JSA(project_id=project_id)
    revision = JsaRevision(revision_number=0)
    for position, stored_file in enumerate(submitted_files):
        revision.file_links.append(
            JsaFile(
                file=stored_file,
                file_group=JsaFileGroup.SUBMITTED,
                position=position,
            )
        )
    jsa.revisions.append(revision)
    session.add(jsa)
    await session.flush()
    return jsa


async def update_notes(
    session: AsyncSession,
    jsa: JSA,
    notes: str | None,
) -> JSA:
    """Replace JSA-level internal notes and flush without changing its status."""
    jsa.notes = notes
    jsa.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return jsa


async def get_revisions(session: AsyncSession, jsa_id: int) -> list[JsaRevision]:
    """Return a JSA's revisions oldest first, with their ordered files."""
    result = await session.execute(
        select(JsaRevision)
        .where(JsaRevision.jsa_id == jsa_id)
        .order_by(JsaRevision.revision_number)
    )
    return list(result.scalars().all())
