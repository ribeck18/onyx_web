from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.vdi.submit_status import SubmitStatus
from tests.factories import make_file, make_project, make_revision, make_vdi


async def make_vdi_row(
    session: AsyncSession,
    *,
    status: SubmitStatus = SubmitStatus.NOT_STARTED,
    submittal_number: str | None = "26-131-001",
    spec_drawing_reference: str | None = "Spec §3.4 / Dwg S-201",
    description: str | None = "Mix design for foundation concrete.",
    notes: str | None = "Working notes.",
) -> int:
    """Persist a project + VDI and return the VDI id."""
    project = make_project(project_number="26-131", name="Acme Plant Expansion")
    vdi = make_vdi(project, item_number=12, name="Concrete Mix Design")
    vdi.status = status
    vdi.submittal_number = submittal_number
    vdi.spec_drawing_reference = spec_drawing_reference
    vdi.description = description
    vdi.notes = notes
    session.add(project)
    session.add(vdi)
    await session.flush()
    return vdi.id


async def add_submitted_revision(
    session: AsyncSession,
    vdi_id: int,
    *,
    revision_number: int = 0,
    filename: str = "rev0.pdf",
    content_type: str = "application/pdf",
):
    """Persist a revision still out for review (submit file only)."""
    submit_file = make_file(original_name=filename, content_type=content_type)
    vdi = await _load_vdi(session, vdi_id)
    revision = make_revision(
        vdi, revision_number=revision_number, submit_file=submit_file
    )
    session.add(revision)
    await session.flush()
    return revision


async def add_returned_revision(
    session: AsyncSession,
    vdi_id: int,
    *,
    revision_number: int = 0,
    return_code: SubmitStatus = SubmitStatus.B,
    return_filename: str = "rev0_redline.pdf",
    return_content_type: str = "application/pdf",
    comments: str | None = "See markups on sheet 3.",
):
    """Persist a revision the buyer has returned (both files present)."""
    revision = await add_submitted_revision(
        session, vdi_id, revision_number=revision_number
    )
    revision.return_file = make_file(
        original_name=return_filename, content_type=return_content_type
    )
    revision.returned_at = datetime.now(timezone.utc)
    revision.comments = comments
    revision.status = return_code
    await session.flush()
    return revision


async def _load_vdi(session: AsyncSession, vdi_id: int):
    from app.vdi import service as vdi_service

    return await vdi_service.get_vdi(session, vdi_id)


async def test_unknown_vdi_returns_404(client: AsyncClient) -> None:
    """A missing VDI id is a 404."""
    response = await client.get("/vdi/9999")
    assert response.status_code == 404


@pytest.mark.parametrize(
    ("status", "family", "hero_word"),
    [
        (SubmitStatus.NOT_STARTED, "fam-ns", "Not started"),
        (SubmitStatus.SUBMITTED, "fam-info", "Submitted"),
        (SubmitStatus.A, "fam-ok", "Approved"),
        (SubmitStatus.D, "fam-ok", "Approved"),
        (SubmitStatus.B, "fam-bad", "Rejected"),
        (SubmitStatus.C, "fam-bad", "Rejected"),
    ],
)
async def test_hero_status_per_status(
    client: AsyncClient,
    session: AsyncSession,
    status: SubmitStatus,
    family: str,
    hero_word: str,
) -> None:
    """The hero shows the right family color and word for every status."""
    vdi_id = await make_vdi_row(session, status=status)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}")

    assert response.status_code == 200
    body = response.text
    assert f"hero-status {family}" in body
    assert f'class="hero-word">{hero_word}' in body


async def test_returned_status_shows_letter_code(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Returned states append the letter code to the hero."""
    vdi_id = await make_vdi_row(session, status=SubmitStatus.B)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}")

    assert '<span class="hero-code">/B</span>' in response.text


async def test_specification_uses_human_labels(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Spec attributes render human labels, never raw enum values."""
    vdi_id = await make_vdi_row(session, status=SubmitStatus.NOT_STARTED)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}")

    body = response.text
    assert "Mandatory Approval" in body
    assert "Prior to Construction" in body  # PTC full label
    assert "mandatory_approval" not in body


async def test_preview_pdf_branch(client: AsyncClient, session: AsyncSession) -> None:
    """A submitted PDF embeds in an iframe."""
    vdi_id = await make_vdi_row(session, status=SubmitStatus.SUBMITTED)
    await add_submitted_revision(
        session, vdi_id, filename="mix.pdf", content_type="application/pdf"
    )
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}")

    assert 'class="preview-pdf"' in response.text


async def test_preview_image_branch(client: AsyncClient, session: AsyncSession) -> None:
    """A submitted image renders inline."""
    vdi_id = await make_vdi_row(session, status=SubmitStatus.SUBMITTED)
    await add_submitted_revision(
        session, vdi_id, filename="markup.png", content_type="image/png"
    )
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}")

    assert 'class="preview-image"' in response.text


async def test_preview_download_branch(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A non-previewable type falls back to a download link with an ext chip."""
    vdi_id = await make_vdi_row(session, status=SubmitStatus.SUBMITTED)
    await add_submitted_revision(
        session, vdi_id, filename="layout.dwg", content_type="application/octet-stream"
    )
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}")

    body = response.text
    assert "preview-download" in body
    assert "Download file" in body
    assert ">DWG<" in body


async def test_preview_empty_when_not_started(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A not-started VDI shows the empty preview, not a file."""
    vdi_id = await make_vdi_row(session, status=SubmitStatus.NOT_STARTED)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}")

    body = response.text
    assert "preview-empty" in body
    assert "This VDI has not been started." in body


