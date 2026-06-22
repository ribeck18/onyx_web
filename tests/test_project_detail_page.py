from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vdi import VendorDataItem
from app.vdi.approval_type import ApprovalType
from app.vdi.submit_code import SubmitCode
from app.vdi.submit_status import SubmitStatus
from tests.factories import make_project


async def seed_project(session: AsyncSession, **kwargs: str) -> int:
    """Persist a project and return its id."""
    project = make_project(**kwargs)
    session.add(project)
    await session.flush()
    return project.id


async def add_vdi(
    session: AsyncSession,
    project_id: int,
    *,
    item_number: int = 1,
    name: str = "Concrete Mix Design",
    status: SubmitStatus = SubmitStatus.NOT_STARTED,
    submittal_number: str | None = None,
    submit_code: SubmitCode = SubmitCode.PTC,
) -> int:
    """Persist a VDI on the project and return its id."""
    vdi = VendorDataItem(
        project_id=project_id,
        item_number=item_number,
        name=name,
        approval_type=ApprovalType.MANDATORY_APPROVAL,
        submit_code=submit_code,
        submittal_number=submittal_number,
        status=status,
    )
    session.add(vdi)
    await session.flush()
    return vdi.id


async def test_unknown_project_returns_404(client: AsyncClient) -> None:
    """A missing project id is a 404."""
    response = await client.get("/projects/9999")
    assert response.status_code == 404


async def test_header_shows_project_identity_and_edit(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The header carries the number, name, description, and an edit trigger."""
    project_id = await seed_project(
        session,
        project_number="26-131",
        name="Acme Plant Expansion",
    )
    await session.commit()

    response = await client.get(f"/projects/{project_id}")

    assert response.status_code == 200
    body = response.text
    assert "26-131" in body
    assert "Acme Plant Expansion" in body
    # The edit control opens the project modal in edit mode against the JSON API.
    assert 'data-modal-open="project-modal"' in body
    assert 'data-mode="edit"' in body
    assert f'data-url="/api/projects/{project_id}"' in body


async def test_table_renders_row_per_vdi_with_badge_and_code(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Each VDI is a row showing the status badge label, submit code, and link."""
    project_id = await seed_project(session, project_number="26-131")
    vdi_id = await add_vdi(
        session,
        project_id,
        item_number=12,
        name="Concrete Mix Design",
        status=SubmitStatus.B,
        submittal_number="26-131-001",
        submit_code=SubmitCode.PS,
    )
    await session.commit()

    response = await client.get(f"/projects/{project_id}")

    body = response.text
    assert "Concrete Mix Design" in body
    assert "REJECTED /B" in body  # human badge label, never the raw enum
    assert ">PS<" in body  # compact submit code
    assert "26-131-001" in body
    assert f'href="/vdi/{vdi_id}"' in body


async def test_null_submittal_renders_em_dash(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A VDI with no submittal number shows a muted em-dash in that column."""
    project_id = await seed_project(session, project_number="26-131")
    await add_vdi(session, project_id, submittal_number=None)
    await session.commit()

    response = await client.get(f"/projects/{project_id}")

    assert 'class="cell-dash">—' in response.text


async def test_empty_state_when_no_vdis(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A project with no VDIs shows the empty state and the New VDI CTA."""
    project_id = await seed_project(session, project_number="26-007")
    await session.commit()

    response = await client.get(f"/projects/{project_id}")

    body = response.text
    assert "No vendor data items yet." in body
    assert 'data-modal-open="vdi-modal"' in body
    # Nothing to delete, so the row delete toggle is hidden.
    assert "data-delete-toggle" not in body


async def test_vdi_modal_selects_show_labels_not_raw_codes(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The classification selects render human labels, never bare enum values."""
    project_id = await seed_project(session, project_number="26-131")
    await session.commit()

    response = await client.get(f"/projects/{project_id}")

    body = response.text
    assert 'data-modal="vdi-modal"' in body
    assert f'value="{project_id}"' in body  # project_id implicit on create
    assert "Mandatory Approval" in body
    assert "Information Only" in body
    assert "PS — Prior to Shipment" in body  # "code — meaning"
    # The submit-code option carries the raw value as the option value only.
    assert "<option value=\"ps\">" in body


async def test_vdi_modal_notes_field_is_create_only(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Notes live in the modal but are flagged create-only (edit omits them)."""
    project_id = await seed_project(session, project_number="26-131")
    await session.commit()

    response = await client.get(f"/projects/{project_id}")

    body = response.text
    assert 'name="notes"' in body
    assert "data-create-only" in body


async def test_duplicate_item_number_409_carries_inline_message(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A second VDI with the same item number is a 409 with the inline message.

    The page renders the field-error slot under the item_number input, and the
    API returns the exact message the modal drops into that slot.
    """
    project_id = await seed_project(session, project_number="26-131")
    await add_vdi(session, project_id, item_number=12)
    await session.commit()

    # The slot exists on the page.
    page = await client.get(f"/projects/{project_id}")
    assert "data-field-error" in page.text

    response = await client.post(
        "/api/vdi",
        json={
            "project_id": project_id,
            "item_number": 12,
            "name": "Duplicate Item",
            "approval_type": "mandatory_approval",
            "submit_code": "ptc",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Item number already used in this project"


async def test_delete_toggle_present_with_rows(
    client: AsyncClient, session: AsyncSession
) -> None:
    """With VDIs present, the row delete toggle and per-row metadata appear."""
    project_id = await seed_project(session, project_number="26-131")
    vdi_id = await add_vdi(session, project_id, name="Concrete Mix Design")
    await session.commit()

    response = await client.get(f"/projects/{project_id}")

    body = response.text
    assert 'data-delete-toggle="vdi-table"' in body
    assert f'data-vdi-id="{vdi_id}"' in body
    assert 'data-vdi-name="Concrete Mix Design"' in body
