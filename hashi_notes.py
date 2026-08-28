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
    Qt,
    QTimer,
    QVBoxLayout,
)
from aqt.webview import AnkiWebView

from . import config
from . import safe_storage
from .translations import tr


# ─── Constants ────────────────────────────────────────────────────────────────

CONF_KEY = "onigiri_hashi_notes"
CONF_GROUPS_KEY = "onigiri_hashi_note_groups"
USER_FILES_SUBDIR = "hashi_notes"
RETENTION_CHOICES = (7, 30, 0)  # 0 == Never

SORT_KEYS = ("manual", "age", "tags", "priority", "title")
PRIORITY_ORDER = {"high": 0, "med": 1, "low": 2, "none": 3}

_popup = None
_gallery = None


# ─── Small utilities ──────────────────────────────────────────────────────────

def _addon_root():
    return os.path.dirname(__file__)


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

        return effective_night_mode(conf or config.get_config_readonly())
    except Exception:
        return False


def _accent_color(conf=None):
    conf = conf or config.get_config_readonly()
    mode = "dark" if _is_dark_mode(conf) else "light"
    return conf.get("colors", {}).get(mode, {}).get("--accent-color", "#00A982")


# ─── Preferences (local config) ───────────────────────────────────────────────

def get_prefs(conf=None):
    conf = conf or config.get_config_readonly()
    defaults = config.DEFAULTS.get("hashi_notes", {})
    prefs = conf.get("hashi_notes", {})
    if not isinstance(prefs, dict):
        prefs = {}
    merged = dict(defaults)
    merged.update(prefs)
    return merged


def default_retention():
    """0 == Never: notes are kept forever unless the user picks a countdown."""
    try:
        value = int(get_prefs().get("retention_default", 0))
    except Exception:
        value = 0
    return value if value in RETENTION_CHOICES else 0


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
        safe_storage.atomic_write_json(path, note)
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
        # Gallery layout: which group card the note lives in ("" == top level)
        # and its manual position inside that context.
        "group": "",
        "order": 0,
    }


def _normalize(note):
    """Fills missing keys so older/partial notes stay valid."""
    base = _new_note()
    base.update({k: v for k, v in note.items() if k in base})
    base["id"] = note.get("id") or base["id"]
    if base["retention"] not in RETENTION_CHOICES:
        base["retention"] = 0
    if base["priority"] not in PRIORITY_ORDER:
        base["priority"] = "none"
    if not isinstance(base["tags"], list):
        base["tags"] = []
    if not isinstance(base["linked_cards"], list):
        base["linked_cards"] = []
    if not isinstance(base["group"], str):
        base["group"] = ""
    base["order"] = _as_int(base["order"])
    return base


def _as_int(value, fallback=0):
    try:
        return int(value)
    except Exception:
        return fallback


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


# ─── Gallery groups + manual layout ───────────────────────────────────────────
#
# A group is only a gallery affordance: a folder card that holds notes. Notes
# keep living in the single flat note list; membership is the note's "group"
# field, so nothing else in the add-on has to know groups exist.

def load_groups():
    if not mw or not mw.col:
        return []
    try:
        raw = mw.col.conf.get(CONF_GROUPS_KEY, [])
    except Exception:
        return []
    groups = []
    for group in raw if isinstance(raw, list) else []:
        if isinstance(group, dict) and group.get("id"):
            groups.append({
                "id": str(group["id"]),
                "title": str(group.get("title") or ""),
                "order": _as_int(group.get("order")),
            })
    return groups


def _write_groups(groups):
    if not mw or not mw.col:
        return
    try:
        mw.col.conf[CONF_GROUPS_KEY] = groups
        mw.col.setMod()
    except Exception as e:
        print(f"Hashi Notes: group save error: {e}")


