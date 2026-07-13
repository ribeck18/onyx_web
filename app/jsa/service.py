from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.jsa import JSA
from app.models.jsa_file import JsaFile, JsaFileGroup
from app.models.jsa_revision import JsaRevision
from app.jsa.status import JsaStatus

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


async def submit_revision(
    session: AsyncSession,
    jsa: JSA,
    submitted_files: list[File],
) -> JsaRevision:
    """Create the next submitted package for a resolved JSA and flush."""
    revision = JsaRevision(revision_number=jsa.revisions[-1].revision_number + 1)
    for position, stored_file in enumerate(submitted_files):
        revision.file_links.append(
            JsaFile(
                file=stored_file,
                file_group=JsaFileGroup.SUBMITTED,
                position=position,
            )
        )
    jsa.revisions.append(revision)
    jsa.status = JsaStatus.SUBMITTED
    jsa.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return revision


async def record_approval(
    session: AsyncSession,
    jsa: JSA,
    comments: str | None,
) -> JsaRevision:
    """Record approval of the current submitted revision and flush."""
    return await _record_decision(session, jsa, JsaStatus.APPROVED, comments, [])


async def record_rejection(
    session: AsyncSession,
    jsa: JSA,
    returned_files: list[File],
    comments: str | None,
) -> JsaRevision:
    """Record rejection and its buyer-marked-up package, then flush."""
    return await _record_decision(
        session,
        jsa,
        JsaStatus.REJECTED,
        comments,
        returned_files,
    )


async def _record_decision(
    session: AsyncSession,
    jsa: JSA,
    decision: JsaStatus,
    comments: str | None,
    returned_files: list[File],
) -> JsaRevision:
    """Apply one buyer decision to the latest JSA Revision and flush."""
    revision = jsa.revisions[-1]
    revision.status = decision
    revision.decided_at = datetime.now(timezone.utc)
    revision.comments = comments
    for position, stored_file in enumerate(returned_files):
        revision.file_links.append(
            JsaFile(
                file=stored_file,
                file_group=JsaFileGroup.RETURNED,
                position=position,
            )
        )
    jsa.status = decision
    jsa.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return revision


async def delete_latest_revision(session: AsyncSession, jsa: JSA) -> bool:
    """Delete the newest revision and restore its predecessor's status.

    Return whether deleting the sole revision also removed the JSA singleton.
    """
    if len(jsa.revisions) == 1:
        await session.delete(jsa)
        await session.flush()
        return True

    jsa.status = jsa.revisions[-2].status
    jsa.updated_at = datetime.now(timezone.utc)
    jsa.revisions.pop()
    await session.flush()
    return False


async def delete_jsa(session: AsyncSession, jsa: JSA) -> None:
    """Delete a JSA and its revision/link history, then flush."""
    await session.delete(jsa)
    await session.flush()


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


async def get_revision(
    session: AsyncSession,
    jsa_id: int,
    revision_id: int,
) -> JsaRevision | None:
    """Return one JSA Revision scoped to its JSA, if it exists."""
    result = await session.execute(
        select(JsaRevision).where(
            JsaRevision.jsa_id == jsa_id,
            JsaRevision.id == revision_id,
        )
    )
    return result.scalar_one_or_none()


async def get_revisions(session: AsyncSession, jsa_id: int) -> list[JsaRevision]:
    """Return a JSA's revisions oldest first, with their ordered files."""
    result = await session.execute(
        select(JsaRevision)
        .where(JsaRevision.jsa_id == jsa_id)
        .order_by(JsaRevision.revision_number)
    )
    return list(result.scalars().all())
