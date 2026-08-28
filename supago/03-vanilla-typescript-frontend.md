# Vanilla HTML/CSS/TypeScript Frontend Migration Report

**Scope:** migrate the current Jinja/FastAPI UI to server-rendered vanilla HTML/CSS plus browser-native TypeScript modules while the backend moves to Go and authentication moves to Supabase Auth. No SPA, client router, runtime framework, or JavaScript SDK is required. `plan.md` and `progress.md` were requested but are absent at the repository root (verified 2026-04-22); this report is based on the checked-in implementation.

## Findings

| Severity | Evidence | Finding / required action |
|---|---|---|
| blocker | `app/static/app.js:310-315,334-338` | A rejected `fetch` (offline, DNS, aborted connection) escapes `submit_modal_form`; the modal remains pending and closers stay disabled. The TS API client must catch network errors and always restore pending state. |
| high | `app/auth/web_pages.py:36-51`; `app/static/app.js:30-51,429-470,487-494` | Cookie-authenticated mutations have no CSRF token or Origin/Referer validation. `SameSite=Lax` is a mitigation, not a complete CSRF design. The Go BFF must enforce an Origin allowlist plus synchronizer/double-submit CSRF for all unsafe cookie-auth requests. |
| medium | `app/templates/macros/modal.html:8-29`; `app/static/app.js:96-116,622-638,744-751` | Modal markup has no `role="dialog"`, `aria-modal`, accessible label/reference, focus trap, focus restoration, or inert background. Implement these before parity sign-off. |
| medium | `app/static/app.js:487-495` | Failed notes saves return silently; users receive neither an error nor retry indication. Render a polite/alert error and leave the editor dirty. |
| medium | `app/static/style.css:1512-1517` | The sole responsive breakpoint only wraps filter controls. Wide tables, topbar, preview header/tabs, and document/action rows have no narrow-screen treatment. Define the required mobile table overflow/reflow behavior and test it. |
| low | `app/static/app.js:298-301` | Custom required-field checking bypasses native constraint validation beyond blank values (for example `type=email`). TS should call `form.reportValidity()` and retain server validation as authoritative. |
| low | `app/templates/base.html:7-10,51`; `app/app.py:50-51` | The page has external Google font CSS and no CSP/security-header configuration. A strict CSP needs either self-hosted fonts or explicit Google sources; keep all executable scripts external. |

## Current inventory

### Shell, assets, and shared presentation

| Path (lines) | Current responsibility | Migration disposition |
|---|---|---|
| `app/templates/base.html:1-53` | One themed HTML shell, nav, authenticated links, theme toggle, modal block, `/static/app.js`. | Rewrite as Go `html/template` base layout; change only the final script to module entry. Preserve SSR `data-theme`. |
| `app/templates/macros/modal.html:1-31` | Reused form modal, error/status/progress hooks. | Translate to a Go template definition/partial and add dialog semantics/focus contract. |
| `app/templates/macros/badge.html:1-18` | Status badge and document type chip. | Translate to template funcs/partials; retain human-label source of truth server-side. |
| `app/templates/macros/preview.html:1-22` | PDF/image/download preview choice. | Translate to template definition; keep server-selected safe preview kind. |
| `app/static/style.css:1-1517` | One CSS file: dark/light tokens (`:7-48`), modal/form (`:508-654`), preview (`:846-958`), list/table (`:1257-1369`), auth (`:1440-1486`), one 640px rule (`:1512-1517`). | Keep as the starting CSS; split only by concern if it remains served as concatenated plain CSS. No preprocessor. |
| `app/static/app.js:1-752` | Entire enhancement layer: theme, JSON/multipart fetch, modal lifecycle, filters, deletion, admin actions, notes, previews/version panes, delegated events. | Rewrite into typed ES modules; do not mechanically port global functions. |
| `app/web/templating.py:16-75`, `app/web/labels.py:17-174` | Jinja environment, SSR theme/current user, display labels/status families/option maps. | Replace with Go renderer/template funcs and typed presentation DTOs. Do not duplicate enum labels in browser code. |
| `app/app.py:38-51` | `/api` router mounting, page-router mounting, `/static` delivery. | Go router serves identical paths in compatibility phase; static mount serves generated JS and CSS. |

