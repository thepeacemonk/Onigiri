"""Reviewer top dock modes: Static (default), Minimal (icon-only), and Island (Rubber Dock)."""

from __future__ import annotations

import base64
import html
import json
import os
import re
from pathlib import Path
from typing import Any

try:
    from aqt import mw
except Exception:  # pragma: no cover
    mw = None

from ..core import config
from ..core.translations import tr as tr_at

_ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ADDON_PATH = Path(_ADDON_ROOT)

VALID_DOCK_MODES = ("static", "minimal", "island")
_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
DEFAULT_DOCK_ICONS: dict[str, str] = {
    "decks": "system:deck.svg",
    "add": "system:add.svg",
    "browse": "system:browse.svg",
    "stats": "system:stats.svg",
    "sync": "system:sync.svg",
    "hashi_notes": "system:hashi_notes.svg",
    "pomodoro": "system:pomodoro.svg",
}
DEFAULT_ICON_COLOR_LIGHT = "#17181a"
DEFAULT_ICON_COLOR_DARK = "#ffffff"
DEFAULT_GOO_COLOR_LIGHT = "#17181a"
DEFAULT_GOO_COLOR_DARK = "#ffffff"

_cached_css_mtime: int | None = None
_cached_css_text: str = ""
_icon_data_cache: dict[tuple[str, int], str] = {}

_DOCK_ICONS = {
    "decks": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.85" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="m12 3 8 4.5-8 4.5L4 7.5 12 3Z"/>'
        '<path d="m4 12 8 4.5 8-4.5"/>'
        '<path d="m4 16.5 8 4.5 8-4.5"/>'
        "</svg>"
    ),
    "add": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.85" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<rect x="4" y="4" width="16" height="16" rx="4"/>'
        '<path d="M12 8v8M8 12h8"/>'
        "</svg>"
    ),
    "browse": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.85" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<circle cx="11" cy="11" r="6.5"/>'
        '<path d="m20 20-4.2-4.2"/>'
        "</svg>"
    ),
    "stats": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.85" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M5 19v-5"/>'
        '<path d="M12 19V5"/>'
        '<path d="M19 19v-9"/>'
        "</svg>"
    ),
    "sync": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.85" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M21 12a9 9 0 0 0-15.5-6.3L3 8"/>'
        '<path d="M3 3v5h5"/>'
        '<path d="M3 12a9 9 0 0 0 15.5 6.3L21 16"/>'
        '<path d="M16 16h5v5"/>'
        "</svg>"
    ),
    "hashi_notes": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.85" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M15 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/>'
        '<path d="M14 3v5h5"/>'
        '<path d="M8 13h8"/>'
        '<path d="M8 17h5"/>'
        "</svg>"
    ),
    "pomodoro": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.85" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<circle cx="12" cy="13" r="8"/>'
        '<path d="M12 9v4l2.5 2"/>'
        '<path d="M9 2h6"/>'
        "</svg>"
    ),
}


def dock_mode(conf: dict[str, Any] | None = None) -> str:
    """Return normalized reviewer dock mode: 'static', 'minimal', or 'island'."""
    if conf is None:
        conf = config.get_config_readonly()
    raw = str((conf or {}).get("onigiri_reviewer_dock_mode", "static") or "static").strip().lower()
    return raw if raw in VALID_DOCK_MODES else "static"


def _read_dock_css_text() -> str:
    global _cached_css_mtime, _cached_css_text
    css_path = os.path.join(_ADDON_ROOT, "web", "reviewer_dock.css")
    try:
        mtime = os.stat(css_path).st_mtime_ns
        if _cached_css_mtime != mtime:
            with open(css_path, "r", encoding="utf-8") as handle:
                _cached_css_text = handle.read()
            _cached_css_mtime = mtime
    except OSError:
        return ""
    return _cached_css_text


def _dock_action_items(conf: dict[str, Any]) -> list[dict[str, str]]:
    from ..core.study_tool_visibility import reviewer_button_visible

    items = [
        {"id": "decks", "cmd": "decks", "label": tr_at("decks"), "extra_cls": ""},
        {"id": "add", "cmd": "add", "label": tr_at("add"), "extra_cls": ""},
        {"id": "browse", "cmd": "browse", "label": tr_at("browse"), "extra_cls": ""},
        {"id": "stats", "cmd": "stats", "label": tr_at("stats"), "extra_cls": ""},
        {"id": "sync", "cmd": "sync", "label": tr_at("sync"), "extra_cls": ""},
    ]
    if reviewer_button_visible("hashi_notes", conf):
        items.append(
            {
                "id": "hashi_notes",
                "cmd": "openHashiNotes:reviewer",
                "label": tr_at("hashi_notes_title"),
                "extra_cls": "onigiri-hashi-notes-button",
            }
        )
    if reviewer_button_visible("pomodoro", conf):
        items.append(
            {
                "id": "pomodoro",
                "cmd": "togglePomodoro",
                "label": tr_at("pomodoro_title"),
                "extra_cls": "onigiri-pomodoro-button",
            }
        )
    return items


