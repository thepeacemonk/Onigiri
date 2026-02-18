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

import base64
import html
import json
import os
import re
import urllib.parse
from dataclasses import dataclass
from typing import Dict, Optional

import datetime

from . import config

import_time_str = datetime.datetime.now().strftime("%H:%M:%S")


@dataclass(frozen=True)
class SidebarEntry:
    entry_id: str
    label: str
    command: str
    icon_class: str = "action-external-addon"
    icon_svg: str = ""
    render_html: str = ""


_registry: Dict[str, SidebarEntry] = {}
_toolbar_entry_ids = set()
_toolbar_cmds = set()
_TOOLBAR_ENTRY_PREFIX = "toolbar."
_TOOLBAR_CMD_BLACKLIST = {
    "decks",
    "add",
    "browse",
    "stats",
    "sync",
}


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


def register_sidebar_html(
    entry_id: str,
    label: str,
    render_html: str,
) -> SidebarEntry:
    """
    Register a sidebar entry with raw HTML.
    """
    if not isinstance(entry_id, str) or not entry_id.strip():
        raise ValueError("entry_id must be a non-empty string")

    entry_id = entry_id.strip()
    label = (label or entry_id).strip()

    entry = SidebarEntry(
        entry_id=entry_id,
        label=label,
        command="",
        icon_class="action-external-addon",
        icon_svg="",
        render_html=render_html or "",
    )
    _registry[entry_id] = entry
    _ensure_layout_entry(entry)
    return entry


def get_sidebar_entries() -> Dict[str, SidebarEntry]:
    return dict(_registry)


def _get_label_overrides(conf: Optional[dict] = None) -> Dict[str, str]:
    try:
        if conf is None:
            conf = config.get_config()
        layout = conf.get("sidebarButtonLayout", {}) if isinstance(conf, dict) else {}
        labels = layout.get("labels", {})
        return labels if isinstance(labels, dict) else {}
    except Exception:
        return {}


def get_sidebar_labels(include_overrides: bool = True) -> Dict[str, str]:
    labels = {entry_id: entry.label for entry_id, entry in _registry.items()}
    if not include_overrides:
        return labels
    overrides = _get_label_overrides()
    for entry_id, label in overrides.items():
        if entry_id in labels and isinstance(label, str) and label.strip():
            labels[entry_id] = label.strip()
    return labels


def render_sidebar_entry(entry_id: str) -> str:
    entry = _registry.get(entry_id)
    if not entry:
        return ""
    if entry.render_html:
        return entry.render_html

    label_override = _get_label_overrides().get(entry.entry_id)
    label_text = label_override.strip() if isinstance(label_override, str) and label_override.strip() else entry.label
    safe_label = html.escape(label_text)
    safe_class = html.escape(entry.icon_class or "action-external-addon")
    js_cmd = json.dumps(entry.command or "")
    icon_style = ""
    data_attr = ""
    icon_override = _load_icon_override(entry.entry_id)
    icon_source = icon_override or entry.icon_svg
    icon_kind = _icon_kind(icon_source)
    if icon_source:
        icon_svg = icon_source.strip()
        icon_svg = re.sub(r"^\s*<\?xml[^>]*\?>", "", icon_svg)
        icon_svg = re.sub(r"<!--.*?-->", "", icon_svg, flags=re.S)
        icon_svg = icon_svg.strip()
        if icon_svg:
            if icon_kind == "image":
                # Raster mask (PNG data URI): use it as a CSS mask so icons follow theme color.
                data_uri = icon_svg
                size_px = 14
                icon_style = (
                    " style=\""
                    f"width: {size_px}px; height: {size_px}px; display: inline-block; "
                    "background-color: var(--icon-color); "
                    f"mask: url('{data_uri}') no-repeat center / contain; "
                    f"-webkit-mask: url('{data_uri}') no-repeat center / contain;\""
                )
                data_attr = " data-onigiri-icon=\"1\""
            else:
                # SVG mask: inline SVG is turned into a data URI and used as a CSS mask.
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