### Page inventory and SSR context

| URL / route source | Template (lines) | Server context / interactive contract |
|---|---|---|
| `GET /` — `app/project/web_pages.py:27-43` | `project/list.html:1-84` | `cards`; project modal `POST /api/projects`; card delete mode. |
| `GET /projects/{id}` — `app/project/web_pages.py:47-75` | `project/detail.html:1-219` | `project`, `vdis`, document/RFI counts, `jsa`; edit project, VDI CRUD, local VDI search/delete. |
| `GET /projects/{id}/documents` — `app/project_doc/web_pages.py:22-43` | `project_doc/list.html:1-136` | `project`, `project_docs`; filter and multipart create. |
| `GET /project-docs/{id}` — `app/project_doc/web_pages.py:46-71` | `project_doc/detail.html:1-156` | `project`, `doc`, `doc_versions`; pre-rendered version panes, current-only edit, add version/delete. |
| `GET /projects/{id}/rfis` — `app/rfi/web_pages.py:19-33` | `rfi/list.html:1-141` | `project`, `rfis`; filter, create/edit, armed deletion. |
| `GET /rfis/{id}` — `app/rfi/web_pages.py:36-60` | `rfi/detail.html:1-264` | `rfi`, `project`, `revisions`, `latest_revision`, editability; lifecycle upload/return, notes, file tabs. |
| `GET /rfis/{id}/revisions/{rid}` — `app/rfi/revision/web_pages.py:19-50` | `rfi/detail.html:1-264` | Same template with `historical=true`; no mutation controls. |
| `GET /vdi/{id}` — `app/vdi/web_pages.py:21-51` | `vdi/detail.html:1-328` | `vdi`, `project`, revisions/latest, editability; lifecycle upload/return, notes, file tabs. |
| `GET /vdi/{id}/revisions/{rid}` — `app/vdi/revision/web_pages.py:22-59` | `vdi/detail.html:1-328` | Same template with `historical=true`; no mutation controls. |
| `GET /projects/{id}/jsa` and `/revisions/{rid}` — `app/jsa/web_pages.py:14-51` | `jsa/detail.html:1-204` | `project`, `jsa`, revisions and optional historical revision; 1–3-file lifecycle/decision, notes, file tabs. |
| `GET /library` — `app/library_document/web_pages.py:13-24` | `library_document/list.html:1-113` | `library_documents`; filter and multipart create. |
| `GET /library-documents/{id}` — `app/library_document/web_pages.py:27-48` | `library_document/detail.html:1-154` | document/versions; in-place historical pane and current version-note edit. |
| `GET /login`, `/auth/login`, `/auth/callback`, `/logout` — `app/auth/web_pages.py:58-109` | `auth/login.html:1-24`, `auth/denied.html:1-19` | Login screen carries sanitized `next`; current Entra PKCE/callback/session flow. |
| `GET /tokens` — `app/auth/token_pages.py:21-30` | `auth/tokens.html:1-113` | current user's token metadata; create reveals secret once; revoke action. |
| `GET /admin/users` — `app/auth/admin_pages.py:22-41` | `auth/admin_users.html:1-126` | `rows`; provision, deactivate/reactivate, promote/demote/delete. |

The backend adds `theme` and `current_user` to every render (`app/web/templating.py:55-75`), while `base.html:25-33` uses `current_user` for nav. Preserve that global layout DTO rather than having each page independently query identity.

### DOM, event, state, and API map

