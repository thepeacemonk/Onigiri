"""
Prep Station — Study Planner for Onigiri

Storage model (mirrors Hashi Notes):
  1. mw.col.conf[PREP_STATION_CONF_KEY] — source of truth. Lives inside
     collection.anki2, so it syncs via AnkiWeb collection sync (unlike
     config.json, which is local-only to this profile/computer).
  2. user_files/prep_station/plans.json — local mirror. Rides the existing
     Onigiri media-zip sync (sync.py), so plans are also safe on disk.
"""

from __future__ import annotations

import html
import json
import os
import uuid
from datetime import date, datetime, timedelta

from aqt import mw
from aqt.qt import (
    QColor, QDialog, QFileDialog, QVBoxLayout,
)
from aqt.webview import AnkiWebView
from PyQt6.QtCore import QLocale

from . import config
from . import safe_storage
from .translations import tr, current_locale

_dialog: "PrepStationDialog | None" = None

PREP_STATION_CONF_KEY = "onigiri_prep_station_plans"
PREP_STATION_SUSPENDED_KEY = "onigiri_prep_station_include_suspended"
PREP_STATION_CHART_NUMBERS_KEY = "onigiri_prep_station_chart_numbers"
PREP_STATION_WEEK_START_KEY = "onigiri_prep_station_week_start"
PREP_THUMBNAIL_DIR = "prep_station_thumbnails"

# revlog.type / RevlogEntry.ReviewKind values used for actual card answers.
# Manual and rescheduled entries (4/5) are deliberately excluded: they change
# scheduling history, but the learner did not answer a card.
REVIEW_KINDS = (
    ("learning", 0),
    ("review", 1),
    ("relearning", 2),
    ("filtered", 3),
)

MOTIVATIONAL_PHRASES = [
    "Small steps every day add up to big results.",
    "Discipline beats motivation when motivation runs out.",
    "Your future self is built by what you study today.",
    "Progress, not perfection.",
    "One more card. One more rep. One step closer.",
    "Consistency compounds — keep showing up.",
    "You don't have to be perfect, just consistent.",
    "Hard things become easy with repetition.",
    "Review today so exam day feels easy.",
    "The pace you keep today shapes the score you get tomorrow.",
    "A little bit, every day, beats a lot, some days.",
    "You're not behind. You're exactly where today's effort puts you.",
]


# ─── Persistence (mw.col.conf — syncs via AnkiWeb) ───────────────────────────

def _get_plans() -> list:
    if not mw or not mw.col:
        return []
    try:
        return list(mw.col.conf.get(PREP_STATION_CONF_KEY, []))
    except Exception:
        return []


def _save_plans(plans: list) -> None:
    if not mw or not mw.col:
        return
    try:
        mw.col.conf[PREP_STATION_CONF_KEY] = plans
        mw.col.setMod()
    except Exception as e:
        print(f"Prep Station: save error: {e}")
    _write_json_mirror(plans)


# ─── Persistence: user_files JSON mirror ──────────────────────────────────────

def _mirror_dir():
    path = os.path.join(os.path.dirname(__file__), "user_files", "prep_station")
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    return path


def _write_json_mirror(plans: list) -> None:
    try:
        path = os.path.join(_mirror_dir(), "plans.json")
        safe_storage.atomic_write_json(path, plans)
    except Exception as e:
        print(f"Prep Station: mirror write error: {e}")


# ─── Anki data helpers ────────────────────────────────────────────────────────

def _get_deck_names() -> list:
    if not mw or not mw.col:
        return []
    try:
        return sorted([d.name for d in mw.col.decks.all_names_and_ids()])
    except Exception:
        return []


