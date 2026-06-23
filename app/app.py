from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

import config
from app.auth.admin_pages import router as admin_pages_router
from app.auth.middleware import AuthMiddleware
from app.auth.router import router as user_router
from app.auth.web_pages import router as auth_pages_router
from app.file.router import router as file_router
from app.project.router import router as project_router
from app.project.web_pages import router as project_pages_router
from app.vdi.revision.router import router as revision_router
from app.vdi.revision.web_pages import router as revision_pages_router
from app.vdi.router import router as vdi_router
from app.vdi.web_pages import router as vdi_pages_router

app = FastAPI(title="Onyx")

# Middleware runs outermost-first in reverse registration order. AuthMiddleware
# is registered last so it gates every request before anything else; the inner
# SessionMiddleware carries the short-lived OIDC handshake state for the public
# login/callback routes (ADR 0007).
app.add_middleware(
    SessionMiddleware,
    secret_key=config.session_secret,
    same_site="lax",
    https_only=config.cookie_secure,
)
app.add_middleware(AuthMiddleware)


@app.get("/healthz", tags=["health"])
async def healthz() -> dict[str, str]:
    """Public liveness probe — reachable without a session."""
    return {"status": "ok"}


app.include_router(user_router, prefix="/api")
app.include_router(project_router, prefix="/api")
app.include_router(vdi_router, prefix="/api")
app.include_router(revision_router, prefix="/api")
app.include_router(file_router, prefix="/api")

# HTML page routers are mounted at root (no /api prefix).
app.include_router(auth_pages_router)
app.include_router(admin_pages_router)
app.include_router(project_pages_router)
app.include_router(vdi_pages_router)
app.include_router(revision_pages_router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