def apply_layout(payload):
    """Stores the gallery's drag result: per-note group/order plus the group
    list. Never touches updated_at — moving a card is not editing a note."""
    if not isinstance(payload, dict):
        return
    patches = payload.get("notes") or {}
    if not isinstance(patches, dict):
        patches = {}
    groups, seen = [], set()
    for group in payload.get("groups") or []:
        if not isinstance(group, dict):
            continue
        gid = str(group.get("id") or "").strip()
        if not gid or gid in seen:
            continue
        seen.add(gid)
        groups.append({
            "id": gid,
            "title": str(group.get("title") or "")[:80],
            "order": _as_int(group.get("order")),
        })

    notes, touched = _read_all(), []
    for note in notes:
        if not isinstance(note, dict):
            continue
        patch = patches.get(note.get("id"))
        if not isinstance(patch, dict):
            continue
        group = str(patch.get("group") or "")
        if group not in seen:
            group = ""
        order = _as_int(patch.get("order"))
        if note.get("group", "") == group and _as_int(note.get("order")) == order:
            continue
        note["group"], note["order"] = group, order
        touched.append(note)

    # A group with no members left is dead weight; drop it.
    used = {n.get("group") for n in notes if isinstance(n, dict) and n.get("group")}
    groups = [g for g in groups if g["id"] in used]

    _write_all(notes)
    _write_groups(groups)
    for note in touched:
        _write_json_mirror(_normalize(note))


# ─── Retention / trash sweep ──────────────────────────────────────────────────

def _expiry(note):
    retention = note.get("retention", 0)
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
            from . import config as _config

            filename = _config.themed_asset(
                conf.get, "modern_menu_profile_bg_image", dark,
                dynamic_key="modern_menu_profile_bg_dynamic_mode",
            )
            path = os.path.join(_addon_root(), "user_files", "profile_bg", filename) if filename else ""
            image = _file_data_uri(path)
        return {"color": color, "image": image, "opacity": opacity, "blur": blur}
    except Exception:
        return {"color": _accent_color(), "image": "", "opacity": 100, "blur": 0}


def _profile_name():
    try:
        conf = mw.col.conf if (mw and mw.col) else {}
        name = conf.get("modern_menu_profile_name", "") or config.get_config_readonly().get("userName", "")
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


# Direct ports of paperForTheme() / textOnPaper() / mixHex() from
# hashi_notes.html. The single-note widget is meant to be the pinned note, so it
# has to resolve the exact same paper colour the editor paints - not a lookalike
# tint. Any change to the JS side must be mirrored here or the two drift apart.
_DARK_NOTE_COLORS = {
    "#ffd2d2": "#704146", "#ffdfbf": "#704d38", "#fff0a8": "#67582d",
    "#c9efcf": "#345e48", "#c7e8f7": "#315569", "#d4dcff": "#414979",
    "#e6d0f5": "#59436b", "#f5d0e0": "#6b4156", "#d8dcd9": "#4b504c",
}


