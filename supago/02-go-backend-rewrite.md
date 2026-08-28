# Go Backend Rewrite Report

**Scope:** FastAPI/Python -> Go + Supabase Database/Auth/Storage; retain server-rendered vanilla HTML/CSS and migrate `app.js` to compiled vanilla TypeScript. Inspection date: 2026-07-23. `plan.md` and `progress.md` were requested but do not exist at the repository root (`ENOENT`); this report is derived from the checked-in application, ADRs, tests, requirements, and runtime inspection.

## 1. Current system / compatibility baseline

- Startup is `main.py:1-4` -> `app/app.py:32-79`: FastAPI, signed Starlette OIDC handshake session, fail-closed auth middleware, `/api` routers, root page routers, static mount. `/healthz` is public (`app/app.py:47-50`).
- Configuration is import-time dotenv loading (`config.py:1-72`): `DATABASE_URL`, filesystem `FILE_STORAGE_ROOT`, SQL echo, Entra OIDC settings, cookie flags, break-glass emails, public base URL. The current async SQLAlchemy engine/session seam is `app/database.py:8-24`; local schema creation is `create_tables.py:10-22`, not migrations.
- Data store is SQLite locally / Postgres in production per `README.md:32-57`. All mutations flush in a service and commit in a route except auth middleware state touches (`app/auth/service.py:193-208,306-307`). No background jobs, queues, e-mail, webhooks, task scheduler, or outbound business side effects were found.
- Every non-public request is protected centrally. Unauthenticated `/api`/Bearer -> `401 {"detail":"Not authenticated"}`; other pages -> `302 /login?next=...` (`app/auth/middleware.py:28-100`). Every authenticated user can access all business data; admin only gates account management (ADR 0007, `docs/adr/0007-en...md:33-36`).
- Browser auth is Entra Authorization Code + PKCE, then an app-owned opaque `onyx_session` cookie (8h idle/7d absolute); bearer access is a hashed, 90-day opaque PAT (`app/auth/service.py:23-50,152-210,224-307`). Users are pre-provisioned and bind an Entra OID on first login; break-glass e-mails are configured by environment (`app/auth/service.py:108-149`).
- UI is 16 Jinja pages/macros, one CSS file and one 752-line JavaScript file. Pages call services directly; mutations call `/api`; only notes patch in place (`app/web/templating.py:25-75`, `app/static/app.js:25-80,292-369,482-511`). Theme cookie is presentation-only.
- Uploads read the complete part into memory, then write `<uuid><client extension>` under `FILE_STORAGE_ROOT`; a `files` row records declared MIME type and original name (`app/file/service.py:21-52`). `GET /api/files/{id}` authenticates and sends `inline` only for PDF/raster allowlist; all else/`?download=1` is attachment plus `X-Content-Type-Options: nosniff` (`app/file/router.py:17-52`, `app/web/file_preview.py:15-48`).

### Inventory: tables, types, constraints, and service ownership

All time values are timezone-aware UTC in intent; IDs are signed integer PKs today. Enums are lowercase string values, not native enums (ADR 0001).

| Current table / source | Go/Supabase target | Required database rules / owner |
|---|---|---|
| `projects` (`app/models/project.py:18-57`) | `projects` + `Project`/`ProjectCreate`/`ProjectPatch` | `bigint generated ... identity` compatibility ID, unique `project_number`; cascade domain children. `project` package owns CRUD. |
| `vendor_data_items` (`app/models/vdi.py:19-89`) | `vendor_data_items` + `VDI`, `ApprovalType`, `SubmitCode`, `SubmitStatus` | FK project; unique `(project_id,item_number)`; VDI lifecycle owns status. `vdi` package. |
| `revisions` (`app/models/revision.py:17-95`) | `vdi_revisions` **or retain `revisions` during compatibility** + `VDIRevision` | FK VDI, unique `(vendor_data_item_id,revision_number)`, one required submit file/optional return file. No generic write route. |
| `rfis`, `rfi_revisions` (`app/models/rfi.py:25-72`, `rfi_revision.py:17-84`) | same + `RFI`, `RFIRevision`, `RFIStatus` | FK/cascade; unique `(project_id,rfi_number)` and `(rfi_id,revision_number)`. `rfi` owns lifecycle. |
| `project_docs`, `doc_versions` (`app/models/project_doc.py:17-74`, `doc_version.py:16-60`) | same + `ProjectDocument`, `DocumentVersion`, `DocumentType` | FK/cascade; unique `(project_doc_id,version_number)`; document creation includes v1; do not generalize with approval revisions. |
| `library_documents`, `library_document_versions` (`app/models/library_document.py:15-46`, `library_document_version.py:16-48`) | same + `LibraryDocument`, `LibraryDocumentVersion` | FK/cascade; unique `(library_document_id,version_number)`; title intentionally non-unique. |
| `jsas`, `jsa_revisions`, `jsa_files` (`app/models/jsa.py:17-55`, `jsa_revision.py:17-50`, `jsa_file.py:21-50`) | same + `JSA`, `JSARevision`, `JSAFile`, `JSAFileGroup`, `JSAStatus` | singleton unique `jsas.project_id`; revision unique `(jsa_id,revision_number)`; link unique `(jsa_revision_id,file_group,position)`; package cardinality 1..3 validated in service. |
| `files` (`app/models/file.py:11-30`) | `files` + `StoredFile` | Add `bucket text`, `object_key text unique` instead of local `stored_path`; retain original name, MIME, created time. Domain FKs remain on version/revision/link rows. |
| `users`, `sessions`, `api_tokens` (`app/models/user.py:16-57`, `session.py:15-46`, `api_token.py:15-52`) | `onyx_users`, `api_tokens`; Supabase `auth.users` is identity/session authority | `onyx_users.id bigint` can preserve API IDs; nullable unique `auth_user_id uuid references auth.users`; case-insensitive email unique index; admin/active flags. Do not migrate app `sessions`; retain hashed PAT table with FK `onyx_user_id`. |

