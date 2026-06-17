# File Storage — Notes & Deferred Work

## content_type is client-supplied (not verified)

The `File.content_type` column stores the MIME type taken from
`UploadFile.content_type`, which is **supplied by the uploading client**. It can
be `None`, missing, or deliberately spoofed. We accept this for now because Onyx
is an internal tool and the risk is low.

### Future consideration: server-side type sniffing
If we ever need to *trust* `content_type` (e.g. public uploads, serving files
inline to browsers where a spoofed type could be an XSS/content-sniffing vector,
or rejecting non-PDF/Office uploads), verify the type server-side by inspecting
the file's magic bytes rather than trusting the header.

- Likely approach: `python-magic` (libmagic bindings) or a small hand-rolled
  magic-number check for the handful of types we accept (PDF, XLSX, DOCX, etc.).
- `python-magic` is a **new dependency** — per CLAUDE.md, ask before adding it,
  and remember libmagic is a system-level dep on the VPS.
- Decide at that point whether to reject-on-mismatch or just store the sniffed
  type alongside the declared one.

## Deferred: orphaned-file cleanup / GC job

Writing bytes to disk is **not** part of the DB transaction. We write bytes
first, then create the `File` row, then flush, then the route commits. This makes
a *dangling reference* (row with no bytes) impossible, but allows *orphaned bytes*
(bytes on disk with no row) if a commit fails after the write. We accept that for
now — a stray unreferenced file is harmless.

Future work: a reconciliation/GC job that:
- deletes files on disk under `FILE_ROOT` that have no matching `File` row, and
- deletes the bytes when a `Revision`/`VDI` is removed — note the FK direction
  (FKs live on `Revision`, see ADR/Q3) means an ORM cascade will **not** clean up
  `File` rows or their bytes automatically; this must be explicit.

## Deferred: real migration story (Alembic) before VPS launch

There is no migration tool today; `create_tables.py` runs `create_all`, which is
additive only and will not ALTER existing tables. The File-storage change is
applied locally by deleting `onyx.db` and recreating it — fine while there's no
data to preserve. Before the VPS launch (production data), introduce Alembic so
schema changes can be migrated instead of requiring a DB drop. Alembic is a new
dependency — ask before adding.

## Deferred: VPS upload size cap

No app-level upload size limit. Set `client_max_body_size` on the VPS reverse
proxy (nginx) to cap upload size at the edge.
