from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.jsa import service as jsa_service
from app.project import service as project_service
from app.web.templating import render

router = APIRouter(tags=["pages"])


@router.get("/projects/{project_id}/jsa")
async def jsa_detail(
    project_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Render a Project's JSA empty state or current submitted package."""
    project = await project_service.get_project(session, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    jsa = await jsa_service.get_jsa(session, project_id)
    revisions = jsa.revisions if jsa else []
    return render(
        request,
        "jsa/detail.html",
        {"project": project, "jsa": jsa, "revisions": revisions},
    )


@router.get("/projects/{project_id}/jsa/revisions/{revision_id}")
async def jsa_revision_detail(
    project_id: int,
    revision_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Render one past JSA Revision with immutable lifecycle controls."""
    project = await project_service.get_project(session, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    jsa = await jsa_service.get_jsa(session, project_id)
    if jsa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="JSA not found")
    revision = await jsa_service.get_revision(session, jsa.id, revision_id)
    if revision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="JSA Revision not found")
    return render(
        request,
        "jsa/detail.html",
        {
            "project": project,
            "jsa": jsa,
            "revision": revision,
            "revisions": jsa.revisions,
            "historical": True,
        },
    )
