import enum


class RfiStatus(enum.Enum):
    """Current lifecycle state of a Request for Information."""

    NOT_STARTED = "not_started"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
