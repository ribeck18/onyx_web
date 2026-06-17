from fastapi import FastAPI

from app.project.router import router as project_router

app = FastAPI(title="Onyx")

app.include_router(project_router)
