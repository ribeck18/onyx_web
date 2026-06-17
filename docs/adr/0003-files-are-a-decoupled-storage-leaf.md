# Files are a decoupled storage leaf referenced by Revision

A `File` is a pure storage record — `stored_path` (a `<uuid>.<ext>` name resolved against `FILE_STORAGE_ROOT`), `original_name`, and `content_type` — and it knows nothing about the domain. It carries no foreign key to `Revision` and no back-reference. Instead, the link runs the other way: `Revision` owns two foreign keys, `submit_file_id` (non-null) and `return_file_id` (nullable), each pointing at one `File`. The `app/file/` module depends on nothing domain-specific; the route layer is the only place that knows both a `File` and a `Revision`, and it orchestrates `file.service.save_upload` followed by `vdi.service.submit_vdi`/`return_vdi`, which take a `File`.

We chose this because the cardinality rule — a Revision has exactly one submit file and at most one return file — becomes structurally true: two single-valued columns, no extra uniqueness constraint, no "role" discriminator, no way to attach a second submit file. Keeping `File` ignorant of the domain makes it a clean, reusable leaf (anything could gain files later) and preserves the one-directional dependency flow `route -> vdi.service -> revision.service`, with `file.service` sitting off to the side depending on neither.

The trade-off is cleanup. Because the foreign keys live on `Revision`, deleting a `Revision` (or a `VDI` cascading to its revisions) does **not** remove the `File` rows it pointed at, nor the bytes on disk — an ORM cascade runs the wrong direction for that. File cleanup therefore has to be an explicit, separate concern (a future reconciliation/GC job, tracked in `claude_brain/FILE_STORAGE_NOTES.md`). We accept manual cleanup in exchange for the decoupling and the structurally-enforced cardinality.

## Considered options

- **FK on `File` (`revision_id` + `role` discriminator), Revision holds a collection** — the generic "attachments" pattern. Rejected: it cannot enforce "exactly one submit / at most one return" without an added unique constraint, and it forces the storage leaf to know about revisions, coupling infrastructure to the domain.
- **FKs on `Revision`, `File` as a decoupled leaf (chosen)** — encodes the cardinality directly and keeps `File` reusable and dependency-free, at the cost of manual file cleanup since cascade won't reach the `File` rows.
