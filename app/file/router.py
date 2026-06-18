from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.file import service
from app.file.dependencies import get_storage_root

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{file_id}")
async def download_file(
    file_id: int,
    session: AsyncSession = Depends(get_session),
    storage_root: Path = Depends(get_storage_root),
) -> FileResponse:
    """Return a stored file's original bytes with its original name and type.

    404 when either the row or the on-disk bytes are missing, so a stale row
    pointing at a deleted file is treated the same as an unknown id.
    """
    stored_file = await service.get_file(session, file_id)
    if stored_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    disk_path = storage_root / stored_file.stored_path
    if not disk_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    return FileResponse(
        path=disk_path,
        filename=stored_file.original_name,
        media_type=stored_file.content_type,
    )
