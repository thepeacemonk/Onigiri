"""Shared WebUI settings surface for Bento Widget integrations.

The Bento add-ons intentionally keep their own configuration and rendering
code.  This module owns only the settings chrome and value plumbing: the same
rail/panel/card hierarchy, automatic saving, and production-rendered preview
contract used by Onigiri's main settings window.

Integrations subclass :class:`BentoSettingsDialog`, pass a small page schema,
and provide a preview callback.  The callback receives the in-progress config,
preview variant, and requested light/dark mode and must return a complete HTML
document (normally built with :func:`preview_document`).
"""

from __future__ import annotations

import base64
import copy
import json
import os
import urllib.parse
from typing import Callable, Dict, Iterable, List, Optional

from aqt import mw
from aqt.qt import QColor, QDialog, QTimer, Qt, QVBoxLayout
from aqt.theme import theme_manager
from aqt.utils import openLink
from aqt.webview import AnkiWebView


BRIDGE_PREFIX = "bws:"
ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_ROOT = os.path.join(ADDON_ROOT, "web")


def _read_asset(name: str) -> str:
    try:
        with open(os.path.join(WEB_ROOT, name), "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        print(f"[Onigiri] Bento settings asset missing ({name}): {exc}")
        return ""


def safe_json(value) -> str:
    """JSON safe for embedding inside an HTML ``script`` element."""
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def image_data_uri(path: str) -> str:
    """Inline a Bento logo so the WebUI never depends on web-export order."""
    if not path or not os.path.isfile(path):
        return ""
    extension = os.path.splitext(path)[1].lower()
    mime = {
        ".gif": "image/gif", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".svg": "image/svg+xml", ".webp": "image/webp",
    }.get(extension)
    if not mime:
        return ""
    try:
        with open(path, "rb") as handle:
            encoded = base64.b64encode(handle.read()).decode("ascii")
    except OSError:
        return ""
    return f"data:{mime};base64,{encoded}"


def get_path(config: dict, path: str, default=None):
    value = config
    for part in str(path).split("."):
        if not isinstance(value, dict) or part not in value:
            return copy.deepcopy(default)
        value = value[part]
    return copy.deepcopy(value)


def set_path(config: dict, path: str, value) -> None:
    parts = str(path).split(".")
    target = config
    for part in parts[:-1]:
        child = target.get(part)
        if not isinstance(child, dict):
            child = {}
            target[part] = child
        target = child
    target[parts[-1]] = value


def deep_merge(base: dict, overlay: dict) -> dict:
    out = copy.deepcopy(base if isinstance(base, dict) else {})
    for key, value in (overlay or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def palette(dark: bool) -> dict:
    """Keep the shared Bento surface on Onigiri's settings color tokens."""
    if dark:
        return {
            "outer": "#232323", "panel": "#1a1a1a", "surface": "#242424",
            "surface_alt": "#2a2a2a", "inset": "#2e2e2e",
            "inset_hover": "#383838", "hairline": "#333333",
            "hairline_soft": "#262626", "fg": "#f4f4f5",
            "fg_muted": "#a1a1a4", "fg_faint": "#7c7c80",
            "shadow": "rgba(0,0,0,.45)", "danger": "#ef6461",
        }
    return {
        "outer": "#ececeb", "panel": "#f8f8f7", "surface": "#ffffff",
        "surface_alt": "#fbfbfa", "inset": "#f0f0ef",
        "inset_hover": "#e7e7e6", "hairline": "#e3e4e7",
        "hairline_soft": "#ededec", "fg": "#202124",
        "fg_muted": "#63666c", "fg_faint": "#8f9299",
        "shadow": "rgba(15,23,42,.12)", "danger": "#d64545",
    }


def wallpaper_css(wallpaper: Optional[dict], dark: bool = False) -> str:
    """Translate the Bento bridge wallpaper descriptor to preview CSS."""
    fallback = "#181818" if dark else "#f7f7f7"
    if not isinstance(wallpaper, dict):
        return f"background:{fallback};"
    color = wallpaper.get("color") or fallback
    if wallpaper.get("kind") != "image" or not wallpaper.get("url"):
        return f"background:{color};"
    url = str(wallpaper["url"]).replace("'", "%27")
    opacity_value = wallpaper.get("opacity", 1)
    opacity = float(1 if opacity_value is None else opacity_value)
    blur = float(wallpaper.get("blur_px", 0) or 0)
    return (
        f"background-color:{color};background-image:linear-gradient("
        f"rgba(0,0,0,{1-opacity:.3f}),rgba(0,0,0,{1-opacity:.3f})),"
        f"url('{url}');background-size:cover;background-position:center;"
        f"filter:blur({blur}px);"
    )


def preview_document(
    content: str,
    css: str = "",
    *,
    dark: bool = False,
    wallpaper: Optional[dict] = None,
    body_class: str = "",
) -> str:
    """Wrap production widget markup in a self-fitting preview document.

    No replica widget is drawn here.  ``content`` and ``css`` are the output of
    the integration's real renderer.  The wrapper only supplies the same kind
    of wallpaper stage used by Onigiri and scales the result to the iframe.
    """
    stage_css = wallpaper_css(wallpaper, dark)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:transparent}}
