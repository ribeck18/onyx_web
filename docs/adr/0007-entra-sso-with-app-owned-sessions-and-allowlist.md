# Human auth is Microsoft Entra SSO, but Onyx owns its sessions and its access list

All human authentication is single-tenant Microsoft Entra OIDC (Authorization
Code + PKCE, via Authlib). But Entra's job ends at "who is this human": after
the ID token is validated once at the `/auth/callback`, Onyx mints its **own**
server-side session — an opaque, httponly cookie backed by a `sessions` row —
and runs every subsequent request off that. We do **not** carry Entra's
ID/access tokens in the cookie. Separately, access is gated by an app-side
**allowlist**: a `users` row must already exist, keyed on the immutable Entra
`oid` (email is held only for provisioning/display). A break-glass admin set in
`ONYX_ADMIN_EMAILS` bootstraps the empty table and can never be locked out.

We mint our own session rather than ride Entra's tokens so that Onyx's session
lifetime (8h idle / 7d cap) is decoupled from Entra's ~1h token expiry: no
refresh-token juggling, and we get **instant server-side revocation** —
deleting the row, or deactivating the user, kills the session immediately.
That revocation is the defining capability we wanted against a targeted
outsider, and stateless tokens can't provide it without rebuilding server-side
sessions anyway.

We keep an app-side allowlist because Entra authenticates the *whole tenant* —
authentication is not authorization. "May this person use Onyx" is a separate
decision that we own, and "no self-signup" means an admin must have created the
row. We key it on `oid`, never email, because emails get renamed and even
reassigned, and keying access off a mutable, reusable string is how someone
inherits another person's account.

A future reader will see Microsoft SSO and reasonably ask "why is there still a
`users` table *and* a `sessions` table — doesn't Entra handle all that?" This
records that SSO here is **authentication only**: Onyx owns authorization (the
allowlist) and session management (its own cookie) on purpose.

The explicit no-s: single-tenant only (no personal Microsoft accounts); every
authenticated user sees every Project (the admin role gates account management,
not data); and MFA is delegated to your Entra Conditional Access policy, not
built into the app.

## Considered options

- **Mint an Onyx-owned server-side session after validating the ID token
  (chosen)** — session lifetime is ours to set, logout/deactivation revoke
  instantly, and there are no Entra refresh tokens to manage.
- **Carry Entra's ID/access token in the cookie and re-validate per request**
  — rejected: couples the login lifetime to Entra's ~1h expiry (forcing refresh
  tokens to avoid hourly logouts), and revocation becomes murky.
- **App-side allowlist as the authoritative gate (chosen)** — control lives in
  the app, where admins provision people. Entra enterprise-app assignment is a
  fine *additional* gate but was declined as the sole control: it lives in the
  Azure portal and doesn't match in-app provisioning. The app must be correct
  on its own.
- **`fastapi-users` / password auth** — rejected: it would store passwords and
  reinvent, less well, what Entra already does. The employees already have
  Entra identities; the most secure password is the one we never hold.

## Consequences

- The Entra `CLIENT_SECRET` expires (max 24 months); when it does, logins fail
  silently with no code change. Its expiry date must be tracked and the secret
  rotated before it dies.
- New logins depend on Entra availability; an Entra outage blocks sign-in,
  though existing Onyx sessions keep working until their own cap.
