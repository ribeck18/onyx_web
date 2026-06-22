# Handoff: Onyx Frontend

## Overview
Onyx is an internal back-office web app that tracks **vendor data items** (required vendor
documents) on construction projects through a **submit → return** approval lifecycle with an
external buyer. An employee creates projects, logs the documents each requires, submits them to the
buyer, and records the buyer's verdict when it returns. Hierarchy: **Project → Vendor Data Item
(VDI) → Revision → File**. The single most important thing on every screen is a VDI's **status**,
which is derived entirely from submit/return actions (never set by hand).

This package contains the approved visual design plus a complete, build-ready specification.

## About the design files
The HTML files in this bundle are **design references**, not production code to copy directly. They
are prototypes showing the intended look and behavior. Your task is to **recreate this design in the
Onyx codebase's established environment** — the existing stack is **server-rendered Jinja2 templates
+ one `static/style.css` + one `static/app.js` (vanilla JS), no framework, no build step** (see the
project's ADR 0005). Translate the prototype's inline styles into CSS classes in `style.css`; do not
ship the HTML prototype as-is. The backend (FastAPI, JSON under `/api`) is already built — wire the
UI to it.

## Fidelity
**High-fidelity.** Final colors (full dark + light palettes), typography, spacing, component
anatomy, and interactions are all specified to the pixel/token. Recreate the UI faithfully using
exact tokens. **`Onyx Frontend Spec.md` is the authoritative source** — it contains every design
token, component spec, page layout, modal, the lifecycle state machine, the enum→label maps, the API
surface, and the dark/light implementation. Read it first and build from it.

## Files in this bundle
| File | What it is |
|---|---|
| **`Onyx Frontend Spec.md`** | **The build spec — start here.** Complete tokens, components, pages, modals, behavior, API, dark/light. |
| `Onyx Prototype (standalone).html` | Self-contained runnable prototype. Open in any browser — clickable, with a dark/light toggle (top-right). Use it as the visual reference. |
| `Onyx.dc.html` | Source of the prototype (single-component form used for the design review). Reference only; do not port its structure. |

## How to use this package
1. Open **`Onyx Prototype (standalone).html`** in a browser and click through all four
   pages/states (it ships with realistic seed data covering every status).
2. Read **`Onyx Frontend Spec.md`** end to end — it is self-sufficient.
3. Recreate the four pages as Jinja2 templates over the existing `/api`, building one `style.css`
   (with the two token sets) and one small `app.js`. Use the spec's §16 acceptance checklist to
   confirm completeness.

## Screens (full detail in the spec)
- **Home — Project gallery** (`/`): responsive card grid, New Project + delete-mode, empty state.
- **Project detail** (`/projects/{id}`): header + Edit, scannable VDI table (name / item / submittal
  / code / status badge), New VDI + delete-mode.
- **VDI detail** (`/vdi/{id}`): the workhorse — hero with status, specification attributes, the
  single status-driven **lifecycle button**, buyer-comments callout, file preview (PDF/image/
  download/empty), editable notes with in-place save, and a revision timeline.
- **Historical revision view** (`/vdi/{id}/revisions/{rid}`): same layout reflecting a past
  revision, with a warning banner, disabled lifecycle, and read-only notes.

## Interactions, state & behavior
All specified in the spec: the lifecycle state machine (§9), the four modals with create/edit dual
modes and inline 409 handling (§8), delete-mode, file-preview tab switching, in-place notes save,
and the dark/light toggle. Mutation pattern: `fetch()` → 2xx `location.reload()` / non-2xx inline
error — **except notes**, which update in place. See spec §11 and §13.

## Design tokens
The complete dark + light CSS custom-property sets, typography scale (Space Grotesk + JetBrains
Mono), spacing, radii, borders, the background grid, gradient dividers, glows, and the `onyxPop`
animation are all in spec §4. Copy them verbatim.

## Assets
No image or icon assets — the UI is pure CSS/typography (the "gem" wordmark is a rotated square; the
background is a CSS grid). Fonts load from Google Fonts (Space Grotesk, JetBrains Mono). Uploaded
files are served by the backend at `GET /api/files/{id}`.

## Dark / light mode
Both themes are first-class and fully specified (spec §12). Define both token sets in `style.css`
scoped by a `data-theme` attribute on `<html>`, default dark, render from a `theme` cookie
server-side to avoid a flash, and flip + persist on toggle with no reload. Verify every screen in
**both** themes.