body{{display:grid;place-items:center;position:relative}}
#bws-wallpaper{{position:absolute;inset:-24px;{stage_css}}}
#bws-safe{{position:absolute;inset:18px;display:grid;place-items:center;overflow:hidden}}
#bws-fit{{position:relative;transform-origin:center center;will-change:transform}}
{css}
</style></head><body class="{body_class}">
<div id="bws-wallpaper"></div><div id="bws-safe"><div id="bws-fit">{content}</div></div>
<script>
(function(){{
  function fit(){{
    var safe=document.getElementById('bws-safe'), node=document.getElementById('bws-fit');
    if(!safe||!node)return;
    node.style.transform='none';
    var r=node.getBoundingClientRect(), w=Math.max(node.scrollWidth,r.width,1), h=Math.max(node.scrollHeight,r.height,1);
    var s=Math.min(1,(safe.clientWidth-12)/w,(safe.clientHeight-12)/h);
    node.style.transform='scale('+Math.max(.1,s)+')';
  }}
  function ready(){{
    fit();
    requestAnimationFrame(function(){{
      requestAnimationFrame(function(){{
        parent.postMessage('bws-preview-ready','*');
      }});
    }});
  }}
  addEventListener('load',ready); addEventListener('resize',fit);
  setTimeout(fit,40); setTimeout(fit,180);
}})();
</script></body></html>"""


def field(
    path: str,
    label: str,
    kind: str = "text",
    *,
    default=None,
    description: str = "",
    options: Optional[Iterable] = None,
    minimum=None,
    maximum=None,
    step=None,
    unit: str = "",
    scale: float = 1,
    placeholder: str = "",
    show_if: Optional[dict] = None,
    rows: int = 4,
    button_label: str = "",
) -> dict:
    """Small schema helper used by Bento integrations."""
    out = {
        "path": path, "label": label, "type": kind, "default": default,
        "description": description, "unit": unit, "scale": scale,
        "placeholder": placeholder, "rows": rows,
        "buttonLabel": button_label,
    }
    if options is not None:
        out["options"] = list(options)
    if minimum is not None:
        out["min"] = minimum
    if maximum is not None:
        out["max"] = maximum
    if step is not None:
        out["step"] = step
    if show_if:
        out["showIf"] = show_if
    return out


def section(title: str, fields: List[dict], description: str = "") -> dict:
    return {"title": title, "description": description, "fields": fields}


def page(
    page_id: str,
    title: str,
    sections: List[dict],
    description: str = "",
    icon: str = "",
    show_preview: bool = True,
) -> dict:
    return {
        "id": page_id, "title": title, "description": description,
        "icon": icon or title[:1].upper(), "sections": sections,
        "showPreview": bool(show_preview),
    }


class BentoSettingsDialog(QDialog):
    """Declarative WebUI settings dialog shared by Bento integrations."""

    def __init__(
        self,
        parent=None,
        *,
        title: str,
        subtitle: str,
        accent: str,
        pages: List[dict],
        config: dict,
        defaults: Optional[dict] = None,
        save_callback: Callable[[dict], None],
        preview_callback: Callable[[dict, str, str], str],
        preview_variants: Optional[List[dict]] = None,
        logo_path: str = "",
        mini_logo_path: str = "",
        donate_url: str = "https://buymeacoffee.com/peacemonk",
        bugs_url: str = "",
        initial_page: Optional[str] = None,
    ):
        super().__init__(parent or mw)
        self.title = title
        self.subtitle = subtitle
        self.accent = accent
        self.pages = copy.deepcopy(pages)
        self.defaults = copy.deepcopy(defaults or {})
        self.config = deep_merge(self.defaults, config or {})
        self.save_callback = save_callback
        self.preview_callback = preview_callback
        self.preview_variants = list(preview_variants or [{"value": "default", "label": "Live"}])
        self.logo = image_data_uri(logo_path)
        self.mini_logo = image_data_uri(mini_logo_path)
        self.donate_url = donate_url
        self.bugs_url = bugs_url
        self.preview_variant = str(self.preview_variants[0].get("value", "default"))
        self.preview_theme = "dark" if theme_manager.night_mode else "light"
        self.initial_page = initial_page or (self.pages[0]["id"] if self.pages else "")
        onigiri_api = getattr(mw, "onigiri_api", None)
        self.onigiri_connected = bool(
            isinstance(onigiri_api, dict) and onigiri_api.get("id") == "1011095603"
        )
        self.onigiri_version = str(onigiri_api.get("version") or "") if self.onigiri_connected else ""
        nested_config = self.config.get("ui_settings")
        nested_defaults = self.defaults.get("ui_settings")
        nested_footprint = any(
            isinstance(candidate, dict) and (
                "manual_widget_width" in candidate or "manual_widget_height" in candidate
            )
            for candidate in (nested_config, nested_defaults)
        )
        footprint_prefix = "ui_settings." if nested_footprint else ""
        footprint_minimum = 160 if nested_footprint else 120
        self.footprint_fields = [
            field(
                f"{footprint_prefix}manual_widget_width", "Width", "number",
                default=get_path(self.defaults, f"{footprint_prefix}manual_widget_width", 200),
                minimum=footprint_minimum, maximum=900, unit="px",
            ),
            field(
                f"{footprint_prefix}manual_widget_height", "Height", "number",
                default=get_path(self.defaults, f"{footprint_prefix}manual_widget_height", 200),
                minimum=footprint_minimum, maximum=900, unit="px",
            ),
        ]
        self._closed = False
        self._close_requested = False

        self.setWindowTitle(f"{title} Settings")
        self._apply_size()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.web = AnkiWebView(self)
        layout.addWidget(self.web, 1)
        try:
            self.web.page().setBackgroundColor(QColor(palette(theme_manager.night_mode)["outer"]))
        except Exception:
            pass
        self.web.set_bridge_command(self._on_bridge, self)
        self.web.stdHtml(self._render())
        self.finished.connect(self._cleanup)

    def _apply_size(self) -> None:
        screen = (self.screen() if hasattr(self, "screen") else None) or (
            mw.app.primaryScreen() if mw and mw.app else None
        )
        if screen is None:
            self.resize(1120, 720)
            self.setMinimumSize(900, 560)
            return
        available = screen.availableGeometry()
        width = min(1260, available.width())
        height = min(max(620, int(available.height() * 0.72)), available.height())
        self.setMinimumSize(min(980, available.width()), min(560, available.height()))
        self.resize(width, height)
        self.move(
            available.x() + (available.width() - width) // 2,
            available.y() + (available.height() - height) // 2,
        )

    def _schema_context(self) -> List[dict]:
        pages = copy.deepcopy(self.pages)
        for item in pages:
            for group in item.get("sections", []):
                for spec in group.get("fields", []):
                    raw = get_path(self.config, spec["path"], spec.get("default"))
                    scale = spec.get("scale") or 1
                    if spec.get("type") in ("number", "range") and scale != 1:
                        try:
                            raw = float(raw) / float(scale)
                        except (TypeError, ValueError, ZeroDivisionError):
                            raw = spec.get("default", 0)
                    spec["value"] = raw
        return pages

    def _footprint_context(self) -> List[dict]:
        fields = copy.deepcopy(self.footprint_fields)
        for spec in fields:
            spec["value"] = get_path(self.config, spec["path"], spec.get("default"))
        return fields

    def _render_preview(self) -> str:
        try:
            return self.preview_callback(
                copy.deepcopy(self.config), self.preview_variant, self.preview_theme
            ) or ""
        except Exception as exc:  # noqa: BLE001 - show preview errors in the stage
            print(f"[{self.title}] preview error: {exc}")
            return preview_document(
                f"<div style='padding:24px;font:14px system-ui;color:#d64545'>"
                f"Preview unavailable: {str(exc)}</div>",
                dark=self.preview_theme == "dark",
            )

    def _render(self) -> str:
        template = _read_asset("bento_settings.html")
        context = {
            "title": self.title,
            "subtitle": self.subtitle,
            "accent": self.accent,
            "logo": self.logo,
            "miniLogo": self.mini_logo,
            "palette": palette(bool(theme_manager.night_mode)),
            "pages": self._schema_context(),
            "initialPage": self.initial_page,
            "preview": self._render_preview(),
            "previewVariant": self.preview_variant,
            "previewTheme": self.preview_theme,
            "previewVariants": self.preview_variants,
            "hasDonate": bool(self.donate_url),
            "hasBugs": bool(self.bugs_url),
            "onigiriConnected": self.onigiri_connected,
            "onigiriVersion": self.onigiri_version,
            "footprint": self._footprint_context(),
        }
        return (
            template.replace("/*__BWS_CSS__*/", _read_asset("bento_settings.css"))
            .replace("/*__BWS_CONTEXT__*/null", safe_json(context))
            .replace("/*__BWS_JS__*/", _read_asset("bento_settings.js"))
            .replace("/*__BWS_BOOT_BG__*/", context["palette"]["outer"])
        )

    def normalize_patch(self, patch: Dict[str, object]) -> Dict[str, object]:
        """Hook for derived fields such as Hours' background-mode selector."""
        return patch

    def handle_action(self, action: str) -> dict:
        """Optional hook for non-value controls such as gallery/favorite actions."""
        return {"ok": False, "error": f"Unsupported action: {action}"}

    def after_save(self) -> None:
        """Optional hook for cache invalidation/refresh after a successful write."""

    def _save(self) -> None:
        self.save_callback(copy.deepcopy(self.config))
        self.after_save()

    def _apply_patch(self, patch: dict) -> dict:
        if not isinstance(patch, dict):
            return {"ok": False, "error": "Invalid settings patch"}
        patch = self.normalize_patch(dict(patch))
        specs = {
            spec["path"]: spec
            for item in self.pages
            for group in item.get("sections", [])
            for spec in group.get("fields", [])
        }
        if not self.onigiri_connected:
            specs.update({spec["path"]: spec for spec in self.footprint_fields})
        for path, value in patch.items():
            spec = specs.get(path)
            if not spec:
                continue
            kind = spec.get("type", "text")
            if kind == "bool":
                value = bool(value)
            elif kind in ("range", "number"):
                try:
                    value = float(value)
                    if spec.get("step", 1) == 1:
                        value = int(round(value))
                    value *= spec.get("scale") or 1
                    if isinstance(value, float) and value.is_integer():
                        value = int(value)
                except (TypeError, ValueError):
                    continue
            else:
                value = str(value)
            set_path(self.config, path, value)
        try:
            self._save()
        except Exception as exc:  # noqa: BLE001 - surfaced to autosave status
            print(f"[{self.title}] settings save failed: {exc}")
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "preview": self._render_preview()}

    def _reset(self) -> dict:
        self.config = copy.deepcopy(self.defaults)
        try:
            self._save()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True, "pages": self._schema_context(),
            "footprint": self._footprint_context(),
            "preview": self._render_preview(),
        }

    def _on_bridge(self, command: str):
        command = str(command or "")
        if not command.startswith(BRIDGE_PREFIX):
            return None
        action, _, arg = command[len(BRIDGE_PREFIX):].partition(":")
        if action == "ready":
            return {"ok": True}
        if action == "patch":
            try:
                patch = json.loads(urllib.parse.unquote(arg))
            except (ValueError, TypeError):
                return {"ok": False, "error": "Invalid settings data"}
            return self._apply_patch(patch)
        if action == "preview":
            try:
                state = json.loads(urllib.parse.unquote(arg))
                self.preview_variant = str(state.get("variant", self.preview_variant))
                self.preview_theme = str(state.get("theme", self.preview_theme))
            except (ValueError, TypeError, AttributeError):
                pass
            return {"ok": True, "preview": self._render_preview()}
        if action == "reset":
            return self._reset()
        if action == "action":
            try:
                result = self.handle_action(urllib.parse.unquote(arg)) or {"ok": True}
            except Exception as exc:  # noqa: BLE001 - action errors belong in WebUI
                return {"ok": False, "error": str(exc)}
            if result.get("ok"):
                result.setdefault("pages", self._schema_context())
                result.setdefault("preview", self._render_preview())
            return result
        if action == "haptic":
            try:
                from ..settings_web.dialog import _trigger_mac_haptic_native

                pattern = int(urllib.parse.unquote(arg) or 0)
                _trigger_mac_haptic_native(pattern)
            except Exception:
                pass
            return {"ok": True}
        if action == "donate" and self.donate_url:
            openLink(self.donate_url)
            return {"ok": True}
        if action == "bugs" and self.bugs_url:
            openLink(self.bugs_url)
            return {"ok": True}
        if action == "done":
            # ``_on_bridge()`` is invoked synchronously by QWebChannel.  Closing
            # this modal dialog here emits ``finished``, which cleans up the
            # AnkiWebView/page while QtWebChannel is still sending this method's
            # return value back to JavaScript.  Queue the close until the
            # bridge invocation has returned.
            if not self._close_requested:
                self._close_requested = True
                QTimer.singleShot(0, self.accept)
            return {"ok": True}
        return {"ok": False, "error": "Unknown command"}

    def _cleanup(self, *_args) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self.web.cleanup()
        except Exception:
            pass
        self.deleteLater()