def _get_deck_options() -> list[dict]:
    """Return the deck rows used by the WebUI picker.

    Keep the same icon resolution as the real deck browser, including per-deck
    custom icons and the configured folder/deck/subdeck defaults.  The full
    path remains available for search/tooltips while the visible label is the
    leaf name, which keeps deeply nested collections readable.
    """
    if not mw or not mw.col:
        return []
    try:
        from .prep_station_ui import deck_icon_value

        decks = sorted(mw.col.decks.all_names_and_ids(), key=lambda item: item.name.casefold())
        custom_icons = mw.col.conf.get("onigiri_custom_deck_icons", {}) or {}
        names = {deck.name for deck in decks}
        options = []
        for deck in decks:
            name = str(deck.name)
            has_children = any(other != name and other.startswith(name + "::") for other in names)
            icon_value = str(deck_icon_value(name, has_children) or "deck.svg")
            if icon_value in {"deck.svg", "folder.svg", "subdeck.svg", "filtered-deck.svg"}:
                icon_value = "system-unavailable:" + icon_value
            custom = custom_icons.get(str(deck.id), {}) if isinstance(custom_icons, dict) else {}
            # Mirror the deck browser's linked/separate light-dark tint.  A
            # legacy entry may only have ``color``; in that case it remains the
            # fallback for both modes.
            icon_color = str(
                (custom.get("colorDark") if _is_dark_mode() else custom.get("color"))
                or custom.get("color")
                or _accent_color()
            )
            options.append({
                "name": name,
                "label": name.rsplit("::", 1)[-1],
                "depth": name.count("::"),
                "icon": icon_value,
                "iconColor": icon_color,
            })
        return options
    except Exception as exc:
        print(f"Prep Station: deck picker error: {exc}")
        return [{"name": name, "label": name.rsplit("::", 1)[-1], "depth": name.count("::"), "icon": "system-unavailable:deck.svg", "iconColor": _accent_color()} for name in _get_deck_names()]


def _get_deck_card_counts(deck_names: list) -> dict:
    if not mw or not mw.col or not deck_names:
        return {}
    result = {}
    try:
        all_decks = mw.col.decks.all_names_and_ids()
        for name in deck_names:
            dids = [d.id for d in all_decks if d.name == name or d.name.startswith(name + "::")]
            if not dids:
                result[name] = {"new": 0, "due": 0, "susp": 0, "total": 0}
                continue
            dids_str = ",".join(str(d) for d in dids)
            rows = mw.col.db.all(
                f"SELECT queue, count(*) FROM cards WHERE did IN ({dids_str}) GROUP BY queue"
            )
            new_cnt = due_cnt = susp_cnt = total_cnt = 0
            for queue, cnt in rows:
                total_cnt += cnt
                if queue == 0:
                    new_cnt += cnt
                elif queue in (1, 2, 3):
                    due_cnt += cnt
                elif queue == -1:
                    susp_cnt += cnt
            result[name] = {"new": new_cnt, "due": due_cnt, "susp": susp_cnt, "total": total_cnt}
    except Exception as e:
        print(f"Prep Station: deck count error: {e}")
    return result


def _include_suspended() -> bool:
    if not mw or not mw.col:
        return False
    try:
        return bool(mw.col.conf.get(PREP_STATION_SUSPENDED_KEY, False))
    except Exception:
        return False


def _week_starts_on() -> str:
    """The Prep Station chart always shows the current week, not a rolling
    seven-day window.  Keep this preference in collection config so it follows
    the user between profiles/devices just like their plans do."""
    try:
        value = mw.col.conf.get(PREP_STATION_WEEK_START_KEY, "monday")
    except Exception:
        value = "monday"
    return value if value in ("monday", "sunday") else "monday"


def _week_days():
    today = date.today()
    # date.weekday(): Monday = 0 … Sunday = 6.
    offset = today.weekday() if _week_starts_on() == "monday" else (today.weekday() + 1) % 7
    first = today - timedelta(days=offset)
    return [first + timedelta(days=i) for i in range(7)]


def _weekday_label(day: date) -> str:
    # QLocale uses Monday=1 … Sunday=7.
    return current_locale().dayName(day.isoweekday(), QLocale.FormatType.ShortFormat)


PREP_STATION_WIDGET_FONT_KEY = "onigiri_prep_station_widget_font_scale"


def _widget_font_scale() -> float:
    """Font-size multiplier for the deck-browser Study Plans widget (stored as
    a percentage, clamped 60–160)."""
    if not mw or not mw.col:
        return 1.0
    try:
        percent = int(mw.col.conf.get(PREP_STATION_WIDGET_FONT_KEY, 100) or 100)
    except Exception:
        percent = 100
    percent = max(60, min(160, percent))
    return percent / 100.0


