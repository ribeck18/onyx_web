# Onyx — Frontend Implementation Specification

**Audience:** an engineer (Claude Code) building the production Onyx web frontend.
**Status:** build-ready. This document is the contract between the approved visual prototype
(`Onyx.dc.html`) and the shipped UI. Where this spec and the older `FRONTEND_DESIGN_BRIEF.md`
disagree on *visuals*, **this spec wins** — it is derived pixel-for-pixel and token-for-token
from the signed-off prototype. The brief still wins for *intent and scope*.

> **How to read this.** §1–§3 set the rules. §4 is the complete design system (copy the tokens
> verbatim). §5–§6 are the reusable shell + components. §7 is the four pages. §8 the four modals.
> §9–§11 the behavior (lifecycle, data, API). §12 dark/light. §13 a build checklist. Nothing
> here is decorative — every px, hex, and rule was chosen. Reproduce exactly; do not "improve."

---

## 1. What you are building

Onyx tracks **vendor data items** (required vendor documents) on construction projects through a
**submit → return** approval lifecycle with an external buyer. An internal employee creates
projects, logs the documents each requires, submits them to the buyer, and records the buyer's
verdict when it returns. The strict three-level hierarchy:

```
Project            26-131 — Acme Plant Expansion
 └── Vendor Data Item (VDI)   Concrete Mix Design        ← carries a lifecycle STATUS
      └── Revision            one submit→return round-trip (immutable history)
           └── File           the uploaded PDF/image, served by id
```

The single most important fact on every screen is **status**. Badges and the lifecycle button are
the visual anchors. Status is **never** set by hand — it is derived entirely from submit/return
actions (ADR 0002). All history is immutable Revision records.

## 2. Tech constraints (non-negotiable)

- **Server-rendered HTML (Jinja2) + minimal vanilla JS.** No React/Vue/Svelte, no HTMX, no build
  step, no SPA. (ADR 0005.)
- **One stylesheet** `static/style.css` and **one script** `static/app.js`. JS scope is small:
  modal open/close, delete-mode toggle, theme toggle, file-preview tab switching, notes save, and
  `fetch()` for mutations.
- **Pages are full documents** at clean URLs. Mutations call the JSON `/api`, then
  `location.reload()` — **except notes**, which update in place without reload.
- **Desktop-first** internal back-office tool. Must not break on a tablet; mobile is not a
  priority. Content column is capped, never edge-to-edge.

> The prototype was authored as a single component for review. **Do not port its structure.**
> Port its *look* (tokens, spacing, type, component anatomy) onto Jinja2 templates + plain CSS
> classes. Translate every inline style in the prototype into a CSS class in `style.css`.

## 3. Routes & templates

| Route | Template | Purpose |
|---|---|---|
| `GET /` | `home.html` | Project gallery |
| `GET /projects/{id}` | `project.html` | Project detail + VDI table |
| `GET /vdi/{id}` | `vdi.html` | VDI detail (the workhorse page) |
| `GET /vdi/{id}/revisions/{rid}` | `vdi.html` (historical mode) | Past-revision snapshot |

All four extend one `base.html` (the global shell, §5). The historical view reuses the VDI
template with a `historical=True` flag plus the warning banner.

---

## 4. Design system

### 4.1 Typography

