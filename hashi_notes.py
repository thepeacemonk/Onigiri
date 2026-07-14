"""
Hashi Notes — a lightweight "napkin" for fast, temporary study notes.

Storage model (two physical stores satisfy the three-way spec):
  1. mw.col.conf["onigiri_hashi_notes"] — source of truth. Lives inside
     collection.anki2, so it is both the "SQL DB copy" and the "AnkiWeb" copy
     (it syncs with the collection). Mirrors the Prep Station pattern.
  2. user_files/hashi_notes/<id>.json — one file per note. Rides the existing
     Onigiri media-zip sync (sync.py).

Preferences (retention default, custom CSS, default sort, trash grace) live in
the local Onigiri config (config.py DEFAULTS["hashi_notes"]).

Retention is creation-based with a soft trash: a note expires at
created_at + retention days, at which point it is moved to trash (trashed_at
set). After trash_grace_days in the trash it is purged from both stores.
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

from aqt import mw
from aqt.qt import (
    QColor,
    QDialog,
    QFrame,
    QHBoxLayout,
    QIcon,
    QLabel,
    QPainter,
    QPixmap,
    Qt,
    QTimer,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from aqt.webview import AnkiWebView
from PyQt6.QtCore import QRectF
from PyQt6.QtSvg import QSvgRenderer

from . import config
from .translations import tr


# ─── Constants ────────────────────────────────────────────────────────────────

CONF_KEY = "onigiri_hashi_notes"
USER_FILES_SUBDIR = "hashi_notes"
RETENTION_CHOICES = (7, 30, 0)  # 0 == Never
SORT_KEYS = ("age", "tags", "priority", "title")
PRIORITY_ORDER = {"high": 0, "med": 1, "low": 2, "none": 3}

_popup = None
_gallery = None


# ─── Small utilities ──────────────────────────────────────────────────────────

def _addon_root():
    return os.path.dirname(__file__)


def _system_icon_path(filename):
    return os.path.join(_addon_root(), "system_files", "system_icons", "unavailable_for_users", filename)


def _tinted_icon(path, color, size=16):
    """Renders a currentColor-based SVG tinted for the active theme, for the
    native (non-webview) chrome buttons."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            svg_xml = f.read().replace("currentColor", color)
        renderer = QSvgRenderer(svg_xml.encode("utf-8"))
        pixmap = QPixmap(size * 2, size * 2)
        pixmap.setDevicePixelRatio(2.0)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # The painter operates in the pixmap's logical coordinate space (it
        # already accounts for the 2x device pixel ratio set above), so the
        # render target must be size x size, not the physical size*2 x size*2
        # - otherwise the icon is drawn at 2x scale and gets cropped by the
        # pixmap edge. Also fixes icons with no explicit width/height (just a
        # viewBox), which QSvgRenderer won't auto-scale to fit otherwise.
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        return QIcon(pixmap)
    except Exception:
        return QIcon(path)


def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso(value):
    if not value:
        return None
    try:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _is_dark_mode(conf=None):
    try:
        from .config import effective_night_mode

        return effective_night_mode(conf or config.get_config())
    except Exception:
        return False


def _accent_color(conf=None):
    conf = conf or config.get_config()
    mode = "dark" if _is_dark_mode(conf) else "light"
    return conf.get("colors", {}).get(mode, {}).get("--accent-color", "#00A982")


# ─── Preferences (local config) ───────────────────────────────────────────────

def get_prefs(conf=None):
    conf = conf or config.get_config()
    defaults = config.DEFAULTS.get("hashi_notes", {})
    prefs = conf.get("hashi_notes", {})
    if not isinstance(prefs, dict):
        prefs = {}
    merged = dict(defaults)
    merged.update(prefs)
    return merged


def default_retention():
    try:
        value = int(get_prefs().get("retention_default", 30))
    except Exception:
        value = 30
    return value if value in RETENTION_CHOICES else 30


def trash_grace_days():
    try:
        return max(0, int(get_prefs().get("trash_grace_days", 7)))
    except Exception:
        return 7


# ─── Persistence: mw.col.conf source of truth ─────────────────────────────────

def _read_all():
    if not mw or not mw.col:
        return []
    try:
        notes = mw.col.conf.get(CONF_KEY, [])
        return list(notes) if isinstance(notes, list) else []
    except Exception:
        return []