Use `text CHECK (...)` for every present enum rather than Postgres enum, preserving ADR 0001 and allowing values to evolve without `ALTER TYPE`. Emit Go typed string constants:

```go
type SubmitStatus string
const (
    SubmitNotStarted SubmitStatus = "not_started"
    SubmitSubmitted  SubmitStatus = "submitted"
    SubmitA SubmitStatus = "a"; SubmitB SubmitStatus = "b"
    SubmitC SubmitStatus = "c"; SubmitD SubmitStatus = "d"
)
```

Map remaining values exactly: `ApprovalType={mandatory_approval,information_only}` (`app/vdi/approval_type.py:4-8`); `SubmitCode={ac,afi,aro,at,bc,bfa,bfs,pds,ps,pt,ptc,pti,ptp,ptw,ros,ts}` (`submit_code.py:4-22`); `RFIStatus={not_started,submitted,approved,rejected}` (`app/rfi/status.py:4-10`); `JSAStatus={submitted,approved,rejected}` (`app/jsa/status.py:4-8`); `JSAFileGroup={submitted,returned}` (`app/models/jsa_file.py:16-19`); `DocumentType={drawing,specification,special_condition,contract,vendor_data_schedule,addendum}` (`app/project_doc/document_type.py:4-10`). Define request/response structs separately from database row structs; JSON field names remain snake_case and time encoding remains RFC3339.

## 2. Endpoint and page contract matrix

All API paths below have the `/api` prefix. `Auth=U` means any valid current user/PAT, `A` admin, `P` public. All successful JSON GET/PATCH/action responses are `200` unless shown; unknown resource normally is `404 {detail}`; framework binding/JSON validation is currently `422 {detail:[...]}`. Preserve these status/body shapes until a deliberately versioned contract replaces them.