Two families, loaded from Google Fonts. **No other fonts.**

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
```

- **Space Grotesk** — all UI text, headings, body, buttons, form values. Fallback:
  `'Space Grotesk', system-ui, sans-serif`.
- **JetBrains Mono** — every label, eyebrow, metadata, breadcrumb, table header, code/number,
  badge, timeline date, notes textarea. This monospace voice is core to the aesthetic: anything
  that is a *label, code, count, date, or system string* is mono. Fallback: `'JetBrains Mono', monospace`.

Type scale actually used (px / weight / tracking):

| Role | Family | Size | Weight | Letter-spacing | Notes |
|---|---|---|---|---|---|
| Page H1 (Home "Projects") | Grotesk | 34 | 600 | -0.025em | line-height 1 |
| Page H1 (Project name) | Grotesk | 32 | 600 | -0.025em | line-height 1.05 |
| Page H1 (VDI name) | Grotesk | 40 | 600 | -0.03em | line-height 1 |
| Modal title | Grotesk | 20 | 600 | -0.01em | |
| Card name | Grotesk | 19 | 600 | -0.01em | |
| Hero status word | Grotesk | 26 | 600 | -0.01em | colored by status |
| Body / table cell | Grotesk | 14–15 | 400–500 | — | base font-size 14, line-height 1.5 |
| Eyebrow / section label | Mono | 11 | 500 | 0.18–0.24em | UPPERCASE, `--faint` |
| Field label | Mono | 11 | 500 | 0.06em | UPPERCASE, `--muted` |
| Table header | Mono | 10.5 | 500 | 0.12em | UPPERCASE, `--faint` |
| Badge | Mono | 10.5 (sm) / 12 (lg) | 500 | 0.05em | UPPERCASE |
| Metadata / dates / counts | Mono | 11–12.5 | 400–500 | 0.02–0.04em | `--faint`/`--muted` |
| Wordmark "ONYX" | Grotesk | 18 | 700 | 0.05em | |

**Rule:** labels, eyebrows, table headers, badges, and the wordmark are UPPERCASE. Headings and
body are sentence case. Never set body text below 14px or labels below 10.5px.

### 4.2 Color tokens — the theming contract

The entire UI is painted from **CSS custom properties**. There are two complete sets: dark
(default) and light. Define them on a theme root (see §12) and reference **only** the variables in
every rule — no raw hex in component CSS except where a token doesn't exist.

Token naming convention: each semantic family (`accent`, `ok`, `bad`, `info`, `ns`, `warn`) has up
to four slots — base `--x` (solid fill / dot), `--x-text` (readable text on panel), `--x-line`
(border), `--x-soft` (tinted background). `ns` = "not started" neutral grey.

#### Dark theme (default)

```
--bg:#0f1115;          --panel:#14171d;       --panel-2:#0f1217;     --grid:rgba(255,255,255,.022);
--line:#1c2026;        --line-2:#20242c;      --line-3:#262b34;      --hair:#1c2026;        --row-hover:#14181f;
--text:#e6e9ef;        --muted:#8a91a0;       --faint:#6f7787;
--accent:#4ea1ff;      --accent-glow:rgba(78,161,255,.6);   --accent-soft:rgba(78,161,255,.07);  --accent-line:#2a3a4d;
--ok:#24d49f;          --ok-text:#3ce0ad;     --ok-line:#1d6b4a;     --ok-soft:rgba(36,212,159,.1);
--bad:#e88a5f;         --bad-text:#e88a5f;    --bad-line:#5a3422;    --bad-soft:rgba(226,138,95,.1);
--info:#4ea1ff;        --info-text:#4ea1ff;   --info-line:#2a3a4d;   --info-soft:rgba(78,161,255,.1);
--ns:#5a6473;          --ns-text:#9aa3b2;     --ns-line:#262b34;     --ns-soft:#1a1e26;
--warn-text:#e8b15f;   --warn-line:#5a4422;   --warn-soft:rgba(232,177,95,.1);
--topbar:rgba(18,21,27,.9);                   --topbar-line:#1c2026;
--btn-bg:#4ea1ff;      --btn-text:#08121d;    --btn-hover:#6ab2ff;
--ghost-bg:transparent;--ghost-line:#2c3340;  --ghost-text:#cdd3df;
--del-bg:#a23a17;      --del-line:#5a3422;    --del-soft:rgba(226,138,95,.1);
--disabled-bg:#1a1e26; --disabled-text:#4a525f;--disabled-line:#2c3340;
--field-bg:#0f1217;    --field-line:#2c3340;  --field-text:#cdd3df;
--overlay:rgba(5,7,10,.66);                   --modal:#14171d;       --modal-line:#262b34;
--stripe-a:#12151b;    --stripe-b:#13161d;    --on-bad:#1a0d05;
```

#### Light theme

```
--bg:#f7f8fa;          --panel:#ffffff;       --panel-2:#fbfcfd;     --grid:rgba(40,52,72,.028);
--line:#ebedf1;        --line-2:#e8eaef;      --line-3:#e6e9ee;      --hair:#e8eaef;        --row-hover:#f1f3f6;
--text:#1b2230;        --muted:#6c7585;       --faint:#8a93a3;
--accent:#2f6fed;      --accent-glow:rgba(47,111,237,.35);  --accent-soft:#eef4fd;          --accent-line:#c5dbf7;
--ok:#0fae78;          --ok-text:#0c8f63;     --ok-line:#9ed9bd;     --ok-soft:#e8f6ef;
--bad:#d2693f;         --bad-text:#c2410c;    --bad-line:#f0cdb9;    --bad-soft:#fbeee5;
--info:#2f6fed;        --info-text:#2f6fed;   --info-line:#c5dbf7;   --info-soft:#eef4fd;
--ns:#9aa1ae;          --ns-text:#6c7585;     --ns-line:#e6e9ee;     --ns-soft:#eef0f3;
--warn-text:#9a6a12;   --warn-line:#eccf86;   --warn-soft:#fdf3e0;
--topbar:#ffffff;                             --topbar-line:#e2e6ec;
--btn-bg:#2f6fed;      --btn-text:#ffffff;    --btn-hover:#225fd6;
--ghost-bg:#ffffff;    --ghost-line:#dde2ea;  --ghost-text:#2a313d;
--del-bg:#c2410c;      --del-line:#c2410c;    --del-soft:#fbeee5;
--disabled-bg:#f1f4f8; --disabled-text:#a7aebb;--disabled-line:#dde2ea;
--field-bg:#fbfcfd;    --field-line:#dde2ea;  --field-text:#2a313d;
--overlay:rgba(20,28,40,.34);                 --modal:#ffffff;       --modal-line:#e8eaef;
--stripe-a:#fbfcfd;    --stripe-b:#f3f5f8;    --on-bad:#ffffff;
```

**Status → token family map** (used by badges, dots, hero, timeline, lifecycle button):

| status value | family | meaning |
|---|---|---|
| `not_started` | `ns` (grey) | neutral |
| `submitted` | `info` (blue) | in progress |
| `a` | `ok` (green) | approved (terminal) |
| `d` | `ok` (green) | approved (terminal) |
| `b` | `bad` (orange/red) | rejected, resubmit |
| `c` | `bad` (orange/red) | rejected, resubmit |

Never communicate status by color alone — the text label always rides along.

### 4.3 Spacing, radii, borders, effects

- **Radii:** `4px` standard (buttons, inputs, cards, panels, table-less containers); `3px` small
  (badges, tabs, the wordmark icon inner); `6px` modal panel. No large/pill radii anywhere except
  status dots which are circles (`999px`).
- **Borders:** hairlines everywhere. `1px solid var(--hair)` for internal dividers and table cell
  bottoms; `1px solid var(--line-3)` for card/container outlines; `1px solid var(--line-2)`/`--line`
  for slightly stronger edges. Dashed (`1px dashed var(--line-3)`) only for "empty / not started"
  placeholders.
- **Content width:** every page's content (and the top bar's inner row) is `max-width:1180px;
  margin:0 auto; padding:0 28px`.
- **Section rhythm:** page headers `padding:40px 0`; section blocks `~24–30px` vertical;
  card grid / table bottom padding `80px` (breathing room above the fold bottom).
- **Background grid:** the app shell carries a faint blueprint grid —
  `background-image: linear-gradient(var(--grid) 1px, transparent 1px), linear-gradient(90deg, var(--grid) 1px, transparent 1px); background-size:40px 40px; background-attachment:fixed;`
  over `background:var(--bg)`. This is part of the brand; keep it.
- **Glows:** the wordmark diamond and the hero status dot use a colored `box-shadow` glow
  (`0 0 12px var(--accent-glow)` / `0 0 12px var(--<status>)`). Used sparingly — only those two
  places plus the "current" timeline dot (`0 0 10px`).
- **Gradient dividers:** the rule under a project/VDI header is
  `height:1px; background:linear-gradient(90deg, var(--accent), var(--ok) ~38–40%, transparent); opacity:.4–.45`.
  Plain dividers elsewhere are `height:1px; background:var(--hair)`.
- **Modal shadow:** `box-shadow:0 24px 70px rgba(0,0,0,.45)`.
- **Transitions:** only subtle ones — `border-color .12s` on cards, `background .1s` on table rows.
  No elaborate motion. One keyframe `onyxPop` for modal entrance:
  `@keyframes onyxPop { from { opacity:0; transform:translateY(8px) scale(.99) } to { opacity:1; transform:none } }`
  applied as `animation:onyxPop .16s ease`.

### 4.4 Global resets

```css
*{box-sizing:border-box;}
html,body{margin:0;padding:0;}
textarea,input,select,button{font-family:inherit;}
button{white-space:nowrap;}
```

---

## 5. Global shell (`base.html`)

A sticky top bar, an optional historical banner, the centered content column, and the (single)
modal mount point.

### 5.1 Top bar

- Container: `position:sticky; top:0; z-index:40; background:var(--topbar); border-bottom:1px solid
  var(--topbar-line); backdrop-filter:blur(6px);`
- Inner row: capped 1180px, `height:56px`, flex, `gap:18px`, `align-items:center`.
- **Wordmark** (left, links to `/`): a 16px square rotated 45° (the "onyx" gem) filled `--accent`
  with `box-shadow:0 0 12px var(--accent-glow)`, followed by **ONYX** (Grotesk 18/700, tracking
  .05em, `--text`). `gap:11px`.
- **Divider:** a 1px × 20px `--line-3` vertical rule.
- **Breadcrumb** (mono 12, `--faint`): the primary "back up" mechanism. Separators are an accent
  `/`. Segments before the last are links (`--muted`, hover `--text`); the last is plain `--text`
  and may ellipsis-truncate. Forms by depth:
  - Home: `PROJECTS` (single non-link).
  - Project: `HOME / 26-131` (project_number; HOME links to `/`).
  - VDI / historical: `HOME / 26-131 / CONCRETE MIX DESIGN` (VDI name uppercased; HOME and the
    project_number are links).
- **Right cluster** (`margin-left:auto`, `gap:14px`):
  - On VDI pages, a faint mono tag `VDI-{id}` (11px, tracking .12em, `--faint`).
  - **Theme toggle button** (ghost): mono 11px, shows `☀ Light` in dark mode and `☾ Dark` in light
    mode. See §12.

### 5.2 Historical banner (historical route only)

Full-width strip directly under the top bar: `background:var(--warn-soft); border-bottom:1px solid
var(--warn-line)`. Inner capped row, mono 12px `--warn-text`: a 16px square `!` glyph box (1px
border) + **"VIEWING PAST REVISION — NOT THE CURRENT STATE OF THIS VDI."** + right-aligned
underlined link **"RETURN TO CURRENT ↩"** → `/vdi/{id}`.

### 5.3 Content column

`max-width:1180px; margin:0 auto; padding:0 28px` wrapping each page's body.

---

## 6. Component library

Build these as reusable CSS classes / Jinja macros. Sizes and colors are exact.

### 6.1 Buttons

| Variant | Use | Spec |
|---|---|---|
| **Primary** | New Project, New VDI, modal submit, Download | `padding:9px 16px; radius:4px; border:1px solid var(--btn-bg); background:var(--btn-bg); color:var(--btn-text); font:600 13px Grotesk; tracking:.02em`. Hover `background:var(--btn-hover)`. |
| **Ghost** | Edit, Cancel, theme toggle | `padding:8px 15px; radius:4px; border:1px solid var(--ghost-line); background:var(--ghost-bg); color:var(--ghost-text); font:600 13px`. Hover `border-color:var(--accent-line); color:var(--text)`. |
| **Delete-toggle** | Home/Project "Delete" / "Done" | inactive = ghost-ish (`--ghost-line` border, `--ghost-bg`, `--muted` text); active = `border/background:var(--del-line)/var(--del-bg); color:#fff`, label switches to "Done". |
| **Lifecycle** (big) | the one VDI action | `padding:13px 26px; radius:4px; font:600 15px Grotesk; tracking:.03em`. Fill depends on status — see §9. |
| **Save notes** | next to notes | mono 12.5px 600, tracking .04em; enabled = `--accent` text on `--accent-soft` with `--accent-line` border; disabled = `--disabled-*`. |

