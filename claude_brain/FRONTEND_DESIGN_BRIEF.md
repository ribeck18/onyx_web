# Onyx Frontend — Design & Prototyping Brief

This is a complete, self-contained brief for prototyping the Onyx web UI. It is
the build-ready expansion of `claude_brain/FRONTEND_MVP.md` (the decisions) and
should be read alongside the codebase. Where this brief and `FRONTEND_MVP.md`
disagree, **this brief wins** for UI specifics; `FRONTEND_MVP.md` wins for intent.

The reader (a designer/prototyper) may also read the code. Key files to ground
the data and API:
- Models: `app/models/project.py`, `app/models/vdi.py`, `app/models/revision.py`,
  `app/models/file.py`
- Schemas (exact field shapes): `app/project/schema.py`, `app/vdi/schema.py`,
  `app/vdi/revision/schema.py`, `app/file/schema.py`
- Enums: `app/vdi/approval_type.py`, `app/vdi/submit_code.py`,
  `app/vdi/submit_status.py`
- API routers: `app/project/router.py`, `app/vdi/router.py`,
  `app/vdi/revision/router.py`, `app/file/router.py`, mounted under `/api` in
  `app/app.py`
- Domain language (authoritative): `CONTEXT.md`
- Decisions of record: `docs/adr/0002` (lifecycle-driven status), `docs/adr/0004`
  (`/api` namespace), `docs/adr/0005` (vanilla JS over HTMX)

---

## 1. What Onyx is

Onyx tracks **vendor data items** on construction projects through a
submit/return approval lifecycle with a buyer. A user (an internal employee)
manages projects, logs the documents required for each, submits them to the
buyer, and records the buyer's verdict when it comes back.

The mental model is a strict three-level hierarchy:

```
Project  (a construction job, e.g. "26-131 — Acme Plant Expansion")
 └── Vendor Data Item (VDI)   (one required document, e.g. "Concrete Mix Design")
      └── Revision            (one submit→return round-trip with the buyer)
           └── File           (the actual uploaded PDF/image, served by id)
```

A VDI carries a **status** that always reflects its current lifecycle state.
Status is never set by hand — it is driven entirely by submit/return actions
(ADR 0002). All history lives in the immutable Revision records.

## 2. Tech constraints the prototype must respect

- **Server-rendered HTML (Jinja2) + minimal vanilla JS.** No React/Vue/Svelte,
  no HTMX, no build step, no SPA. The prototype should be plain HTML + CSS +
  small vanilla JS so it maps 1:1 onto the real implementation. See ADR 0005.
- **One stylesheet** (`static/style.css`) and **one script** (`static/app.js`).
  Keep JS to the minimum: modal open/close, delete-mode toggle, `fetch()` for
  mutations, file-preview selection.
- **Pages are full documents** served at clean URLs; mutations call the JSON
  `/api` and then `location.reload()` (except notes, which update in place).
- Target: **desktop-first** (this is an internal back-office tool used at a
  desk). It should not break on a tablet, but mobile is not a priority.

## 3. Data model — fields and where they appear

### Project (`app/models/project.py`, `ProjectRead`)
| Field | Type | Shown |
|---|---|---|
| `id` | int | internal (URLs) |
| `project_number` | str (e.g. "26-131") | gallery card, detail header, breadcrumb |
| `name` | str | gallery card, detail header, breadcrumb |
| `description` | str \| null | detail header |
| `created_at` / `updated_at` | datetime | not shown in MVP |

A Project has **no status of its own.**

### Vendor Data Item (`app/models/vdi.py`, `VdiRead`)
| Field | Type | Shown |
|---|---|---|
| `id` | int | internal |
| `project_id` | int | internal |
| `item_number` | int (buyer-assigned, unique per project) | project table, VDI header |
| `submittal_number` | str \| null (our internal number, often blank until submitted) | project table (if any), VDI header |
| `name` | str | project table, VDI header, breadcrumb |
| `description` | str \| null | VDI header |
| `approval_type` | enum (2 values) | VDI header |
| `submit_code` | enum (16 values) | project table, VDI header |
| `spec_drawing_reference` | str \| null | VDI header |
| `notes` | str \| null | VDI detail editable notes box |
| `status` | enum (`not_started`/`submitted`/`a`/`b`/`c`/`d`) | project table (badge), VDI header (badge) |
| `created_at` / `updated_at` | datetime | not shown in MVP |

