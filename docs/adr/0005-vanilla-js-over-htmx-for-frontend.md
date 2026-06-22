# The server-rendered frontend uses minimal vanilla JS, not HTMX

The frontend is server-rendered Jinja2 with a small, dependency-free sprinkle of
**vanilla JS** (`static/app.js`) for the interactions plain HTML forms can't do:
modal open/close, the delete-mode border toggle + `confirm()`, and `fetch()`
calls for mutations (notes `PATCH`, deletes, create). We chose vanilla JS over
HTMX because our `/api` is JSON-first by deliberate design (ADR 0004): every
route returns a pydantic `*Read` model. Vanilla JS consumes that JSON natively
(`fetch` → JSON → update DOM), whereas HTMX expects **HTML fragments** back and
would force us to build a parallel set of fragment-returning endpoints alongside
the JSON API — re-forking the surface we just unified under `/api`.

A future reader will see JavaScript in an app described as "server-rendered,
minimal JS" and reasonably ask "why not HTMX?" — this records that the question
was considered and answered, not overlooked.

## Considered options

- **Minimal vanilla JS against the JSON API (chosen)** — no new dependency, no
  build step, and the existing JSON `/api` is already the exact contract a
  `fetch`-driven UI wants. The JS stays small: reach for the server / full-page
  reload first, use JS only where a client-side interaction genuinely requires
  it (modals, delete-mode toggle, in-place notes save).
- **HTMX** — rejected. It is the better tool *only* for the server-round-trip
  parts (notes `PATCH`, `hx-delete` + `hx-confirm`), and even then it wants HTML
  fragments, not the JSON our API returns — so adopting it means a second,
  fragment-returning endpoint set. It also does **not** handle the pure
  client-state toggles (modal open/close, delete-mode highlighting), which still
  need JS regardless. So HTMX would add a dependency and a backend fork while
  only partially removing the JS. Net loss at this scale.
- **Pure no-JS (dedicated pages + POST-only forms)** — rejected. It would force
  dropping the modal and delete-mode UX in favor of separate `/new` pages, and
  HTML forms can't issue the `PATCH`/`DELETE` the lifecycle and notes editing
  rely on.

## Consequences

- A new frontend dependency (HTMX, Alpine, a framework, or a build step) is a
  deliberate reversal of this ADR, not a default to reach for.
- The JSON `/api` stays the single backend contract; HTML pages render via
  direct service calls (not self-HTTP), and all UI mutations go through that
  same JSON API.