def _resolve_chart_number_mode() -> str:
    if not mw or not mw.col:
        return "hide"
    try:
        mode = mw.col.conf.get(PREP_STATION_CHART_NUMBERS_KEY, "hide")
    except Exception:
        mode = "hide"
    return mode if mode in ("show", "hover", "hide") else "hide"


def _enrich_plan(plan: dict) -> dict:
    p = dict(plan)
    exam_str = plan.get("exam_date", "")
    decks = plan.get("decks", [])
    if not exam_str:
        p["_pace"] = None
        return p
    try:
        exam_date = date.fromisoformat(exam_str)
        today = date.today()
        days_left = (exam_date - today).days
        counts = _get_deck_card_counts(decks)
        total_new = sum(v["new"] for v in counts.values())
        total_due = sum(v["due"] for v in counts.values())
        total_susp = sum(v.get("susp", 0) for v in counts.values())
        include_susp = _include_suspended()
        total_pending = total_new + total_due + (total_susp if include_susp else 0)

        if days_left < 0:
            status = "expired"
            req = None
        elif total_pending == 0:
            status = "done"
            req = 0.0
        else:
            req = round(total_pending / max(days_left, 1), 1)
            # A pace label should describe the student's current rhythm, not
            # shame them for having a large deck.  The screen turns this into
            # a gentle, actionable status after it has the week's review data.
            status = "active"

        p["_pace"] = {
            "status": status,
            "days_left": days_left,
            "total_pending": total_pending,
            "total_new": total_new,
            "total_due": total_due,
            "total_susp": total_susp,
            "include_suspended": include_susp,
            "required_per_day": req,
            "deck_counts": counts,
        }
    except Exception as e:
        print(f"Prep Station: pace error: {e}")
        p["_pace"] = None
    return p


def _attach_week_progress(plan: dict) -> dict:
    """Attach presentation-ready current-week pace data to an enriched plan.

    `revlog` records review events (rather than a mutable historical target),
    so the honest and least judgmental comparison is cards reviewed this week
    against the plan's own daily target accumulated up to today.
    """
    week_data = _weekly_review_data(plan.get("decks", []))
    counts, labels = week_data["counts"], week_data["labels"]
    pace = plan.get("_pace") or {}
    days = _week_days()
    today = date.today()
    elapsed = min(7, max(1, (today - days[0]).days + 1)) if days else 1
    reviewed = sum(counts[:elapsed])
    target = pace.get("required_per_day")
    expected = round(float(target or 0) * elapsed)
    status = pace.get("status", "")
    ratio = (reviewed / expected) if expected else 1.0
    if not plan.get("decks"):
        pulse = "not_ready"
    elif status == "done":
        pulse = "caught_up"
    elif status == "expired":
        pulse = "past"
    elif target is None:
        pulse = "not_ready"
    elif ratio >= 1.1:
        pulse = "ahead"
    elif ratio >= 0.65:
        pulse = "steady"
    elif reviewed > 0:
        pulse = "reset"
    else:
        pulse = "starting"
    plan["_week"] = {
        "counts": counts,
        "labels": labels,
        "series": week_data["series"],
        "reviewed": reviewed,
        "today_reviewed": counts[elapsed - 1] if counts else 0,
        "elapsed": elapsed,
        "target": expected,
        "ratio": min(1.0, ratio),
        "pulse": pulse,
    }
    return plan


