import enum


class SubmitStatus(enum.Enum):
    """Current state of a vendor data item / revision submittal.

    A and D are approved outcomes; B and C are rejected and require resubmittal.
    """

    NOT_STARTED = "not_started"
    SUBMITTED = "submitted"
    A = "a"  # approved
    B = "b"  # rejected, resubmit
    C = "c"  # rejected, resubmit
    D = "d"  # approved
