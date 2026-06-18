# The JSON API lives under `/api`; root is reserved for HTML; no URL versioning

Every JSON route is served under an `/api` prefix (`/api/projects`, `/api/vdi`,
`/api/files`, `/api/vdi/{vdi_id}/revisions`). The prefix is applied in one place
— `app.include_router(..., prefix="/api")` in `app/app.py` — so the domain
routers keep their domain-relative prefixes and never know they live under
`/api`. The application root (`/`, `/projects/{id}`, `/vdi/{id}`, …) is reserved
for the server-rendered HTML pages of the planned frontend. The FastAPI docs
(`/docs`, `/openapi.json`) stay at the root by convention. There is **no**
version segment: it is `/api`, not `/api/v1`.

We split the namespace because the frontend is server-rendered HTML served by
this same app, and the clean, human-facing URLs belong to those pages. Keeping
the JSON API under `/api` lets pages and data endpoints coexist without
colliding (no content negotiation on shared URLs, no separate host), and makes
the JSON/HTML boundary a four-line story in `app.py` rather than something
smeared across every router.

We omit versioning because URL versioning only earns its keep when there are
consumers you cannot redeploy in lockstep with the API. Every consumer here is
in-house and lockstep-deployable: the web frontend, and a future internal MCP
server that gives employees AI help. A breaking change to a route is fixed in
the same change that updates its caller. Critically, the future MCP server's
*tool definitions* — not these URLs — are the stable contract the AI and
employees depend on; that façade insulates them from route changes, which
reduces rather than increases the case for versioning the URLs beneath it.

## Considered options

- **JSON at root, HTML elsewhere / content negotiation on shared URLs** —
  rejected: a shared URL like `GET /vdi/{id}` returning either JSON or HTML
  depending on `Accept` is the kind of cleverness this codebase avoids, and it
  muddies which surface owns the clean URLs.
- **`/api` with no version (chosen)** — clean separation, single point of
  definition, no premature contract commitments.
- **`/api/v1`** — rejected as YAGNI: it implies a versioned public contract we
  do not have, and adds URL noise. Versioning can be introduced later if an
  out-of-deploy-control consumer ever appears; until then it is double
  bookkeeping atop the MCP tool-schema façade.
