"""HTML page routes for the project_doc domain.

Mounted at root with no ``/api`` prefix. Pages render by calling services
directly (ADR 0005) — never by self-calling the JSON API.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.project import service as project_service
from app.project_doc import service as project_doc_service
from app.web.templating import render

router = APIRouter(tags=["pages"])


@router.get("/projects/{project_id}/documents")
async def project_documents_list(
    project_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Render the documents list for one project.

    Each row shows the document's label, type chip, current version, and
    updated date, linking to the document detail page.
    """
    project = await project_service.get_project(session, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    project_docs = await project_doc_service.get_project_docs(session, project_id)
    return render(
        request,
        "project_doc/list.html",
        {"project": project, "project_docs": project_docs},
    )


@router.get("/project-docs/{project_doc_id}")
async def project_doc_detail(
    project_doc_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Render a document's detail page with its full version history.

    Version display names are composed in the template from the document's
    current label ("{label} Version {n}"), never stored, so a renamed label is
    reflected on every version.
    """
    project_doc = await project_doc_service.get_project_doc(session, project_doc_id)
    if project_doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project document not found"
        )
    project = await project_service.get_project(session, project_doc.project_id)
    doc_versions = await project_doc_service.get_versions(session, project_doc_id)
    return render(
        request,
        "project_doc/detail.html",
        {
            "project": project,
            "doc": project_doc,
            "doc_versions": doc_versions,
        },
    )
