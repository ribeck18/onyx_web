"""Auth page routes: the SSO handshake and local logout (ADR 0007).

Mounted at root (no ``/api`` prefix) and on the public allowlist. ``/login``
shows the branded sign-in page; ``/auth/login`` starts the Entra redirect;
``/auth/callback`` validates the identity, applies the allowlist, and mints the
Onyx session; ``/logout`` is local-only — it drops Onyx's session and leaves the
user's Microsoft session untouched.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

import config
from app.auth import entra
from app.auth import service as auth_service
from app.database import get_session
from app.web.templating import render

router = APIRouter(tags=["auth"])


def _safe_next(raw_next: str | None) -> str:
    """Constrain the post-login target to a local path (no open redirect).

    Anything that is not a single-slash-rooted relative path (e.g. ``//evil`` or
    an absolute URL) falls back to the home page.
    """
    if raw_next and raw_next.startswith("/") and not raw_next.startswith("//"):
        return raw_next
    return "/"


def _set_session_cookie(response: Response, raw_token: str) -> None:
    """Attach the opaque session cookie with its security attributes.

    ``httponly`` keeps it out of JavaScript, ``samesite=lax`` blocks it on
    cross-site requests, and ``secure`` (driven by ``COOKIE_SECURE``) keeps local
    http dev working while never sending it in clear text in production.
    """
    response.set_cookie(
        key=auth_service.SESSION_COOKIE_NAME,
        value=raw_token,
        max_age=int(auth_service.SESSION_ABSOLUTE_CAP.total_seconds()),
        httponly=True,
        samesite="lax",
        secure=config.cookie_secure,
        path="/",
    )


@router.get("/login")
async def login_page(request: Request, next: str = "/"):
    """Render the sign-in page, carrying the post-login target through."""
    return render(
        request,
        "auth/login.html",
        {"next": _safe_next(next)},
    )


@router.get("/auth/login")
async def start_login(request: Request, next: str = "/"):
    """Begin the Entra Authorization Code + PKCE flow."""
    request.session["next"] = _safe_next(next)
    return await entra.build_authorize_redirect(request)


@router.get("/auth/callback")
async def auth_callback(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Validate the Entra identity, enforce the allowlist, mint the session.

    A provisioned (or break-glass) identity signs in and is redirected to its
    original destination; an authenticated-but-unprovisioned identity is refused
    with the account-denied page and no session.
    """
    claims = await entra.exchange_code_for_claims(request)
    user = await auth_service.resolve_login(session, claims)
    if user is None:
        await session.rollback()
        return render(request, "auth/denied.html", {}, status_code=403)

    raw_token, _ = await auth_service.mint_session(session, user)
    await session.commit()

    next_target = _safe_next(request.session.pop("next", None))
    response = RedirectResponse(next_target, status_code=302)
    _set_session_cookie(response, raw_token)
    return response


@router.api_route("/logout", methods=["GET", "POST"])
async def logout(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Delete the Onyx session and clear the cookie (Microsoft session intact)."""
    raw_token = request.cookies.get(auth_service.SESSION_COOKIE_NAME)
    if raw_token:
        await auth_service.delete_session(session, raw_token)
        await session.commit()
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(auth_service.SESSION_COOKIE_NAME, path="/")
    return response
