# Frontend Implementation Plan

Build plan for the Onyx server-rendered frontend, derived from the design handoff
(`claude_brain/design_handoff_onyx_frontend/Onyx Frontend Spec.md`) and the
`FRONTEND_DESIGN_BRIEF.md`, reconciled in a grilling session.

Authority: where the spec and brief disagree on **visuals**, the spec wins (it is
token-for-token from the signed-off prototype); the brief wins for **intent/scope**.

## Resolved discrepancies

| # | Topic | Decision |
|---|---|---|
| 1 | Dark/light theming | **Build it in full**: both palettes, top-bar toggle, `theme` cookie rendered server-side (no flash), parity QA on every screen. |
| 2 | Breadcrumb content | **Spec wins** — project crumb is `project_number` only (e.g. `HOME / 26-131 / CONCRETE MIX DESIGN`); the full project name shows in the page H1. |
| 3 | Rejected badge label | **Spec wins** — `REJECTED /B` / `REJECTED /C` (no "resubmit"); the REVISE lifecycle button conveys the action. |

## Architecture decisions

- **No new packages.** `jinja2`, `python-multipart`, `starlette` ship with `fastapi[standard]`; cookies are native; Google Fonts is a CDN `<link>`.
- **Per-domain page layout** (honors the CLAUDE.md folder convention over the spec's flat layout).
- **Page routes:** a `web_pages.py` in each domain — a single APIRouter mounted at root (no `/api` prefix), rendering by calling services **directly** (ADR 0005):
  - `app/project/web_pages.py` → `GET /` (gallery), `GET /projects/{id}`
  - `app/vdi/web_pages.py` → `GET /vdi/{id}`
  - `app/vdi/revision/web_pages.py` → `GET /vdi/{id}/revisions/{rid}` (renders `vdi/detail.html`)
- **Shared plumbing in `app/web/`:** `templating.py` (the one `Jinja2Templates` + a `render()` that injects the theme from the cookie), `labels.py` (all enum→label + badge string/family/hero-word maps — single source of truth; exposed to templates as Jinja globals/filters).
- **Templates:** shared shell + macros at `templates/` root (`base.html`, `macros/`); page bodies per domain (`templates/project/list.html`, `project/detail.html`, `vdi/detail.html`). **No** `new.html` (modals instead) and **no** `revision/detail.html` (historical reuses `vdi/detail.html` with `historical=True`).
- **Open count:** define `OPEN_STATUSES` in `app/vdi/service.py` (open = status not in `{a, d}`); the gallery route loops projects and counts via `get_vdis(project_id)` (small counts, no pagination — optimize later if needed). "Open Item" is now a glossary term in `CONTEXT.md`.
- **Mutations:** small `fetch` helper in `app.js` — 2xx → `location.reload()`, non-2xx → inline modal error; notes `PATCH` is the only in-place update; dup item_number 409 renders inline under the item_number field.

## Build sequence (shell-first tracer bullet)

0. **De-stale `CLAUDE.md`** — folder diagram + frontend conventions. ✅ done.
1. **Shell + Home read-only** — `app/web/templating.py`, StaticFiles mount in `app.py`, `base.html` (top bar, theme toggle, breadcrumb), `style.css` with **both** theme token sets, `labels.py`, `project/web_pages.py` `GET /`, `project/list.html` (cards, open/total counts via `OPEN_STATUSES`, empty state). Proves routing + tokens + theme cookie end-to-end.
2. **Home interactivity** — Project modal (create/edit), delete-mode + `confirm()`+DELETE, `app.js` modal/delete/theme/fetch scaffolding.
3. **Project detail** — `GET /projects/{id}`, `project/detail.html` (header + Edit, VDI table, gradient divider), VDI modal (create/edit, 16-code select, 409 inline), row delete-mode.
4. **VDI detail (read-only)** — `vdi/web_pages.py`, `vdi/detail.html`: hero + status, specification block, file-preview pane (PDF iframe / image / download / empty), buyer-comments callout, revision timeline.
5. **VDI lifecycle + notes** — lifecycle button state machine (Submit/Return/Revise/disabled), Submit + Return modals (multipart), notes in-place save with `SAVED ✓`, preview SUBMITTED/RETURNED tabs.
6. **Historical view** — `revision/web_pages.py` rendering `vdi/detail.html` with `historical=True`: warning banner, disabled lifecycle, read-only notes.
7. **Polish + QA** — verify every screen in **both** themes; background grid, gradient dividers, glows, `onyxPop`; acceptance checklist (spec §16).

## Mechanical notes (decided, no further grilling needed)

- Modals render as hidden partials on the page that needs them; `app.js` shows/hides + pre-fills for edit mode (no dynamic content injection).
- Theme toggle flips `document.documentElement.dataset.theme` + writes the `theme` cookie; no reload.
- Smoke-test each page route (200 + key content) under `tests/`.
- Trim the enum source comments that duplicate `labels.py` meanings, leaving `labels.py` authoritative.