| DOM contract | Event/state | Current request / result | TS module |
|---|---|---|---|
| `[data-theme-toggle]`, `<html data-theme>` | click toggles `dark`/`light`; cookie persists one year. | no API (`app.js:5-24`). | `ui/theme.ts` |
| `[data-modal-open]` → `[data-modal]`, `[data-modal-form]` | delegated click opens/configures title, method, URL, intro, JSON prefill; form state is `pending`; Esc/backdrop/close dismiss. | JSON or FormData from per-trigger `data-*`; success reload/redirect; error displayed (`:96-366,622-710`). | `ui/modal.ts`, `api/client.ts`, `features/forms.ts` |
| `[data-list-filter]` inputs/tables/rows | input lowercases `data-list-filter-text`, hides rows/table, updates polite count. | client-only (`:374-402`). | `features/list-filter.ts` |
| `[data-delete-toggle]`, project cards, `[data-delete-row]` | armed `is-deleting` state; native `confirm`; delete then reload. | `DELETE /api/projects/{id}`, or element `data-delete-url` (`:407-461`). | `features/delete.ts` |
| `[data-user-action]` | optional confirm, one-shot mutation. | admin actions, token revoke, document/JSA deletes; reload or `data-redirect` (`:466-479`). | `features/action.ts` |
| `[data-notes]` | textarea baseline in `defaultValue`; save enabled when dirty; transient saved text. | `PATCH` endpoint with `{notes}` or `{version_note}`; current failure is silent (`:483-511,735-742`). | `features/notes.ts` |
| `[data-preview-tab]` / panels | active class/`hidden`; updates displayed filename and download URL. | client-only (`:516-541`). | `features/preview-tabs.ts` |
| `[data-doc-version]` / doc panes | swaps pre-rendered panes; historical banner/viewing tag; disables edit off-current version. | client-only (`:550-601`). | `features/document-versions.ts` |
| `[data-jsa-decision]` template | select chooses approve JSON vs reject multipart URL; inserts/removes required files field. | `POST .../approve` or `.../reject` (`:713-730`). | `features/jsa-decision.ts` |
| `[data-row-href]`, `[data-vdi-row]` | bare row click navigates without stealing inner link/button behavior. | navigation only (`:682-700`). | `features/row-link.ts` |

Current UI mutation endpoints are JSON unless stated multipart: `POST/PATCH/DELETE /api/projects`; `POST/PATCH/DELETE /api/vdi`; `POST/PATCH/DELETE /api/rfis`; `POST /api/{vdi,rfi}/{id}/submit|return` (multipart); `POST/PATCH/DELETE /api/project-docs` and `POST .../versions` (multipart); `POST/DELETE/PATCH /api/projects/{id}/jsa...` (mixed); `POST/PATCH/DELETE /api/library-documents...` (mixed); `POST /api/users...`; and `POST /api/tokens`, `POST /api/tokens/{id}/revoke`. Endpoint definitions and lifecycle rules are in `app/{project,vdi,rfi,project_doc,jsa,library_document}/router.py`, `app/auth/router.py`, and `app/auth/token_router.py`.

`GET /api/files/{id}` is an authenticated binary endpoint used by preview and download links. It sends `X-Content-Type-Options: nosniff` and serves inline only for the safe allowlist (`app/file/router.py:17-52`; ADR 0006). This contract must remain exact during migration.

## Target layout and boundaries

```
web/
  templates/
    base.tmpl                    # layout and named blocks
    partials/{modal,badge,preview}.tmpl
    auth/{login,denied,users,tokens}.tmpl
    project/{list,detail}.tmpl
    vdi/detail.tmpl
    rfi/{list,detail}.tmpl
    jsa/detail.tmpl
    project_doc/{list,detail}.tmpl
    library_document/{list,detail}.tmpl
  static/
    css/style.css
    js/
      main.ts                    # only page entry; imports enhancements
      api/{client,contracts}.ts
      dom/{query,events}.ts
      ui/{theme,modal}.ts
      features/{action,delete,document-versions,forms,jsa-decision,list-filter,notes,preview-tabs,row-link}.ts
      main.js + emitted module graph (build output; not hand-edited)
internal/web/
  render.go                       # html/template parse/execute, layout DTO
  handlers/                       # page handlers and PRG fallback handlers
  middleware/{auth,csrf,headers}.go
  presentation/                   # status labels, option lists, page DTOs
```

