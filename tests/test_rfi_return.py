from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_project


async def seed_submitted_rfi(client: AsyncClient, session: AsyncSession) -> int:
    """Create and submit an RFI that is ready for a buyer decision."""
    project = make_project()
    session.add(project)
    await session.flush()
    created = await client.post(
        "/api/rfis",
        json={
            "project_id": project.id,
            "rfi_number": "RFI-001",
            "title": "Clarify foundation elevation",
        },
    )
    rfi_id = created.json()["id"]
    submitted = await client.post(
        f"/api/rfis/{rfi_id}/submit",
        files={"file": ("question.pdf", b"question document", "application/pdf")},
    )
    assert submitted.status_code == 200
    return rfi_id


@pytest.mark.parametrize(
    ("decision", "return_kwargs", "expected_file", "expected_comments"),
    [
        ("approved", {"data": {"decision": "approved"}}, None, None),
        (
            "rejected",
            {
                "data": {"decision": "rejected", "comments": "Revise sheet S-101."},
                "files": {"file": ("marked-up.pdf", b"markups", "application/pdf")},
            },
            "marked-up.pdf",
            "Revise sheet S-101.",
        ),
    ],
)
async def test_buyer_return_records_each_decision_with_optional_material(
    client: AsyncClient,
    session: AsyncSession,
    decision: str,
    return_kwargs: dict[str, object],
    expected_file: str | None,
    expected_comments: str | None,
) -> None:
    """Approved and Rejected returns retain optional buyer file and comments."""
    rfi_id = await seed_submitted_rfi(client, session)

    response = await client.post(f"/api/rfis/{rfi_id}/return", **return_kwargs)

    assert response.status_code == 200
    assert response.json()["status"] == decision
    revision = (await client.get(f"/api/rfis/{rfi_id}/revisions/latest")).json()
    assert revision["status"] == decision
    assert revision["returned_at"] is not None
    assert revision["comments"] == expected_comments
    if expected_file is None:
        assert revision["return_file"] is None
    else:
        return_file = revision["return_file"]
        assert return_file["original_name"] == expected_file
        assert (await client.get(f"/api/files/{return_file['id']}")).content == b"markups"


async def test_buyer_return_is_guarded_to_submitted_rfis(
    client: AsyncClient,
    session: AsyncSession,
) -> None:
    """Only an open submitted revision may receive an Approved or Rejected return."""
    project = make_project()
    session.add(project)
    await session.flush()
    created = await client.post(
        "/api/rfis",
        json={
            "project_id": project.id,
            "rfi_number": "RFI-001",
            "title": "Clarify foundation elevation",
        },
    )
    rfi_id = created.json()["id"]

    not_started = await client.post(
        f"/api/rfis/{rfi_id}/return",
        data={"decision": "approved"},
    )
    assert not_started.status_code == 409

    await client.post(
        f"/api/rfis/{rfi_id}/submit",
        files={"file": ("question.pdf", b"question document", "application/pdf")},
    )
    invalid_decision = await client.post(
        f"/api/rfis/{rfi_id}/return",
        data={"decision": "submitted"},
    )
    assert invalid_decision.status_code == 422

    assert (
        await client.post(
            f"/api/rfis/{rfi_id}/return",
            data={"decision": "approved"},
        )
    ).status_code == 200
    repeated = await client.post(
        f"/api/rfis/{rfi_id}/return",
        data={"decision": "rejected"},
    )
    assert repeated.status_code == 409


@pytest.mark.parametrize("decision", ["approved", "rejected"])
async def test_resolved_rfi_can_submit_the_next_revision(
    client: AsyncClient,
    session: AsyncSession,
    decision: str,
) -> None:
    """Both resolved states preserve REV 0 and permit a new submitted REV 1."""
    rfi_id = await seed_submitted_rfi(client, session)
    returned = await client.post(
        f"/api/rfis/{rfi_id}/return",
        data={"decision": decision},
    )
    assert returned.status_code == 200

    resubmitted = await client.post(
        f"/api/rfis/{rfi_id}/submit",
        files={"file": ("revision-1.pdf", b"revision one", "application/pdf")},
    )

    assert resubmitted.status_code == 200
    assert resubmitted.json()["status"] == "submitted"
    revisions = (await client.get(f"/api/rfis/{rfi_id}/revisions")).json()
    assert [revision["revision_number"] for revision in revisions] == [0, 1]
    assert [revision["status"] for revision in revisions] == [decision, "submitted"]
