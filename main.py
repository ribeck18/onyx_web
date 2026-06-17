from fastapi import FastAPI

from app.project.router import router as project_router
from app.vdi.revision.router import router as revision_router
from app.vdi.router import router as vdi_router

app = FastAPI(title="Onyx")

app.include_router(project_router)
app.include_router(vdi_router)
app.include_router(revision_router)