Use one module entry and declarative `data-*` hooks. `dom/query.ts` is limited to checked `querySelector`/`closest` helpers that return typed elements or `null`; it must not become a client-side renderer. `api/contracts.ts` defines only request/response shapes used by enhancements. Server-owned values—labels, enum options, lifecycle/editability decisions, permission flags, signed/opaque URLs, and user text—remain rendered HTML/attributes, not duplicated constants in TypeScript.

Keep pages server-rendered. Go `html/template` replaces Jinja, with page handlers assembling one DTO and executing a named template. The browser only enhances an already meaningful page. Do not have page handlers self-call Go JSON endpoints; share service/use-case code as the current page routes do.

## TypeScript authoring, build, and delivery

### Recommended minimum (decision required before implementation)

Approve **one build-only dependency: `typescript`**, pinned in a lockfile and invoked with `npx tsc --project web/tsconfig.json` (or a CI-installed pinned compiler). It is needed because browsers do not execute TypeScript. Add no runtime npm dependency, bundler, framework, CSS processor, test runner, or Supabase browser SDK.

Use a no-bundle native-module build:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "bundler",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "useUnknownInCatchVariables": true,
    "verbatimModuleSyntax": true,
    "rootDir": "static/js",
    "outDir": "static/js-dist",
    "noEmitOnError": true
  },
  "include": ["static/js/**/*.ts"]
}
```

Adapt paths to the final Go repository, emit to the static directory served by Go, and make the layout load exactly:

```html
<script type="module" src="/static/js/main.js"></script>
```

In TS source, use explicit emitted `.js` specifiers (`import { request } from "./api/client.js"`), so emitted browser imports resolve unchanged. CI sequence: `tsc --noEmit` → `tsc` → Go test/build. The Go server serves the output as immutable, content-versioned release assets (or hashes filenames in a later release); it must set correct JavaScript MIME type, `nosniff`, and cache policy. With a single same-origin binary, embed the final `web/static` files using [`embed`](https://pkg.go.dev/embed) and `http.FS`; do not generate assets at runtime.

Why this is dependable: type checking is strict, the output is ordinary inspectable ES modules, source maps can be enabled only in non-production, and Go/static hosting has no Node process in production. Official TypeScript compiler option reference: <https://www.typescriptlang.org/tsconfig/>. Browser module behavior is specified by MDN: <https://developer.mozilla.org/docs/Web/JavaScript/Guide/Modules>.

### Alternatives rejected or conditional

* **Keep `app.js` as JavaScript with `// @ts-check`/JSDoc:** lowest tooling but does not meet the TypeScript direction. Use only if the TypeScript dependency decision is declined.
* **esbuild/Vite/Rollup:** add only if measured module-request count, legacy-browser requirements, asset hashing/minification, or code splitting requires it. The current 752-line script does not justify it.
* **Inline compiled JS, CDN imports, import maps, or a framework:** reject. They weaken CSP/reproducibility or add runtime surface with no corresponding UI need.
* **`supabase-js`/`@supabase/ssr`:** reject for the recommended same-origin Go BFF. They put session behavior in browser code and add a runtime dependency; use only if product explicitly requires direct browser-to-Supabase data/auth calls.

## Exact JS-to-TS conversion plan

