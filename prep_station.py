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
from aqt.theme import theme_manager
from aqt.utils import askUser
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QScrollArea, QStackedWidget, Qt, QPixmap,
)
from PyQt6.QtCore import QLocale
from PyQt6.QtGui import QImage

from . import config
from .ui_widgets import FlowLayout
from .translations import tr, current_locale
from .prep_station_ui import (
    HeaderBar, ExamCard, AddExamCard, PlanCardsContainer, MiniCalendar, UpcomingPlansCard, StatCard, QuoteCard,
    PlanEditDialog, PlanDetailView,
    palette, build_qss, circular_pixmap, resolve_plan_color, fit_dialog_to_screen,
    readable_on,
)

_dialog: "PrepStationDialog | None" = None

PREP_STATION_CONF_KEY = "onigiri_prep_station_plans"

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
        with open(path, "w", encoding="utf-8") as f:
            json.dump(plans, f, ensure_ascii=False, indent=2)
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


def _get_deck_card_counts(deck_names: list) -> dict:
    if not mw or not mw.col or not deck_names:
        return {}
    result = {}
    try:
        all_decks = mw.col.decks.all_names_and_ids()
        for name in deck_names:
            dids = [d.id for d in all_decks if d.name == name or d.name.startswith(name + "::")]
            if not dids:
                result[name] = {"new": 0, "due": 0, "total": 0}
                continue
            dids_str = ",".join(str(d) for d in dids)
            rows = mw.col.db.all(
                f"SELECT queue, count(*) FROM cards WHERE did IN ({dids_str}) GROUP BY queue"
            )
            new_cnt = due_cnt = total_cnt = 0
            for queue, cnt in rows:
                total_cnt += cnt
                if queue == 0:
                    new_cnt += cnt
                elif queue in (1, 2, 3):
                    due_cnt += cnt
            result[name] = {"new": new_cnt, "due": due_cnt, "total": total_cnt}
    except Exception as e:
        print(f"Prep Station: deck count error: {e}")
    return result


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
        total_pending = total_new + total_due

        if days_left < 0:
            status = "expired"
            req = None
        elif total_pending == 0:
            status = "done"
            req = 0.0
        else:
            req = round(total_pending / max(days_left, 1), 1)
            if req <= 30:
                status = "ok"
            elif req <= 80:
                status = "warn"
            else:
                status = "danger"

        p["_pace"] = {
            "status": status,
            "days_left": days_left,
            "total_pending": total_pending,
            "total_new": total_new,
            "total_due": total_due,
            "required_per_day": req,
            "deck_counts": counts,
        }
    except Exception as e:
        print(f"Prep Station: pace error: {e}")
        p["_pace"] = None
    return p


def _weekly_review_counts():
    if not mw or not mw.col:
        return [0] * 7, [""] * 7
    today = date.today()
    locale = current_locale()
    counts, labels = [], []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        start_dt = datetime(day.year, day.month, day.day)
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = start_ms + 86400000
        try:
            cnt = mw.col.db.scalar(
                "SELECT count(*) FROM revlog WHERE id >= ? AND id < ?", start_ms, end_ms
            ) or 0
        except Exception:
            cnt = 0
        counts.append(cnt)
        labels.append(locale.dayName(day.isoweekday(), QLocale.FormatType.ShortFormat))
    return counts, labels