def _write_all(notes):
    if not mw or not mw.col:
        return
    try:
        mw.col.conf[CONF_KEY] = notes
        mw.col.setMod()
    except Exception as e:
        print(f"Hashi Notes: save error: {e}")


# ─── Persistence: user_files JSON mirror ──────────────────────────────────────

def _mirror_dir():
    path = os.path.join(_addon_root(), "user_files", USER_FILES_SUBDIR)
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    return path


def _write_json_mirror(note):
    try:
        path = os.path.join(_mirror_dir(), f"{note['id']}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(note, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Hashi Notes: mirror write error: {e}")


def _delete_json_mirror(note_id):
    try:
        path = os.path.join(_mirror_dir(), f"{note_id}.json")
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print(f"Hashi Notes: mirror delete error: {e}")


# ─── Note model ───────────────────────────────────────────────────────────────

def _new_note():
    now = _now_iso()
    return {
        "id": uuid.uuid4().hex,
        "title": "",
        "icon": "",
        "body_md": "",
        "created_at": now,
        "updated_at": now,
        "retention": default_retention(),
        "priority": "none",
        "tags": [],
        "color": "",
        "bg_color": "",
        "linked_cards": [],
        "trashed_at": None,
    }


def _normalize(note):
    """Fills missing keys so older/partial notes stay valid."""
    base = _new_note()
    base.update({k: v for k, v in note.items() if k in base})
    base["id"] = note.get("id") or base["id"]
    if base["retention"] not in RETENTION_CHOICES:
        base["retention"] = 30
    if base["priority"] not in PRIORITY_ORDER:
        base["priority"] = "none"
    if not isinstance(base["tags"], list):
        base["tags"] = []
    if not isinstance(base["linked_cards"], list):
        base["linked_cards"] = []
    return base


def load_notes(include_trashed=False):
    notes = [_normalize(n) for n in _read_all() if isinstance(n, dict)]
    if not include_trashed:
        notes = [n for n in notes if not n.get("trashed_at")]
    return notes


def get_note(note_id):
    for n in _read_all():
        if isinstance(n, dict) and n.get("id") == note_id:
            return _normalize(n)
    return None


def save_note(note):
    """Insert or update a note across both stores. Returns the stored note."""
    note = _normalize(note)
    note["updated_at"] = _now_iso()
    notes = _read_all()
    replaced = False
    for i, existing in enumerate(notes):
        if isinstance(existing, dict) and existing.get("id") == note["id"]:
            notes[i] = note
            replaced = True
            break
    if not replaced:
        notes.append(note)
    _write_all(notes)
    _write_json_mirror(note)
    return note


def trash_note(note_id):
    note = get_note(note_id)
    if not note:
        return
    note["trashed_at"] = _now_iso()
    save_note(note)


def restore_note(note_id):
    note = get_note(note_id)
    if not note:
        return
    note["trashed_at"] = None
    save_note(note)


def delete_note(note_id):
    """Hard-remove from both stores."""
    notes = [n for n in _read_all() if not (isinstance(n, dict) and n.get("id") == note_id)]
    _write_all(notes)
    _delete_json_mirror(note_id)


# ─── Retention / trash sweep ──────────────────────────────────────────────────

def _expiry(note):
    retention = note.get("retention", 30)
    if not retention:  # Never
        return None
    created = _parse_iso(note.get("created_at"))
    if not created:
        return None
    return created + timedelta(days=int(retention))


def purge_expired():
    """Move expired notes to trash; hard-delete notes past the grace window.

    Safe to call on collection load and whenever the gallery opens.
    """
    if not mw or not mw.col:
        return
    now = datetime.now(timezone.utc)
    grace = timedelta(days=trash_grace_days())
    notes = [_normalize(n) for n in _read_all() if isinstance(n, dict)]
    changed = False
    survivors = []
    for note in notes:
        trashed = _parse_iso(note.get("trashed_at"))
        if trashed is not None:
            if now - trashed >= grace:
                _delete_json_mirror(note["id"])
                changed = True
                continue  # purged
            survivors.append(note)
            continue
        expiry = _expiry(note)
        if expiry is not None and now >= expiry:
            note["trashed_at"] = _now_iso()
            _write_json_mirror(note)
            changed = True
        survivors.append(note)
    if changed:
        _write_all(survivors)