### Revision (`app/models/revision.py`, `RevisionRead`)
Immutable history; one per submit→return round-trip, `revision_number` starts at 0.
| Field | Type | Shown |
|---|---|---|
| `id` | int | internal (historical-view URL) |
| `revision_number` | int (0-based) | timeline entry, historical header |
| `submit_file` | File (always present) | preview when current/this rev is `submitted` |
| `submitted_at` | datetime (always present) | timeline entry |
| `return_file` | File \| null | preview when current/this rev is returned |
| `returned_at` | datetime \| null | timeline entry |
| `comments` | str \| null (buyer comments) | return-comments block |
| `status` | enum | timeline entry badge, historical header badge |

### File (`app/models/file.py`, `FileRead`)
| Field | Type | Notes |
|---|---|---|
| `id` | int | preview/download via `GET /api/files/{id}` |
| `original_name` | str | filename shown on download links |
| `content_type` | str | drives the preview rule (see §9) |

`stored_path` exists on the model but is **never** exposed — files are always
referenced by `/api/files/{id}` (ADR 0003).

## 4. Enum → human label maps (use these labels everywhere)

Raw enum values are terse codes; **the UI must always show human labels.** These
maps will be passed from the server into templates — never hardcode the raw
value in front of a user.

### ApprovalType
| value | label |
|---|---|
| `mandatory_approval` | Mandatory Approval |
| `information_only` | Information Only |

### SubmitCode (shown as "CODE — Meaning")
| value | label |
|---|---|
| `ac` | AC — As Completed |
| `afi` | AFI — At Final Inspection |
| `aro` | ARO — After Receipt of Order |
| `at` | AT — After Test |
| `bc` | BC — Before Contract Awarded |
| `bfa` | BFA — Before Final Acceptance |
| `bfs` | BFS — Before Fabrication Start |
| `pds` | PDS — Prior to Delivery on Site |
| `ps` | PS — Prior to Shipment |
| `pt` | PT — Prior to Test |
| `ptc` | PTC — Prior to Construction |
| `pti` | PTI — Prior to Installation |
| `ptp` | PTP — Prior to Purchase |
| `ptw` | PTW — Prior to Welding |
| `ros` | ROS — Prior to Removal Off-Site |
| `ts` | TS — Time of Shipment |

### SubmitStatus (used for VDI status badge AND revision status)
| value | label | semantic |
|---|---|---|
| `not_started` | Not started | neutral / grey |
| `submitted` | Submitted | in-progress / blue |
| `a` | Approved (A) | success / green |
| `d` | Approved (D) | success / green |
| `b` | Rejected — resubmit (B) | error / red or amber |
| `c` | Rejected — resubmit (C) | error / red or amber |

A and D are both **approved (terminal)**; B and C are both **rejected (resubmit)**.
The letter still matters to users, so keep it visible alongside the meaning.

### Return codes (the select inside the Return modal — these 4 only)
| value | label |
|---|---|
| `a` | A — Approved |
| `b` | B — Rejected, resubmit |
| `c` | C — Rejected, resubmit |
| `d` | D — Approved |

Never offer `not_started` or `submitted` as return codes.

## 5. API surface (already built, JSON under `/api`)

The prototype can mock these, but should shape mock data to match exactly so the
real wiring drops in cleanly. Responses are JSON unless noted.

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| POST | `/api/projects` | `ProjectCreate` JSON: `project_number`, `name`, `description?` | 201 `ProjectRead` | — |
| GET | `/api/projects` | — | 200 `ProjectRead[]` | — |
| GET | `/api/projects/{id}` | — | 200 `ProjectRead` | 404 |
| PATCH | `/api/projects/{id}` | `ProjectUpdate` JSON (any subset) | 200 `ProjectRead` | 404 |
| DELETE | `/api/projects/{id}` | — | 204 | 404 |
| POST | `/api/vdi` | `VdiCreate` JSON (incl. `project_id`) | 201 `VdiRead` | 404 (project), **409 (duplicate item_number)** |
| GET | `/api/vdi?project_id=` | — | 200 `VdiRead[]` | — |
| GET | `/api/vdi/{id}` | — | 200 `VdiRead` | 404 |
| PATCH | `/api/vdi/{id}` | `VdiUpdate` JSON (any subset; **never** status) | 200 `VdiRead` | 404 |
| POST | `/api/vdi/{id}/submit` | multipart: `file` | 200 `VdiRead` | 404, **409 (not submittable)**, 400 (empty file) |
| POST | `/api/vdi/{id}/return` | multipart: `return_code`, `file`, `comments?` | 200 `VdiRead` | 404, **409 (not returnable)**, 422 (bad code) |
| DELETE | `/api/vdi/{id}` | — | 204 | 404 |
| GET | `/api/vdi/{id}/revisions` | — | 200 `RevisionRead[]` | — |
| GET | `/api/vdi/{id}/revisions/latest` | — | 200 `RevisionRead` | 404 |
| GET | `/api/vdi/{id}/revisions/{rid}` | — | 200 `RevisionRead` | 404 |
| GET | `/api/files/{id}` | — | file bytes (orig name + content type) | 404 |