def _weekly_review_counts_for_decks(deck_names: list):
    """Same as _weekly_review_counts but scoped to a plan's assigned decks
    (and their subdecks), for the per-plan progress chart in the detail view."""
    if not mw or not mw.col:
        return [0] * 7, [""] * 7
    dids = []
    if deck_names:
        try:
            all_decks = mw.col.decks.all_names_and_ids()
            wanted = set(deck_names)
            dids = [
                d.id for d in all_decks
                if d.name in wanted or any(d.name.startswith(n + "::") for n in wanted)
            ]
        except Exception:
            dids = []
    today = date.today()
    locale = current_locale()
    counts, labels = [], []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        start_dt = datetime(day.year, day.month, day.day)
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = start_ms + 86400000
        cnt = 0
        if dids:
            try:
                dids_str = ",".join(str(d) for d in dids)
                cnt = mw.col.db.scalar(
                    "SELECT count(*) FROM revlog WHERE id >= ? AND id < ? "
                    f"AND cid IN (SELECT id FROM cards WHERE did IN ({dids_str}))",
                    start_ms, end_ms,
                ) or 0
            except Exception:
                cnt = 0
        counts.append(cnt)
        labels.append(locale.dayName(day.isoweekday(), QLocale.FormatType.ShortFormat))
    return counts, labels


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


def _bg_folder() -> str:
    path = os.path.join(os.path.dirname(__file__), "user_files", "prep_station_bg")
    os.makedirs(path, exist_ok=True)
    return path