| Method/path | Auth | Input -> output | Side effects / special errors | Source |
|---|---|---|---|---|
| GET `/healthz` | P | -> `{"status":"ok"}` | liveness only | `app/app.py:47-50` |
| GET `/api/projects` | U | -> `[]ProjectRead`, number asc | none | `project/router.py:24-30` |
| POST `/api/projects` | U | JSON `project_number,name,description?` -> `201 ProjectRead` | unique number DB conflict currently unnormalized; creates project | `project/router.py:13-21` |
| GET/PATCH/DELETE `/api/projects/{id}` | U | ->/JSON partial -> `ProjectRead`/`204` | PATCH updates timestamp; DELETE cascades DB children | `project/router.py:33-76` |
| GET/POST `/api/vdi?project_id=` | U | -> `[]VdiRead` item asc / JSON `VdiCreate` -> `201 VdiRead` | POST needs project, rejects duplicate item number `409` | `vdi/router.py:24-57` |
| GET/PATCH/DELETE `/api/vdi/{id}` | U | ->/JSON `VdiUpdate` -> `VdiRead`/`204` | PATCH never accepts status; post-submit `item_number,approval_type,submit_code` actual changes -> `409`; sibling collision -> `409` | `vdi/router.py:60-122,195-207` |
| POST `/api/vdi/{id}/submit` | U | multipart required `file` -> `VdiRead` | only `not_started,b,c`; saves file, appends revision numbered 0+, sets submitted; invalid state `409`, empty `400` | `vdi/router.py:125-150`, `vdi/service.py:18-27,100-117` |
| POST `/api/vdi/{id}/return` | U | multipart `return_code` A/B/C/D, required `file`, `comments?` -> `VdiRead` | only submitted; writes latest revision return and VDI status; bad code `422`, state `409`, empty `400` | `vdi/router.py:153-192` |
| GET `/api/vdi/{id}/revisions` | U | -> `[]RevisionRead`, oldest first | parent required | `vdi/revision/router.py:14-26` |
| GET `/api/vdi/{id}/revisions/latest` | U | -> `RevisionRead` | missing -> `404` | `vdi/revision/router.py:31-39` |
| GET `/api/vdi/{id}/revisions/{rid}` | U | -> `RevisionRead` | scoped parent -> `404` | `vdi/revision/router.py:42-54` |
| GET/POST `/api/rfis?project_id=` | U | -> `[]RfiRead` rfi-number asc / JSON `RfiCreate` -> `201 RfiRead` | required trimmed nonblank number/title; project-scoped duplicate `409` | `rfi/router.py:20-56`, `rfi/schema.py:10-46` |
| GET/PATCH/DELETE `/api/rfis/{id}` | U | ->/JSON `RfiUpdate` -> `RfiRead`/`204` | number locks after submit; duplicate `409`; metadata including notes otherwise editable | `rfi/router.py:59-116,184-197` |
| POST `/api/rfis/{id}/submit` | U | multipart required `file` -> `RfiRead` | locks row; from `not_started,approved,rejected`; creates revision 0+, sets submitted | `rfi/router.py:119-145`, `rfi/service.py:19-22` |
| POST `/api/rfis/{id}/return` | U | multipart `decision=approved|rejected`, optional `file,comments` -> `RfiRead` | only submitted; optional return file; invalid decision `422` | `rfi/router.py:148-181` |
| GET `/api/rfis/{id}/revisions` | U | -> `[]RfiRevisionRead`, oldest first | parent required | `rfi/revision/router.py:14-26` |
| GET `/api/rfis/{id}/revisions/latest` | U | -> `RfiRevisionRead` | missing -> `404` | `rfi/revision/router.py:29-41` |
| GET `/api/rfis/{id}/revisions/{rid}` | U | -> `RfiRevisionRead` | parent-scoped -> `404` | `rfi/revision/router.py:44-57` |
| POST `/api/project-docs` | U | multipart `project_id,label,type,file,doc_number?,description?` -> `201 ProjectDocRead` | validates parent before storage; atomic doc + v1; empty file `400` | `project_doc/router.py:24-56` |
| GET `/api/project-docs?project_id=` | U | -> `[]ProjectDocRead`, label asc | query required `422` | `project_doc/router.py:119-126` |
| GET/PATCH/DELETE `/api/project-docs/{id}` | U | ->/JSON `ProjectDocUpdate` -> `ProjectDocRead`/`204` | no lifecycle field lock; delete DB versions but current implementation leaves files | `project_doc/router.py:129-172` |
| POST `/api/project-docs/{id}/versions` | U | multipart `file,description?` -> `201 DocVersionRead` | next 1-based version, bumps parent; missing/empty file `422`/`400` | `project_doc/router.py:59-86` |
| GET `/api/project-docs/{id}/versions` | U | -> `[]DocVersionRead`, oldest first | parent required | `project_doc/router.py:89-101` |
| GET/PATCH/DELETE `/api/project-docs/{id}/versions/{vid}` | U | ->/JSON `{description?}` -> `DocVersionRead`/`204` | scoped; only description mutable; deleting sole v1 -> `409` | `project_doc/router.py:104-116,175-223` |
| GET `/api/files/{id}?download=0|1` | U | -> bytes, original MIME/name | inline only PDF/png/jpeg/gif/webp/bmp; otherwise/flag attachment, `nosniff`; missing metadata/bytes `404` | `file/router.py:17-52` |
| GET/POST `/api/projects/{pid}/jsa` | U | -> `JsaRead` / multipart `files` (1..3) -> `201 JsaRead` | one JSA per project; first submitted revision 0; duplicate `409`, invalid/empty package `400` | `jsa/router.py:35-70` |
| POST `/api/projects/{pid}/jsa/submit` | U | multipart `files` 1..3 -> `JsaRead` | only approved/rejected -> next submitted revision | `jsa/router.py:73-96` |
| GET `/api/projects/{pid}/jsa/revisions` | U | -> `[]JsaRevisionRead` oldest first | JSA required | `jsa/router.py:99-109` |
| GET/DELETE `/api/projects/{pid}/jsa/revisions/{rid}` | U | -> `JsaRevisionRead` / -> `204` | delete newest only; restores previous status or removes sole JSA | `jsa/router.py:112-125,175-191`, `jsa/service.py:127-141` |
| POST `/api/projects/{pid}/jsa/approve` | U | JSON optional `{comments}` -> `JsaRead` | only submitted; decision time/status | `jsa/router.py:128-145` |
| POST `/api/projects/{pid}/jsa/reject` | U | multipart `files` 1..3, `comments?` -> `JsaRead` | only submitted; adds returned ordered links | `jsa/router.py:148-172` |
| DELETE `/api/projects/{pid}/jsa` | U | -> `204` | DB history/link cascade; current files remain | `jsa/router.py:194-204` |
| PATCH `/api/projects/{pid}/jsa/notes` | U | JSON `{notes:null|string}` -> `JsaRead` | in-place UI mutation; any JSA state | `jsa/router.py:207-219` |
| GET/POST `/api/library-documents` | U | -> `[]LibraryDocumentRead` title asc / multipart `title,file,description?,version_note?` -> `201 LibraryDocumentRead` | title trim/nonblank `422`; title non-unique; v1 required | `library_document/router.py:31-60,247-271` |
| GET/PATCH/DELETE `/api/library-documents/{id}` | U | ->/JSON `{title?,description?}` -> `LibraryDocumentRead`/`204` | title nonblank; delete removes metadata then local bytes after commit | `library_document/router.py:96-129,176-200` |
| POST `/api/library-documents/{id}/versions` | U | multipart `file,version_note?` -> `201 LibraryDocumentVersionRead` | parent row lock, next version, bump parent | `library_document/router.py:63-93` |
| GET `/api/library-documents/{id}/versions` | U | -> `[]LibraryDocumentVersionRead` oldest first | parent required | `library_document/router.py:202-221` |
| GET/PATCH `/api/library-documents/{id}/versions/{vid}` | U | ->/JSON required `version_note:null|string` -> version | only current version note editable; historic -> `409` | `library_document/router.py:132-173,224-244` |
| GET/POST `/api/tokens` | U | -> `[]ApiTokenRead` newest / JSON `{name}` -> `201 ApiTokenCreated` | POST trims nonblank `422`, emits raw `secret` exactly once | `auth/token_router.py:21-56` |
| POST `/api/tokens/{id}/revoke` | U | -> `ApiTokenRead` | owner-only; idempotent revocation, unknown `404` | `auth/token_router.py:59-73` |
| GET/POST `/api/users` | A | -> `[]UserRead` newest / JSON `{email,display_name?,is_admin?}` -> `201 UserRead` | provision allowlist identity; empty `422`, case-insensitive duplicate `409` | `auth/router.py:32-63` |
| POST `/api/users/{id}/deactivate|reactivate|promote|demote` | A | -> `UserRead` | deactivate removes app sessions; self deactivate/demote and break-glass demote `409` | `auth/router.py:66-128` |
| DELETE `/api/users/{id}` | A | -> `204` | only never-logged-in user; otherwise `409` | `auth/router.py:131-148` |

