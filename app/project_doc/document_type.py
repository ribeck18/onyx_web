import enum


class DocumentType(enum.Enum):
    """What kind of project document this is (see labels.py for display names)."""

    DRAWING = "drawing"
    SPECIFICATION = "specification"
    SPECIAL_CONDITION = "special_condition"
    CONTRACT = "contract"
    VENDOR_DATA_SCHEDULE = "vendor_data_schedule"
    ADDENDUM = "addendum"