def _fast_blur_pixmap(pixmap: QPixmap, percent: int) -> QPixmap:
    if percent <= 0 or pixmap.isNull():
        return pixmap
    factor = max(2, int(2 + (percent / 100.0) * 18))
    w = max(1, pixmap.width() // factor)
    h = max(1, pixmap.height() // factor)
    small = pixmap.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return small.scaled(
        pixmap.width(), pixmap.height(),
        Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation,
    )


def _accent_color() -> str:
    conf = config.get_config()
    mode = "dark" if _is_dark_mode() else "light"
    try:
        default = config.DEFAULTS["colors"][mode]["--accent-color"]
    except Exception:
        default = "#00A982"
    return conf.get("colors", {}).get(mode, {}).get("--accent-color", default)


def _resolve_header_background(dark: bool):
    """Returns (color_hex, QPixmap|None, opacity_percent).

    When synced, mirrors the Profile Bar Background exactly (accent/custom/image
    modes, blur, opacity) using the same modern_menu_profile_* keys the sidebar
    profile bar reads.
    """
    addon_path = os.path.dirname(__file__)
    if not mw or not mw.col:
        return _accent_color(), None, 100
    conf = mw.col.conf
    suffix = "dark" if dark else "light"
    sync = bool(conf.get("onigiri_prep_station_bg_sync_profile", True))

    if sync:
        mode = conf.get("modern_menu_profile_bg_mode", "image")
        if mode == "accent":
            color = _accent_color()
        else:
            color = conf.get(f"modern_menu_profile_bg_color_{suffix}", "#555555" if dark else "#EEEEEE")
        opacity = int(conf.get("modern_menu_profile_bg_opacity", 50) or 50)
        blur = int(conf.get("modern_menu_profile_bg_blur", 0) or 0)
        pixmap = None
        if mode == "image":
            filename = conf.get("modern_menu_profile_bg_image", "")
            path = os.path.join(addon_path, "user_files", "profile_bg", filename) if filename else ""
            if not path or not os.path.exists(path):
                path = os.path.join(addon_path, "system_files", "profile_default", "onigiri-bg.png")
            if os.path.exists(path):
                pixmap = QPixmap(path)
                if blur > 0:
                    pixmap = _fast_blur_pixmap(pixmap, blur)
        return color, pixmap, opacity

    mode = conf.get("onigiri_prep_station_bg_mode", "color")
    color = conf.get(f"onigiri_prep_station_bg_color_{suffix}", _accent_color())
    opacity = int(conf.get("onigiri_prep_station_bg_opacity", 100) or 100)
    blur = int(conf.get("onigiri_prep_station_bg_blur", 0) or 0)
    pixmap = None
    if mode == "image":
        filename = conf.get(f"onigiri_prep_station_bg_image_{suffix}", "")
        if filename:
            path = os.path.join(_bg_folder(), filename)
            if os.path.exists(path):
                pixmap = QPixmap(path)
                if blur > 0:
                    pixmap = _fast_blur_pixmap(pixmap, blur)
    return color, pixmap, opacity


def _resolve_chart_colors(dark: bool):
    """Returns (line_color, fill_intensity, opacity_percent)."""
    if not mw or not mw.col:
        return _accent_color(), 50, 100
    conf = mw.col.conf
    suffix = "dark" if dark else "light"
    color = conf.get(f"onigiri_prep_station_chart_color_{suffix}", "") or "#ffffff"
    fill_intensity = int(conf.get("onigiri_prep_station_chart_blur", 50) or 0)
    opacity = int(conf.get("onigiri_prep_station_chart_opacity", 100) or 0)
    return color, fill_intensity, opacity


def _resolve_avatar_pixmap(size: int) -> QPixmap:
    """Circular avatar mirroring the sidebar profile picture resolution."""
    addon_path = os.path.dirname(__file__)
    try:
        conf = mw.col.conf if (mw and mw.col) else {}
        dark = _is_dark_mode()
        pic_dynamic = bool(conf.get("modern_menu_profile_picture_dynamic_mode", True))
        filename = (
            conf.get(f"modern_menu_profile_picture_{'dark' if dark else 'light'}", "")
            if pic_dynamic else ""
        ) or conf.get("modern_menu_profile_picture", "")
        path = os.path.join(addon_path, "user_files", "profile", filename) if filename else ""
        if not path or not os.path.exists(path):
            path = os.path.join(addon_path, "system_files", "profile_default", "onigiri-san.png")
        if os.path.exists(path):
            img = QImage(path)
            if not img.isNull():
                return circular_pixmap(img, size)
    except Exception:
        pass
    return QPixmap()


# ─── Dialog ───────────────────────────────────────────────────────────────────

class PrepStationDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("prep_station_title"))
        fit_dialog_to_screen(self, 1060, 720, 720, 480)
        self.accent_color = _accent_color()
        self.addon_path = os.path.dirname(__file__)

        self.pal = palette(_is_dark_mode())
        self.setStyleSheet(f"QDialog {{ background: {self.pal['bg']}; }}" + build_qss(self.pal))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(16)

        self.header = HeaderBar(self)
        outer.addWidget(self.header)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        grid_page = QWidget()
        content_row = QHBoxLayout(grid_page)
        content_row.setContentsMargins(0, 0, 0, 0)
        content_row.setSpacing(16)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        left_scroll.viewport().setAutoFillBackground(False)
        self.cards_container = PlanCardsContainer(self.pal)
        self.cards_container.setAutoFillBackground(False)
        self.cards_container.orderCommitted.connect(self._reorder_plan)
        self.cards_flow = FlowLayout(self.cards_container, margin=2, spacing=14)
        left_scroll.setWidget(self.cards_container)
        content_row.addWidget(left_scroll, 2)

        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        right_scroll.setFixedWidth(286)
        right_scroll.viewport().setAutoFillBackground(False)
        right_container = QWidget()
        right_container.setAutoFillBackground(False)
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 4, 0)
        right_layout.setSpacing(14)

        self.calendar = MiniCalendar(self.pal)
        right_layout.addWidget(self.calendar)

        self.upcoming_card = UpcomingPlansCard(self.pal)
        right_layout.addWidget(self.upcoming_card)

        self.stat_card = StatCard(self.pal)
        right_layout.addWidget(self.stat_card)

        self.quote_card = QuoteCard(self.pal)
        right_layout.addWidget(self.quote_card)

        right_layout.addStretch(1)
        right_scroll.setWidget(right_container)
        content_row.addWidget(right_scroll, 0)

        self.stack.addWidget(grid_page)

        self.detail_view = PlanDetailView(self.addon_path, self.pal)
        self.detail_view.backRequested.connect(self._close_plan_detail)
        self.detail_view.editRequested.connect(self._edit_from_detail)
        self.detail_view.deleteRequested.connect(self._delete_from_detail)
        self.stack.addWidget(self.detail_view)

        self.refresh()

    def refresh(self) -> None:
        dark = _is_dark_mode()
        self.pal = palette(dark)
        self.cards_container.pal = self.pal
        plans = _get_plans()
        enriched = [_enrich_plan(p) for p in plans]

        user_name = config.get_config().get("userName", "USER")
        color, pixmap, opacity = _resolve_header_background(dark)
        self.header.set_background(color, pixmap, opacity)
        self.header.set_profile(user_name, _resolve_avatar_pixmap(54))
        counts, labels = _weekly_review_counts()
        line_color, fill_intensity, chart_opacity = _resolve_chart_colors(dark)
        label_color = getattr(self.header, "_chart_label_color", None) or "#9b9895"
        if not isinstance(label_color, str):
            label_color = label_color.name()
        self.header.chart.set_colors(line_color, label_color, fill_intensity)
        self.header.chart.set_opacity(chart_opacity)
        self.header.chart.set_data(counts, labels)

        while self.cards_flow.count():
            item = self.cards_flow.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for p in enriched:
            card = ExamCard(p, p.get("_pace") or {}, self.addon_path, self.pal)
            card.clicked.connect(self._open_plan_detail)
            self.cards_flow.addWidget(card)
        add_card = AddExamCard(self.pal)
        add_card.clicked.connect(self._open_add_modal)
        self.cards_flow.addWidget(add_card)

        marks = {}
        for p in enriched:
            try:
                d = date.fromisoformat(p.get("exam_date", ""))
                marks.setdefault(d, []).append(resolve_plan_color(p))
            except Exception:
                pass
        self.calendar.set_marks(marks)

        upcoming = []
        today = date.today()
        for p in enriched:
            try:
                d = date.fromisoformat(p.get("exam_date", ""))
            except Exception:
                continue
            days_left = (d - today).days
            if days_left < 0:
                continue
            if days_left == 0:
                date_label = tr("prep_today_badge")
            else:
                date_label = tr("prep_days_left_badge").format(days_left)
            name = p.get("name") or tr("prep_default_plan_name")
            upcoming.append((days_left, name, date_label, resolve_plan_color(p)))
        upcoming.sort(key=lambda x: x[0])
        self.upcoming_card.set_items([(name, date_label, color) for _, name, date_label, color in upcoming])

        total_pace = 0.0
        active_count = 0
        for p in enriched:
            pace = p.get("_pace") or {}
            req = pace.get("required_per_day")
            if req is not None and pace.get("status") not in ("expired", "done"):
                total_pace += req
                active_count += 1
        plan_word = tr("prep_plan") if active_count == 1 else tr("prep_plans")
        self.stat_card.set_value(f"{total_pace:.0f}", tr("prep_across_active_tpl").format(active_count, plan_word))

        self.quote_card.set_quote(_motivational_phrase())

    def _reorder_plan(self, plan_id: str, target_index: int) -> None:
        plans = _get_plans()
        src_index = next((i for i, p in enumerate(plans) if p.get("id") == plan_id), None)
        if src_index is None:
            return
        plan = plans.pop(src_index)
        if target_index > src_index:
            target_index -= 1
        target_index = max(0, min(target_index, len(plans)))
        if target_index == src_index:
            return
        plans.insert(target_index, plan)
        _save_plans(plans)
        self.refresh()

    def _open_add_modal(self) -> None:
        dialog = PlanEditDialog(self.addon_path, _get_deck_names(), None, self)
        result_code = dialog.exec()
        self.raise_()
        self.activateWindow()
        if result_code == QDialog.DialogCode.Accepted:
            result = dialog.get_result()
            if result:
                _handle_save_plan(result)
                self.refresh()

    def _open_edit_modal(self, plan_id: str) -> None:
        plans = _get_plans()
        plan = next((p for p in plans if p.get("id") == plan_id), None)
        if not plan:
            return
        dialog = PlanEditDialog(self.addon_path, _get_deck_names(), plan, self)
        result_code = dialog.exec()
        self.raise_()
        self.activateWindow()
        if result_code == QDialog.DialogCode.Accepted:
            if dialog.was_delete_requested():
                _handle_delete_plan(plan_id)
                self.refresh()
                return
            result = dialog.get_result()
            if result:
                _handle_save_plan(result)
                self.refresh()

    def _open_plan_detail(self, plan_id: str) -> None:
        self._detail_plan_id = plan_id
        self._refresh_detail_view()
        self.stack.setCurrentWidget(self.detail_view)

    def _refresh_detail_view(self) -> None:
        plan_id = getattr(self, "_detail_plan_id", "")
        plans = _get_plans()
        plan = next((p for p in plans if p.get("id") == plan_id), None)
        if not plan:
            self._close_plan_detail()
            return
        enriched = _enrich_plan(plan)
        counts, labels = _weekly_review_counts_for_decks(plan.get("decks", []))
        self.detail_view.set_plan(enriched, enriched.get("_pace") or {}, counts, labels)

    def _close_plan_detail(self) -> None:
        self.stack.setCurrentIndex(0)
        self.refresh()

    def _edit_from_detail(self, plan_id: str) -> None:
        self._open_edit_modal(plan_id)
        if any(p.get("id") == plan_id for p in _get_plans()):
            self._refresh_detail_view()
        else:
            self._close_plan_detail()

    def _delete_from_detail(self, plan_id: str) -> None:
        if not askUser(tr("prep_confirm_delete")):
            return
        _handle_delete_plan(plan_id)
        self._close_plan_detail()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape and self.cards_container.is_reordering():
            self.cards_container.cancel_reorder()
            return
        super().keyPressEvent(event)

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