### Root HTML/auth routes

All page routes render named templates; failures are JSON `404` except account-denied template `403`. Preserve content, DOM `data-*` contracts, root paths, and middleware redirect behavior during cutover.

| Path/method | Auth | Template/behavior | Source |
|---|---|---|---|
| GET `/` | U | project gallery with VDI-only open count | `project/web_pages.py:24-42` |
| GET `/projects/{id}` | U | project detail, VDI table, doc/RFI/JSA counts | `project/web_pages.py:45-75` |
| GET `/projects/{id}/documents`, `/project-docs/{id}` | U | project-document list/detail | `project_doc/web_pages.py:20-71` |
| GET `/projects/{id}/rfis`, `/rfis/{id}`, `/rfis/{id}/revisions/{rid}` | U | RFI list/live/history detail | `rfi/web_pages.py:18-60`, `rfi/revision/web_pages.py:17-50` |
| GET `/vdi/{id}`, `/vdi/{id}/revisions/{rid}` | U | VDI live/history detail; history uses same template read-only | `vdi/web_pages.py:22-50`, `vdi/revision/web_pages.py:22-59` |
| GET `/projects/{id}/jsa`, `/projects/{id}/jsa/revisions/{rid}` | U | JSA empty/live/history detail | `jsa/web_pages.py:14-60` |
| GET `/library`, `/library-documents/{id}` | U | library list/detail with client-side historical pane switching | `library_document/web_pages.py:13-48` |
| GET `/tokens`, `/admin/users` | U / U then admin page 403 | token/user management page | `auth/token_pages.py:21-30`, `auth/admin_pages.py:22-41` |
| GET `/login`, GET `/auth/login`, GET `/auth/callback`, GET/POST `/logout` | P | login page; Entra redirect/callback; local logout -> `302 /login` | `auth/web_pages.py:54-109` |
| `/static/*` | P | `style.css`, `app.js` | `app/app.py:78-79`, auth allowlist `middleware.py:28-37` |

## 3. Target architecture

### Recommendation: `net/http` + `chi`, not an application framework

Use Go 1.24+ (pin exact supported Go release at implementation) and `net/http` as the HTTP substrate; add **`github.com/go-chi/chi/v5` only** for nested route mounting, path params, and middleware composition. It is a thin standard-library router, not a second application architecture. `net/http` alone is feasible but would require handwritten parameter dispatch and makes the present nested endpoint set less readable. Do **not** use Gin/Fiber/Echo: their binding/error conventions would require adapter code to preserve the existing response contract and provide no needed capability.

Use `pgx/v5`/`pgxpool` rather than an ORM or an unreviewed Supabase Go SDK. Supabase Database is Postgres; direct typed SQL gives transactions, row locks, retryable unique conflicts, and predictable lifecycle queries. Use Supabase REST only for Auth/Storage HTTP APIs. This avoids an ORM/repository framework while retaining interface seams at real external boundaries.

```text
supago/
  go.mod                         # Go module, tool versions documented
  cmd/onyx/main.go               # config, clients, pool, Router, graceful shutdown
  internal/
    config/config.go             # getenv/parse/validate once; no globals
    http/
      router.go                  # public allowlist, static, /api mounts
      middleware.go              # request ID, recover, access log, auth, CSRF gate
      errors.go                  # APIError -> existing {detail} contract
      render.go                  # template renderer + theme/current-user view context
      auth_handlers.go           # login/callback/logout/token/user routes
      files_handlers.go          # stream upload/download
    auth/
      principal.go               # Supabase JWT/PAT -> Principal
      jwt.go                     # issuer/audience/JWKS validation and key cache
      cookie.go                  # encrypted/HttpOnly auth token transport
      service.go                 # allowlist bind, profile/admin/PAT operations
    project/ handler.go service.go repository.go types.go
    vdi/     handler.go service.go repository.go types.go
    rfi/     handler.go service.go repository.go types.go
    documents/                     # project_document + library_document, separate services
    jsa/     handler.go service.go repository.go types.go
    files/   service.go repository.go storage.go types.go
    platform/
      postgres.go                 # pgx transaction, RLS claim context
      supabase_auth.go            # narrow Auth HTTP client
      supabase_storage.go         # narrow Storage HTTP client
      observability.go
  web/
    templates/                    # migrated Jinja templates
    static/style.css
    src/app.ts                    # current app.js, type-checked
    dist/app.js                   # generated deployment artifact (or build into embed)
  migrations/                     # ordered Supabase SQL only
  tests/                          # Go unit/integration/contract tests
```

Dependency direction is `cmd -> http -> domain service -> {repository, auth/storage ports} -> platform`; `http/render` may consume domain read DTOs, never repositories; domain packages do not import `http`, templates, Supabase SDKs, or sibling services. `documents` must not invent a common lifecycle/version abstraction: project documents and library documents share storage only, as ADR 0011 requires. Use a one-method interface only at `FileStore`, `AuthClient`, `JWTVerifier`, clock, and repository boundaries that tests replace; concrete `pgx` repos elsewhere are enough.

