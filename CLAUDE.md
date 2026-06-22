## Rules
- Ask the user before importing a new package or library.
- Maintain a requirements.txt
- Keep md files, excluding README.md, and CLAUDE.md in the gitignore
- All new .md files (excluding README.md and CLAUDE.md) must be placed in the `claude_brain/` directory at the project root.
- As this is a FastAPI app, use async.

## Style

- Prefer simple implementation and code rather than clever implementations
- Avoid repetitive code; if something is done more than 5 times, make a function
- Keep files in the correct domain folder (i.e things about vendor data in the vdi folder)
## Conventions

- Git branch names are in camel case and use dashes. Example: Feature-FileSaves
- Variable and function names use snake case. No single-letter variables, even when writing a for loop.
- Type annotations: if the type is ambiguous or when the return type is unclear.
- Classes should be kept in separate files dedicated to only that class. The file name matches the class name.
- Use modern union syntax: str | None, not Optional[str]. list[Project], not List[Project].
- Use from __future__ import annotations at the top of any file that needs forward references or has circular import concerns.
- Keep data things sorted by domain; if it is vendor data code, store it in vdi/
	- There are some exceptions to this rule, such as when code touches several places. Make sure these types of files are stored and named meaningfully. 
	- You should try your best to separate by domain; this makes clear deep modules

## Naming
- Files: Lowercase snake_case for all .py files(seed_data.py, general_service.py). UPPER_SNAKE_CASE for .md files.
- Classes: PascalCase (Project, ReadSubmittal, UserManager).
- Functions and variables: snake_case (create_project, get_engine, read_project).
- Enum members: UPPER_SNAKE_CASE (NOT_STARTED, APPROVED_W_COMMENTS).
- Enum values: lowercase snake_case strings ("not_started", "approved_w_comments").

## Documentation

- Code should be self-documenting with clear variable, class, and function names.
- Write docstrings for all functions.
- When comments are written they should address the why rather than the what
## Packages

- Use minimal packages and libraries; prefer the standard library

## Database

- Use SQLAlchemy to interact with the database.
- Use the async engine and AsyncSession everywhere (service signatures take `session: AsyncSession`).
- Sessions are created in the route layer and passed down — services never create their own sessions.
- Create functions instantiate the model, add to session, then flush (not commit). Transaction control stays in the route layer.
- list getters should wrap the result in a list.
- Use Mapped[...] with mapped_column(...) for all columns. Always specify the SQLAlchemy type explicitly
- Use string-based relationship targets with TYPE_CHECKING-guarded imports to avoid circular dependencies

## FastAPI

- Every route file creates a single APIRouter
- Routes that deal with the database call service functions, commit, and return the schema

## Frontend (server-rendered)

- Server-rendered Jinja2 + one `static/style.css` + one `static/app.js` (vanilla JS). No framework, no build step, no HTMX (ADR 0005).
- HTML page routes live in a per-domain `web_pages.py` (a single APIRouter, mounted at root with **no** `/api` prefix). They render templates by calling services **directly** — never by self-calling the JSON `/api`.
- All page rendering goes through the one `Jinja2Templates` in `app/web/templating.py`; its `render()` helper injects the current theme from the `theme` cookie (default dark) so there is no flash. Static is mounted once in `app.py`.
- Never show a raw enum value to a user. Human labels, badge strings, and the status color family (`ns`/`info`/`ok`/`bad`) come from `app/web/labels.py`, exposed to templates as Jinja globals/filters. `labels.py` is the source of truth for enum meanings (keep the enum source comments minimal to avoid drift).
- Mutations from the UI call the JSON `/api` via a small `fetch` helper: 2xx → `location.reload()`, non-2xx → inline modal error. The only in-place mutation is the notes `PATCH` (no reload). The duplicate-item-number 409 renders inline under the item_number field.
- Both dark and light themes are first-class and painted entirely from CSS custom properties; verify every screen in both.

## Enums

- Inherit from enum.Enum (not StrEnum)

## Import Style

- Group imports: stdlib → third-party → local. No enforced separator comments required.

## Formatting

- Follow PEP 8 line length and whitespace conventions.
- One blank line between functions within a class or module.
- Two blank lines between top-level definitions (classes, standalone functions).
- Trailing commas on the last item of multi-line argument lists and collections.

## Folder Structure
```
app/
├── app.py                     # FastAPI instance: includes /api routers + page routers, mounts /static
├── database.py
├── web/                       # shared frontend plumbing (cross-domain, not a data domain)
│   ├── templating.py          # the single Jinja2Templates instance + render() that injects the theme
│   └── labels.py              # enum→label + status badge/family/hero-word presentation maps
├── models/
│   ├── project.py
│   ├── vdi.py
│   ├── revision.py
│   └── file.py
├── project/
│   ├── router.py              # JSON API under /api
│   ├── service.py
│   ├── schema.py
│   └── web_pages.py           # HTML page routes: GET / (gallery), GET /projects/{id}
├── vdi/
│   ├── router.py
│   ├── service.py
│   ├── schema.py
│   ├── approval_type.py       # enum
│   ├── submit_code.py         # enum
│   ├── submit_status.py       # enum
│   ├── web_pages.py           # HTML page route: GET /vdi/{id}
│   └── revision/
│       ├── router.py
│       ├── service.py
│       ├── schema.py
│       └── web_pages.py       # HTML route: GET /vdi/{id}/revisions/{rid} (renders vdi/detail.html)
├── file/
│   ├── router.py
│   ├── service.py
│   ├── schema.py
│   └── dependencies.py
├── templates/
│   ├── base.html              # global shell: top bar, theme, single modal mount
│   ├── macros/                # shared, cross-domain partials (status badge, modal shell, buttons)
│   ├── project/
│   │   ├── list.html          # Home — project gallery
│   │   └── detail.html
│   └── vdi/
│       └── detail.html        # also serves the historical view (rendered with historical=True)
├── static/
│   ├── style.css              # both theme token sets + every component class
│   └── app.js                 # modal/delete-mode/theme toggle, file-preview tabs, notes save, fetch helper
uploads/
claude_brain/
```
- Store other documents such as the readme or the .env in the root.
- Page bodies live per domain (`templates/<domain>/`); the shared shell + macros live at the `templates/` root.
- There are no `new.html` pages and no `revision/detail.html`: create/edit use modals, and the historical view reuses `vdi/detail.html`.

## Agent skills

### Issue tracker

Issues live in GitHub Issues on `ribeck18/onyx_web`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repo — `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
