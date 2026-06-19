from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.file.router import router as file_router
from app.project.router import router as project_router
from app.project.web_pages import router as project_pages_router
from app.vdi.revision.router import router as revision_router
from app.vdi.revision.web_pages import router as revision_pages_router
from app.vdi.router import router as vdi_router
from app.vdi.web_pages import router as vdi_pages_router

app = FastAPI(title="Onyx")

app.include_router(project_router, prefix="/api")
app.include_router(vdi_router, prefix="/api")
app.include_router(revision_router, prefix="/api")
app.include_router(file_router, prefix="/api")

# HTML page routers are mounted at root (no /api prefix).
app.include_router(project_pages_router)
app.include_router(vdi_pages_router)
app.include_router(revision_pages_router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
