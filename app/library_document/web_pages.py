"""HTML page routes for the Library Documents domain."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.library_document import service
from app.web.templating import render

router = APIRouter(tags=["pages"])


@router.get("/library")
async def library_documents_list(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Render the company-wide Library Documents list."""
    library_documents = await service.get_library_documents(session)
    return render(
        request,
        "library_document/list.html",
        {"library_documents": library_documents},
    )


@router.get("/library-documents/{library_document_id}")
async def library_document_detail(
    library_document_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Render a Library Document with its complete version history."""
    library_document = await service.get_library_document(session, library_document_id)
    if library_document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Library document not found",
        )
    library_document_versions = await service.get_versions(session, library_document_id)
    return render(
        request,
        "library_document/detail.html",
        {
            "library_document": library_document,
            "library_document_versions": library_document_versions,
        },
    )