def _normalize_hex(value):
    h = str(value or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h.lower() if re.fullmatch(r"[0-9a-fA-F]{6}", h) else ""


def _mix_hex(a, b, amount):
    x, y = _hex_to_rgb(a), _hex_to_rgb(b)
    return _rgb_to_hex(tuple(x[i] + (y[i] - x[i]) * amount for i in range(3)))


def _paper_for_theme(value, dark):
    """The note's paper fill: the raw colour in light mode, its hand-picked dark
    counterpart (or a computed fallback) in dark mode."""
    source = _normalize_hex(value)
    if not source or not dark:
        return source
    return _DARK_NOTE_COLORS.get(source) or _mix_hex(source, "#23211f", 0.52)


_INK_DARK = "#241f1b"
_INK_LIGHT = "#fffdf7"


def _rel_luminance(color):
    channels = []
    for n in _hex_to_rgb(color):
        v = n / 255
        channels.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(a, b):
    """WCAG contrast ratio between two hex colours (1 - 21)."""
    la, lb = _rel_luminance(a), _rel_luminance(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def _text_on_paper(color):
    """Ink colour for a given paper: whichever of the two inks actually reads
    better on it, not a fixed luminance cut-off.

    The old `luminance > 0.38` split put light ink on mid-tone papers where
    dark ink is the more legible of the two - a paper at luminance .38 gave
    white text a 2.4:1 ratio. The real crossover between these two inks sits
    near .21, and comparing the ratios finds it without hard-coding it. When
    even the better ink stays under 4.5:1 (mid-tone papers have no comfortable
    ink), it is pushed to pure black/white, which is the most either side can
    give."""
    dark_ratio, light_ratio = _contrast(_INK_DARK, color), _contrast(_INK_LIGHT, color)
    ink, best = (_INK_DARK, dark_ratio) if dark_ratio >= light_ratio else (_INK_LIGHT, light_ratio)
    if best >= 4.5:
        return ink
    extreme = "#000000" if ink == _INK_DARK else "#ffffff"
    return extreme if _contrast(extreme, color) > best else ink


def _muted_ink(fg, paper, amount, min_ratio):
    """Ink faded toward the paper for secondary text, but never faded past
    `min_ratio` - on a mid-tone paper a flat 30/48% mix washes the text out
    entirely, so the mix backs off until the contrast holds."""
    step = amount
    while step > 0:
        candidate = _mix_hex(fg, paper, step)
        if _contrast(candidate, paper) >= min_ratio:
            return candidate
        step -= 0.06
    return fg


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


def _web_icon_catalog():
    """Icon filenames exposed to the in-page picker.

    Hashi Notes no longer opens native Qt picker dialogs.  Only basenames from
    the two known icon directories are sent to JavaScript, which keeps the
    picker fast and prevents arbitrary paths from reaching the webview.
    """
    catalogs = []
    for rel_dir, extensions in (
        (("system_files", "system_icons", "available_for_users"), {".svg"}),
        (("user_files", "custom_deck_icons"), {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif"}),
    ):
        path = os.path.join(_addon_root(), *rel_dir)
        try:
            names = sorted(
                name for name in os.listdir(path)
                if os.path.isfile(os.path.join(path, name))
                and os.path.splitext(name)[1].lower() in extensions
            )
        except Exception:
            names = []
        catalogs.append(names)
    return catalogs


# Every user-facing string the two webviews (hashi_notes.html / hashi_gallery.html)
# render. Injected into the context JSON as ctx.strings so the HTML/JS can look
# them up; English is kept inline in the templates as a fallback.
_WEBVIEW_STRING_KEYS = (
    "hashi_notes_title", "hashi_notes_short", "hashi_back_to_notes",
    "hashi_note_colors", "hashi_set_note_icon",
    "hashi_editor_placeholder", "hashi_keep", "hashi_priority",
    "hashi_prio_low", "hashi_prio_med", "hashi_prio_high",
    "hashi_tags_placeholder", "hashi_color_label", "hashi_custom_color",
    "hashi_never", "hashi_days_suffix", "hashi_no_cards",
    "hashi_view_trash", "hashi_sort_prefix", "hashi_sort_recent",
    "hashi_sort_tags", "hashi_sort_priority", "hashi_sort_title",
    "hashi_empty_note", "hashi_kept", "hashi_days_left_suffix",
    "hashi_new_note", "hashi_trash_empty", "hashi_restore",
    "hashi_delete_forever", "hashi_move_to_trash", "hashi_profile_you",
    "hashi_months", "hashi_today", "hashi_yesterday", "hashi_days_ago",
    "hashi_quick_note", "hashi_saved", "hashi_note_title_placeholder",
    "hashi_note_details", "hashi_title_label", "hashi_icon_label",
    "hashi_no_icon", "hashi_paper_color", "hashi_default_paper",
    "hashi_hex_color", "hashi_close", "hashi_browse_previous",
    "search_icons_placeholder", "hashi_sort_manual", "hashi_search_notes",
    "hashi_new_note_sub", "hashi_sort_age", "hashi_saving", "no_matching_icons",
)


def _webview_strings():
    return {key: tr(key) for key in _WEBVIEW_STRING_KEYS}


def _build_context_json(dark):
    pal = _palette(dark)
    prefs = get_prefs()
    system_icons, custom_icons = _web_icon_catalog()
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
        "systemIcons": system_icons,
        "customIcons": custom_icons,
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
    try:
        from .fonts import poppins_font_face_css

        pkg = mw.addonManager.addonFromModule(__name__)
        font_face_css = poppins_font_face_css(pkg)
    except Exception:
        font_face_css = ""
    return (
        template
        .replace("/*__HASHI_FONT_FACE__*/", font_face_css)
        .replace("/*__HASHI_CONTEXT__*/null", _safe_json(ctx))
        .replace("/*__HASHI_DATA__*/null", _safe_json(note_data))
    )


# ─── Shared note-editor bridge handling ───────────────────────────────────────
#
# Both the floating popup and the Gallery's embedded editor render
# hashi_notes.html into an AnkiWebView and need to answer the same save and
# card-search commands. Icon, note-colour, and highlight pickers now live
# entirely inside the page.

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
        return False


_WINDOW_RESIZE_EDGES = {
    "top": Qt.Edge.TopEdge,
    "bottom": Qt.Edge.BottomEdge,
    "left": Qt.Edge.LeftEdge,
    "right": Qt.Edge.RightEdge,
    "topleft": Qt.Edge.TopEdge | Qt.Edge.LeftEdge,
    "topright": Qt.Edge.TopEdge | Qt.Edge.RightEdge,
    "bottomleft": Qt.Edge.BottomEdge | Qt.Edge.LeftEdge,
    "bottomright": Qt.Edge.BottomEdge | Qt.Edge.RightEdge,
}


def _start_window_drag(dialog):
    """Drags a frameless popup by polling the *global* cursor position.

    The obvious implementations both fail here. windowHandle().startSystemMove()
    needs the native mouse-press that started the gesture, which is already gone
    by the time the async pycmd round-trip reaches Python, so the window never
    moves. Tracking mousemove/pointermove in the page instead stops the moment
    the cursor leaves the webview, which is exactly when the window "falls
    behind" - and pointer capture doesn't rescue it either, because Chromium
    fires pointercancel as soon as the native window starts moving under the
    captured pointer.

    QCursor.pos() is screen-global and QApplication.mouseButtons() reports the
    real button state, so a short-interval timer keeps tracking no matter where
    the pointer goes, and stops cleanly when the button is released anywhere."""
    from aqt.qt import QApplication, QCursor

    existing = getattr(dialog, "_drag_timer", None)
    if existing is not None:
        existing.stop()

    origin_cursor = QCursor.pos()
    origin_window = dialog.pos()
    timer = QTimer(dialog)
    timer.setInterval(8)

    def _tick():
        if not (QApplication.mouseButtons() & Qt.MouseButton.LeftButton):
            timer.stop()
            dialog._drag_timer = None
            return
        try:
            delta = QCursor.pos() - origin_cursor
            dialog.move(origin_window + delta)
        except RuntimeError:  # dialog closed mid-drag
            timer.stop()
            dialog._drag_timer = None

    timer.timeout.connect(_tick)
    dialog._drag_timer = timer
    timer.start()


def _handle_web_window_command(dialog, cmd):
    """Executes the small set of window actions initiated by web chrome."""
    if cmd == "hashi:window_drag_start":
        _start_window_drag(dialog)
        return True
    if cmd.startswith("hashi:window_resize:"):
        edge = _WINDOW_RESIZE_EDGES.get(cmd.rsplit(":", 1)[-1])
        handle = dialog.windowHandle()
        if edge is not None and handle is not None and not dialog.isMaximized():
            handle.startSystemResize(edge)
        return True
    if cmd == "hashi:window_minimize":
        dialog.showMinimized()
        return True
    if cmd == "hashi:window_toggle_maximize":
        if dialog.isMaximized():
            dialog.showNormal()
        else:
            dialog.showMaximized()
        try:
            dialog.web.eval(
                "window.hashiSetMaximized && window.hashiSetMaximized(%s);"
                % ("true" if dialog.isMaximized() else "false")
            )
        except Exception:
            pass
        return True
    return False


# ─── Editor pop-up ────────────────────────────────────────────────────────────

class HashiNotePopup(QDialog, _HashiNoteEditorMixin):
    """Frameless floating editor whose complete visible surface is web UI."""

    def __init__(self, note, context="reviewer", parent=None):
        super().__init__(parent or mw)
        # Set before any resize()/move() below: those can deliver geometry
        # events synchronously, and the handlers read this state.
        self._last_geom = None      # see resizeEvent()
        self._restoring_geom = False
        self.context = context
        self.note = note
        self._skip_close_refocus = False
        self.dark = _is_dark_mode()

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
        self.resize(510, 660)
        self.setMinimumSize(390, 500)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.web = AnkiWebView(self)
        try:
            self.web.page().setBackgroundColor(QColor(Qt.GlobalColor.transparent))
        except Exception:
            pass
        outer.addWidget(self.web, 1)

        # See present(): the window is shown fully transparent and only revealed
        # once the page reports its first painted frame (hashi:ready).
        self._revealed = False

        web_ctx = _build_context_json(self.dark)
        web_ctx["hostMode"] = "popup"
        self.web.stdHtml(_render_html("hashi_notes.html", self.note, self.dark, web_ctx))
        self.web.set_bridge_command(self._on_bridge, self)

    def moveEvent(self, event):
        # Re-anchor on a *pure* move (our window drag) so the next resize is
        # measured from where the window actually is now. The size check is what
        # makes this ordering-proof: a native top-edge drag changes position and
        # size together and can deliver its move event first, so re-anchoring on
        # any move at all would hide the very change resizeEvent must reject.
        super().moveEvent(event)
        if self._restoring_geom or self._last_geom is None:
            return
        if self.size() == self._last_geom.size():
            self._last_geom = self.geometry()

    def resizeEvent(self, event):
        """Rejects resizes that would move the window's top edge.

        Deleting the top/top-corner handles from hashi_notes.html is not enough:
        the window is frameless but still resizable, so macOS gives its NSWindow
        the resizable style mask and lets the user drag *any* borderless edge
        natively, with no HTML involved.

        A top-edge drag is the only gesture that changes y and height together
        (our own window drag changes position only, and the remaining bottom
        handles change height only), so that pair is a reliable signal: restore
        the previous geometry and the top edge simply never budges."""
        super().resizeEvent(event)
        if self._restoring_geom:
            return
        previous = self._last_geom
        if previous is not None and self.y() != previous.y():
            self._restoring_geom = True
            try:
                self.setGeometry(previous)
            finally:
                self._restoring_geom = False
            return
        self._last_geom = self.geometry()

    def _reveal(self):
        """Makes the (already shown, fully transparent) window visible."""
        if self._revealed:
            return
        self._revealed = True
        try:
            self.setWindowOpacity(1.0)
        except RuntimeError:
            pass  # dialog was closed/deleted while we were waiting

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
        is worth more than eliminating the last bit of visual polish.

        Keeping the window *hidden* until the webview finished loading does not
        work either: QtWebEngine does not render (and throttles rAF) for a page
        whose window is not visible, so the first painted frame still lands
        after show() and the user sees the empty shell for a few hundred ms -
        the "glitch". The window is therefore shown immediately but with
        windowOpacity 0, which keeps the page visible to WebEngine while
        invisible to the user; hashi_notes.html calls pycmd("hashi:ready")
        once its first frame is painted, and _reveal() flips the opacity."""
        _position_centered(self, anchor)
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        # Safety net: a JS error (or an old cached page) must never leave the
        # window permanently invisible.
        QTimer.singleShot(900, self._reveal)

    def closeEvent(self, event):
        # A close that lands while present() is still waiting for hashi:ready
        # must not be re-revealed by the pending timer.
        self._revealed = True
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
            if _handle_web_window_command(self, cmd):
                return
            if cmd == "hashi:ready":
                self._reveal()
                return
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


def _id_list(payload):
    return [part for part in str(payload or "").split(",") if part]


# ─── Gallery dialog ───────────────────────────────────────────────────────────

class HashiGalleryDialog(QDialog, _HashiNoteEditorMixin):
    def __init__(self, parent=None):
        super().__init__(parent or mw)
        self.dark = _is_dark_mode()
        self.note = None
        self.current_view = "active"  # track Notes vs Trash view
        self.setWindowTitle(tr("hashi_notes_title", "Hashi Notes"))
        # The gallery is a conventional application window/page. Only the
        # compact quick-note editor uses custom floating web chrome.
        self.setWindowFlags(Qt.WindowType.Window)
        self.setMinimumSize(720, 560)
        self.resize(960, 700)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.web = AnkiWebView(self)
        try:
            self.web.page().setBackgroundColor(QColor(_palette(self.dark)["bg"]))
        except Exception:
            pass
        layout.addWidget(self.web, 1)

        self._reload()
        self.web.set_bridge_command(self._on_bridge, self)

    def _reload(self):
        purge_expired()
        self.note = None
        data = {
            "notes": load_notes(),
            "trashed": load_notes(include_trashed=True),
            "groups": load_groups(),
        }
        ctx = _build_context_json(self.dark)
        ctx["initialView"] = self.current_view  # restore the Notes/Trash view
        ctx["hostMode"] = "gallery"
        self.web.stdHtml(_render_html("hashi_gallery.html", data, self.dark, ctx))

    def _show_editor(self, note):
        """Opens a note (new or existing) inside this dialog's own webview, in
        place of the grid. The Reviewer's button is the only entry point that
        still spawns the separate floating HashiNotePopup."""
        self.note = note
        ctx = _build_context_json(self.dark)
        ctx["hostMode"] = "gallery-editor"
        self.web.stdHtml(_render_html("hashi_notes.html", note, self.dark, ctx))

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
            if _handle_web_window_command(self, cmd):
                return
            if cmd == "hashi:close":
                self.close()
                return
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
            if cmd.startswith("hashi:layout:"):
                # Fired by every drag/group/reorder. The page already shows the
                # new arrangement, so this only persists — no reload.
                try:
                    apply_layout(json.loads(cmd[len("hashi:layout:"):]))
                except Exception as e:
                    print(f"Hashi Notes: layout parse error: {e}")
                return
            if cmd.startswith("hashi:trash_many:"):
                for note_id in _id_list(cmd[len("hashi:trash_many:"):]):
                    trash_note(note_id)
                self._reload()
                return
            if cmd.startswith("hashi:restore_many:"):
                for note_id in _id_list(cmd[len("hashi:restore_many:"):]):
                    restore_note(note_id)
                self._reload()
                return
            if cmd.startswith("hashi:delete_many:"):
                for note_id in _id_list(cmd[len("hashi:delete_many:"):]):
                    delete_note(note_id)
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


# ─── Dashboard widget (deck browser, HTML) ────────────────────────────────────
#
# Two modes, both driven by hashi_widget_style in the add-on config:
#   "gallery" - a compact card grid of the most recently updated notes
#   "single"  - one pinned note with a longer excerpt
#
# The surface colors arrive as --hashiw-* CSS variables from
# patcher.generate_dynamic_css, so the widget follows Widget Color and Effect when
# the user keeps that sync on.

_HASHI_TAG_RE = re.compile(r"<[^>]+>")


def widget_style(conf=None) -> dict:
    style = (conf or config.get_config_readonly()).get("hashi_widget_style", {})
    return style if isinstance(style, dict) else {}


def _plain_excerpt(body_html: str, limit: int = 160) -> str:
    """Body text with markup stripped, collapsed to a single line."""
    text = _HASHI_TAG_RE.sub(" ", str(body_html or ""))
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > limit:
        text = text[:limit].rstrip() + "…"
    return text


def _widget_icon_html(value: str) -> str:
    """Note icon as a small chip. Mirrors _HashiNoteEditorMixin._icon_html."""
    value = str(value or "")
    if not value:
        return ""
    if value.startswith("emoji:"):
        glyph = value.split(":", 1)[1]
        asset = _emoji_sprite_map().get(glyph)
        if asset:
            return f'<img class="hashi-widget-icon" src="{_addon_uri("system_files/emojis/" + asset)}">'
        return f'<span class="hashi-widget-icon">{html.escape(glyph)}</span>'
    if value.startswith("system:"):
        uri = _addon_uri(f"system_files/system_icons/available_for_users/{value.split(':', 1)[1]}")
        return (
            f'<span class="hashi-widget-icon hashi-widget-icon-mask" '
            f'style="-webkit-mask-image:url(\'{uri}\');mask-image:url(\'{uri}\')"></span>'
        )
    uri = _addon_uri(f"user_files/custom_deck_icons/{value}")
    return f'<img class="hashi-widget-icon" src="{uri}">'


def _widget_date_label(iso: str) -> str:
    """Short relative age, matching the gallery's "today / 3d ago" wording."""
    parsed = _parse_iso(iso)
    if not parsed:
        return ""
    delta = datetime.now(timezone.utc) - parsed
    days = delta.days
    if days <= 0:
        return tr("hashi_today", "today")
    if days == 1:
        return tr("hashi_yesterday", "yesterday")
    return tr("hashi_days_ago", "{}d ago").format(days)


def widget_notes(style=None):
    """Notes the widget should display, newest first, already limited."""
    style = style if isinstance(style, dict) else widget_style()
    notes = load_notes()
    notes.sort(key=lambda n: str(n.get("updated_at") or n.get("created_at") or ""), reverse=True)
    if style.get("mode") == "single":
        note_id = str(style.get("note_id") or "")
        if note_id:
            for note in notes:
                if note.get("id") == note_id:
                    return [note]
        # Falls back to the newest note so a deleted pin never blanks the widget.
        return notes[:1]
    try:
        limit = int(style.get("limit", 4))
    except (TypeError, ValueError):
        limit = 4
    return notes[:max(1, min(8, limit))]


def render_widget_html(row_span: int = 1, col_span: int = 1) -> str:
    style = widget_style()
    mode = "single" if style.get("mode") == "single" else "gallery"
    show_excerpt = bool(style.get("show_excerpt", True))
    show_icon = bool(style.get("show_icon", True))
    show_date = bool(style.get("show_date", True))

    title_html = html.escape(tr("hashi_notes_title", "Hashi Notes"), quote=False)
    notes = widget_notes(style)

    # A note's colour tints the whole card (the same fill the editor pop-up
    # paints its shell with), so the widget reads as a miniature of the pop-up
    # instead of a plain card with an accent bar on its edge.
    tint_dark = _is_dark_mode() if bool(style.get("dynamic", True)) else False

    def _note_style(note):
        """Paints a note in its real paper colour, for both widget modes.

        Both the single widget and the gallery cards resolve the exact colour
        the editor paints (_paper_for_theme mirrors its paperForTheme) instead
        of a lookalike tint. The ink has to be derived from that fill too: the
        dashboard's own foreground is unreadable on a light paper in dark mode,
        and vice versa. Notes with no colour emit nothing, so every consumer
        falls back to the neutral dashboard tokens."""
        # Mirrors the editor's own precedence (`note.bg_color || note.color`).
        raw = str(note.get("bg_color") or note.get("color") or "").strip()
        try:
            paper = _paper_for_theme(raw, tint_dark)
        except Exception:
            paper = ""
        if not paper:
            return ""
        try:
            fg = _text_on_paper(paper)
            fg2 = _muted_ink(fg, paper, 0.30, 4.5)
            fg3 = _muted_ink(fg, paper, 0.48, 3.0)
            edge = _mix_hex(paper, fg, 0.12)
        except Exception:
            return ""
        return (
            f' style="--hashiw-note-fill:{html.escape(paper, quote=True)};'
            f'--hashiw-note-fg:{html.escape(fg, quote=True)};'
            f'--hashiw-note-fg2:{html.escape(fg2, quote=True)};'
            f'--hashiw-note-fg3:{html.escape(fg3, quote=True)};'
            f'--hashiw-note-edge:{html.escape(edge, quote=True)}"'
        )

    if not notes:
        return f"""
<div class="hashi-notes-widget is-{mode}" onclick="pycmd('openHashiGallery')">
  <div class="onigiri-widget-head"><h3>{title_html}</h3></div>
  <div class="hashi-widget-empty">{html.escape(tr("hashi_no_notes_yet", "No notes yet"), quote=False)}</div>
</div>"""

    if mode == "single":
        note = notes[0]
        note_title = html.escape(note.get("title") or "", quote=False)
        accent_style = _note_style(note)
        icon_html = _widget_icon_html(note.get("icon")) if show_icon else ""
        date_html = ""
        if show_date:
            label = _widget_date_label(note.get("updated_at") or note.get("created_at"))
            if label:
                date_html = f'<span class="hashi-widget-date">{html.escape(label, quote=False)}</span>'
        body_html = ""
        if show_excerpt:
            excerpt = _plain_excerpt(note.get("body_md"), 420)
            body_html = (
                f'<p class="hashi-widget-excerpt">{html.escape(excerpt, quote=False)}</p>'
                if excerpt
                else f'<p class="hashi-widget-excerpt is-empty">{html.escape(tr("hashi_empty_note", "Empty note"), quote=False)}</p>'
            )
        head_html = (
            f'<div class="hashi-widget-single-title">{icon_html}<span>{note_title}</span></div>'
            if (note_title or icon_html)
            else ""
        )
        return f"""
<div class="hashi-notes-widget is-single"{accent_style} onclick="pycmd('hashiWidget:open:{html.escape(str(note.get('id')), quote=True)}')">
  <div class="onigiri-widget-head">
    <h3>{title_html}</h3>
    {date_html}
  </div>
  <div class="hashi-widget-single">
    {head_html}
    {body_html}
  </div>
</div>"""

    cards_html = ""
    for note in notes:
        note_title = html.escape(note.get("title") or "", quote=False)
        accent_style = _note_style(note)
        icon_html = _widget_icon_html(note.get("icon")) if show_icon else ""
        date_html = ""
        if show_date:
            label = _widget_date_label(note.get("updated_at") or note.get("created_at"))
            if label:
                date_html = f'<span class="hashi-widget-card-date">{html.escape(label, quote=False)}</span>'
        excerpt_html = ""
        if show_excerpt:
            excerpt = _plain_excerpt(note.get("body_md"), 90)
            if excerpt:
                excerpt_html = f'<p class="hashi-widget-card-excerpt">{html.escape(excerpt, quote=False)}</p>'
        head_html = (
            f'<div class="hashi-widget-card-head">{icon_html}'
            f'<span class="hashi-widget-card-title">{note_title}</span></div>'
            if (note_title or icon_html)
            else ""
        )
        cards_html += f"""
<div class="hashi-widget-card"{accent_style} onclick="event.stopPropagation(); pycmd('hashiWidget:open:{html.escape(str(note.get('id')), quote=True)}')">
  {head_html}
  {excerpt_html}
  {date_html}
</div>"""

    return f"""
<div class="hashi-notes-widget is-gallery" onclick="pycmd('openHashiGallery')">
  <div class="onigiri-widget-head"><h3>{title_html}</h3></div>
  <div class="hashi-widget-cards">{cards_html}</div>
</div>"""


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
