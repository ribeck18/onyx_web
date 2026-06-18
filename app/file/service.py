from __future__ import annotations

import uuid
from pathlib import Path

from anyio.to_thread import run_sync
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File


def _write_bytes(destination: Path, data: bytes) -> None:
    """Write data to destination; offloaded to a worker thread by save_upload so
    the event loop stays free while a large upload is written to disk."""
    with open(destination, "wb") as file_handle:
        file_handle.write(data)


async def save_upload(
    session: AsyncSession,
    upload: UploadFile,
    storage_root: Path,
) -> File:
    """Persist an uploaded file's bytes under storage_root and record a File row.

    Bytes are written before the row is created so a row can never reference
    missing bytes; the only residual failure is rare orphaned bytes on a failed
    commit, which is accepted (see FILE_STORAGE_NOTES.md). Transaction control
    stays with the route: this flushes, never commits.
    """
    data = await upload.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    storage_root.mkdir(parents=True, exist_ok=True)
    extension = Path(upload.filename or "").suffix
    stored_path = f"{uuid.uuid4()}{extension}"
    await run_sync(_write_bytes, storage_root / stored_path, data)

    stored_file = File(
        stored_path=stored_path,
        original_name=upload.filename or "",
        content_type=upload.content_type or "application/octet-stream",
    )
    session.add(stored_file)
    await session.flush()
    return stored_file


async def get_file(session: AsyncSession, file_id: int) -> File | None:
    """Return a single stored file by ID, or None if not found."""
    result = await session.execute(select(File).where(File.id == file_id))
    return result.scalar_one_or_none()
