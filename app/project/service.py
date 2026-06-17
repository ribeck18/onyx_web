from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.project.schema import ProjectCreate, ProjectUpdate


async def create_project(session: AsyncSession, data: ProjectCreate) -> Project:
    """Create a new project and flush it to the session."""
    project = Project(
        project_number=data.project_number,
        name=data.name,
        description=data.description,
    )
    session.add(project)
    await session.flush()
    return project


async def get_project(session: AsyncSession, project_id: int) -> Project | None:
    """Return a single project by ID, or None if not found."""
    result = await session.execute(select(Project).where(Project.id == project_id))
    return result.scalar_one_or_none()


async def get_projects(session: AsyncSession) -> list[Project]:
    """Return all projects."""
    result = await session.execute(select(Project).order_by(Project.project_number))
    return list(result.scalars().all())


async def update_project(
    session: AsyncSession,
    project: Project,
    data: ProjectUpdate,
) -> Project:
    """Apply partial updates to a project and flush."""
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    project.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return project


async def delete_project(session: AsyncSession, project_id: int) -> None:
    """Delete a project and cascade to its VDIs and Revisions."""
    project = session.execute(select(Project).where(Project.id == project_id))

    await session.delete(project)
    await session.flush()