def _load_icon_override(entry_id: str) -> str:
    try:
        from aqt import mw
        filename = mw.col.conf.get(f"modern_menu_icon_{entry_id}", "")
    except Exception:
        return ""

    if not filename:
        return ""

    icon_path = os.path.join(os.path.dirname(__file__), "user_files", "icons", filename)
    if not os.path.exists(icon_path):
        return ""

    try:
        with open(icon_path, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except Exception:
        return ""


def _extract_attr(html_str: str, attr: str) -> str:
    match = re.search(
        rf"{re.escape(attr)}\s*=\s*(\"([^\"]*)\"|'([^']*)')",
        html_str,
        flags=re.I,
    )
    if not match:
        return ""
    return match.group(2) or match.group(3) or ""


def _extract_pycmd(html_str: str) -> Optional[str]:
    match = re.search(r"pycmd\(['\"]([^'\"]+)['\"]\)", html_str)
    if not match:
        return None
    return match.group(1).strip()


def _label_from_html(html_str: str, fallback: str) -> str:
    label = _extract_attr(html_str, "aria-label") or _extract_attr(html_str, "title")
    if not label:
        text = re.sub(r"<[^>]+>", " ", html_str)
        label = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return label or fallback


def _extract_inline_svg(html_str: str) -> str:
    match = re.search(r"<svg\b[^>]*>.*?</svg>", html_str, flags=re.I | re.S)
    if match:
        return match.group(0).strip()
    return ""


def _extract_first_img_src(html_str: str) -> str:
    for match in re.finditer(r"<img\b[^>]*>", html_str, flags=re.I):
        src = _extract_attr(match.group(0), "src")
        if src:
            return src
    return ""


def _extract_url_from_style(style_str: str) -> str:
    match = re.search(r"url\(([^)]+)\)", style_str, flags=re.I)
    if not match:
        return ""
    url = match.group(1).strip().strip("\"'")
    return url


def _extract_first_style_url(html_str: str) -> str:
    style_attr = _extract_attr(html_str, "style")
    if style_attr:
        url = _extract_url_from_style(style_attr)
        if url:
            return url
    match = re.search(r"url\(([^)]+)\)", html_str, flags=re.I)
    if match:
        return match.group(1).strip().strip("\"'")
    return ""


def _svg_from_data_uri(data_uri: str) -> str:
    # Parse the data URI into header + payload to decide how to decode.
    try:
        header, data = data_uri.split(",", 1)
    except ValueError:
        return ""

    # Check if the payload is base64 or URL-encoded.
    is_base64 = ";base64" in header
    media_type = header.split(":", 1)[1].split(";", 1)[0] if ":" in header else ""

    # Decode the raw bytes from the data URI.
    if is_base64:
        try:
            raw = base64.b64decode(data)
        except Exception:
            return ""
    else:
        raw = urllib.parse.unquote_to_bytes(data)

    # If this is already SVG, return the SVG markup directly.
    if media_type == "image/svg+xml":
        try:
            return raw.decode("utf-8", errors="ignore").strip()
        except Exception:
            return ""

    # For raster images, convert them into a luminance mask PNG data URI.
    mask_uri = _raster_to_luminance_mask_data_uri(raw)
    if mask_uri:
        return mask_uri

    # Fallback: keep the original raster data as-is.
    b64 = base64.b64encode(raw).decode("ascii")
    normalized_type = media_type or "image/png"
    return f"data:{normalized_type};base64,{b64}"


def _svg_from_file(path: str) -> str:
    # Branch by file extension so SVGs can be returned as markup.
    ext = os.path.splitext(path)[1].lower()
    if ext == ".svg":
        try:
            with open(path, "r", encoding="utf-8") as handle:
                return handle.read().strip()
        except Exception:
            return ""

    # For raster images, read bytes and convert to a luminance mask PNG.
    if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        try:
            with open(path, "rb") as handle:
                raw = handle.read()
        except Exception:
            return ""
        mask_uri = _raster_to_luminance_mask_data_uri(raw)
        if mask_uri:
            return mask_uri

        # Fallback: keep the original raster data as-is.
        b64 = base64.b64encode(raw).decode("ascii")
        media_type = "image/png"
        if ext in {".jpg", ".jpeg"}:
            media_type = "image/jpeg"
        elif ext == ".webp":
            media_type = "image/webp"
        elif ext == ".gif":
            media_type = "image/gif"
        return f"data:{media_type};base64,{b64}"

    return ""


def _resolve_addon_path(url: str) -> str:
    if not url.startswith("/_addons/"):
        return ""
    parts = url.split("/")
    if len(parts) < 4:
        return ""
    addon_id = parts[2]
    rel_path = "/".join(parts[3:])
    rel_path = rel_path.split("?", 1)[0].split("#", 1)[0]
    try:
        from aqt import mw
        base = mw.addonManager.addonsFolder()
    except Exception:
        return ""
    return os.path.join(base, addon_id, rel_path)


def _extract_icon_svg_from_html(html_str: str) -> str:
    svg = _extract_inline_svg(html_str)
    if svg:
        return svg

    src = _extract_first_img_src(html_str)
    if not src:
        src = _extract_first_style_url(html_str)

    if not src:
        return ""

    if src.startswith("data:"):
        return _svg_from_data_uri(src)

    path = _resolve_addon_path(src)
    if path:
        return _svg_from_file(path)

    return ""


def _icon_kind(icon_value: str) -> str:
    # Determine how the icon should be rendered (SVG mask vs raster mask).
    if not icon_value:
        return ""
    stripped = icon_value.lstrip()
    if stripped.startswith("<svg"):
        return "svg"
    if stripped.startswith("data:image/svg+xml"):
        return "svg"
    if stripped.startswith("data:image/"):
        return "image"
    return ""


def _raster_to_luminance_mask_data_uri(raw: bytes) -> str:
    """
    Convert raster bytes into a PNG data URI where pixel luminance becomes alpha.

    - The output is a white image with alpha representing brightness.
    - We auto-detect if inversion is needed using corner luminance.
    - Original alpha (if present) is preserved by multiplying with luminance alpha.
    """
    # Import Qt lazily so this module still loads in non-GUI contexts.
    try:
        from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt
        from PyQt6.QtGui import QImage, QColor
    except Exception:
        try:
            from PyQt5.QtCore import QBuffer, QByteArray, QIODevice, Qt
            from PyQt5.QtGui import QImage, QColor
        except Exception:
            return ""

    # Decode bytes into a QImage so we can inspect per-pixel color.
    image = QImage.fromData(raw)
    if image.isNull():
        return ""

    # Normalize to ARGB so we can read and write alpha reliably (PyQt5/6 compatible).
    format_argb32 = getattr(QImage, "Format_ARGB32", None)
    if format_argb32 is None:
        format_argb32 = QImage.Format.Format_ARGB32
    image = image.convertToFormat(format_argb32)
    # Resolve Qt enum values in a PyQt5/6 compatible way (avoids AttributeError).
    aspect_mode = getattr(Qt, "KeepAspectRatio", None)
    if aspect_mode is None and hasattr(Qt, "AspectRatioMode"):
        aspect_mode = Qt.AspectRatioMode.KeepAspectRatio
    transform_mode = getattr(Qt, "SmoothTransformation", None)
    if transform_mode is None and hasattr(Qt, "TransformationMode"):
        transform_mode = Qt.TransformationMode.SmoothTransformation

    # Optional: upscale for smoother edges (only if enums are available).
    if aspect_mode is not None and transform_mode is not None:
        target = 64
        image = image.scaled(
            target, target,
            aspect_mode,
            transform_mode
        )
    # Helper to compute luminance from an RGB triple.
    def _luminance(color: QColor) -> int:
        return int(0.2126 * color.red() + 0.7152 * color.green() + 0.0722 * color.blue())

    # Sample the corners to guess if the background is light (white-ish).
    # If it's light, we invert so the background becomes transparent.
    w = image.width() - 1
    h = image.height() - 1
    corners = [
        QColor(image.pixel(0, 0)),
        QColor(image.pixel(w, 0)),
        QColor(image.pixel(0, h)),
        QColor(image.pixel(w, h)),
    ]
    corner_avg = sum(_luminance(c) for c in corners) / 4.0
    invert = corner_avg > 180

    # Convert each pixel: luminance -> alpha; preserve original alpha too.
    for y in range(image.height()):
        for x in range(image.width()):
            c = QColor(image.pixel(x, y))
            lum = _luminance(c)
            alpha = 255 - lum if invert else lum
            # When we are NOT inverting, boost low luminance so mid/dark colors stay visible.
            if not invert and alpha > 0:
                alpha = max(alpha, 64)
            if c.alpha() < 255:
                alpha = int(alpha * (c.alpha() / 255.0))
            image.setPixelColor(x, y, QColor(255, 255, 255, alpha))

    # Encode the result as PNG and return a data URI.
    buffer = QByteArray()
    qbuf = QBuffer(buffer)
    # Open the buffer for writing (PyQt5/6 compatible).
    open_mode = getattr(QBuffer, "WriteOnly", None)
    if open_mode is None:
        open_mode_enum = getattr(QBuffer, "OpenModeFlag", None)
        if open_mode_enum is not None:
            open_mode = open_mode_enum.WriteOnly
        else:
            open_mode = getattr(QIODevice, "WriteOnly", None)
            if open_mode is None:
                open_mode = QIODevice.OpenModeFlag.WriteOnly
    qbuf.open(open_mode)
    image.save(qbuf, "PNG")
    return f"data:image/png;base64,{base64.b64encode(bytes(buffer)).decode('ascii')}"


def _reset_toolbar_entries() -> None:
    if not _toolbar_entry_ids:
        return
    for entry_id in list(_toolbar_entry_ids):
        _registry.pop(entry_id, None)
    _toolbar_entry_ids.clear()
    _toolbar_cmds.clear()


def _capture_toolbar_links(links, _toolbar) -> None:
    try:
        # Debug logging
        log_path = os.path.join(os.path.dirname(__file__), "sidebar_debug.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"--- Capture Hook Run at {import_time_str} ---\n")
            f.write(f"Links count: {len(links)}\n")
            for i, link in enumerate(links):
                f.write(f"Link {i}: {link}\n")

        _reset_toolbar_entries()
        for link_html in links:
            cmd = _extract_pycmd(link_html or "")
            if not cmd:
                continue
            if cmd in _TOOLBAR_CMD_BLACKLIST:
                continue
            entry_id = f"{_TOOLBAR_ENTRY_PREFIX}{cmd}"
            label = _label_from_html(link_html, cmd)
            icon_svg = _extract_icon_svg_from_html(link_html or "")
            
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"  -> Captured: {entry_id} ({label})\n")

            register_sidebar_action(
                entry_id=entry_id,
                label=label,
                command=cmd,
                icon_svg=icon_svg,
            )
            _toolbar_entry_ids.add(entry_id)
            _toolbar_cmds.add(cmd)
    except Exception as exc:
        print(f"Onigiri: Failed to capture toolbar links: {exc}")
        try:
            log_path = os.path.join(os.path.dirname(__file__), "sidebar_debug.log")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"ERROR: {exc}\n")
        except:
            pass


