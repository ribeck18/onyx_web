"""Import all models so the SQLAlchemy mapper configures with every class registered."""

from app.models.project import Project
from app.models.vdi import VendorDataItem
from app.models.revision import Revision
from app.models.file import File

__all__ = ["Project", "VendorDataItem", "Revision", "File"]
