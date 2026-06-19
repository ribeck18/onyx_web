# The file route serves inline only for an allowlist, attachment otherwise

`GET /api/files/{id}` serves a stored upload with `Content-Disposition: inline`
only when its content type is in a fixed safe set (`application/pdf` and raster
images: png/jpeg/gif/webp/bmp); every other type — and any request carrying
`?download=1` — is served `attachment`. We did this to fix the VDI detail page
auto-downloading the latest revision instead of previewing it (issue #25):
`FileResponse(filename=...)` defaults to `attachment`, so the inline `<iframe>`
and `<img>` requests were treated as downloads (the PDF iframe went blank and
the file saved on every load).

The decision worth recording is that the inline allowlist is **deliberately
narrower than `preview_kind`** in `app/web/file_preview.py`, and lives in a
separate `is_inline_safe()` helper. `preview_kind` answers "how does the detail
pane embed this file" and treats *all* `image/*` as previewable — which is
correct, because an `<img src>`-referenced SVG cannot run its scripts.
`is_inline_safe()` answers a different question: "is it safe to hand the browser
these bytes inline at a URL someone can navigate to." There it **excludes
`image/svg+xml`**, because a direct top-level navigation to an inline-served SVG
renders it as the top document, where its `<script>` executes on our origin —
stored XSS against any logged-in user. The route also sends
`X-Content-Type-Options: nosniff`.

We accept the apparent duplication (two overlapping content-type predicates) in
exchange for keeping the security boundary explicit and correct. Reusing
`preview_kind != download` as the inline gate would have been simpler but would
serve SVG uploads inline, relying only on `nosniff` — which does not stop a
correctly-typed `image/svg+xml`.

## Considered options

- **Reuse `preview_kind != download` as the inline gate** — DRY, one predicate.
  Rejected: it serves `image/svg+xml` inline, leaving a scriptable top-level
  navigation on our origin.
- **Dedicated `is_inline_safe()` allowlist excluding SVG (chosen)** — a second,
  narrower predicate in the same module, so "can the pane embed it" and "is it
  safe to serve inline" stay honestly separate.