# ─── Anki data helpers (card linking) ─────────────────────────────────────────

def search_cards(query, limit=12):
    """Returns a light list of {id, label} for the @-linking picker."""
    if not mw or not mw.col:
        return []
    query = (query or "").strip()
    results = []
    try:
        if query:
            search = query
        else:
            search = "deck:*"
        card_ids = mw.col.find_cards(search)[:limit]
        for cid in card_ids:
            try:
                card = mw.col.get_card(cid)
                note = card.note()
                label = _first_field_text(note)
                deck = mw.col.decks.name(card.did)
                results.append({"id": int(cid), "label": label or "(card)", "deck": deck})
            except Exception:
                continue
    except Exception as e:
        print(f"Hashi Notes: card search error: {e}")
    return results


def _first_field_text(note):
    for value in note.fields:
        cleaned = re.sub(r"<[^>]+>", " ", value or "")
        cleaned = html.unescape(cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned:
            return cleaned[:80]
    return ""


# ─── Profile avatar (data URI, mirrors the sidebar profile picture) ───────────

def _file_data_uri(path):
    try:
        if not path or not os.path.exists(path):
            return ""
        with open(path, "rb") as f:
            raw = f.read()
        ext = os.path.splitext(path)[1].lstrip(".").lower() or "png"
        mime = "jpeg" if ext in ("jpg", "jpeg") else ext
        return f"data:image/{mime};base64," + base64.b64encode(raw).decode("ascii")
    except Exception:
        return ""


def _avatar_data_uri():
    try:
        conf = mw.col.conf if (mw and mw.col) else {}
        dark = _is_dark_mode()
        pic_dynamic = bool(conf.get("modern_menu_profile_picture_dynamic_mode", True))
        filename = (
            conf.get(f"modern_menu_profile_picture_{'dark' if dark else 'light'}", "")
            if pic_dynamic else ""
        ) or conf.get("modern_menu_profile_picture", "")
        path = os.path.join(_addon_root(), "user_files", "profile", filename) if filename else ""
        if not path or not os.path.exists(path):
            path = os.path.join(_addon_root(), "system_files", "profile_default", "onigiri-san.png")
        return _file_data_uri(path)
    except Exception:
        return ""


def _profile_bar_context():
    """Resolves the Profile Bar background (accent/custom/image) the same way
    the sidebar profile bar + Prep Station header do."""
    try:
        conf = mw.col.conf if (mw and mw.col) else {}
        dark = _is_dark_mode()
        suffix = "dark" if dark else "light"
        mode = conf.get("modern_menu_profile_bg_mode", "image")
        if mode == "accent":
            color = _accent_color()
        else:
            color = conf.get(f"modern_menu_profile_bg_color_{suffix}", "#555555" if dark else "#EEEEEE")
        opacity = int(conf.get("modern_menu_profile_bg_opacity", 50) or 50)
        blur = int(conf.get("modern_menu_profile_bg_blur", 0) or 0)
        image = ""
        if mode == "image":
            filename = conf.get("modern_menu_profile_bg_image", "")
            path = os.path.join(_addon_root(), "user_files", "profile_bg", filename) if filename else ""
            image = _file_data_uri(path)
        return {"color": color, "image": image, "opacity": opacity, "blur": blur}
    except Exception:
        return {"color": _accent_color(), "image": "", "opacity": 100, "blur": 0}


def _profile_name():
    try:
        conf = mw.col.conf if (mw and mw.col) else {}
        name = conf.get("modern_menu_profile_name", "") or config.get_config().get("userName", "")
        return str(name or "").strip() or tr("hashi_profile_you", "You")
    except Exception:
        return tr("hashi_profile_you", "You")


# ─── Theme palette for the webviews ───────────────────────────────────────────

def _palette(dark):
    if dark:
        return {
            "bg": "#161616", "shell": "#1f1f1f", "surface": "#2a2a2a",
            "border": "#343434", "fg": "#f4f4f5", "fg2": "#b6b6b8", "fg3": "#7c7c80",
            "input_bg": "#242424", "hover": "#343434", "chip": "#2a2a2a",
            "highlight": "#fff3b0",
        }
    return {
        "bg": "#f5f5f4", "shell": "#ffffff", "surface": "#f1f1f0",
        "border": "#e5e7eb", "fg": "#1f2933", "fg2": "#4b5563", "fg3": "#8a9099",
        "input_bg": "#ffffff", "hover": "#f1f3f5", "chip": "#eef0f2",
        "highlight": "#fff3b0",
    }


def _hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def _fill_tint(base_hex, dark):
    """Mirrors hashi_notes.html's fillTint()/mixHex() JS so the native shell
    can be painted with the correct tinted colour on first show, instead of
    starting plain and jumping to the tint once the page's JS reports it back
    over the bridge (which visibly flickers)."""
    target = (22, 22, 22) if dark else (255, 255, 255)
    base = _hex_to_rgb(base_hex)
    t = 0.80
    mixed = tuple(base[i] + (target[i] - base[i]) * t for i in range(3))
    return _rgb_to_hex(mixed)


def _read_web_asset(name):
    path = os.path.join(_addon_root(), "web", name)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Hashi Notes: could not read {name}: {e}")
        return ""


def _addon_uri(rel_from_root):
    """Addon-root-relative path served through Anki's media server
    (/_addons/<package>/...)."""
    rel = rel_from_root.lstrip("/")
    try:
        pkg = mw.addonManager.addonFromModule(__name__)
        return f"/_addons/{pkg}/{rel}"
    except Exception:
        return rel


def _emoji_sprite_map():
    """Maps each Onigiri gallery emoji to its sprite SVG under system_files/emojis."""
    try:
        from .emoji_sprites import EMOJI_SPRITES

        return {it["value"]: it["asset"] for it in EMOJI_SPRITES}
    except Exception:
        return {}


# Every user-facing string the two webviews (hashi_notes.html / hashi_gallery.html)
# render. Injected into the context JSON as ctx.strings so the HTML/JS can look
# them up; English is kept inline in the templates as a fallback.
_WEBVIEW_STRING_KEYS = (
    "hashi_notes_title", "hashi_notes_short", "hashi_back_to_notes",
    "hashi_note_colors", "hashi_set_note_icon", "hashi_untitled",
    "hashi_bold", "hashi_italic", "hashi_heading1", "hashi_heading2",
    "hashi_hl_yellow", "hashi_hl_green", "hashi_hl_blue", "hashi_hl_pink",
    "hashi_hl_custom", "hashi_hl_remove", "hashi_insert_emoji",
    "hashi_editor_placeholder", "hashi_keep", "hashi_priority",
    "hashi_prio_low", "hashi_prio_med", "hashi_prio_high",
    "hashi_tags_placeholder", "hashi_color_label", "hashi_custom_color",
    "hashi_never", "hashi_days_suffix", "hashi_no_cards",
    "hashi_view_trash", "hashi_sort_prefix", "hashi_sort_recent",
    "hashi_sort_tags", "hashi_sort_priority", "hashi_sort_title",
    "hashi_empty_note", "hashi_kept", "hashi_days_left_suffix",
    "hashi_new_note", "hashi_trash_empty", "hashi_restore",
    "hashi_delete_forever", "hashi_move_to_trash", "hashi_profile_you",
    "hashi_months",
)


def _webview_strings():
    return {key: tr(key) for key in _WEBVIEW_STRING_KEYS}


def _build_context_json(dark):
    pal = _palette(dark)
    prefs = get_prefs()
    return {
        "strings": _webview_strings(),
        "dark": bool(dark),
        "accent": _accent_color(),
        "palette": pal,
        "customCss": str(prefs.get("custom_css", "") or ""),
        "defaultSort": str(prefs.get("default_sort", "age") or "age"),
        "avatar": _avatar_data_uri(),
        "profileName": _profile_name(),
        "profileBg": _profile_bar_context(),
        "addonBase": _addon_uri(""),
        "emojiSprites": _emoji_sprite_map(),
        "retentionChoices": list(RETENTION_CHOICES),
        "katexCss": _addon_uri("web/lib/katex/katex.min.css"),
        "katexJs": _addon_uri("web/lib/katex/katex.min.js"),
        "katexAutoJs": _addon_uri("web/lib/katex/auto-render.min.js"),
    }


def _safe_json(value):
    """json.dumps escaped so it can't break out of the <script> tag it is
    injected into (a note body may legitimately contain '</script>')."""
    return json.dumps(value).replace("</", "<\\/")


def _render_html(template_name, note_data, dark, ctx_override=None):
    template = _read_web_asset(template_name)
    if not template:
        return "<html><body>Hashi Notes assets missing.</body></html>"
    ctx = ctx_override or _build_context_json(dark)
    return (
        template
        .replace("/*__HASHI_CONTEXT__*/null", _safe_json(ctx))
        .replace("/*__HASHI_DATA__*/null", _safe_json(note_data))
    )


# ─── Shared note-editor bridge handling ───────────────────────────────────────
#
# Both the floating popup and the Gallery's embedded editor render
# hashi_notes.html into an AnkiWebView and need to answer the same set of
# bridge commands (save, icon/colour pickers, @card search). This mixin holds
# that shared behaviour; each host still owns its own window chrome and
# whatever "hashi:set_shell:" means for it (a no-op unless the host defines
# _set_shell_bg).

class _HashiNoteEditorMixin:
    def _handle_note_bridge(self, cmd):
        """Handles the commands hashi_notes.html can send. Returns True if the
        command was recognised (and thus already dealt with)."""
        if cmd.startswith("hashi:save:"):
            payload = cmd.split(":", 2)[2]
            data = json.loads(payload)
            merged = dict(self.note)
            merged.update(data)
            self.note = save_note(merged)
            return True
        if cmd.startswith("hashi:search_cards:"):
            query = cmd.split(":", 2)[2]
            results = search_cards(query)
            self.web.eval(
                "window.hashiReceiveCards && window.hashiReceiveCards(%s);"
                % json.dumps(results)
            )
            return True
        if cmd.startswith("hashi:pick_icon"):
            mode = "title" if cmd.endswith(":title") else "inline"
            self._pick_icon(mode)
            return True
        if cmd.startswith("hashi:set_shell:"):
            set_shell = getattr(self, "_set_shell_bg", None)
            if set_shell:
                set_shell(cmd.split(":", 2)[2])
            return True
        if cmd == "hashi:pick_color":
            self._pick_color()
            return True
        if cmd == "hashi:pick_highlight":
            self._pick_highlight()
            return True
        return False

    def _pick_icon(self, mode="inline"):
        try:
            from .icon_picker import DeckIconPickerDialog

            current = self.note.get("icon", "") if mode == "title" else ""
            dlg = DeckIconPickerDialog(current, _addon_root(), self.window(), allow_emoji=True, night_mode=self.dark)
            dlg.iconSelected.connect(lambda value: self._on_icon_selected(value, mode))
            dlg.exec()
            # Frameless always-on-top picker can drop us behind Anki on close.
            self.raise_()
            self.activateWindow()
        except Exception as e:
            print(f"Hashi Notes: icon picker error: {e}")

    def _open_color_dialog(self, current):
        """Runs Onigiri's native colour picker (same as Settings), floated in
        its own always-on-top translucent top-level window. Returns (hex, ok).

        The picker is an in-window overlay, but our editor is an AnkiWebView,
        whose native surface paints over sibling widgets — so a picker parented
        to this popup would hide *behind* the webview. Hosting it in a separate
        top-level window (its own native surface) laid over this popup lets it
        float above the webview where clicked.
        """
        from .onigiri_color_picker import OnigiriColorDialog

        host = QWidget(None)
        host.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        host.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        host.setGeometry(self.frameGeometry())
        host.show()
        host.raise_()
        host.activateWindow()
        try:
            return OnigiriColorDialog.getColor(current, host)
        finally:
            host.close()
            host.deleteLater()
            self.raise_()
            self.activateWindow()

    def _pick_color(self):
        """Custom note colour; the chosen hex drives both marker and fill."""
        try:
            current = self.note.get("color", "") or _accent_color()
            chosen, ok = self._open_color_dialog(current)
            if ok and chosen:
                self.web.eval("window.hashiSetColor && window.hashiSetColor(%s);" % json.dumps(chosen))
        except Exception as e:
            print(f"Hashi Notes: color picker error: {e}")

    def _pick_highlight(self):
        """Custom text-highlight colour; applied to the editor's saved selection."""
        try:
            chosen, ok = self._open_color_dialog("#fff3b0")
            if ok and chosen:
                self.web.eval("window.hashiApplyHighlight && window.hashiApplyHighlight(%s);" % json.dumps(chosen))
        except Exception as e:
            print(f"Hashi Notes: highlight picker error: {e}")

    def _on_icon_selected(self, value, mode="inline"):
        if not value:
            return
        if mode == "title":
            self.web.eval("window.hashiSetIcon && window.hashiSetIcon(%s);" % json.dumps(value))
        else:
            self.web.eval(
                "window.hashiInsertIcon && window.hashiInsertIcon(%s);"
                % json.dumps(self._icon_html(value))
            )

    def _icon_html(self, value):
        """Turns a DeckIconPickerDialog value (emoji:X / system:x.svg / file) into
        an inline chip the editor can insert."""
        if value.startswith("emoji:"):
            em = value.split(":", 1)[1]
            asset = _emoji_sprite_map().get(em)
            if asset:
                uri = _addon_uri(f"system_files/emojis/{asset}")
                return f'<img class="hashi-inline-icon" src="{uri}">'
            return em
        if value.startswith("system:"):
            uri = _addon_uri(f"system_files/system_icons/available_for_users/{value.split(':', 1)[1]}")
            # currentColor SVGs are masked so they follow the editor text colour
            return (
                f'<span class="hashi-inline-icon hashi-sysmask" '
                f'style="-webkit-mask-image:url(\'{uri}\');mask-image:url(\'{uri}\')"></span>'
            )
        uri = _addon_uri(f"user_files/custom_deck_icons/{value}")
        return f'<img class="hashi-inline-icon" src="{uri}">'


# ─── Editor pop-up ────────────────────────────────────────────────────────────

class HashiNotePopup(QDialog, _HashiNoteEditorMixin):
    """Frameless floating editor with a slim native chrome.

    A slim native top bar handles dragging + close (the AnkiWebView below would
    otherwise swallow the mouse events); the profile bar + editor live inside
    the webview HTML.
    """

    def __init__(self, note, context="reviewer", parent=None):
        super().__init__(parent or mw)
        self.context = context
        self.note = note
        self._drag_pos = None
        self._skip_close_refocus = False
        self.dark = _is_dark_mode()
        self.pal = pal = _palette(self.dark)

        self.setWindowTitle(tr("hashi_notes_title", "Hashi Notes"))
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            # macOS animates in a native drop shadow for frameless windows,
            # recomputed from the (irregular, rounded/translucent) content -
            # that recompute is what shows up as a glitch/flash right as the
            # window appears. We draw our own rounded border on the shell, so
            # the native shadow isn't needed.
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(460, 620)
        self.setMinimumSize(360, 440)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)

        # Pre-compute the shell's tint (if the note has a colour) so it paints
        # correctly on the very first frame - waiting for the webview's JS to
        # report it back over the bridge (hashi:set_shell:) is a visible
        # flicker from the default shell colour to the tinted one.
        initial_shell_bg = None
        bg_color = (note.get("bg_color") or "").strip()
        if bg_color:
            try:
                initial_shell_bg = _fill_tint(bg_color, self.dark)
            except Exception:
                initial_shell_bg = None

        self.shell = shell = QFrame()
        shell.setObjectName("hashiShell")
        shell.setStyleSheet(self._shell_qss(initial_shell_bg))
        outer.addWidget(shell)

        shell_layout = QVBoxLayout(shell)
        shell_layout.setContentsMargins(6, 6, 6, 6)
        shell_layout.setSpacing(4)

        self.topbar = QFrame()
        self.topbar.setObjectName("hashiTopbar")
        self.topbar.setFixedHeight(34)
        self.topbar.setCursor(Qt.CursorShape.SizeAllCursor)
        top = QHBoxLayout(self.topbar)
        top.setContentsMargins(10, 0, 6, 0)
        title = QLabel(tr("hashi_notes_title", "Hashi Notes"))
        title.setObjectName("hashiTitle")
        browse_btn = QToolButton()
        browse_btn.setIcon(_tinted_icon(_system_icon_path("browse.svg"), pal["fg2"], 15))
        browse_btn.setFixedSize(26, 26)
        browse_btn.setCursor(Qt.CursorShape.ArrowCursor)
        browse_btn.setToolTip(tr("hashi_browse_previous", "Browse previous notes"))
        browse_btn.clicked.connect(self._open_gallery)
        close_btn = QToolButton()
        close_btn.setText("✕")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(Qt.CursorShape.ArrowCursor)
        close_btn.setToolTip(tr("hashi_close", "Close"))
        close_btn.clicked.connect(self.close)
        top.addWidget(title)
        top.addStretch()
        top.addWidget(browse_btn)
        top.addWidget(close_btn)
        shell_layout.addWidget(self.topbar)

        self.web = AnkiWebView(self)
        try:
            self.web.page().setBackgroundColor(QColor(Qt.GlobalColor.transparent))
        except Exception:
            pass
        shell_layout.addWidget(self.web, 1)

        self.web.stdHtml(_render_html("hashi_notes.html", self.note, self.dark))
        self.web.set_bridge_command(self._on_bridge, self)

    def present(self, anchor):
        """Shows the popup at its centered position.

        A previous version of this method moved the window to an off-screen
        position (e.g. -10000,-10000) before showing it, then repositioned it
        once ready, to try to avoid first-frame rendering glitches. That
        turned out to be the cause of a crash: teleporting a translucent
        frameless window across such a large distance right as mouse
        enter/leave events are being dispatched corrupted macOS's native
        cursor-image handling (crash in QWindowPrivate::setCursor ->
        QImage::toCGImage -> CGImageCreate). A stable, boring show sequence
        is worth more than eliminating the last bit of visual polish."""
        _position_centered(self, anchor)
        self.show()
        self.raise_()
        self.activateWindow()

    def _shell_qss(self, bg=None):
        pal = self.pal
        shell_bg = bg or pal["shell"]
        border = bg or pal["border"]
        return f"""
            QFrame#hashiShell {{
                background: {shell_bg};
                border: 1px solid {border};
                border-radius: 20px;
            }}
            QFrame#hashiTopbar {{ background: transparent; }}
            QLabel#hashiTitle {{ color: {pal['fg']}; font-size: 14px; font-weight: 700; background: transparent; }}
            QToolButton {{ background: transparent; border: none; border-radius: 12px; padding: 3px;
                color: {pal['fg2']}; font-size: 16px; }}
            QToolButton:hover {{ background: {pal['hover']}; }}
        """

    def _set_shell_bg(self, hex_color):
        """Tints the native shell to match the note's chosen fill (post-it look)."""
        try:
            hex_color = (hex_color or "").strip()
            self.shell.setStyleSheet(self._shell_qss(hex_color or None))
        except Exception as e:
            print(f"Hashi Notes: shell tint error: {e}")

    # --- window dragging via the native top bar ---
    def _topbar_at(self, event):
        pos = event.position().toPoint()
        return self.topbar.geometry().contains(self.topbar.mapFrom(self, pos))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._topbar_at(event):
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def closeEvent(self, event):
        # Flush any pending edit before closing, then return focus to the opener.
        try:
            self.web.eval("window.hashiFlush && window.hashiFlush();")
        except Exception:
            pass
        anchor = self.parent()
        super().closeEvent(event)
        if anchor is not None and not self._skip_close_refocus:
            try:
                top = anchor.window()
                top.raise_()
                top.activateWindow()
            except Exception:
                pass

    def _open_gallery(self):
        """Flushes the note being edited, then swaps this floating popup out
        for the Gallery (past notes live there, not in the popup)."""
        try:
            self.web.eval("window.hashiFlush && window.hashiFlush();")
        except Exception:
            pass
        open_hashi_gallery(self.parent())
        # Closing normally re-focuses the anchor window (mw), which would pop
        # it in front of the Gallery we just opened - skip that here.
        self._skip_close_refocus = True
        self.close()

    # --- bridge from the editor JS ---
    def _on_bridge(self, cmd):
        try:
            if self._handle_note_bridge(cmd):
                return
            if cmd == "hashi:open_gallery":
                self._open_gallery()
                return
            if cmd == "hashi:close":
                self.close()
                return
        except Exception as e:
            print(f"Hashi Notes: bridge error ({cmd[:40]}): {e}")


