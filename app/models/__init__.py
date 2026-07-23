"""Import all models so the SQLAlchemy mapper configures with every class registered."""

from app.models.project import Project
from app.models.vdi import VendorDataItem
from app.models.revision import Revision
from app.models.project_doc import ProjectDoc
from app.models.library_document import LibraryDocument
from app.models.library_document_version import LibraryDocumentVersion
from app.models.rfi import Rfi
from app.models.rfi_revision import RfiRevision
from app.models.doc_version import DocVersion
from app.models.file import File
from app.models.jsa import JSA
from app.models.jsa_file import JsaFile
from app.models.jsa_revision import JsaRevision
from app.models.user import User
from app.models.session import Session
from app.models.api_token import ApiToken

__all__ = [
    "Project",
    "VendorDataItem",
    "Revision",
    "ProjectDoc",
    "LibraryDocument",
    "LibraryDocumentVersion",
    "Rfi",
    "RfiRevision",
    "DocVersion",
    "File",
    "JSA",
    "JsaFile",
    "JsaRevision",
    "User",
    "Session",
    "ApiToken",
]