### Seams and transaction model

- **Handler:** decode strictly (`DisallowUnknownFields` for JSON only after compatibility assessment), enforce content type/body limit, construct response DTO, map typed errors. No business transition in handlers.
- **Service:** owns VDI/RFI/JSA state machine, immutable-field rules, 1..3 package validation, and transaction boundary. `Submit`/`Return`/version creation each executes one serializable/retryable `pgx.Tx`, locks parent `FOR UPDATE`, allocates next sequence, writes metadata, then commits. Database unique constraints are the final conflict authority; map `23505` to the current specific `409` text.
- **Repository:** SQL statements and scans only. Query shapes should directly produce read DTOs/current version using joins/window query rather than N+1. Keep `FOR UPDATE` methods private to the domain repository.
- **RLS context:** each request transaction calls `SELECT set_config('request.jwt.claim.sub',$1,true)` and `SET LOCAL ROLE authenticated` before domain SQL. PAT auth supplies the mapped profile UUID after database lookup. The runtime DB role must be `NOBYPASSRLS`; service role is never a general repository credential.
- **Storage:** `FileStore.Put(ctx,key,reader,contentType)`, `Open`, `Delete`. The handler streams `multipart.Part` through a bounded reader; service records metadata only after storage accepts bytes. On transaction failure, enqueue/synchronously attempt compensating object delete and emit an orphan metric. Never make Storage public.

## 4. Supabase Auth, JWT, RLS, and service-role design

### Required decision gates (do not silently choose)

1. **Identity provider / continuity — owner decision.** Current product contract is Entra single-tenant, pre-provisioned allowlist, break-glass admins, and instant disable. Recommended default: keep Microsoft Entra as the enterprise IdP through Supabase Auth's Azure/SSO configuration, do not enable password/email signup, and retain a public `onyx_users` allowlist table. Confirm tenant/issuer, callback URL, and whether break-glass remains environment-controlled or becomes a two-admin DB procedure.
2. **Browser token transport — security-owner decision.** Recommended default: Go performs PKCE callback/exchange with Supabase Auth and puts the short-lived access token plus refresh token only in Secure, HttpOnly, `SameSite=Lax`, path-scoped encrypted cookies; it refreshes server-side and never exposes tokens to TypeScript. This preserves same-origin server pages and avoids XSS-accessible bearer tokens. Add origin-checked CSRF protection for cookie-authenticated mutations. Do not issue a Go-signed substitute JWT.
3. **Data visibility — product/security decision.** Current behavior is every active user can read/write all business data. Recommended default: encode exactly that in RLS through active profile membership, with `is_admin` only for account-management tables/actions. Project membership/tenant partitioning is a product change and must not be inferred.
4. **PAT retention — product/security decision.** Current API/MCP compatibility needs opaque personal tokens. Recommended default: retain `api_tokens` and current 90-day/one-time-secret/revoke semantics; resolve it in Go, map to the owning active profile, then apply the RLS request UUID. Do not substitute Supabase user JWTs for PATs without updating the MCP consumer.
5. **Admin Auth API / revocation — security-owner decision.** Recommended default: use Supabase service-role key only in the Go process for the narrow Auth admin calls needed by confirmed lifecycle operations; never send it to browser, logs, templates, or database. Setting `onyx_users.active=false` must be the immediate authorization kill switch because every Go request and RLS checks it. Confirm whether to additionally globally sign a user out through the Auth Admin API; do not claim access-token revocation is instantaneous.

### Concrete auth data and policies

1. Create `public.onyx_users` with stable existing bigint `id`, `auth_user_id uuid unique null references auth.users(id)`, normalized `email`, `display_name`, `is_admin`, `is_active`, timestamps, unique `lower(email)`. Import current provisioned users as unbound records. Preserve `last_login_at`; expose `has_logged_in` from it.
2. Callback obtains validated Supabase subject/email. Call a SECURITY INVOKER/definer, transaction-safe `bind_onyx_identity(subject uuid, email text, display_name text)` function that: resolves same subject; otherwise binds only an unbound case-insensitive matching row; rejects a different bound subject; applies approved break-glass rule; updates display/last-login; returns active profile. This is the exact current anti-email-reassignment behavior (`app/auth/service.py:79-149`). It must not auto-create ordinary users.
3. JWT verifier accepts only the configured Supabase issuer, audience, expiry/not-before, and signing key selected from cached JWKS. Use cache-control/rotation-aware refresh on unknown `kid`; no “decode without verify.” Parse `sub` UUID, then query profile active/admin state before serving. Cookie refresh failures clear both cookies and follow current 401/302 split.
4. Enable RLS on every `public` table including `files`; force RLS on application tables. Policies use `exists (select 1 from onyx_users u where u.auth_user_id=auth.uid() and u.is_active)`. For `onyx_users` and PAT metadata, scope `auth_user_id=auth.uid()`; admin management policy additionally calls `is_onyx_admin()`. `auth.uid()` must return null/deny where no transaction claim is set. Storage uses private bucket and `storage.objects` policies by the same active principal, but Go proxy should be the only delivery path initially.
5. Migration role check: create/use an application DB role that has table privileges but `NOBYPASSRLS`; fail startup if connection role is `postgres`, `service_role`, or has `rolbypassrls`. This is essential because Supabase service-role credentials bypass RLS. Run schema migrations through the deployment/migration credential only.
6. Existing app sessions cannot be transformed into Supabase sessions. At cutover invalidate the `onyx_session` cookies and require login; PAT hashes can migrate unchanged. Explicitly communicate this forced browser re-login.