1. Copy behavior into modules without changing data attributes or endpoint paths. Start with `dom/query.ts` and `api/client.ts`; do not modify templates until the equivalent module works.
2. `api/client.ts`: expose `requestJSON<T>`, `requestForm<T>`, and `ApiError { status, message, fieldErrors? }`. Set `credentials: "same-origin"`, `Accept: application/json`, JSON `Content-Type` only for JSON bodies, CSRF header on unsafe methods, and `signal` support. Parse the current `{detail}` error shape plus the Go RFC 9457 problem shape during transition. Catch `TypeError`/abort and return a user-safe network error.
3. `ui/theme.ts`: validate `"dark" | "light"`; set `document.documentElement.dataset.theme`; set an encode-safe `theme` cookie with `Path=/; Max-Age=31536000; SameSite=Lax; Secure` on HTTPS; update accessible button text. SSR remains authoritative on next load.
4. `ui/modal.ts`: model `idle | pending | revealed-secret`; parse only trusted server-rendered JSON prefill; preserve create-only disablement, JSA reset, multipart progress label, duplicate-field 409 placement, token secret reveal, and redirect/reload behavior. On close restore trigger focus; on open trap Tab and focus first invalid/interactive item; use a single `AbortController` only if closing is allowed (currently it is intentionally not allowed while pending).
5. `features/forms.ts`: use submit delegation, `form.reportValidity()`, then typed JSON/FormData serialization. Preserve omitted blank optional fields and `data-null-if-blank`; never stringify `File`; disable submit/closers while pending and re-enable in `finally` on failure.
6. Port independent features one at a time: filters, row links, preview tabs, document versions, delete/actions, notes, JSA decision. Each feature exports `init(root = document)` and is initialized once by `main.ts` after DOM is parsed.
7. Preserve `textContent`, `hidden`, `disabled`, `classList`, and `URL` APIs; prohibit `innerHTML` for API/server strings. Use `new URL(fileURL, location.origin)` to append `download=1` rather than string concatenation.
8. Delete `app/static/app.js` only after `main.ts` is emitted and browser parity tests pass. Keep `test_list_filter.js` conceptually, but replace its `vm` source evaluation with TypeScript unit tests against exported pure filter functions or browser tests.

## Go API and Supabase Auth contracts

### HTTP/API compatibility

Keep `/api` routes, snake_case JSON names, enum strings, integer identifiers, multipart field names, status codes, response bodies, and binary file URL shape unchanged for the first release. Existing template tests assert many of these attributes, including VDI `409` field errors, historical views, filter metadata, upload mode, and file tabs. Generate or hand-maintain Go request/response structs from this compatibility table; do not expose database structs directly.

Go API rules:

* `2xx` success; `201` creation; `204` delete; JSON errors with stable `detail` during compatibility. Add `application/problem+json` only when the TS client accepts both and a published migration date exists.
* Validate authorization and lifecycle state server-side. Browser `data-*` controls are hints, never permission boundaries.
* Keep current multipart names exactly: `file`, `files`, `return_code`, `decision`, `comments`, `version_note`; retain 1–3 JSA file validation and server-side size/type/content scanning policy.
* File download stays same-origin and authenticated. Preserve content-disposition, `X-Content-Type-Options: nosniff`, explicit safe-inline type allowlist, and non-guessable storage keys. Never proxy a Supabase Storage signed URL into an iframe if it broadens access or loses disposition controls.
* Define a redirect convention: page GET unauthenticated → `302 /login?next=<encoded local path>`; API unauthenticated/expired → `401` JSON/problem with no HTML redirect. TS treats `401/403` as session expiry: preserve safe current local path then navigate to login, not an API error modal.

### Recommended Supabase model: Go BFF, app-owned browser session

1. Configure Supabase Auth with the approved Microsoft/Azure provider and exact production/staging callback URLs. The login page link remains `/auth/login`; Go starts the authorization-code + PKCE flow and validates callback state/nonce/verifier server-side.
2. At callback, Go verifies the Supabase-issued JWT against cached JWKS: exact issuer, allowed signing algorithm/key ID, expiration/not-before, audience as configured, and immutable `sub`. Map `sub` to a local user record. Keep the local allowlist, roles, disabled state, and audit/session table: Supabase authenticates identity; Go authorizes application access and supports immediate revocation.
3. Mint a random opaque **Go session cookie** (`HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`, host-only, short idle/absolute TTL) whose server record stores user/session metadata. Encrypt any Supabase refresh token at rest only if Go needs it to refresh upstream identity; do not put access or refresh JWTs in browser storage or readable cookies. Current ownership/revocation rationale is ADR 0007.
4. Go auth middleware resolves the opaque cookie once, rejects revoked/expired/disabled sessions, and attaches a minimal principal to request context. Preserve current fail-closed default and explicit public allowlist (`app/auth/middleware.py:22-83`; ADR 0009).
5. Keep personal API tokens separate from Supabase user tokens. Store only a secure hash, scope to the local user, expiry/revocation, and accept them solely via `Authorization: Bearer` for machine API use. Browser UI never reads or sends these except displaying the newly created value once.

