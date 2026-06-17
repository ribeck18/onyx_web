# Revisions are created only through the VDI submit lifecycle

A Revision is never created as a standalone resource: there is no `POST /revisions`. Revision creation is owned by `vdi.service.submit_vdi`, which assigns the next `revision_number` (max+1 per VDI, starting at 0) and synchronizes the VDI's status. The `revision` module is nested under `vdi/`, and `vdi.service` depends on `revision.service` (never the reverse). Revision routes are read-only (`GET /vdi/{id}/revisions`); the buyer's return is recorded through `POST /vdi/{id}/return`, not a generic update.

We chose this because a Revision in this domain is *always a real submittal* — never a draft — with a sequential number and a VDI status that must always reflect the latest round-trip. Exposing generic Revision CRUD would let callers create revisions out of order, without a submittal, or with a VDI status that drifts from its history. The trade-off is giving up the uniform per-resource CRUD shape used for Project and VDI; we accept that to keep the submit/return lifecycle the single, guarded path through which revisions and status change.

## Considered options

- **Generic Revision CRUD** (`POST/PATCH/DELETE /revisions`) — rejected: uniform but allows drafts, out-of-order numbers, and VDI status drift.
- **Lifecycle-driven (chosen)** — revision creation/return flow through guarded VDI actions; revisions are read-only as a resource.
