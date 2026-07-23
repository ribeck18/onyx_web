"""HTML page routes for the Library Documents domain."""

from fastapi import APIRouter, Depends, Request
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