def _weekly_review_data(deck_names: list | None = None) -> dict:
    """Current-week answered cards, split by Anki review kind.

    When ``deck_names`` is provided, selected decks and their descendants are
    included.  A grouped query per day keeps the page payload small while
    preserving every segment needed by the stacked chart and its tooltip.
    """
    labels = [_weekday_label(day) for day in _week_days()]
    empty_series = {name: [0] * 7 for name, _ in REVIEW_KINDS}
    if not mw or not mw.col:
        return {"counts": [0] * 7, "labels": labels, "series": empty_series}

    dids = []
    if deck_names is not None:
        try:
            all_decks = mw.col.decks.all_names_and_ids()
            wanted = set(deck_names)
            dids = [
                d.id for d in all_decks
                if d.name in wanted or any(d.name.startswith(n + "::") for n in wanted)
            ]
        except Exception:
            dids = []

    series = {name: [] for name, _ in REVIEW_KINDS}
    values = {kind: name for name, kind in REVIEW_KINDS}
    for day in _week_days():
        start_dt = datetime(day.year, day.month, day.day)
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = start_ms + 86400000
        day_counts = {name: 0 for name, _ in REVIEW_KINDS}
        if deck_names is None or dids:
            try:
                deck_clause = ""
                if deck_names is not None:
                    dids_str = ",".join(str(d) for d in dids)
                    deck_clause = f" AND cid IN (SELECT id FROM cards WHERE did IN ({dids_str}))"
                rows = mw.col.db.all(
                    "SELECT type, count(*) FROM revlog "
                    "WHERE id >= ? AND id < ? AND type IN (0, 1, 2, 3)"
                    + deck_clause + " GROUP BY type",
                    start_ms, end_ms,
                )
                for kind, count in rows:
                    name = values.get(int(kind))
                    if name:
                        day_counts[name] = int(count or 0)
            except Exception:
                pass
        for name, _ in REVIEW_KINDS:
            series[name].append(day_counts[name])

    counts = [sum(series[name][i] for name, _ in REVIEW_KINDS) for i in range(7)]
    return {"counts": counts, "labels": labels, "series": series}


def _weekly_review_counts():
    data = _weekly_review_data()
    return data["counts"], data["labels"]


def _weekly_review_counts_for_decks(deck_names: list):
    data = _weekly_review_data(deck_names)
    return data["counts"], data["labels"]


def _motivational_phrase() -> str:
    day_idx = date.today().timetuple().tm_yday
    return tr(f"prep_station_quote_{day_idx % len(MOTIVATIONAL_PHRASES)}", MOTIVATIONAL_PHRASES[day_idx % len(MOTIVATIONAL_PHRASES)])


# ─── Action handlers ──────────────────────────────────────────────────────────

def _handle_save_plan(payload: dict) -> None:
    plans = _get_plans()
    pid = payload.get("id")
    if pid:
        found = False
        for i, p in enumerate(plans):
            if p.get("id") == pid:
                payload["created_at"] = p.get("created_at", date.today().isoformat())
                plans[i] = payload
                found = True
                break
        if not found:
            payload["created_at"] = date.today().isoformat()
            plans.append(payload)
    else:
        payload["id"] = str(uuid.uuid4())
        payload["created_at"] = date.today().isoformat()
        plans.append(payload)
    _save_plans(plans)


def _handle_delete_plan(plan_id: str) -> None:
    _save_plans([p for p in _get_plans() if p.get("id") != plan_id])


# ─── Theming helpers ──────────────────────────────────────────────────────────

def _is_dark_mode() -> bool:
    try:
        from .config import effective_night_mode
        return effective_night_mode(config.get_config())
    except Exception:
        return False


def _accent_color() -> str:
    conf = config.get_config()
    mode = "dark" if _is_dark_mode() else "light"
    try:
        default = config.DEFAULTS["colors"][mode]["--accent-color"]
    except Exception:
        default = "#00A982"
    return conf.get("colors", {}).get(mode, {}).get("--accent-color", default)


# ─── Dialog ───────────────────────────────────────────────────────────────────

def _resolve_plan_color(plan: dict) -> str:
    """Return the active theme colour without importing the old Qt planner."""
    legacy = str(plan.get("color") or "")
    if plan.get("color_dynamic"):
        return str(plan.get("color_dark" if _is_dark_mode() else "color_light") or legacy or "#60A5FA")
    return str(plan.get("color_light") or legacy or "#60A5FA")


def _readable_on(color: str) -> str:
    value = QColor(color)
    luminance = 0.299 * value.red() + 0.587 * value.green() + 0.114 * value.blue()
    return "#ffffff" if luminance < 150 else "#1a1a1a"


def _read_web_asset(name: str) -> str:
    try:
        with open(os.path.join(os.path.dirname(__file__), "web", name), encoding="utf-8") as handle:
            return handle.read()
    except Exception as exc:
        print(f"Prep Station: could not read {name}: {exc}")
        return ""


def _addon_uri(relative: str) -> str:
    package = mw.addonManager.addonFromModule(__name__)
    return f"/_addons/{package}/{relative.lstrip('/')}"


