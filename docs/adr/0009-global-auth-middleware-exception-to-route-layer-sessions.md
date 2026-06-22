# Auth is enforced in global middleware — a deliberate exception to "no DB sessions outside the route layer"

Authentication is enforced by a single global ASGI middleware. It validates the
request's session cookie (or bearer PAT), loads the `User` once onto
`request.state.user`, and rejects anything unauthenticated — a `302` to `/login`
for HTML page requests, a `401` for `/api` requests — against a small public
allowlist (`/login`, `/auth/callback`, `/logout`, `/static`, `/healthz`). To
validate the session it opens a database session in the middleware (plumbing)
layer. That is a deliberate deviation from the project convention that "sessions
are created in the route layer and passed down; services never create their
own."

We did this to make the app **fail closed**. A per-route or per-router
dependency only protects routes someone remembered to decorate; the day a new
router is mounted without it, there is a silent hole open to the internet. One
gate in front of everything means a new route is protected *by default* — you
must consciously add a path to the public allowlist to expose it. For an
internet-facing app whose threat model includes a targeted outsider, "secure
unless you opt out" is the right default, and it is worth bending one convention
to get it.

The convention it bends exists to keep *transaction control* in the route layer.
This exception is narrow and respects that intent: the middleware does a single
read-only auth lookup (plus a throttled `last_seen` touch), and route handlers
still receive their normal injected `AsyncSession` for all real domain work. The
`current_user` dependency simply reads back `request.state.user`, so handlers
stay convention-shaped and there is no second lookup.

A future reader will see a DB session opened in middleware, recognize it breaks
the documented route-layer rule, and be tempted to "fix" it by moving auth into
a route dependency. This records that the deviation is intentional — reverting
it reopens the fail-open hole.

## Considered options

- **Global fail-closed middleware (chosen)** — every route is protected by
  default; the public surface is one explicit, reviewable allowlist.
- **A `require_user` dependency on each router at `include_router`** — rejected
  as the sole mechanism: it fails *open* if a future router is mounted without
  the dependency, relying on memory and code review rather than the framework to
  stay secure.

## Consequences

- The public allowlist is security-sensitive: adding a path to it serves that
  path unauthenticated, so it must change deliberately.
- Auth-state reads/writes (session validation, throttled `last_seen`) live
  outside the route layer by design; domain transactions do not.