Notes:
- **Submit and Return both return the updated `VdiRead`**, not the revision. The
  UI does not need the revision back — after success it just `location.reload()`s
  and the server re-renders fresh state.
- The duplicate-item-number 409 (`detail: "Item number already used in this
  project"`) is the headline create error and must surface inline in the modal.

## 6. Global shell (`base.html`)

Every page extends one base layout:

- **Top bar** (full width, slim, fixed or sticky): app wordmark "Onyx" on the
  left, links to Home (`/`). To its right, a **breadcrumb** that is the primary
  "back up" mechanism. No user menu, no global search, no settings (all post-MVP).
- **Breadcrumb forms by depth:**
  - Home: `Onyx` only (no crumb, or "Projects").
  - Project detail: `Home / 26-131 — Acme Plant Expansion`
  - VDI detail: `Home / 26-131 — Acme Plant Expansion / Concrete Mix Design`
  - Historical view: same as VDI detail, plus the warning banner below the bar.
  - Project crumb label = `project_number — name`; VDI crumb label = VDI `name`.
  - All crumb segments except the last are links.
- **Main content** area below the bar, comfortably max-widthed and centered
  (this is a data tool — don't let tables sprawl edge to edge on wide monitors).

## 7. Pages

### 7.1 Home — Project gallery (`/`)
- A responsive **grid of project cards**, one per project. Each card shows
  `name` (primary) and `project_number` (secondary). Whole card is clickable →
  `/projects/{id}`.
- **Toolbar above the grid:** a primary **"New Project"** button (left or right),
  and a secondary **"Delete"** button that toggles delete-mode.
- **Create:** "New Project" opens the **Project modal** (create mode) → on submit
  `POST /api/projects` → success: `location.reload()`; failure: inline error in
  modal.
- **Delete mode:** clicking "Delete" puts the gallery into delete-mode — every
  card gains a red border and a slightly "armed" look; the Delete button shows it
  is active (e.g. label becomes "Done" / it stays highlighted). Clicking a card in
  delete-mode triggers a `confirm()` ("Delete project 26-131 — Acme Plant
  Expansion? This removes all its vendor data items.") → on confirm
  `DELETE /api/projects/{id}` → `location.reload()`. Clicking "Delete"/"Done"
  again exits delete-mode (cards become normal, clicks navigate again).
- **Empty state:** no projects → centered message "No projects yet." with the
  "New Project" button as the primary CTA.

### 7.2 Project detail (`/projects/{id}`)
- **Header:** `project_number — name` as the title, `description` below it, and an
  **"Edit"** control that opens the Project modal in edit mode (pre-filled) →
  `PATCH /api/projects/{id}`.
- **VDI table** (clean, scannable; the core of the page). Columns, in order:
  `name | item_number | submittal_number | submit_code | status`.
  - `submittal_number`: render an em-dash / muted "—" when null.
  - `submit_code`: human label (e.g. "PS — Prior to Shipment"); a compact column
    may show just the code "PS" with the full meaning on hover/title.
  - `status`: a **status badge** (see §8) with semantic color + label.
  - Whole row is clickable → `/vdi/{id}`.
- **Toolbar above the table:** primary **"New VDI"** (opens VDI modal, create
  mode → `POST /api/vdi` with this `project_id`) and secondary **"Delete"**
  (delete-mode, mirroring the gallery: red left-border or row highlight on every
  row, click a row → `confirm()` → `DELETE /api/vdi/{id}` → reload).
- **Empty state:** no VDIs → "No vendor data items yet." with the "New VDI" CTA.

### 7.3 VDI detail (`/vdi/{id}`) — the workhorse page
Layout suggestion: a two-column feel — left = identity + lifecycle + notes,
right (or below) = file preview + timeline. Designer owns the exact arrangement;
the required regions are:

1. **Header block** (fixed VDI attributes; these do not change across revisions):
   - Title: VDI `name`.
   - **Status badge** (§8) prominently near the title.
   - Attribute list: `item_number`, `submittal_number` (— if null),
     `approval_type` (label), `submit_code` (label), `spec_drawing_reference`
     (— if null), `description`.
   - **"Edit"** control → VDI modal in edit mode (pre-filled, **notes excluded**)
     → `PATCH /api/vdi/{id}`.

2. **Lifecycle action button** — a *single* button whose label/behavior is driven
   by the current status (this is the heart of the page). See the state table in
   §10. One of: **Submit**, **Return**, **Revise**, or **disabled** (terminal).

3. **Notes box** — an editable `<textarea>` bound to the VDI's `notes`, with an
   explicit **"Save notes"** button beside/below it (disabled until the text
   changes). On save → `PATCH /api/vdi/{id}` with `{notes}` → on success update in
   place and show a small "Saved" indicator (no reload). Available at **any**
   status, including `not_started`. (Notes are an item-level attribute, not part
   of a revision.)

4. **File preview of the current revision** (see §9 for the content-type rule):
   - `not_started` (no revisions): a placeholder — "This VDI has not been
     started." (No preview pane content.)
   - `submitted`: preview the latest revision's **submit_file**.
   - returned (`a`/`b`/`c`/`d`): preview the latest revision's **return_file**.

5. **Return comments block** — when the current revision has `comments`, show them
   near the preview/status (e.g. a callout "Buyer comments"). Omit entirely when
   there are none.

6. **Timeline** — the revision history, oldest → newest. Each entry shows:
   `Rev N`, `submitted_at`, outcome (status badge), `returned_at` (if any). Each
   entry links to the historical view `/vdi/{id}/revisions/{revision_id}`. The
   current/latest revision should be visually marked as current.

### 7.4 Historical revision view (`/vdi/{id}/revisions/{revision_id}`)
- **Same layout as VDI detail**, but the preview, status, and comments reflect the
  *chosen* revision rather than the current one.
- **Warning banner** at the very top of the content (below the global bar): "You
  are viewing a past revision — this is not the current state of this VDI."
  Visually distinct (amber/caution).
- The **notes box is read-only here** (shows the VDI's *current* notes, since
  notes are item-level/not versioned) — render it disabled to keep the historical
  view unambiguously a read-only snapshot.
- No lifecycle action button here (or render it disabled) — actions happen only on
  the live VDI detail page.

## 8. Status badge component
A small pill used in the project table, VDI header, and timeline. Maps status →
label + semantic color (see §4): neutral/grey for `not_started`, blue for
`submitted`, green for approved (`a`/`d`), red/amber for rejected (`b`/`c`). Keep
the letter visible for the returned states. This is the single most repeated
visual element — make it crisp and unambiguous at a glance, since the whole point
of the tool is seeing where everything stands.

## 9. File preview rule (by `content_type`)
`File.content_type` drives the preview, pointing at `GET /api/files/{id}`:
- `application/pdf` → embed inline via `<iframe>`/`<embed>` (a tall preview pane).
- `image/*` → `<img>`.
- anything else → a **download link** showing the `original_name`.
Always also offer a download/open-in-new-tab affordance even for embedded types.

## 10. Lifecycle action button — state machine
The single action button on VDI detail is fully determined by `status`. This maps
directly to `SUBMITTABLE_STATUSES = {not_started, b, c}` and
`RETURNABLE_STATUSES = {submitted}` in `app/vdi/service.py`:

| status | button label | enabled? | opens | endpoint |
|---|---|---|---|---|
| `not_started` | **Submit** | yes | Submit modal | `POST /api/vdi/{id}/submit` |
| `submitted` | **Return** | yes | Return modal | `POST /api/vdi/{id}/return` |
| `b` | **Revise** | yes | Submit modal (same form) | `POST /api/vdi/{id}/submit` |
| `c` | **Revise** | yes | Submit modal (same form) | `POST /api/vdi/{id}/submit` |
| `a` | (Submit) | **disabled/greyed** | — | terminal (approved) |
| `d` | (Submit) | **disabled/greyed** | — | terminal (approved) |

Flow example to prototype end-to-end:
`not_started` → Submit (upload file) → reload → `submitted` → Return (code B +
file + comments) → reload → `b` → Revise (upload new file) → reload →
`submitted` → Return (code A) → reload → `a` (button now disabled, timeline shows
Rev 0 = B, Rev 1 = A).

## 11. Modals (4 total, all dependency-free)
All modals: overlay + centered panel, close on ✕ / overlay click / Esc, trap is
optional. On submit they call `fetch()`; **success → `location.reload()`;
non-2xx → keep modal open and show an inline error message** (don't lose input).
Use the native `<dialog>` element or a simple shown/hidden class — designer's
choice, but keep the JS tiny.

1. **Project modal (create + edit).** Fields: `project_number*`, `name*`,
   `description`. Create → `POST /api/projects`. Edit → pre-filled →
   `PATCH /api/projects/{id}`. Same markup, two modes (title + submit verb +
   target differ).
2. **VDI modal (create + edit).** Fields (all 8): `item_number*` (number),
   `name*`, `submittal_number`, `approval_type*` (select, 2 labelled options),
   `submit_code*` (select, 16 labelled options), `spec_drawing_reference`,
   `description`, `notes`. Required fields flagged with `*`. `project_id` is
   implicit (the page you're on). Group visually: identity (item_number, name,
   submittal_number) / classification (approval_type, submit_code,
   spec_drawing_reference) / description / notes. Create → `POST /api/vdi`.
   Edit → pre-filled, **omit notes** (it has its own box on the page) →
   `PATCH /api/vdi/{id}`. The duplicate-item-number **409** must render inline
   (e.g. under the item_number field: "Item number already used in this project").
3. **Submit modal** (also used for **Revise**). One required **file input**.
   Title/intro reads "Submit" from `not_started`, "Revise" from `b`/`c` — same
   form, same endpoint. Sends multipart `FormData` to
   `POST /api/vdi/{id}/submit`. Block an empty submission client-side.
4. **Return modal.** Fields: `return_code*` (select of the **4** codes from §4),
   `file*` (required upload), `comments` (optional textarea). Sends multipart
   `FormData` to `POST /api/vdi/{id}/return`.

## 12. Visual direction (designer owns this; here's the intent)
- **Tone:** clean, dense-but-calm, professional back-office software. Think a
  well-made internal tool, not a marketing site. Construction/industrial domain —
  unfussy, legible, trustworthy.
- **Hierarchy:** the **status** of things is the most important information on
  every screen — make badges and the lifecycle button the visual anchors.
- **Tables over cards** for VDIs (data scanning); **cards** for the project
  gallery (fewer, more browse-y).
- Restrained palette + one accent; semantic colors reserved for status. Generous
  whitespace, clear typographic scale, comfortable line lengths. Accessible
  contrast; don't rely on color alone for status (keep the text label).

## 13. Sample data for the prototype
Use realistic content so the mockups read true:
- **Project:** `26-131 — Acme Plant Expansion`; also `25-094 — Riverside Pump
  Station`, `26-007 — North Terminal Retrofit` to populate the gallery.
- **VDIs under 26-131** (showcasing every status):
  - `Concrete Mix Design` — item 12 — submittal `26-131-003` — `ps` — status `a`
    (Approved, terminal; 2 revisions: Rev0 = C rejected, Rev1 = A).
  - `Structural Steel Shop Drawings` — item 7 — submittal — (blank) — `bfs` —
    status `submitted` (Rev0 out for review).
  - `Anchor Bolt Layout` — item 3 — submittal `26-131-001` — `ptc` — status `b`
    (Rejected; one revision returned B with comments "Dimensions on sheet 2 do
    not match spec §3.4. Revise and resubmit.").
  - `O&M Manuals` — item 21 — submittal — (blank) — `afi` — status `not_started`.
- Files: a couple of PDFs (e.g. `concrete-mix-design-revA.pdf`) and at least one
  image (e.g. `anchor-bolt-markup.png`) to exercise both preview branches, plus
  one non-previewable type (e.g. `.dwg`) to show the download-link fallback.

## 14. Out of scope (do not design)
Auth / login, user accounts, email notifications to the buyer, PDF generation,
cloud file storage, global search/filtering, project-level status, bulk actions,
pagination (assume project/VDI counts are small for the MVP). Status is never
directly editable anywhere.

## 15. What we want from the prototype
1. All four pages (Home, Project detail, VDI detail, Historical view) as clickable
   HTML/CSS, navigable via real links and the breadcrumb.
2. All four modals wired to open/close, with the create/edit dual-mode behavior.
3. The lifecycle button rendering correctly for each of the six statuses (show a
   VDI in each state).
4. The status badge, file-preview pane (all three content-type branches), notes
   box with Save, delete-mode, and empty states all demonstrated.
5. Mock data shaped to match the `*Read` schemas so the real backend wiring is a
   drop-in. Mutations can be faked (log + simulate reload) in the prototype.
