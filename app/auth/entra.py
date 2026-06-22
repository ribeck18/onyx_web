"""The single-tenant Microsoft Entra OIDC client and the identity seam.

Authentication is Authorization Code + PKCE with a confidential client secret,
requesting only ``openid profile email`` — no Microsoft Graph, no admin-consent
scopes (ADR 0007). ``exchange_code_for_claims`` is the one thin seam the callback
depends on: auth-flow tests monkeypatch it to return fake validated claims, so
everything downstream runs for real without ever contacting Microsoft.
"""

from __future__ import annotations

from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
from starlette.responses import RedirectResponse

import config

oauth = OAuth()
oauth.register(
    name="entra",
    client_id=config.client_id,
    client_secret=config.client_secret,
    # The tenant-scoped metadata URL pins logins to the company directory, so
    # arbitrary personal Microsoft accounts cannot authenticate.
    server_metadata_url=(
        f"https://login.microsoftonline.com/{config.tenant_id}"
        "/v2.0/.well-known/openid-configuration"
    ),
    client_kwargs={"scope": "openid profile email"},
)


def callback_redirect_uri() -> str:
    """The absolute redirect URI registered with Entra for the callback."""
    return f"{config.app_base_url}/auth/callback"


async def build_authorize_redirect(request: Request) -> RedirectResponse:
    """Start the Authorization Code + PKCE flow, redirecting to Entra.

    Authlib stashes the transient ``state`` / ``nonce`` / PKCE verifier in the
    signed handshake cookie (Starlette SessionMiddleware) for the callback.
    """
    return await oauth.entra.authorize_redirect(request, callback_redirect_uri())


async def exchange_code_for_claims(request: Request) -> dict[str, str]:
    """Complete the callback and return the validated identity claims.

    ``authorize_access_token`` exchanges the code and fully validates the ID
    token (JWKS signature, ``iss`` / ``aud`` / ``exp`` / ``nonce``) before we
    trust any claim. We read only the identity fields Onyx needs.
    """
    token = await oauth.entra.authorize_access_token(request)
    userinfo = token.get("userinfo") or {}
    return {
        "oid": userinfo.get("oid", ""),
        "email": userinfo.get("email") or userinfo.get("preferred_username") or "",
        "name": userinfo.get("name", ""),
    }