## 5. Templates, static delivery, uploads, validation, errors, config, logging

### Templates and TypeScript

- Use `html/template` (context-aware escaping) with parsed named templates. Port `base.html`, domain templates, and macros to `{{define}}` partials; do not implement a general Jinja compatibility layer. Preserve routes, HTML, `data-*`, interpolation escaping, names, and page inputs first. Current shared render responsibilities are theme validation/current user injection (`app/web/templating.py:47-75`) and label/preview helpers (`labels.py:19-156`, `file_preview.py:11-51`); reimplement them in `internal/http/render.go` as typed view helpers.
- Retain CSS byte-for-byte initially: `app/static/style.css` is the two-theme token source. Port labels from `labels.py` into Go helper functions so templates never render raw enum values. Keep current preview and `nosniff` policy exactly.
- Convert only `app/static/app.js` to `web/src/app.ts`; preserve external DOM behavior and `fetch` semantics. Use `esbuild` to type-check/bundle one `web/dist/app.js` at build/CI time; serve immutable cacheable hashed asset or embed it in the binary. This is the one required build-step reversal of ADR 0005 to meet the stated TypeScript end state—no frontend framework, runtime package, or component system. Decision gate: approve generated artifact policy (commit `dist` for simple deploy or build in CI image; recommended: CI builds, Go embeds).
- Serve static files with `http.FileServer`/`embed.FS`; retain `/static` public and no SPA fallback. Preserve external Google font dependency unless the deployment owner elects to self-host it.

### Files

- Private bucket `onyx-files`; deterministic key `<uuid><sanitized allowed extension>` or `<uuid>` (preferred, extension only presentation) and database `object_key`. Retain `original_name` for `Content-Disposition` (RFC 5987-safe encoding) and MIME metadata. Do not trust path/name from client.
- `GET /api/files/{id}` must authorise metadata lookup before opening object, stream with `io.Copy`, preserve `Content-Type`, `Content-Disposition`, and `X-Content-Type-Options: nosniff`; allow inline only the current exact allowlist. Do not return public/signed Storage URLs in the compatibility phase.
- Stream upload without `ReadAll`; enforce `http.MaxBytesReader`, reject empty body, store to Storage, then transactionally create file/domain metadata. **Decision gate:** current system has no file-size/type policy. Recommended default is a documented 50 MiB request cap and MIME sniff/mismatch rejection; security/product owner must approve because that changes previously unbounded acceptance.
- On any parent delete, delete database references/files and private objects intentionally. Run a reconciliation job/report comparing `files.object_key` and bucket objects; do not depend on DB FK cascade to delete objects. This corrects the current intentional orphan behavior (ADR 0003) without making storage a background subsystem.

### Validation/errors/logging/config

- Keep client-visible `{"detail":"text"}` for known errors; malformed JSON/form/path/query uses `422 {"detail":[...]}` during compatibility, 404 uses current messages, conflict messages match the matrix, and empty uploads remain `400 {"detail":"Uploaded file is empty."}`. Implement `APIError{Status,Detail}` and a one-place renderer; default errors are logged request-ID correlated and returned as `500 {"detail":"Internal server error"}`.
- Validate required text as current RFI validators do (`app/rfi/schema.py:10-46`); trim only where current behavior trims (RFI/title/PAT/user/library title), preserve nullable-vs-absent PATCH semantics using pointer fields. JSON numbers/enums must reject invalid values before service transition.
- `config.Load()` must fail at startup for `SUPABASE_URL`, database DSN/runtime role, JWT issuer/audience, Auth callback URL, cookie encryption/signing secret, service-role key (only if approved admin Auth calls are enabled), Storage bucket, deployment environment, and log level. Use `os.LookupEnv`, `url.Parse`, `time.ParseDuration`; redact all secret values. Never preserve the production-capable default `dev-insecure-session-secret-change-me` (`config.py:56-59`).
- Structured `slog` JSON: request ID, method, route, status, duration, actor profile ID, auth method, domain object IDs, Storage operation/key hash, Postgres SQLSTATE; never raw JWT/PAT/cookie, e-mail unless explicitly approved, multipart bytes, DB DSN, or service key. Add OpenTelemetry only if deployment already has a collector; otherwise standard logs plus `/healthz` and a protected `/readyz` that pings pool/Storage only if required.

## 6. Database migration and implementation order