async def test_tabs_only_when_both_files_exist(
    client: AsyncClient, session: AsyncSession
) -> None:
    """SUBMITTED/RETURNED tabs appear for a returned revision (both files)."""
    vdi_id = await make_vdi_row(session, status=SubmitStatus.B)
    await add_returned_revision(session, vdi_id, return_code=SubmitStatus.B)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}")

    body = response.text
    assert "preview-tabs" in body
    assert 'data-preview-tab="submitted"' in body
    assert 'data-preview-tab="returned"' in body


async def test_no_tabs_when_only_submit_file(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A still-out revision (one file) shows no tabs."""
    vdi_id = await make_vdi_row(session, status=SubmitStatus.SUBMITTED)
    await add_submitted_revision(session, vdi_id)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}")

    assert "preview-tabs" not in response.text


async def test_buyer_comments_shown_when_present(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The buyer-comments callout shows when the current revision has comments."""
    vdi_id = await make_vdi_row(session, status=SubmitStatus.B)
    await add_returned_revision(
        session, vdi_id, return_code=SubmitStatus.B, comments="Fix the rebar spacing."
    )
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}")

    body = response.text
    assert "BUYER COMMENTS" in body
    assert "Fix the rebar spacing." in body


async def test_buyer_comments_hidden_without_comments(
    client: AsyncClient, session: AsyncSession
) -> None:
    """No callout when the current revision has no comments."""
    vdi_id = await make_vdi_row(session, status=SubmitStatus.SUBMITTED)
    await add_submitted_revision(session, vdi_id)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}")

    assert "BUYER COMMENTS" not in response.text


async def test_timeline_orders_and_marks_current(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The timeline lists revisions oldest→newest, marking and linking current."""
    vdi_id = await make_vdi_row(session, status=SubmitStatus.SUBMITTED)
    rev0 = await add_returned_revision(
        session, vdi_id, revision_number=0, return_code=SubmitStatus.C
    )
    rev1 = await add_submitted_revision(session, vdi_id, revision_number=1)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}")

    body = response.text
    # Oldest first.
    assert body.index("REV 0") < body.index("REV 1")
    # Current (latest) is tagged and links back to the live page.
    assert "CURRENT" in body
    assert f'href="/vdi/{vdi_id}/revisions/{rev0.id}"' in body
    assert f'href="/vdi/{vdi_id}"' in body
    assert f"/revisions/{rev1.id}" not in body  # current links to live, not history


async def test_timeline_empty_when_not_started(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A not-started VDI shows the empty timeline message."""
    vdi_id = await make_vdi_row(session, status=SubmitStatus.NOT_STARTED)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}")

    assert "NO REVISIONS YET." in response.text


@pytest.mark.parametrize(
    ("status", "label", "url_fragment"),
    [
        (SubmitStatus.NOT_STARTED, "Submit", "/submit"),
        (SubmitStatus.SUBMITTED, "Return", "/return"),
        (SubmitStatus.B, "Revise", "/submit"),
        (SubmitStatus.C, "Revise", "/submit"),
    ],
)
async def test_lifecycle_button_label_per_actionable_status(
    client: AsyncClient,
    session: AsyncSession,
    status: SubmitStatus,
    label: str,
    url_fragment: str,
) -> None:
    """Each actionable status drives the right enabled button and endpoint."""
    vdi_id = await make_vdi_row(session, status=status)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}")

    body = response.text
    assert f">{label}</button>" in body
    assert f'data-url="/api/vdi/{vdi_id}{url_fragment}"' in body


@pytest.mark.parametrize("status", [SubmitStatus.A, SubmitStatus.D])
async def test_lifecycle_button_disabled_when_terminal(
    client: AsyncClient,
    session: AsyncSession,
    status: SubmitStatus,
) -> None:
    """Approved (A/D) statuses show a disabled Submit button with no action."""
    vdi_id = await make_vdi_row(session, status=status)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}")

    body = response.text
    assert '<button type="button" class="lifecycle-btn" disabled>Submit</button>' in body
    assert "SEQUENCE COMPLETE" in body
    # A terminal item exposes neither lifecycle modal trigger.
    assert "data-modal-open=\"submit-modal\"" not in body
    assert "data-modal-open=\"return-modal\"" not in body


async def test_return_modal_offers_only_four_codes(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The return select offers A/B/C/D only, never lifecycle states."""
    vdi_id = await make_vdi_row(session, status=SubmitStatus.SUBMITTED)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}")

    body = response.text
    assert 'data-modal="return-modal"' in body
    for code in ("a", "b", "c", "d"):
        assert f'<option value="{code}">' in body
    assert '<option value="not_started">' not in body
    assert '<option value="submitted">' not in body


async def test_notes_box_is_editable_with_save(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The live notes box is editable and carries the in-place save controls."""
    vdi_id = await make_vdi_row(session, status=SubmitStatus.NOT_STARTED)
    await session.commit()

    response = await client.get(f"/vdi/{vdi_id}")

    body = response.text
    assert f'data-notes-url="/api/vdi/{vdi_id}"' in body
    assert "data-notes-input" in body
    assert "data-notes-save" in body
    assert "readonly" not in body
