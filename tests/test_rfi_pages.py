from __future__ import annotations

import re

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.vdi import VendorDataItem
from app.vdi.approval_type import ApprovalType
from app.vdi.submit_code import SubmitCode
from app.vdi.submit_status import SubmitStatus
from tests.factories import make_project


def rfi_payload(project_id: int, **overrides: object) -> dict[str, object]:
    """Build a valid RFI API payload for one project."""
    payload: dict[str, object] = {
        "project_id": project_id,
        "rfi_number": "RFI-001",
        "title": "Clarify foundation elevation",
    }
    payload.update(overrides)
    return payload


async def seed_project(session: AsyncSession, project_number: str = "26-131") -> int:
    """Persist one project for rendered-page tests and return its ID."""
    project = make_project(project_number=project_number, name="Acme Plant Expansion")
    session.add(project)
    await session.flush()
    return project.id


async def test_project_rfi_selector_has_count_between_documents_and_jsa(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """The Project selector counts RFIs and sits between Documents and JSA."""
    project_id = await seed_project(session)
    created = await client.post("/api/rfis", json=rfi_payload(project_id))
    assert created.status_code == 201
    assert (
        await client.post(
            "/api/rfis", json=rfi_payload(project_id, rfi_number="RFI-002")
        )
    ).status_code == 201

    response = await client.get(f"/projects/{project_id}")

    assert response.status_code == 200
    body = response.text
    documents = body.index(f'href="/projects/{project_id}/documents"')
    rfis = body.index(f'href="/projects/{project_id}/rfis"')
    jsa = body.index(f'href="/projects/{project_id}/jsa"')
    assert documents < rfis < jsa
    assert 'class="doc-pill-count">2<' in body


async def test_rfi_list_empty_state_and_create_contract(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """An empty RFI list exposes the established modal-backed create path."""
    project_id = await seed_project(session)

    response = await client.get(f"/projects/{project_id}/rfis")

    assert response.status_code == 200
    body = response.text
    assert "No RFIs yet." in body
    assert 'data-modal="rfi-modal"' in body
    assert 'name="rfi_number"' in body
    assert 'name="title"' in body
    assert 'name="spec_drawing_reference"' in body
    assert 'data-null-if-blank' in body
    assert 'name="notes"' in body
    assert f'value="{project_id}"' in body
    assert 'data-url="/api/rfis"' in body
    assert "data-field-error" in body
    assert "data-list-filter" not in body
    assert "No RFIs match your search." not in body


async def test_populated_rfi_list_renders_shared_filter_contract(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """A populated RFI list filters only visible RFI row fields."""
    project_id = await seed_project(session)
    created = await client.post(
        "/api/rfis",
        json=rfi_payload(
            project_id,
            rfi_number="RFI-014",
            title="Clarify roof drain slope",
            spec_drawing_reference="A-201",
            notes="Not searchable",
        ),
    )
    assert created.status_code == 201

    response = await client.get(f"/projects/{project_id}/rfis")

    body = response.text
    search_text = re.search(
        r'<tr[^>]*data-list-filter-text="([^"]+)"',
        body,
    )
    assert response.status_code == 200
    assert 'class="list-filter" data-list-filter' in body
    assert 'data-list-filter-count aria-live="polite">Showing all 1</p>' in body
    assert 'id="rfi-search"' in body
    assert 'aria-controls="rfi-table"' in body
    assert 'data-list-filter-input' in body
    assert body.index('data-list-filter-input') < body.index('data-delete-toggle')
    assert body.index('data-list-filter-input') < body.index('+ New RFI')
    assert 'id="rfi-table" data-list-filter-table' in body
    assert search_text is not None
    assert search_text.group(1) == (
        "Clarify roof drain slope RFI-014 A-201 NOT STARTED"
    )
    assert 'data-row-href="/rfis/' in body
    assert 'data-list-filter-no-results hidden' in body
    assert "No RFIs match your search." in body
    assert (
        "Search by title, RFI number, spec / drawing reference, or lifecycle "
        "status."
    ) in body
    assert "Not searchable" not in body


async def test_rfi_list_is_ordered_and_has_edit_delete_contract(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """Rows show all list fields, with modal edit and generic delete metadata."""
    project_id = await seed_project(session)
    second = await client.post(
        "/api/rfis",
        json=rfi_payload(
            project_id,
            rfi_number="RFI-010",
            title="Later question",
            notes="Internal list note",
        ),
    )
    first = await client.post(
        "/api/rfis",
        json=rfi_payload(
            project_id,
            rfi_number="RFI-002",
            title="Earlier question",
            spec_drawing_reference="D-101",
        ),
    )

    response = await client.get(f"/projects/{project_id}/rfis")

    assert response.status_code == 200
    body = response.text
    assert body.index("RFI-002") < body.index("RFI-010")
    assert "Earlier question" in body
    assert "D-101" in body
    assert "NOT STARTED" in body
    assert 'data-delete-toggle="rfi-table"' in body
    assert 'data-delete-error' in body
    assert f'data-delete-url="/api/rfis/{first.json()["id"]}"' in body
    assert f'data-url="/api/rfis/{second.json()["id"]}"' in body
    assert 'data-method="PATCH"' in body
    assert 'data-create-only' in body
    assert "Internal list note" not in body


async def test_home_open_items_remains_vdi_only_after_rfi_creation(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """RFIs do not alter the Home gallery's established VDI-only metric."""
    project_id = await seed_project(session)
    session.add(
        VendorDataItem(
            project_id=project_id,
            item_number=1,
            name="Concrete Mix",
            approval_type=ApprovalType.MANDATORY_APPROVAL,
            submit_code=SubmitCode.PTC,
            status=SubmitStatus.A,
        )
    )
    await session.commit()
    created = await client.post("/api/rfis", json=rfi_payload(project_id))
    assert created.status_code == 201

    response = await client.get("/")

    assert response.status_code == 200
    assert "1 ITEM" in response.text
    assert "ALL CLEAR" in response.text
