from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.file import service as file_service
from app.file.dependencies import get_storage_root
from app.jsa import service
from app.jsa.schema import JsaDecision, JsaNotesUpdate, JsaRead, JsaRevisionRead
from app.jsa.status import JsaStatus
from app.project import service as project_service

router = APIRouter(prefix="/projects/{project_id}/jsa", tags=["jsa"])


async def _validate_package(files: list[UploadFile]) -> None:
    """Reject packages outside the one-to-three non-empty-file boundary."""
    if not 1 <= len(files) <= 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A JSA package must contain one to three files.",
        )
    for uploaded_file in files:
        if not await uploaded_file.read():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
            )
        await uploaded_file.seek(0)


@router.post("", response_model=JsaRead, status_code=status.HTTP_201_CREATED)
async def create_jsa(
    project_id: int,
    files: list[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
    storage_root: Path = Depends(get_storage_root),
) -> JsaRead:
    """Create the first submitted JSA package for a Project atomically."""
    project = await project_service.get_project(session, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if await service.get_jsa(session, project_id) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project already has a JSA.",
        )
    await _validate_package(files)
    stored_files = [
        await file_service.save_upload(session, uploaded_file, storage_root)
        for uploaded_file in files
    ]
    jsa = await service.create_jsa(session, project_id, stored_files)
    await session.commit()
    return JsaRead.model_validate(jsa)


@router.get("", response_model=JsaRead)
async def read_jsa(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> JsaRead:
    """Return a Project's JSA and its submitted package history."""
    jsa = await service.get_jsa(session, project_id)
    if jsa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="JSA not found")
    return JsaRead.model_validate(jsa)


@router.post("/submit", response_model=JsaRead)
async def submit_revision(
    project_id: int,
    files: list[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
    storage_root: Path = Depends(get_storage_root),
) -> JsaRead:
    """Submit the next JSA package after an approval or rejection."""
    jsa = await service.get_jsa(session, project_id)
    if jsa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="JSA not found")
    if jsa.status not in {JsaStatus.APPROVED, JsaStatus.REJECTED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="JSA can only be revised after approval or rejection.",
        )
    await _validate_package(files)
    submitted_files = [
        await file_service.save_upload(session, uploaded_file, storage_root)
        for uploaded_file in files
    ]
    await service.submit_revision(session, jsa, submitted_files)
    await session.commit()
    return JsaRead.model_validate(jsa)


@router.get("/revisions", response_model=list[JsaRevisionRead])
async def list_revisions(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[JsaRevisionRead]:
    """Return a Project JSA's revision history oldest first."""
    jsa = await service.get_jsa(session, project_id)
    if jsa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="JSA not found")
    revisions = await service.get_revisions(session, jsa.id)
    return [JsaRevisionRead.model_validate(revision) for revision in revisions]


@router.get("/revisions/{revision_id}", response_model=JsaRevisionRead)
async def read_revision(
    project_id: int,
    revision_id: int,
    session: AsyncSession = Depends(get_session),
) -> JsaRevisionRead:
    """Return one JSA Revision belonging to its Project's singleton JSA."""
    jsa = await service.get_jsa(session, project_id)
    if jsa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="JSA not found")
    revision = await service.get_revision(session, jsa.id, revision_id)
    if revision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="JSA Revision not found")
    return JsaRevisionRead.model_validate(revision)


@router.post("/approve", response_model=JsaRead)
async def approve_jsa(
    project_id: int,
    data: JsaDecision | None = None,
    session: AsyncSession = Depends(get_session),
) -> JsaRead:
    """Approve the current submitted JSA package without return files."""
    jsa = await service.get_jsa(session, project_id)
    if jsa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="JSA not found")
    if jsa.status is not JsaStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="JSA can only be decided while submitted.",
        )
    await service.record_approval(session, jsa, data.comments if data else None)
    await session.commit()
    return JsaRead.model_validate(jsa)


@router.post("/reject", response_model=JsaRead)
async def reject_jsa(
    project_id: int,
    files: list[UploadFile] = File(...),
    comments: str | None = Form(None),
    session: AsyncSession = Depends(get_session),
    storage_root: Path = Depends(get_storage_root),
) -> JsaRead:
    """Reject the current JSA with one to three buyer-marked-up files."""
    jsa = await service.get_jsa(session, project_id)
    if jsa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="JSA not found")
    if jsa.status is not JsaStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="JSA can only be decided while submitted.",
        )
    await _validate_package(files)
    returned_files = [
        await file_service.save_upload(session, uploaded_file, storage_root)
        for uploaded_file in files
    ]
    await service.record_rejection(session, jsa, returned_files, comments)
    await session.commit()
    return JsaRead.model_validate(jsa)


@router.patch("/notes", response_model=JsaRead)
async def patch_notes(
    project_id: int,
    data: JsaNotesUpdate,
    session: AsyncSession = Depends(get_session),
) -> JsaRead:
    """Save internal notes on the live JSA in every lifecycle status."""
    jsa = await service.get_jsa(session, project_id)
    if jsa is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="JSA not found")
    jsa = await service.update_notes(session, jsa, data.notes)
    await session.commit()
    return JsaRead.model_validate(jsa)