# ─── Gallery dialog ───────────────────────────────────────────────────────────

class HashiGalleryDialog(QDialog, _HashiNoteEditorMixin):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.dark = _is_dark_mode()
        self.note = None
        self.current_view = "active"  # track Notes vs Trash view
        self.setWindowTitle(tr("hashi_notes_title", "Hashi Notes"))
        self.setMinimumSize(720, 560)
        self.resize(880, 640)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.web = AnkiWebView(self)
        layout.addWidget(self.web, 1)

        self._reload()
        self.web.set_bridge_command(self._on_bridge, self)

    def _reload(self):
        purge_expired()
        self.note = None
        data = {
            "notes": load_notes(),
            "trashed": load_notes(include_trashed=True),
        }
        ctx = _build_context_json(self.dark)
        ctx["initialView"] = self.current_view  # restore the Notes/Trash view
        self.web.stdHtml(_render_html("hashi_gallery.html", data, self.dark, ctx))

    def _show_editor(self, note):
        """Opens a note (new or existing) inside this dialog's own webview, in
        place of the grid. The Reviewer's button is the only entry point that
        still spawns the separate floating HashiNotePopup."""
        self.note = note
        self.web.stdHtml(_render_html("hashi_notes.html", note, self.dark))

    def _show_grid(self):
        if self.note is None:
            self._reload()
            return
        try:
            self.web.eval("window.hashiFlush && window.hashiFlush(); window.hashiFadeOut && window.hashiFadeOut();")
        except Exception:
            pass
        QTimer.singleShot(140, self._reload)

    def _on_bridge(self, cmd):
        try:
            if self.note is not None and self._handle_note_bridge(cmd):
                return
            if cmd == "hashi:back":
                self._show_grid()
                return
            if cmd == "hashi:new":
                note = save_note(_new_note())
                self._show_editor(note)
                return
            if cmd.startswith("hashi:open:"):
                self._show_editor(get_note(cmd.split(":", 2)[2]))
                return
            if cmd.startswith("hashi:trash:"):
                trash_note(cmd.split(":", 2)[2])
                self._reload()
                return
            if cmd.startswith("hashi:restore:"):
                restore_note(cmd.split(":", 2)[2])
                self._reload()
                return
            if cmd.startswith("hashi:delete:"):
                delete_note(cmd.split(":", 2)[2])
                self._reload()
                return
            if cmd.startswith("hashi:set_sort:"):
                self._save_sort(cmd.split(":", 2)[2])
                return
            if cmd.startswith("hashi:set_view:"):
                self.current_view = cmd.split(":", 2)[2]
                return
        except Exception as e:
            print(f"Hashi Notes: gallery bridge error ({cmd[:40]}): {e}")

    def closeEvent(self, event):
        if self.note is not None:
            try:
                self.web.eval("window.hashiFlush && window.hashiFlush();")
            except Exception:
                pass
        super().closeEvent(event)

    def _save_sort(self, key):
        if key not in SORT_KEYS:
            return
        try:
            conf = config.get_config()
            prefs = conf.setdefault("hashi_notes", {})
            prefs["default_sort"] = key
            config.write_config(conf)
        except Exception as e:
            print(f"Hashi Notes: sort save error: {e}")


