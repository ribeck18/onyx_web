"""Import all models so the SQLAlchemy mapper configures with every class registered."""

from app.models.project import Project
from app.models.vdi import VendorDataItem
from app.models.revision import Revision
from app.models.project_doc import ProjectDoc
from app.models.doc_version import DocVersion
from app.models.file import File
from app.models.user import User
from app.models.session import Session
from app.models.api_token import ApiToken

__all__ = [
    "Project",
    "VendorDataItem",
    "Revision",
    "ProjectDoc",
    "DocVersion",
    "File",
    "User",
    "Session",
    "ApiToken",
]
