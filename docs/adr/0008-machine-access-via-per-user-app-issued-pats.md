# Machine and MCP access uses per-user app-issued tokens, not Entra tokens

Non-browser clients — chiefly the internal MCP server that lets employees drive
projects with AI — authenticate to `/api` with a per-user **Personal Access
Token** that Onyx itself issues: an opaque bearer string, stored hashed in an
`api_tokens` row, with a 90-day hard expiry and one-click revocation. The same
auth middleware accepts **either** a browser session cookie or a bearer PAT,
both resolving to the same `User` and the same downstream rules. We deliberately
did **not** expose Onyx's API as an Entra-protected resource.

Routing machine identity through Entra *with per-user fidelity* means the
on-behalf-of flow, which requires the MCP to itself be an Entra-registered
confidential client that exchanges each user's token — a lot of Azure machinery
for an internal tool. The simpler Entra path, client-credentials, collapses to a
single service identity and loses what we actually want: per-user revocation and
attribution. App-issued PATs keep the machine path self-contained and per-user —
a deactivated user's tokens die with them, and one person's token can be revoked
without touching anyone else's. This continues the reasoning of ADR 0004: the
MCP is an in-house, lockstep-deployable consumer, so its auth is likewise kept
in-house and simple rather than federated.

A future reader will see Entra SSO carrying human login and ask "why doesn't the
API just unify on Entra too?" This records that the answer is on-behalf-of
complexity weighed against simple per-user revocation — a deliberate split, not
an oversight.

A PAT is a long-lived bearer secret sitting in a client config file, which is
the honest cost here. It is mitigated by hashing at rest (a DB leak yields no
usable tokens), the 90-day hard expiry (a leaked token dies on its own),
`last_used_at` visibility, instant revocation, and TLS-only transport — the same
well-understood posture as a GitHub PAT.

## Considered options

- **Per-user app-issued PAT (chosen)** — self-contained, per-user, instantly
  revocable, no new Azure surface; doubles as the test harness for the suite.
- **Entra on-behalf-of** — rejected: the MCP would have to be an Entra
  confidential client exchanging each user's token; heavy for an internal tool.
- **Entra client-credentials / a single service account** — rejected: one
  machine identity for all AI actions, with no per-user revocation or
  attribution and an all-or-nothing kill switch.

## Consequences

- The 90-day hard expiry means the MCP needs a fresh token quarterly; the token
  UI surfaces the expiry date and warns as it approaches, since a silently dead
  MCP is a bad failure mode.
- Cutting over requires a change in the separate MCP codebase to send the PAT as
  an `Authorization: Bearer` header; the two must land together.
