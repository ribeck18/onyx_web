"""The single Jinja2 environment for every server-rendered page.

All page routes render through ``render()`` so the current theme (from the
``theme`` cookie, default dark) is injected server-side and there is no flash of
the wrong theme on load. Enum presentation helpers from ``labels.py`` are
registered here as globals and filters so no template ever shows a raw enum.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.web import file_preview, labels

# Templates live at app/templates; this file is app/web/templating.py.
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

VALID_THEMES = ("dark", "light")
DEFAULT_THEME = "dark"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Expose the label maps and accessors to every template. Filters let templates
# write `vdi.status | status_label`; globals expose the raw maps when needed.
templates.env.filters["status_label"] = labels.status_label
templates.env.filters["status_family"] = labels.status_family
templates.env.filters["status_hero_word"] = labels.status_hero_word
templates.env.filters["approval_type_label"] = labels.approval_type_label
templates.env.filters["submit_code_label"] = labels.submit_code_label
templates.env.filters["submit_code_short"] = labels.submit_code_short
templates.env.filters["preview_kind"] = file_preview.preview_kind
templates.env.filters["file_extension"] = file_preview.file_extension

# The full enum→label maps power the modal selects (rendered server-side so the
# labels are never duplicated in JS). Keyed by enum member, valued by human label.
templates.env.globals["approval_type_options"] = labels.APPROVAL_TYPE_LABELS
templates.env.globals["submit_code_options"] = labels.SUBMIT_CODE_LABELS


def resolve_theme(request: Request) -> str:
    """Return the theme from the request cookie, defaulting to dark.

    An unrecognized cookie value falls back to the default so a stale or tampered
    cookie can never render a broken theme.
    """
    theme = request.cookies.get("theme", DEFAULT_THEME)
    return theme if theme in VALID_THEMES else DEFAULT_THEME


def render(request: Request, template_name: str, context: dict[str, Any] | None = None):
    """Render a template with the resolved theme injected into the context."""
    full_context = dict(context or {})
    full_context["theme"] = resolve_theme(request)
    return templates.TemplateResponse(request, template_name, full_context)