Do **not** use Supabase's browser client default local storage for this architecture. Direct browser Supabase access is a different security model: it requires RLS for every table/bucket, short-lived access/refresh token lifecycle in JS, CORS, and a CSRF model distinct from the BFF. Make it a separate explicit architecture decision, not a partial migration.

Supabase references: [Auth JWTs and JWKS verification](https://supabase.com/docs/guides/auth/jwts), [Auth server-side guidance](https://supabase.com/docs/guides/auth/server-side), and [Azure provider configuration](https://supabase.com/docs/guides/auth/social-login/auth-azure). Verify current provider callback/PKCE parameters against these docs at implementation time.

### CSRF, XSS, CSP, and headers

Use same-origin deployment: UI, Go pages/API, and auth callback share one schemeful site. This retains simple `credentials: "same-origin"` and avoids CORS. For every unsafe cookie-authenticated request (`POST`, `PATCH`, `PUT`, `DELETE`), Go must require both an allowed `Origin` (fallback strict Referer policy only where Origin is legitimately absent) and a CSRF token. Render a per-session token in a `<meta name="csrf-token">` and send it in `X-CSRF-Token`; accept it only when it matches a server-side session secret (or use a correctly signed double-submit cookie). Native fallback forms carry the token hidden. Do not use a token in a URL.

Use Go `html/template` autoescaping; retain `textContent` for all dynamic browser text; do not interpolate API values into HTML, selectors, URLs, or script. Treat filenames, descriptions, notes, comments, and token names as hostile. Preserve the SVG/top-level navigation protection described in ADR 0006.

Start enforceable headers in report-only mode, then enforce:

```
Content-Security-Policy: default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-src 'self';
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
X-Content-Type-Options: nosniff
```

Self-host the two current fonts or use system fonts before enforcing the CSP; otherwise narrowly allow Google style/font hosts and document the exception. Never add `'unsafe-inline'` to `script-src`; module scripts, event delegation, and external CSS already avoid it. Add HSTS at the TLS edge only after HTTPS is universal. CSP reference: <https://developer.mozilla.org/docs/Web/HTTP/CSP>; CSRF guidance: <https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html>.

## Template, CSS, behavior, and accessibility plan

### Progressive enhancement and forms

Current create/edit/action buttons have no non-JS form action (`app/templates/project/list.html:18-25`, macro `modal.html:8-29`), so mutations do not work with JavaScript disabled. Preserve readable/navigation/preview/download access immediately; to preserve mutation capability too, add Go HTML PRG endpoints as an explicit compatibility layer:

* modal has a real `<form method="post" action="/actions/...">` plus hidden `_method` for patch/delete, CSRF token, and `next`; server validates, performs use-case call, stores field errors/values in a short-lived flash, then redirects back;
* `main.ts` intercepts the same form only after initialization and calls JSON API; if TS fails to load, normal POST/redirect remains;
* file uploads use native multipart forms unchanged; client enhancement adds only pending/error affordances;
* destructive actions retain confirm dialog, but server confirmation/authorization is still final.

This costs several Go endpoints. If product accepts read-only/no-JS behavior as existing compatibility, record that decision and use button-only modals; do not claim full progressive enhancement.

Successful create/update/delete reloads the page or follows server-supplied safe same-origin redirect. Notes remain the sole in-place mutation: disable save while clean/pending; on success update baseline and announce “Saved”; on error set `role="alert"`, retain input, re-enable save, and focus the error only when the operation was explicitly submitted. Upload status is indeterminate unless an XHR upload-progress implementation is deliberately added; fetch does not reliably expose request upload progress. Avoid fake percentage.

### CSS migration

Keep one authored `web/static/css/style.css` initially. Preserve `:root`/`[data-theme]` tokens exactly (`app/static/style.css:7-48`), status family custom properties (`:657-662`), component classes, and dark/light visual snapshots. Move literal values introduced during migration into semantic tokens; do not introduce Tailwind, Sass, CSS-in-JS, or a component library.

Required CSS fixes while preserving design:

* Add visible `:focus-visible` styles for links, buttons, inputs, selects, textareas, timeline/version buttons, preview tabs, and row links; do not remove outline without replacement.
* Honor `@media (prefers-reduced-motion: reduce)` by stopping modal/progress animation and transitions (`:75-78,597-607`).
* At narrow widths, make topbar/action rows wrap, use `overflow-x:auto` with accessible table label/scroll cue (or an intentionally designed card layout), keep controls at least 44×44 CSS pixels where feasible, and prevent preview filename/tab overflow.
* Check contrast for every token pair and every `fam-*` state in both themes; check native file/select controls in Safari/Firefox/Chromium.

### Accessibility requirements

* Use semantic `<main>`, `<nav>`, headings in order, real `<button>` for actions and `<a>` for navigation; retain existing explicit labels, `aria-controls`, and filter count `aria-live` (`project/detail.html:63-75`; list templates follow the same convention).
* Modal: `role="dialog" aria-modal="true" aria-labelledby`, optional `aria-describedby`; focus first invalid control or heading, trap Tab, restore opener, close on Escape/backdrop only while idle, and keep background inert. Error summary is `role="alert"`; field errors are referenced with `aria-describedby`.
* Preview tabs use `role="tablist"`, `role="tab"`, `aria-selected`, `aria-controls`, and panels `role="tabpanel"`; version timeline buttons expose selected/current state. Do not use color alone for lifecycle state.
* Make row navigation keyboard-operable without making invalid nested interactive controls. Prefer a visible link in the leading cell (already true for VDI) over click-only `<tr>`; retain buttons/links as separate controls.
* `<iframe>` already has a title via `file_pane`; keep meaningful image alt text and ensure download fallback remains available. Validate zoom at 200%/400%, keyboard-only, screen reader announcements, reduced motion, and high contrast.

## Testing strategy

**Unit (TypeScript):** API error parsing; `FormData`/JSON blank/null policy; safe same-origin redirect; theme validation; filter matching/count; modal pending cleanup after rejected fetch; JSA endpoint/encoding switch; notes dirty/error/success states; URL download query construction. Run with Node's built-in test runner only if it can import emitted modules; otherwise test pure functions through Go/browser tests rather than add a framework.

**Go/template/API:** port existing page assertions first. The current suite covers SSR routes, historical read-only states, auth gate/redirects, lifecycle transitions, upload/download, theme SSR, and data attributes—examples: `tests/test_home_gallery.py:103-172`, `tests/test_vdi_detail_page.py:366-472`, `tests/test_project_doc_pages.py:93-485`, `tests/test_auth_gate.py:8-75`, and `tests/test_list_filter.js:1-88`. Add contract fixtures for every JSON and multipart request before swapping backend implementation.

**Browser integration (required for behavior not observable in HTTP tests):** use one approved browser runner (Playwright is the pragmatic choice, but is a separate dependency/decision). Cover keyboard modal focus/restore, Esc/pending lock, offline/rejected fetch recovery, client validation, 401 re-login, CSRF rejection, theme persistence/no flash, filters, row navigation, document/preview switching, uploads, notes errors, token reveal/redaction, and responsive dark/light screenshots. Do not add it until the TypeScript/build decision is approved; manual verification is the interim gate.

**Manual/security:** keyboard and screen-reader pass; Chromium/Firefox/Safari current versions; 320px and 200% zoom; slow/offline network; files PDF/raster/SVG/unknown types; CSP report-only console; CSRF cross-origin proof; XSS strings in every user field; session revoke/deactivate; token revoke; callback open-redirect/state/PKCE failures; authorized/unauthorized file reads.

## Rollout, compatibility, rollback

1. **Freeze contract:** capture rendered HTML/JSON/multipart fixtures and route inventory; decide TypeScript compiler, Go templates, BFF Supabase session model, progressive-enhancement scope, font/CSP policy, and browser test tool.
2. **Backend seam:** implement Go page renderer/API behind a non-production hostname using existing routes/contracts; establish Supabase callback and server session middleware. No browser TS change yet.
3. **Static parity:** move CSS unchanged, translate base/macros/pages and presentation DTOs; screenshot/HTTP-compare dark/light pages and historical states.
4. **Enhancement parity:** ship TypeScript modules behind the same declarative hooks; include CSRF; exercise browser/manual matrix. Keep page full reload mutations except notes.
5. **Canary:** route a small internal cohort by host/feature flag; record API error, CSP, auth callback, upload, and client network failure telemetry without recording tokens/content.
6. **Cutover:** switch primary host only after acceptance checklist; retain FastAPI deployment and database/file backup read-only for a defined window.
7. **Rollback:** DNS/reverse-proxy/feature flag returns users to the unchanged FastAPI origin; do not run irreversible schema/auth identity transformations until Go session and Supabase subject mapping are proven. Existing opaque sessions will not be portable unless deliberately shared—force re-login on rollback/cutover and communicate it.

## Keep, rewrite, remove

| Keep (behavior/contract) | Rewrite | Remove only after parity |
|---|---|---|
| URLs, API shapes/statuses, lifecycle guards, server-side labels, file inline allowlist, historical read-only pages, SSR theme cookie, login redirect safety, app-owned authorization/PAT semantics. | Jinja templates → Go templates; `app/web/templating.py`/`labels.py` → Go renderer/presentation; `app/static/app.js` → TS modules; FastAPI page/API/auth middleware → Go handlers/middleware; Entra callback → Supabase-backed Go BFF callback. | `app/static/app.js`; Jinja macro/template infrastructure; Python page router layer; FastAPI static mount. Do not remove CSS until visual parity passes. |

## No-framework guardrails

* Server renders all pages; no hydration, virtual DOM, client router, global store, JSON-to-HTML renderer, or component framework.
* One external module entry; features initialize against declarative hooks and export small functions. No inline handlers/scripts.
* TypeScript compiler is build-only. No package is added without user approval; no runtime npm packages absent an accepted decision record.
* JSON API remains the mutation/data contract; use cases are shared directly by page and API handlers, never page-to-self HTTP.
* Browser state is local and ephemeral (open dialog, pending action, selected preview/version, filter term, notes dirty state). Authoritative data, permissions, and lifecycle states stay server-side.
* Build output is reproducible in CI; generated JS is not hand-edited. Do not add a bundler unless the stated trigger in this report occurs.

## Decision gates

1. Approve the build-only `typescript` compiler and lockfile, or explicitly waive TypeScript in favor of checked JS/JSDoc.
2. Approve Go server-rendered templates plus native ES modules, rather than an SPA/direct Supabase browser architecture.
3. Confirm Supabase Azure/Entra provider, callback domains, user-subject migration/allowlist mapping, local role/session retention, and forced re-login cutover.
4. Decide whether mutation-capable no-JS PRG fallbacks are mandatory. If yes, budget corresponding Go action endpoints/flash handling.
5. Approve CSRF token design, same-origin host topology, CSP/font approach, and HTTP security headers before Go API reaches production.
6. Approve one browser test tool before declaring interactive/accessibility parity.

## Completion checklist

- [ ] Every inventory URL renders from Go with identical access control, status, labels, and dark/light SSR theme.
- [ ] Every current JSON/multipart/file API contract fixture passes against Go; lifecycle/authorization decisions remain server-enforced.
- [ ] Strict TypeScript compiles with no emitted-on-error artifacts; no runtime frontend dependency/framework exists.
- [ ] Network failures always clear pending UI and show an actionable error; notes errors are visible and non-destructive.
- [ ] Unsafe cookie requests require validated Origin and CSRF token; no Supabase access/refresh token is readable by browser JS.
- [ ] CSP is enforced without inline-script exceptions; XSS/file-serving probes pass.
- [ ] Modal/dialog, focus, keyboard, live-region, tab, responsive, reduced-motion, and both-theme checks pass.
- [ ] Uploads, downloads, login/logout/session expiry/revocation, PAT reveal/revoke, historical views, filters, delete mode, and redirects pass browser/manual tests.
- [ ] FastAPI rollback environment, migration backup, cutover/forced-login notice, and rollback owner/window are documented.