# ─── Entry points ─────────────────────────────────────────────────────────────

def open_hashi_note_popup(context="reviewer", parent=None, note=None):
    global _popup
    try:
        if _popup is not None:
            _popup.close()
    except Exception:
        pass
    if note is None:
        note = save_note(_new_note())
    anchor = parent or mw
    _popup = HashiNotePopup(note, context=context, parent=anchor)
    _popup.present(anchor)
    return _popup


def open_hashi_gallery(parent=None):
    global _gallery
    try:
        if _gallery is not None:
            _gallery.close()
    except Exception:
        pass
    _gallery = HashiGalleryDialog(parent or mw)
    _gallery.show()
    _gallery.raise_()
    _gallery.activateWindow()
    return _gallery


def _position_centered(dialog, anchor=None):
    """Places the pop-up in the center of its screen, before it is shown, so
    it doesn't visibly jump into place after appearing wherever Qt/the OS
    would otherwise put it first.

    dialog.screen() is unreliable before the widget has actually been shown,
    so we prefer the (already on-screen) anchor's screen when available."""
    from aqt.qt import QApplication

    screen = None
    try:
        if anchor is not None:
            screen = anchor.window().screen()
    except Exception:
        screen = None
    if screen is None:
        screen = dialog.screen() or (QApplication.instance() and QApplication.instance().primaryScreen())
    if screen is None:
        return
    avail = screen.availableGeometry()
    x = avail.left() + (avail.width() - dialog.width()) // 2
    y = avail.top() + (avail.height() - dialog.height()) // 2
    dialog.move(x, y)
