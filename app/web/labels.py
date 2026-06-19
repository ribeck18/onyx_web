"""Presentation maps for every domain enum shown in the UI.

This module is the single source of truth for human labels, badge strings, the
status color family (``ns``/``info``/``ok``/``bad``), and hero words. Templates
reach these through Jinja globals/filters registered in ``templating.py`` so a
raw enum value is never rendered to a user. The enum source files keep their
meanings minimal to avoid drift — the meaning lives here.
"""

from __future__ import annotations

from app.vdi.approval_type import ApprovalType
from app.vdi.submit_code import SubmitCode
from app.vdi.submit_status import SubmitStatus

# Status badge strings (exact, UPPERCASE) shown in tables, cards, and timelines.
STATUS_LABELS: dict[SubmitStatus, str] = {
    SubmitStatus.NOT_STARTED: "NOT STARTED",
    SubmitStatus.SUBMITTED: "SUBMITTED",
    SubmitStatus.A: "APPROVED /A",
    SubmitStatus.D: "APPROVED /D",
    SubmitStatus.B: "REJECTED /B",
    SubmitStatus.C: "REJECTED /C",
}

# Status → color family. Badges, dots, hero, timeline, and the lifecycle button
# all paint from the token group named here (e.g. --ok, --ok-text, --ok-line).
STATUS_FAMILIES: dict[SubmitStatus, str] = {
    SubmitStatus.NOT_STARTED: "ns",
    SubmitStatus.SUBMITTED: "info",
    SubmitStatus.A: "ok",
    SubmitStatus.D: "ok",
    SubmitStatus.B: "bad",
    SubmitStatus.C: "bad",
}

# The single status word for the VDI hero treatment (sentence case).
STATUS_HERO_WORDS: dict[SubmitStatus, str] = {
    SubmitStatus.NOT_STARTED: "Not started",
    SubmitStatus.SUBMITTED: "Submitted",
    SubmitStatus.A: "Approved",
    SubmitStatus.D: "Approved",
    SubmitStatus.B: "Rejected",
    SubmitStatus.C: "Rejected",
}

APPROVAL_TYPE_LABELS: dict[ApprovalType, str] = {
    ApprovalType.MANDATORY_APPROVAL: "Mandatory Approval",
    ApprovalType.INFORMATION_ONLY: "Information Only",
}

# Submit code → full meaning. The compact table column shows the short code with
# this meaning on hover.
SUBMIT_CODE_LABELS: dict[SubmitCode, str] = {
    SubmitCode.AC: "As Completed",
    SubmitCode.AFI: "At Final Inspection",
    SubmitCode.ARO: "After Receipt of Order",
    SubmitCode.AT: "After Test",
    SubmitCode.BC: "Before Contract Awarded",
    SubmitCode.BFA: "Before Final Acceptance",
    SubmitCode.BFS: "Before Fabrication Start",
    SubmitCode.PDS: "Prior to Delivery on Site",
    SubmitCode.PS: "Prior to Shipment",
    SubmitCode.PT: "Prior to Test",
    SubmitCode.PTC: "Prior to Construction",
    SubmitCode.PTI: "Prior to Installation",
    SubmitCode.PTP: "Prior to Purchase",
    SubmitCode.PTW: "Prior to Welding",
    SubmitCode.ROS: "Prior to Removal Off-Site",
    SubmitCode.TS: "Time of Shipment",
}


def status_label(status: SubmitStatus) -> str:
    """Return the UPPERCASE badge string for a submit status."""
    return STATUS_LABELS[status]


def status_family(status: SubmitStatus) -> str:
    """Return the color-family key (ns/info/ok/bad) for a submit status."""
    return STATUS_FAMILIES[status]


def status_hero_word(status: SubmitStatus) -> str:
    """Return the sentence-case hero word for a submit status."""
    return STATUS_HERO_WORDS[status]


def approval_type_label(approval_type: ApprovalType) -> str:
    """Return the human label for an approval type."""
    return APPROVAL_TYPE_LABELS[approval_type]


def submit_code_label(submit_code: SubmitCode) -> str:
    """Return the full meaning for a submit code."""
    return SUBMIT_CODE_LABELS[submit_code]


def submit_code_short(submit_code: SubmitCode) -> str:
    """Return the compact UPPERCASE code shown in the narrow table column."""
    return submit_code.value.upper()