def _normalize_hex_color(value: Any, fallback: str) -> str:
    raw = str(value or "").strip()
    if not _HEX_COLOR_RE.match(raw):
        return fallback
    if len(raw) == 4:
        return "#" + "".join(ch * 2 for ch in raw[1:]).lower()
    return raw.lower()


def _contrast_ink(hex_color: str) -> str:
    normalized = _normalize_hex_color(hex_color, DEFAULT_GOO_COLOR_LIGHT)
    c = normalized[1:]
    r, g, b = int(c[0:2], 16) / 255.0, int(c[2:4], 16) / 255.0, int(c[4:6], 16) / 255.0

    def _linear(channel: float) -> float:
        return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4

    lum = 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)
    return "#0e0f11" if lum > 0.36 else "#ffffff"


def _resolve_icon_file(value: str) -> Path | None:
    if not value or value.startswith("emoji:"):
        return None
    is_system = value.startswith("system:")
    name = value[len("system:") :] if is_system else value
    if not name or Path(name).name != name or "\\" in name or "/" in name:
        return None
    if Path(name).suffix.lower() not in (".svg", ".png"):
        return None
    system_folders = (
        "system_files/system_icons/available_for_users",
        "system_files/system_icons/unavailable_for_users",
        "system_files/system_icons",
    )
    search_folders = system_folders if is_system else ("user_files/icons", "user_files/custom_deck_icons", *system_folders)
    for folder in search_folders:
        candidate = _ADDON_PATH / folder / name
        if candidate.is_file():
            return candidate
    return None