Disabled buttons: `background:var(--disabled-bg); color:var(--disabled-text); border:1px solid
var(--disabled-line); cursor:not-allowed`.

### 6.2 Status badge (the most repeated element)

Inline pill. Anatomy: `display:inline-flex; align-items:center; gap:7px; border-radius:3px;
font-family:JetBrains Mono; font-weight:500; letter-spacing:.05em; white-space:nowrap;
background:var(--K-soft); color:var(--K-text); border:1px solid var(--K-line);` where `K` is the
status family from §4.2. A leading dot: `width/height` `6px` (small) / `8px` (large),
`border-radius:999px; background:var(--K)`.

| size | padding | font-size | dot |
|---|---|---|---|
| small (tables, timeline) | `3px 9px` | 10.5px | 6px |
| large (reserved) | `5px 12px` | 12px | 8px |

**Badge labels** (exact strings):

| status | label |
|---|---|
| `not_started` | `NOT STARTED` |
| `submitted` | `SUBMITTED` |
| `a` | `APPROVED /A` |
| `d` | `APPROVED /D` |
| `b` | `REJECTED /B` |
| `c` | `REJECTED /C` |

### 6.3 Hero status (VDI header only)

Not a pill — a larger inline treatment: a glowing dot (`11px`, `box-shadow:0 0 12px var(--K)`),
the status **word** in Grotesk 26/600 colored `--K-text` (`Not started` / `Submitted` / `Approved`
/ `Rejected`), and, for returned states, the letter code (`/A` `/B` `/C` `/D`) in mono 14px `--K`,
bottom-aligned.