1. **Freeze contract.** Generate route manifest/OpenAPI/HTML snapshots from Python; record representative API fixtures and all transition/error tests. Capture SQLite/Postgres row counts, PK ranges, unique/FK violations, object checksums, users/PAT hash counts. Add a maintenance-write freeze only for final transfer.
2. **Provision Supabase.** Create project, private Storage bucket, runtime/migration roles, SQL migration baseline, RLS/policies/functions, Auth provider configuration, secrets, database backups, and least-privileged CI deploy identity. Validate in a non-production Supabase project first.
3. **Build platform/auth first.** Go server serves `/healthz`, static, templates, public login/callback/logout, JWT/PAT principal resolution, CSRF, error envelope, request logs. Test invalid JWT, expired JWT, key rotation, inactive/admin/non-admin, open redirect, cookie flags, and RLS denial before mounting business routes.
4. **Migrate storage/data.** Stop writes; export tables in parent-before-child order while retaining bigint IDs and timestamps; upload each local object to private Storage under recorded key; load metadata/FKs; reconcile counts, FK/unique checks, per-object SHA-256, sample download headers, and enum distribution. Import users as allowlist rows; import PAT hashes/expiry/revocation/last-used. Do not import app sessions. Take a final delta only while writes are frozen.
5. **Implement vertical slices.** Projects/files -> VDI/revisions -> RFI/revisions -> project documents -> library -> JSA -> users/PAT. For every lifecycle write use a parent lock/advisory lock and unique-conflict retry; do not retain `max()+1` without serialization. Keep API and root URLs unchanged.
6. **Compatibility verification.** Run the equivalence suite against Python baseline and Go staging with same fixture data, compare status/header/body (canonicalized timestamps/IDs only where expected), rendered HTML DOM markers, storage bytes/disposition, and database transition results. Load test upload streaming and concurrent submit/version creation.
7. **Cutover.** Put Python in read-only/maintenance mode, final sync/reconcile, deploy Go on same origin behind reversible routing, smoke login/PAT/critical transitions/downloads, then shift traffic. Retain Python image/database export and Storage object manifest. Browser sessions re-login; PATs continue.
8. **Rollback.** Before accepting writes, reverse proxy to Python. After accepting writes, rollback is only safe by restoring Go-write data into the frozen Python schema/object volume or keeping Go authoritative; do not silently dual-write. Prefer a short maintenance window over dual writes. Declare rollback window closed after first unreconciled Go mutation.

### Deployment/data consistency/observability

- No live dual-write. A strangler is useful only for read-only pages/API GETs behind a feature/proxy switch; lifecycle writes must have one authority to avoid divergent revision numbers and uploaded object references.
- Health: liveness `/healthz`; readiness checks runtime DB role/RLS query and Auth/JWKS cache availability without leaking detail. Monitor 5xx, auth 401/403/302 rate, `23505` transition conflicts, upload size/duration/failures, storage compensation/orphans, object download 404s, RLS denials, DB pool saturation, callback errors, and migration reconciliation mismatches. Alert on nonzero orphan backlog and unexpected service-role use.
- Back up Postgres and Storage independently; test restore into an isolated project before cutover. Object deletion should be asynchronous/retryable only after metadata transaction commits; no storage event/webhook is required for v1.

## 7. Test strategy and equivalence suite

- **Unit:** enum/label/preview/disposition, strict decode, nullable PATCH, state transition tables, revision allocator retry, timestamp clock, cookie/next sanitization, PAT hash/expiry/revoke. The existing equivalent behavior is concentrated in `tests/test_auth_service.py`, `test_file_preview.py`, `test_vdi_lifecycle.py`, `test_rfi_submit.py`, and `test_jsa.py`.
- **Repository integration:** disposable Supabase/Postgres schema; assert RLS for active/inactive/admin/anonymous principals, constraints/cascades, function binding, concurrent version/submission allocation, and SQLSTATE-to-409 mapping. Never use a bypass-RLS test connection for authorization assertions.
- **HTTP contract:** table-driven tests for every matrix row: auth mode, request body/form, exact status/`detail`, response JSON schema/order, headers, redirects/cookies, file bytes/disposition. Port the Python suite (39 Python test files plus `tests/test_list_filter.js`) as behavior specification, not line-for-line implementation.
- **HTML/TS:** `httptest` HTML DOM/substring snapshots for every page and historical/read-only condition; TypeScript DOM tests for fetch/multipart/modal/theme/list filtering using a lightweight browser runner only if chosen by frontend owner. Manual dark/light accessibility/keyboard pass remains required.
- **Migration:** fixture database with every lifecycle state, bound/unbound/deactivated/break-glass users, expired/revoked PATs, missing local file, MIME branches, duplicate values, all version histories. Assert row/object checksums, constraints, and Go-vs-Python golden endpoint responses.
- **Security:** JWT issuer/audience/signature/key rotation/expiry rejection; CSRF; open redirect; stored SVG download-only behavior; path traversal; oversized/truncated multipart; RLS direct-connection tests; service-role non-exposure scan.

Current test command is blocked locally: `pytest -q` fails during `tests/conftest.py:5` import because the executing Python lacks `pytest_asyncio` (`ModuleNotFoundError`), despite `requirements.txt:9-10` declaring it. No packages were installed.

## 8. Files: replace, retain, delete after cutover

| Action | Files |
|---|---|
| Replace/add | `supago/go.mod`, `supago/cmd/onyx/main.go`, `supago/internal/**`, `supago/migrations/**`, `supago/web/**`, `supago/tests/**`, deployment manifest/CI changes approved separately. |
| Retain/migrate | `app/templates/**` -> `supago/web/templates/**`; `app/static/style.css` -> `supago/web/static/style.css`; `app/static/app.js` -> `supago/web/src/app.ts`; `CONTEXT.md`; ADRs as behavioral requirements; tests as golden specification; README rewritten for Go/Supabase after cutover. |
| Delete only after Go production verification and rollback expiry | Python `app/**`, `main.py`, `config.py`, `create_tables.py`, `requirements.txt`, `pytest.ini`, Python tests/venv, local `onyx.db`, filesystem `uploads/` **only after verified Storage migration/backups**. Never delete historical upload bytes merely because their DB references were removed. |
| Do not carry forward | SQLAlchemy models/session engine, FastAPI routers/dependencies, Authlib/Starlette opaque sessions, `aiosqlite/asyncpg` Python requirements, application-created `sessions` table. |

