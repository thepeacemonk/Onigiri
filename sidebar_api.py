"""
Sidebar API (Onigiri)

Usage:
    import Onigiri
    Onigiri.register_sidebar_action(
        entry_id="MyAddon.open_panel",
        label="My Panel",
        command="myaddon_open_panel",
        icon_svg="<svg ...>...</svg>",  # optional
    )

Notes:
- `entry_id` must be unique.
- External entries are archived by default and can be enabled in Settings.
- `command` is dispatched via `pycmd()`; handle it in `gui_hooks.webview_did_receive_js_message`.
- `icon_svg` is an optional inline SVG string used for the icon mask.
- XML headers and HTML comments are stripped from `icon_svg` before use.
"""

import html
import json
import re
import urllib.parse
from dataclasses import dataclass
from typing import Dict

from . import config


@dataclass(frozen=True)
class SidebarEntry:
    entry_id: str
    label: str
    command: str
    icon_class: str = "action-external-addon"
    icon_svg: str = ""


_registry: Dict[str, SidebarEntry] = {}


def register_sidebar_action(
    entry_id: str,
    label: str,
    command: str,
    icon_class: str = "action-external-addon",
    icon_svg: str = "",
) -> SidebarEntry:
    """
    Register a sidebar entry for the Onigiri deck browser sidebar.

    - entry_id must be globally unique (suggestion: "module.function" style).
    - label is shown in the sidebar layout editor.
    - command is the pycmd string to fire.
    """
    if not isinstance(entry_id, str) or not entry_id.strip():
        raise ValueError("entry_id must be a non-empty string")

    entry_id = entry_id.strip()
    label = (label or entry_id).strip()

    entry = SidebarEntry(
        entry_id=entry_id,
        label=label,
        command=command or "",
        icon_class=icon_class or "action-external-addon",
        icon_svg=icon_svg or "",
    )
    _registry[entry_id] = entry
    _ensure_layout_entry(entry)
    return entry


def get_sidebar_entries() -> Dict[str, SidebarEntry]:
    return dict(_registry)


def get_sidebar_labels() -> Dict[str, str]:
    return {entry_id: entry.label for entry_id, entry in _registry.items()}


def render_sidebar_entry(entry_id: str) -> str:
    entry = _registry.get(entry_id)
    if not entry:
        return ""

    safe_label = html.escape(entry.label)
    safe_class = html.escape(entry.icon_class or "action-external-addon")
    js_cmd = json.dumps(entry.command or "")
    icon_style = ""
    data_attr = ""
    if entry.icon_svg:
        icon_svg = entry.icon_svg.strip()
        icon_svg = re.sub(r"^\s*<\?xml[^>]*\?>", "", icon_svg)
        icon_svg = re.sub(r"<!--.*?-->", "", icon_svg, flags=re.S)
        icon_svg = icon_svg.strip()
        if icon_svg:
            data_uri = "data:image/svg+xml," + urllib.parse.quote(icon_svg)
            size_px = 14
            icon_style = (
                " style=\""
                f"width: {size_px}px; height: {size_px}px; display: inline-block; "
                "background-color: var(--icon-color); "
                f"mask: url('{data_uri}') no-repeat center / contain; "
                f"-webkit-mask: url('{data_uri}') no-repeat center / contain;\""
            )
            data_attr = " data-onigiri-icon=\"1\""

    return (
        f"<div class=\"menu-item {safe_class}\"{data_attr} onclick='pycmd({js_cmd})'>"
        f"<i class=\"icon\"{icon_style}></i><span>{safe_label}</span></div>"
    )


def _ensure_layout_entry(entry: SidebarEntry) -> None:
    try:
        conf = config.get_config()
        layout = conf.setdefault("sidebarButtonLayout", {"visible": [], "archived": []})
        visible = layout.setdefault("visible", [])
        archived = layout.setdefault("archived", [])

        if entry.entry_id in visible or entry.entry_id in archived:
            return

        archived.append(entry.entry_id)
        config.write_config(conf)
    except Exception as exc:
        print(f"Onigiri: Failed to persist sidebar entry {entry.entry_id}: {exc}")