### 6.4 Project card (Home grid)

`background:var(--panel); border:1px solid var(--line-3); border-radius:4px; padding:18px 18px 16px;
cursor:pointer`. Hover: `border-color:var(--accent-line)`. Contents:
- Top row (space-between): `project_number` (mono 12/500, `--accent`) · cue (mono 11): `N OPEN`
  in `--info-text` when open items exist, else `ALL CLEAR` in `--ok-text`.
- Name (Grotesk 19/600, `margin-top:12px`).
- Footer: `margin-top:18px; padding-top:14px; border-top:1px solid var(--hair)`; mono 11.5px
  `--faint` → `N ITEMS`.

"Open" = VDIs with status in {`not_started`, `submitted`, `b`, `c`}.

### 6.5 VDI table (Project detail)

`width:100%; border-collapse:collapse; font-size:14px`. Header row `border-bottom:1px solid
var(--line-3)`; each `th` mono 10.5/500 tracking .12em `--faint`, left-aligned, UPPERCASE. Columns
and widths:

| col | header | width | cell rendering |
|---|---|---|---|
| 1 | NAME | auto | Grotesk 500, `--text` |
| 2 | ITEM | 60px | mono, `--muted` → `item_number` |
| 3 | SUBMITTAL | 140px | mono → `submittal_number` or `—`; `—` colored `--faint`, value `--muted` |
| 4 | CODE | 70px | mono 12/500 `--accent`, shows uppercase code (e.g. `PS`), `title=` full label, `cursor:help` |
| 5 | STATUS | 200px | small status badge |

Cells: `padding:14px` (first/last slightly trimmed toward the edge), `border-bottom:1px solid
var(--hair)`. Whole row is a link to `/vdi/{id}`, `cursor:pointer`, hover `background:var(--row-hover)`.

### 6.6 Inputs & form fields

- Field label: a block `<span>` above the control — mono 11/500, tracking .06em, `--muted`,
  UPPERCASE, `margin-bottom:7px`. Required fields append ` *` in `--bad-text`.
- Text input / select / textarea base: `width:100%; padding:10px 12px; border:1px solid
  var(--field-line); border-radius:4px; font-size:14px; background:var(--field-bg);
  color:var(--field-text); outline:none; font-family:Grotesk`. Textareas add `resize:vertical` and
  an explicit height.
- File input: `padding:14px; border:1px dashed var(--field-line); border-radius:4px;
  background:var(--field-bg); color:var(--field-text); cursor:pointer`.
- Stack fields with `gap:13–15px`. Group sections inside the VDI modal with a mono 10.5px `--faint`
  group label (IDENTITY / CLASSIFICATION).

### 6.7 File-preview pane (VDI detail, left column)

The pane content is chosen by the active file's `content_type` (§9). Five mutually exclusive states:

1. **PDF (have bytes):** `<iframe src="/api/files/{id}">` at `width:100%; height:480px; border:1px
   solid var(--line-3); border-radius:4px; background:#525659`.
2. **Image:** centered `<img>` (max 480px tall, radius 3px) inside a `--panel-2` framed box.
3. **Placeholder** (previewable type but bytes not yet available — only relevant if you ever render
   server-side without a live URL): a striped box —
   `background:repeating-linear-gradient(45deg, var(--stripe-a) 0 11px, var(--stripe-b) 11px 22px)`,
   a little document glyph, and mono caption `PDF · RENDER INLINE · /api/files/{id}`. In production
   you have real URLs, so this rarely shows; keep it as the graceful fallback.
4. **Download** (non-previewable type, e.g. `.dwg`): a `--panel-2` box with an extension chip (e.g.
   `DWG`), the `original_name`, mono caption `CANNOT PREVIEW INLINE`, and a **primary** "Download
   file" link to `/api/files/{id}` (`target="_blank"`).
5. **Empty** (`not_started`, no revision): a **dashed** box — "This VDI has not been started." +
   mono `SUBMIT THE FIRST REVISION TO BEGIN THE LIFECYCLE`.

Preview header row above the pane (mono 11 tracking .18em `--faint`): the title
(`CURRENT FILE` live / `REVISION FILE` historical), optional **SUBMITTED / RETURNED** tab toggle
(only when the revision has *both* files), the filename (`--muted`), and a right-aligned
`OPEN ↗` link to the file in a new tab. Tabs: `padding:5px 12px; radius:3px; mono 11/500`; active
tab = `--accent` text on `--accent-soft` with `--accent-line` border; inactive = `--muted` on
transparent with `--line-3` border.

### 6.8 Revision timeline (VDI detail, right column)