## 9. Recommended toolchain (do not install until approved)

- Go toolchain, `net/http`, `html/template`, `embed`, `slog`, `testing`, `httptest`, `mime`, `io`, `crypto/*` (stdlib).
- `github.com/go-chi/chi/v5` — route/middleware composition.
- `github.com/jackc/pgx/v5` — PostgreSQL/Supavisor connection pool and transactions.
- `github.com/golang-jwt/jwt/v5` — verified JWT parsing; pair with a small cached JWKS fetcher, do not use it to mint Supabase access tokens.
- `github.com/google/uuid` only if UUID parsing/generation is preferred over a small local wrapper; Go-side UUID generation is optional because Postgres `gen_random_uuid()` can own it.
- `esbuild` pinned as a build tool for one TypeScript bundle. No ORM, dependency-injection framework, Supabase client SDK, frontend framework, message queue, or generic repository factory.

## 10. Review findings and residual risks

### Findings

- **High — current storage integrity:** Project/VDI/RFI/JSA deletions cascade database rows but not `files` records/bytes because ownership points from domain rows to `files` (`app/models/project.py:38-57`, `app/models/revision.py:35-95`, ADR 0003 `docs/adr/0003-files-are-a-decoupled-storage-leaf.md:3-7`). A Go migration must inventory and reconcile these orphans; target delete policy is a decision gate, not an implicit cleanup.
- **High — current upload resource/security boundary:** `save_upload` consumes each upload fully into RAM with no size limit and trusts client content type/extension (`app/file/service.py:33-48`). Go must stream and enforce approved limits; preserving unbounded behavior is not robust.
- **High — RLS/service-role risk:** Supabase service-role bypasses RLS. A Go backend connecting as a bypass role while claiming RLS protection would defeat the target authorization model. Require a NOBYPASSRLS runtime DB role plus per-transaction claims/role assertion.
- **Medium — concurrent sequence allocation:** VDI and RFI revisions use `max(revision_number)+1` without an equivalent VDI lock (`app/vdi/revision/service.py:17-48`, `app/rfi/revision/service.py:45-50`); document/library versions derive current loaded collection (`project_doc/service.py:107-128`, `library_document/service.py:45-73`). Unique constraints catch some races, but Go needs parent row locking/retry.
- **Medium — non-atomic local library deletion:** metadata commits before filesystem unlink (`app/library_document/router.py:192-200`), so deletion can leave object bytes. Storage compensation/reconciliation is required.
- **Medium — migration capability:** `create_all()` cannot alter existing schema and explicitly lacks Alembic (`create_tables.py:13-16`); no migration framework/SQL migration files were found. Supabase SQL migrations are a prerequisite, not cleanup.
- **Medium — production secret fail-safe:** `SESSION_SECRET` has an insecure default (`config.py:56-59`). Target config must reject production startup absent strong secret material.
- **Low — page query cost:** home loops projects and individually fetches VDIs (`app/project/web_pages.py:30-41`), an N+1 query. Replace with one aggregate query when porting; no cache is warranted.
- **Low — test environment:** `pytest -q` is presently not runnable due missing `pytest_asyncio`, so baseline execution must be restored in a separate environment before claiming green equivalence.
- **Info — source-plan gap:** required root `plan.md`/`progress.md` are absent. No assumptions from them could be validated.

### Residual risks / gates before implementation

- Supabase Auth provider setup may not exactly reproduce Entra subject/e-mail claims or pre-provision behavior; prove callback/binding in staging with a real tenant test account.
- Supabase database access/role topology must be proven in a staging project; do not rely on client-side RLS documentation alone for direct pgx connections.
- Existing orphan uploads and missing local bytes make a perfect metadata/object migration impossible without a signed reconciliation policy; report every missing/orphan object and obtain owner disposition.
- Current API Pydantic `422` detail format, accidental unique-project errors, datetime formatting, and template whitespace need golden baselines before strict compatibility can be asserted.
- Browser sessions necessarily terminate at auth cutover; communicate forced re-login. PAT continuation requires retaining hashes and exact token lookup semantics.

## 11. Official sources

- Supabase Auth JWTs: <https://supabase.com/docs/guides/auth/jwts>
- Supabase Auth server-side/PKCE flow: <https://supabase.com/docs/guides/auth/server-side/creating-a-client>
- Supabase Azure social login: <https://supabase.com/docs/guides/auth/social-login/auth-azure>
- Supabase Row Level Security: <https://supabase.com/docs/guides/database/postgres/row-level-security>
- Supabase RLS with Auth helpers: <https://supabase.com/docs/guides/database/postgres/row-level-security#helper-functions>
- Supabase database roles: <https://supabase.com/docs/guides/database/postgres/roles>
- Supabase Storage access control: <https://supabase.com/docs/guides/storage/security/access-control>
- Supabase Storage uploads: <https://supabase.com/docs/guides/storage/uploads/standard-uploads>
- Supabase connecting to Postgres: <https://supabase.com/docs/guides/database/connecting-to-postgres>
- Go `net/http`: <https://pkg.go.dev/net/http>
- pgx: <https://pkg.go.dev/github.com/jackc/pgx/v5>