def _thumbnail_url(filename: str) -> str:
    filename = os.path.basename(str(filename or ""))
    path = os.path.join(os.path.dirname(__file__), "user_files", PREP_THUMBNAIL_DIR, filename)
    return _addon_uri(f"user_files/{PREP_THUMBNAIL_DIR}/{filename}") if filename and os.path.isfile(path) else ""


def _emoji_sprite_map() -> dict:
    try:
        from .emoji_sprites import EMOJI_SPRITES
        return {item["value"]: item["asset"] for item in EMOJI_SPRITES}
    except Exception:
        return {}


def _web_icon_catalog() -> tuple[list, list, dict]:
    """Return picker inventories plus exact URLs for user supplied assets.

    The deck browser accepts both its own custom-deck folder and the Settings
    icon library.  Keeping the source URL with each basename lets Prep Station
    draw the same icon without guessing which directory a user chose it from.
    """
    root = os.path.dirname(__file__)
    system_icons = []
    user_icons = []
    icon_paths = {}
    for index, (rel, extensions) in enumerate((
        (("system_files", "system_icons", "available_for_users"), {".svg"}),
        (("user_files", "custom_deck_icons"), {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif"}),
        (("user_files", "icons"), {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif"}),
    )):
        folder = os.path.join(root, *rel)
        try:
            names = sorted(
                name for name in os.listdir(folder)
                if os.path.splitext(name)[1].lower() in extensions and os.path.isfile(os.path.join(folder, name))
            )
        except Exception:
            names = []
        if index == 0:
            system_icons = names
            continue
        for name in names:
            # The deck browser checks custom_deck_icons first, so keep its
            # image in a same-name collision.
            if name not in icon_paths:
                icon_paths[name] = _addon_uri("/".join((*rel, name)))
                user_icons.append(name)
    return system_icons, user_icons, icon_paths


def _web_strings() -> dict:
    keys = (
        "prep_station_title", "prep_new_plan", "prep_edit", "prep_delete", "cancel",
        "prep_save_changes", "prep_create_plan", "prep_plan_name_placeholder", "prep_exam_date_label",
        "prep_study_decks_label", "prep_notes_label", "prep_notes_placeholder", "prep_choose_photo",
        "prep_remove_photo", "prep_daily_target", "prep_cards_remaining", "prep_reviewed_this_week",
        "prep_this_week", "prep_deck_breakdown", "prep_no_decks", "prep_all_caught_up",
        "prep_days_left_badge", "prep_today_badge", "prep_exam_has_passed", "prep_search_decks_placeholder",
        "search_icons_placeholder", "cards", "close", "icon_picker",
        "choose_icon", "icon_label", "no_matching_icons",
        "prep_choose_icon_or_emoji", "prep_target_today", "prep_today_progress",
        "prep_empty_title", "prep_empty_desc", "prep_study_plans_eyebrow",
        "prep_name_label", "prep_icon_label", "prep_no_decks_available",
        "prep_appearance_label", "prep_light_card", "prep_dark_card",
    )
    return {key: tr(key) for key in keys}


def _web_palette() -> dict:
    """Resolve Prep Station directly from Onigiri's active theme settings."""
    dark = _is_dark_mode()
    mode = "dark" if dark else "light"
    conf = config.get_config_readonly()
    defaults = config.DEFAULTS.get("colors", {}).get(mode, {})
    colors = conf.get("colors", {}).get(mode, {})

    def value(key: str, fallback: str) -> str:
        return str(colors.get(key) or defaults.get(key) or fallback)

    return {
        "bg": value("--bg", "#161616" if dark else "#f5f5f4"),
        "surface": value("--canvas-inset", "#242424" if dark else "#ffffff"),
        "surface2": value("--highlight-bg", "#343434" if dark else "#f1f1f0"),
        "border": value("--border", "#424242" if dark else "#e0e0e0"),
        "fg": value("--fg", "#f4f4f5" if dark else "#212121"),
        "fg2": value("--fg-subtle", "#b6b6b8" if dark else "#64655f"),
        "fg3": value("--fg-subtle", "#7c7c80" if dark else "#92948d"),
        "accent": value("--accent-color", "#0077C8"),
    }


def _web_context() -> dict:
    system_icons, custom_icons, icon_paths = _web_icon_catalog()
    plans = []
    for raw in _get_plans():
        plan = _attach_week_progress(_enrich_plan(raw))
        plan["displayColor"] = _resolve_plan_color(plan)
        plan["thumbnailUrl"] = _thumbnail_url(plan.get("thumbnail", ""))
        plans.append(plan)
    week_data = _weekly_review_data()
    palette = _web_palette()
    week_days = _week_days()
    elapsed = min(7, max(1, (date.today() - week_days[0]).days + 1)) if week_days else 1
    return {
        "dark": _is_dark_mode(),
        "accent": palette["accent"],
        "palette": palette,
        "addonBase": _addon_uri(""),
        "plans": plans,
        "deckNames": _get_deck_names(),
        "deckOptions": _get_deck_options(),
        "week": {
            "counts": week_data["counts"],
            "labels": week_data["labels"],
            "series": week_data["series"],
            "elapsed": elapsed,
            "startsOn": _week_starts_on(),
        },
        "strings": _web_strings(),
        "emojiSprites": _emoji_sprite_map(),
        "systemIcons": system_icons,
        "customIcons": custom_icons,
        "iconPaths": icon_paths,
        "quote": _motivational_phrase(),
    }


def _safe_json(value) -> str:
    return json.dumps(value).replace("</", "<\\/")


def _render_web() -> str:
    template = _read_web_asset("prep_station.html")
    if not template:
        return "<html><body>Prep Station assets missing.</body></html>"
    try:
        from .fonts import poppins_font_face_css
        font_css = poppins_font_face_css(mw.addonManager.addonFromModule(__name__))
    except Exception:
        font_css = ""
    return template.replace("/*__PREP_FONT_FACE__*/", font_css).replace("/*__PREP_CONTEXT__*/null", _safe_json(_web_context()))


class PrepStationDialog(QDialog):
    """A conventional dialog shell around the fully web-based Prep Station."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent or mw)
        self.setWindowTitle(tr("prep_station_title", "Prep Station"))
        self.setMinimumSize(720, 540)
        self.resize(1060, 720)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.web = AnkiWebView(self)
        try:
            self.web.page().setBackgroundColor(QColor(_web_palette()["bg"]))
        except Exception:
            pass
        layout.addWidget(self.web)
        self.web.set_bridge_command(self._on_bridge, self)
        self._reload()

    def _reload(self) -> None:
        self.web.stdHtml(_render_web())

    def _copy_thumbnail(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self, tr("prep_choose_photo", "Choose Photo…"), "", "Images (*.png *.jpg *.jpeg *.webp *.gif *.bmp)"
        )
        if not source:
            return
        extension = os.path.splitext(source)[1].lower() or ".png"
        filename = f"{uuid.uuid4().hex}{extension}"
        folder = os.path.join(os.path.dirname(__file__), "user_files", PREP_THUMBNAIL_DIR)
        try:
            os.makedirs(folder, exist_ok=True)
            import shutil
            shutil.copyfile(source, os.path.join(folder, filename))
            self.web.eval("window.prepReceivePhoto && window.prepReceivePhoto(%s);" % _safe_json({"name": filename, "url": _thumbnail_url(filename)}))
        except Exception as exc:
            print(f"Prep Station: thumbnail copy error: {exc}")

    def _save_from_web(self, payload: dict) -> None:
        existing = next((p for p in _get_plans() if p.get("id") == payload.get("id")), {})
        name = str(payload.get("name") or "").strip()
        if not name:
            self.web.eval("window.prepSaveError && window.prepSaveError('name');")
            return
        try:
            exam_date = date.fromisoformat(str(payload.get("exam_date") or ""))
        except ValueError:
            self.web.eval("window.prepSaveError && window.prepSaveError('date');")
            return
        valid_decks = set(_get_deck_names())
        allowed_colors = ("color_light", "color_dark")
        plan = {
            "id": str(payload.get("id") or ""), "name": name,
            "icon": str(payload.get("icon") or "emoji:📚"),
            "exam_date": exam_date.isoformat(),
            "decks": [str(d) for d in payload.get("decks", []) if str(d) in valid_decks],
            "notes": str(payload.get("notes") or "").strip(),
            "thumbnail": os.path.basename(str(payload.get("thumbnail") or "")),
            "thumbnail_opacity": max(0, min(100, int(payload.get("thumbnail_opacity", 100) or 100))),
            "thumbnail_blur": max(0, min(100, int(payload.get("thumbnail_blur", 0) or 0))),
            "color_only": bool(payload.get("color_only", False)),
            "color_dynamic": bool(payload.get("color_dynamic", False)),
        }
        icon_color = str(payload.get("icon_color") or existing.get("icon_color") or _accent_color())
        plan["icon_color"] = icon_color if icon_color.startswith("#") and len(icon_color) in (4, 7) else _accent_color()
        for key in allowed_colors:
            color = str(payload.get(key) or existing.get(key) or "")
            plan[key] = color if color.startswith("#") and len(color) in (4, 7) else ("#1E3A8A" if key == "color_dark" else "#60A5FA")
        _handle_save_plan(plan)
        old_thumbnail = str(existing.get("thumbnail") or "")
        if old_thumbnail and old_thumbnail != plan["thumbnail"]:
            old_path = os.path.join(os.path.dirname(__file__), "user_files", PREP_THUMBNAIL_DIR, os.path.basename(old_thumbnail))
            try:
                os.remove(old_path)
            except OSError:
                pass
        self._reload()

    def _on_bridge(self, cmd: str) -> None:
        try:
            if cmd == "prep:choose_photo":
                self._copy_thumbnail()
            elif cmd.startswith("prep:save:"):
                self._save_from_web(json.loads(cmd.split(":", 2)[2]))
            elif cmd.startswith("prep:delete:"):
                _handle_delete_plan(cmd.split(":", 2)[2])
                self._reload()
        except Exception as exc:
            print(f"Prep Station: bridge error ({cmd[:40]}): {exc}")

    def closeEvent(self, event) -> None:
        try:
            if mw and getattr(mw, "deckBrowser", None):
                mw.deckBrowser.refresh()
        except Exception:
            pass
        super().closeEvent(event)


def open_prep_station(parent=None) -> None:
    global _dialog
    try:
        if _dialog is not None:
            _dialog.close()
    except Exception:
        pass
    _dialog = PrepStationDialog(parent or mw)
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()


# ─── Main menu widget (deck browser, HTML) ───────────────────────────────────

def _prep_card_icon_html(addon_path: str, addon_package: str, icon_value: str, icon_color: str) -> str:
    """Renders a plan's icon exactly as the Qt dialog does (render_icon_pixmap
    in prep_station_ui.py): emoji sprite image, tinted system/custom SVG, or
    a plain text glyph as last resort. Keeps the widget's mini card visually
    identical to ExamCard/PlanDetailBanner instead of falling back to blank."""
    from .emoji_sprites import path_for_emoji
    from .ui_kit.common import system_icon_path

    icon_value = str(icon_value or "")
    if not icon_value:
        return "<span></span>"

    def _rel_url(path: str) -> str:
        rel = os.path.relpath(path, addon_path).replace(os.sep, "/")
        return f"/_addons/{addon_package}/{rel}"

    if icon_value.startswith("emoji:"):
        glyph = icon_value[len("emoji:"):]
        sprite_path = path_for_emoji(addon_path, glyph)
        if sprite_path:
            return f'<img class="prep-card-icon" src="{_rel_url(sprite_path)}">'
        return f'<span class="prep-card-icon">{html.escape(glyph)}</span>'

    path = ""
    if icon_value.startswith("system:"):
        path = system_icon_path(icon_value[len("system:"):])
    else:
        for folder in ("custom_deck_icons", "icons"):
            candidate = os.path.join(addon_path, "user_files", folder, icon_value)
            if os.path.exists(candidate):
                path = candidate
                break
        if not path:
            path = system_icon_path(icon_value)
    if path and os.path.exists(path):
        url = _rel_url(path)
        if path.lower().endswith(".svg"):
            safe_color = icon_color if str(icon_color).startswith("#") else "#ffffff"
            return (
                '<span class="prep-card-icon prep-card-icon-mono" '
                f'style="display:inline-block;width:13px;height:13px;background:{safe_color};'
                f'-webkit-mask:url(&quot;{url}&quot;) center/contain no-repeat;'
                f'mask:url(&quot;{url}&quot;) center/contain no-repeat"></span>'
            )
        return f'<img class="prep-card-icon" src="{url}">'
    return "<span></span>"


def render_widget_html(slot_count: int = 4) -> str:
    slot_count = max(1, min(4, slot_count))
    plans = _get_plans()
    today = date.today()
    addon_path = os.path.dirname(__file__)
    addon_package = mw.addonManager.addonFromModule(__name__)

    active_plans = []
    for p in plans:
        exam_str = p.get("exam_date", "")
        if not exam_str:
            continue
        try:
            days_left = (date.fromisoformat(exam_str) - today).days
            if days_left >= 0:
                active_plans.append((days_left, p))
        except Exception:
            pass
    active_plans.sort(key=lambda item: item[0])

    widget_title = html.escape(tr("prep_widget_title"))
    font_style = f' style="--prep-fs: {_widget_font_scale():.3f};"'

    if not active_plans:
        return f"""
<div class="prep-station-widget"{font_style} onclick="pycmd('openPrepStation')">
  <div class="onigiri-widget-head">
    <h3>{widget_title}</h3>
  </div>
  <div class="prep-widget-empty">{html.escape(tr("prep_no_active_plans"))}</div>
</div>"""

    cards_html = ""
    for days_left, p in active_plans[:slot_count]:
        name = html.escape(p.get("name", tr("prep_default_exam_name")))
        color = _resolve_plan_color(p)
        enriched = _attach_week_progress(_enrich_plan(p))
        pace = enriched.get("_pace") or {}
        week = enriched.get("_week") or {}
        req = pace.get("required_per_day")
        status = pace.get("status", "")

        if not p.get("decks"):
            big, small = "—", tr("prep_set_date_and_decks")
        elif status == "expired":
            big, small = "—", tr("prep_exam_has_passed")
        elif req is None:
            big, small = "—", tr("prep_set_date_and_decks")
        elif status == "done":
            big, small = "✓", tr("prep_all_caught_up")
        else:
            big, small = f"{req:.0f}", tr("prep_cards_per_day_unit")

        if days_left == 0:
            badge_text = tr("prep_today_badge")
        elif days_left > 0:
            badge_text = tr("prep_days_left_badge").format(days_left)
        else:
            badge_text = tr("prep_past_badge")

        fg_on_band = _readable_on(color)
        icon_color = str(p.get("icon_color") or fg_on_band)
        icon_html = _prep_card_icon_html(addon_path, addon_package, p.get("icon", "emoji:📚"), icon_color)

        reviewed = int(week.get("reviewed") or 0)
        weekly_target = int(week.get("target") or 0)
        percentage = min(100, max(0, round(float(week.get("ratio") or 0) * 100)))
        progress_html = f"""
    <div class="prep-card-progress" title="{reviewed} reviewed this week">
      <span class="prep-card-progress-track"><i class="prep-card-progress-fill" style="width:{percentage}%;background:{color}"></i></span>
      <span class="prep-card-progress-label">{reviewed}/{weekly_target}</span>
    </div>"""

        cards_html += f"""
<div class="prep-plan-card" onclick="event.stopPropagation(); pycmd('openPrepStation')">
  <div class="prep-card-band" style="background-color:{color}">
    <div class="prep-card-band-top">
      <span class="prep-card-badge">{html.escape(badge_text)}</span>
    </div>
    <div class="prep-card-name-row">
      {icon_html}
      <span class="prep-card-name">{name}</span>
    </div>
  </div>
  <div class="prep-card-body">
    <div class="prep-card-pace">
      <span class="prep-card-pace-num" style="color:{color}">{big}</span>
      <span class="prep-card-pace-unit">{html.escape(small)}</span>
    </div>{progress_html}
  </div>
</div>"""

    return f"""
<div class="prep-station-widget"{font_style} onclick="pycmd('openPrepStation')">
  <div class="onigiri-widget-head">
    <h3>{widget_title}</h3>
  </div>
  <div class="prep-plan-cards" style="grid-template-columns: repeat({slot_count}, 1fr);">
    {cards_html}
  </div>
</div>"""