def _prep_card_icon_html(addon_path: str, addon_package: str, icon_value: str, fg_color: str) -> str:
    """Renders a plan's icon exactly as the Qt dialog does (render_icon_pixmap
    in prep_station_ui.py): emoji sprite image, tinted system/custom SVG, or
    a plain text glyph as last resort. Keeps the widget's mini card visually
    identical to ExamCard/PlanDetailBanner instead of falling back to blank."""
    from .emoji_sprites import path_for_emoji
    from .assets import system_icon_path

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
        mono_filter = "brightness(0) invert(1)" if fg_color == "#ffffff" else "brightness(0)"
        return f'<img class="prep-card-icon prep-card-icon-mono" style="filter:{mono_filter}" src="{_rel_url(path)}">'
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

    widget_title = html.escape(tr("prep_widget_title"))

    if not active_plans:
        return f"""
<div class="prep-station-widget" onclick="pycmd('openPrepStation')">
  <div class="prep-widget-header">
    <span class="prep-widget-title">{widget_title}</span>
  </div>
  <div class="prep-widget-empty">{html.escape(tr("prep_no_active_plans"))}</div>
</div>"""

    cards_html = ""
    for days_left, p in active_plans[:slot_count]:
        name = html.escape(p.get("name", tr("prep_default_exam_name")))
        color = resolve_plan_color(p)
        enriched = _enrich_plan(p)
        pace = enriched.get("_pace") or {}
        req = pace.get("required_per_day")
        status = pace.get("status", "")

        if status == "expired":
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

        fg_on_band = readable_on(color)
        icon_html = _prep_card_icon_html(addon_path, addon_package, p.get("icon", "emoji:📚"), fg_on_band)

        progress_html = ""

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
<div class="prep-station-widget" onclick="pycmd('openPrepStation')">
  <div class="prep-widget-header">
    <span class="prep-widget-title">{widget_title}</span>
  </div>
  <div class="prep-plan-cards" style="grid-template-columns: repeat({slot_count}, 1fr);">
    {cards_html}
  </div>
</div>"""
