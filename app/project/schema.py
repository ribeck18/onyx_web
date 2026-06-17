from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    project_number: str
    name: str
    description: str | None = None


class ProjectUpdate(BaseModel):
    project_number: str | None = None
    name: str | None = None
    description: str | None = None


class ProjectRead(BaseModel):
    id: int
    project_number: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
