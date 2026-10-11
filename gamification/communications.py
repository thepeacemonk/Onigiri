"""Shared Onigiri announcements inbox backed by the Database Apps Script."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import unquote

import requests
from aqt import mw
from aqt.qt import QDialog, QTimer, QVBoxLayout
from aqt.webview import AnkiWebView

from .. import safe_storage
from ..fonts import poppins_font_face_css
from ..settings_web import render as settings_render
from ..theme_palette import mix as mix_colors, rgb as parse_rgb
from ..translations import tr


COMMUNICATIONS_API_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbyQl6b_cPnXJEJeEJryvsuRzZYclfIt_LWN1Mqqf63FjzCbKdPKV_uHIgYtHIXmAbnB/exec"
)
COMMUNICATIONS_TIMEOUT = (10, 90)
MAX_ANNOUNCEMENTS = 100


def _addon_package() -> str:
    return mw.addonManager.addonFromModule(__name__)


def _logo_markup() -> str:
    addon_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logo_path = os.path.join(addon_root, "system_files", "onigiri_mini_logo.svg")
    try:
        with open(logo_path, encoding="utf-8") as logo_file:
            svg = logo_file.read()
        return svg.replace(
            "<svg ",
            '<svg class="brand-logo" role="img" aria-label="Onigiri" ',
            1,
        )
    except OSError:
        return '<span class="brand-logo-fallback" aria-label="Onigiri">Onigiri</span>'


def _profile_name() -> str:
    try:
        return mw.pm.name or "default"
    except Exception:
        return "default"


def _state_path() -> str:
    profile = _profile_name().replace("/", "_").replace("\\", "_")
    return os.path.join(safe_storage.user_files_dir(), f"communications_{profile}.json")


def _load_state() -> Dict[str, Any]:
    data = safe_storage.read_json(
        _state_path(), default={}, label="Your Communications inbox"
    )
    if not isinstance(data, dict):
        data = {}
    announcements = data.get("announcements", [])
    read_ids = data.get("read_ids", [])
    return {
        "announcements": announcements if isinstance(announcements, list) else [],
        "read_ids": [str(value) for value in read_ids] if isinstance(read_ids, list) else [],
        "last_synced_at": str(data.get("last_synced_at") or ""),
    }


def _save_state(state: Dict[str, Any]) -> None:
    safe_storage.atomic_write_json(_state_path(), state, mirror=True)


def _strings() -> Dict[str, str]:
    keys = (
        "communications_title",
        "communications_subtitle",
        "communications_sync",
        "communications_syncing",
        "communications_mark_all_read",
        "communications_unread_count",
        "communications_read",
        "communications_mark_read",
        "communications_empty_title",
        "communications_empty_body",
        "communications_never_synced",
        "communications_last_synced",
        "communications_sync_success",
        "communications_sync_failed",
        "communications_first_sync_title",
        "communications_first_sync_body",
        "communications_first_sync_failed_title",
        "communications_first_sync_failed_body",
        "communications_new_badge",
    )
    return {key: tr(key) for key in keys}


def _normalize_announcements(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []
    announcements = []
    for entry in value[:MAX_ANNOUNCEMENTS]:
        if not isinstance(entry, dict):
            continue
        announcement_id = str(entry.get("id") or "").strip()
        title = str(entry.get("title") or "").strip()
        message = str(entry.get("message") or "").strip()
        if not announcement_id or not (title or message):
            continue
        image_url = str(entry.get("imageUrl") or entry.get("image_url") or "").strip()
        if not image_url.startswith("https://"):
            image_url = ""
        announcements.append({
            "id": announcement_id,
            "title": title,
            "message": message,
            "imageUrl": image_url,
            "publishedAt": str(entry.get("publishedAt") or entry.get("published_at") or ""),
        })
    return announcements


def _communications_payload(state: Dict[str, Any], syncing: bool = False, status: str = "") -> Dict[str, Any]:
    dark = settings_render.is_dark()
    palette = settings_render.palette(dark)
    accent = palette["accent"]
    accent_rgb = ", ".join(str(channel) for channel in parse_rgb(accent))
    settings_tokens = {
        "outer": palette["outer"],
        "panel": palette["panel"],
        "surface": palette["surface"],
        "surface-alt": palette["surface_alt"],
        "inset": palette["inset"],
        "inset-hover": palette["inset_hover"],
        "hairline": palette["hairline"],
        "hairline-soft": palette["hairline_soft"],
        "fg": palette["fg"],
        "fg-muted": palette["fg_muted"],
        "fg-faint": palette["fg_faint"],
        "accent": accent,
        "accent-a14": f"rgba({accent_rgb}, 0.14)",
        "accent-a16": f"rgba({accent_rgb}, 0.16)",
        "accent-line": mix_colors(accent, palette["hairline"], 0.45),
        "accent-line-strong": mix_colors(accent, palette["hairline"], 0.55),
        "accent-wash": mix_colors(accent, palette["surface"], 0.05),
        "accent-wash-strong": mix_colors(accent, palette["surface"], 0.07),
        "shadow": palette["shadow"],
        "danger": palette["danger"],
    }
    return {
        "announcements": _normalize_announcements(state.get("announcements", [])),
        "readIds": state.get("read_ids", []),
        "lastSyncedAt": state.get("last_synced_at", ""),
        "hasSynced": bool(state.get("last_synced_at")),
        "isSyncing": bool(syncing),
        "status": status,
        "colorMode": "dark" if dark else "light",
        "themeTokens": settings_tokens,
        "strings": _strings(),
    }


class CommunicationsDialog(QDialog):
    """Native dialog shell; announcement cards are rendered in an Anki WebView."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("communications_title", "Announcements"))
        self.resize(900, 740)
        self.setMinimumSize(640, 500)
        self._state = _load_state()
        self._initial_sync_pending = not bool(self._state.get("last_synced_at"))
        self._is_syncing = self._initial_sync_pending
        self.web = AnkiWebView(self)
        self.web.set_bridge_command(self._on_bridge, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self._render()
        if self._initial_sync_pending:
            QTimer.singleShot(0, lambda: self._sync(initial=True))

    def _render(self) -> None:
        root = os.path.dirname(os.path.dirname(__file__))
        html_path = os.path.join(
            root, "web", "gamification", "communications", "communications.html"
        )
        try:
            with open(html_path, encoding="utf-8") as handle:
                body = handle.read()
        except OSError:
            body = "<main><h1>Communications page assets are missing.</h1></main>"
        body = body.replace("<!--__ONIGIRI_LOGO__-->", _logo_markup())

        initial_status = (
            tr("communications_syncing", "Checking for announcements…")
            if self._initial_sync_pending else ""
        )
        data = json.dumps(
            _communications_payload(self._state, self._is_syncing, initial_status),
            ensure_ascii=False,
        ).replace("</", "<\\/")
        font_css = poppins_font_face_css(_addon_package())
        head = (
            f"<style>{font_css}</style>"
            f"<script>window.ONIGIRI_COMMUNICATIONS_DATA={data};</script>"
        )
        html_root = os.path.dirname(html_path)
        css = [f"/_addons/{_addon_package()}/web/gamification/communications/communications.css"]
        js = [f"/_addons/{_addon_package()}/web/gamification/communications/communications.js"]
        for paths, filename in ((css, "communications.css"), (js, "communications.js")):
            try:
                paths[0] += f"?v={os.stat(os.path.join(html_root, filename)).st_mtime_ns}"
            except OSError:
                pass
        self.web.stdHtml(body, css=css, js=js, head=head, context=self)

    def _push(self, status: str = "", error: bool = False) -> None:
        data = json.dumps(
            _communications_payload(self._state, self._is_syncing, status),
            ensure_ascii=False,
        ).replace("</", "<\\/")
        try:
            self.web.eval(
                "window.onCommunicationsData && "
                f"window.onCommunicationsData({data}, {json.dumps({'error': error})});"
            )
        except RuntimeError:
            pass

    def _on_bridge(self, command: str) -> bool:
        if command == "communications:sync":
            self._sync()
            return True
        if command == "communications:read-all":
            self._state["read_ids"] = [
                item["id"] for item in self._state.get("announcements", [])
            ]
            _save_state(self._state)
            self._push()
            return True
        if command.startswith("communications:read:"):
            announcement_id = unquote(command.split(":", 2)[2])
            known_ids = {
                item["id"] for item in self._state.get("announcements", [])
            }
            if announcement_id in known_ids:
                read_ids = set(self._state.get("read_ids", []))
                read_ids.add(announcement_id)
                self._state["read_ids"] = sorted(read_ids)
                _save_state(self._state)
                self._push()
            return True
        return False

    def _sync(self, initial: bool = False) -> None:
        if self._is_syncing and not initial:
            return
        if not self._is_syncing:
            self._is_syncing = True
            self._push(tr("communications_syncing", "Checking for announcements…"))
        self._initial_sync_pending = False

        def request() -> Dict[str, Any]:
            response = requests.post(
                COMMUNICATIONS_API_URL,
                json={"action": "communicationsSync"},
                timeout=COMMUNICATIONS_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or payload.get("result") != "success":
                message = payload.get("message") if isinstance(payload, dict) else ""
                raise RuntimeError(message or "The database returned an invalid response.")
            return payload

        def done(future) -> None:
            self._is_syncing = False
            try:
                payload = future.result()
                self._state["announcements"] = _normalize_announcements(
                    payload.get("announcements", [])
                )
                self._state["last_synced_at"] = str(
                    payload.get("synced_at")
                    or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
                )
                current_ids = {item["id"] for item in self._state["announcements"]}
                self._state["read_ids"] = [
                    item_id for item_id in self._state.get("read_ids", [])
                    if item_id in current_ids
                ]
                _save_state(self._state)
                self._push(tr("communications_sync_success", "Announcements synced."))
            except Exception as exc:
                print(f"Onigiri Communications sync failed: {exc}")
                self._push(
                    tr(
                        "communications_sync_failed",
                        "Could not sync announcements. Check your connection and try again.",
                    ),
                    error=True,
                )

        mw.taskman.run_in_background(request, done)


_dialog = None


def open_communications_dialog() -> None:
    global _dialog
    if _dialog is not None:
        _dialog.close()
    _dialog = CommunicationsDialog(mw)
    _dialog.show()
