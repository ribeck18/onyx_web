import enum


class SubmitCode(enum.Enum):
    """When a submittal is due relative to the project timeline."""

    AC = "ac"  # As Completed
    AFI = "afi"  # At Final Inspection
    ARO = "aro"  # After Receipt of Order
    AT = "at"  # After Test
    BC = "bc"  # Before Contract Awarded
    BFA = "bfa"  # Before Final Acceptance
    BFS = "bfs"  # Before Fabrication Start
    PDS = "pds"  # Prior to Delivery on Site
    PS = "ps"  # Prior to Shipment
    PT = "pt"  # Prior to Test
    PTC = "ptc"  # Prior to Construction
    PTI = "pti"  # Prior to Installation
    PTP = "ptp"  # Prior to Purchase
    PTW = "ptw"  # Prior to Welding
    ROS = "ros"  # Prior to Removal Off-Site
    TS = "ts"  # Time of Shipment
