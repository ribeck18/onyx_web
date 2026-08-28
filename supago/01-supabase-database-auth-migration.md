# Supabase database + auth migration

## Executive recommendation

Move the authoritative data and file bytes to one Supabase project: Postgres (`public` application schema), Auth (Azure/Entra OIDC), and private Storage. Keep **all mutations and lifecycle/version allocation behind the Go API/RPCs**; do not expose the generated data API as the product API initially. The vanilla TypeScript browser uses only a publishable/legacy `anon` key plus its Auth JWT; the Go service validates that JWT and uses a database connection carrying the caller JWT for RLS, or a server-only `service_role`/secret key only for narrowly audited administration and migrations.

Default tenancy: one organization, because the application explicitly says every allowed user can see every project ([`CONTEXT.md:63-67`](../CONTEXT.md#L63-L67)). Still add `organizations` and `organization_memberships` now; it makes RLS explicit and prevents a later tenant retrofit. Default roles: `member` can read/write business data; `admin` manages memberships and API keys; no browser role can bypass RLS. This retains present behavior while permitting project-scoped roles later.

**Do not cut over by pointing SQLAlchemy at Supabase.** The destination is shared by a Go server and browser, the current application has no migration history, and important write invariants live in Python routes/services. Use versioned Supabase SQL migrations and a Go API replacement, then retire Python.

Assumptions: the checked-in SQLite DB and `uploads/` are the source of truth; Entra remains single-tenant; internal users remain allowed to read all organization data; no active production workload must remain writable during more than a brief cutover. `plan.md` and `progress.md` were requested but do not exist at the supplied paths.

## Verified current state

### Data, lifecycle, and access inventory

* Async SQLAlchemy is configured from mandatory `DATABASE_URL`, with `async_sessionmaker`; no pool, TLS, schema, or lifecycle hook configuration exists ([`app/database.py:1-24`](../app/database.py#L1-L24)). `create_tables.py` calls `Base.metadata.create_all`; it is explicitly additive-only and has a TODO for Alembic ([`create_tables.py:10-18`](../create_tables.py#L10-L18)).
* All 15 models are registered in [`app/models/__init__.py:3-36`](../app/models/__init__.py#L3-L36). IDs are integer PKs. FKs omit database `ON DELETE` actions; SQLAlchemy relationship cascades supply some deletes, so a raw SQL/client delete would not preserve present behavior.
* `Project` is globally unique by `project_number` and owns VDIs, project documents, RFIs, and at most one JSA ([`app/models/project.py:18-58`](../app/models/project.py#L18-L58)). Current API/page routes have a global authentication gate; business routers have no per-project authorization because every user is intentionally universal ([`app/app.py:53-76`](../app/app.py#L53-L76), [`app/auth/middleware.py:26-100`](../app/auth/middleware.py#L26-L100)).
* VDI/revision, RFI/revision, project-document/version, library-document/version, and JSA/revision/file-link model cardinalities and uniqueness are defined at [`app/models/vdi.py:27-89`](../app/models/vdi.py#L27-L89), [`revision.py:26-95`](../app/models/revision.py#L26-L95), [`rfi.py:28-71`](../app/models/rfi.py#L28-L71), [`rfi_revision.py:20-84`](../app/models/rfi_revision.py#L20-L84), [`project_doc.py:26-74`](../app/models/project_doc.py#L26-L74), [`doc_version.py:24-59`](../app/models/doc_version.py#L24-L59), [`library_document*.py`](../app/models), and [`jsa*.py`](../app/models). Enum values are stored as strings; this is intentional for SQLite/Postgres portability (ADR 0001).
* State changes are route/service code, not DB constraints: VDI submit/return restrictions ([`app/vdi/service.py:18-34`](../app/vdi/service.py#L18-L34), [`app/vdi/router.py:125-192`](../app/vdi/router.py#L125-L192)); RFI restrictions and its `FOR UPDATE` lock ([`app/rfi/service.py:19-50`](../app/rfi/service.py#L19-L50)); JSA decisions ([`app/jsa/router.py:73-172`](../app/jsa/router.py#L73-L172)). Version numbers are `max + 1`; only RFI acquisition is locked. VDI (`app/vdi/revision/service.py:17-47`) and project-doc (`app/project_doc/service.py:107-128`) concurrent uploads can race today.
* File metadata is a deliberately decoupled leaf: `stored_path`, original name, client-provided MIME, timestamp ([`app/models/file.py:11-30`](../app/models/file.py#L11-L30)). Bytes are read wholly into memory, written to a local UUID path before the DB row/commit, and can orphan on rollback ([`app/file/service.py:21-52`](../app/file/service.py#L21-L52); [`claude_brain/FILE_STORAGE_NOTES.md:23-44`](../claude_brain/FILE_STORAGE_NOTES.md#L23-L44)). Any authenticated user can retrieve any file ID through `/api/files/{id}` ([`app/file/router.py:17-52`](../app/file/router.py#L17-L52)); that currently matches universal access but cannot survive tenant/project access.
* Browser pages are server-rendered and mutation JavaScript calls `/api` ([`app/static/app.js:28-48`](../app/static/app.js#L28-L48)); all pages/services use the same database session. Tests override an in-memory SQLite database and use a minted PAT by default ([`tests/conftest.py:23-94`](../tests/conftest.py#L23-L94)). The suite passed: **315 passed**.

### Authentication and deployment inventory

* Entra uses Authlib authorization-code + PKCE, tenant-specific OIDC metadata, `openid profile email`, and callback `APP_BASE_URL/auth/callback` ([`app/auth/entra.py:18-59`](../app/auth/entra.py#L18-L59)). Authlib validates the ID token before claims are used.
* Local `users` is the allowlist/role record: email-provisioned then permanently bound to Entra `oid`, with `is_admin` and `is_active` ([`app/models/user.py:16-57`](../app/models/user.py#L16-L57)). Login supports `.env` break-glass email rebinding/auto-provisioning ([`app/auth/service.py:108-149`](../app/auth/service.py#L108-L149)). Admin API is router-wide gated ([`app/auth/router.py:19-148`](../app/auth/router.py#L19-L148)).
* Human auth is an app-owned opaque cookie/session row (8-hour idle, 7-day absolute), only SHA-256 token hashes persist ([`app/models/session.py:15-46`](../app/models/session.py#L15-L46), [`app/auth/service.py:152-221`](../app/auth/service.py#L152-L221)); local logout deletes it ([`app/auth/web_pages.py:97-109`](../app/auth/web_pages.py#L97-L109)).
* Machine access is an app-issued opaque PAT (SHA-256 hash, 90-day expiry, revoke/last-used), accepted as `Authorization: Bearer` by middleware ([`app/models/api_token.py:15-52`](../app/models/api_token.py#L15-L52), [`app/auth/service.py:224-308`](../app/auth/service.py#L224-L308)).
* Environment has SQLite local DB, local upload root, Entra client credentials, cookie secret, break-glass list and flags ([`config.py:37-71`](../config.py#L37-L71), [`.example_env:1-10`](../.example_env#L1-L10)). Requirements contain SQLAlchemy/asyncpg/Authlib but no Supabase CLI/client ([`requirements.txt`](../requirements.txt)). There is no Docker/deployment manifest or test workflow; the sole CI workflow is CodeQL ([`.github/workflows/codeql.yml:12-101`](../.github/workflows/codeql.yml#L12-L101)).

### Findings carried into the plan

| Severity | Finding | Evidence / required treatment |
|---|---|---|
| High | No reproducible, reversible schema migration path. | `create_all` cannot alter existing production schema ([`create_tables.py:13-16`](../create_tables.py#L13-L16)). Establish Supabase CLI SQL migrations before loading data. |
| High | Files are non-transactional, unbounded in app, and MIME is untrusted. | Whole upload is read in memory and trusts `UploadFile.content_type` ([`app/file/service.py:33-49`](../app/file/service.py#L33-L49)); deferred notes acknowledge no cap/type verification ([`FILE_STORAGE_NOTES.md:3-21,46-49`](../claude_brain/FILE_STORAGE_NOTES.md#L3-L21)). Enforce Storage bucket limits, server streaming/size checks, allowlist/sniffing, and reconciliation. |
| High for future multi-tenancy | Current routes and file endpoint authorize only “authenticated”, not organization/project membership. | Global gate ([`app/auth/middleware.py:71-88`](../app/auth/middleware.py#L71-L88)) and file fetch ([`app/file/router.py:32-51`](../app/file/router.py#L32-L51)). RLS must derive access from membership and storage object ownership/path. |
| Medium | Concurrent VDI/project-document version allocation can conflict. | `max + 1` without lock (`app/vdi/revision/service.py:17-47`; `app/project_doc/service.py:107-128`). Replace with transactionally locked Go workflow/RPC; retain unique constraints as backstop. |
| Medium | Present deletes leave file metadata/bytes for most domain deletes; only library deletion explicitly removes file rows/bytes. | ADR 0003 ([`docs/adr/0003-files-are-a-decoupled-storage-leaf.md:3-7`](../docs/adr/0003-files-are-a-decoupled-storage-leaf.md#L3-L7)); library special case ([`app/library_document/service.py:104-112`](../app/library_document/service.py#L104-L112)). Decide retention, then use a cleanup queue/job—not accidental DB cascades. |
| Medium | No actor/audit history exists for business mutations. | Models hold timestamps but no `created_by`, `updated_by`, or audit table. Add actor fields/audit event table before a shared browser backend. |

## Target architecture and trust boundaries

```text
TypeScript browser --HTTPS--> Supabase Auth (Azure PKCE) ----> JWT/session
       | publishable/anon key + bearer access token only          |
       +--HTTPS--> Go API (validates issuer/audience/signature/JWKS; authorizes)
                           | transaction/RPC as caller JWT
                           +--> Supabase Postgres RLS + private Storage signed URLs
                           |
                           +--> secret/service_role client: migrations, Auth admin,
                                data import and scheduled cleanup only (never browser)
```

1. Auth is identity only; application authorization is `public.profiles`, `organizations`, and `organization_memberships`. `profiles.id uuid primary key references auth.users(id) on delete restrict`; do **not** expose `auth` schema or read `auth.users` from browser policies.
2. A `security definer` membership helper owned by a non-login migration owner returns membership only, has `set search_path = public`, and is not executable by `anon`/`public` unless needed by policy. Policies call `(select is_org_member(organization_id))` so it is evaluated once per query.
3. Browser may call `supabase.auth.signInWithOAuth({provider:'azure', options:{redirectTo}})` and carry its access token to Go. It may use Storage direct upload only through a Go-generated signed upload URL after authorization. It must not perform direct business-table writes in phase 1.
4. Go verifies tokens **before** trusting `sub`, `role`, email, or custom claims: accept only the configured project issuer and audience, validate signature via the project JWKS with cached key rotation, `exp`, `nbf`, and algorithm allowlist. Never use `getSession()`-style unverified browser state as server proof. For RLS-preserving DB calls, set the verified incoming JWT in the Supabase client/connection; never replace it with `service_role` for ordinary requests.
5. Service/secret keys bypass RLS. Keep them only in Go/CI secrets, restrict their code paths, log actor/action/target, and rotate if exposed. Supabase now calls browser-safe keys “publishable”; legacy `anon` has the same public placement only when RLS is enabled. The requested `service_role` is legacy terminology but has the same server-only, RLS-bypass constraint.

### Minimal authorization schema and policy pattern

```sql
create type public.app_role as enum ('admin', 'member');
create table public.organizations (
  id uuid primary key default gen_random_uuid(), slug text not null unique,
  name text not null, created_at timestamptz not null default now()
);
create table public.profiles (
  id uuid primary key references auth.users(id) on delete restrict,
  entra_oid uuid unique, email citext not null unique, display_name text,
  is_active boolean not null default true, created_at timestamptz not null default now(),
  last_login_at timestamptz
);
create table public.organization_memberships (
  organization_id uuid not null references public.organizations(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  role public.app_role not null default 'member',
  primary key (organization_id, user_id)
);
create or replace function public.is_org_member(target_org uuid)
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from organization_memberships m join profiles p on p.id=m.user_id
                 where m.organization_id=target_org and m.user_id=auth.uid() and p.is_active)
$$;
revoke all on function public.is_org_member(uuid) from public;
grant execute on function public.is_org_member(uuid) to authenticated;
alter table public.projects enable row level security;
create policy project_read on public.projects for select to authenticated
  using ((select public.is_org_member(organization_id)));
create policy project_write on public.projects for all to authenticated
  using ((select public.is_org_member(organization_id)))
  with check ((select public.is_org_member(organization_id)));
```

Use `citext` only after enabling the extension in the first migration, or use `lower(email)` unique index. Use server-set timestamps and `created_by/updated_by uuid` populated in Go/RPC; do not let the client submit organization/actor ownership. Reassess `on delete restrict` vs right-to-erasure before implementation; it prevents an admin Auth deletion from silently losing business records.

## Table-by-table destination and import map

Use `bigint generated by default as identity` for imported application IDs in phase 1, preserving all integer PK/FK values and existing URL/API references. Each organization-owned table gains `organization_id uuid not null`; set it to the one migrated organization. Later UUID-only public IDs are optional and should not block the cutover. Import source timestamps as UTC `timestamptz`, use destination defaults only for new rows.

| Current table / source | Destination / mapping | Constraints and migration notes |
|---|---|---|
| `projects` | `projects(id bigint, organization_id, project_number, name, description, created_at, updated_at, created_by, updated_by)` | Change unique `(project_number)` to `(organization_id, project_number)`. Add index `(organization_id, project_number)`. |
| `vendor_data_items` | Same name; copy all fields plus `organization_id` and actors. | FK `project_id -> projects` `on delete cascade`; unique `(project_id,item_number)`; checks for approval type, submit code, and status strings. Index `(organization_id,project_id,item_number)`. |
| `revisions` | Rename to `vdi_revisions` **only if Go API is intentionally versioned/breaking**; otherwise retain `revisions` for low-risk parity. | Preserve submit/return file IDs and `(vendor_data_item_id,revision_number)`. Validate status/returned field consistency in Go/RPC. |
| `rfis` | Same name plus organization/actors. | `project_id` cascade; unique `(project_id,rfi_number)`; RFI status check. |
| `rfi_revisions` | Same name plus organization/actors. | FKs to RFI and files; unique `(rfi_id,revision_number)`. |
| `project_docs` | Same name plus organization/actors. | Project cascade. Preserve label/type/doc_number/description; document type check. |
| `doc_versions` | Same name plus organization/actors. | Project-doc cascade; file FK `restrict`; unique `(project_doc_id,version_number)`. Ensure initial documents have version 1. |
| `jsas` | Same name plus organization/actors. | Project cascade; unique `project_id`; JSA status check. |
| `jsa_revisions` | Same name plus organization/actors. | JSA cascade; unique `(jsa_id,revision_number)`. |
| `jsa_files` | Same name plus organization/actors. | JSA-revision cascade; file FK restrict; unique `(jsa_revision_id,file_group,position)` plus check group/`position >= 0`. |
| `library_documents` | Same name plus `organization_id` and actors. | Current “company-wide” becomes organization-wide. Index `(organization_id, lower(title))`. |
| `library_document_versions` | Same name plus organization/actors. | Library-document cascade, file restrict, unique `(library_document_id,version_number)`. |
| `files` | `files(id bigint, organization_id, bucket_id text, object_path text unique, original_name, content_type, byte_size bigint, sha256 text, created_at, created_by)` | Replace `stored_path` with opaque Storage object key. Backfill MIME only as declared value; calculate byte size/SHA-256 during upload copy. Restrict row deletion while referenced. |
| `users` | Split into `auth.users` + `public.profiles` + membership above. | Preserve local integer ID in `profiles.legacy_user_id unique` for token migration/audit; do not put roles in JWT as sole authority. |
| `sessions` | **Do not import.** | Supabase Auth owns refresh/session state; force sign-in after cutover. |
| `api_tokens` | `personal_access_tokens` only if machine PAT compatibility is required. | New UUID id, `profile_id`, `token_hash`, token prefix/last four, scopes, created/expires/last_used/revoked. Import hashes unchanged only if SHA-256 lookup is retained; never import raw token (none exists). |

The import must reject (not coerce) missing FK targets, malformed timestamps, duplicate uniqueness keys, unknown enum values, noncontiguous/nonpositive required version positions, and DB/file mismatch. Capture deletion/orphan findings separately rather than inventing domain links.

## Auth migration, Entra, sessions, and PATs

1. **Provisioning model (default):** retain app-controlled allowlisting. An admin creates a pending `profiles`/membership record with normalized email; no self-signup. On first Azure login, a Go Auth webhook or post-login Go callback links `auth.uid()` to the pending record after validating email and Entra immutable object ID. Store the Entra `oid` in `profiles`, not email as identity. Enforce one matching pending record and transactionally reject a collision; only a separately audited break-glass operation may rebind.
2. Configure Supabase Auth Azure provider with the existing tenant-specific Entra app registration/client secret. Change Entra’s redirect URI to `https://<project-ref>.supabase.co/auth/v1/callback`; add allowed application redirect URLs for local/staging/prod. Disable email/password, magic link, and arbitrary signups if Entra-only is chosen. Azure Conditional Access/MFA remains Entra’s responsibility.
3. **Decision gate — Supabase Auth vs app-owned browser sessions. Default: Supabase Auth sessions.** This simplifies the future TypeScript client and makes JWT/RLS native, but immediate per-request server-side revocation differs from current opaque rows. Compensate with short access-token lifetime, refresh-token controls, `profiles.is_active` RLS checks, and Go authorization checks. If instant logout/session inventory is a hard requirement, retain a Go session-denylist/session table and validate it in Go; do not expect RLS alone to invalidate an already minted JWT instantly.
4. **Decision gate — break-glass. Default: remove `.env` email auto-admin/rebind.** Bootstrap a first admin using a controlled migration/runbook and maintain membership roles in DB. If break-glass is mandatory, retain an emergency group/account documented in Entra plus a separately rotated server-side bootstrap mechanism; never make an email environment variable silently override deactivation.
5. PATs are not Supabase Auth access tokens. Default: retain scoped, hashed `personal_access_tokens` only for MCP/CLI during transition; Go exchanges/validates them and maps to a profile. Do not put a PAT in browser storage or pass it to Supabase directly. Add `scope`, prefix, rate limits, expiry/revocation, last-used throttle, and audit event. Decision gate: if the MCP can use OAuth device/authorization-code flow, retire PATs after it ships; this is more secure but changes the current ADR 0008 contract.
6. Migration ordering: create Auth users by Azure login/provisioning, map old user integer IDs to Auth UUIDs, then memberships/profiles. No current passwords, refresh tokens, or raw sessions can or should be copied. Existing cookie users must reauthenticate; existing PATs may continue only through the Go compatibility validator until their 90-day natural expiry, then revoke all.

## RLS and private Storage policy matrix

Enable RLS on **every** `public` table at creation. Tables must not be created through the dashboard without policies. The matrix assumes one organization, then works unchanged for many.

| Resource | `authenticated` direct browser policy | Go ordinary request | Service/secret key |
|---|---|---|---|
| profiles | select/update own safe fields only; no client role/active/Entra updates | verify active profile; admin provisioning operations | Auth-admin reconciliation only |
| organizations/memberships | member reads its organization/membership; admin-only membership changes | enforce admin membership in transaction | bootstrap/import only |
| projects, VDIs, RFIs, docs, JSAs, revisions/link rows | select where active org membership; **no insert/update/delete policy initially** | transaction/RPC verifies membership, lifecycle, actor, then writes with caller JWT/RLS | never normal request |
| files metadata | select if member and referenced by an accessible object; no direct changes | creates after authorized upload; deletes only retention workflow | import/GC only |
| personal access tokens | owner reads metadata/creates/revokes own only, no hash select | validates hashed bearer token server-side | emergency revoke/audit |
| audit_events | no direct write; own-org/admin read only if required | append-only procedure | forensic export |
| `storage.objects`, bucket `onyx-private` | no list/select/insert/delete by broad path policy; direct signed URL only | issue signed upload/download after membership + file-reference authorization | importer/cleanup only |

Storage is warranted: all current binary data is local and needs shared, durable access. Create private bucket `onyx-private`; object key is server-created `org/<org_uuid>/files/<file_uuid>`—never user filename or user-supplied key. Go issues short-lived signed upload/download URLs after authorizing the *specific file reference*. Prefer Go proxy/stream for inline content if response headers/type disposition need central enforcement. Verify magic bytes and size before finalizing metadata, set `Content-Disposition` safely, `X-Content-Type-Options: nosniff`, and allow only safe preview types. Do not make the bucket public and do not rely on hidden object names as authorization.

Example defense-in-depth Storage policy for a strictly server-signed-url design (service role bypasses it; signed URLs are capability tokens):

```sql
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('onyx-private','onyx-private',false, 52428800,
  array['application/pdf','image/png','image/jpeg','image/gif','image/webp',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document']);
-- No authenticated storage.objects policies: browser accesses only signed URLs.
-- Explicitly revoke broad grants/policies introduced by templates; test anon/authenticated denial.
```

If direct browser uploads are later selected, create a narrow `storage.objects INSERT ... WITH CHECK` policy tied to `owner=auth.uid()` and the exact org prefix, plus a finalization RPC that validates it; do not grant arbitrary object `SELECT`/`UPDATE`/`DELETE`.

## Go/backend and TypeScript contracts

**Go API:** `/v1` endpoints accept `Authorization: Bearer <Supabase access JWT>`; authenticate middleware returns `subject UUID`, active profile, memberships, and request ID. It maps `401` for invalid/expired JWT, `403` for valid but inactive/not a member, `404` for inaccessible object IDs where enumeration matters, `409` for lifecycle/unique conflicts, and `422` for malformed payload. It owns validation, lifecycle transition, version allocation, storage URL issue/finalize, transaction and audit insert. Use `pgx` with a pooled direct Postgres connection for migrations/jobs and parameterized queries; per user request use an RPC with `auth.uid()` context or a Supabase client configured with that caller’s JWT so RLS is actually exercised.

**Browser:** Supabase JS Auth client receives project URL + publishable/anon key only; `onAuthStateChange` supplies access token to Go. Browser never receives database password, JWT signing key, secret/service-role key, Azure secret, PAT hash, or a Storage management token. Send cookies only if choosing SSR/PKCE cookie integration; otherwise use bearer token and protect against XSS with CSP, no token logging, and short session scope. Existing server-rendered Python pages can remain during parallel operation behind the Go API only; direct table REST access is deliberately postponed.

**Lifecycle RPC/API shape:** e.g. `POST /v1/vdis/{id}/submissions` first creates an upload intent, then `POST /finalize` verifies object checksum and in one transaction locks VDI (`SELECT ... FOR UPDATE`), inserts next revision, sets state, and audits. This fixes the current byte-before-commit orphan window and version race. Equivalent operations cover return, RFI, JSA package, document version, and library version.

## Phased, rollback-safe delivery

0. **Decisions and backup:** approve the three decision gates above; inventory source with read-only SQLite `PRAGMA foreign_key_check`, row counts, file list/size/hash manifest; back up `onyx.db` and uploads immutable/offsite. Freeze a source timestamp. Do not run `create_tables.py` against Supabase.
1. **Foundation:** `supabase init`, link non-production project, create ordered SQL migrations for extensions/schema/constraints/RLS/bucket/functions/seed admin. Apply to disposable local Supabase and staging with `supabase db reset`/migration lint. Deploy a Go JWT middleware proof that rejects wrong issuer/audience/signature and refuses secret key in browser build.
2. **Auth pilot:** configure Azure provider, redirect allowlists, email/password/signup settings, SMTP if invitations are used, first admin runbook, profile/membership linking. Test a nonmember, pending member, inactive member, admin, and Azure tenant outsider. No production data writes yet.
3. **Data + objects dry run:** export SQLite tables in FK order into staging with explicit identity values; upload each local file under a new object key, calculate size/SHA-256, then import `files` and dependent tables. Use resumable/idempotent manifest keyed by legacy file ID/object checksum. Do not delete source bytes. Produce per-table count/min-max ID/hash totals/FK/unique/check validation report.
4. **Shadow/read pilot:** Go reads staging (or production replica after confidence), compare API/page outputs and signed downloads to Python. Keep Python as writer. Exercise lifecycle/version race, file type/limit, RLS, admin/pending/disabled, PAT compatibility, and rollback drill.
5. **Cutover:** announce maintenance; stop Python writes; take final SQLite/uploads backup and final delta import; validate; deploy Go and TypeScript config; switch traffic; require human re-login; retain source read-only. Keep old PAT validator for its planned short overlap only.
6. **Rollback:** before accepting any irreversible schema/data change, restore Python traffic, source DB, and local files; invalidate new browser sessions if necessary. Do **not** bidirectionally sync after Go accepts writes. If post-cutover rollback is required, export a timestamped Go write delta and either replay through a tested reverse importer or accept a maintenance/read-only recovery—this is a decision gate. Preserve Supabase backups/PITR and object version/recovery policy according to the selected plan.
7. **Decommission:** after agreed retention and reconciliation, revoke legacy PATs, archive source SQLite/uploads encrypted, remove Python secrets/Entra redirect, then delete/replace listed files. Run storage orphan/referenced-object reconciliation continuously.

## Secrets, CI, tooling, tests

* CI secrets: `SUPABASE_ACCESS_TOKEN`, project ref, database password/connection for migration job, and server-only `SUPABASE_SECRET_KEY`/legacy `SERVICE_ROLE_KEY` only in protected deploy environment. Browser build variables: `SUPABASE_URL`, publishable/anon key only. Go runtime: URL, DB connection, expected issuer/audience/JWKS URL, service key only if privileged operations cannot use direct DB role. Keep Azure client secret in Supabase Auth provider configuration/secret manager, never TypeScript.
* Separate dev/staging/prod projects and Entra redirect URLs. Use Supabase CLI migrations in repository, not dashboard drift; CI performs `supabase db reset`, schema diff/lint, migration apply to staging, Go tests, and a migration dry-run fixture. Pin CLI/Go modules and add secret scanning/dependency scanning; current CodeQL alone does not run tests ([`.github/workflows/codeql.yml:42-99`](../.github/workflows/codeql.yml#L42-L99)).
* Recommended additions (obtain approval before adding): Supabase CLI (developer/CI migration tool), `supabase-go` only if it simplifies Auth/Storage calls; otherwise `pgx` + standard `net/http` is sufficient. TypeScript needs `@supabase/supabase-js` only for Auth and possibly signed-URL upload. Do not add a PostgREST browser data client while Go owns business writes.
* Verification: unit-test Go claims validation and lifecycle transactions; integration-test migrations from SQLite fixture plus hash/count/FK checks; use test Auth users/JWTs to prove every RLS table allows own org and denies other org/anon/inactive user; test storage signed URL expiry, cross-org path denial, oversized/spoofed MIME/malware handling policy, deleted references, no service key in bundles/logs; run concurrent version upload test; perform restore/PITR and cutover/rollback rehearsal. Retain existing Python test cases as behavior fixtures until Go parity is proven (current suite: 315 passing).

## Exact likely replacements/removals

**Replace:** `app/database.py`, `config.py` DB/file/auth variables, `create_tables.py`, all `app/models/*.py`, `app/*/service.py`, `app/*/router.py`, `app/*/web_pages.py`, `app/file/*`, `app/auth/*`, `main.py`, `requirements.txt`, test fixtures/routes, and `app/static/app.js` API/Auth wiring. **Remove after Go/TypeScript cutover:** the Python FastAPI/SQLAlchemy/Authlib/Starlette app (`app/`, `main.py`, `create_tables.py`), local `onyx.db`, and `uploads/` runtime dependency. Keep templates/CSS only if they are intentionally migrated/served; otherwise replace them with the vanilla TypeScript frontend. Preserve historical ADRs as context, but supersede ADRs 0003/0007/0008/0009 with migration decisions.

## Open decisions and residual risks

1. Confirm one organization/global data access versus per-project membership. Default is one org plus membership; choosing direct browser table writes materially expands RLS/RPC scope.
2. Confirm acceptable session revocation latency. Default Supabase session plus active-profile checks cannot revoke a previously issued JWT instantly at every external service without a server denylist.
3. Confirm whether PAT compatibility is needed and its exact consumer/scopes. Default 90-day Go-only compatibility then OAuth migration/retirement.
4. Confirm file retention/deletion, legal hold, maximum size/types, malware scanning, and whether historical local files include sensitive data. Private Storage is necessary, but scan/retention policy is not inferable from this repository.
5. Supabase Auth Azure provider behavior/plan limits, email claim availability, Entra app redirect registration, and backup/PITR/object recovery retention must be verified in the selected Supabase plan before production cutover.

## Official implementation references (accessed 2026-07-28)

* [Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security) — enable RLS, policy behavior, service-role bypass.
* [Login with Azure (Microsoft)](https://supabase.com/docs/guides/auth/social-login/auth-azure) — Azure provider and `https://<project-ref>.supabase.co/auth/v1/callback` registration.
* [JWTs](https://supabase.com/docs/guides/auth/jwts) — issuer/signature/JWKS validation and key rotation.
* [Creating a Supabase client for SSR](https://supabase.com/docs/guides/auth/server-side/creating-a-client) — server/browser session handling guidance.
* [Storage Access Control](https://supabase.com/docs/guides/storage/security/access-control) — Storage RLS policies and private objects.
* [Database migrations / Supabase CLI](https://supabase.com/docs/guides/cli/local-development) — local development and migration workflow.
* [API keys](https://supabase.com/docs/guides/api/api-keys) — publishable/anon versus secret/service-role key placement and bypass risks.