def _icon_data_uri(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    try:
        mtime = path.stat().st_mtime_ns
        cache_key = (str(path), mtime)
        cached = _icon_data_cache.get(cache_key)
        if cached is not None:
            return cached
        mime = "image/png" if path.suffix.lower() == ".png" else "image/svg+xml"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        uri = f"data:{mime};base64,{encoded}"
        _icon_data_cache[cache_key] = uri
        return uri
    except OSError:
        return ""


def _dock_icon_html(item_id: str, conf: dict[str, Any]) -> str:
    icons = conf.get("onigiri_reviewer_dock_icons")
    raw = icons.get(item_id, "") if isinstance(icons, dict) else ""
    raw = str(raw or "").strip() or DEFAULT_DOCK_ICONS.get(item_id, "")
    if raw.startswith("emoji:") and raw[len("emoji:") :].strip():
        emoji = html.escape(raw[len("emoji:") :].strip())
        return f'<span class="onigiri-dock-glyph is-emoji" aria-hidden="true">{emoji}</span>'
    path = _resolve_icon_file(raw)
    if path is None:
        default_raw = DEFAULT_DOCK_ICONS.get(item_id, "")
        if default_raw and default_raw != raw:
            path = _resolve_icon_file(default_raw)
    uri = _icon_data_uri(path)
    if uri:
        return (
            '<span class="onigiri-dock-glyph" '
            f'style="-webkit-mask-image: url(\'{uri}\'); mask-image: url(\'{uri}\');" '
            'aria-hidden="true"></span>'
        )
    return _DOCK_ICONS.get(item_id, "")


def resolve_icon_colors(item_id: str, conf: dict[str, Any]) -> tuple[str, str]:
    light_map = conf.get("onigiri_reviewer_dock_icon_colors_light")
    dark_map = conf.get("onigiri_reviewer_dock_icon_colors_dark")
    raw_light = light_map.get(item_id) if isinstance(light_map, dict) else None
    raw_dark = dark_map.get(item_id) if isinstance(dark_map, dict) else None
    return (
        _normalize_hex_color(raw_light, DEFAULT_ICON_COLOR_LIGHT),
        _normalize_hex_color(raw_dark, DEFAULT_ICON_COLOR_DARK),
    )


def resolve_goo_palette(conf: dict[str, Any]) -> dict[str, str]:
    theme_mode = str(conf.get("onigiri_web_rdock_goo_theme_mode", "separate") or "separate").strip().lower()
    goo_light = _normalize_hex_color(conf.get("onigiri_reviewer_dock_goo_color_light"), DEFAULT_GOO_COLOR_LIGHT)
    if theme_mode == "single":
        goo_dark = goo_light
    else:
        goo_dark = _normalize_hex_color(conf.get("onigiri_reviewer_dock_goo_color_dark"), DEFAULT_GOO_COLOR_DARK)
    return {
        "goo_light": goo_light,
        "goo_dark": goo_dark,
        "ink_light": _contrast_ink(goo_light),
        "ink_dark": _contrast_ink(goo_dark),
    }


def _render_icon_buttons(items: list[dict[str, str]], base_cls: str, conf: dict[str, Any]) -> str:
    parts = []
    for item in items:
        label = html.escape(str(item["label"]), quote=True)
        cmd = item["cmd"]
        cls = f"{base_cls} {item['extra_cls']}".strip()
        icon_html = _dock_icon_html(item["id"], conf)
        color_light, color_dark = resolve_icon_colors(item["id"], conf)
        style_attr = (
            f"--rd-icon-color-light: {color_light}; "
            f"--rd-icon-color-dark: {color_dark};"
        )
        parts.append(
            f'<a href="#" onclick="pycmd(\'{cmd}\'); return false;" '
            f'class="{cls}" data-dock-id="{html.escape(item["id"], quote=True)}" '
            f'style="{style_attr}" aria-label="{label}" data-tip="{label}">{icon_html}</a>'
        )
    return "\n".join(parts)


def _header_info_parts(conf: dict[str, Any], include_overview_class: bool) -> dict[str, str]:
    from . import patcher

    restaurant_conf = conf.get("restaurant_level", {})
    if not restaurant_conf:
        restaurant_conf = conf.get("achievements", {}).get("restaurant_level", {})
    restaurant_chip_html = ""
    if (
        not include_overview_class
        and restaurant_conf.get("enabled", False)
        and restaurant_conf.get("show_reviewer_header", False)
    ):
        restaurant_chip_html = patcher._get_reviewer_nook_level_chip_html()

    progress_settings = patcher._reviewer_progress_settings(
        conf, force=not include_overview_class
    )
    progress_html = ""
    if not include_overview_class and progress_settings["enabled"]:
        patcher.reset_reviewer_progress_session()
        progress_html = patcher._reviewer_progress_html(progress_settings)

    from ..api.sidebar import render_reviewer_toolbar_entries

    external_html = "" if include_overview_class else render_reviewer_toolbar_entries()
    return {
        "restaurant_chip_html": restaurant_chip_html,
        "progress_html": progress_html,
        "progress_position": progress_settings.get("position", "right"),
        "external_html": external_html,
    }


def generate_top_bar_html_and_css(
    conf: dict[str, Any] | None = None,
    include_overview_class: bool = False,
) -> tuple[str, str]:
    """Generate Reviewer top bar HTML and CSS honoring Static, Minimal, or Island."""
    from . import patcher

    if conf is None:
        conf = config.get_config_readonly()
    mode = dock_mode(conf)
    base_html, base_css = patcher.generate_reviewer_top_bar_html_and_css(
        include_overview_class=include_overview_class
    )
    if not base_html.strip() or mode == "static":
        return base_html, base_css

    info = _header_info_parts(conf, include_overview_class=include_overview_class)
    items = _dock_action_items(conf)
    dock_css = _read_dock_css_text()
    full_css = base_css + f'\n<style id="onigiri-reviewer-dock-style">\n{dock_css}\n</style>'

    if mode == "minimal":
        buttons_html = _render_icon_buttons(items, "onigiri-reviewer-button is-icon-only", conf)
        prog_left = info["progress_html"] if info["progress_position"] == "left" else ""
        prog_right = info["progress_html"] if info["progress_position"] == "right" else ""
        header_html = f"""
        <div id="onigiri-reviewer-header" class="header is-minimal">
            <div class="onigiri-reviewer-header-buttons">
                {prog_left}
                {buttons_html}
                <span id="onigiri-reviewer-external-actions" style="display: contents">{info["external_html"]}</span>
                {info["restaurant_chip_html"]}
                {prog_right}
            </div>
        </div>
        """
        return header_html, full_css

    # mode == "island"
    dock_items_html = _render_icon_buttons(items, "onigiri-dock-item", conf)
    goo = resolve_goo_palette(conf)
    header_style = (
        f"--rd-goo-light: {goo['goo_light']}; "
        f"--rd-goo-dark: {goo['goo_dark']}; "
        f"--rd-goo-ink-light: {goo['ink_light']}; "
        f"--rd-goo-ink-dark: {goo['ink_dark']};"
    )
    prog_left = info["progress_html"] if info["progress_position"] == "left" else ""
    prog_right = info["progress_html"] if info["progress_position"] == "right" else ""
    info_blocks = "".join(part for part in (prog_left, info["restaurant_chip_html"], prog_right) if part.strip())
    info_section = (
        f'<span class="onigiri-dock-divider" aria-hidden="true"></span>'
        f'<div class="onigiri-island-info">{info_blocks}</div>'
        if info_blocks
        else ""
    )
    header_html = f"""
    <div id="onigiri-reviewer-header" class="header is-island" style="{header_style}">
        <div class="onigiri-island-shell">
            <span class="onigiri-island-surface" aria-hidden="true"></span>
            <div class="onigiri-island-bar">
                <div class="onigiri-reviewer-header-buttons">
                    <nav class="onigiri-rubber-dock" aria-label="Study dock">
                        <i class="onigiri-dock-indicator" aria-hidden="true"></i>
                        {dock_items_html}
                        <span id="onigiri-reviewer-external-actions" style="display: contents">{info["external_html"]}</span>
                        <div class="onigiri-dock-ink" aria-hidden="true"></div>
                        <span class="onigiri-dock-tip" aria-hidden="true"></span>
                    </nav>
                    {info_section}
                </div>
            </div>
            <div class="onigiri-island-notice" aria-live="polite">
                <div class="onigiri-island-notice-inner"></div>
            </div>
        </div>
    </div>
    """
    return header_html, full_css


def build_shadow_header_payload(
    addon_package: str,
    conf: dict[str, Any] | None = None,
) -> tuple[str, str, str]:
    """Build (mode, html, shadow_css) for initial mount and live Settings refresh."""
    from . import patcher

    if conf is None:
        conf = config.get_config_readonly()
    mode = dock_mode(conf)
    top_bar_html, top_bar_css = generate_top_bar_html_and_css(
        conf, include_overview_class=False
    )
    if not top_bar_html.strip():
        return mode, "", ""

    shadow_css = (
        patcher.generate_scoped_main_font_css(addon_package, "#onigiri-reviewer-header")
        + patcher.generate_box_effect_button_vars_css(
            conf,
            selector="#onigiri-reviewer-header",
            night_selector=":host(.night-mode) #onigiri-reviewer-header",
        )
        + top_bar_css
    )
    shadow_css = shadow_css.replace(
        ".night_mode #onigiri-reviewer-header",
        ":host(.night-mode) #onigiri-reviewer-header",
    )
    shadow_css = shadow_css.replace(
        ".night_mode .onigiri-island-shell",
        ":host(.night-mode) .onigiri-island-shell",
    )
    shadow_css = re.sub(r"@font-face\s*\{[^{}]*\}", "", shadow_css)
    return mode, top_bar_html, shadow_css


def refresh_live_dock(conf: dict[str, Any] | None = None) -> None:
    """Repaint the Reviewer or Overview dock live when Dock Style or buttons change."""
    if mw is None:
        return
    state = getattr(mw, "state", None)
    if state not in ("review", "overview"):
        return
    if conf is None:
        conf = config.get_config_readonly()
    try:
        addon_package = mw.addonManager.addonFromModule(__name__)
    except Exception:
        addon_package = os.path.basename(_ADDON_ROOT)

    if state == "review":
        reviewer = getattr(mw, "reviewer", None)
        reviewer_web = reviewer and getattr(reviewer, "web", None)
        if not reviewer_web:
            return
        mode, header_html, shadow_css = build_shadow_header_payload(addon_package, conf)
        reviewer_web.eval(
            "window.OnigiriReviewerDock && window.OnigiriReviewerDock.replaceHeader("
            f"{json.dumps(header_html)}, {json.dumps(shadow_css)}, {json.dumps(mode)});"
        )
        return

    overview = getattr(mw, "overview", None)
    overview_web = overview and getattr(overview, "web", None)
    if not overview_web:
        return
    mode = dock_mode(conf)
    header_html, top_bar_css = generate_top_bar_html_and_css(
        conf, include_overview_class=True
    )
    overview_web.eval(
        "window.OnigiriReviewerDock && window.OnigiriReviewerDock.replaceHeader("
        f"{json.dumps(header_html)}, {json.dumps(top_bar_css)}, {json.dumps(mode)});"
    )