Heading `REVISION LOG` (mono 11 tracking .2em `--faint`). A vertical rail: `position:relative;
padding-left:24px`, with an absolute spine `left:6px; top/bottom:6px; width:1px;
background:linear-gradient(180deg, var(--bad), var(--ok)); opacity:.5`. Entries oldest→newest, each
`margin-bottom:24px; cursor:pointer`:
- A node dot at `left:-23px; top:3px; 13px; border-radius:999px; background:var(--bg); border:2px
  solid var(--K)` (K = that revision's status family); the **current** revision's dot adds
  `box-shadow:0 0 10px var(--K)`.
- Row: `REV {n}` (mono 600 14px) + a `CURRENT` tag (mono 10, `--accent`, `--accent-line` border)
  when current + right-aligned small status badge.
- Dates line (mono 11 `--faint`): `SUB {yyyy-mm-dd} · RET {yyyy-mm-dd}` or `· AWAITING RETURN`.
- Click → `/vdi/{id}/revisions/{rid}` (the latest/current entry links back to `/vdi/{id}`).

Empty: mono `NO REVISIONS YET.`

### 6.9 Notes box (VDI detail, left column)

Label `NOTES` (mono 11 tracking .2em `--faint`), with a `READ-ONLY` warn-tag in historical mode and
a right-aligned `SAVED ✓` (`--ok-text`) flash after saving. A `<textarea>` bound to the VDI's
`notes`: `height:84px; mono 12.5/1.55; background:var(--field-bg)`; in historical/read-only mode it
is `disabled` and text is `--faint`. Below: a **Save notes** button, disabled until the text differs
from the saved value. Save → `PATCH /api/vdi/{id}` `{notes}` → update in place + flash `SAVED ✓` for
~2.2s. **No page reload.**

### 6.10 Modal (one reusable shell, 4 content bodies)

- Overlay: `position:fixed; inset:0; z-index:100; background:var(--overlay);
  backdrop-filter:blur(3px); display:flex; align-items:flex-start; justify-content:center;
  padding:60px 20px; overflow:auto`. Click on overlay closes.
- Panel: `width:100%; max-width:520px; background:var(--modal); border:1px solid var(--modal-line);
  border-radius:6px; box-shadow:0 24px 70px rgba(0,0,0,.45); animation:onyxPop .16s ease`. Click
  inside does **not** close (`stopPropagation`).
- Header: title (Grotesk 20/600) + optional intro (`--muted` 13.5/1.55) + a 32px square ✕ close
  button (ghost-ish, hover `--accent-line`/`--text`).
- Body: `padding:20px 24px`. Optional inline error banner at top: `background:var(--bad-soft);
  border:1px solid var(--bad-line); color:var(--bad-text); radius:4px; padding:10px 13px; 13px`.
- Footer: right-aligned `padding:18px 24px 22px; gap:10px` → **Cancel** (ghost) + **primary submit**
  (label varies by modal/mode).
- Closes on ✕, overlay click, and **Esc**. On submit: `fetch()` → 2xx → `location.reload()`;
  non-2xx → keep open, show inline error, preserve input.

---

## 7. Pages

### 7.1 Home — Project gallery (`/`)

- **Header** (`padding:40px 0 20px`, flex end/space-between): left = eyebrow `WORKSPACE` (mono 11
  tracking .22em `--faint`) over H1 **Projects** (34/600) over count `N PROJECTS` (mono 12
  `--muted`). Right = **Delete** toggle + **+ New Project** (primary).
- Hairline `1px var(--hair)`, `margin-bottom:30px`.
- **Grid:** `display:grid; grid-template-columns:repeat(auto-fill, minmax(300px,1fr)); gap:18px;
  padding-bottom:80px`. One project card (§6.4) each, linking to `/projects/{id}`.
- **Delete mode:** toggling "Delete" arms the gallery — each card border → `--del-line`,
  `project_number` and cue recolor to `--bad-text`, cue text → `CLICK TO DELETE`. Clicking a card
  fires `confirm("Delete project {number} — {name}? This removes all its vendor data items.")` →
  `DELETE /api/projects/{id}` → reload. Button label → "Done"; toggling again disarms.
- **Empty state:** centered box (`border:1px solid var(--line-3); radius:4px; background:var(--panel);
  padding:80px 20px`): "No projects yet." + muted line + **+ New Project** primary.

### 7.2 Project detail (`/projects/{id}`)

- **Header** (`padding:40px 0 0`): `project_number` (mono 12 `--accent`) over H1 `name` (32/600)
  over `description` (`--muted` 15/1.6, `max-width:64ch`) when present. Right-aligned **Edit** ghost
  → Project modal (edit mode).
- **Gradient divider** (§4.3), `margin:30px 0 0`.
- **Section header** (`padding:26px 0 14px`, space-between): label `VENDOR DATA ITEMS` (mono 11
  tracking .2em `--faint`) + **Delete** toggle + **+ New VDI** primary.
- **VDI table** (§6.5), `padding-bottom:80px`.
- **Delete mode:** mirrors the gallery — every row gets `box-shadow:inset 3px 0 0 var(--bad)` +
  `background:var(--bad-soft)`; clicking a row → `confirm("Delete VDI "{name}"? This removes its
  revision history.")` → `DELETE /api/vdi/{id}` → reload.
- **Empty state:** "No vendor data items yet." + **+ New VDI** primary.

### 7.3 VDI detail (`/vdi/{id}`) — the workhorse

Top-to-bottom regions inside the content column:

1. **Hero** (`padding:40px 0 26px`, flex space-between, wrap): left = eyebrow `VENDOR DATA ITEM ·
   {item_number}` (mono 11 tracking .24em `--faint`), H1 `name` (40/600), meta line (mono 12.5
   `--muted`) `SUB {submittal or —} · CODE {code accent} · {approval_type label}`. Right =
   `STATUS` label + **hero status** (§6.3) + **Edit** ghost → VDI modal (edit mode).
2. **Gradient divider.**
3. **Specification** (`padding:26px 0`): label `SPECIFICATION`, then a flexible row of four attribute
   cells separated by `1px var(--hair)` right-borders — **APPROVAL TYPE**, **SUBMIT CODE** (full
   label), **SPEC / DWG REF**, **SUBMITTAL** — each a mono 10.5 label over a 15px value. Below, the
   `description` (`--muted` 15/1.6, `max-width:74ch`) when present.
4. **Plain divider.**
5. **Lifecycle row** (`padding:24px 0`, flex, wrap): label `LIFECYCLE` (mono 11, width 120px) + the
   single **lifecycle button** (§9) + a mono 12 `--faint` note describing the next action.
6. **Plain divider.**
7. **Two columns** (`padding:30px 0 80px; display:flex; gap:48px; flex-wrap:wrap`):
   - **Left (`flex:1 1 440px`):**
     - **Buyer comments** block (only if the current revision has `comments`): `border-left:2px
       solid var(--accent); padding-left:18px`; label `BUYER COMMENTS` (mono 11, `--accent`) + the
       comment text (15/1.65, `--text`).
     - **File preview** (§6.7) of the current revision.
     - **Notes box** (§6.9).
   - **Right (`flex:1 1 320px`):** **Revision timeline** (§6.8).

**Which file/revision drives the page (live mode):** the *latest* revision. If status is
`submitted`, preview its `submit_file`; if returned (`a`/`b`/`c`/`d`), preview its `return_file`
(tabs let the user flip to the submitted file). If `not_started` (no revisions), the preview is the
empty state and there's no comments block.

### 7.4 Historical revision view (`/vdi/{id}/revisions/{rid}`)

Identical layout to 7.3 with these differences, all driven by the **chosen** revision `rid`:
- The **historical warning banner** (§5.2) shows under the top bar.
- Hero status, preview, buyer comments, and the preview title (`REVISION FILE`) reflect the chosen
  revision, **not** the current VDI status.
- The **lifecycle button is disabled** (shows `SUBMIT`, greyed) with note `ACTIONS AVAILABLE ONLY ON
  CURRENT VDI.`
- The **notes box is read-only** (disabled, `--faint`) with a `READ-ONLY` tag — notes are
  item-level, not versioned, so it still shows the VDI's current notes.
- In the timeline, the chosen revision is marked current; clicking the true-latest entry returns to
  `/vdi/{id}`.

---

## 8. Modals (4)

All share the shell (§6.10). All required fields marked `*`. Submit → `fetch()` → 2xx reload /
non-2xx inline error.

### 8.1 Project modal — create & edit (same markup, two modes)

Fields: `project_number*` (text, e.g. `26-131`), `name*` (text, e.g. `Acme Plant Expansion`),
`description` (textarea, ~78px).
- Create: title **New Project**, submit **Create Project** → `POST /api/projects`.
- Edit: title **Edit Project**, submit **Save Changes**, pre-filled → `PATCH /api/projects/{id}`.
- Validation: project_number and name required (inline error "Project number and name are required.").

### 8.2 VDI modal — create & edit

Grouped fields:
- **IDENTITY:** `item_number*` (number, ~120px wide) + `name*` (text) on one row; then
  `submittal_number` (text, placeholder "often blank until submitted").
- **CLASSIFICATION:** `approval_type*` (select, 2 options), `submit_code*` (select, 16 options),
  `spec_drawing_reference` (text, e.g. `Spec §3.4 / Dwg S-201`).
- `description` (textarea ~64px).
- `notes` (textarea ~64px) — **create mode only**; in edit mode notes are omitted (they have their
  own box on the page).
- Create: title **New Vendor Data Item**, submit **Create VDI** → `POST /api/vdi` (with the page's
  `project_id`). Edit: title **Edit Vendor Data Item**, submit **Save Changes**, pre-filled →
  `PATCH /api/vdi/{id}`.
- Validation: item_number + name required; submit_code must be chosen. **Duplicate item_number →
  409** must render inline under the item_number field: *"Item number already used in this project."*

### 8.3 Submit modal (also used for Revise)

A single required **file input**. Intro reads "Submit the first revision of {name}." from
`not_started`, or "Upload a corrected revision for {name}." from `b`/`c`. Submit label **Submit** /
**Resubmit**. Sends multipart `FormData` (`file`) to `POST /api/vdi/{id}/submit`. Block empty file
client-side. Helper line: "Uploads as a new revision and moves this item to **Submitted**."

### 8.4 Return modal

Fields: `return_code*` (select of the **four** codes — `A — Approved`, `B — Rejected, resubmit`,
`C — Rejected, resubmit`, `D — Approved`; never offer not_started/submitted), `file*` (required
upload of the returned file), `comments` (optional textarea, ~78px). Title **Record Buyer Return**,
submit **Record Return**. Sends multipart `FormData` (`return_code`, `file`, `comments?`) to
`POST /api/vdi/{id}/return`.

---

## 9. Lifecycle action button — state machine

The single VDI action button is **fully determined by `status`** (maps to
`SUBMITTABLE_STATUSES = {not_started, b, c}`, `RETURNABLE_STATUSES = {submitted}`). Big button spec
in §6.1; the fill color and behavior:

| status | label | fill | enabled | opens | endpoint | note text |
|---|---|---|---|---|---|---|
| `not_started` | **SUBMIT** | `--btn-bg` (accent) | yes | Submit modal | `POST /api/vdi/{id}/submit` | UPLOAD THE FIRST REVISION AND SEND TO BUYER. |
| `submitted` | **RETURN** | `--info` | yes | Return modal | `POST /api/vdi/{id}/return` | RECORD THE BUYER'S VERDICT FOR THIS REVISION. |
| `b` | **REVISE** | `--bad` (text `--on-bad`) | yes | Submit modal | `POST /api/vdi/{id}/submit` | UPLOAD A CORRECTED REVISION AND RESUBMIT. |
| `c` | **REVISE** | `--bad` (text `--on-bad`) | yes | Submit modal | `POST /api/vdi/{id}/submit` | UPLOAD A CORRECTED REVISION AND RESUBMIT. |
| `a` | SUBMIT | `--disabled-*` | **no** | — | terminal (approved) | SEQUENCE COMPLETE · NO ACTION REQUIRED. |
| `d` | SUBMIT | `--disabled-*` | **no** | — | terminal (approved) | SEQUENCE COMPLETE · NO ACTION REQUIRED. |
| historical (any) | SUBMIT | `--disabled-*` | **no** | — | — | ACTIONS AVAILABLE ONLY ON CURRENT VDI. |

End-to-end flow to verify: `not_started` → Submit (upload) → reload → `submitted` → Return (code B +
file + comments) → reload → `b` → Revise (upload) → reload → `submitted` → Return (code A) → reload
→ `a` (button disabled; timeline shows Rev 0 = B, Rev 1 = A).

---

## 10. Data model & enum label maps

Field shapes are the pydantic `*Read` schemas (`app/.../schema.py`). **Never** show a raw enum
value to a user — always map to the label.

**Project** (`ProjectRead`): `id`, `project_number`, `name`, `description?`, `created_at`,
`updated_at`. No status. Create body `{project_number, name, description?}`; update = any subset.

**VDI** (`VdiRead`): `id`, `project_id`, `item_number`, `submittal_number?`, `name`, `description?`,
`approval_type`, `submit_code`, `spec_drawing_reference?`, `notes?`, `status`, `created_at`,
`updated_at`. Create body includes `project_id` + all 8 editable fields; update = any subset but
**never `status`** (the API rejects it; status is lifecycle-only).

**Revision** (`RevisionRead`): `id`, `vendor_data_item_id`, `revision_number` (0-based),
`submit_file` (always present), `submitted_at`, `return_file?`, `returned_at?`, `comments?`,
`status`, timestamps. Immutable.

**File** (`FileRead`): `id`, `original_name`, `content_type`. Served at `GET /api/files/{id}`.
`stored_path` is never exposed.

### ApprovalType
`mandatory_approval` → **Mandatory Approval** · `information_only` → **Information Only**

### SubmitCode (show "CODE — Meaning"; compact column shows just the code with full label on hover)
`ac` As Completed · `afi` At Final Inspection · `aro` After Receipt of Order · `at` After Test ·
`bc` Before Contract Awarded · `bfa` Before Final Acceptance · `bfs` Before Fabrication Start ·
`pds` Prior to Delivery on Site · `ps` Prior to Shipment · `pt` Prior to Test ·
`ptc` Prior to Construction · `pti` Prior to Installation · `ptp` Prior to Purchase ·
`ptw` Prior to Welding · `ros` Prior to Removal Off-Site · `ts` Time of Shipment

### SubmitStatus → badge label / family (§4.2, §6.2)
`not_started` NOT STARTED (ns) · `submitted` SUBMITTED (info) · `a` APPROVED /A (ok) ·
`d` APPROVED /D (ok) · `b` REJECTED /B (bad) · `c` REJECTED /C (bad)

### Return codes (Return modal select — these 4 only)
`a` A — Approved · `b` B — Rejected, resubmit · `c` C — Rejected, resubmit · `d` D — Approved

### Date formatting
- Long (descriptions, where used): `Mar 2, 2026` (`toLocaleString` month short / day numeric / year).
- Mono / timeline / table: `YYYY-MM-DD`.
- Null dates render as em-dash `—`.

---

## 11. API surface (JSON under `/api`) & mutation pattern

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| POST | `/api/projects` | `{project_number, name, description?}` | 201 ProjectRead | — |
| GET | `/api/projects` | — | 200 ProjectRead[] | — |
| GET | `/api/projects/{id}` | — | 200 ProjectRead | 404 |
| PATCH | `/api/projects/{id}` | subset | 200 ProjectRead | 404 |
| DELETE | `/api/projects/{id}` | — | 204 | 404 |
| POST | `/api/vdi` | VdiCreate (incl. `project_id`) | 201 VdiRead | 404 (project), **409 dup item_number** |
| GET | `/api/vdi?project_id=` | — | 200 VdiRead[] | — |
| GET | `/api/vdi/{id}` | — | 200 VdiRead | 404 |
| PATCH | `/api/vdi/{id}` | subset (never status) | 200 VdiRead | 404 |
| POST | `/api/vdi/{id}/submit` | multipart `file` | 200 VdiRead | 404, **409 not submittable**, 400 empty |
| POST | `/api/vdi/{id}/return` | multipart `return_code`, `file`, `comments?` | 200 VdiRead | 404, **409 not returnable**, 422 bad code |
| DELETE | `/api/vdi/{id}` | — | 204 | 404 |
| GET | `/api/vdi/{id}/revisions` | — | 200 RevisionRead[] | — |
| GET | `/api/vdi/{id}/revisions/latest` | — | 200 RevisionRead | 404 |
| GET | `/api/vdi/{id}/revisions/{rid}` | — | 200 RevisionRead | 404 |
| GET | `/api/files/{id}` | — | file bytes (orig name + content type) | 404 |

**Mutation pattern (app.js):**
- JSON mutations (project/VDI create-edit) → `fetch(url, {method, headers:{'Content-Type':
  'application/json'}, body: JSON.stringify(payload)})`.
- File mutations (submit/return) → `fetch(url, {method:'POST', body: FormData})` (no manual
  Content-Type).
- On 2xx → `location.reload()`. On non-2xx → read `detail`, show inline modal error, keep input.
  The duplicate-item-number 409 (`detail: "Item number already used in this project"`) renders under
  the item_number field specifically.
- **Notes are the only in-place mutation:** `PATCH /api/vdi/{id}` `{notes}` → update DOM + flash
  `SAVED ✓`, no reload.
- Submit and Return both return the updated **VdiRead** (not the revision); the UI just reloads.

Page GET routes server-render from the same services; the prototype's mock arrays exist only to
demonstrate shape and can be deleted.

---

## 12. Dark / light mode

The prototype ships both palettes (§4.2) and a toggle. Production implementation:

- **Theme application:** put both token sets in `style.css` scoped by a `data-theme` attribute on
  `<html>` (or `<body>`):
  ```css
  :root, [data-theme="dark"]  { /* dark tokens */ }
  [data-theme="light"]        { /* light tokens */ }
  ```
  Default is **dark**. Render the attribute server-side from a `theme` cookie so there is **no
  flash** of the wrong theme on load.
- **Toggle button** (top bar, §5.1): label/icon reflect the *target* — `☀ Light` while dark,
  `☾ Dark` while light. On click, `app.js` flips `document.documentElement.dataset.theme`, writes
  the `theme` cookie (and/or `localStorage`), **no reload**. Because everything is CSS variables,
  the whole UI repaints instantly.
- **Every component already references tokens**, so neither template nor JS needs theme branches
  beyond the toggle. The only literal colors permitted are: the PDF iframe backdrop `#525659`, the
  delete-mode card text `#fff` on `--del-bg`, and any value that *is* a token. Do not hardcode
  anything else — add a token if you need one.
- **Parity requirement:** both themes must be visually complete. Verify every screen, badge family,
  modal, the grid background, gradient dividers, glows, and disabled states in **both** modes.
  Contrast must stay legible (the light palette deliberately darkens `--*-text` relative to `--*`).

---

## 13. Interaction & JS behavior summary (`app.js`)

Keep it tiny and event-delegated:
1. **Modal open/close** — open by `data-` triggers; close on ✕, overlay click, **Esc**. Reset
   inline error on open.
2. **Create/edit dual mode** — same modal markup; mode sets title, submit label, target URL, and
   pre-fills (edit). VDI edit hides the notes field.
3. **Delete-mode toggle** (Home + Project) — flips an `is-deleting` class on the grid/table;
   card/row click switches between navigate and `confirm()`+DELETE; button label toggles
   Delete/Done.
4. **Lifecycle button** — opens the correct modal per §9; disabled states are inert.
5. **File-preview tabs** — switch SUBMITTED/RETURNED `iframe`/`img` source; only present when both
   files exist.
6. **Notes** — enable Save when textarea ≠ saved value; on save PATCH `{notes}`, update baseline,
   flash `SAVED ✓` ~2.2s, no reload.
7. **Theme toggle** — §12.
8. **Fetch helper** — one wrapper handling JSON vs FormData, 2xx-reload vs inline-error, and the
   409 dup-item special case.

No client-side routing, no state library, no framework.

---

## 14. Out of scope (do not build)

Auth/login, user accounts, buyer email notifications, PDF generation, cloud storage, global
search/filter, project-level status, bulk actions, pagination (counts are small). Status is never
directly editable anywhere.

---

## 15. Sample / seed data (shape must match the `*Read` schemas)

Use realistic content so screens read true. Project **26-131 — Acme Plant Expansion** with VDIs that
exercise every status and every preview branch:

| VDI | item | submittal | code | status | revisions |
|---|---|---|---|---|---|
| Concrete Mix Design | 12 | 26-131-003 | ps | `a` (approved, terminal) | Rev0 = C (rejected, PDF + redline PDF), Rev1 = A (approved PDF) |
| Structural Steel Shop Drawings | 7 | — | bfs | `submitted` | Rev0 out for review (`.dwg` → download fallback) |
| Anchor Bolt Layout | 3 | 26-131-001 | ptc | `b` (rejected) | Rev0 returned B, comments + PNG markup (image branch) |
| Fireproofing Submittal | 15 | 26-131-004 | pti | `c` (rejected) | Rev0 returned C, PDF markup |
| Electrical Panel Schedules | 9 | 26-131-002 | aro | `d` (approved) | Rev0 approved, no comments |
| O&M Manuals | 21 | — | afi | `not_started` | none (empty preview + Submit) |

Plus gallery-filler projects **25-094 — Riverside Pump Station** and **26-007 — North Terminal
Retrofit** (no/few VDIs). Include ≥1 PDF, ≥1 image, and ≥1 non-previewable type (`.dwg`) to exercise
all three preview branches.

---

## 16. Acceptance checklist

- [ ] All four pages render server-side at their routes and navigate via real links + breadcrumb.
- [ ] Tokens copied verbatim; **both** dark and light themes complete, toggle persists via cookie,
      no flash on load.
- [ ] Status badge correct (label + family color + dot) in table, hero, and timeline for all six
      statuses.
- [ ] Lifecycle button renders correctly (label, fill, enabled/disabled, note) for all six statuses
      and historical.
- [ ] All four modals open/close (✕ / overlay / Esc), dual create-edit modes work, 409 dup
      item_number shows inline under item_number.
- [ ] File preview shows all branches: PDF iframe, image, download fallback, empty/not-started; tabs
      appear only when both files exist; OPEN ↗ and Download work.
- [ ] Notes save in place with `SAVED ✓`, no reload; read-only + banner in historical view.
- [ ] Delete-mode (gallery + table) arms visually, confirms, deletes, reloads, disarms.
- [ ] Empty states for no-projects and no-VDIs.
- [ ] Background grid, gradient dividers, glows, and `onyxPop` modal animation present.
- [ ] One `style.css`, one `app.js`, no framework, no build step.