def _dispatch_toolbar_cmd(handled, message, context):
    if message not in _toolbar_cmds:
        return handled
    try:
        from aqt import mw
        handler = getattr(getattr(mw, "toolbar", None), "link_handlers", {}).get(message)
        if handler:
            handler()
            return (True, None)
    except Exception as exc:
        print(f"Onigiri: Toolbar cmd failed ({message}): {exc}")
        return (True, None)
    return handled


def _install_toolbar_bridge() -> None:
    if getattr(_install_toolbar_bridge, "_installed", False):
        return
    _install_toolbar_bridge._installed = True
    try:
        from aqt import gui_hooks
        gui_hooks.top_toolbar_did_init_links.append(_capture_toolbar_links)
        gui_hooks.webview_did_receive_js_message.append(_dispatch_toolbar_cmd)
    except Exception as exc:
        print(f"Onigiri: Failed to install toolbar bridge: {exc}")


def ensure_capture_hook_is_last() -> None:
    """
    Ensures that our capture hook runs LAST, after all other add-ons have added their links.
    """
    try:
        from aqt import gui_hooks
        if _capture_toolbar_links in gui_hooks.top_toolbar_did_init_links:
            gui_hooks.top_toolbar_did_init_links.remove(_capture_toolbar_links)
            gui_hooks.top_toolbar_did_init_links.append(_capture_toolbar_links)
    except Exception as exc:
        print(f"Onigiri: Failed to reorder toolbar hook: {exc}")


_install_toolbar_bridge()

