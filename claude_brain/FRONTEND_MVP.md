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
  - Files: `GET /api/files/{id}` → `FileResponse` (original name + content type)
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

## Submit / Return modals

Two modals drive the lifecycle, sending multipart `FormData` via JS `fetch()`:

- **Submit modal** (`POST /api/vdi/{id}/submit`): one required file input. Reused
  for both **Submit** (from `not_started`) and **Revise** (from `b`/`c`) — same
  form and endpoint; only the title/copy changes to "Revise". The backend opens
  the next revision. The Return modal is only reachable from `submitted`.
- **Return modal** (`POST /api/vdi/{id}/return`): `return_code` as a `<select>`
  of the **4 return codes only** (A, B, C, D — matching `RETURN_CODES`; never
  `not_started`/`submitted`), labelled "A — Approved" / "B — Rejected, resubmit" /
  etc.; a required file input; an optional `comments` textarea.

## File preview by content type
`File` carries `content_type`. Preview rule:
- `application/pdf` → embed (`<iframe>`/`<embed>` pointing at `/api/files/{id}`).
- `image/*` → `<img>`.
- anything else → download link with original filename.

## Create-VDI form

The create-VDI modal shows **all 8 fields**, with the 4 required ones flagged
(`item_number`, `name`, `approval_type`, `submit_code`); `project_id` is implicit
from the `/projects/{id}` page. Optional: `submittal_number`, `description`,
`spec_drawing_reference`, `notes`. `submittal_number` is genuinely optional and
usually left blank at create time (often unassigned until submittal). Both enums
render as `<select>` dropdowns showing **human labels** (label maps passed from
the server, not duplicated in JS): `approval_type` → "Mandatory Approval" /
"Information Only"; `submit_code` → all 16 as "code — meaning" (e.g. "PS — Prior
to Shipment").

## Enum display
Raw enum values are terse (`ps`, `a`). The UI maps them to human labels, e.g.
status `a` → "Approved", `b` → "Rejected — resubmit", `submitted` → "Submitted",
`not_started` → "Not started". Submit codes show their full meaning (e.g.
`ps` → "Prior to Shipment").

---

## Decisions

1. **Rendering.** Server-rendered Jinja2 (ships with `fastapi[standard]`, no new
   dependency) as the backbone. A minimal sprinkle of dependency-free **vanilla
   JS** (`static/app.js`) drives the client-only interactions the UX needs:
   modal open/close, delete-mode border toggle + `confirm()`, and `fetch()`
   calls against the existing JSON API (notes `PATCH`, deletes). No HTMX/SPA/
   framework, no build step. Vanilla JS over HTMX because the `/api` is already
   JSON-first (ADR 0004); HTMX would want HTML fragments and force a parallel set
   of HTML-returning endpoints, while still not removing the toggle JS. Goal:
   keep the JS small — reach for the server/full-page reload first, use JS only
   where a client-side interaction genuinely requires it.
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
7. **Page routes live per-domain.** Each domain gets a `views.py` with its own
   `APIRouter` returning `HTMLResponse`, mounted at root (no `/api` prefix) —
   `app/project/views.py`, `app/vdi/views.py`, and the revision view. This keeps
   page code beside its API code per the domain-folder rule. `templates/` and
   `static/` stay shared at the app level (cross-domain by nature).
8. **Pages call services directly.** Page handlers use the same `AsyncSession`
   dependency and call the service layer directly — never HTTP round-trips to our
   own `/api`. Services are the shared core; the JSON API and the HTML pages are
   both thin consumers. The "two reads" on the VDI detail page (Decision #5) are
   just `get_vdi` + `get_latest_revision` in one handler. Mutations from the UI
   (create/delete/notes) go through JS `fetch()` to the JSON `/api`.
9. **Mutation → UI update.** On a successful mutation, JS does a full-page
   reload (`location.reload()`) and lets the server render fresh state — no
   client-side DOM patching or list re-rendering in JS. On a non-2xx response,
   JS keeps the modal open and shows an inline error message inside it (so input
   isn't lost); the most likely error is the `UniqueConstraint(project_id,
   item_number)` duplicate on VDI create. The **notes box** is the one exception:
   a successful `PATCH` updates in place with a small "Saved" indicator, no
   reload.

10. **Edit is in scope; reuse the create modals.** Both Project and VDI support
    editing via the *same* modal as create, opened in an "edit" mode pre-filled
    with current values and `PATCH`ing on save (one form, two modes — keeps JS
    and markup minimal, no duplicate forms).
    - **Project**: "Edit" control on the project detail header → pre-filled
      project modal → `PATCH /api/projects/{id}`.
    - **VDI**: "Edit" control on the VDI detail header → pre-filled VDI modal
      (notes excluded — it has its own box) → `PATCH /api/vdi/{id}`. This is how
      `submittal_number` gets assigned after the fact and how field mistakes are
      corrected. Status is never editable (lifecycle-driven, ADR 0002).

## Empty states & notes save

- **Home, no projects:** centered empty state ("No projects yet.") with the
  Create-project button as the primary CTA.
- **Project detail, no VDIs:** empty state under the header ("No vendor data
  items yet.") with the Create-VDI button.
- **Notes save:** an explicit "Save notes" button beside the textarea (not
  save-on-blur), disabled until the text changes. On success the `PATCH` updates
  in place with a "Saved" indicator; no reload.

## Navigation

Shared `base.html` with a slim top bar: app name/logo (links Home, `/`) on the
left and a **breadcrumb** as the primary "back up" mechanism — e.g.
`Home / 26-131 — Acme Plant / Concrete Mix Design`. Project crumb shows
`project_number — name`; VDI crumb shows its `name`. No sidebar, no user menu
(auth is post-MVP), no global search/filters for the MVP. The historical
revision view's warning banner sits below this bar.

## Backend status

The `/api` prefix refactor is **done** (commit c6e16aa) — every router is mounted
under `/api` in `app.py`. `notes` already lives on `VdiUpdate`, so notes editing
needs no model or schema change. No backend refactors remain before building the
frontend.
