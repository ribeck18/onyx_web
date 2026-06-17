import enum


class ApprovalType(enum.Enum):
    """Whether a vendor data item requires buyer approval or is informational only."""

    MANDATORY_APPROVAL = "mandatory_approval"
    INFORMATION_ONLY = "information_only"
