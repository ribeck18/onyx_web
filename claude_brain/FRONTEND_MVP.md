# Frontend MVP Plan

Status: **draft / under discussion**. This captures the proposed frontend for the
Onyx MVP and the open questions we need to settle before building.

## Goal

A simple, fast, user-friendly interface for browsing projects and their vendor
data items (VDIs), and for moving a VDI through its submit/return lifecycle.
Server-rendered, minimal JavaScript, minimal dependencies.

## Backend we are building on (already done)

- **Models**: `Project` → `VendorDataItem` → `Revision` → `File`.
  - `VendorDataItem` fields: `item_number`, `submittal_number?`, `name`,
    `description?`, `approval_type`, `submit_code`, `spec_drawing_reference?`,
    `notes?`, `status`.
  - `Revision` is the immutable history: `revision_number` (0-based),
    `submit_file` + `submitted_at` (always present), `return_file?` +
    `returned_at?` + `comments?` + `status` (set on return).
  - `File` is decoupled, served by id.
- **JSON API today**:
  - Projects: `POST/GET /projects/`, `GET/PATCH/DELETE /projects/{id}`
  - VDIs: `POST/GET /vdi`, `GET/PATCH/DELETE /vdi/{id}`,
    `POST /vdi/{id}/submit` (multipart file), `POST /vdi/{id}/return`
    (multipart: `return_code`, `file`, `comments?`)
  - Revisions: `GET /vdi/{id}/revisions`, `/latest`, `/{revision_id}`
  - Files: `GET /files/{id}` → `FileResponse` (original name + content type)
- **Status lifecycle** (`SubmitStatus`): `not_started` → `submitted` →
  `a`/`b`/`c`/`d`. A/D approved, B/C rejected (resubmit). Status is never set
  directly; it is driven by submit/return (ADR 0002).

## Proposed pages

### 1. Home — project gallery (`/`)
- Gallery of project **cards**, one per project.
- Card shows: project name, project number.
- Click a card → project detail page.
- **Create project** button → opens a modal with the required project fields;
  submitting `POST`s and reloads the gallery.
- **Delete project** button → enters "delete mode": every card gains a red
  border. Clicking a card asks for confirmation; on yes the project is deleted
  and the gallery reloads.

### 2. Project detail (`/projects/{id}`)
- Header: project name, number, description.
- **Table of VDIs**, clean and simple. Columns:
  `name | item_number | submittal_number (if any) | submit_code | status`.
- Click a row → VDI detail page.
- **Create VDI** and **Delete VDI** controls mirror the project gallery: a modal
  for create, a red-border "delete mode" with per-row confirmation for delete.

### 3. VDI detail (`/vdi/{id}`)
- Header: name, status, description, spec_drawing_reference, item_number,
  submittal_number. (These never change across revisions in the company
  workflow, so they live on the VDI, not the revision.)
- **Notes box**: edits the VDI's `notes` via `PATCH /api/vdi/{id}`. Notes are an
  item-level attribute, so the box is available at any status — including
  `not_started`, before any revision exists.
- **Timeline**: revision history (oldest→newest). Each entry shows revision
  number, submitted_at, outcome (status), returned_at. Click → historical view.
- **Return comments**: when the current revision has been returned with
  `comments`, display them on the page (near the preview / status). Omitted when
  there are none.
- **File preview** of the *current* revision:
  - `not_started` (no revisions): "This VDI has not been started."
  - `submitted`: preview the latest revision's **submit_file**.
  - returned (A/B/C/D): preview the latest revision's **return_file**.
- **Lifecycle action button** — a single button whose label and behavior follow
  the current status:
  - `not_started` → **"Submit"** → opens the submit modal
    (`POST /api/vdi/{id}/submit`, multipart: submittal file).
  - `submitted` → **"Return"** → opens the return modal
    (`POST /api/vdi/{id}/return`, multipart: `return_code` A/B/C/D + return file
    + optional `comments`).
  - returned `b` / `c` (rejected, resubmit) → **"Revise"** → opens the submit
    modal (same submit action; the backend opens the next revision).
  - returned `a` / `d` (approved) → button **greyed out / disabled** (terminal).

  These map directly to the backend's `SUBMITTABLE_STATUSES` (Submit/Revise) and
  `RETURNABLE_STATUSES` (Return); the disabled state is any status in neither.

### 4. Historical revision view (`/vdi/{id}/revisions/{revision_id}`)
- Same layout as the VDI detail page, but showing the chosen revision's files,
  status, and comments.
- **Warning banner** at top: "You are viewing a past revision — this is not the
  current state of this VDI."
- Notes are item-level (not versioned), so the box shows the VDI's current notes
  and is read-only here to keep the historical view clearly a read-only snapshot.

## File preview by content type
`File` carries `content_type`. Preview rule:
- `application/pdf` → embed (`<iframe>`/`<embed>` pointing at `/files/{id}`).
- `image/*` → `<img>`.
- anything else → download link with original filename.

## Enum display
Raw enum values are terse (`ps`, `a`). The UI maps them to human labels, e.g.
status `a` → "Approved", `b` → "Rejected — resubmit", `submitted` → "Submitted",
`not_started` → "Not started". Submit codes show their full meaning (e.g.
`ps` → "Prior to Shipment").

---

## Decisions

1. **Rendering.** Server-rendered Jinja2 (ships with `fastapi[standard]`, no new
   dependency). Plain HTML forms with full-page reloads — no HTMX/SPA for now.
2. **URLs.** All JSON API routes move under an `/api` prefix; HTML pages own the
   clean URLs (`/`, `/projects/{id}`, `/vdi/{id}`, etc.). See Required refactors.
3. **History is revision-level only.** The VDI's own fields (name, description,
   spec_drawing_reference, submit_code, …) never change across revisions in the
   company workflow, so no point-in-time snapshot of the VDI is needed. The
   historical view shows that revision's files/status/comments/notes alongside
   the VDI's current header.
4. **Both `description` and `notes` stay on the VDI.** A note is about the *item*,
   not a submittal round, so notes stay item-level and are editable at any
   status (including `not_started`). Description is the fixed attribute shown in
   the header; notes are the editable box.
5. **Detail page makes two reads** (VDI + its latest revision) to know which file
   to preview. Accepted; no new endpoint.
6. **Create/delete from the UI** for both projects (home) and VDIs (project
   detail): modal create, red-border "delete mode" with confirmation.

## Required refactors (do BEFORE building the frontend)

### Prefix the JSON API with `/api`
- Re-prefix every existing router (`/api/projects`, `/api/vdi`, `/api/files`,
  `/api/vdi/{id}/revisions`). Update all tests to the new paths.

Notes stay on the VDI, so `notes` already lives on `VdiUpdate` — no model or
schema change is needed for notes editing.
