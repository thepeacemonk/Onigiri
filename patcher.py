import os
import re
import json
import base64
import html
from anki.hooks import wrap
from . import webview_handlers

# Default configuration values
DEFAULTS = {
    "congratsMessage": "Congratulations! You have finished this deck for now."
}

# Import after DEFAULTS to avoid circular imports
from aqt import mw, gui_hooks
from aqt.qt import *
import aqt
from aqt import mw, gui_hooks
from .onigiri_notifications import notify as tooltip
from .onigiri_notifications import notify_info as showInfo
from aqt.webview import AnkiWebView
from aqt.deckbrowser import DeckBrowser
from aqt.main import MainWebView
from aqt.utils import tr as anki_tr
from aqt.overview import Overview
from aqt.reviewer import Reviewer
import os
import json
import time
import re
import html
import base64
import random
import math
import webbrowser
import copy
import sys
from datetime import datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs, urlencode, unquote, quote_plus
from typing import Optional, Dict, List, Tuple, Any, Callable, Union
from . import config
from . import onigiri_renderer
from .decks import tree_updater as deck_tree_updater
from . import heatmap
from .translations import tr as tr_at
from .constants import COLOR_LABELS
from .emoji_sprites import asset_for_emoji

# Use Onigiri's string-key translator throughout this module. Anki 25.09's
# translator expects structured keys, so passing Onigiri keys to it crashes.
tr = tr_at

_OVERVIEW_FORMAT_KEYS = ("deck", "table", "shareLink", "desc")


def _selected_deck_ids(col):
    deck_id = int(col.decks.current()["id"])
    deck_ids = [deck_id]
    try:
        deck_ids.extend(int(child_id) for child_id in col.decks.child_ids(deck_id))
    except Exception:
        # A parent deck should still get a working notice on Anki versions
        # where the child-deck helper has changed.
        pass
    return list(dict.fromkeys(deck_ids))


def _ready_learning_card_ids(col):
    """Return ready learning cards in the selected deck tree.

    Use Anki's search backend for scheduler semantics, then hand the Browser an
    explicit cid list so the result represents the moment the button was
    clicked rather than a broader, reusable search.
    """
    current_deck = col.decks.current()
    deck_name = str(current_deck.get("name", ""))
    if not deck_name:
        return []
    deck_search_value = json.dumps(deck_name, ensure_ascii=False)
    card_ids = col.find_cards(f"deck:{deck_search_value} is:learn is:due")
    return [int(card_id) for card_id in card_ids]


def _learning_due_later_info(col):
    """Return today's learning data for the currently selected deck.

    ``congratulations_info()`` reads Anki's *active study queue*, which may
    still belong to the previously studied deck while the user browses the
    overview. Query the selected deck and its children directly so every deck
    shows its own next-learning time and remaining count.
    """
    info = {
        "next_seconds": None,
        "later_today": 0,
        "ready_now": 0,
    }

    # This is the exact source used by the green Learning bubble in new_table().
    # Keep it independent from the direct SQL query so one compatibility issue
    # cannot erase the entire notice.
    try:
        counts = list(col.sched.counts())
        if len(counts) > 1:
            info["ready_now"] = max(0, int(counts[1] or 0))
    except Exception:
        pass

    try:
        now = int(time.time())
        day_cutoff = int(col.sched.day_cutoff)
        dids_sql = ",".join(str(deck_id) for deck_id in _selected_deck_ids(col))
        row = col.db.first(
            "select min(due), count() from cards "
            f"where queue = 1 and due > ? and due < ? and did in ({dids_sql})",
            now,
            day_cutoff,
        )
        next_due, remaining = row or (None, 0)
        if next_due is not None:
            info["next_seconds"] = max(60, int(next_due) - now)
        info["later_today"] = max(0, int(remaining or 0))
    except Exception:
        pass

    return info


def _learning_notice_enabled(conf, surface):
    """Read the independent placement setting with a legacy fallback."""
    key = (
        "showNextLearningCardNoticeOnCongrats"
        if surface == "congrats"
        else "showNextLearningCardNoticeOnOverview"
    )
    return bool(conf.get(key, conf.get("showOverviewDueLaterNotice", True)))


def _learning_due_later_notice(col, enabled=True):
    """Build the optional native-style next-learning notice for Onigiri.

    This runs inside Anki's overview renderer. It is strictly decorative, so a
    scheduler or translation compatibility problem must never prevent a deck
    from opening.
    """
    try:
        return _build_learning_due_later_notice(col, enabled)
    except Exception:
        # This surface is optional, but an enabled notice must never silently
        # disappear. Keep the fallback entirely scheduler-independent.
        if not enabled:
            return ""
        return (
            '<div class="onigiri-learning-due-notice">'
            f"<p>{html.escape(str(tr_at('no_learning_cards_later_today', 'No learning cards later today here.')))}</p>"
            "</div>"
        )


def _build_learning_due_later_notice(col, enabled=True):
    """Inner notice renderer; callers should use the fail-safe wrapper above."""
    if not enabled:
        return ""

    info = _learning_due_later_info(col)
    notice_parts = ['<div class="onigiri-learning-due-notice">']
    seconds = info["next_seconds"]
    ready_now = info["ready_now"]
    ready_count_text = ""
    ready_button_suffix = ""
    if ready_now == 1:
        ready_count_text = tr_at(
            "one_learning_card_count",
            "One learning card",
        )
        ready_state_text = tr_at(
            "one_learning_card_ready_suffix",
            "is ready now.",
        )
    elif ready_now > 1:
        ready_count_text = tr_at(
            "learning_cards_count",
            "{count} learning cards",
        ).format(count=ready_now)
        ready_state_text = tr_at(
            "learning_cards_ready_suffix",
            "are ready now.",
        )
    else:
        ready_state_text = ""

    if ready_now:
        ready_button_suffix = f" {ready_state_text}"

    if seconds is None:
        if ready_now:
            no_more_text = tr_at(
                "no_additional_learning_cards_later_today",
                "No additional learning cards are due later today.",
            )
            ready_button_suffix += f" {no_more_text}"
        else:
            notice_parts.append(f"<p>{html.escape(tr_at('no_learning_cards_later_today'))}</p>")
    else:
        remaining = info["later_today"]
        if seconds < 60:
            amount, unit = seconds, "seconds"
        elif seconds < 3600:
            amount, unit = round(seconds / 60), "minutes"
        else:
            amount, unit = round(seconds / 3600), "hours"

        try:
            next_due = col.tr.scheduling_next_learn_due(amount=amount, unit=unit)
            remaining_due = col.tr.scheduling_learn_remaining(remaining=remaining)
        except Exception:
            try:
                duration = col.format_timespan(seconds)
            except Exception:
                duration = f"{amount} {unit}"
            next_due = f"The next learning card will be ready in {duration}."
            if remaining == 1:
                remaining_due = "There is one remaining learning card due later today."
            else:
                remaining_due = f"There are {remaining} learning cards due later today."
        notice_parts.extend(
            (
                f"<p>{html.escape(str(next_due))}</p>",
                f"<p>{html.escape(str(remaining_due))}</p>",
            )
        )

    if ready_now:
        ready_label = html.escape(str(ready_count_text))
        suffix_label = html.escape(str(ready_button_suffix))
        action_label = html.escape(
            str(tr_at("browse_ready_learning_cards", "Browse ready learning cards")),
            quote=True,
        )
        notice_parts.append(
            '<button type="button" class="onigiri-learning-browse-button" '
            f'aria-label="{action_label}" title="{action_label}" '
            'onclick="pycmd(\'onigiri_browse_ready_learning\'); return false;">'
            f'<span class="onigiri-learning-ready-text">{ready_label}</span>'
            f"{suffix_label}</button>"
        )
    notice_parts.append("</div>")
    return "".join(notice_parts)


def _escape_overview_body_percent_literals(html_text: str) -> str:
    """Escape literal % signs in Overview._body without touching Anki slots."""
    if "%" not in html_text:
        return html_text

    percent_token = "__ONIGIRI_LITERAL_PERCENT__"
    format_tokens = {}
    escaped = html_text
    for key in _OVERVIEW_FORMAT_KEYS:
        placeholder = f"%({key})s"
        token = f"__ONIGIRI_OVERVIEW_FORMAT_{key.upper()}__"
        format_tokens[token] = placeholder
        escaped = escaped.replace(placeholder, token)

    escaped = escaped.replace("%%", percent_token)
    escaped = escaped.replace("%", "%%")
    escaped = escaped.replace(percent_token, "%%")
    for token, placeholder in format_tokens.items():
        escaped = escaped.replace(token, placeholder)
    return escaped


def _nook_level():
    from .gamification import nook_level

    return nook_level


def _hexagon_land():
    from .gamification import hexagon_land

    return hexagon_land


def _focus_dango():
    from .gamification import focus_dango

    return focus_dango

# --- Menu Styling ---
def apply_menu_styling():
    """
    Applies modern styling to QMenu widgets (context menus) using Qt Style Sheets.
    This gives the 'Options' menu and others a rounded, modern look.
    """
    # 1. Determine which colors to use based on the current mode
    # Safely check for night mode; default to False if PM not ready
    night_mode = config.effective_night_mode()

    # 2. Define Colors
    if night_mode:
        bg_color = "#2c2c2c"
        border_color = "#424242"
        text_color = "#e0e0e0"
        hover_bg = "#3c3c3c" # Highlight background
        hover_text = "#ffffff"
    else:
        bg_color = "#ffffff"
        border_color = "#d0d0d0"
        text_color = "#000000"
        hover_bg = "#e5f1fb" # Light blue-ish highlight
        hover_text = "#000000"

    # 3. Construct the QSS
    new_style_block = f"""
    /* ONIGIRI_MENU_START */
    QMenu {{
        background-color: {bg_color};
        border: 1px solid {border_color};
        border-radius: 12px;
        padding: 5px;
        color: {text_color};
        font-family: 'Poppins', -apple-system, sans-serif;
    }}
    QMenu::item {{
        background-color: transparent;
        padding: 6px 20px 6px 12px;
        border-radius: 8px;
        margin: 2px 4px;
    }}
    QMenu::item:selected {{
        background-color: {hover_bg};
        color: {hover_text};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {border_color};
        margin: 4px 10px;
    }}
    /* ONIGIRI_MENU_END */
    """
    
    # 4. Inject the stylesheet safely (Replace if exists, Append if not)
    app = QApplication.instance()
    if app:
        current_sheet = app.styleSheet()
        
        # Regex to find existing block
        pattern = re.compile(r'/\* ONIGIRI_MENU_START \*/.*?/\* ONIGIRI_MENU_END \*/', re.DOTALL)
        
        if pattern.search(current_sheet):
            # Replace existing block
            updated_sheet = pattern.sub(new_style_block.strip(), current_sheet)
        else:
            # Append new block
            updated_sheet = current_sheet + "\n" + new_style_block.strip()
            
        app.setStyleSheet(updated_sheet)

def patch_qmenu():
    """
    Patches QMenu to enable translucent background, allowing for real rounded corners
    without square artifacts on the window backdrop.
    """
    # We need to monkeypatch the __init__ method of QMenu
    # to set the WA_TranslucentBackground attribute on every new menu instances.
    
    # Store reference to original init
    if hasattr(QMenu, "_onigiri_patched"):
        return

    original_init = QMenu.__init__

    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        # Enable transparency for the window/widget background
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    # Apply the patch
    QMenu.__init__ = new_init
    QMenu._onigiri_patched = True


# --- Toolbar Patching ---
_managed_hooks = []
_toolbar_patched = False
_original_MainWebView_eventFilter = None


_SYNAPSEPRO_DECK_WIDGETS = (
    {
        "suffix": "level_widget",
        "label": "SynapsePro Level",
        "classes": ("gamewidget", "level-widget"),
    },
    {
        "suffix": "streak_widget",
        "label": "SynapsePro Streak",
        "classes": ("gamewidget", "streak-widget"),
    },
    {
        "suffix": "challenge_widget",
        "label": "SynapsePro Challenge",
        "classes": ("gamewidget", "challenge-widget"),
    },
    {
        "suffix": "next_level_widget",
        "label": "SynapsePro Next Level",
        "classes": ("gamewidget", "next-level-widget"),
    },
    {
        "suffix": "plan_widget",
        "label": "SynapsePro Learning Plan",
        "classes": ("daily-widget", "plan-widget"),
    },
    {
        "suffix": "fact_widget",
        "label": "SynapsePro Daily Fact",
        "classes": ("daily-widget", "fact-widget"),
    },
    {
        "suffix": "stats_widget",
        "label": "SynapsePro Statistics",
        "classes": ("stats-widget-container",),
    },
)

_SYNAPSEPRO_OVERVIEW_WIDGET = {
    "label": "SynapsePro Overview",
    "classes": ("white-box",),
}

_synapsepro_split_hook_cache = {}
_synapsepro_overview_original_bodies = {}
_synapsepro_overview_hooks = []
_synapsepro_theme_hook_wrappers = {}
_synapsepro_overview_bridge_installed = False


class _OnigiriElementExtractor(HTMLParser):
    def __init__(self, required_classes: Tuple[str, ...]):
        super().__init__(convert_charrefs=False)
        self.required_classes = set(required_classes)
        self.style_parts: List[str] = []
        self._style_depth = 0
        self._style_buffer: List[str] = []
        self._capture_depth = 0
        self._capture_buffer: List[str] = []
        self.match_html = ""

    def _attrs_to_text(self, attrs):
        parts = []
        for key, value in attrs:
            if value is None:
                parts.append(key)
            else:
                parts.append(f'{key}="{html.escape(str(value), quote=True)}"')
        return (" " + " ".join(parts)) if parts else ""

    def _start_text(self, tag, attrs):
        return f"<{tag}{self._attrs_to_text(attrs)}>"

    def _end_text(self, tag):
        return f"</{tag}>"

    def _append_text(self, text):
        if self._style_depth:
            self._style_buffer.append(text)
        if self._capture_depth:
            self._capture_buffer.append(text)

    def _classes_match(self, attrs):
        class_value = ""
        for key, value in attrs:
            if key and key.lower() == "class" and value:
                class_value = str(value)
                break
        classes = set(class_value.split())
        return self.required_classes.issubset(classes)

    def handle_starttag(self, tag, attrs):
        text = self._start_text(tag, attrs)
        lower_tag = tag.lower()
        if lower_tag == "style":
            self._style_depth += 1
            self._style_buffer = [text]
        elif self._style_depth:
            self._style_depth += 1
            self._style_buffer.append(text)

        if self._capture_depth:
            self._capture_depth += 1
            self._capture_buffer.append(text)
        elif not self.match_html and self._classes_match(attrs):
            self._capture_depth = 1
            self._capture_buffer = [text]

    def handle_startendtag(self, tag, attrs):
        text = f"<{tag}{self._attrs_to_text(attrs)} />"
        self._append_text(text)
        if not self.match_html and self._classes_match(attrs):
            self.match_html = text

    def handle_endtag(self, tag):
        text = self._end_text(tag)
        lower_tag = tag.lower()
        if self._style_depth:
            self._style_buffer.append(text)
            self._style_depth -= 1
            if self._style_depth == 0:
                self.style_parts.append("".join(self._style_buffer))
                self._style_buffer = []

        if self._capture_depth:
            self._capture_buffer.append(text)
            self._capture_depth -= 1
            if self._capture_depth == 0 and not self.match_html:
                self.match_html = "".join(self._capture_buffer)
                self._capture_buffer = []

    def handle_data(self, data):
        self._append_text(data)

    def handle_entityref(self, name):
        self._append_text(f"&{name};")

    def handle_charref(self, name):
        self._append_text(f"&#{name};")

    def handle_comment(self, data):
        self._append_text(f"<!--{data}-->")

    def handle_decl(self, decl):
        self._append_text(f"<!{decl}>")


def _extract_html_by_classes(html_text: str, required_classes: Tuple[str, ...]) -> str:
    if not html_text or not required_classes:
        return ""
    try:
        parser = _OnigiriElementExtractor(required_classes)
        parser.feed(str(html_text))
        parser.close()
        if not parser.match_html:
            return ""
        styles = "".join(parser.style_parts)
        return styles + parser.match_html
    except Exception as exc:
        print(f"Onigiri: failed to extract external widget {required_classes}: {exc}")
        return ""


def _is_synapsepro_hook(hook) -> bool:
    hook_id = _get_hook_name(hook)
    module_name = getattr(hook, "__module__", "")
    hook_name = getattr(hook, "__name__", "")
    lowered = f"{hook_id} {module_name} {hook_name}".lower()
    return (
        "synapsepro" in lowered
        or "render_all_deck_browser_widgets" in lowered
        or "gamificationplusdailywidgets" in lowered
    )


def _is_synapsepro_overview_hook(hook) -> bool:
    hook_name = getattr(hook, "__name__", "")
    module_name = getattr(hook, "__module__", "")
    lowered = f"{module_name}.{hook_name}".lower()
    return (
        ("on_overview_render" in hook_name.lower() or "overview" in hook_name.lower())
        and "deck_overview" in lowered
    )


def _is_synapsepro_theme_assets_hook(hook) -> bool:
    hook_name = getattr(hook, "__name__", "")
    module_name = getattr(hook, "__module__", "")
    module = sys.modules.get(module_name)
    module_file = str(getattr(module, "__file__", "") or getattr(hook, "__code__", None) or "").lower()
    lowered = f"{module_name}.{hook_name} {module_file}".lower()
    return hook_name == "inject_theme_assets" and ("236979321" in lowered or "synapsepro" in lowered)


def _make_synapsepro_theme_passthrough_hook(original_hook):
    original_id = _get_hook_name(original_hook)
    cached = _synapsepro_theme_hook_wrappers.get(original_id)
    if cached:
        return cached

    def onigiri_synapsepro_theme_passthrough(web_content, context):
        if isinstance(context, Overview):
            return
        return original_hook(web_content, context)

    onigiri_synapsepro_theme_passthrough.__name__ = "onigiri_synapsepro_theme_passthrough"
    onigiri_synapsepro_theme_passthrough.__module__ = getattr(original_hook, "__module__", "synapsepro")
    onigiri_synapsepro_theme_passthrough.__qualname__ = onigiri_synapsepro_theme_passthrough.__name__
    onigiri_synapsepro_theme_passthrough._onigiri_synapsepro_theme_original_hook = original_hook
    _synapsepro_theme_hook_wrappers[original_id] = onigiri_synapsepro_theme_passthrough
    return onigiri_synapsepro_theme_passthrough


def take_control_of_synapsepro_overview_theme_hook():
    try:
        hooks = gui_hooks.webview_will_set_content
        hook_list = getattr(hooks, "_hooks", hooks)
        for index, hook in enumerate(list(hook_list)):
            if getattr(hook, "_onigiri_synapsepro_theme_original_hook", None):
                continue
            if not _is_synapsepro_theme_assets_hook(hook):
                continue
            wrapper = _make_synapsepro_theme_passthrough_hook(hook)
            try:
                hook_list[index] = wrapper
            except Exception:
                try:
                    hook_list.remove(hook)
                except ValueError:
                    pass
                hooks.append(wrapper)
    except Exception as exc:
        print(f"Onigiri: failed to isolate SynapsePro overview theme hook: {exc}")


def _remember_synapsepro_overview_hook(hook) -> None:
    if hook and hook not in _synapsepro_overview_hooks:
        _synapsepro_overview_hooks.append(hook)


def _find_synapsepro_overview_hooks_from_modules():
    hooks = []
    for module_name, module in list(sys.modules.items()):
        lowered_name = str(module_name).lower()
        if "deck_overview" not in lowered_name:
            continue
        hook = getattr(module, "on_overview_render", None)
        if not callable(hook):
            continue
        module_file = str(getattr(module, "__file__", "") or "").lower()
        if "synapsepro" in module_file or "236979321" in module_file or "deck_overview.py" in module_file:
            hooks.append(hook)
    return hooks


def take_control_of_synapsepro_overview_hook():
    try:
        hooks = gui_hooks.webview_will_set_content
        hook_list = getattr(hooks, "_hooks", hooks)
        for hook in list(hook_list):
            if not _is_synapsepro_overview_hook(hook):
                continue
            _remember_synapsepro_overview_hook(hook)
            try:
                hook_list.remove(hook)
            except ValueError:
                pass
        for hook in _find_synapsepro_overview_hooks_from_modules():
            _remember_synapsepro_overview_hook(hook)
            try:
                if hook in hook_list:
                    hook_list.remove(hook)
            except ValueError:
                pass
    except Exception as exc:
        print(f"Onigiri: failed to capture SynapsePro overview hook: {exc}")


def is_synapsepro_identified() -> bool:
    if not synapsepro_addon_installed():
        return False
    try:
        take_control_of_deck_browser_hook()
    except Exception:
        pass

    try:
        for hook in _managed_hooks:
            if _is_synapsepro_hook(hook):
                return True
    except Exception:
        pass

    try:
        for hook in list(gui_hooks.deck_browser_will_render_content._hooks):
            if _is_synapsepro_hook(hook):
                return True
    except Exception:
        pass

    try:
        for hook in list(gui_hooks.webview_will_set_content._hooks):
            if _is_synapsepro_overview_hook(hook):
                return True
    except Exception:
        pass

    try:
        if mw.findChild(QDockWidget, "MobesaLauncherSidebarDock_v2"):
            return True
    except Exception:
        pass

    try:
        addon_manager = getattr(mw, "addonManager", None)
        if addon_manager:
            for addon_id in addon_manager.allAddons():
                try:
                    name = addon_manager.addonName(addon_id)
                except Exception:
                    name = ""
                if "synapsepro" in f"{addon_id} {name}".lower():
                    if hasattr(addon_manager, "isEnabled") and callable(addon_manager.isEnabled):
                        if addon_manager.isEnabled(addon_id):
                            return True
                    else:
                        return True
    except Exception:
        pass

    return False


def _make_synapsepro_split_hook(original_hook, spec):
    def split_hook(deck_browser, content):
        class TempContent:
            stats = ""
            tree = ""
            body = ""

        temp_content = TempContent()
        original_hook(deck_browser, temp_content)
        combined_html = "".join(
            str(getattr(temp_content, attr, "") or "")
            for attr in ("stats", "tree", "body")
        )
        content.stats = _extract_html_by_classes(combined_html, spec["classes"])

    split_hook.__name__ = f"onigiri_synapsepro_{spec['suffix']}"
    split_hook.__module__ = getattr(original_hook, "__module__", "synapsepro")
    split_hook.__qualname__ = split_hook.__name__
    split_hook._onigiri_external_display_name = spec["label"]
    split_hook._onigiri_synapsepro_original_hook = original_hook
    return split_hook


def _get_synapsepro_split_hooks(original_hook):
    original_id = _get_hook_name(original_hook)
    cached = _synapsepro_split_hook_cache.get(original_id)
    if cached:
        return cached
    hooks = [_make_synapsepro_split_hook(original_hook, spec) for spec in _SYNAPSEPRO_DECK_WIDGETS]
    _synapsepro_split_hook_cache[original_id] = hooks
    return hooks


def get_external_hook_display_name(hook_id: str, fallback: str = "") -> str:
    hook_id = str(hook_id or "")
    for spec in _SYNAPSEPRO_DECK_WIDGETS:
        if hook_id.endswith(f"onigiri_synapsepro_{spec['suffix']}"):
            return spec["label"]
    return fallback or hook_id.split(".")[0]


def _sanitize_synapsepro_overview_widget_html(widget_html: str) -> str:
    if not widget_html:
        return ""
    page_selector_pattern = re.compile(
        r"(?<![\w-])(?:html|body|#overview-wrapper|#overview|\.overview-container|\.main|\.toolbar|\.bottom)(?:\b|[:.#\s>+~\[,])",
        flags=re.IGNORECASE,
    )
    white_box_selector_pattern = re.compile(
        r"(?<![\w-])\.white-box(?:\b|[:.#\s>+~\[,])",
        flags=re.IGNORECASE,
    )

    def sanitize_style_tag(match):
        style_open = match.group(1)
        css_text = match.group(2)
        style_close = match.group(3)

        def keep_widget_rules(rule_match):
            selectors = rule_match.group(1)
            if page_selector_pattern.search(selectors) and not white_box_selector_pattern.search(selectors):
                return ""
            return rule_match.group(0)

        css_text = re.sub(r"([^{}@][^{}]*)\{([^{}]*)\}", keep_widget_rules, css_text)
        return f"{style_open}{css_text}{style_close}"

    sanitized = re.sub(
        r"(<style\b[^>]*>)(.*?)(</style>)",
        sanitize_style_tag,
        widget_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    sanitized = re.sub(
        r"\.overview-container\s*,\s*\.bottom\s*,\s*#overview\s*,\s*\.toolbar\s*,\s*\.main\s*\{[^{}]*display\s*:\s*none\s*!important;?[^{}]*\}",
        "",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"#overview-wrapper\s*\{[^{}]*\}",
        "",
        sanitized,
        flags=re.IGNORECASE,
    )
    return sanitized


def _synapsepro_overview_background_priority_css(addon_path: str) -> str:
    """Keep SynapsePro's overview theme from taking over Onigiri's page background."""
    conf = config.get_config_readonly()
    overview_mode = conf.get("onigiri_overview_bg_mode", "main")
    main_mode = mw.col.conf.get("modern_menu_background_mode", "color")
    has_image_layer = (
        overview_mode in ("image_color", "slideshow")
        or (overview_mode == "main" and main_mode in ("image", "image_color", "slideshow"))
    )

    if overview_mode == "main":
        light_color = mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
        dark_color = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
    else:
        light_color = conf.get("onigiri_overview_bg_light_color", "#FFFFFF")
        dark_color = conf.get("onigiri_overview_bg_dark_color", "#2C2C2C")

    if has_image_layer:
        return f"""
        <style id="onigiri-synapsepro-background-priority">
            html {{
                background-color: {light_color} !important;
                background-image: none !important;
            }}
            body,
            body.overview,
            body.onigiri-overview,
            body:has(#custom-dashboard) {{
                background: transparent !important;
                background-image: none !important;
                background-color: transparent !important;
                background-attachment: scroll !important;
            }}
            .night-mode html,
            .nightMode html {{
                background-color: {dark_color} !important;
                background-image: none !important;
            }}
            .night-mode body,
            .nightMode body,
            body.nightMode.overview,
            body.nightMode.onigiri-overview,
            body.nightMode:has(#custom-dashboard) {{
                background: transparent !important;
                background-image: none !important;
                background-color: transparent !important;
                background-attachment: scroll !important;
            }}
            body::before {{
                z-index: 0 !important;
            }}
            body > *:not(style):not(script) {{
                position: relative;
                z-index: 1;
            }}
        </style>
        """

    return f"""
    <style id="onigiri-synapsepro-background-priority">
        html,
        body,
        body.overview,
        body.onigiri-overview,
        body:has(#custom-dashboard) {{
            background-image: none !important;
            background-color: {light_color} !important;
            background-attachment: scroll !important;
        }}
        .night-mode html,
        .night-mode body,
        .nightMode html,
        .nightMode body,
        body.nightMode.overview,
        body.nightMode.onigiri-overview,
        body.nightMode:has(#custom-dashboard) {{
            background-image: none !important;
            background-color: {dark_color} !important;
            background-attachment: scroll !important;
        }}
    </style>
    """


def extract_synapsepro_overview_widget(body_html: str) -> str:
    widget_html = _extract_html_by_classes(body_html, _SYNAPSEPRO_OVERVIEW_WIDGET["classes"])
    if not widget_html:
        return ""
    widget_html = _sanitize_synapsepro_overview_widget_html(widget_html)
    return (
        '<div class="onigiri-external-overview-addon onigiri-synapsepro-overview-widget">'
        f"{widget_html}"
        "</div>"
    )


def _render_synapsepro_overview_widget_from_hooks(context) -> str:
    if not _synapsepro_overview_hooks:
        take_control_of_synapsepro_overview_hook()
    for hook in list(_synapsepro_overview_hooks):
        class TempWebContent:
            body = ""
            head = ""
            css = []
            js = []

        temp_content = TempWebContent()
        try:
            hook(temp_content, context)
        except Exception as exc:
            print(f"Onigiri: failed to render SynapsePro overview widget: {exc}")
            continue
        widget_html = extract_synapsepro_overview_widget(getattr(temp_content, "body", "") or "")
        if widget_html:
            return widget_html
    return ""


def _strip_synapsepro_overview_assets(web_content) -> None:
    try:
        css_files = getattr(web_content, "css", None)
        if isinstance(css_files, list):
            web_content.css = [
                css_file
                for css_file in css_files
                if "236979321/theme/user_files/" not in str(css_file)
            ]
    except Exception as exc:
        print(f"Onigiri: failed to strip SynapsePro overview CSS: {exc}")


def inject_synapsepro_overview_widget(web_content, context):
    if not isinstance(context, Overview):
        return
    if not synapsepro_addon_installed():
        return
    # Hook ownership is established once during profile setup.  Reordering the
    # same hook while Qt is dispatching it can leave duplicate callbacks behind
    # and eventually terminate Anki after repeated deck transitions.
    if not _synapsepro_overview_hooks:
        _synapsepro_overview_original_bodies.pop(id(context), None)
        return

    addon_path = os.path.dirname(__file__)
    background_guard = (
        generate_overview_background_css(addon_path)
        + _synapsepro_overview_background_priority_css(addon_path)
        + """
    <style id="onigiri-synapsepro-overview-guard">
        #overview-wrapper {
            background: transparent !important;
        }
        body.onigiri-overview .overview-center-container,
        body.onigiri-overview #overview-wrapper,
        body.onigiri-overview #overview,
        body.onigiri-overview .main,
        body.onigiri-overview .toolbar,
        body.onigiri-overview .bottom {
            background: transparent !important;
            background-image: none !important;
        }
    </style>
    """
    )
    _strip_synapsepro_overview_assets(web_content)
    body = _synapsepro_overview_original_bodies.pop(id(context), None)
    if not body:
        body = getattr(web_content, "body", "") or ""
        if "custom-dashboard" in body or "SynapsePro" in body:
            print("Onigiri: SynapsePro overview override could not restore a captured body.")
    web_content.body = body + background_guard


def capture_onigiri_overview_body(web_content, context):
    if not synapsepro_addon_installed():
        return
    if isinstance(context, Overview):
        _synapsepro_overview_original_bodies[id(context)] = getattr(web_content, "body", "") or ""


_synapsepro_installed_cache = None


def synapsepro_addon_installed() -> bool:
    """
    Cheap, cached "is SynapsePro installed" check.

    The full is_synapsepro_identified() walks sys.modules and every hook list;
    running that on each screen change and each overview render was pure
    overhead for the ~all users who do not have SynapsePro. The add-on list
    cannot change without a restart, so this is safe to cache for the session.
    """
    global _synapsepro_installed_cache
    if _synapsepro_installed_cache is not None:
        return _synapsepro_installed_cache

    present = False
    try:
        addon_manager = getattr(mw, "addonManager", None)
        if addon_manager:
            for addon_id in addon_manager.allAddons():
                try:
                    name = addon_manager.addonName(addon_id)
                except Exception:
                    name = ""
                if "synapsepro" in f"{addon_id} {name}".lower() or "236979321" in str(addon_id):
                    present = True
                    break
    except Exception:
        present = False
    _synapsepro_installed_cache = present
    return present


def ensure_synapsepro_overview_bridge_hook():
    global _synapsepro_overview_bridge_installed
    if not synapsepro_addon_installed():
        return
    if _synapsepro_overview_bridge_installed:
        return
    try:
        take_control_of_synapsepro_overview_hook()
        take_control_of_synapsepro_overview_theme_hook()
        hooks = gui_hooks.webview_will_set_content
        hook_list = getattr(hooks, "_hooks", None)
        if isinstance(hook_list, list):
            for hook in (capture_onigiri_overview_body, inject_synapsepro_overview_widget):
                try:
                    hook_list.remove(hook)
                except ValueError:
                    pass
            hook_list.insert(0, capture_onigiri_overview_body)
            hook_list.append(inject_synapsepro_overview_widget)
        else:
            hooks.append(capture_onigiri_overview_body)
            hooks.append(inject_synapsepro_overview_widget)
        _synapsepro_overview_bridge_installed = True
    except Exception as exc:
        print(f"Onigiri: failed to install SynapsePro overview bridge: {exc}")


def apply_synapsepro_sidebar_visibility(conf=None):
    conf = conf or config.get_config_readonly()
    if not conf.get("hideSynapseProSidebar", False):
        return
    try:
        dock = mw.findChild(QDockWidget, "MobesaLauncherSidebarDock_v2")
        if dock:
            dock.setVisible(False)
            dock.hide()
    except Exception as exc:
        print(f"Onigiri: failed to hide SynapsePro sidebar: {exc}")


def get_sync_status():
    """
    Determines the current sync status of the collection.
    Returns 'sync' if any sync is needed, 'none' if no sync needed.
    """
    try:
        # Check if collection is available
        if not mw.col:
            return 'none'
        
        # Get last sync timestamp and modification time from database
        try:
            # Get last sync timestamp from database
            ls = mw.col.db.scalar("select ls from col")
            mod = mw.col.mod if hasattr(mw.col, 'mod') else 0
            
            # If ls is None or 0, we've never synced - no indicator needed yet
            if ls is None or ls == 0:
                return 'none'
            
            # Show sync needed if mod > ls (changes since last sync)
            if mod > ls:
                return 'sync'
        except:
            pass
        
        # No sync needed
        return 'none'
    except:
        return 'none'


def _get_profile_pic_html(user_name: str, addon_package: str, css_class: str = "profile-pic") -> str:    
    """Generates profile picture HTML (img or default) based on user settings."""
    is_dark = config.effective_night_mode()
    mode = mw.col.conf.get("modern_menu_profile_picture_mode", "image")
    dynamic = bool(mw.col.conf.get("modern_menu_profile_picture_dynamic_mode", True))
    theme_key = "dark" if is_dark else "light"
    color = mw.col.conf.get(f"modern_menu_profile_picture_color_{theme_key}", "#B8BDC3" if is_dark else "#8CACB4") if dynamic else mw.col.conf.get("modern_menu_profile_picture_color_light", "#8CACB4")
    if mode == "accent":
        color = "var(--accent-color)"
    
    blur = max(0, min(100, int(mw.col.conf.get("modern_menu_profile_picture_blur", 0) or 0)))
    style_parts = []
    if blur:
        style_parts.append(f"filter: blur({blur * 0.2}px)")

    if mode in {"accent", "custom"}:
        initial = html.escape((user_name[:1] or "U").upper(), quote=False)
        style_parts.insert(0, f"background-color: {color}")
        style_str = "; ".join(style_parts)
        return f'<span class="{css_class} profile-pic-generated" style="{style_str}">{initial}</span>'

    if dynamic:
        profile_pic_filename = mw.col.conf.get(f"modern_menu_profile_picture_{theme_key}", "") or mw.col.conf.get("modern_menu_profile_picture", "")
    else:
        profile_pic_filename = mw.col.conf.get("modern_menu_profile_picture", "")

    if profile_pic_filename and os.path.exists(os.path.join(mw.addonManager.addonsFolder(addon_package), "user_files", "profile", profile_pic_filename)):
        pic_url = f"/_addons/{addon_package}/user_files/profile/{profile_pic_filename}"
    else:
        default_pic = "onigiri-san.png"
        pic_url = f"/_addons/{addon_package}/system_files/profile_default/{default_pic}"

    style_attr = f' style="{"; ".join(style_parts)}"' if style_parts else ""
    return f'<img src="{pic_url}" class="{css_class}"{style_attr}>'


def take_control_of_deck_browser_hook():
    """
    Finds external hooks and stores them for Onigiri to render inside its
    custom deck browser.

    Keep the hooks registered with Anki. Some add-ons, including Anki
    Leaderboard, reorder their own hook later; removing it here makes their
    remove/re-append step fail and can break their home widget.
    """
    global _managed_hooks
    onigiri_module_name = config.__name__.split('.')[0]
    known_hook_indexes = {
        _get_hook_name(hook): index
        for index, hook in enumerate(_managed_hooks)
    }

    for hook in list(gui_hooks.deck_browser_will_render_content._hooks):
        hook_id = _get_hook_name(hook)
        should_manage = onigiri_module_name not in hook_id or "learner_stats_widget" in hook_id
        if not should_manage:
            continue
        if hook_id in known_hook_indexes:
            _managed_hooks[known_hook_indexes[hook_id]] = hook
            _synapsepro_split_hook_cache.pop(hook_id, None)
        else:
            _managed_hooks.append(hook)
            known_hook_indexes[hook_id] = len(_managed_hooks) - 1

def _render_background_css(selector, mode, light_color, dark_color, light_image_path, dark_image_path, blur_val, addon_path, style_id, opacity_val=100, background_position="center"):
	"""Internal helper to generate a complete <style> block for a given background configuration."""
	blur_px = blur_val * 0.2
	addon_name = os.path.basename(addon_path)

	def get_img_url(image_path):
		if not image_path:
			return None
		if image_path.startswith("user_files/"):
			return f"/_addons/{addon_name}/{image_path}"
		else:
			return f"/_addons/{addon_name}/user_files/{image_path}"

	if mode == "accent":
		return f"""<style id="{style_id}">{selector} {{ background: var(--accent-color) !important; }}</style>"""

	if mode == "color":
		return f"""<style id="{style_id}">
			{selector} {{ background-color: {light_color} !important; }}
			.night-mode {selector} {{ background-color: {dark_color} !important; }}
		</style>"""

	# --- START OF REVISED LOGIC ---

	elif mode == "image":
		light_img_url = get_img_url(light_image_path)
		dark_img_url = get_img_url(dark_image_path) if dark_image_path else light_img_url
		if not light_img_url: return ""

		opacity_float = opacity_val / 100.0
		# Scale factor to prevent white borders when blur is applied
		scale = 1.0 + (blur_px / 50.0) if blur_px > 0 else 1.0
		if 'body' in selector:
			base_before_css = f"""
				content: ''; position: fixed;
				top: 50%; left: 50%;
				width: 100vw; height: 100vh;
				transform: translate(-50%, -50%) scale({scale});
				background-size: cover; background-position: {background_position};
				background-repeat: no-repeat; filter: blur({blur_px}px);
				image-rendering: -webkit-optimize-contrast; image-rendering: crisp-edges;
				opacity: {opacity_float}; z-index: 0;
				pointer-events: none;
			"""
		else:
			base_before_css = f"""
				content: ''; position: absolute;
				top: 50%; left: 50%;
				width: 100%; height: 100%;
				transform: translate(-50%, -50%) scale({scale});
				background-size: cover; background-position: {background_position};
				background-repeat: no-repeat; filter: blur({blur_px}px);
				image-rendering: -webkit-optimize-contrast; image-rendering: crisp-edges;
				opacity: {opacity_float}; z-index: 0;
			"""

		image_css = f"{selector}::before {{ {base_before_css} background-image: url('{light_img_url}'); }}"
		if dark_img_url and dark_img_url != light_img_url:
			image_css += f"\n.night-mode {selector}::before {{ background-image: url('{dark_img_url}'); }}"

		container_css = ""
		if "body" in selector:
			container_css += f"html {{ background: transparent !important; overflow: hidden !important; }} {selector} {{ background: transparent !important; overflow: hidden !important; }}"
		else:
			container_css += f"{selector} {{ background: transparent; overflow: hidden; isolation: isolate; }}"

		if "container" in selector or ".sidebar-left" in selector or "#outer" in selector:
			container_css += f"{selector} {{ position: relative; z-index: 1; overflow: hidden; isolation: isolate; }} {selector} > * {{ position: relative; z-index: 1; }}"
		elif "body" in selector:
			container_css += f"{selector} {{ position: relative; z-index: 1; overflow: hidden; }}"

		return f"<style id='{style_id}'>{container_css}\n{image_css}</style>"

    # Located in patcher.py

	elif mode == "image_color":
		light_img_url = get_img_url(light_image_path)
		dark_img_url = get_img_url(dark_image_path) if dark_image_path else light_img_url

		# If no image, fallback to solid color
		if not light_img_url:
				return f"""<style id="{style_id}">
					{selector} {{ background-color: {light_color} !important; }}
					.night-mode {selector} {{ background-color: {dark_color} !important; }}
				</style>"""

		# --- START OF FIX ---
		image_opacity = opacity_val / 100.0
		blur_px = blur_val * 0.2
		# Scale factor to prevent white borders when blur is applied
		scale = 1.0 + (blur_px / 50.0) if blur_px > 0 else 1.0

		# This pseudo-element holds the background image with its effects.
		if 'body' in selector:
			base_before_css = f"""
				content: ''; position: fixed;
				top: 50%; left: 50%;
				width: 100vw; height: 100vh;
				transform: translate(-50%, -50%) scale({scale});
				background-size: cover; background-position: {background_position};
				background-repeat: no-repeat;
				filter: blur({blur_px}px);
				opacity: {image_opacity};
				z-index: 0;
				pointer-events: none;
			"""
		else:
			base_before_css = f"""
				content: ''; position: absolute;
				top: 50%; left: 50%;
				width: 100%; height: 100%;
				transform: translate(-50%, -50%) scale({scale});
				background-size: cover; background-position: {background_position};
				background-repeat: no-repeat;
				filter: blur({blur_px}px);
				opacity: {image_opacity};
				z-index: 0;
			"""

		image_css = f"{selector}::before {{ {base_before_css} background-image: url('{light_img_url}'); }}"
		if dark_img_url and dark_img_url != light_img_url:
			image_css += f"\n.night-mode {selector}::before {{ background-image: url('{dark_img_url}'); }}"

		# The container gets the SOLID color and acts as a positioning context.
		if "body" in selector:
			container_css = f"""
				html {{ background: transparent !important; overflow: hidden !important; }}
				{selector} {{
					position: relative; z-index: 1; overflow: hidden !important;
					background-color: {light_color} !important;
				}}
				.night-mode {selector} {{
					background-color: {dark_color} !important;
				}}
			"""
		else:
			container_css = f"""
				{selector} {{
					position: relative; z-index: 1; overflow: hidden; isolation: isolate;
					background-color: {light_color} !important;
				}}
				.night-mode {selector} {{
					background-color: {dark_color} !important;
				}}
				{selector} > * {{
					position: relative;
					z-index: 1;
				}}
			"""

		return f"<style id='{style_id}'>{container_css}\n{image_css}</style>"
	# --- END OF REVISED LOGIC ---

	return ""

def _render_body_slideshow_background_css(style_id, image_urls, interval_seconds, light_color, dark_color, blur_val, opacity_val, extra_css=""):
    if not image_urls:
        return f"""<style id="{style_id}">
            html, body {{
                background-color: {light_color} !important;
                background-image: none !important;
            }}
            .night-mode html, .night-mode body,
            .nightMode html, .nightMode body {{
                background-color: {dark_color} !important;
            }}
            body::before,
            body::after,
            html::before,
            html::after,
            #overview-wrapper::before,
            #overview-wrapper::after,
            #overview::before,
            #overview::after,
            .main::before,
            .main::after,
            .toolbar::before,
            .toolbar::after,
            .bottom::before,
            .bottom::after {{
                content: none !important;
                background: none !important;
                background-image: none !important;
            }}
            {extra_css}
        </style>"""

    blur_px = blur_val * 0.2
    scale = 1.0 + (blur_px / 50.0) if blur_px > 0 else 1.0
    opacity_float = opacity_val / 100.0
    transition_class = f"{style_id}-transitioning"
    before_id = f"{style_id}-before-image"
    after_id = f"{style_id}-after-image"

    return f"""
    <style id="{style_id}">
        body {{
            position: relative;
            overflow-y: auto !important;
            background-image: none !important;
            background-color: {light_color} !important;
        }}
        .night-mode body,
        .nightMode body {{
            background-color: {dark_color} !important;
        }}
        body::before,
        body::after {{
            content: '' !important;
            position: fixed;
            top: 50%;
            left: 50%;
            width: 100vw;
            height: 100vh;
            transform: translate(-50%, -50%) scale({scale});
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            filter: blur({blur_px}px);
            pointer-events: none;
        }}
        body::before {{
            background-image: url('{image_urls[0]}') !important;
            opacity: {opacity_float} !important;
            z-index: -2 !important;
        }}
        body::after {{
            opacity: 0 !important;
            z-index: -1 !important;
            transition: opacity 1.2s cubic-bezier(0.4, 0, 0.2, 1);
        }}
        body.{transition_class}::after {{
            opacity: {opacity_float} !important;
        }}
        .overview-center-container, .congrats-container,
        #overview-wrapper, #overview, .main, .toolbar, .bottom {{
            background: transparent !important;
            background-image: none !important;
        }}
        html::before,
        html::after,
        #overview-wrapper::before,
        #overview-wrapper::after,
        #overview::before,
        #overview::after,
        .main::before,
        .main::after,
        .toolbar::before,
        .toolbar::after,
        .bottom::before,
        .bottom::after {{
            content: none !important;
            background: none !important;
            background-image: none !important;
        }}
        {extra_css}
    </style>
    <script>
        (function() {{
            const images = {json.dumps(image_urls)};
            const interval = {max(1, int(interval_seconds or 10)) * 1000};
            let nextIndex = 1;

            function updateBackground() {{
                if (!document.body || images.length < 2) return;

                let afterStyleTag = document.getElementById('{after_id}');
                if (!afterStyleTag) {{
                    afterStyleTag = document.createElement('style');
                    afterStyleTag.id = '{after_id}';
                    document.head.appendChild(afterStyleTag);
                }}
                afterStyleTag.textContent = `body::after {{ background-image: url('${{images[nextIndex]}}') !important; }}`;

                setTimeout(() => {{
                    document.body.classList.add('{transition_class}');
                }}, 50);

                setTimeout(() => {{
                    let beforeStyleTag = document.getElementById('{before_id}');
                    if (!beforeStyleTag) {{
                        beforeStyleTag = document.createElement('style');
                        beforeStyleTag.id = '{before_id}';
                        document.head.appendChild(beforeStyleTag);
                    }}
                    beforeStyleTag.textContent = `body::before {{ background-image: url('${{images[nextIndex]}}') !important; }}`;
                    document.body.classList.remove('{transition_class}');
                    nextIndex = (nextIndex + 1) % images.length;
                }}, 1250);
            }}

            if (images.length > 1) {{
                setInterval(updateBackground, interval);
            }}
        }})();
    </script>
    """

# --- Profile Page Generation ---

# Nook Level and Mr. Taiyaki's Store are now fully rendered in WebViews. Keep
# these public functions here because the deck browser and existing menu hooks
# dispatch to patcher, but keep no PyQt game page implementation in this module.
def open_nook_level_dialog():
    from .gamification.nook_web_ui import open_nook_level_dialog as open_page

    open_page()

_onigimon_care_dialog = None

def open_onigimon_care_dialog():
    global _onigimon_care_dialog
    from .gamification.onigimon_web_ui import OnigimonWebDialog
    if _onigimon_care_dialog is not None:
        _onigimon_care_dialog.close()
    _onigimon_care_dialog = OnigimonWebDialog(mw)
    _onigimon_care_dialog.show()
    return _onigimon_care_dialog


def open_mr_taiyaki_store_dialog():
    from .gamification.nook_web_ui import open_taiyaki_store_dialog as open_page

    open_page()


def _profile_level_chip_detail(game, level):
    """Tooltip text for the profile Level chip, per selected game."""
    try:
        if game == "nook":
            from .gamification import nook_level
            progress = nook_level.manager.get_progress()
            xp_into = max(0, getattr(progress, "xp_into_level", 0))
            xp_next = max(1, getattr(progress, "xp_to_next_level", 100))
            return f"{xp_into}/{xp_next} XP"
        if game == "hexagon":
            hexagon_land = _hexagon_land()
            info = hexagon_land.manager.level_info()
            return f"{info['title']} - {info['landsToNext']} lands to next level"
        if game == "onigimon":
            return f"Onigimon Lv {level}"
    except Exception:
        pass
    return f"Lv {level}"


def _get_nook_level_chip_html():
    # Profile Level chip. Which game it reflects is chosen in
    # Settings > Games > Gamification > Profile Level.
    try:
        from . import onigiri_renderer
        game = onigiri_renderer._selected_profile_level_game()
        enabled, level, fraction, level_color = onigiri_renderer._profile_level_progress()
        if not enabled:
            return ""
        # Nook keeps its own "show progress on profile bar" visibility gate.
        if game == "nook":
            conf = config.get_config_readonly()
            restaurant_conf = conf.get("restaurant_level", {}) or conf.get("achievements", {}).get("restaurant_level", {})
            if not restaurant_conf.get("show_profile_bar_progress", True):
                return ""

        from .gamification import nook_level
        chip_style = nook_level.build_chip_style_attr()
        # The selected game supplies the level/fraction, but the progress bar
        # color is shared with Profile Level. Nook's chip-style helper still
        # provides the background/text colors; override only its progress
        # variables so Hexagon Land and Onigimon cannot replace the user's
        # Profile progress color with their own/default accent.
        if level_color:
            safe_color = html.escape(str(level_color), quote=True)
            chip_style = "; ".join(
                part for part in (
                    chip_style,
                    f"--profile-level-bar-bg: {safe_color}",
                    f"--reviewer-level-bar-bg: {safe_color}",
                    f"--reviewer-level-bar-hover-bg: {safe_color}",
                )
                if part
            )
        style_attr = f' style="{chip_style}"' if chip_style else ""

        cmd_map = {"nook": "restaurant_level", "onigimon": "openOnigimonCare", "hexagon": "openHexagonLand"}
        cmd = cmd_map.get(game, "restaurant_level")
        progress_percent = min(100, max(0, fraction * 100))
        detail = _profile_level_chip_detail(game, level)
        return f"""
        <div class="restaurant-level-chip" onclick="event.stopPropagation(); pycmd('{cmd}'); return false;" title="{html.escape(detail, quote=True)}"{style_attr}>
            <span class="rl-chip-level">Lv {level}</span>
            <div class="rl-chip-progress">
                <div class="rl-chip-progress-fill" style="width: {progress_percent:.2f}%"></div>
            </div>
        </div>
        """
    except Exception as e:
        print(f"Onigiri: Error rendering profile level chip: {e}")
        return ""


def _get_reviewer_nook_level_chip_html():
    # Rebuilt after every answered card - read-only, so skip the deep copy.
    conf = config.get_config_readonly()
    restaurant_conf = conf.get("restaurant_level", {})
    if not restaurant_conf:
        restaurant_conf = conf.get("achievements", {}).get("restaurant_level", {})
    if not restaurant_conf.get("enabled", False):
        return ""
    if not restaurant_conf.get("show_reviewer_header", False):
        return ""
    try:
        from .gamification import nook_level
        progress = nook_level.manager.get_progress()
        if not progress or not progress.enabled:
            return ""

        current_level = getattr(progress, "level", 0)
        xp_into_level = max(0, getattr(progress, "xp_into_level", 0))
        xp_to_next_level = max(1, getattr(progress, "xp_to_next_level", 100))
        progress_percent = min(100, max(0, (xp_into_level / xp_to_next_level) * 100))

        chip_style_str = nook_level.build_chip_style_attr()
        style_attr = f' style="{chip_style_str}"' if chip_style_str else ""

        xp_detail = f"{xp_into_level}/{xp_to_next_level} XP"
        return f"""
        <div class="restaurant-level-chip" onclick="pycmd('restaurant_level')" title="{html.escape(xp_detail, quote=True)}"{style_attr}>
            <span class="rl-chip-level">Lv {current_level}</span>
            <div class="rl-chip-progress">
                <div class="rl-chip-progress-fill" style="width: {progress_percent:.2f}%"></div>
            </div>
        </div>
        """
    except Exception as e:
        print(f"Onigiri: Error rendering reviewer restaurant level chip: {e}")
        return ""


def _get_theme_colors_html(mode, conf):
    colors = conf.get("colors", {}).get(mode, {})
    items_html = ""
    
    # Use COLOR_LABELS for ordering and friendly names
    for key, info in COLOR_LABELS.items():
        if key == "--shadow-sm":
            break
        if key in colors:
            hex_val = colors[key]
            items_html += f"""
            <div class="color-item">
                <div class="color-swatch" style="background-color: {hex_val};"></div>
                <div class="color-info">
                    <span class="color-name">{info['label']}</span>
                    <span class="color-code">{hex_val.upper()}</span>
                </div>
            </div>
            """
            
    return f"""
    <h2 class="section-title">{tr("theme_colors_mode").format(mode=mode)}</h2>
    <div class="color-list">{items_html}</div>
    """

def _get_backgrounds_html(addon_package):
    main_bg_style = ""
    main_text = ""
    sidebar_bg_style = ""
    sidebar_text = ""

    # --- 1. Process Main Background ---
    main_mode = mw.col.conf.get("modern_menu_background_mode", "color")

    if main_mode == "image" or main_mode == "image_color":
        if mw.col.conf.get("modern_menu_background_image_mode", "single") == "separate":
            main_img_file = mw.col.conf.get("modern_menu_background_image_light", "")
        else:
            main_img_file = mw.col.conf.get("modern_menu_background_image", "")
            
        if main_img_file:
            main_img_path = f"/_addons/{addon_package}/user_files/main_bg/{main_img_file}"
            main_bg_style = f"background-image: url('{main_img_path}');"
        else:
            main_bg_style = "" # Use default card color
            main_text = "Image mode selected, but no file chosen."
    
    if main_mode == "color" or main_mode == "image_color":
        # Use the correct color for the current theme in the preview swatch
        if config.effective_night_mode():
            color = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
        else:
            color = mw.col.conf.get("modern_menu_bg_color_light", "#FFFFFF")
        # In combo mode, color is applied first, then image style.
        main_bg_style = f"background-color: {color}; {main_bg_style}"

    elif main_mode == "accent":
        main_bg_style = "background-color: var(--accent-color);"

    # --- 2. Process Sidebar Background ---
    sidebar_mode = mw.col.conf.get("modern_menu_sidebar_bg_mode", "main")

    if sidebar_mode == "main":
        sidebar_bg_style = "" # Use default card color
    else: # custom
        sidebar_type = mw.col.conf.get("modern_menu_sidebar_bg_type", "color")
        if sidebar_type == "image" or sidebar_type == "image_color":
            if mw.col.conf.get("modern_menu_sidebar_bg_image_theme_mode", "separate") == "separate":
                image_key = "modern_menu_sidebar_bg_image_dark" if config.effective_night_mode() else "modern_menu_sidebar_bg_image_light"
                sidebar_img_file = mw.col.conf.get(image_key, "")
            else:
                sidebar_img_file = mw.col.conf.get("modern_menu_sidebar_bg_image", "")
            if sidebar_img_file:
                sidebar_img_path = f"/_addons/{addon_package}/user_files/sidebar_bg/{sidebar_img_file}"
                sidebar_bg_style = f"background-image: url('{sidebar_img_path}');"
            else:
                sidebar_bg_style = ""
                sidebar_text = "Image mode selected, but no file chosen."

        elif sidebar_type == "slideshow":
            slideshow_images = mw.col.conf.get("modern_menu_sidebar_slideshow_images", [])
            if slideshow_images:
                sidebar_img_path = f"/_addons/{addon_package}/user_files/sidebar_bg/{slideshow_images[0]}"
                sidebar_bg_style = f"background-image: url('{sidebar_img_path}');"
            else:
                sidebar_bg_style = ""
                sidebar_text = "Slideshow selected, but no images chosen."
        
        if sidebar_type == "color" or sidebar_type == "image_color" or sidebar_type == "slideshow":
            if config.effective_night_mode():
                color = mw.col.conf.get("modern_menu_sidebar_bg_color_dark", "#3C3C3C")
            else:
                color = mw.col.conf.get("modern_menu_sidebar_bg_color_light", "#EEEEEE")
            sidebar_bg_style = f"background-color: {color}; {sidebar_bg_style}"

        elif sidebar_type == "accent":
            sidebar_bg_style = "background-color: var(--accent-color);"

    # --- 3. Construct Final HTML ---
    # The title is changed to "Backgrounds" to be more accurate
    return f"""
    <h2 class="section-title">{tr("backgrounds")}</h2>
    <div class="background-previews">
        <div class="preview-card">
            <div class="preview-image" style="{main_bg_style}">
                <span>{main_text}</span>
            </div>
            <div class="preview-info">{tr("main_background_label")}</div>
        </div>
        <div class="preview-card">
            <div class="preview-image" style="{sidebar_bg_style}">
                 <span>{sidebar_text}</span>
            </div>
            <div class="preview-info">{tr("sidebar_background_label")}</div>
        </div>
    </div>
    """

# --- Caching for Profile Stats ---
_profile_stats_cache = {
    "html": "",
    "timestamp": 0,
    "timeout": 300  # 5 minutes
}

def _get_stats_html():
    global _profile_stats_cache
    import time
    
    # Return cached if valid
    if time.time() - _profile_stats_cache["timestamp"] < _profile_stats_cache["timeout"] and _profile_stats_cache["html"]:
        return _profile_stats_cache["html"]

    conf = config.get_config_readonly()
    show_heatmap = conf.get("showHeatmapOnProfile", True)

    # Calculate today's stats from the database directly
    # This correctly counts only actual reviews from today, not deck resets or other operations
    # type IN (0,1,2,3) filters out manual operations (type 4 = manual rescheduling/resets)
    cards_today, time_today_seconds = mw.col.db.first(
        "select count(), sum(time)/1000 from revlog where type IN (0,1,2,3) and id > ?", 
        (mw.col.sched.day_cutoff - 86400) * 1000
    ) or (0, 0)
    time_today_seconds = time_today_seconds if time_today_seconds is not None else 0
    cards_today = cards_today if cards_today is not None else 0

    time_today_minutes = time_today_seconds / 60
    seconds_per_card = time_today_seconds / cards_today if cards_today > 0 else 0
    
    # --- START: New Retention Calculation ---
    total_reviews, correct_reviews = mw.col.db.first(
        "select count(*), sum(case when ease > 1 then 1 else 0 end) from revlog where type = 1 and id > ?",
        (mw.col.sched.day_cutoff - 86400) * 1000
    ) or (0, 0)
    total_reviews = total_reviews or 0
    correct_reviews = correct_reviews or 0
    retention_percentage = (correct_reviews / total_reviews * 100) if total_reviews > 0 else 0

    if retention_percentage >= 90: stars = 5
    elif retention_percentage >= 70: stars = 4
    elif retention_percentage >= 50: stars = 3
    elif retention_percentage >= 30: stars = 2
    elif total_reviews > 0: stars = 1
    else: stars = 0
    
    star_html = "".join([f"<i class='star{' empty' if i >= stars else ''}'></i>" for i in range(5)])
    hide_retention_stars = conf.get("hideRetentionStars", False)
    retention_card_class = "stat-card retention-card retention-stars-hidden" if hide_retention_stars else "stat-card retention-card"
    star_rating_html = "" if hide_retention_stars else f'<div class="star-rating">{star_html}</div>'

    retention_stat_html = f"""
    <div class="{retention_card_class}">
        <h3>{tr("retention")}</h3>
        <p>{retention_percentage:.0f}%</p>
        {star_rating_html}
    </div>
    """
    # --- END: New Retention Calculation ---

    # 2. Generate the HTML for the stats grid
    stats_grid_parts = [] 
    if not conf.get("hideStudiedStat", False):
        stats_grid_parts.append(f"""<div class="stat-card studied-card"><h3>{tr("studied")}</h3><p>{cards_today} {tr("cards")}</p></div>""")
    if not conf.get("hideTimeStat", False):
        stats_grid_parts.append(f"""<div class="stat-card time-card"><h3>{tr("time")}</h3><p>{time_today_minutes:.1f} min</p></div>""")
    if not conf.get("hidePaceStat", False):
        stats_grid_parts.append(f"""<div class="stat-card pace-card"><h3>{tr("pace")}</h3><p>{seconds_per_card:.1f} s/{tr("card")}</p></div>""")
    # Add the retention card to the grid
    if not conf.get("hideRetentionStat", False):
        stats_grid_parts.append(retention_stat_html)

    stats_grid_html = f"""<div class="stats-grid">{''.join(stats_grid_parts)}</div>""" if stats_grid_parts else ""

    heatmap_html = ""
    if show_heatmap:
        heatmap_html = "<div id='onigiri-profile-heatmap-container'></div>"

    # 3. Construct the final HTML for the stats section
    html_content = f"""
    {stats_grid_html}
    <div id='onigiri-profile-heatmap-wrapper' style='margin-top: 20px;'>
        {heatmap_html}
    </div>
    """
    
    # Update cache
    _profile_stats_cache["html"] = html_content
    _profile_stats_cache["timestamp"] = time.time()
    
    return html_content


def _get_nook_level_profile_html() -> str:
    nook_level = _nook_level()
    payload = nook_level.manager.get_progress_payload()
    if not payload.get("enabled") or not payload.get("showProfilePage"):
        return ""

    level = int(payload.get("level", 0) or 0)
    total_xp = int(payload.get("totalXp", 0) or 0)
    xp_into = int(payload.get("xpIntoLevel", 0) or 0)
    xp_next = int(payload.get("xpToNextLevel", 0) or 0)
    progress_fraction = payload.get("progressFraction", 0.0)

    if not isinstance(progress_fraction, (int, float)):
        progress_fraction = 0.0
    progress_fraction = max(0.0, min(float(progress_fraction), 1.0))
    if xp_next <= 0:
        progress_fraction = 1.0

    percent = f"{progress_fraction * 100:.1f}%"
    if xp_next > 0:
        xp_label = f"{xp_into:,} / {xp_next:,} XP"
    else:
        xp_label = f"{total_xp:,} XP total"

    total_label = f"{total_xp:,} XP total"
    phrase = html.escape(payload.get("phrase") or "Keep serving knowledge!", quote=False)
    custom_name = html.escape(payload.get("name") or "Nook Level", quote=False)

    current_id = nook_level.manager.get_current_theme_id()
    current_image = nook_level.manager.get_current_theme_image() or "sushi/onigiri_stand.webp"
    addon_package = mw.addonManager.addonFromModule(__name__)
    image_url = f"/_addons/{addon_package}/system_files/gamification_images/nook_folder/{html.escape(current_image, quote=True)}"
    current_restaurant_name = custom_name
    try:
        store_data = nook_level.manager.get_store_data()
        restaurants = store_data.get("restaurants", {})
        evolutions = store_data.get("evolutions", {})
        shops = store_data.get("shops", {})
        item_data = restaurants.get(current_id) or evolutions.get(current_id) or shops.get(current_id)
        if item_data and item_data.get("name"):
            current_restaurant_name = html.escape(item_data.get("name"), quote=False)
    except Exception:
        pass

    bar_mode = mw.col.conf.get("onigiri_profile_level_bar_mode", "theme")
    if bar_mode == "custom":
        bar_color = mw.col.conf.get("onigiri_profile_level_bar_custom_color", "#4CAF50")
    else:
        bar_color = nook_level.manager.get_current_theme_color()

    style_attr = ""
    if bar_color:
        style_attr = f'style="--profile-level-bar-bg: {bar_color};"'

    return f"""
    <section class="profile-restaurant-level" data-level="{level}" {style_attr}>
        <header class="prl-header">
            <img class="prl-image" src="{image_url}" alt="">
            <div class="prl-title-group">
                <span class="prl-title">{current_restaurant_name}</span>
                <span class="prl-name">{custom_name}</span>
                <span class="prl-level">Lv {level}</span>
            </div>
            <span class="prl-total">{html.escape(total_label, quote=False)}</span>
        </header>
        <div class="prl-progress" role="presentation">
            <div class="prl-progress-fill" style="width: {percent};"></div>
        </div>
        <div class="prl-meta">
            <span class="prl-xp">{html.escape(xp_label, quote=False)}</span>
        </div>
        <p class="prl-phrase">{phrase}</p>
    </section>
    """


def _profile_bg_image_name():
    """The bar background for the current theme (see config.themed_asset)."""
    from . import config as _config

    try:
        is_dark = bool(_config.effective_night_mode())
    except Exception:
        is_dark = False
    return _config.themed_asset(
        mw.col.conf.get,
        "modern_menu_profile_bg_image",
        is_dark,
        dynamic_key="modern_menu_profile_bg_dynamic_mode",
    )


def _profile_background_render_parts(addon_package, include_default_image=True):
    container_style = ""
    layer_style = ""
    bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "image")
    dyn_bg = bool(mw.col.conf.get("modern_menu_profile_bg_dynamic_mode", True))
    is_dark = config.effective_night_mode()
    theme_key = "dark" if (is_dark and dyn_bg) else "light"
    bg_color = mw.col.conf.get(f"modern_menu_profile_bg_color_{theme_key}", "#3C3C3C" if is_dark else "#EEEEEE") or ("#3C3C3C" if is_dark else "#EEEEEE")

    if bg_mode == "image":
        bg_image_file = _profile_bg_image_name()
        if bg_image_file and os.path.exists(os.path.join(mw.addonManager.addonsFolder(addon_package), "user_files", "profile_bg", bg_image_file)):
            bg_url = f"/_addons/{addon_package}/user_files/profile_bg/{bg_image_file}"
        elif include_default_image:
            # Use default background image when none is selected or file doesn't exist
            bg_url = f"/_addons/{addon_package}/system_files/profile_default/onigiri-bg.png"
        else:
            bg_url = ""
        container_style = f"background-color: {bg_color} !important; --profile-image-overlay-bg: transparent;"
        if bg_url:
            blur = max(0, min(100, int(mw.col.conf.get("modern_menu_profile_bg_blur", 0) or 0)))
            opacity_value = mw.col.conf.get("modern_menu_profile_bg_opacity", 50)
            opacity = max(0, min(100, int(100 if opacity_value is None else opacity_value))) / 100.0
            blur_px = blur * 0.2
            scale = 1.0 + (blur_px / 50.0) if blur_px > 0 else 1.0
            layer_style = (
                f"background-image: url('{bg_url}'); background-size: cover; background-position: center; "
                f"filter: blur({blur_px}px); opacity: {opacity}; transform: scale({scale});"
            )
    elif bg_mode == "custom":
        container_style = f"background-color: {bg_color} !important;"
    else: # accent
        container_style = "background-color: var(--accent-color) !important;"
    return container_style, layer_style


def on_webview_js_message(handled, message, context):
    """
    Unified handler for messages from all webviews.
    """
    if message.startswith("openHashiNotes"):
        from . import hashi_notes

        parts = message.split(":", 1)
        hn_context = parts[1] if len(parts) > 1 and parts[1] else "reviewer"
        hashi_notes.open_hashi_note_popup(hn_context, mw)
        return (True, None)

    if message == "togglePomodoro":
        from . import pomodoro

        pomodoro.toggle_widget(mw)
        return (True, None)

    if isinstance(context, Reviewer):
        focus_dango = _focus_dango()
        if focus_dango.is_focus_dango_enabled():
            exit_commands = ["decks", "add", "browse", "stats", "sync"]
            if message in exit_commands:
                if focus_dango.intercept_exit_attempt(message):
                    focus_dango.show_dango_dialog(message)
                    return (True, None)
    if message in ("restaurant_level", "openRestaurantLevel"):
        open_nook_level_dialog()
        return (True, None)
    if isinstance(context, DeckBrowser):
        cmd = message
        
        # Let webview_handlers handle the command
        # if cmd.startswith("onigiri_"):
        #    return webview_handlers.handle_webview_cmd((False, None), cmd, context)
        
        if cmd == "openTaiyakiStore":
            open_mr_taiyaki_store_dialog()
            return (True, None)
        if cmd == "openRestaurantLevel":
            open_nook_level_dialog()
            return (True, None)
        if cmd == "openOnigimonCare":
            open_onigimon_care_dialog()
            return (True, None)
        if cmd == "openHexagonLand":
            hexagon_land = _hexagon_land()
            hexagon_land.open_hexagon_land_dialog()
            return (True, None)
        if cmd.startswith("hex_land_widget_pan:"):
            try:
                hexagon_land = _hexagon_land()
                coords = cmd.split(":", 1)[1]
                import json
                data = json.loads(unquote(coords))
                state = hexagon_land.manager.load()
                state.widget_offset_x = float(data.get("x", 0))
                state.widget_offset_y = float(data.get("y", 0))
                if "s" in data:
                    state.widget_scale = float(data.get("s", 0))
                hexagon_land.manager.save(state)
            except Exception as e:
                print(f"Error saving Hexagon Land widget pan: {e}")
            return (True, None)
        if cmd == "buyHexCoins":
            hexagon_land = _hexagon_land()
            hexagon_land.open_buy_hex_coins()
            return (True, None)
        if cmd == "redeemReward:hex":
            from .gamification.reward_redemption import open_reward_redeem_dialog

            open_reward_redeem_dialog(context="hex")
            return (True, None)
        if cmd == "showGamification":
            open_gamification_dialog()
            return (True, None)
        if cmd == "add":
            mw.onAddCard()
            return (True, None)
        if cmd == "browse":
            mw.onBrowse()
            return (True, None)
        if cmd == "stats":
            mw.onStats()
            return (True, None)
        if cmd == "sync":
            if hasattr(mw.deckBrowser, 'web') and mw.deckBrowser.web:
                mw.deckBrowser.web.eval("SyncStatusManager.setSyncing(true);")
            mw.onSync()
            return (True, None)
        if cmd == "onigiri_check_sync_status":
            sync_status = get_sync_status()
            if hasattr(mw.deckBrowser, 'web') and mw.deckBrowser.web:
                mw.deckBrowser.web.eval(f"SyncStatusManager.setSyncStatus('{sync_status}');")
            return (True, None)
        if cmd == "openOnigiriSettings":
            from . import settings_web

            settings_web.open_settings(0)
            return (True, None)
        if cmd == "openGamificationSettings":
            from . import settings_web

            settings_web.open_settings("gamification")
            return (True, None)
        if cmd == "openOnigimonSettings":
            from . import settings_web

            settings_web.open_settings("onigimon")
            return (True, None)
        if cmd == "shared":
            QDesktopServices.openUrl(QUrl("https://ankiweb.net/shared/decks"))
            return (True, None)
        if cmd == "create":
            # Fix for duplicate dialog: Use QInputDialog directly and create deck manually
            # instead of calling _on_create() which was triggering the dialog twice
            name, ok = QInputDialog.getText(mw, "Create Deck", "Name:")
            if ok and name:
                # Create the deck
                mw.col.decks.id(name)
                # Refresh the deck browser to show the new deck
                mw.deckBrowser.refresh()
            return (True, None)
        if cmd.startswith("opts:"):
            try:
                deck_id = cmd.split(":")[1]
                # Call Anki's standard deck options functionality
                mw.deckBrowser._show_options_for_deck_id(int(deck_id))
                return (True, None)
            except (ValueError, IndexError, AttributeError):
                # If deck ID is invalid or deckBrowser doesn't have the method, fall through to default handler
                pass
        if cmd.startswith("saveSidebarWidth:"):
            try:
                width = int(cmd.split(":")[1])
                mw.col.conf["modern_menu_sidebar_width"] = width
                mw.col.setMod()
            except:
                pass
            return (True, None)
        if cmd.startswith("saveSidebarSize:"):
            try:
                _, width_raw, height_raw = cmd.split(":", 2)
                width = int(float(width_raw))
                height = int(float(height_raw))
                if width > 0:
                    mw.col.conf["modern_menu_sidebar_width"] = width
                if height > 0:
                    mw.col.conf["modern_menu_sidebar_height"] = height
                mw.col.setMod()
            except:
                pass
            return (True, None)
        if cmd.startswith("saveSidebarState:"):
            try:
                is_collapsed = cmd.split(":")[1] == 'true'
                mw.col.conf["onigiri_sidebar_collapsed"] = is_collapsed
                mw.col.setMod()
            except Exception as e:
                print(f"Onigiri: Error saving sidebar state: {e}")
            return (True, None)
        # --- Focus Mode ---
        if cmd.startswith("saveDeckFocusState:"):
            try:
                is_focused = cmd.split(":")[1] == 'true'
                mw.col.conf["onigiri_deck_focus_mode"] = is_focused
                mw.col.conf["onigiri_deck_cycle_state"] = 1 if is_focused else 0
                mw.col.setMod()
            except Exception as e:
                print(f"Onigiri: Error saving deck focus state: {e}")
            return (True, None)
        if cmd.startswith("saveDeckCycleState:"):
            try:
                value = int(cmd.split(":", 1)[1])
                value = max(0, min(4, value))
                mw.col.conf["onigiri_deck_cycle_state"] = value
                mw.col.conf["onigiri_deck_focus_mode"] = value in (1, 2)
                mw.col.setMod()
            except Exception as e:
                print(f"Onigiri: Error saving deck cycle state: {e}")
            return (True, None)
        # --- Focus Mode ---

    elif isinstance(context, Overview):
        cmd = message  # <-- This line must come FIRST

        if cmd == "onigiri_browse_ready_learning":
            try:
                from aqt import dialogs

                card_ids = _ready_learning_card_ids(mw.col)
                search = (
                    "cid:" + ",".join(str(card_id) for card_id in card_ids)
                    if card_ids
                    else "cid:0"
                )
                dialogs.open("Browser", mw, search=(search,))
            except Exception:
                tooltip(
                    tr_at(
                        "could_not_open_ready_learning_cards",
                        "Could not open the ready learning cards in Browser.",
                    )
                )
            return (True, None)

        
        # Now handle the commands normally
        if cmd == "deckBrowser":
            mw.moveToState("deckBrowser")
            return (True, None)
        if cmd in ["study", "opts", "refresh", "empty", "studymore", "description"]:
            return handled
        if cmd == "decks":
            mw.moveToState("deckBrowser")
            return (True, None)
        if cmd == "add":
            mw.onAddCard()
            return (True, None)
        if cmd == "browse":
            mw.onBrowse()
            return (True, None)
        if cmd == "stats":
            mw.onStats()
            return (True, None)
        if cmd == "sync":
            mw.onSync()
            return (True, None)
        if cmd == "onigiri_check_sync_status":
            return (True, None)

    elif isinstance(context, Reviewer):
        cmd = message  # <-- This line must come FIRST
        
        # Focus Dango check for exit commands
        exit_commands = ["decks", "add", "browse", "stats", "sync"]
        if cmd in exit_commands:
            focus_dango = _focus_dango()
            if focus_dango.is_focus_dango_enabled():
                if focus_dango.intercept_exit_attempt(cmd):
                    focus_dango.show_dango_dialog(cmd)
                    return (True, None)
        
        # Now handle the commands normally
        if cmd == "decks":
            mw.moveToState("deckBrowser")
            return (True, None)
        if cmd == "add":
            mw.onAddCard()
            return (True, None)
        if cmd == "browse":
            mw.onBrowse()
            return (True, None)
        if cmd == "stats":
            mw.onStats()
            return (True, None)
        if cmd == "sync":
            mw.onSync()
            return (True, None)
        if cmd == "onigiri_check_sync_status":
            return (True, None)

    return handled


def patch_overview():
	"""Replaces the HTML generation for the overview screen."""
	
	conf = config.get_config_readonly()
	show_toolbar_replacements = conf.get("hideNativeHeaderAndBottomBar", False)
	max_hide = conf.get("maxHide", False)
	flow_mode = conf.get("flowMode", False)
    
	overview_style = mw.col.conf.get("onigiri_overview_style", "pro")
	style_class = "mini-overview" if overview_style == "mini" else ""

	mini_css = ""
	if overview_style == "mini":
		mini_css = """
        <style id="onigiri-mini-overview-style">
            /* Keep Mini below the fixed navigation while Pro stays vertically centered. */
            body.mini-overview { align-items: flex-start !important; }
            .overview-center-container.mini-overview {
                align-self: flex-start !important;
                box-sizing: border-box;
                padding-top: 58px !important;
                padding-bottom: 12px !important;
            }

            /* --- The rest of the styling for the mini-overview components --- */
            .mini-overview .overview-title {
                font-size: 20px !important;
                line-height: 1.2;
                font-weight: 600;
                margin: 0 0 6px !important;
                text-align: center;
            }
            .mini-overview .overview-profile-bar {
                width: max-content;
                max-width: min(360px, calc(100%% - 40px));
                padding: 3px;
                margin: 0 auto -14px auto;
                position: relative;
                z-index: 3;
            }
            .mini-overview .overview-profile-bar .profile-pic,
            .mini-overview .overview-profile-bar .profile-pic-placeholder {
                width: 22px;
                height: 22px;
                margin-right: 7px;
            }
            .mini-overview .overview-profile-bar .profile-name {
                font-size: 12px;
            }
            .mini-overview .overview-profile-bar .restaurant-level-chip {
                gap: 6px;
                margin-left: 8px;
                padding: 2px 7px;
            }
            .mini-overview .overview-profile-bar .restaurant-level-chip .rl-chip-level {
                font-size: 11px;
            }
            .mini-overview .overview-profile-bar .restaurant-level-chip .rl-chip-progress {
                width: 42px;
                height: 4px;
            }
            .mini-overview .overview-container {
                width: min(280px, calc(100vw - 32px)) !important;
                max-width: none !important;
                box-sizing: border-box;
                margin: 0 auto 18px !important;
            }
            .mini-overview .stats-container {
                width: 100% !important;
                box-sizing: border-box;
                margin: 0 auto 14px auto;
                background: var(--overview-box-bg, var(--canvas-inset));
                padding: 16px 12px 8px 12px !important;
                border: var(--overview-box-stroke, 1px) solid var(--overview-box-border, var(--border));
                border-radius: var(--overview-box-radius, 12px);
                backdrop-filter: blur(var(--overview-box-blur, 0px));
                -webkit-backdrop-filter: blur(var(--overview-box-blur, 0px));
            }
            .mini-overview .stats-container.no-profile {
                padding-top: 6px;
            }
            .mini-overview .stats-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0 !important; font-family: var(--font-main), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 14px !important; color: var(--fg); }
            .mini-overview .stats-row span:first-child { color: var(--fg); }
            .mini-overview .new-count-bubble, .mini-overview .learn-count-bubble, .mini-overview .review-count-bubble { font-family: inherit; font-size: inherit; font-weight: 500; padding: 3px 10px; border-radius: 12px; min-width: 30px; text-align: center; }
            .mini-overview .new-count-bubble { color: var(--overview-new-count-fg, var(--fg)) !important; }
            .mini-overview .learn-count-bubble { color: var(--overview-learn-count-fg, var(--fg)) !important; }
            .mini-overview .review-count-bubble { color: var(--overview-review-count-fg, var(--fg)) !important; }
            .mini-overview #study {
                width: 100% !important;
                box-sizing: border-box !important;
                margin: 0 auto !important;
                padding: 8px 12px !important;
                min-height: 40px;
                font-family: var(--font-main), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                font-size: 14px !important;
                color: var(--fg) !important;
                border-radius: 9999px;
                box-shadow: none !important;
            }
            .mini-overview .overview-bottom-actions { 
                width: 100%; 
                margin: 10px auto 0 auto; 
                display: flex; 
                justify-content: center; 
                gap: 8px; 
                text-align: center;
            }
            .mini-overview .overview-bottom-actions .overview-button { 
                background: var(--overview-action-button-bg, var(--onigiri-box-effect-bg, var(--canvas-inset, #f5f5f5))) !important; 
                color: var(--overview-action-button-fg, var(--onigiri-box-effect-fg, var(--fg, #333))) !important; 
                border: var(--onigiri-box-effect-stroke, 1px) solid var(--overview-action-button-border, var(--onigiri-box-effect-border, var(--border, #d9d9d9))); 
                border-radius: var(--onigiri-box-effect-radius, 8px); 
                text-decoration: none; 
                font-family: var(--font-main), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                font-size: var(--font-size-main, 13px); 
                padding: 5px 12px; 
                font-weight: 500; 
                transition: background-color 0.2s, border-color 0.2s, color 0.2s; 
                opacity: 1 !important; 
                box-shadow: none !important;
                backdrop-filter: blur(var(--onigiri-box-effect-blur, 0px));
                -webkit-backdrop-filter: blur(var(--onigiri-box-effect-blur, 0px));
            }
            .mini-overview #onigiri-reveal-btn {
                margin: 14px auto;
                padding: 8px 16px;
                font-size: 12px;
            }
            .mini-overview .overview-bottom-actions .overview-button:hover { 
                background-color: var(--overview-action-button-bg, var(--onigiri-box-effect-bg, var(--button-hover-bg, #e6e6e6))) !important; 
                border-color: var(--overview-action-button-border, var(--onigiri-box-effect-border-hover, var(--button-hover-border, #bfbfbf)));
                color: var(--overview-action-button-fg, var(--onigiri-box-effect-fg, var(--button-hover-fg, #000))) !important;
                box-shadow: none !important;
            }
            /* Dark mode overrides */
            .nightMode .mini-overview .overview-bottom-actions .overview-button {
                --button-bg: var(--window-bg, #2a2a2a);
                --button-fg: var(--fg, #e0e0e0);
                --button-border: var(--border, #3a3a3a);
                --button-hover-bg: var(--window-bg, #333333);
                --button-hover-border: var(--border, #4a4a4a);
                --button-hover-fg: var(--fg, #ffffff);
                box-shadow: none !important;
            }
        </style>
        """

	profile_bar_html = ""
	profile_type = mw.col.conf.get("modern_menu_profile_type", "bar")
	if conf.get("showOverviewProfileBar", True) and profile_type == "bar":
		user_name = conf.get("userName", "USER")
		profile_pic_html = _get_profile_pic_html(user_name, mw.addonManager.addonFromModule(__name__), "profile-pic")
		restaurant_chip_html = _get_nook_level_chip_html()
		profile_bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "image")
		bg_class_str = "with-image-bg" if profile_bg_mode == "image" else ""
		if profile_bg_mode == "image" and not _profile_bg_image_name() and mw.col.conf.get("modern_menu_profile_bg_dynamic_mode", True):
			bg_class_str += " dynamic-default-bg"
		bg_style_str, bg_layer_style = _profile_background_render_parts(mw.addonManager.addonFromModule(__name__))
		bg_layer_html = f'<div class="profile-bg-layer" style="{bg_layer_style}"></div>' if bg_layer_style else ""
		profile_bar_html = f"""
	<div class="overview-profile-bar profile-bar {bg_class_str}" style="{bg_style_str}">
		{bg_layer_html}
		{profile_pic_html}
		<span class="profile-name">{user_name}</span>
		{restaurant_chip_html}
	</div>
"""
    
	def new_table(self) -> str:
		counts = list(self.mw.col.sched.counts())
		learning_notice_html = _learning_due_later_notice(
			self.mw.col, _learning_notice_enabled(conf, "overview")
		)
		
		# The add-on language can differ from Anki's own interface language.
		# Keep these replacement labels consistent with the rest of Onigiri.
		count_data = [
			{"label": tr_at("new"), "count": counts[0], "class": "new-count-bubble"},
			{"label": tr_at("learning"), "count": counts[1], "class": "learn-count-bubble"},
			{"label": tr_at("to_review"), "count": counts[2], "class": "review-count-bubble"},
		]

		rows_html = ""
		for item in count_data:
			rows_html += (
				'<div class="stats-row">'
				f"<span>{item['label']}</span>"
				f"<span class=\"{item['class']}\">{item['count']}</span>"
				'</div>'
			)

		configured_study_now_text = mw.col.conf.get("modern_menu_studyNowText")
		# ``Study Now`` is the legacy stored default. Preserve user-written
		# overrides, but translate the default in the selected add-on language.
		study_now_text = (
			tr_at("study_now")
			if not configured_study_now_text or configured_study_now_text == "Study Now"
			else configured_study_now_text
		)
		custom_study_text = tr_at("custom") if overview_style == "mini" else tr_at("custom_study")

		bottom_actions_html = ""
		if show_toolbar_replacements:
			# Check if current deck is filtered (dynamic)
			current_deck = self.mw.col.decks.current()
			is_filtered = current_deck and current_deck.get("dyn", False)
			
			if is_filtered:
				# Filtered deck buttons: Options, Rebuild, Empty
				bottom_actions_html = (
					'<div class="overview-bottom-actions">'
					f'<a href="#" key=O onclick="pycmd(\'opts\'); return false;" class="overview-button onigiri-overview-action-options">{tr_at("options")}</a>'
					f'<a href="#" key=R onclick="pycmd(\'refresh\'); return false;" class="overview-button">{tr_at("rebuild")}</a>'
					f'<a href="#" key=E onclick="pycmd(\'empty\'); return false;" class="overview-button">{tr_at("empty")}</a>'
					'</div>'
				)
			else:
				# Non-filtered deck buttons: Options, Custom Study, Description
				bottom_actions_html = (
					'<div class="overview-bottom-actions">'
					f'<a href="#" key=O onclick="pycmd(\'opts\'); return false;" class="overview-button overview-button-normal onigiri-overview-action-options">{tr_at("options")}</a>'
					f'<a href="#" key=C onclick="pycmd(\'studymore\'); return false;" class="overview-button overview-button-normal onigiri-overview-action-custom-study">{custom_study_text}</a>'
					f'<a href="#" onclick="pycmd(\'description\'); return false;" class="overview-button overview-button-normal onigiri-overview-action-description">{tr_at("description")}</a>'
					'</div>'
				)

		stats_container_class = "stats-container" if profile_bar_html else "stats-container no-profile"
		return (
			'<div class="overview-container">'
				f'<div class="{stats_container_class}">'
					f'{rows_html}'
					f'{learning_notice_html}'
				'</div>'
				f'<button id="study" class="add-button-dashed" onclick="pycmd(\'study\'); return false;" autofocus>'
					f'{study_now_text}'
				'</button>'
				f'{bottom_actions_html}'
				f'<button id="onigiri-reveal-btn" class="onigiri-overview-action-reveal">{tr_at("click_to_reveal")}</button>'
			'</div>'
		)

	Overview._table = new_table
	
	header_html = ""
	if show_toolbar_replacements and not flow_mode:
		header_html = f"""
    <div id="onigiri-overview-header" class="overview-header">
        <div class="onigiri-reviewer-header-buttons">
            <a href="#" onclick="pycmd('decks'); return false;" class="onigiri-reviewer-button">{tr_at("decks")}</a>
            <a href="#" onclick="pycmd('add'); return false;" class="onigiri-reviewer-button">{tr_at("add")}</a>
            <a href="#" onclick="pycmd('browse'); return false;" class="onigiri-reviewer-button">{tr_at("browse")}</a>
            <a href="#" onclick="pycmd('stats'); return false;" class="onigiri-reviewer-button">{tr_at("stats")}</a>
            <a href="#" onclick="pycmd('sync'); return false;" class="onigiri-reviewer-button">{tr_at("sync")}</a>
        </div>
    </div>
"""

	reveal_label_js = json.dumps(tr_at("click_to_reveal"))
	hide_label_js = json.dumps(tr_at("click_to_hide"))

	js_code = """
	    document.addEventListener("DOMContentLoaded", function() {
	        document.body.classList.add('onigiri-overview');

	        // Onigiri Deck Title Fix
	        const titleElement = document.querySelector('.overview-title');
        if (titleElement) {
            // Anki provides the full deck path, so we split it by "::" and take the last part.
            const fullTitle = titleElement.textContent;
            const shortTitle = fullTitle.split('::').pop();
            titleElement.textContent = shortTitle;
        }
        
        if (!document.getElementById('onigiri-background-div')) {
            const bgDiv = document.createElement('div');
            bgDiv.id = 'onigiri-background-div';
            document.body.prepend(bgDiv);
        } 

        // NEW SCRIPT TO ADD CLASS TO BODY
        // This allows our CSS to target the body tag and override the alignment
        if (document.querySelector('.overview-center-container.mini-overview')) { 
            document.body.classList.add('mini-overview');
        }
        
        // Collect all external content (anything not Onigiri)
        const container = document.querySelector('.overview-center-container');
        const onigiriHeader = document.getElementById('onigiri-overview-header');
        const onigiriTitle = document.querySelector('.overview-title');
        const onigiriContainer = document.querySelector('.overview-container');
        const revealBtn = document.getElementById('onigiri-reveal-btn');
        
        // Find all direct children of the container that are NOT Onigiri content
        const allExternalElements = [];
        if (container) {
            Array.from(container.children).forEach(function(child) {
                // Skip Onigiri elements and the reveal button
                if (child !== onigiriHeader &&
                    !child.classList.contains('overview-profile-bar') &&
                    child !== onigiriTitle && 
                    child !== onigiriContainer && 
                    child !== revealBtn && 
                    child.id !== 'onigiri-overview-header' &&
                    child.id !== 'onigiri-reveal-btn' &&
                    !child.classList.contains('overview-header') &&
                    !child.classList.contains('overview-title') &&
                    !child.classList.contains('overview-container')) {
                    
                    // Check if element has any meaningful content instantly
                    const hasVisibleContent = function(el) {
                        if (el.tagName === 'BR' || el.tagName === 'HR') return true;
                        if (el.textContent.trim() !== '') return true;
                        // Avoid getComputedStyle layout thrashing, check fast markers
                        if (el.querySelector('img, iframe, canvas, svg, input, button, select, textarea')) return true;
                        return false;
                    };
                    
                    if (hasVisibleContent(child)) {
                        child.classList.add('onigiri-external-overview-addon');
                        allExternalElements.push(child);
                        child.style.display = 'none'; // Hide initially
                    }
                }
            });
        }
        if (container) {
            container.classList.remove('onigiri-mask-external');
        }
        
        // Hide reveal button if there are no external elements with content
        if (revealBtn && allExternalElements.length === 0) {
            revealBtn.style.display = 'none';
        }
        
        // Handle reveal button functionality
        if (revealBtn && allExternalElements.length > 0) {
            let isRevealed = false;
            revealBtn.addEventListener('click', function() {
                isRevealed = !isRevealed;
                
                if (isRevealed) {
                    // Show all external elements
                    allExternalElements.forEach(function(el) {
                        el.style.display = '';
                    });
	                    revealBtn.textContent = __ONIGIRI_CLICK_TO_HIDE_LABEL__;
                } else {
                    // Hide all external elements
                    allExternalElements.forEach(function(el) {
                        el.style.display = 'none';
                    });
	                    revealBtn.textContent = __ONIGIRI_CLICK_TO_REVEAL_LABEL__;
                }
            });
        }
    });
	    """
	js_code = (
		js_code
		.replace("__ONIGIRI_CLICK_TO_HIDE_LABEL__", hide_label_js)
		.replace("__ONIGIRI_CLICK_TO_REVEAL_LABEL__", reveal_label_js)
	)

	reveal_button_css = """
    <style id="onigiri-reveal-button-style">
        #onigiri-reveal-btn {
            display: block;
            margin: 20px auto;
            padding: 10px 20px;
            background: var(--overview-reveal-button-bg, var(--button-primary-bg));
            color: var(--overview-reveal-button-fg, white) !important;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s ease;
        }
        #onigiri-reveal-btn:hover {
            transform: scale(1.05);
        }
        .night-mode #onigiri-reveal-btn {
            color: white !important;
        }
        .descfont.descmid.description.dyn {
            display: none !important;
        }
        .overview-center-container.onigiri-mask-external > *:not(#onigiri-overview-header):not(.overview-profile-bar):not(.overview-title):not(.overview-container):not(#onigiri-reveal-btn):not(style):not(script) {
            opacity: 0 !important;
            pointer-events: none !important;
        }
    </style>
    """
	late_background_css = generate_overview_background_css(os.path.dirname(__file__))

	Overview._body = _escape_overview_body_percent_literals(f"""
{mini_css}
{reveal_button_css}
<div class="overview-center-container {style_class} onigiri-mask-external">
	{header_html}
	<h3 class="overview-title">%(deck)s</h3>
	{profile_bar_html}
	%(table)s
	<div>%(shareLink)s</div>
	<div>%(desc)s</div>
</div>
<script>{js_code}</script>
{late_background_css}
""")
    

# --- Congrats Page Patcher ---

def patch_congrats_page():
    """Replaces the default congratulations screen with a custom, stylable one."""
    
    def new_show_finished_screen(self: Overview, _old):
        addon_path = os.path.dirname(__file__)
        conf = config.get_config_readonly()
        addon_package = mw.addonManager.addonFromModule(__name__)

        # Check for hide mode to determine if the header should be shown
        show_toolbar_replacements = conf.get("hideNativeHeaderAndBottomBar", False)
        max_hide = conf.get("maxHide", False)
        flow_mode = conf.get("flowMode", False)

        header_html = ""
        if show_toolbar_replacements and not flow_mode:
            header_html = f"""
            <div class="overview-header">
                <div class="onigiri-reviewer-header-buttons">
                    <a href="#" onclick="pycmd('decks'); return false;" class="onigiri-reviewer-button">{tr_at("decks")}</a>
                    <a href="#" onclick="pycmd('add'); return false;" class="onigiri-reviewer-button">{tr_at("add")}</a>
                    <a href="#" onclick="pycmd('browse'); return false;" class="onigiri-reviewer-button">{tr_at("browse")}</a>
                    <a href="#" onclick="pycmd('stats'); return false;" class="onigiri-reviewer-button">{tr_at("stats")}</a>
                    <a href="#" onclick="pycmd('sync'); return false;" class="onigiri-reviewer-button">{tr_at("sync")}</a>
                </div>
            </div>
            """

        # 1. Build Profile Bar HTML (if enabled)
        profile_bar_html = ""
        profile_type = mw.col.conf.get("modern_menu_profile_type", "bar")
        if conf.get("showCongratsProfileBar", True) and profile_type == "bar":
            user_name = conf.get("userName", "USER")
            profile_pic_html = _get_profile_pic_html(user_name, addon_package, "profile-pic")
            restaurant_chip_html = _get_nook_level_chip_html()

            profile_bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "image")
            bg_class_str = ""
            bg_style_str, bg_layer_style = _profile_background_render_parts(addon_package)
            bg_layer_html = f'<div class="profile-bg-layer" style="{bg_layer_style}"></div>' if bg_layer_style else ""
            if profile_bg_mode == "image":
                bg_class_str = "with-image-bg"
                if not _profile_bg_image_name() and mw.col.conf.get("modern_menu_profile_bg_dynamic_mode", True):
                    bg_class_str += " dynamic-default-bg"

            profile_bar_html = f"""
                <div class="overview-profile-bar profile-bar {bg_class_str}" style="{bg_style_str}">
                    {bg_layer_html}
                    {profile_pic_html}
                    <span class="profile-name">{user_name}</span>
                    {restaurant_chip_html}
                </div>
                """

        # 2. Get Custom Message with fallback to default
        message = conf.get("congratsMessage", DEFAULTS["congratsMessage"])
        
        learning_notice_html = _learning_due_later_notice(
            self.mw.col, _learning_notice_enabled(conf, "congrats")
        )

        # 3. Build Bottom Actions HTML
        bottom_actions_html = ""
        if show_toolbar_replacements:
            current_deck = self.mw.col.decks.current()
            is_filtered = current_deck and current_deck.get("dyn", False)
            
            if is_filtered:
                # Filtered deck buttons: Options, Rebuild, Empty
                bottom_actions_html = f"""
                <div class="congrats-bottom-actions">
                    <a href="#" key=O onclick="pycmd('opts'); return false;" class="overview-button onigiri-overview-action-options">{tr_at("options")}</a>
                    <a href="#" key=R onclick="pycmd('refresh'); return false;" class="overview-button">{tr_at("rebuild")}</a>
                    <a href="#" key=E onclick="pycmd('empty'); return false;" class="overview-button">{tr_at("empty")}</a>
                </div>
                """
            else:
                # Non-filtered deck buttons: Options, Custom Study, Description
                bottom_actions_html = f"""
                <div class="congrats-bottom-actions">
                    <a href="#" key=O onclick="pycmd('opts'); return false;" class="overview-button onigiri-overview-action-options">{tr_at("options")}</a>
                    <a href="#" key=C onclick="pycmd('studymore'); return false;" class="overview-button onigiri-overview-action-custom-study">{tr_at("custom_study")}</a>
                    <a href="#" onclick="pycmd('description'); return false;" class="overview-button onigiri-overview-action-description">{tr_at("description")}</a>
                </div>
                """

        # 4. Construct Final HTML Body
        # Note: the nav header is kept OUTSIDE .congrats-container so it is a direct
        # child of <body>. The container is a narrow, vertically-centered box, and
        # nesting the header inside it caused `position: fixed` to be measured against
        # the container (dropping the buttons on top of the profile bar) instead of
        # the viewport. As a body-level sibling it pins cleanly to the top-center.
        congrats_card_class = "congrats-card" if profile_bar_html else "congrats-card no-profile"
        body_html = f"""
        {header_html}
        <div class="congrats-container">
            {profile_bar_html}
            <div class="{congrats_card_class}">
                <h1>{message}</h1>
                {learning_notice_html}
            </div>
            {bottom_actions_html}
        </div>
        """
        
        # 5. Generate Head Content (CSS)
        head_html = generate_dynamic_css(conf)
        head_html += generate_overview_background_css(addon_path)
        
        # 6. Render the page
        self.web.stdHtml(
            body_html,
            css=[f"/_addons/{addon_package}/web/congrats.css"],
            js=[], # JS messages are handled by the hook, no need to inject a file
            head=head_html,
            context=self,
        )
        # Manually run JS to create the background div after the page is loaded.
        self.web.eval("""
            if (!document.getElementById('onigiri-background-div')) {
                const bgDiv = document.createElement('div');
                bgDiv.id = 'onigiri-background-div';
                document.body.prepend(bgDiv);
            }
        """)

    # patch_overview() re-runs on every settings save, so the wrapper must not
    # stack: each extra layer is one more nested call on the congrats screen.
    if not getattr(Overview._show_finished_screen, "_onigiri_wrapped", False):
        Overview._show_finished_screen = wrap(
            Overview._show_finished_screen, new_show_finished_screen, "around"
        )
        Overview._show_finished_screen._onigiri_wrapped = True


def generate_deck_browser_backgrounds(addon_path):
    """Generates CSS for the main container background and sidebar."""
    conf = config.get_config_readonly()
    
    main_mode = mw.col.conf.get("modern_menu_background_mode", "color")
    main_image_mode = mw.col.conf.get("modern_menu_background_image_mode", "single")
    main_light_color = mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
    main_dark_color = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
    main_blur = mw.col.conf.get("modern_menu_background_blur", 0)
    main_opacity = mw.col.conf.get("modern_menu_background_opacity", 100)

    # Handle slideshow mode
    if main_mode == "slideshow":
        slideshow_images = config.get_collection_config("modern_menu_slideshow_images", [])
        slideshow_interval = mw.col.conf.get("modern_menu_slideshow_interval", 10)
        
        if slideshow_images:
            addon_name = os.path.basename(addon_path)
            image_urls = [f"/_addons/{addon_name}/user_files/main_bg/{img}" for img in slideshow_images]
            
            blur_px = main_blur * 0.2
            scale = 1.0 + (blur_px / 50.0) if blur_px > 0 else 1.0
            opacity_float = main_opacity / 100.0
            
            # Generate CSS for slideshow with smooth crossfade effect
            first_image_url = image_urls[0]
            main_container_css = f"""
            <style id='modern-menu-main-background-style'>
                .container.modern-main-menu {{
                    position: relative;
                    z-index: 1;
                    overflow: hidden;
                    background-color: {main_light_color} !important;
                }}
                .night-mode .container.modern-main-menu {{
                    background-color: {main_dark_color} !important;
                }}
                /* Base layer - always visible */
                .container.modern-main-menu::before {{
                    content: '';
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    width: 100%;
                    height: 100%;
                    transform: translate(-50%, -50%) scale({scale});
                    background-image: url('{first_image_url}');
                    background-size: cover;
                    background-position: center;
                    background-repeat: no-repeat;
                    filter: blur({blur_px}px);
                    opacity: {opacity_float};
                    z-index: 0;
                }}
                /* Transition layer - fades in/out */
                .container.modern-main-menu::after {{
                    content: '';
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    width: 100%;
                    height: 100%;
                    transform: translate(-50%, -50%) scale({scale});
                    background-size: cover;
                    background-position: center;
                    background-repeat: no-repeat;
                    filter: blur({blur_px}px);
                    opacity: 0;
                    z-index: 1;
                    transition: opacity 1.2s cubic-bezier(0.4, 0, 0.2, 1);
                }}
                .container.modern-main-menu.slideshow-transitioning::after {{
                    opacity: {opacity_float};
                }}
                .container.modern-main-menu > * {{
                    position: relative;
                    z-index: 2;
                }}
            </style>
            <script>
                (function() {{
                    const images = {json.dumps(image_urls)};
                    const interval = {slideshow_interval * 1000};
                    let currentIndex = 0;
                    let nextIndex = 1;
                    
                    function updateBackground() {{
                        const container = document.querySelector('.container.modern-main-menu');
                        if (!container) return;
                        
                        // Set the next image on the ::after layer
                        let afterStyleTag = document.getElementById('slideshow-after-image');
                        if (!afterStyleTag) {{
                            afterStyleTag = document.createElement('style');
                            afterStyleTag.id = 'slideshow-after-image';
                            document.head.appendChild(afterStyleTag);
                        }}
                        afterStyleTag.textContent = `.container.modern-main-menu::after {{ background-image: url('${{images[nextIndex]}}'); }}`;
                        
                        // Trigger the fade-in transition
                        setTimeout(() => {{
                            container.classList.add('slideshow-transitioning');
                        }}, 50);
                        
                        // After transition completes, swap layers
                        setTimeout(() => {{
                            // Update the ::before layer with the new image
                            let beforeStyleTag = document.getElementById('slideshow-before-image');
                            if (!beforeStyleTag) {{
                                beforeStyleTag = document.createElement('style');
                                beforeStyleTag.id = 'slideshow-before-image';
                                document.head.appendChild(beforeStyleTag);
                            }}
                            beforeStyleTag.textContent = `.container.modern-main-menu::before {{ background-image: url('${{images[nextIndex]}}'); }}`;
                            
                            // Reset the transition
                            container.classList.remove('slideshow-transitioning');
                            
                            // Update indices
                            currentIndex = nextIndex;
                            nextIndex = (nextIndex + 1) % images.length;
                        }}, 1250); // Slightly longer than transition duration
                    }}
                    
                    // Start slideshow only if there are multiple images
                    if (images.length > 1) {{
                        setInterval(updateBackground, interval);
                    }}
                }})();
            </script>
            """
            main_container_css += "<style>.main-content { background: transparent !important; }</style>"
        else:
            # No images selected, fallback to color mode
            main_container_css = f"""
            <style id='modern-menu-main-background-style'>
                .container.modern-main-menu {{ background-color: {main_light_color} !important; }}
                .night-mode .container.modern-main-menu {{ background-color: {main_dark_color} !important; }}
            </style>
            """
            main_container_css += "<style>.main-content { background: transparent !important; }</style>"
    else:
        # Original image mode handling
        if main_image_mode == "separate":
            main_light_img_filename = mw.col.conf.get("modern_menu_background_image_light", "")
            main_dark_img_filename = mw.col.conf.get("modern_menu_background_image_dark", "")
        else:
            main_light_img_filename = mw.col.conf.get("modern_menu_background_image", "")
            main_dark_img_filename = main_light_img_filename

        main_light_img = f"user_files/main_bg/{main_light_img_filename}" if main_light_img_filename else ""
        main_dark_img = f"user_files/main_bg/{main_dark_img_filename}" if main_dark_img_filename else ""
    
        main_container_css = _render_background_css(
            ".container.modern-main-menu", main_mode, main_light_color, main_dark_color, 
            main_light_img, main_dark_img, main_blur, addon_path, "modern-menu-main-background-style", main_opacity
        )
        main_container_css += "<style>.main-content { background: transparent !important; }</style>"

    sidebar_mode = mw.col.conf.get("modern_menu_sidebar_bg_mode", "main")
    sidebar_css = ""
    if sidebar_mode == 'custom':
        side_mode = mw.col.conf.get("modern_menu_sidebar_bg_type", "color")
        side_light_color = mw.col.conf.get("modern_menu_sidebar_bg_color_light", "#F3F3F3")
        side_dark_color = mw.col.conf.get("modern_menu_sidebar_bg_color_dark", "#2C2C2C")
        try:
            side_blur = float(mw.col.conf.get("modern_menu_sidebar_bg_blur", 0) or 0)
        except (TypeError, ValueError):
            side_blur = 0.0
        side_image_mode = mw.col.conf.get("modern_menu_sidebar_bg_image_theme_mode", "separate")
        side_opacity = mw.col.conf.get("modern_menu_sidebar_bg_opacity", 100)
        try:
            side_opacity_percent = max(0.0, min(100.0, float(side_opacity)))
        except (TypeError, ValueError):
            side_opacity_percent = 100.0
        side_opacity_alpha = side_opacity_percent / 100.0
        addon_name = os.path.basename(addon_path)

        if mw.col.conf.get("modern_menu_sidebar_sync_box_effect", True):
            box_colors = conf.get("colors", {})
            side_light_color = box_colors.get("light", {}).get("--canvas-inset", side_light_color)
            side_dark_color = box_colors.get("dark", {}).get("--canvas-inset", side_dark_color)

            box_blur, box_opacity, _, _ = _box_effect_values()
            try:
                side_blur = float(box_blur)
            except (TypeError, ValueError):
                pass
            try:
                side_opacity_percent = float(box_opacity)
            except (TypeError, ValueError):
                pass

            side_opacity_alpha = side_opacity_percent / 100.0
            if side_blur > 0:
                side_opacity_alpha = min(side_opacity_alpha, 0.62)

            if side_mode not in ("color", "accent"):
                side_mode = "color"

        if side_mode == "color" or side_mode == "accent":
            alpha = side_opacity_alpha
            backdrop_blur_px = side_blur * 0.2
            
            if side_mode == "accent":
                 sidebar_css = f"""<style id='modern-menu-sidebar-background-style'>
                    .sidebar-left {{
                        position: relative;
                        background: transparent !important;
                        isolation: isolate;
                        backdrop-filter: blur({backdrop_blur_px}px);
                        -webkit-backdrop-filter: blur({backdrop_blur_px}px);
                    }}
                    .sidebar-left::before {{
                        content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 100%;
                        background: var(--accent-color);
                        opacity: {alpha};
                        z-index: 0;
                    }}
                    .sidebar-left > * {{
                        position: relative;
                        z-index: 1;
                    }}
                </style>"""
            else: # solid color
                light_rgba = _hex_to_rgba(side_light_color, alpha)
                dark_rgba = _hex_to_rgba(side_dark_color, alpha)
                sidebar_css = f"""<style id='modern-menu-sidebar-background-style'>
                    .sidebar-left {{
                        background-color: {light_rgba} !important;
                        backdrop-filter: blur({backdrop_blur_px}px);
                        -webkit-backdrop-filter: blur({backdrop_blur_px}px);
                    }}
                    .night-mode .sidebar-left {{ background-color: {dark_rgba} !important; }}
                </style>"""

        elif side_mode == "image_color":
            if side_image_mode == "separate":
                side_light_img_filename = mw.col.conf.get("modern_menu_sidebar_bg_image_light", "")
                side_dark_img_filename = mw.col.conf.get("modern_menu_sidebar_bg_image_dark", "")
            else:
                side_light_img_filename = mw.col.conf.get("modern_menu_sidebar_bg_image", "")
                side_dark_img_filename = side_light_img_filename

            side_light_img = f"user_files/sidebar_bg/{side_light_img_filename}" if side_light_img_filename else ""
            side_dark_img = f"user_files/sidebar_bg/{side_dark_img_filename}" if side_dark_img_filename else ""
            side_light_color_render = _hex_to_rgba(side_light_color, side_opacity_alpha)
            side_dark_color_render = _hex_to_rgba(side_dark_color, side_opacity_alpha)
            sidebar_css = _render_background_css(
                ".sidebar-left", "image_color", side_light_color_render, side_dark_color_render,
                side_light_img, side_dark_img, side_blur, addon_path,
                "modern-menu-sidebar-background-style", side_opacity_percent
            )
            sidebar_css += f"""<style>
                .sidebar-left {{
                    backdrop-filter: blur({side_blur * 0.2}px);
                    -webkit-backdrop-filter: blur({side_blur * 0.2}px);
                }}
            </style>"""

        elif side_mode == "slideshow":
            slideshow_images = mw.col.conf.get("modern_menu_sidebar_slideshow_images", [])
            slideshow_interval = mw.col.conf.get("modern_menu_sidebar_slideshow_interval", 10)
            if slideshow_images:
                image_urls = [f"/_addons/{addon_name}/user_files/sidebar_bg/{img}" for img in slideshow_images]
                blur_px = side_blur * 0.2
                scale = 1.0 + (blur_px / 50.0) if blur_px > 0 else 1.0
                opacity_float = side_opacity_alpha
                first_image_url = image_urls[0]
                sidebar_css = f"""
                <style id='modern-menu-sidebar-background-style'>
                    .sidebar-left {{
                        position: relative;
                        z-index: 1;
                        overflow: hidden;
                        background-color: {_hex_to_rgba(side_light_color, side_opacity_alpha)} !important;
                        backdrop-filter: blur({blur_px}px);
                        -webkit-backdrop-filter: blur({blur_px}px);
                    }}
                    .night-mode .sidebar-left {{
                        background-color: {_hex_to_rgba(side_dark_color, side_opacity_alpha)} !important;
                    }}
                    .sidebar-left::before {{
                        content: '';
                        position: absolute;
                        top: 50%;
                        left: 50%;
                        width: 100%;
                        height: 100%;
                        transform: translate(-50%, -50%) scale({scale});
                        background-image: url('{first_image_url}');
                        background-size: cover;
                        background-position: center;
                        background-repeat: no-repeat;
                        filter: blur({blur_px}px);
                        opacity: {opacity_float};
                        z-index: 0;
                    }}
                    .sidebar-left::after {{
                        content: '';
                        position: absolute;
                        top: 50%;
                        left: 50%;
                        width: 100%;
                        height: 100%;
                        transform: translate(-50%, -50%) scale({scale});
                        background-size: cover;
                        background-position: center;
                        background-repeat: no-repeat;
                        filter: blur({blur_px}px);
                        opacity: 0;
                        z-index: 1;
                        transition: opacity 1.2s cubic-bezier(0.4, 0, 0.2, 1);
                    }}
                    .sidebar-left.sidebar-slideshow-transitioning::after {{
                        opacity: {opacity_float};
                    }}
                    .sidebar-left > * {{
                        position: relative;
                        z-index: 2;
                    }}
                </style>
                <script>
                    (function() {{
                        const images = {json.dumps(image_urls)};
                        const interval = {slideshow_interval * 1000};
                        let nextIndex = 1;

                        function updateSidebarBackground() {{
                            const sidebar = document.querySelector('.sidebar-left');
                            if (!sidebar) return;

                            let afterStyleTag = document.getElementById('sidebar-slideshow-after-image');
                            if (!afterStyleTag) {{
                                afterStyleTag = document.createElement('style');
                                afterStyleTag.id = 'sidebar-slideshow-after-image';
                                document.head.appendChild(afterStyleTag);
                            }}
                            afterStyleTag.textContent = `.sidebar-left::after {{ background-image: url('${{images[nextIndex]}}'); }}`;

                            setTimeout(() => {{
                                sidebar.classList.add('sidebar-slideshow-transitioning');
                            }}, 50);

                            setTimeout(() => {{
                                let beforeStyleTag = document.getElementById('sidebar-slideshow-before-image');
                                if (!beforeStyleTag) {{
                                    beforeStyleTag = document.createElement('style');
                                    beforeStyleTag.id = 'sidebar-slideshow-before-image';
                                    document.head.appendChild(beforeStyleTag);
                                }}
                                beforeStyleTag.textContent = `.sidebar-left::before {{ background-image: url('${{images[nextIndex]}}'); }}`;
                                sidebar.classList.remove('sidebar-slideshow-transitioning');
                                nextIndex = (nextIndex + 1) % images.length;
                            }}, 1250);
                        }}

                        if (images.length > 1) {{
                            setInterval(updateSidebarBackground, interval);
                        }}
                    }})();
                </script>
                """
            else:
                sidebar_css = f"""<style id='modern-menu-sidebar-background-style'>
                    .sidebar-left {{ background-color: {_hex_to_rgba(side_light_color, side_opacity_alpha)} !important; }}
                    .night-mode .sidebar-left {{ background-color: {_hex_to_rgba(side_dark_color, side_opacity_alpha)} !important; }}
                </style>"""
    else: # sidebar_mode == 'main'
        effect_mode = mw.col.conf.get("onigiri_sidebar_main_bg_effect_mode", "opaque")

        if effect_mode == "glassmorphism":
            intensity = mw.col.conf.get("onigiri_sidebar_main_bg_effect_intensity", 50)
            blur_px = (intensity / 100.0) * 15.0
            alpha = (intensity / 100.0) * 0.3
            main_tint = ("#FFFFFF", "#000000", alpha)

            sidebar_css = f"""
            <style id='modern-menu-sidebar-background-style'>
                .sidebar-left {{
                    background-color: rgba(255, 255, 255, {alpha}) !important;
                    backdrop-filter: blur({blur_px}px);
                    -webkit-backdrop-filter: blur({blur_px}px);
                }}
                .night-mode .sidebar-left {{
                    background-color: rgba(0, 0, 0, {alpha}) !important;
                }}
            </style>
            """
        else: # opaque color overlay
            intensity = mw.col.conf.get("onigiri_sidebar_opaque_tint_intensity", 30)
            alpha = intensity / 100.0
            
            light_color_hex = mw.col.conf.get("onigiri_sidebar_opaque_tint_color_light", "#FFFFFF")
            dark_color_hex = mw.col.conf.get("onigiri_sidebar_opaque_tint_color_dark", "#1D1D1D")
            main_tint = (light_color_hex, dark_color_hex, alpha)

            light_rgba = _hex_to_rgba(light_color_hex, alpha)
            dark_rgba = _hex_to_rgba(dark_color_hex, alpha)

            sidebar_css = f"""
            <style id='modern-menu-sidebar-background-style'>
                .sidebar-left {{
                    background-color: {light_rgba} !important;
                }}
                .night-mode .sidebar-left {{
                    background-color: {dark_rgba} !important;
                }}
            </style>
            """
        
    if sidebar_mode == 'custom' and side_mode == 'accent':
        ring_light_color = ring_dark_color = "var(--accent-color)"
        menu_light_color, menu_dark_color = ring_light_color, ring_dark_color
    elif sidebar_mode == 'custom':
        ring_light_color, ring_dark_color = side_light_color, side_dark_color
        menu_light_color, menu_dark_color = ring_light_color, ring_dark_color
    else:
        ring_light_color, ring_dark_color = main_light_color, main_dark_color
        # In 'main' mode the sidebar is the main background seen through a tint
        # layer, so flatten the two into the single colour that ends up on screen.
        tint_light, tint_dark, tint_alpha = main_tint
        menu_light_color = _mix_colors(tint_light, main_light_color, tint_alpha)
        menu_dark_color = _mix_colors(tint_dark, main_dark_color, tint_alpha)

    ring_color_css = f"""
    <style id='modern-menu-sidebar-ring-style'>
        :root {{ --onigiri-profile-ring-color: {ring_light_color}; }}
        .night-mode {{ --onigiri-profile-ring-color: {ring_dark_color}; }}
    </style>
    """

    # The quick menus pop up over the sidebar, so they follow its chosen colour.
    # Opacity/blur are deliberately not carried over: a popup has to stay readable
    # against whatever it covers.
    quick_menu_css = f"""
    <style id='modern-menu-quick-menu-style'>
        :root {{ --onigiri-quick-menu-bg: {menu_light_color}; }}
        .night-mode {{ --onigiri-quick-menu-bg: {menu_dark_color}; }}
    </style>
    """

    def _sidebar_int_setting(key, default):
        try:
            return max(0, int(float(mw.col.conf.get(key, default))))
        except (TypeError, ValueError):
            return default

    sidebar_radius = _sidebar_int_setting("modern_menu_sidebar_radius", 15)
    sidebar_stroke = _sidebar_int_setting("modern_menu_sidebar_stroke", 1)
    sidebar_margin = _sidebar_int_setting("modern_menu_sidebar_margin", 10)
    if mw.col.conf.get("modern_menu_sidebar_sync_box_effect", True):
        sidebar_radius = _sidebar_int_setting("onigiri_canvas_inset_border_radius", sidebar_radius)
        sidebar_stroke = _sidebar_int_setting("onigiri_canvas_inset_border_width", sidebar_stroke)
    sidebar_frame_css = f"""
    <style id='modern-menu-sidebar-frame-style'>
        .sidebar-left {{
            border-radius: {sidebar_radius}px !important;
            border: {sidebar_stroke}px solid var(--border) !important;
            margin: {sidebar_margin}px !important;
        }}
        .container.modern-main-menu.onigiri-cycle-stacked .sidebar-left,
        .container.modern-main-menu.onigiri-sidebar-center .sidebar-left {{
            margin: {sidebar_margin}px auto !important;
        }}
        .sidebar-left::before,
        .sidebar-left::after {{
            border-radius: inherit;
        }}
    </style>
    """

    return main_container_css + sidebar_css + sidebar_frame_css + ring_color_css + quick_menu_css


def _resolve_night_mode():
    """Best-effort current night-mode state for the main window."""
    try:
        from aqt.theme import theme_manager

        return bool(theme_manager.night_mode)
    except Exception:
        # Kept only for compatibility with Anki versions predating
        # ``theme_manager.night_mode``.
        try:
            return config.effective_night_mode()
        except Exception:
            return False


def _reviewer_base_bg_color(conf):
    """The solid color painted behind the reviewer body, for the current theme.

    Mirrors the ``body`` background-color chosen in
    ``generate_reviewer_background_css`` so the Qt-level webview base color can
    match it exactly.
    """
    night = _resolve_night_mode()
    mode = conf.get("onigiri_reviewer_bg_mode", "main")
    if mode == "main":
        if night:
            return mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
        return mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
    # "color", "image_color" and "slideshow" all paint the body with these keys.
    if night:
        return conf.get("onigiri_reviewer_bg_dark_color", "#2C2C2C")
    return conf.get("onigiri_reviewer_bg_light_color", "#FFFFFF")


def _overview_base_bg_color(conf):
    """The solid color painted behind the overview body, for the current theme."""
    night = _resolve_night_mode()
    mode = conf.get("onigiri_overview_bg_mode", "main")
    if mode == "main":
        if night:
            return mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
        return mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
    if night:
        return conf.get("onigiri_overview_bg_dark_color", "#2C2C2C")
    return conf.get("onigiri_overview_bg_light_color", "#FFFFFF")


def _deckbrowser_base_bg_color():
    """The solid color painted behind the deck browser, for the current theme."""
    if _resolve_night_mode():
        return mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
    return mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")


def set_main_webview_background_color(color):
    """Paint the shared main webview's Qt base color to ``color``.

    Anki reuses a single ``QWebEngineView`` (``mw.web``) for the deck browser,
    overview and reviewer. Until the page's HTML ``body`` paints, the view shows
    the page's *base* color, which defaults to a solid black. That produces the
    black flash the user sees when the reviewer first opens, and again on the
    repaint after grading a card. Setting the base color to match the screen's
    background makes any such gap invisible. The value persists on the page, so
    it also covers card transitions that don't re-fire ``webview_will_set_content``.
    """
    try:
        from aqt.qt import QColor
        qcolor = QColor(color) if color else QColor()
        if not qcolor.isValid():
            # A blank/invalid stored color must not become an invalid QColor,
            # which Qt paints as black - the very flash we are trying to avoid.
            qcolor = QColor("#2C2C2C") if _resolve_night_mode() else QColor("#F5F5F5")
        web = getattr(mw, "web", None)
        page = web.page() if web is not None else None
        if page is not None:
            page.setBackgroundColor(qcolor)
    except Exception as e:
        print(f"Onigiri: could not set main webview background color: {e}")


def generate_reviewer_background_css(addon_path):
    """Generates CSS for the reviewer - exact copy of overview implementation with reviewer config keys."""
    conf = config.get_config_readonly()
    reviewer_mode = conf.get("onigiri_reviewer_bg_mode", "main")
    addon_name = os.path.basename(addon_path)
    
    # Show scrollbar with transparent background when needed
    scrollbar_css = """
        /* Styled scrollbar with transparent background */
        ::-webkit-scrollbar {
            width: 10px;
        }

        ::-webkit-scrollbar-track {
            background: transparent;
        }

        ::-webkit-scrollbar-thumb {
            background: rgba(128, 128, 128, 0.5);
            border-radius: 5px;
        }

        ::-webkit-scrollbar-thumb:hover {
            background: rgba(128, 128, 128, 0.7);
        }

        html {
            overflow-y: auto !important;
            scrollbar-width: thin;  /* Firefox */
            scrollbar-color: rgba(128, 128, 128, 0.5) transparent;  /* Firefox */
        }
        
        body {
            overflow-y: visible !important;
        }
    """
    reviewer_extra_css = f"""
        #_flag {{
            font-family: revert !important;
        }}
        #_flag, #_flag * {{
            background-attachment: initial !important;
            background-blend-mode: initial !important;
            background-clip: initial !important;
            background-origin: initial !important;
        }}
        {scrollbar_css}
    """
    
    if reviewer_mode == "slideshow":
        light_color = conf.get("onigiri_reviewer_bg_light_color", "#FFFFFF")
        dark_color = conf.get("onigiri_reviewer_bg_dark_color", "#2C2C2C")
        blur_val = conf.get("onigiri_reviewer_bg_blur", 0)
        opacity_val = conf.get("onigiri_reviewer_bg_opacity", 100)
        images = conf.get("onigiri_reviewer_slideshow_images", []) or []
        image_urls = [f"/_addons/{addon_name}/user_files/reviewer_bg/{img}" for img in images]
        return _render_body_slideshow_background_css(
            "onigiri-reviewer-background-style",
            image_urls,
            conf.get("onigiri_reviewer_slideshow_interval", 10),
            light_color,
            dark_color,
            blur_val,
            opacity_val,
            reviewer_extra_css,
        )
    
    if reviewer_mode == "main":
        # Use main background settings (like overview does)
        mode = mw.col.conf.get("modern_menu_background_mode", "color")
        light_color = mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
        dark_color = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
        blur_val = conf.get("onigiri_reviewer_bg_main_blur", 0)
        opacity_val = conf.get("onigiri_reviewer_bg_main_opacity", 100)
        
        if mode == "slideshow":
            images = config.get_collection_config("modern_menu_slideshow_images", []) or []
            image_urls = [f"/_addons/{addon_name}/user_files/main_bg/{img}" for img in images]
            return _render_body_slideshow_background_css(
                "onigiri-reviewer-background-style",
                image_urls,
                mw.col.conf.get("modern_menu_slideshow_interval", 10),
                light_color,
                dark_color,
                blur_val,
                opacity_val,
                reviewer_extra_css,
            )

        if mode not in ["image", "image_color"]:
            return f"""<style id="onigiri-reviewer-background-style">
                body {{ background-color: {light_color} !important; }}
                .night-mode body {{ background-color: {dark_color} !important; }}
            
                #_flag {{
                    font-family: revert !important;
                }}

                #_flag, #_flag * {{
                    background-attachment: initial !important;
                    background-blend-mode: initial !important;
                    background-clip: initial !important;
                    background-origin: initial !important;
                }}

                body.card {{

                }}
                {scrollbar_css}
            </style>"""

        image_mode = mw.col.conf.get("modern_menu_background_image_mode", "single")
        if image_mode == "separate":
            light_img_file = mw.col.conf.get("modern_menu_background_image_light", "")
            dark_img_file = mw.col.conf.get("modern_menu_background_image_dark", "")
        else:
            light_img_file = mw.col.conf.get("modern_menu_background_image", "")
            dark_img_file = light_img_file

        light_img_url = f"/_addons/{addon_name}/user_files/main_bg/{light_img_file}" if light_img_file else "none"
        dark_img_url = f"/_addons/{addon_name}/user_files/main_bg/{dark_img_file}" if dark_img_file else "none"
        
    elif reviewer_mode == "color":
        # Solid color only
        light_color = conf.get("onigiri_reviewer_bg_light_color", "#FFFFFF")
        dark_color = conf.get("onigiri_reviewer_bg_dark_color", "#2C2C2C")
        return f"""<style id="onigiri-reviewer-background-style">
            body {{ background-color: {light_color} !important; }}
            .night-mode body {{ background-color: {dark_color} !important; }}
            
            body.card {{

            }}
            {scrollbar_css}
        </style>"""
    
    else:  # image_color mode
        light_color = conf.get("onigiri_reviewer_bg_light_color", "#FFFFFF")
        dark_color = conf.get("onigiri_reviewer_bg_dark_color", "#2C2C2C")
        blur_val = conf.get("onigiri_reviewer_bg_blur", 0)
        opacity_val = conf.get("onigiri_reviewer_bg_opacity", 100)
        
        image_mode = conf.get("onigiri_reviewer_bg_image_theme_mode", conf.get("onigiri_reviewer_bg_image_mode", "separate"))
        if image_mode == "separate":
            light_img_file = conf.get("onigiri_reviewer_bg_image_light", "")
            dark_img_file = conf.get("onigiri_reviewer_bg_image_dark", "")
        else:
            light_img_file = conf.get("onigiri_reviewer_bg_image", "")
            dark_img_file = light_img_file

        light_img_url = f"/_addons/{addon_name}/user_files/reviewer_bg/{light_img_file}" if light_img_file else "none"
        dark_img_url = f"/_addons/{addon_name}/user_files/reviewer_bg/{dark_img_file}" if dark_img_file else "none"

    # EXACT COPY of overview CSS generation
    blur_px = blur_val * 0.2
    blur_bleed_px = math.ceil(blur_px * 3) if blur_px > 0 else 0
    opacity_float = opacity_val / 100.0
    bar_height = _reviewer_bottom_bar_height_px(conf)

    return f"""
    <style id="onigiri-reviewer-background-style">
        :root {{
            --onigiri-reviewer-bottom-bar-height: {bar_height}px;
            --onigiri-reviewer-background-blur-bleed: {blur_bleed_px}px;
        }}

        /* Use body::before pseudo-element for instant background rendering - no JavaScript delay */
        body {{
            position: relative;
            background-color: {light_color} !important;
        }}
        .night-mode body {{
            background-color: {dark_color} !important;
        }}

        body::before {{
            content: '';
            position: fixed;
            top: auto;
            bottom: calc(-1 * (var(--onigiri-reviewer-bottom-bar-height) + var(--onigiri-reviewer-background-blur-bleed)));
            left: 50%;
            width: 100vw;
            height: calc(100vh + var(--onigiri-reviewer-bottom-bar-height) + var(--onigiri-reviewer-background-blur-bleed));
            transform-origin: center bottom;
            transform: translateX(-50%) scale({1.0 + (blur_px / 50.0) if blur_px > 0 else 1.0});
            background-position: center;
            background-size: cover;
            background-repeat: no-repeat;
            z-index: -1;
            filter: blur({blur_px}px);
            opacity: {opacity_float};
            pointer-events: none;
            background-image: url('{light_img_url}');
        }}
        .night-mode body::before {{
            background-image: url('{dark_img_url}');
        }}

        html, .overview-center-container, .congrats-container {{
            background: transparent !important;
        }}

        /* Prevent body::before from affecting card content rendering */
        body.card {{

        }}
        {scrollbar_css}
    </style>
    """

def generate_overview_background_css(addon_path):
    """Generates CSS for the overview screen with instant background rendering using CSS pseudo-elements."""
    conf = config.get_config_readonly()
    overview_mode = conf.get("onigiri_overview_bg_mode", "main")
    
    # Defaults
    light_color = "#F5F5F5"
    dark_color = "#2C2C2C"
    blur_val = 0
    opacity_val = 100
    light_img_file = ""
    dark_img_file = ""
    is_image_mode = False

    if overview_mode == "main":
        # Use main menu background settings
        main_mode = mw.col.conf.get("modern_menu_background_mode", "color")
        light_color = mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
        dark_color = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
        
        # Use overview-specific blur/opacity for main mode
        blur_val = conf.get("onigiri_overview_bg_main_blur", 0)
        opacity_val = conf.get("onigiri_overview_bg_main_opacity", 100)
        
        if main_mode in ["image", "image_color"]:
            is_image_mode = True
            image_mode = mw.col.conf.get("modern_menu_background_image_mode", "single")
            if image_mode == "separate":
                light_img_file = mw.col.conf.get("modern_menu_background_image_light", "")
                dark_img_file = mw.col.conf.get("modern_menu_background_image_dark", "")
            else:
                light_img_file = mw.col.conf.get("modern_menu_background_image", "")
                dark_img_file = light_img_file
                
    elif overview_mode == "color":
        # Solid color only
        light_color = conf.get("onigiri_overview_bg_light_color", "#FFFFFF")
        dark_color = conf.get("onigiri_overview_bg_dark_color", "#2C2C2C")
        is_image_mode = False
        
    elif overview_mode == "image_color":
        # Image + Color
        light_color = conf.get("onigiri_overview_bg_light_color", "#FFFFFF")
        dark_color = conf.get("onigiri_overview_bg_dark_color", "#2C2C2C")
        
        blur_val = conf.get("onigiri_overview_bg_blur", 0)
        opacity_val = conf.get("onigiri_overview_bg_opacity", 100)
        is_image_mode = True
        
        image_mode = conf.get("onigiri_overview_bg_image_theme_mode", "separate")
        if image_mode == "separate":
            light_img_file = conf.get("onigiri_overview_bg_image_light", "")
            dark_img_file = conf.get("onigiri_overview_bg_image_dark", "")
        else:
            light_img_file = conf.get("onigiri_overview_bg_image", "")
            dark_img_file = light_img_file

    elif overview_mode == "slideshow":
        light_color = conf.get("onigiri_overview_bg_light_color", "#FFFFFF")
        dark_color = conf.get("onigiri_overview_bg_dark_color", "#2C2C2C")
        blur_val = conf.get("onigiri_overview_bg_blur", 0)
        opacity_val = conf.get("onigiri_overview_bg_opacity", 100)
        addon_name = os.path.basename(addon_path)
        images = conf.get("onigiri_overview_slideshow_images", []) or []
        image_urls = [f"/_addons/{addon_name}/user_files/main_bg/{img}" for img in images]
        return _render_body_slideshow_background_css(
            "onigiri-overview-background-style",
            image_urls,
            conf.get("onigiri_overview_slideshow_interval", 10),
            light_color,
            dark_color,
            blur_val,
            opacity_val,
            "#onigiri-background-div { display: none !important; }",
        )

    if overview_mode == "main" and mw.col.conf.get("modern_menu_background_mode", "color") == "slideshow":
        addon_name = os.path.basename(addon_path)
        images = config.get_collection_config("modern_menu_slideshow_images", []) or []
        image_urls = [f"/_addons/{addon_name}/user_files/main_bg/{img}" for img in images]
        return _render_body_slideshow_background_css(
            "onigiri-overview-background-style",
            image_urls,
            mw.col.conf.get("modern_menu_slideshow_interval", 10),
            light_color,
            dark_color,
            blur_val,
            opacity_val,
            "#onigiri-background-div { display: none !important; }",
        )

    if not is_image_mode:
        return f"""<style id="onigiri-overview-background-style">
            html,
            body {{
                background-color: {light_color} !important;
                background-image: none !important;
            }}
            .night-mode html,
            .night-mode body,
            .nightMode html,
            .nightMode body {{
                background-color: {dark_color} !important;
            }}
            body::before,
            body::after,
            html::before,
            html::after,
            #overview-wrapper::before,
            #overview-wrapper::after,
            #overview::before,
            #overview::after,
            .main::before,
            .main::after,
            .toolbar::before,
            .toolbar::after,
            .bottom::before,
            .bottom::after {{
                content: none !important;
                background: none !important;
                background-image: none !important;
            }}
            .overview-center-container,
            .congrats-container,
            #overview-wrapper,
            #overview,
            .main,
            .toolbar,
            .bottom {{
                background: transparent !important;
                background-image: none !important;
            }}
        </style>"""

    addon_name = os.path.basename(addon_path)
    light_img_url = f"/_addons/{addon_name}/user_files/main_bg/{light_img_file}" if light_img_file else "none"
    dark_img_url = f"/_addons/{addon_name}/user_files/main_bg/{dark_img_file}" if dark_img_file else "none"

    blur_px = blur_val * 0.2
    opacity_float = opacity_val / 100.0

    return f"""
    <style id="onigiri-overview-background-style">
        /* Use body::before pseudo-element for instant background rendering - no JavaScript delay */
        html {{
            background-color: {light_color} !important;
            background-image: none !important;
        }}
        body {{
            position: relative;
            isolation: isolate;
            background: transparent !important;
            background-image: none !important;
            background-color: transparent !important;
        }}
        .night-mode html,
        .nightMode html {{
            background-color: {dark_color} !important;
            background-image: none !important;
        }}
        .night-mode body,
        .nightMode body {{
            background: transparent !important;
            background-image: none !important;
            background-color: transparent !important;
        }}

        body::before {{
            content: '' !important;
            position: fixed;
            top: 50%; left: 50%;
            width: 100vw; height: 100vh;
            transform: translate(-50%, -50%) scale({1.0 + (blur_px / 50.0) if blur_px > 0 else 1.0});
            background-position: center;
            background-size: cover;
            background-repeat: no-repeat;
            z-index: 0 !important;
            filter: blur({blur_px}px);
            opacity: {opacity_float} !important;
            pointer-events: none;
            background-image: url('{light_img_url}') !important;
        }}
        body::after {{
            content: none !important;
            background: none !important;
            background-image: none !important;
        }}
        html::before,
        html::after,
        #overview-wrapper::before,
        #overview-wrapper::after,
        #overview::before,
        #overview::after,
        .main::before,
        .main::after,
        .toolbar::before,
        .toolbar::after,
        .bottom::before,
        .bottom::after {{
            content: none !important;
            background: none !important;
            background-image: none !important;
        }}
        .night-mode body::before,
        .nightMode body::before {{
            background-image: url('{dark_img_url}') !important;
        }}

        /* Keep JavaScript-created div styling for backwards compatibility */
        #onigiri-background-div {{
            display: none !important;
        }}

        .overview-center-container, .congrats-container,
        #overview-wrapper, #overview, .main, .toolbar, .bottom {{
            background: transparent !important;
            background-image: none !important;
        }}
        body > *:not(style):not(script),
        .overview-center-container,
        .congrats-container {{
            position: relative;
            z-index: 1;
        }}
    </style>
    """

def generate_toolbar_background_css(addon_path):
	"""Generates background CSS for the top and bottom toolbars based on user settings."""
	toolbar_mode = mw.col.conf.get("onigiri_toolbar_bg_mode", "main")

	if toolbar_mode == "main":
		# Use main background settings
		mode = mw.col.conf.get("modern_menu_background_mode", "color")
		light = mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
		dark = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
		image = mw.col.conf.get("modern_menu_background_image", "")
		blur = mw.col.conf.get("modern_menu_background_blur", 0)
		opacity = 100 # Opacity not supported for toolbar custom bg yet
		image_path = f"user_files/{image}" if image else ""
	else:
		# Use toolbar-specific settings
		mode = toolbar_mode
		light = mw.col.conf.get("onigiri_toolbar_bg_color_light", "#FFFFFF")
		dark = mw.col.conf.get("onigiri_toolbar_bg_color_dark", "#2C2C2C")
		image = mw.col.conf.get("onigiri_toolbar_bg_image", "")
		blur = mw.col.conf.get("onigiri_toolbar_bg_blur", 0)
		opacity = 100 # Opacity not supported for toolbar custom bg yet
		image_path = f"user_files/toolbar_bg/{image}" if image else ""

	return _render_background_css("body", mode, light, dark, image_path, image_path, blur, addon_path, "onigiri-toolbar-bg-style", opacity)

# ── Reviewer header progress bar ──────────────────────────────────────────────
#
# A slim "light at the end of the tunnel" gauge that rides in the reviewer
# header next to the header buttons.
#
# `left` is exactly what Anki's bottom bar shows - the scheduler's
# new/learning/review counts for the deck being studied - so the two surfaces
# can never disagree. `done` is either the cards answered since the reviewer was
# entered ("session", the default) or every review logged today across the decks
# in play ("today"). The total is `done + left` rather than a snapshot taken at
# the start, because a snapshot lies: answering a new card with Good moves it
# from the new count into the learning count, leaving `left` unchanged, and a
# bar built on `left` alone would sit frozen for the first half of a session.

_PROGRESS_STYLES = ("bar", "segments", "ring", "text")
_PROGRESS_LABELS = ("fraction", "percent", "remaining", "done", "none")

# Answered-card bookkeeping for the "session" scope, plus the revlog baseline
# the "today" scope starts from. Reset whenever the reviewer is (re-)entered or
# the studied deck changes; `mw` is single-collection, so a plain module global
# is the right amount of machinery here.
_progress_session = {"key": None, "answered": 0, "today_base": 0}

# Settings are read once per reviewer entry and reused for every card. The
# answer path must not touch the config store (see the 2026-08-19 lag fix).
_progress_settings_cache = {"key": None, "settings": None}


def _reviewer_progress_settings(conf=None, force=False):
    """The progress bar's settings, resolved and clamped exactly once per
    reviewer session."""
    col = getattr(mw, "col", None)
    cache_key = id(col) if col is not None else None
    if not force and _progress_settings_cache["key"] == cache_key:
        cached = _progress_settings_cache["settings"]
        if cached is not None:
            return cached

    if conf is None:
        conf = config.get_config_readonly()

    def _num(key, default, low, high):
        try:
            value = float(conf.get(key, default))
        except (TypeError, ValueError):
            value = float(default)
        return int(max(low, min(high, value)))

    def _pick(key, default, allowed):
        value = str(conf.get(key, default) or default)
        return value if value in allowed else default

    def _pair(key, light_default, dark_default):
        return (
            str(conf.get(f"{key}_light", light_default) or light_default),
            str(conf.get(f"{key}_dark", dark_default) or dark_default),
        )

    # The segment colours can follow the very count bubbles the bottom bar
    # paints, so "23 review cards left" is the same green in both places.
    overview_colors = (conf.get("overview_style", {}) or {}).get("colors", {}) or {}

    def _count_pair(key, light_default, dark_default):
        light = (overview_colors.get("light", {}) or {}).get(key) or light_default
        dark = (overview_colors.get("dark", {}) or {}).get(key) or dark_default
        return str(light), str(dark)

    seg_source = _pick("onigiri_reviewer_progress_segment_source", "counts", ("counts", "custom"))
    if seg_source == "counts":
        seg_new = _count_pair("new_bubble", "#1e8cff", "#0a84ff")
        seg_learn = _count_pair("learn_bubble", "#ff5757", "#ff453a")
        seg_review = _count_pair("review_bubble", "#19c96b", "#12b765")
    else:
        seg_new = _pair("onigiri_reviewer_progress_seg_new", "#1e8cff", "#0a84ff")
        seg_learn = _pair("onigiri_reviewer_progress_seg_learn", "#ff5757", "#ff453a")
        seg_review = _pair("onigiri_reviewer_progress_seg_review", "#19c96b", "#12b765")

    settings = {
        "enabled": bool(conf.get("onigiri_reviewer_progress_enabled", True)),
        "style": _pick("onigiri_reviewer_progress_style", "bar", _PROGRESS_STYLES),
        "label": _pick("onigiri_reviewer_progress_label", "fraction", _PROGRESS_LABELS),
        "scope": _pick("onigiri_reviewer_progress_scope", "session", ("session", "today")),
        "position": _pick("onigiri_reviewer_progress_position", "right", ("right", "left")),
        "width": _num("onigiri_reviewer_progress_width", 96, 40, 320),
        "thickness": _num("onigiri_reviewer_progress_thickness", 6, 2, 20),
        "radius": _num("onigiri_reviewer_progress_radius", 999, 0, 999),
        "ring_size": _num("onigiri_reviewer_progress_ring_size", 16, 12, 40),
        "chrome": bool(conf.get("onigiri_reviewer_progress_chrome", True)),
        "animate": bool(conf.get("onigiri_reviewer_progress_animate", True)),
        "gradient": bool(conf.get("onigiri_reviewer_progress_gradient", True)),
        "hide_when_done": bool(conf.get("onigiri_reviewer_progress_hide_when_done", False)),
        "fill": _pair("onigiri_reviewer_progress_fill", "#19c96b", "#12b765"),
        "fill_end": _pair("onigiri_reviewer_progress_fill_end", "#5ad6f0", "#4bc4de"),
        "track": _pair("onigiri_reviewer_progress_track", "rgba(0, 0, 0, 0.12)", "rgba(255, 255, 255, 0.16)"),
        "text": _pair("onigiri_reviewer_progress_text", "#2c2c2c", "#e8e8e8"),
        "seg_new": seg_new,
        "seg_learn": seg_learn,
        "seg_review": seg_review,
    }

    _progress_settings_cache["key"] = cache_key
    _progress_settings_cache["settings"] = settings
    return settings


def invalidate_reviewer_progress_settings():
    """Drop the cached settings so the next reviewer entry re-reads them."""
    _progress_settings_cache["key"] = None
    _progress_settings_cache["settings"] = None


def _progress_session_key(col):
    try:
        return (id(col), int(col.decks.current()["id"]))
    except Exception:
        return (id(col), 0)


def _reviews_logged_today(col):
    """How many reviews today's revlog holds for the decks currently in play.

    Run once per reviewer entry (never on the answer path): the subquery walks
    the card table for the whole deck tree."""
    try:
        cutoff_ms = (int(col.sched.day_cutoff) - 86400) * 1000
        dids = ",".join(str(deck_id) for deck_id in _selected_deck_ids(col))
        if not dids:
            return 0
        count = col.db.scalar(
            "select count() from revlog where id >= ? and ease > 0 "
            f"and cid in (select id from cards where did in ({dids}) or odid in ({dids}))",
            cutoff_ms,
        )
        return max(0, int(count or 0))
    except Exception:
        return 0


def reset_reviewer_progress_session(force=False):
    """Start (or restart) the progress bar's bookkeeping for a study session."""
    col = getattr(mw, "col", None)
    if col is None:
        return
    key = _progress_session_key(col)
    if not force and _progress_session["key"] == key:
        return
    settings = _reviewer_progress_settings()
    _progress_session["key"] = key
    _progress_session["answered"] = 0
    _progress_session["today_base"] = (
        _reviews_logged_today(col) if settings["scope"] == "today" else 0
    )


def _reviewer_progress_counts():
    """{new, learn, review, left, done, total, pct} for the current queue."""
    data = {"new": 0, "learn": 0, "review": 0, "left": 0, "done": 0, "total": 0, "pct": 0}
    col = getattr(mw, "col", None)
    if col is None:
        return data
    try:
        counts = list(col.sched.counts())
    except Exception:
        counts = []
    counts += [0] * (3 - len(counts))
    data["new"] = max(0, int(counts[0] or 0))
    data["learn"] = max(0, int(counts[1] or 0))
    data["review"] = max(0, int(counts[2] or 0))
    data["left"] = data["new"] + data["learn"] + data["review"]

    settings = _reviewer_progress_settings()
    done = _progress_session["answered"]
    if settings["scope"] == "today":
        done += _progress_session["today_base"]
    data["done"] = max(0, int(done))
    data["total"] = data["done"] + data["left"]
    data["pct"] = 100 if data["total"] <= 0 else int(round(100.0 * data["done"] / data["total"]))
    return data


def _reviewer_progress_label_text(settings, data):
    label = settings["label"]
    if label == "none":
        return ""
    if label == "percent":
        return f"{data['pct']}%"
    if label == "remaining":
        return tr("progress_left_short", "{count} left").format(count=data["left"])
    if label == "done":
        return tr("progress_done_short", "{count} done").format(count=data["done"])
    return f"{data['done']}/{data['total']}"


def _reviewer_progress_tooltip(data):
    return tr(
        "progress_tooltip",
        "{done} done · {left} left · {pct}%",
    ).format(done=data["done"], left=data["left"], pct=data["pct"])


def _reviewer_progress_inner_html(settings=None, data=None):
    """The gauge itself. Kept separate from the chip so the per-card update can
    replace only this and leave the chip element (and its transitions) alone."""
    if settings is None:
        settings = _reviewer_progress_settings()
    if data is None:
        data = _reviewer_progress_counts()

    label_text = _reviewer_progress_label_text(settings, data)
    label_html = (
        f'<span class="orp-text">{html.escape(label_text)}</span>' if label_text else ""
    )
    style = settings["style"]
    pct = max(0, min(100, data["pct"]))

    if style == "text":
        return label_html or f'<span class="orp-text">{data["done"]}/{data["total"]}</span>'

    if style == "ring":
        size = settings["ring_size"]
        stroke = max(1, min(max(2, size // 3), settings["thickness"]))
        radius = (size - stroke) / 2.0
        circumference = 2 * math.pi * radius
        dash = circumference * (pct / 100.0)
        gauge = (
            f'<svg class="orp-ring" viewBox="0 0 {size} {size}" width="{size}" height="{size}" aria-hidden="true">'
            f'<circle class="orp-ring-track" cx="{size / 2}" cy="{size / 2}" r="{radius:.2f}" '
            f'fill="none" stroke-width="{stroke}"></circle>'
            f'<circle class="orp-ring-fill" cx="{size / 2}" cy="{size / 2}" r="{radius:.2f}" '
            f'fill="none" stroke-width="{stroke}" stroke-linecap="round" '
            f'stroke-dasharray="{dash:.2f} {circumference:.2f}" '
            f'transform="rotate(-90 {size / 2} {size / 2})"></circle>'
            "</svg>"
        )
        return gauge + label_html

    if style == "segments":
        total = max(1, data["total"])
        widths = {
            "done": 100.0 * data["done"] / total,
            "new": 100.0 * data["new"] / total,
            "learn": 100.0 * data["learn"] / total,
            "review": 100.0 * data["review"] / total,
        }
        segments = "".join(
            f'<span class="orp-seg is-{name}" style="width: {widths[name]:.3f}%;"></span>'
            for name in ("done", "new", "learn", "review")
        )
        gauge = f'<span class="orp-track is-segmented">{segments}</span>'
        return gauge + label_html

    gauge = (
        '<span class="orp-track">'
        f'<span class="orp-fill" style="width: {pct}%;"></span>'
        "</span>"
    )
    return gauge + label_html


def _reviewer_progress_classes(settings):
    classes = ["onigiri-reviewer-progress", f"is-{settings['style']}"]
    if not settings["chrome"]:
        classes.append("is-bare")
    if settings["animate"]:
        classes.append("is-animated")
    if settings["label"] == "none":
        classes.append("is-labelless")
    return " ".join(classes)


def _reviewer_progress_html(settings=None, data=None):
    """The whole chip, or "" when the bar is off / has nothing to say."""
    if settings is None:
        settings = _reviewer_progress_settings()
    if not settings["enabled"]:
        return ""
    if data is None:
        data = _reviewer_progress_counts()
    if settings["hide_when_done"] and data["left"] <= 0:
        return ""

    return (
        f'<div id="onigiri-reviewer-progress" class="{_reviewer_progress_classes(settings)}" '
        f'role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{data["pct"]}" '
        f'title="{html.escape(_reviewer_progress_tooltip(data), quote=True)}">'
        f"{_reviewer_progress_inner_html(settings, data)}"
        "</div>"
    )


def _reviewer_progress_css(settings=None):
    """Colour/size tokens for the chip. Emitted with the same
    `.night_mode #onigiri-reviewer-header` prefix the rest of this module uses,
    so __init__.py's shadow-DOM rewrite reaches it too."""
    if settings is None:
        settings = _reviewer_progress_settings()
    if not settings["enabled"]:
        return ""

    fill_light, fill_dark = settings["fill"]
    end_light, end_dark = settings["fill_end"]
    track_light, track_dark = settings["track"]
    text_light, text_dark = settings["text"]
    new_light, new_dark = settings["seg_new"]
    learn_light, learn_dark = settings["seg_learn"]
    review_light, review_dark = settings["seg_review"]

    fill_image_light = (
        f"linear-gradient(90deg, {fill_light}, {end_light})" if settings["gradient"] else fill_light
    )
    fill_image_dark = (
        f"linear-gradient(90deg, {fill_dark}, {end_dark})" if settings["gradient"] else fill_dark
    )

    return f"""
    <style id="onigiri-reviewer-progress-style">
        #onigiri-reviewer-header .onigiri-reviewer-progress {{
            --orp-fill: {fill_light};
            --orp-fill-image: {fill_image_light};
            --orp-track: {track_light};
            --orp-text: {text_light};
            --orp-new: {new_light};
            --orp-learn: {learn_light};
            --orp-review: {review_light};
            --orp-width: {settings["width"]}px;
            --orp-thickness: {settings["thickness"]}px;
            --orp-radius: {settings["radius"]}px;

            display: flex !important;
            align-items: center !important;
            gap: 8px !important;
            flex: 0 0 auto !important;
            box-sizing: border-box !important;
            margin: 0 !important;
            padding: 5px 12px !important;
            border-radius: var(--onigiri-box-effect-radius, 8px) !important;
            border: var(--onigiri-box-effect-stroke, 1px) solid var(--onigiri-box-effect-border, rgba(128, 128, 128, 0.2)) !important;
            background: var(--onigiri-box-effect-bg, var(--canvas-inset, rgba(247, 247, 247, 0.92))) !important;
            backdrop-filter: blur(var(--onigiri-box-effect-blur, 0px)) !important;
            -webkit-backdrop-filter: blur(var(--onigiri-box-effect-blur, 0px)) !important;
            color: var(--orp-text) !important;
            font-family: var(--font-main), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
            font-size: var(--font-size-main, 13px) !important;
            font-weight: 500 !important;
            line-height: normal !important;
            white-space: nowrap !important;
            cursor: default !important;
            user-select: none !important;
        }}

        /* The unstyled fallback has to flip with the theme exactly like
           a.onigiri-reviewer-button's does: without it a collection that has
           never set the box-effect colours gets a near-white chip in dark mode,
           and the label - which *does* follow the theme - goes invisible on it. */
        .night_mode #onigiri-reviewer-header .onigiri-reviewer-progress {{
            --orp-fill: {fill_dark};
            --orp-fill-image: {fill_image_dark};
            --orp-track: {track_dark};
            --orp-text: {text_dark};
            --orp-new: {new_dark};
            --orp-learn: {learn_dark};
            --orp-review: {review_dark};

            background: var(--onigiri-box-effect-bg, var(--canvas-inset, rgba(42, 42, 42, 0.92))) !important;
            border-color: var(--onigiri-box-effect-border, rgba(128, 128, 128, 0.2)) !important;
        }}

        .night_mode #onigiri-reviewer-header .onigiri-reviewer-progress.is-bare {{
            background: transparent !important;
            border-color: transparent !important;
        }}

        /* The chip has to end up exactly as tall as the header buttons beside
           it, and a 6px bar is far shorter than a line of 13px text. This strut
           gives the gauge the text's own line box, so both stay in step at any
           font size or thickness. */
        #onigiri-reviewer-header .onigiri-reviewer-progress .orp-track {{
            display: flex !important;
            align-items: stretch !important;
            overflow: hidden !important;
            width: var(--orp-width) !important;
            height: var(--orp-thickness) !important;
            border-radius: var(--orp-radius) !important;
            background: var(--orp-track) !important;
            flex: 0 0 auto !important;
            align-self: center !important;
        }}

        #onigiri-reviewer-header .onigiri-reviewer-progress .orp-fill {{
            display: block !important;
            height: 100% !important;
            min-width: 0 !important;
            border-radius: inherit !important;
            background: var(--orp-fill-image) !important;
        }}

        #onigiri-reviewer-header .onigiri-reviewer-progress .orp-track.is-segmented {{
            gap: 2px !important;
            background: transparent !important;
        }}

        #onigiri-reviewer-header .onigiri-reviewer-progress .orp-seg {{
            display: block !important;
            height: 100% !important;
            min-width: 0 !important;
            border-radius: var(--orp-radius) !important;
        }}

        #onigiri-reviewer-header .onigiri-reviewer-progress .orp-seg.is-done {{ background: var(--orp-fill-image) !important; }}
        #onigiri-reviewer-header .onigiri-reviewer-progress .orp-seg.is-new {{ background: var(--orp-new) !important; }}
        #onigiri-reviewer-header .onigiri-reviewer-progress .orp-seg.is-learn {{ background: var(--orp-learn) !important; }}
        #onigiri-reviewer-header .onigiri-reviewer-progress .orp-seg.is-review {{ background: var(--orp-review) !important; }}

        #onigiri-reviewer-header .onigiri-reviewer-progress .orp-ring {{
            display: block !important;
            flex: 0 0 auto !important;
            overflow: visible !important;
        }}
        #onigiri-reviewer-header .onigiri-reviewer-progress .orp-ring-track {{ stroke: var(--orp-track) !important; }}
        #onigiri-reviewer-header .onigiri-reviewer-progress .orp-ring-fill {{
            stroke: var(--orp-fill) !important;
        }}

        /* Only the in-place update animates: update_reviewer_progress moves the
           existing nodes rather than re-writing the chip, precisely so these
           transitions have something to run on. */
        #onigiri-reviewer-header .onigiri-reviewer-progress.is-animated .orp-fill,
        #onigiri-reviewer-header .onigiri-reviewer-progress.is-animated .orp-seg {{
            transition: width 0.35s ease !important;
        }}
        #onigiri-reviewer-header .onigiri-reviewer-progress.is-animated .orp-ring-fill {{
            transition: stroke-dasharray 0.35s ease !important;
        }}

        #onigiri-reviewer-header .onigiri-reviewer-progress .orp-text {{
            display: block !important;
            color: var(--orp-text) !important;
            font-variant-numeric: tabular-nums !important;
            font-weight: 600 !important;
            letter-spacing: 0.01em !important;
        }}

        #onigiri-reviewer-header .onigiri-reviewer-progress.is-bare {{
            padding: 5px 2px !important;
            background: transparent !important;
            border-color: transparent !important;
            backdrop-filter: none !important;
            -webkit-backdrop-filter: none !important;
        }}

        /* No label means no line box to borrow a height from, so the chip needs
           the strut it was getting from the text for free. */
        #onigiri-reviewer-header .onigiri-reviewer-progress.is-labelless::before {{
            content: "\\200b" !important;
            display: inline !important;
            width: 0 !important;
        }}
    </style>
    """


def _reviewer_progress_payload(settings, data):
    """What the per-card update sends: the numbers to move the existing nodes
    to, plus a full re-render to fall back on when the chip's shape has changed
    under it (a settings save while the reviewer is open)."""
    total = max(1, data["total"])
    # "Text only" with the label switched off would leave nothing at all, so the
    # renderer falls back to the fraction there; the payload has to agree or the
    # in-place update would wipe the text the renderer just drew.
    label = _reviewer_progress_label_text(settings, data)
    if settings["style"] == "text" and not label:
        label = f"{data['done']}/{data['total']}"
    payload = {
        "style": settings["style"],
        "classes": _reviewer_progress_classes(settings),
        "inner": _reviewer_progress_inner_html(settings, data),
        "label": label,
        "pct": data["pct"],
        "title": _reviewer_progress_tooltip(data),
        "hidden": bool(settings["hide_when_done"] and data["left"] <= 0),
        "segments": [
            round(100.0 * data[name] / total, 3)
            for name in ("done", "new", "learn", "review")
        ],
    }
    if settings["style"] == "ring":
        size = settings["ring_size"]
        stroke = max(1, min(max(2, size // 3), settings["thickness"]))
        circumference = 2 * math.pi * ((size - stroke) / 2.0)
        payload["dash"] = f"{circumference * data['pct'] / 100.0:.2f} {circumference:.2f}"
    return payload


def update_reviewer_progress():
    """Repaint the header gauge.

    The nodes are moved rather than replaced whenever the chip already has the
    shape the payload describes: replacing the markup would restart every
    element and the width/dasharray transitions would never run. The full
    re-render is the fallback for when the shape really did change."""
    try:
        if getattr(mw, "state", None) != "review":
            return
        settings = _reviewer_progress_settings()
        if not settings["enabled"]:
            return
        reviewer = getattr(mw, "reviewer", None)
        reviewer_web = reviewer and getattr(reviewer, "web", None)
        if not reviewer_web:
            return

        payload = json.dumps(_reviewer_progress_payload(settings, _reviewer_progress_counts()))
        reviewer_web.eval(
            f"""
        (function() {{
            const p = {payload};
            const host = document.getElementById('onigiri-reviewer-ui-host');
            const root = host && host.shadowRoot;
            const chip = root && root.getElementById('onigiri-reviewer-progress');
            if (!chip) return;
            chip.style.display = p.hidden ? 'none' : '';
            if (p.hidden) return;
            chip.setAttribute('aria-valuenow', String(p.pct));
            chip.setAttribute('title', p.title);

            let moved = chip.classList.contains('is-' + p.style);
            if (moved) {{
                if (p.style === 'bar') {{
                    const fill = chip.querySelector('.orp-fill');
                    if (fill) fill.style.width = p.pct + '%'; else moved = false;
                }} else if (p.style === 'segments') {{
                    const segs = chip.querySelectorAll('.orp-seg');
                    if (segs.length === p.segments.length) {{
                        p.segments.forEach(function(width, i) {{ segs[i].style.width = width + '%'; }});
                    }} else {{ moved = false; }}
                }} else if (p.style === 'ring') {{
                    const ring = chip.querySelector('.orp-ring-fill');
                    if (ring) ring.setAttribute('stroke-dasharray', p.dash); else moved = false;
                }}
            }}
            if (moved) {{
                const text = chip.querySelector('.orp-text');
                if (text) text.textContent = p.label;
                else if (p.label) moved = false;
            }}
            if (!moved) {{
                chip.className = p.classes;
                chip.innerHTML = p.inner;
            }}
        }})();
        """
        )
    except Exception as e:
        print(f"Onigiri: Error updating reviewer progress bar: {e}")


def _reviewer_card_type_info(card):
    """Return the small status marker payload for the card on screen."""
    try:
        queue = int(getattr(card, "queue", -1))
    except (TypeError, ValueError):
        queue = -1

    if queue == 0:
        return {"key": "new", "label": tr("new")}
    if queue in (1, 3):
        return {"key": "learn", "label": tr("learning")}
    if queue == 2:
        return {"key": "review", "label": tr("to_review")}

    # The queue is the authoritative state, but older Anki versions can expose
    # a less specific queue while the card type is already known.
    try:
        card_type = int(getattr(card, "type", -1))
    except (TypeError, ValueError):
        card_type = -1
    fallback = {
        0: ("new", tr("new")),
        1: ("learn", tr("learning")),
        2: ("review", tr("to_review")),
    }.get(card_type)
    return {"key": fallback[0], "label": fallback[1]} if fallback else None


def update_reviewer_card_type(card):
    """Update the count-box marker that identifies the card currently shown."""
    try:
        if getattr(mw, "state", None) != "review":
            return
        bottom_web = getattr(mw, "bottomWeb", None)
        if not bottom_web:
            return
        payload = json.dumps(_reviewer_card_type_info(card))
        bottom_web.eval(
            f"""
            (function() {{
                const info = {payload};
                window.__onigiriPendingReviewerCardType = info;
                if (typeof window.onigiriSetReviewerCardType === 'function') {{
                    window.onigiriSetReviewerCardType(info);
                }}
            }})();
            """
        )
    except Exception as e:
        print(f"Onigiri: Error updating reviewer card type: {e}")


def _on_reviewer_progress_state_change(new_state, old_state):
    if new_state == "review":
        # Deck switches and re-entries both land here; the key check inside
        # keeps a mid-session state bounce from zeroing the counter.
        invalidate_reviewer_progress_settings()
        reset_reviewer_progress_session()
    elif old_state == "review":
        _progress_session["key"] = None


def _on_reviewer_progress_answered(reviewer, card, ease):
    _progress_session["answered"] += 1


def _on_reviewer_progress_show_question(card):
    # Fires after the scheduler has re-counted, which is what makes the numbers
    # here identical to the ones the bottom bar just drew.
    update_reviewer_progress()
    update_reviewer_card_type(card)


def generate_reviewer_top_bar_html_and_css(include_overview_class=True):
    """Generates the HTML and basic structural CSS for the new web-based reviewer top bar."""

    conf = config.get_config_readonly()
    is_base_hide_mode = (
        conf.get("hideNativeHeaderAndBottomBar", False)
        and not conf.get("flowMode", False)
    )
    if not is_base_hide_mode:
        return "", ""

    # Check if restaurant level should be shown in reviewer header
    show_restaurant_chip = False
    restaurant_chip_html = ""
    
    # Get restaurant level config
    restaurant_conf = conf.get("restaurant_level", {})
    if not restaurant_conf:
        achievements_conf = conf.get("achievements", {})
        restaurant_conf = achievements_conf.get("restaurant_level", {})
    
    if (restaurant_conf.get("enabled", False) and
        restaurant_conf.get("show_reviewer_header", False)):
        restaurant_chip_html = _get_reviewer_nook_level_chip_html()
        show_restaurant_chip = bool(restaurant_chip_html.strip())

        # Register the hook if not already registered
        if show_restaurant_chip and not hasattr(mw, '_onigiri_restaurant_hook_registered'):
            from aqt import gui_hooks
            gui_hooks.reviewer_did_answer_card.append(on_reviewer_did_answer_card)
            mw._onigiri_restaurant_hook_registered = True

    # Build the HTML with the restaurant chip if enabled
    hashi_notes_conf = conf.get("hashi_notes", {}) or {}
    show_hashi_notes_button = hashi_notes_conf.get("show_in_reviewer_header", True)
    show_pomodoro_button = conf.get("onigiri_pomodoro_show_in_reviewer_header", True)

    hashi_notes_button_html = (
        '<a href="#" onclick="pycmd(\'openHashiNotes:reviewer\'); return false;" '
        f'class="onigiri-reviewer-button onigiri-hashi-notes-button">{tr_at("hashi_notes_title")}</a>'
        if show_hashi_notes_button else ""
    )
    pomodoro_button_html = (
        '<a href="#" onclick="pycmd(\'togglePomodoro\'); return false;" '
        f'class="onigiri-reviewer-button onigiri-pomodoro-button">{tr_at("pomodoro_title")}</a>'
        if show_pomodoro_button else ""
    )

    # The header gauge only makes sense over a live queue, so it is built for
    # the reviewer webview and left out of the overview's copy of this header.
    # Anki sets the reviewer's web content before it fires state_did_change, so
    # the cache still holds the previous session's settings here: re-read.
    progress_settings = _reviewer_progress_settings(conf, force=not include_overview_class)
    progress_html = ""
    progress_css = ""
    if not include_overview_class and progress_settings["enabled"]:
        reset_reviewer_progress_session()
        progress_html = _reviewer_progress_html(progress_settings)
        progress_css = _reviewer_progress_css(progress_settings)

    header_buttons = f"""
    <div class="onigiri-reviewer-header-buttons">
        {progress_html if progress_settings["position"] == "left" else ""}
        <a href="#" onclick="pycmd('decks'); return false;" class="onigiri-reviewer-button">{tr_at("decks")}</a>
        <a href="#" onclick="pycmd('add'); return false;" class="onigiri-reviewer-button">{tr_at("add")}</a>
        <a href="#" onclick="pycmd('browse'); return false;" class="onigiri-reviewer-button">{tr_at("browse")}</a>
        <a href="#" onclick="pycmd('stats'); return false;" class="onigiri-reviewer-button">{tr_at("stats")}</a>
        <a href="#" onclick="pycmd('sync'); return false;" class="onigiri-reviewer-button">{tr_at("sync")}</a>
        {hashi_notes_button_html}
        {pomodoro_button_html}
        {restaurant_chip_html if show_restaurant_chip else ""}
        {progress_html if progress_settings["position"] == "right" else ""}
    </div>
    """
    
    html = f"""
    <div id="onigiri-reviewer-header" class="header">
        {header_buttons}
    </div>
    """

    css = """
    <style id="onigiri-reviewer-top-bar-structure">
        #onigiri-reviewer-header, .overview-header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            width: max-content;
            max-width: calc(100vw - 24px);
            min-height: 40px;
            /* vh cap keeps the bar's on-screen footprint fixed regardless of
               Anki's zoom. Zooming in shrinks the viewport's CSS px, so the bar
               wraps into extra rows; without a cap its height grows unbounded
               and the qa-offset JS shoves the card down until the bar covers
               most of the reviewer. 30vh is zoom-invariant on screen (30% of
               the reviewer, worst case) and scrolls past that instead. */
            max-height: 30vh;
            overflow-y: auto;
            overflow-x: hidden;
            margin: 5px auto 10px auto;
            border-radius: 12px;
            height: auto;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 4px 10px;
            box-sizing: border-box;
            -webkit-font-smoothing: antialiased;
            pointer-events: auto;
            z-index: 1000; /* Increased z-index */

            /* ISOLATION FROM CARD TEMPLATES */
            font-family: var(--font-main), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
            font-size: var(--font-size-main, 13px) !important;
            line-height: normal !important;
            color: initial !important;
            text-align: center !important;
            text-transform: none !important;
            white-space: normal !important;
            letter-spacing: normal !important;
            word-spacing: normal !important;
            text-shadow: none !important;
        }
        

        
        .onigiri-reviewer-header-buttons {
            display: flex;
            align-items: center;
            justify-content: center;
            flex-wrap: wrap;
            gap: 8px;
            min-width: 0;
            position: relative;
        }

        /* Target A tags specifically to override card template global a {} styles */
        #onigiri-reviewer-header a.onigiri-reviewer-button,
        #onigiri-overview-header a.onigiri-reviewer-button,
        .overview-header a.onigiri-reviewer-button {
            color: var(--onigiri-box-effect-fg, var(--fg)) !important;
            background: var(--onigiri-box-effect-bg, var(--canvas-inset, rgba(247, 247, 247, 0.92))) !important;
            padding: 5px 12px !important;
            border-radius: var(--onigiri-box-effect-radius, 8px) !important;
            border: var(--onigiri-box-effect-stroke, 1px) solid var(--onigiri-box-effect-border, rgba(128, 128, 128, 0.2)) !important;
            font-family: var(--font-main), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
            font-size: var(--font-size-main, 13px) !important;
            text-decoration: none !important;
            font-style: normal !important;
            font-weight: 500 !important;
            transition: background-color 0.2s ease, border-color 0.2s ease !important;
            display: inline-block !important;
            line-height: normal !important;
            white-space: nowrap !important;
            flex: 0 0 auto !important;
            backdrop-filter: blur(var(--onigiri-box-effect-blur, 0px)) !important;
            -webkit-backdrop-filter: blur(var(--onigiri-box-effect-blur, 0px)) !important;
        }

        .night_mode #onigiri-reviewer-header a.onigiri-reviewer-button,
        .night_mode #onigiri-overview-header a.onigiri-reviewer-button,
        .night_mode .overview-header a.onigiri-reviewer-button {
            color: var(--onigiri-box-effect-fg, var(--fg)) !important;
            background: var(--onigiri-box-effect-bg, var(--canvas-inset, rgba(42, 42, 42, 0.92))) !important;
            border-color: var(--onigiri-box-effect-border, rgba(128, 128, 128, 0.2)) !important;
        }

        #onigiri-reviewer-header a.onigiri-reviewer-button:hover,
        #onigiri-overview-header a.onigiri-reviewer-button:hover,
        .overview-header a.onigiri-reviewer-button:hover {
            background: var(--onigiri-box-effect-bg, var(--canvas-inset, rgba(128, 128, 128, 0.25))) !important;
            border-color: var(--onigiri-box-effect-border-hover, var(--onigiri-box-effect-border, rgba(128, 128, 128, 0.3))) !important;
            color: var(--onigiri-box-effect-fg, var(--fg)) !important;
        }
        
        /* Restaurant level progress bar styles */
        #onigiri-reviewer-header .restaurant-level-chip,
        #onigiri-overview-header .restaurant-level-chip,
        .overview-header .restaurant-level-chip {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-left: 0;
            padding: 4px 10px;
            border-radius: 999px;
            /* Same chrome tokens as a.onigiri-reviewer-button so the chip reads
               as one of the header buttons; only the pill radius differs. */
            background: var(--onigiri-box-effect-bg, var(--canvas-inset, rgba(247, 247, 247, 0.92)));
            backdrop-filter: blur(var(--onigiri-box-effect-blur, 0px));
            -webkit-backdrop-filter: blur(var(--onigiri-box-effect-blur, 0px));
            color: var(--onigiri-box-effect-fg, var(--fg));
            font-family: var(--font-main), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: var(--font-size-main, 13px);
            transition: background-color 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
            position: relative;
            overflow: hidden;
            border: var(--onigiri-box-effect-stroke, 1px) solid var(--onigiri-box-effect-border, rgba(128, 128, 128, 0.2));
            cursor: pointer;
            flex: 0 0 auto;
        }

        .night_mode #onigiri-reviewer-header .restaurant-level-chip,
        .night_mode #onigiri-overview-header .restaurant-level-chip,
        .night_mode .overview-header .restaurant-level-chip {
            background: var(--onigiri-box-effect-bg, var(--canvas-inset, rgba(42, 42, 42, 0.92)));
            border-color: var(--onigiri-box-effect-border, rgba(128, 128, 128, 0.2));
        }
        
        #onigiri-reviewer-header .restaurant-level-chip .rl-chip-level,
        #onigiri-overview-header .restaurant-level-chip .rl-chip-level,
        .overview-header .restaurant-level-chip .rl-chip-level {
            font-weight: 600;
            white-space: nowrap;
            color: inherit;
        }
        
        #onigiri-reviewer-header .restaurant-level-chip .rl-chip-progress,
        #onigiri-overview-header .restaurant-level-chip .rl-chip-progress,
        .overview-header .restaurant-level-chip .rl-chip-progress {
            width: 72px;
            height: 6px;
            border-radius: 999px;
            background: rgba(128, 128, 128, 0.28);
            overflow: hidden;
            box-shadow: inset 0 1px 3px rgba(0,0,0,0.12);
        }
        
        .night_mode #onigiri-reviewer-header .restaurant-level-chip .rl-chip-progress,
        .night_mode #onigiri-overview-header .restaurant-level-chip .rl-chip-progress,
        .night_mode .overview-header .restaurant-level-chip .rl-chip-progress {
            background: rgba(255, 255, 255, 0.16);
        }
        
        #onigiri-reviewer-header .restaurant-level-chip .rl-chip-progress-fill,
        #onigiri-overview-header .restaurant-level-chip .rl-chip-progress-fill,
        .overview-header .restaurant-level-chip .rl-chip-progress-fill {
            height: 100%;
            background: var(--reviewer-level-bar-bg, linear-gradient(90deg, #ffb347, #ff6b6b));
            border-radius: inherit;
            transition: width 0.3s ease;
            box-shadow: 0 0 10px rgba(255, 255, 255, 0.3);
        }
        
        #onigiri-reviewer-header .restaurant-level-chip:hover,
        #onigiri-overview-header .restaurant-level-chip:hover,
        .overview-header .restaurant-level-chip:hover {
            background: var(--onigiri-box-effect-bg, var(--canvas-inset, rgba(128, 128, 128, 0.25)));
            border-color: var(--onigiri-box-effect-border-hover, var(--onigiri-box-effect-border, rgba(128, 128, 128, 0.3)));
            transform: translateY(-1px);
        }
        
        #onigiri-reviewer-header .restaurant-level-chip:hover .rl-chip-progress-fill,
        #onigiri-overview-header .restaurant-level-chip:hover .rl-chip-progress-fill,
        .overview-header .restaurant-level-chip:hover .rl-chip-progress-fill {
            background: var(--reviewer-level-bar-hover-bg, linear-gradient(90deg, #ff9a3c, #ff5e62));
            box-shadow: 0 0 15px rgba(255, 107, 107, 0.4);
        }

    </style>
    """

    if not include_overview_class:
        css = css.replace("#onigiri-reviewer-header, .overview-header", "#onigiri-reviewer-header")
        css = css.replace(",\n        .overview-header a.onigiri-reviewer-button", "")
        css = css.replace(",\n        .night_mode .overview-header a.onigiri-reviewer-button", "")
        css = css.replace(",\n        .overview-header a.onigiri-reviewer-button:hover", "")
        css = css.replace(",\n        .overview-header .restaurant-level-chip", "")
        css = css.replace(",\n        .night_mode .overview-header .restaurant-level-chip", "")
        css = css.replace(",\n        .overview-header .restaurant-level-chip .rl-chip-level", "")
        css = css.replace(",\n        .overview-header .restaurant-level-chip .rl-chip-progress", "")
        css = css.replace(",\n        .night_mode .overview-header .restaurant-level-chip .rl-chip-progress", "")
        css = css.replace(",\n        .overview-header .restaurant-level-chip .rl-chip-progress-fill", "")
        css = css.replace(",\n        .overview-header .restaurant-level-chip:hover", "")
        css = css.replace(",\n        .overview-header .restaurant-level-chip:hover .rl-chip-progress-fill", "")

    # Inject theme color CSS if a theme is active
    if show_restaurant_chip:
        try:
            from .gamification import nook_level
            theme_color = nook_level.manager.get_current_theme_color()
        except Exception:
            theme_color = ""
        if isinstance(theme_color, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", theme_color):
            # Convert hex to RGB for shadow
            r = int(theme_color[1:3], 16)
            g = int(theme_color[3:5], 16)
            b = int(theme_color[5:7], 16)
            css += f"""
    <style id="onigiri-reviewer-theme-colors">
        .onigiri-reviewer-header-buttons .level-progress-bar {{
            background: {theme_color} !important;
            box-shadow: 0 0 10px rgba({r}, {g}, {b}, 0.3) !important;
        }}
    </style>
    """
    
    css += progress_css

    return html, css


def _reviewer_bottom_bar_height_px(conf=None):
    if conf is None:
        conf = config.get_config_readonly()
    try:
        height = int(conf.get("onigiri_reviewer_bar_height", 60))
    except (TypeError, ValueError):
        height = 60
    return max(20, min(300, height))


def _reviewer_background_viewport_height_px(bar_height=None):
    """Best-effort shared image canvas height for the reviewer and bottom bar."""
    if bar_height is None:
        bar_height = _reviewer_bottom_bar_height_px(config.get_config_readonly())

    candidates = []
    try:
        main_web = getattr(mw, "web", None)
        if main_web:
            candidates.append(main_web)
    except Exception:
        pass

    for widget in candidates:
        try:
            height = int(widget.height())
        except Exception:
            continue
        if height > bar_height:
            return height + bar_height

    try:
        window_height = int(mw.height())
    except Exception:
        window_height = 0
    if window_height > bar_height:
        return window_height

    return max(720, bar_height)


def _store_bottom_web_default_height(bottom_web):
    if hasattr(mw, "_onigiri_bottom_web_default_height"):
        return
    mw._onigiri_bottom_web_default_height = (
        bottom_web.minimumHeight(),
        bottom_web.maximumHeight(),
    )


def restore_bottom_web_height():
    bottom_web = getattr(mw, "bottomWeb", None)
    defaults = getattr(mw, "_onigiri_bottom_web_default_height", None)
    if not bottom_web or defaults is None:
        return
    min_height, max_height = defaults
    bottom_web.setMinimumHeight(min_height)
    bottom_web.setMaximumHeight(max_height)
    bottom_web.updateGeometry()


def sync_reviewer_background_viewport_height():
    bottom_web = getattr(mw, "bottomWeb", None)
    if not bottom_web:
        return
    height = _reviewer_background_viewport_height_px()
    try:
        bottom_web.eval(
            "document.documentElement.style.setProperty("
            "'--onigiri-reviewer-background-viewport-height', "
            f"'{height}px');"
        )
    except Exception:
        pass


def apply_reviewer_bottom_bar_height(conf=None):
    bottom_web = getattr(mw, "bottomWeb", None)
    if not bottom_web:
        return
    if conf is None:
        conf = config.get_config_readonly()
    _store_bottom_web_default_height(bottom_web)
    if conf.get("maxHide", False):
        bottom_web.setFixedHeight(0)
    else:
        bottom_web.setFixedHeight(_reviewer_bottom_bar_height_px(conf))
    bottom_web.updateGeometry()
    try:
        QTimer.singleShot(0, sync_reviewer_background_viewport_height)
        QTimer.singleShot(120, sync_reviewer_background_viewport_height)
    except Exception:
        pass


def _generate_outer_background_css(mode, light_color, dark_color, light_img_path, dark_img_path, blur_val, opacity_val, addon_path, bg_position, match_viewport=False):
    """Generate CSS for #outer element with ::before pseudo-element for background.
    This ensures buttons are not affected by opacity/blur."""
    addon_name = os.path.basename(addon_path)
    blur_px = blur_val * 0.2
    blur_bleed_px = math.ceil(blur_px * 3) if blur_px > 0 else 0
    opacity_float = opacity_val / 100.0
    bar_height = _reviewer_bottom_bar_height_px(config.get_config_readonly())
    viewport_height = _reviewer_background_viewport_height_px(bar_height)
    has_image_background = mode in ["image", "image_color"]
    document_light_color = "#000000" if has_image_background else light_color
    document_dark_color = "#000000" if has_image_background else dark_color
    
    # Base styling for #outer
    base_css = "<style id='onigiri-reviewer-bottom-bar-bg-style'>"
    base_css += f"""
        :root {{
            --onigiri-reviewer-bottom-bar-height: {bar_height}px;
            --onigiri-reviewer-background-viewport-height: {viewport_height}px;
            --onigiri-reviewer-background-blur-bleed: {blur_bleed_px}px;
        }}
        html, body {{
            margin: 0 !important;
            padding: 0 !important;
            width: 100% !important;
            min-width: 100% !important;
            height: var(--onigiri-reviewer-bottom-bar-height) !important;
            min-height: var(--onigiri-reviewer-bottom-bar-height) !important;
            max-height: var(--onigiri-reviewer-bottom-bar-height) !important;
            overflow: hidden !important;
            background-color: {document_light_color} !important;
        }}
        .night-mode body, body.nightMode {{
            background-color: {document_dark_color} !important;
        }}
        #outer {{
            position: relative;
            margin: 0 !important;
            height: var(--onigiri-reviewer-bottom-bar-height) !important;
            min-height: var(--onigiri-reviewer-bottom-bar-height) !important;
            max-height: var(--onigiri-reviewer-bottom-bar-height) !important;
            width: 100% !important;
            border: none !important;
            border-top: none !important;
            outline: none !important;
            overflow: hidden !important;
            box-sizing: border-box !important;
            background-clip: border-box !important;
        }}
        #outer > table,
        #outer > table > tbody,
        #outer > table tr,
        #outer > table td {{
            height: 100% !important;
            background: transparent !important;
            background-color: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
        }}
    """
    
    if mode == "color":
        # Solid color background - apply directly to #outer
        base_css += f"""
            #outer {{ background-color: {light_color} !important; }}
            .night-mode #outer {{ background-color: {dark_color} !important; }}
        """
    elif mode in ["image", "image_color"]:
        # Image background with ::before pseudo-element
        def get_img_url(img_path):
            if not img_path:
                return None
            if img_path.startswith("user_files/"):
                return f"/_addons/{addon_name}/{img_path}"
            else:
                return f"/_addons/{addon_name}/user_files/{img_path}"
        
        light_img_url = get_img_url(light_img_path)
        dark_img_url = get_img_url(dark_img_path) if dark_img_path else light_img_url
        
        if mode == "image_color":
            # Solid color as base layer on #outer
            base_css += f"""
                #outer {{ background-color: {light_color} !important; }}
                .night-mode #outer {{ background-color: {dark_color} !important; }}
            """
        else:
            # No color, transparent background
            base_css += "#outer { background: transparent !important; }"
        
        if light_img_url or dark_img_url:
            # Add ::before pseudo-element for image on top of the color
            # Using z-index: 0 so it's above the background but below content
            # Apply slight scale even with no blur to prevent edge artifacts
            if match_viewport:
                scale_factor = 1.0 + (blur_px / 50.0) if blur_px > 0 else 1.0
                position_css = """
                    top: auto;
                    bottom: calc(-1 * var(--onigiri-reviewer-background-blur-bleed));
                    left: 50%;
                    width: 100vw;
                    height: calc(var(--onigiri-reviewer-background-viewport-height) + var(--onigiri-reviewer-background-blur-bleed));
                    transform-origin: center bottom;
                    transform: translateX(-50%) scale({scale_factor});
                    background-size: cover;
                    background-position: center;
                """.format(scale_factor=scale_factor)
            else:
                scale_factor = max(1.02, 1.0 + (blur_px / 50.0)) if blur_px > 0 else 1.02
                position_css = """
                    top: 0; left: 0;
                    width: 100%; height: 100%;
                    transform: scale({scale_factor});
                    background-size: cover;
                    background-position: {bg_position};
                """.format(scale_factor=scale_factor, bg_position=bg_position)
            base_img_url = light_img_url or "none"
            base_css += f"""
                #outer::before {{
                    content: '';
                    position: absolute;
                    {position_css}
                    background-image: url('{base_img_url}');
                    background-repeat: no-repeat;
                    filter: blur({blur_px}px);
                    opacity: {opacity_float};
                    z-index: 0;
                    pointer-events: none;
                    border: none !important;
                    outline: none !important;
                }}
                #outer > * {{
                    position: relative;
                    z-index: 1;
                }}
            """

            if dark_img_url and dark_img_url != light_img_url:
                base_css += f"""
                    .night-mode #outer::before {{
                        background-image: url('{dark_img_url}');
                    }}
                """

    base_css += "</style>"
    return base_css

def generate_reviewer_bottom_bar_background_css(addon_path: str) -> str:
    """Generates CSS for the reviewer's bottom bar background."""
    conf = config.get_config_readonly()
    # FIX: Read from conf, not mw.col.conf
    bar_mode = conf.get("onigiri_reviewer_bottom_bar_bg_mode", "match_reviewer_bg")

    bg_position = "center bottom"

    css = ""
    # We don't use 'selector' variable effectively in the original code's structure for this function, 
    # but we'll keep the structure clean.

    # Helper to get main window settings
    def get_main_bg_settings():
        # Main settings are in mw.col.conf
        main_mode = mw.col.conf.get("modern_menu_background_mode", "color")
        light_c = mw.col.conf.get("modern_menu_bg_color_light", "#FFFFFF")
        dark_c = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
        
        # Image handling for main
        img_mode = mw.col.conf.get("modern_menu_background_image_mode", "single")
        if img_mode == "separate":
            l_img = mw.col.conf.get("modern_menu_background_image_light", "")
            # If separate mode but no light image, fallback might be needed or it's just empty
            # But usually main bg logic handles this.
            # For main bg, the key 'modern_menu_background_image' is used for single mode.
        else:
            l_img = mw.col.conf.get("modern_menu_background_image", "")
        
        # For dark image in separate mode
        if img_mode == "separate":
            d_img = mw.col.conf.get("modern_menu_background_image_dark", "")
        else:
            d_img = l_img

        # Path adjustment for main images
        # Main images are in user_files/main_bg/
        l_img_path = f"user_files/main_bg/{l_img}" if l_img else ""
        d_img_path = f"user_files/main_bg/{d_img}" if d_img else ""

        return main_mode, light_c, dark_c, l_img_path, d_img_path

    # Helper to get reviewer settings
    def get_reviewer_bg_settings():
        # Reviewer settings are in conf
        rev_mode = conf.get("onigiri_reviewer_bg_mode", "main")
        
        if rev_mode == "main":
            return get_main_bg_settings()
            
        light_c = conf.get("onigiri_reviewer_bg_light_color", "#FFFFFF")
        dark_c = conf.get("onigiri_reviewer_bg_dark_color", "#2C2C2C")
        
        img_mode = conf.get("onigiri_reviewer_bg_image_mode", "single")
        if img_mode == "separate":
            l_img = conf.get("onigiri_reviewer_bg_image_light", "")
            d_img = conf.get("onigiri_reviewer_bg_image_dark", "")
        else:
            l_img = conf.get("onigiri_reviewer_bg_image", "") # Fallback or same key? Settings saves to 'image' and 'image_light'/'image_dark'
            # Let's check settings.py saving logic. 
            # It saves to 'onigiri_reviewer_bg_image' for single, and 'onigiri_reviewer_bg_image_light'/'dark' for separate.
            # But let's be safe and check specific keys.
            if not l_img:
                 l_img = conf.get("onigiri_reviewer_bg_image_light", "")
            d_img = l_img

        # Reviewer images are in user_files/reviewer_bg/
        l_img_path = f"user_files/reviewer_bg/{l_img}" if l_img else ""
        d_img_path = f"user_files/reviewer_bg/{d_img}" if d_img else ""
        
        # Determine the actual mode based on what's configured
        # If rev_mode is "color", return "color"
        # If rev_mode is "image_color", check if images exist to determine the actual mode
        actual_mode = rev_mode
        if rev_mode == "image_color":
            # If images are configured, use "image_color", otherwise fall back to "color"
            if l_img_path or d_img_path:
                actual_mode = "image_color"
            else:
                actual_mode = "color"
        
        return actual_mode, light_c, dark_c, l_img_path, d_img_path

    def get_reviewer_bg_effects():
        rev_mode = conf.get("onigiri_reviewer_bg_mode", "main")
        if rev_mode == "main":
            return (
                conf.get("onigiri_reviewer_bg_main_blur", 0),
                conf.get("onigiri_reviewer_bg_main_opacity", 100),
            )
        if rev_mode in {"image_color", "slideshow"}:
            return (
                conf.get("onigiri_reviewer_bg_blur", 0),
                conf.get("onigiri_reviewer_bg_opacity", 100),
            )
        return 0, 100

    def get_overview_bg_settings():
        overview_mode = conf.get("onigiri_overview_bg_mode", "main")
        if overview_mode == "main":
            return get_main_bg_settings()

        light_c = conf.get("onigiri_overview_bg_light_color", "#FFFFFF")
        dark_c = conf.get("onigiri_overview_bg_dark_color", "#2C2C2C")
        img_mode = conf.get("onigiri_overview_bg_image_theme_mode", conf.get("onigiri_overview_bg_image_mode", "separate"))
        if img_mode == "separate":
            l_img = conf.get("onigiri_overview_bg_image_light", "")
            d_img = conf.get("onigiri_overview_bg_image_dark", "")
        else:
            l_img = conf.get("onigiri_overview_bg_image", "")
            d_img = l_img

        l_img_path = f"user_files/main_bg/{l_img}" if l_img else ""
        d_img_path = f"user_files/main_bg/{d_img}" if d_img else ""
        actual_mode = overview_mode
        if overview_mode == "image_color" and not (l_img_path or d_img_path):
            actual_mode = "color"
        return actual_mode, light_c, dark_c, l_img_path, d_img_path

    def get_overview_bg_effects():
        overview_mode = conf.get("onigiri_overview_bg_mode", "main")
        if overview_mode == "main":
            return (
                conf.get("onigiri_overview_bg_main_blur", 0),
                conf.get("onigiri_overview_bg_main_opacity", 100),
            )
        if overview_mode in {"image_color", "slideshow"}:
            return (
                conf.get("onigiri_overview_bg_blur", 0),
                conf.get("onigiri_overview_bg_opacity", 100),
            )
        return 0, 100


    if bar_mode == "main":
        # Match Main Background DIRECTLY
        mode, light_color, dark_color, light_img, dark_img = get_main_bg_settings()
        
        # Use bottom bar specific blur and opacity settings for "Match Main"
        blur_val = conf.get("onigiri_reviewer_bottom_bar_match_main_blur", 5)
        opacity_val = conf.get("onigiri_reviewer_bottom_bar_match_main_opacity", 90)

        css += _generate_outer_background_css(mode, light_color, dark_color, light_img, dark_img, blur_val, opacity_val, addon_path, bg_position, match_viewport=True)

    elif bar_mode == "match_overview_bg":
        mode, light_color, dark_color, light_img, dark_img = get_overview_bg_settings()
        blur_val, opacity_val = get_overview_bg_effects()

        css += _generate_outer_background_css(mode, light_color, dark_color, light_img, dark_img, blur_val, opacity_val, addon_path, bg_position, match_viewport=True)

    elif bar_mode == "match_reviewer_bg":
        # Match Reviewer Background (which might itself match Main)
        mode, light_color, dark_color, light_img, dark_img = get_reviewer_bg_settings()
        blur_val, opacity_val = get_reviewer_bg_effects()

        css += _generate_outer_background_css(mode, light_color, dark_color, light_img, dark_img, blur_val, opacity_val, addon_path, bg_position, match_viewport=True)

    else: # Custom settings for the bar
        mode = bar_mode # "color" or "image_color" (mapped from radio buttons)
        
        # FIX: Read from conf, not mw.col.conf
        light_color = conf.get("onigiri_reviewer_bottom_bar_bg_light_color", "#FFFFFF")
        dark_color = conf.get("onigiri_reviewer_bottom_bar_bg_dark_color", "#2C2C2C")
        
        img_filename = conf.get("onigiri_reviewer_bottom_bar_bg_image", "")
        img = f"user_files/reviewer_bar_bg/{img_filename}" if img_filename else ""
        
        blur_val = conf.get("onigiri_reviewer_bottom_bar_bg_blur", 0)
        opacity_val = conf.get("onigiri_reviewer_bottom_bar_bg_opacity", 100)

        # Generate CSS for #outer with ::before pseudo-element for background
        css += _generate_outer_background_css(mode, light_color, dark_color, img, img, blur_val, opacity_val, addon_path, bg_position)

    return css

def generate_profile_page_background_css():
    """Generates background CSS for the profile page."""
    try:
        if mw and mw.col and mw.col.conf:
            mode = mw.col.conf.get("onigiri_profile_page_bg_mode", "color")
            if mode == "gradient":
                light1 = mw.col.conf.get("onigiri_profile_page_bg_light_color1", "#F5F5F5")
                light2 = mw.col.conf.get("onigiri_profile_page_bg_light_color2", "#E0E0E0")
                dark1 = mw.col.conf.get("onigiri_profile_page_bg_dark_color1", "#2C2C2C")
                dark2 = mw.col.conf.get("onigiri_profile_page_bg_dark_color2", "#1A1A1A")
                light_bg = f"linear-gradient(135deg, {light1}, {light2})"
                dark_bg = f"linear-gradient(135deg, {dark1}, {dark2})"
            else:
                light1 = mw.col.conf.get("onigiri_profile_page_bg_light_color1", "#F5F5F5")
                dark1 = mw.col.conf.get("onigiri_profile_page_bg_dark_color1", "#2C2C2C")
                light_bg = light1
                dark_bg = dark1
        else:
            light_bg = "#F5F5F5"
            dark_bg = "#2C2C2C"

        return f"""
        <style>
            body {{
                background: {light_bg} !important;
                background-attachment: fixed !important;
            }}
            body.night-mode {{
                background: {dark_bg} !important;
                background-attachment: fixed !important;
            }}
        </style>
        """
    except Exception as e:
        print(f"Error generating profile page background css: {e}")
        return ""

def generate_profile_bar_fix_css():
    """Generates compatibility CSS for the current profile bar layout matching preview pill style."""
    return """
<style id="onigiri-profile-bar-fix">
.profile-bar {
    height: 64px !important;
    border-radius: 32px !important;
    position: relative !important;
    display: flex !important;
    align-items: center !important;
    padding: 0 12px !important;
    gap: 14px !important;
    overflow: hidden !important;
    box-shadow: none !important;
    box-sizing: border-box !important;
    width: var(--onigiri-deck-header-width, 100%) !important;
    max-width: 100% !important;
}

.profile-bar .profile-content,
.profile-bar .profile-content-main {
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    min-width: 0 !important;
    gap: 14px !important;
}

.profile-bar .restaurant-level-chip {
    margin-left: auto !important;
}

.profile-bar .profile-pic,
.profile-bar .profile-pic-placeholder,
.profile-bar .profile-pic-generated {
    width: 44px !important;
    height: 44px !important;
    border-radius: 50% !important;
    flex: 0 0 44px !important;
    margin: 0 !important;
    object-fit: cover !important;
}

.profile-bar .profile-name {
    font-size: 16px !important;
    font-weight: 600 !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}
</style>
"""

def generate_icon_size_css():
    """
    Generates CSS to control the size of various icons based on user settings.
    """
    # These keys correspond to the settings in the "Icons" tab.
    icon_configs = {
        "deck_folder": {
            "selector": "a.deck::before",
            "default": 18,
        },
        "action_button": {
            "selector": ".menu-item .icon, .add-button-dashed .icon",
            "default": 16,
        },
        "collapse": {
            "selector": "a.collapse, span.collapse",
            "default": 16,
        },
        "options_gear": {
            "selector": "td.opts a",
            "default": 16,
        },
    }

    css_rules = []
    action_button_size = icon_configs["action_button"]["default"]
    for key, config in icon_configs.items():
        config_key = f"modern_menu_icon_size_{key}"
        size = mw.col.conf.get(config_key, config["default"])
        if key == "action_button":
            action_button_size = size
        selector = config["selector"]
        css_rules.append(f"{selector} {{ width: {size}px; height: {size}px; }}")

    # Exposed as a CSS variable so the collapsed sidebar-toolbar mode (which
    # renders Action Buttons as .action-btn/.action-icon via injector.js,
    # separate from the .menu-item markup above) can also size off it.
    css_rules.append(f":root {{ --onigiri-action-icon-size: {action_button_size}px; }}")

    # Count badge (deck new/learn/review pill) size. The base rule in menu.css
    # expresses height/min-width/padding in em relative to the badge font-size,
    # so scaling only the font-size grows the whole pill proportionally.
    badge_size_key = mw.col.conf.get("modern_menu_count_badge_size", "small")
    if badge_size_key == "custom":
        # Custom stores an absolute badge font-size in px.
        badge_font = f"{mw.col.conf.get('modern_menu_count_badge_size_custom_px', 16)}px"
    else:
        badge_em = {"small": 0.75, "medium": 0.98, "big": 1.2}.get(badge_size_key, 0.75)
        badge_font = f"{badge_em}em"
    css_rules.append(
        "tr.deck .new-count-bubble, tr.deck .review-count-bubble, "
        f"tr.deck .learn-count-bubble {{ font-size: {badge_font} !important; }}"
    )

    return f"<style id='modern-menu-icon-size-styles'>{''.join(css_rules)}</style>"

_ICON_CSS_URI_CACHE = {}


def generate_icon_css(addon_package, conf):
    all_icon_selectors = {
        "options": "td.opts a", "folder": "tr.is-folder a.deck::before, .onigiri-drag-preview.is-folder a.deck::before",
        "deck": "tr.is-deck a.deck::before, .onigiri-drag-preview.is-deck a.deck::before", "subdeck": "tr.is-subdeck a.deck::before, .onigiri-drag-preview.is-subdeck a.deck::before",
        "filtered_deck": "tr.is-filtered a.deck::before, .onigiri-drag-preview.is-filtered a.deck::before", "add": ".action-add .icon",
        "browse": ".action-browse .icon", "stats": ".action-stats .icon", "sync": ".action-sync .icon",
        "settings": ".action-settings .icon", "more": ".action-more .icon",
        "get_shared": ".action-get-shared .icon", "create_deck": ".action-create-deck .icon",
        "import_file": ".action-import-file .icon",
        "retention_star": ".star",
        "focus": ".deck-focus-btn .icon",
        "edit": ".deck-edit-btn .icon",
    }
    
    addon_dir = os.path.dirname(__file__)

    def system_icon_path(filename, users_only=False):
        filename = os.path.basename(str(filename or ""))
        folders = ["available_for_users"] if users_only else ["unavailable_for_users", "available_for_users"]
        for folder in folders:
            path = os.path.join(addon_dir, "system_files", "system_icons", folder, filename)
            if os.path.exists(path):
                return path
        return ""

    def user_icon_path(filename):
        filename = os.path.basename(str(filename or ""))
        for folder in ("custom_deck_icons", "icons"):
            path = os.path.join(addon_dir, "user_files", folder, filename)
            if os.path.exists(path):
                return path
        return ""

    def get_data_uri(path):
        # generate_icon_css runs on every deck browser/overview render and asks
        # for the same icon files each time; cache on the file's identity so an
        # edited icon still refreshes.
        if not path:
            return ""
        try:
            stat = os.stat(path)
        except OSError:
            return ""
        key = (stat.st_mtime_ns, stat.st_size)
        cached = _ICON_CSS_URI_CACHE.get(path)
        if cached is not None and cached[0] == key:
            return cached[1]
        try:
            with open(path, "rb") as f:
                data = f.read()
                b64 = base64.b64encode(data).decode("utf-8")
                # Detect file type for correct MIME type
                if path.lower().endswith(".png"):
                    uri = f"url('data:image/png;base64,{b64}')"
                else:
                    # Default to SVG
                    uri = f"url('data:image/svg+xml;base64,{b64}')"
        except Exception as e:
            print(f"Onigiri: Error loading icon {path}: {e}")
            return ""
        if len(_ICON_CSS_URI_CACHE) > 256:
            _ICON_CSS_URI_CACHE.clear()
        _ICON_CSS_URI_CACHE[path] = (key, uri)
        return uri

    hide_defaults = mw.col.conf.get("modern_menu_hide_default_icons", False)

    css_rules = []
    for key, selector in all_icon_selectors.items():
        # Check global hide default setting
        if hide_defaults and key in ["folder", "subdeck", "deck", "filtered_deck"]:
             # If "Hide Default" is ON, we hide the default icons.
             # However, we must NOT 'continue' here because we still want the mask-image logic to be generated
             # just in case a custom icon is NOT set for a specific deck, so it defaults to hidden.
             # But WAIT: if we hide it with display:none, the mask-image doesn't matter.
             # AND if we have a custom icon, the later loop creates a specific rule for that deck ID.
             # That specific rule will override the mask-image/content.
             # BUT does it override display:none? 
             # Only if we explicitly add display:inline-block to the custom rule!
             css_rules.append(f"{selector} {{ display: none !important; }}")
             
             # We still generate the default icon URL logic below so that if the user toggles it back, or if there's some weird state, it's there?
             # Actually no, if display:none is set, it's hidden.
             # We can skip the rest of the logic for this iteration if we want to save bytes, 
             # OR we can just let it run. Let's just let it run but ensure display:none is applied.
             # BUT we need to be careful not to conflict with the specific hide toggles.
             pass

        if key == "folder" and mw.col.conf.get("modern_menu_hide_folder_icon", False):
            css_rules.append(f"{selector} {{ display: none !important; }}")
            continue
        if key == "subdeck" and mw.col.conf.get("modern_menu_hide_subdeck_icon", False):
            css_rules.append(f"{selector} {{ display: none !important; }}")
            continue
        if key == "deck" and mw.col.conf.get("modern_menu_hide_deck_icon", False):
            css_rules.append(f"{selector} {{ display: none !important; }}")
            continue
        if key == "filtered_deck" and mw.col.conf.get("modern_menu_hide_filtered_deck_icon", False):
            css_rules.append(f"{selector} {{ display: none !important; }}")
            continue

        filename = mw.col.conf.get(f"modern_menu_icon_{key}", "")
        url = ""
        if filename:
            if key == "retention_star" and (filename.startswith("emoji:") or (len(filename) <= 8 and "." not in filename and not filename.startswith("system:"))):
                emoji_char = filename[len("emoji:"):] if filename.startswith("emoji:") else filename
                emoji_css = json.dumps(emoji_char, ensure_ascii=False)
                css_rules.append(f"""
                {selector} {{
                    background-color: transparent !important;
                    color: var(--star-color);
                    mask-image: none !important;
                    -webkit-mask-image: none !important;
                    width: 20px;
                    height: 20px;
                    line-height: 20px;
                    text-align: center;
                    font-size: 18px;
                }}
                {selector}::before {{
                    content: {emoji_css};
                }}
                {selector}.empty {{
                    color: var(--empty-star-color);
                }}
                """)
                continue
            if filename.startswith("system:"):
                path = system_icon_path(filename[len("system:"):], users_only=True)
            else:
                path = user_icon_path(filename)
            url = get_data_uri(path)
        
        if not url: # Fallback to system
            system_icon_name = {
                "create_deck": "add-deck",
                "filtered_deck": "filtered-deck",
                "retention_star": "star",
                "reset": "sync",
            }.get(key, key)
            path = system_icon_path(f"{system_icon_name}.svg")
            url = get_data_uri(path)
        
        if url:
            css_rules.append(f"{selector} {{ mask-image: {url}; -webkit-mask-image: {url}; }}")

    # --- Custom Deck Icons ---
    custom_deck_icons = config.get_collection_config("onigiri_custom_deck_icons", {})
    for did, data in custom_deck_icons.items():
        icon_file = data.get("icon")
        color = data.get("color")
        # Absent means "linked to the light colour" (entries saved before the
        # light/dark split only ever wrote "color").
        color_dark = data.get("colorDark", color)

        if icon_file:
                is_emoji = icon_file.startswith("emoji:") or (len(icon_file) <= 8 and "." not in icon_file)
                emoji_char = icon_file[len("emoji:"):] if icon_file.startswith("emoji:") else icon_file
                is_system_icon = icon_file.startswith("system:")

                if is_emoji:
                    emoji_asset = asset_for_emoji(emoji_char)
                    if emoji_asset:
                        emoji_url = json.dumps(f"/_addons/{addon_package}/system_files/emojis/{emoji_asset}")
                        css_rules.append(f"""
                        tr[data-did="{did}"] a.deck::before,
                        .onigiri-drag-preview[data-did="{did}"] a.deck::before {{
                            content: '' !important;
                            mask-image: none !important;
                            -webkit-mask-image: none !important;
                            background-color: transparent !important;
                            background-image: url({emoji_url}) !important;
                            background-size: contain !important;
                            background-position: center !important;
                            background-repeat: no-repeat !important;
                            display: inline-block !important;
                            width: 20px !important; 
                            height: 20px !important;
                            margin-right: 5px !important;
                            overflow: hidden !important;
                        }}
                        """)
                    else:
                        emoji_css = json.dumps(emoji_char, ensure_ascii=False)
                        css_rules.append(f"""
                        tr[data-did="{did}"] a.deck::before,
                        .onigiri-drag-preview[data-did="{did}"] a.deck::before {{
                            content: {emoji_css} !important;
                            mask-image: none !important;
                            -webkit-mask-image: none !important;
                            background-color: transparent !important;
                            background-image: none !important;
                            display: inline-block !important;
                            text-align: center;
                            font-size: 14px; 
                            width: 20px !important; 
                            height: 20px !important;
                            line-height: 20px !important;
                            margin-right: 5px !important;
                            overflow: hidden !important;
                        }}
                        """)
                else:
                    icon_name = icon_file[len("system:"):] if is_system_icon else icon_file
                    path = system_icon_path(icon_name, users_only=True) if is_system_icon else user_icon_path(icon_name)
                    
                    # Check for PNG images
                    is_png = icon_name.strip().lower().endswith(".png")
                    
                    if is_png:
                        url = get_data_uri(path)
                        if url:
                             # PNG rendering style (no mask, original colors)
                            css_rules.append(f"""
                            tr[data-did="{did}"] a.deck::before,
                            .onigiri-drag-preview[data-did="{did}"] a.deck::before {{
                                content: '';
                                background-image: {url} !important;
                                -webkit-mask-image: none !important;
                                mask-image: none !important;
                                background-color: transparent !important;
                                background-size: contain;
                                background-repeat: no-repeat;
                                background-position: center;
                                display: inline-block !important;
                                width: 20px !important;
                                height: 20px !important;
                                margin-right: 5px !important;
                            }}
                            """)
                    else:
                        # SVG rendering style (mask for colorization)
                        url = get_data_uri(path)
                        if url:
                            # No explicit colour: fall back to the shared
                            # --icon-color so the icon tracks the theme like
                            # every other deck icon SVG.
                            icon_color_css = color if color else "var(--icon-color, #888888)"
                            icon_color_dark_css = color_dark if color_dark else "var(--icon-color, #888888)"
                            selectors = (
                                f'tr[data-did="{did}"] a.deck::before,\n'
                                f'                            .onigiri-drag-preview[data-did="{did}"] a.deck::before'
                            )
                            css_rules.append(f"""
                            {selectors} {{
                                mask-image: {url} !important;
                                -webkit-mask-image: {url} !important;
                                background-color: {icon_color_css} !important;
                                display: inline-block !important;
                                mask-size: contain;
                                -webkit-mask-size: contain;
                                mask-repeat: no-repeat;
                                -webkit-mask-repeat: no-repeat;
                                mask-position: center;
                                -webkit-mask-position: center;
                                width: 20px !important;
                                height: 20px !important;
                                margin-right: 5px !important;
                            }}
                            """)
                            # Only needed when the dark slot was actually set to
                            # something else — most decks stay linked and never
                            # emit this second rule.
                            if icon_color_dark_css != icon_color_css:
                                css_rules.append(f"""
                                .night-mode {selectors} {{
                                    background-color: {icon_color_dark_css} !important;
                                }}
                                """)


    # --- Get URLs for collapse icons ---
    closed_icon_file = mw.col.conf.get("modern_menu_icon_collapse_closed", "")
    open_icon_file = mw.col.conf.get("modern_menu_icon_collapse_open", "")

    def configured_icon_path(icon_file):
        if not icon_file:
            return ""
        icon_file = str(icon_file)
        if icon_file.startswith("system:"):
            return system_icon_path(icon_file[len("system:"):], users_only=True)
        return user_icon_path(icon_file)
    
    closed_icon_url = ""
    if closed_icon_file:
        closed_icon_url = get_data_uri(configured_icon_path(closed_icon_file))
    if not closed_icon_url:
        closed_icon_url = get_data_uri(system_icon_path("right.svg"))

    open_icon_url = ""
    if open_icon_file:
        open_icon_url = get_data_uri(configured_icon_path(open_icon_file))
    if not open_icon_url:
        open_icon_url = get_data_uri(system_icon_path("down.svg"))
        
    # Create a list of selectors for the background color, EXCLUDING the star and filtered deck (filtered has own color)
    bg_color_selectors = {k: v for k, v in all_icon_selectors.items() if k not in ["retention_star", "filtered_deck"]}
    bg_selectors_str = ", ".join(bg_color_selectors.values())

    # --- Per-icon colours -------------------------------------------------------
    # Each icon can carry its own tint, set inside its own picker in Settings
    # (Sidebar -> Decks / Action Buttons). Unset falls through to the palette
    # rules above (--icon-color, and --icon-color-filtered for filtered decks),
    # which is why these are emitted last and marked !important: the filtered
    # and collapse rules they have to beat are !important themselves.
    per_icon_color_rules = []
    for key, selector in all_icon_selectors.items():
        if key == "retention_star":
            continue
        color = mw.col.conf.get(f"modern_menu_icon_color_{key}", "")
        if color:
            per_icon_color_rules.append(
                f"{selector} {{ background-color: {color} !important; }}"
            )
    for state, key in (("closed", "collapse_closed"), ("open", "collapse_open")):
        color = mw.col.conf.get(f"modern_menu_icon_color_{key}", "")
        if color:
            per_icon_color_rules.append(
                f"a.collapse.state-{state}::before {{ background-color: {color} !important; }}"
            )
    per_icon_color_css = "\n".join(per_icon_color_rules)

    return f"""
<style id="modern-menu-icon-styles">
    /* Hide the original '+' or '-' text from the link. */
    a.collapse {{
        font-size: 0 !important;
    }}

    /* Create the icon using a pseudo-element on the link. */
    a.collapse::before {{
        content: '';
        display: inline-block;
        width: 100%;
        height: 100%;
        /* START FIX: Set background to transparent by default to prevent flash */
        background-color: transparent;
        transition: background-color 0.1s ease;
        /* END FIX */
        mask-size: contain;
        mask-repeat: no-repeat;
        mask-position: center;
        -webkit-mask-size: contain;
        -webkit-mask-repeat: no-repeat;
        -webkit-mask-position: center;
    }}

    /* Apply the correct SVG icon and background color only when the state class is present. */
    a.collapse.state-closed::before {{
        mask-image: {closed_icon_url};
        -webkit-mask-image: {closed_icon_url};
        background-color: var(--icon-color, #888888);
        /* END FIX */
    }}
    a.collapse.state-open::before {{
        mask-image: {open_icon_url};
        -webkit-mask-image: {open_icon_url};
        /* START FIX: Apply background color here */
        background-color: var(--icon-color, #888888);
        /* END FIX */
    }}

    /* Filtered Deck Specific Color */
    tr.is-filtered a.deck::before,
    .onigiri-drag-preview.is-filtered a.deck::before {{
        background-color: #0a84ff !important; /* Anki Blue */
        mask-size: contain;
        -webkit-mask-size: contain;
        mask-repeat: no-repeat;
        -webkit-mask-repeat: no-repeat;
        mask-position: center;
        -webkit-mask-position: center;
        display: inline-block;
    }}
    .night-mode tr.is-filtered a.deck::before,
    .night-mode .onigiri-drag-preview.is-filtered a.deck::before {{
        background-color: #64d2ff !important; /* Light Blue for Dark Mode */
    }}

    /* General rules for other icons (Unchanged) */
    {bg_selectors_str} {{
        background-color: var(--icon-color, #888888);
        mask-size: contain;
        mask-repeat: no-repeat;
        mask-position: center;
        -webkit-mask-size: contain;
        -webkit-mask-repeat: no-repeat;
        -webkit-mask-position: center;
        display: inline-block;
    }}
    
    /* FIX: Layout and Spacing Overrides requested by user */
    .deck-info {{
        display: flex !important;
        align-items: center !important;
        gap: 0 !important;
        flex: 1 1 0 !important;
        min-width: 0 !important;
        width: auto !important;
    }}
    
    .deck-table a.deck {{
        padding: 0 !important;
        margin-left: 0 !important;
        display: flex !important;
        align-items: center !important;
        gap: 6px !important;
        flex: 1 1 0 !important;
        min-width: 0 !important;
        max-width: 100% !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        white-space: nowrap !important;
    }}

    .deck-table a.deck .deck-name {{
        flex: 1 1 0 !important;
        min-width: 0 !important;
        overflow: hidden !important;
        text-overflow: clip !important;
        white-space: nowrap !important;
        display: block !important;
        -webkit-mask-image: var(--onigiri-name-fade) !important;
        mask-image: var(--onigiri-name-fade) !important;
    }}

    .deck-table a.deck .deck-mark-dot {{
        flex-shrink: 0 !important;
    }}
    
    /* Ensure indentation span works as expected */
    .deck-info > span:first-child {{
        display: inline-flex !important;
        align-items: center !important;
        flex-shrink: 0 !important;
    }}
    /* END FIX */    
    /* Individual mask images for other icons (Unchanged) */
    {''.join(css_rules)}

    /* Per-icon tints, last so they win over the palette defaults above. */
    {per_icon_color_css}
</style>
"""

def generate_conditional_css(conf):
	styles = []
	styles.append("""
        body.deck-browser .sidebar-left.deck-focus-mode .sidebar-expanded-content > #deck-list-header {
            display: flex !important;
        }
    """)
	if conf.get("hideTodaysStats", False):
		styles.append(".stats-grid { display: none !important; }")
	if conf.get("hideDeckCounts", False):
		styles.append(".deck-counts .zero { display: none !important; }")
	if conf.get("hideAllDeckCounts", False):
		styles.append(".deck-counts { display: none !important; }")
	# -- The old, unreliable CSS rule for the header and bottom bar has been removed. --
	if not styles: return ""
	return f"<style id='modern-menu-conditional-styles'>{' '.join(styles)}</style>"

def generate_font_css(addon_package):
    """Generates @font-face rules and CSS variables for selected fonts."""
    main_font_key = mw.col.conf.get("onigiri_font_main", "system")
    subtle_font_key = mw.col.conf.get("onigiri_font_subtle", "system")
    small_title_font_key = mw.col.conf.get("onigiri_font_small_title", "system")
    # Profile bar username font (set on the Profile settings page).
    profile_name_font_key = mw.col.conf.get("modern_menu_profile_name_font", "system") or "system"
    # Stats Title widget font ("sync" == follow the Titles font above).
    stats_title_font_key = mw.col.conf.get("modern_menu_statsTitleFont", "sync") or "sync"
    # Today's Stats cards font ("sync" == inherit Small Titles like before).
    try:
        from . import config as _onigiri_config
        _sw_style = _onigiri_config.get_config_readonly().get("stats_widgets_style", {})
        stats_widget_font_key = (_sw_style or {}).get("font", "sync") or "sync"
    except Exception:
        stats_widget_font_key = "sync"

    # --- NEW: Font Sizes ---
    main_font_size = mw.col.conf.get("onigiri_font_size_main", 14)
    subtle_font_size = mw.col.conf.get("onigiri_font_size_subtle", 20)
    small_title_font_size = mw.col.conf.get("onigiri_font_size_small_title", 15)
    # -----------------------

    # Avoid scanning/loading user fonts unless a selected key actually needs it.
    from .fonts import FONTS, get_all_fonts, poppins_font_face_css

    # "sync" is a mode, not a font, so it never takes part in font lookups.
    extra_font_keys = {profile_name_font_key, "silkscreen"}
    if stats_title_font_key != "sync":
        extra_font_keys.add(stats_title_font_key)
    if stats_widget_font_key != "sync":
        extra_font_keys.add(stats_widget_font_key)

    selected_font_keys = {main_font_key, subtle_font_key, small_title_font_key} | extra_font_keys
    if selected_font_keys.issubset(FONTS.keys()):
        all_fonts = FONTS
    else:
        all_fonts = get_all_fonts(os.path.dirname(__file__))
    main_font_info = all_fonts.get(main_font_key)
    subtle_font_info = all_fonts.get(subtle_font_key)
    small_title_font_info = all_fonts.get(small_title_font_key)
    # <<< END MODIFIED >>>

    if not main_font_info or not subtle_font_info or not small_title_font_info:
        return ""

    # Poppins is the add-on default (the "system" key resolves to it), so its
    # @font-face must always be present regardless of which keys are selected.
    font_faces = poppins_font_face_css(addon_package)
    # Use a set to avoid generating duplicate @font-face rules
    fonts_to_load = {main_font_key, subtle_font_key, small_title_font_key} | extra_font_keys
    
    # <<< MODIFIED: Loop through all fonts to generate @font-face rules >>>
    for font_key in fonts_to_load:
        font_info = all_fonts.get(font_key)
        if font_info and font_info.get("file"):
            # Handle different paths for user vs system fonts
            if font_info.get("user"):
                font_url = f"/_addons/{addon_package}/user_files/fonts/{font_info['file']}"
            else:
                font_url = f"/_addons/{addon_package}/system_files/fonts/system_fonts/{font_info['file']}"
            
            font_faces += f"""
                @font-face {{
                    font-family: '{font_info['family']}';
                    src: url('{font_url}');
                }}
            """
    # <<< END MODIFIED >>>

    # Profile bar username font — only override when a non-system font is chosen,
    # so the default keeps inheriting the main menu font.
    # Stats Title widget — only override when the user picked a dedicated font;
    # "sync" leaves it inheriting --font-subtle like every other title.
    stats_title_font_css = ""
    stats_title_font_info = all_fonts.get(stats_title_font_key)
    if stats_title_font_key != "sync" and stats_title_font_info and stats_title_font_info.get("family"):
        family = stats_title_font_info["family"]
        if stats_title_font_key == "system":
            # The system entry is already a full CSS stack, not a bare family name.
            font_stack = family
        else:
            font_stack = (
                f"'{family}', -apple-system, BlinkMacSystemFont, \"Segoe UI\","
                " Roboto, Helvetica, Arial, sans-serif"
            )
        stats_title_font_css = f".onigiri-widget-title {{ font-family: {font_stack} !important; }}"

    # Today's Stats cards — a dedicated font key overrides both the label and
    # the value; "sync" leaves them on --font-small-title as before.
    stats_widget_font_css = ""
    stats_widget_font_info = all_fonts.get(stats_widget_font_key)
    if stats_widget_font_key != "sync" and stats_widget_font_info and stats_widget_font_info.get("family"):
        family = stats_widget_font_info["family"]
        if stats_widget_font_key == "system":
            sw_stack = family
        else:
            sw_stack = (
                f"'{family}', -apple-system, BlinkMacSystemFont, \"Segoe UI\","
                " Roboto, Helvetica, Arial, sans-serif"
            )
        stats_widget_font_css = (
            ".stat-card, .stat-card h3, .stat-card .stat-value, "
            ".stat-card .stat-unit, .stat-card .stat-sub "
            f"{{ font-family: {sw_stack} !important; }}"
        )

    profile_name_font_css = ""
    profile_name_font_info = all_fonts.get(profile_name_font_key)
    if profile_name_font_key != "system" and profile_name_font_info and profile_name_font_info.get("family"):
        profile_name_font_css = (
            ".profile-bar .profile-name, .onigiri-sidebar-profile-body h2, "
            ".onigiri-profile .opro-name, .onigiri-profile .opro-level, "
            ".onigiri-profile .opro-lv "
            "{{ font-family: '{family}', "
            "-apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, Helvetica, Arial, sans-serif !important; }}"
        ).format(family=profile_name_font_info["family"])

    # Generate the final CSS block
    font_css = f"""
    <style id="onigiri-font-styles">
        {font_faces}
        :root {{
            --font-main: {main_font_info['family']};
            --font-subtle: {subtle_font_info['family']};
            --font-small-title: {small_title_font_info['family']};
            --font-size-main: {main_font_size}px;
            --font-size-subtle: {subtle_font_size}px;
            --font-size-small-title: {small_title_font_size}px;
        }}
        
        /* Apply fonts to specific elements */
        #onigiri-reveal-btn {{
            font-family: var(--font-main) !important;
            box-shadow: none !important;
            border: none !important;
        }}
        
        #study, .mini-overview #study {{
            font-family: var(--font-main) !important;
            color: var(--fg) !important;
        }}

        .stats-row,
        .stats-row span:not(.new-count-bubble):not(.learn-count-bubble):not(.review-count-bubble),
        .congrats-card h1 {{
            font-family: var(--font-main), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
            font-size: var(--font-size-main) !important;
            color: var(--fg) !important;
        }}

        /* Count bubbles stay pill-shaped at a fixed small size regardless of the
           main font size setting; see tr.deck .new-count-bubble in menu.css.
           Color is intentionally NOT forced here so the per-bubble text color
           set in overview.css (--overview-*-count-fg) can take effect. */
        .new-count-bubble,
        .learn-count-bubble,
        .review-count-bubble {{
            font-family: var(--font-main), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        }}
        
        body:not(.card) {{
            font-family: var(--font-main), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
            font-size: var(--font-size-main) !important;
            color: var(--fg) !important;
        }}
        
        /* Apply font size to specific elements explicitly if needed */
        .deck-table a.deck {{
             font-size: var(--font-size-main) !important;
             color: var(--fg) !important;
        }}

        /* Action Buttons (Add/Browse/Stats/Sync/Settings/More/etc.) - list mode */
        .menu-item {{
             font-size: var(--font-size-main) !important;
        }}
        
        /* Titles (Subtle) - e.g. Today's Stats */
        .onigiri-widget-title {{
            font-family: var(--font-subtle), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
            font-size: var(--font-size-subtle) !important;
            color: var(--fg-subtle) !important;
        }}

        {stats_title_font_css}

        /* Small Titles - Sidebar Headers and Widget Titles */
        .sidebar-left h2, .stat-card h3, .onigiri-widget-container h3 {{
            font-family: var(--font-small-title), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
            font-size: var(--font-size-small-title) !important;
            color: var(--font-small-title-color, var(--fg)) !important;
        }}
        {stats_widget_font_css}
        {profile_name_font_css}
    </style>
    """

    return font_css

def _hex_to_rgba(hex_str: str, alpha: float) -> str:
	"""Converts a hex color string to an rgba string."""
	hex_str = hex_str.lstrip('#')
	if len(hex_str) != 6:
		return f"rgba(0,0,0,{alpha})" # Return a default for invalid hex
	try:
		r, g, b = tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
		return f"rgba({r}, {g}, {b}, {alpha})"
	except ValueError:
		return f"rgba(0,0,0,{alpha})"


def _onigiri_int_style_value(value, fallback):
	if value is None or value == "":
		return fallback
	try:
		return int(value)
	except Exception:
		return fallback


def _onigiri_css_color_with_alpha(color, alpha):
	color = str(color or "").strip()
	alpha = max(0.0, min(1.0, alpha))
	if color.startswith("rgba"):
		parts = color[color.find("(") + 1:color.rfind(")")].split(",")
		if len(parts) >= 3:
			return f"rgba({parts[0].strip()}, {parts[1].strip()}, {parts[2].strip()}, {alpha})"
	if color.startswith("rgb"):
		parts = color[color.find("(") + 1:color.rfind(")")].split(",")
		if len(parts) >= 3:
			return f"rgba({parts[0].strip()}, {parts[1].strip()}, {parts[2].strip()}, {alpha})"
	if color.startswith("#"):
		return _hex_to_rgba(color, alpha)
	return color


def _box_effect_values():
	effect_mode = mw.col.conf.get("onigiri_canvas_inset_effect_mode", "none")
	effect_intensity = mw.col.conf.get("onigiri_canvas_inset_effect_intensity", 50)
	if "onigiri_canvas_inset_effect_blur" in mw.col.conf or "onigiri_canvas_inset_effect_opacity" in mw.col.conf:
		blur = int(mw.col.conf.get("onigiri_canvas_inset_effect_blur", 0) or 0)
		opacity = int(mw.col.conf.get("onigiri_canvas_inset_effect_opacity", 100) or 100)
	else:
		if effect_mode == "glassmorphism":
			blur = int(effect_intensity or 0)
			opacity = max(0, min(100, 100 - int(effect_intensity or 0)))
		elif effect_mode == "opacity":
			blur = 0
			opacity = int(effect_intensity or 100)
		else:
			blur = 0
			opacity = 100
	blur = max(0, min(100, blur))
	opacity = max(0, min(100, opacity))
	radius = max(0, min(60, _onigiri_int_style_value(mw.col.conf.get("onigiri_canvas_inset_border_radius", 20), 20)))
	stroke = max(0, min(10, _onigiri_int_style_value(mw.col.conf.get("onigiri_canvas_inset_border_width", 1), 1)))
	return blur, opacity, radius, stroke


def generate_box_effect_button_vars_css(conf=None, selector=":root", night_selector=None):
	if conf is None:
		conf = config.get_config_readonly()
	if night_selector is None:
		night_selector = ".night-mode,\n        .nightMode,\n        .night_mode"
	blur, opacity, radius, stroke = _box_effect_values()
	colors = conf.get("colors", {}) if isinstance(conf.get("colors", {}), dict) else {}

	def _mode_color(mode, key, fallback):
		mode_colors = colors.get(mode, {}) if isinstance(colors.get(mode, {}), dict) else {}
		return mode_colors.get(key, fallback)

	def _box_bg(mode, fallback):
		color = _mode_color(mode, "--canvas-inset", fallback)
		if opacity < 100 or blur > 0:
			alpha = opacity / 100.0
			if blur > 0:
				alpha = min(alpha, 0.62)
			return _onigiri_css_color_with_alpha(color, alpha)
		return color

	blur_px = (blur / 100.0) * 20
	return f"""
    <style id="onigiri-box-effect-button-vars">
        {selector} {{
            --onigiri-box-effect-bg: {_box_bg("light", "#ffffff")};
            --onigiri-box-effect-border: {_mode_color("light", "--border", "#d9d9d9")};
            --onigiri-box-effect-border-hover: {_mode_color("light", "--border-hover", _mode_color("light", "--border", "#bfbfbf"))};
            --onigiri-box-effect-fg: {_mode_color("light", "--fg", "#333333")};
            --onigiri-box-effect-radius: {radius}px;
            --onigiri-box-effect-stroke: {stroke}px;
            --onigiri-box-effect-blur: {blur_px:.2f}px;
        }}
        {night_selector} {{
            --onigiri-box-effect-bg: {_box_bg("dark", "#2c2c2c")};
            --onigiri-box-effect-border: {_mode_color("dark", "--border", "#3a3a3a")};
            --onigiri-box-effect-border-hover: {_mode_color("dark", "--border-hover", _mode_color("dark", "--border", "#4a4a4a"))};
            --onigiri-box-effect-fg: {_mode_color("dark", "--fg", "#e0e0e0")};
        }}
    </style>
    """


def generate_scoped_main_font_css(addon_package, selector):
	main_font_key = mw.col.conf.get("onigiri_font_main", "system")
	main_font_size = mw.col.conf.get("onigiri_font_size_main", 14)
	from .fonts import FONTS, get_all_fonts

	all_fonts = FONTS if main_font_key in FONTS else get_all_fonts(os.path.dirname(__file__))
	main_font_info = all_fonts.get(main_font_key)
	if not main_font_info:
		return ""

	from .fonts import poppins_font_face_css
	# Poppins backs the default ("system") font stack, so its faces must be
	# available in this scoped webview even when no dedicated file is selected.
	font_face = poppins_font_face_css(addon_package)
	if main_font_info.get("file"):
		if main_font_info.get("user"):
			font_url = f"/_addons/{addon_package}/user_files/fonts/{main_font_info['file']}"
		else:
			font_url = f"/_addons/{addon_package}/system_files/fonts/system_fonts/{main_font_info['file']}"
		font_face = f"""
        @font-face {{
            font-family: '{main_font_info['family']}';
            src: url('{font_url}');
        }}
        """

	return f"""
    <style id="onigiri-scoped-main-font">
        {font_face}
        {selector} {{
            --font-main: {main_font_info['family']};
            --font-size-main: {int(main_font_size)}px;
        }}
    </style>
    """


def _hex_to_hsl(hex_str: str):
	"""Converts a hex color to HSL values in the 0..1 range."""
	hex_str = (hex_str or "#007aff").lstrip("#")
	if len(hex_str) == 3:
		hex_str = "".join(ch * 2 for ch in hex_str)
	try:
		r = int(hex_str[0:2], 16) / 255.0
		g = int(hex_str[2:4], 16) / 255.0
		b = int(hex_str[4:6], 16) / 255.0
	except Exception:
		r, g, b = 0.0, 0.478, 1.0
	max_c = max(r, g, b)
	min_c = min(r, g, b)
	l = (max_c + min_c) / 2.0
	if max_c == min_c:
		return 0.0, 0.0, l
	d = max_c - min_c
	s = d / (2.0 - max_c - min_c) if l > 0.5 else d / (max_c + min_c)
	if max_c == r:
		h = (g - b) / d + (6 if g < b else 0)
	elif max_c == g:
		h = (b - r) / d + 2
	else:
		h = (r - g) / d + 4
	h /= 6.0
	return h, s, l


def _hsl_to_hex(h: float, s: float, l: float) -> str:
	"""Converts HSL values in the 0..1 range to a hex color."""
	h = max(0.0, min(1.0, h))
	s = max(0.0, min(1.0, s))
	l = max(0.0, min(1.0, l))
	if s == 0.0:
		v = int(l * 255)
		return "#{:02x}{:02x}{:02x}".format(v, v, v)

	def _hue(p, q, t):
		if t < 0:
			t += 1.0
		if t > 1:
			t -= 1.0
		if t < 1 / 6:
			return p + (q - p) * 6.0 * t
		if t < 1 / 2:
			return q
		if t < 2 / 3:
			return p + (q - p) * (2.0 / 3.0 - t) * 6.0
		return p

	q = l * (1.0 + s) if l < 0.5 else l + s - l * s
	p = 2.0 * l - q
	r = _hue(p, q, h + 1.0 / 3.0)
	g = _hue(p, q, h)
	b = _hue(p, q, h - 1.0 / 3.0)
	return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))


def _mix_colors(c1, c2, ratio):
	"""Mixes two colors (hex or rgba) with a given ratio (0.0 to 1.0).
	ratio is the weight of c1.
	"""
	def parse_color(c):
		if not c: return (0, 0, 0, 1.0)
		if c.startswith('#'):
			c = c.lstrip('#')
			if len(c) == 6:
				return tuple(int(c[i:i+2], 16) for i in (0, 2, 4)) + (1.0,)
			elif len(c) == 3:
				return tuple(int(c[i]*2, 16) for i in (0, 1, 2)) + (1.0,)
		elif c.startswith('rgba'):
			parts = c[5:-1].split(',')
			return float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])
		elif c.startswith('rgb'):
			parts = c[4:-1].split(',')
			return float(parts[0]), float(parts[1]), float(parts[2]), 1.0
		return (0, 0, 0, 1.0) # Fallback

	r1, g1, b1, a1 = parse_color(c1)
	r2, g2, b2, a2 = parse_color(c2)

	r = r1 * ratio + r2 * (1 - ratio)
	g = g1 * ratio + g2 * (1 - ratio)
	b = b1 * ratio + b2 * (1 - ratio)
	a = a1 * ratio + a2 * (1 - ratio)

	return f"rgba({int(r)}, {int(g)}, {int(b)}, {a:.2f})"

def generate_dynamic_css(conf):
	# ADDED to get the add-on's path for font files
	addon_package = mw.addonManager.addonFromModule(__name__)
	# ADDED to generate the font-specific CSS
	font_css_block = generate_font_css(addon_package)

	effect_mode = mw.col.conf.get("onigiri_canvas_inset_effect_mode", "none")
	effect_intensity = mw.col.conf.get("onigiri_canvas_inset_effect_intensity", 50)
	if "onigiri_canvas_inset_effect_blur" in mw.col.conf or "onigiri_canvas_inset_effect_opacity" in mw.col.conf:
		box_effect_blur = int(mw.col.conf.get("onigiri_canvas_inset_effect_blur", 0) or 0)
		box_effect_opacity = int(mw.col.conf.get("onigiri_canvas_inset_effect_opacity", 100) or 100)
	else:
		if effect_mode == "glassmorphism":
			box_effect_blur = int(effect_intensity or 0)
			box_effect_opacity = max(0, min(100, 100 - int(effect_intensity or 0)))
		elif effect_mode == "opacity":
			box_effect_blur = 0
			box_effect_opacity = int(effect_intensity or 100)
		else:
			box_effect_blur = 0
			box_effect_opacity = 100
	box_effect_blur = max(0, min(100, box_effect_blur))
	box_effect_opacity = max(0, min(100, box_effect_opacity))
	def _int_style_value(value, fallback):
		if value is None or value == "":
			return fallback
		try:
			return int(value)
		except Exception:
			return fallback

	box_effect_radius = max(0, min(60, _int_style_value(mw.col.conf.get("onigiri_canvas_inset_border_radius", 20), 20)))
	box_effect_stroke = max(0, min(10, _int_style_value(mw.col.conf.get("onigiri_canvas_inset_border_width", 1), 1)))

	def _apply_canvas_inset_effect(colors: dict):
		"""Applies the box opacity setting to --canvas-inset color."""
		if "--canvas-inset" not in colors:
			return

		if box_effect_opacity < 100 or box_effect_blur > 0:
			alpha = box_effect_opacity / 100.0
			if box_effect_blur > 0:
				alpha = min(alpha, 0.62)
			colors["--canvas-inset"] = _onigiri_css_color_with_alpha(colors["--canvas-inset"], alpha)

	colors = conf.get("colors", {})
	light_colors = colors.get("light", {}).copy()
	dark_colors = colors.get("dark", {}).copy()

	# Captured before the opacity/blur effect so tooltips stay solid.
	raw_box_light = light_colors.get("--canvas-inset", "#ffffff")
	raw_box_dark = dark_colors.get("--canvas-inset", "#2c2c2c")

	# Apply effects if enabled
	_apply_canvas_inset_effect(light_colors)
	_apply_canvas_inset_effect(dark_colors)

	overview_style = conf.get("overview_style", {}) if isinstance(conf.get("overview_style", {}), dict) else {}
	overview_colors = overview_style.get("colors", {}) if isinstance(overview_style.get("colors", {}), dict) else {}
	overview_sync = bool(overview_style.get("sync_box_effect", False))
	overview_blur = box_effect_blur if overview_sync else max(0, min(100, int(overview_style.get("blur", mw.col.conf.get("onigiri_overview_effect_blur", 0)) or 0)))
	overview_opacity = box_effect_opacity if overview_sync else max(0, min(100, int(overview_style.get("opacity", mw.col.conf.get("onigiri_overview_effect_opacity", 100)) or 100)))
	overview_radius = box_effect_radius if overview_sync else max(0, min(60, _int_style_value(overview_style.get("radius", mw.col.conf.get("onigiri_overview_border_radius", 20)), 20)))
	overview_stroke = box_effect_stroke if overview_sync else max(0, min(10, _int_style_value(overview_style.get("stroke", mw.col.conf.get("onigiri_overview_border_width", 1)), 1)))

	def _overview_color(mode: str, key: str, fallback_key: str, fallback: str) -> str:
		mode_colors = overview_colors.get(mode, {}) if isinstance(overview_colors.get(mode, {}), dict) else {}
		theme_colors = light_colors if mode == "light" else dark_colors
		return mode_colors.get(key) or theme_colors.get(fallback_key) or fallback

	def _overview_rgba(color: str, alpha: float) -> str:
		color = str(color or "").strip()
		alpha = max(0.0, min(1.0, alpha))
		if color.startswith("rgba"):
			parts = color[color.find("(") + 1:color.rfind(")")].split(",")
			if len(parts) >= 3:
				return f"rgba({parts[0].strip()}, {parts[1].strip()}, {parts[2].strip()}, {alpha})"
		if color.startswith("rgb"):
			parts = color[color.find("(") + 1:color.rfind(")")].split(",")
			if len(parts) >= 3:
				return f"rgba({parts[0].strip()}, {parts[1].strip()}, {parts[2].strip()}, {alpha})"
		return _hex_to_rgba(color, alpha)

	def _overview_box_bg(mode: str, fallback: str) -> str:
		alpha = overview_opacity / 100.0
		if overview_blur > 0:
			alpha = min(alpha, 0.82)
		if overview_sync:
			color = (light_colors if mode == "light" else dark_colors).get("--canvas-inset", fallback)
			return _overview_rgba(color, alpha) if overview_opacity < 100 or overview_blur > 0 else color
		color = _overview_color(mode, "box_bg", "--canvas-inset", fallback)
		if overview_opacity < 100 or overview_blur > 0:
			return _overview_rgba(color, alpha)
		return color

	# --- Study Now button styling (synced with the box color & effect) ---
	study_btn_opacity = max(0, min(100, _int_style_value(overview_style.get("study_button_opacity", 100), 100)))
	study_btn_radius_raw = _int_style_value(overview_style.get("study_button_radius", 100), 100)
	if study_btn_radius_raw > 100:
		study_btn_radius_raw = 100
	study_btn_radius_pct = max(0, min(100, study_btn_radius_raw))
	if study_btn_radius_pct == 100:
		study_btn_radius = "999"
	else:
		study_btn_radius = f"{(study_btn_radius_pct / 100.0) * 24:.1f}"
	study_btn_stroke = max(0, min(10, _int_style_value(overview_style.get("study_button_stroke", 0), 0)))
	study_btn_dashed = bool(overview_style.get("study_button_dashed", False))
	study_btn_animated = bool(overview_style.get("study_button_animated", True))
	study_btn_stroke_style = "dashed" if study_btn_dashed else "solid"
	study_btn_hover_lift = "-2px" if study_btn_animated else "0px"
	study_btn_hover_shadow = (
		"0 6px 18px rgba(0, 0, 0, 0.22)" if study_btn_animated else "none"
	)
	study_btn_blur_px = (overview_blur / 100.0) * 20 if overview_sync and overview_blur > 0 else 0

	def _study_button_bg(mode: str, fallback: str) -> str:
		color = _overview_color(mode, "study_button", "--button-primary-bg", fallback)
		if study_btn_opacity < 100:
			return _overview_rgba(color, study_btn_opacity / 100.0)
		return color

	def _overview_button_text_color(color: str) -> str:
		"""Return a readable foreground for a user-picked button colour."""
		value = str(color or "").strip().lstrip("#")
		if len(value) == 3:
			value = "".join(char * 2 for char in value)
		if len(value) != 6:
			return "var(--fg)"
		try:
			red, green, blue = (int(value[index:index + 2], 16) for index in (0, 2, 4))
		except ValueError:
			return "var(--fg)"
		return "#1f2124" if (0.299 * red + 0.587 * green + 0.114 * blue) > 150 else "#ffffff"

	def _overview_action_button_rules(mode: str) -> list:
		defaults = {
			"options_button": "#f5f5f5" if mode == "light" else "#2a2a2a",
			"custom_study_button": "#f5f5f5" if mode == "light" else "#2a2a2a",
			"description_button": "#f5f5f5" if mode == "light" else "#2a2a2a",
			"reveal_button": "#0077c8" if mode == "light" else "#0a84ff",
		}
		rules = []
		for key, fallback in defaults.items():
			color = _overview_color(mode, key, "", fallback)
			name = key.replace("_button", "").replace("_", "-")
			rules.extend((
				f"    --overview-{name}-button-bg: {color} !important;",
				f"    --overview-{name}-button-fg: {_overview_button_text_color(color)} !important;",
			))
		return rules

	overview_light_rules = [
		f"    --overview-box-bg: {_overview_box_bg('light', '#ffffff')} !important;",
		f"    --overview-box-border: {_overview_color('light', 'box_border', '--border', '#e0e0e0')} !important;",
		f"    --overview-study-button-bg: {_study_button_bg('light', '#007aff')} !important;",
		f"    --overview-study-button-stroke-width: {study_btn_stroke}px !important;",
		f"    --overview-study-button-stroke-style: {study_btn_stroke_style} !important;",
		f"    --overview-study-button-stroke-color: {_overview_color('light', 'study_button_stroke', 'box_border', '#e0e0e0')} !important;",
		f"    --overview-study-button-hover-lift: {study_btn_hover_lift} !important;",
		f"    --overview-study-button-hover-shadow: {study_btn_hover_shadow} !important;",
		f"    --overview-study-button-blur: {study_btn_blur_px:.2f}px !important;",
		f"    --overview-study-button-radius: {study_btn_radius}px !important;",
		f"    --overview-new-bubble-bg: {_overview_color('light', 'new_bubble', '--new-count-bubble-bg', '#1e8cff')} !important;",
		f"    --overview-new-count-fg: {_overview_color('light', 'new_text', '--new-count-bubble-fg', '#ffffff')} !important;",
		f"    --overview-learn-bubble-bg: {_overview_color('light', 'learn_bubble', '--learn-count-bubble-bg', '#ff5757')} !important;",
		f"    --overview-learn-count-fg: {_overview_color('light', 'learn_text', '--learn-count-bubble-fg', '#ffffff')} !important;",
		f"    --overview-review-bubble-bg: {_overview_color('light', 'review_bubble', '--review-count-bubble-bg', '#19c96b')} !important;",
		f"    --overview-review-count-fg: {_overview_color('light', 'review_text', '--review-count-bubble-fg', '#ffffff')} !important;",
		f"    --overview-box-blur: {(overview_blur / 100.0) * 20:.2f}px !important;",
		f"    --overview-box-radius: {overview_radius}px !important;",
		f"    --overview-box-stroke: {overview_stroke}px !important;",
	]
	overview_light_rules.extend(_overview_action_button_rules("light"))
	overview_dark_rules = [
		f"    --overview-box-bg: {_overview_box_bg('dark', '#2c2c2c')} !important;",
		f"    --overview-box-border: {_overview_color('dark', 'box_border', '--border', '#424242')} !important;",
		f"    --overview-study-button-bg: {_study_button_bg('dark', '#0a84ff')} !important;",
		f"    --overview-study-button-stroke-width: {study_btn_stroke}px !important;",
		f"    --overview-study-button-stroke-style: {study_btn_stroke_style} !important;",
		f"    --overview-study-button-stroke-color: {_overview_color('dark', 'study_button_stroke', 'box_border', '#424242')} !important;",
		f"    --overview-study-button-hover-lift: {study_btn_hover_lift} !important;",
		f"    --overview-study-button-hover-shadow: {study_btn_hover_shadow} !important;",
		f"    --overview-study-button-blur: {study_btn_blur_px:.2f}px !important;",
		f"    --overview-study-button-radius: {study_btn_radius}px !important;",
		f"    --overview-new-bubble-bg: {_overview_color('dark', 'new_bubble', '--new-count-bubble-bg', '#0a84ff')} !important;",
		f"    --overview-new-count-fg: {_overview_color('dark', 'new_text', '--new-count-bubble-fg', '#f7fbff')} !important;",
		f"    --overview-learn-bubble-bg: {_overview_color('dark', 'learn_bubble', '--learn-count-bubble-bg', '#ff453a')} !important;",
		f"    --overview-learn-count-fg: {_overview_color('dark', 'learn_text', '--learn-count-bubble-fg', '#fff5f5')} !important;",
		f"    --overview-review-bubble-bg: {_overview_color('dark', 'review_bubble', '--review-count-bubble-bg', '#12b765')} !important;",
		f"    --overview-review-count-fg: {_overview_color('dark', 'review_text', '--review-count-bubble-fg', '#f4fff8')} !important;",
		f"    --overview-box-blur: {(overview_blur / 100.0) * 20:.2f}px !important;",
		f"    --overview-box-radius: {overview_radius}px !important;",
		f"    --overview-box-stroke: {overview_stroke}px !important;",
	]
	overview_dark_rules.extend(_overview_action_button_rules("dark"))

	# --- Deck Stats widget (learner stats) look & category colors ---
	deck_stats_style = conf.get("deck_stats_style", {}) if isinstance(conf.get("deck_stats_style", {}), dict) else {}
	deck_stats_colors = deck_stats_style.get("colors", {}) if isinstance(deck_stats_style.get("colors", {}), dict) else {}
	deck_stats_sync = bool(deck_stats_style.get("sync_box_effect", True))
	deck_stats_dynamic = bool(deck_stats_style.get("dynamic", True))
	deck_stats_blur = box_effect_blur if deck_stats_sync else max(0, min(100, int(deck_stats_style.get("blur", 0) or 0)))
	deck_stats_opacity = box_effect_opacity if deck_stats_sync else max(0, min(100, int(deck_stats_style.get("opacity", 100) or 100)))
	deck_stats_radius = box_effect_radius if deck_stats_sync else max(0, min(60, _int_style_value(deck_stats_style.get("radius", 20), 20)))
	deck_stats_stroke = box_effect_stroke if deck_stats_sync else max(0, min(10, _int_style_value(deck_stats_style.get("stroke", 1), 1)))

	def _deck_stats_color(mode: str, key: str, fallback: str) -> str:
		# With Dynamic mode off there is a single palette; the "light" entry is
		# the one the settings page writes, so it stands in for both themes.
		source_mode = mode if deck_stats_dynamic else "light"
		palette = deck_stats_colors.get(source_mode, {})
		value = palette.get(key) if isinstance(palette, dict) else None
		return value if isinstance(value, str) and value else fallback

	def _deck_stats_box_bg(mode: str, fallback_key: str, fallback: str) -> str:
		if deck_stats_sync:
			# Already carries the box opacity/blur alpha from _apply_canvas_inset_effect.
			source = light_colors if mode == "light" else dark_colors
			return source.get(fallback_key, fallback)
		color = _deck_stats_color(mode, "box_bg", fallback)
		alpha = deck_stats_opacity / 100.0
		if deck_stats_blur > 0:
			alpha = min(alpha, 0.62)
		if alpha < 1.0:
			return _onigiri_css_color_with_alpha(color, alpha)
		return color

	# patcher's own DEFAULTS is a stub, so the Anki-native palette is repeated
	# here as the last-resort fallback for a config that predates the feature.
	deck_stats_fallback_colors = {
		"light": {
			"in_progress": "#5eaadf", "mastered": "#26a641", "new": "#5eaadf",
			"learning": "#f5a05a", "relearning": "#f4685f", "young": "#7cc87c",
			"mature": "#26a641", "unseen": "#b0b4b9",
			"suspended": "#ffdc41", "buried": "#9e9e9e", "total": "#6f7177",
		},
		"dark": {
			"in_progress": "#6bb6ec", "mastered": "#35b850", "new": "#6bb6ec",
			"learning": "#f7ad6b", "relearning": "#f8776e", "young": "#8ad48a",
			"mature": "#35b850", "unseen": "#7a7f85",
			"suspended": "#ffe066", "buried": "#a8a8a8", "total": "#c4c4c4",
		},
	}

	def _deck_stats_rules(mode: str, box_fallback: str, border_fallback: str) -> list:
		defaults = deck_stats_fallback_colors.get(mode if deck_stats_dynamic else "light", {})
		border = (
			(light_colors if mode == "light" else dark_colors).get("--border", border_fallback)
			if deck_stats_sync
			else _deck_stats_color(mode, "box_border", border_fallback)
		)
		rules = [
			f"    --stats-box-bg: {_deck_stats_box_bg(mode, '--canvas-inset', box_fallback)} !important;",
			f"    --stats-box-border: {border} !important;",
			f"    --stats-box-radius: {deck_stats_radius}px !important;",
			f"    --stats-box-stroke: {deck_stats_stroke}px !important;",
			f"    --stats-box-blur: {(deck_stats_blur / 100.0) * 20:.2f}px !important;",
		]
		for key in (
			"in_progress", "mastered", "new", "learning", "relearning",
			"young", "mature", "unseen", "suspended", "buried", "total",
		):
			var_name = "--stats-" + key.replace("_", "-") + "-color"
			rules.append(f"    {var_name}: {_deck_stats_color(mode, key, defaults.get(key, '#808080'))} !important;")
		return rules

	overview_light_rules.extend(_deck_stats_rules("light", "#ffffff", "#e0e0e0"))
	overview_dark_rules.extend(_deck_stats_rules("dark", "#2c2c2c", "#424242"))

	# --- Today's Stats widgets (Studied / Time / Pace / Retention) ---
	# Same shape as the Deck Stats block above: an optional sync to Box Color
	# and Effect, an optional single-palette (non-dynamic) mode, then per-widget
	# accent colors emitted as --swidget-* vars for menu.css to consume.
	stats_widgets_style = conf.get("stats_widgets_style", {}) if isinstance(conf.get("stats_widgets_style", {}), dict) else {}
	sw_colors = stats_widgets_style.get("colors", {}) if isinstance(stats_widgets_style.get("colors", {}), dict) else {}
	sw_sync = bool(stats_widgets_style.get("sync_box_effect", True))
	sw_dynamic = bool(stats_widgets_style.get("dynamic", True))
	sw_blur = box_effect_blur if sw_sync else max(0, min(100, int(stats_widgets_style.get("blur", 0) or 0)))
	sw_opacity = box_effect_opacity if sw_sync else max(0, min(100, int(stats_widgets_style.get("opacity", 100) or 100)))
	sw_radius = box_effect_radius if sw_sync else max(0, min(60, _int_style_value(stats_widgets_style.get("radius", 20), 20)))
	sw_stroke = box_effect_stroke if sw_sync else max(0, min(10, _int_style_value(stats_widgets_style.get("stroke", 1), 1)))
	sw_value_scale = max(60, min(100, _int_style_value(stats_widgets_style.get("value_scale", 100), 100)))

	sw_fallback_colors = {
		"light": {
			"box_bg": "#ffffff", "box_border": "#e0e0e0",
			"label": "#757575", "value": "#212121",
			"studied": "#5eaadf", "time": "#8b7bd8",
			"pace": "#f5a05a", "retention": "#26a641",
			"retention_star": "#FFD700", "retention_star_empty": "#e0e0e0",
		},
		"dark": {
			"box_bg": "#2c2c2c", "box_border": "#424242",
			"label": "#9c9c9c", "value": "#f0f0f0",
			"studied": "#6bb6ec", "time": "#a294ea",
			"pace": "#f7ad6b", "retention": "#35b850",
			"retention_star": "#FFD700", "retention_star_empty": "#4a4a4a",
		},
	}

	def _sw_color(mode: str, key: str) -> str:
		source_mode = mode if sw_dynamic else "light"
		palette = sw_colors.get(source_mode, {})
		value = palette.get(key) if isinstance(palette, dict) else None
		if isinstance(value, str) and value:
			return value
		return sw_fallback_colors.get(source_mode, {}).get(key, "#808080")

	def _sw_rules(mode: str) -> list:
		if sw_sync:
			theme = light_colors if mode == "light" else dark_colors
			box_bg = theme.get("--canvas-inset", sw_fallback_colors[mode]["box_bg"])
			box_border = theme.get("--border", sw_fallback_colors[mode]["box_border"])
		else:
			box_bg = _sw_color(mode, "box_bg")
			alpha = sw_opacity / 100.0
			if sw_blur > 0:
				alpha = min(alpha, 0.62)
			if alpha < 1.0:
				box_bg = _onigiri_css_color_with_alpha(box_bg, alpha)
			box_border = _sw_color(mode, "box_border")
		rules = [
			f"    --swidget-box-bg: {box_bg} !important;",
			f"    --swidget-box-border: {box_border} !important;",
			f"    --swidget-box-radius: {sw_radius}px !important;",
			f"    --swidget-box-stroke: {sw_stroke}px !important;",
			f"    --swidget-box-blur: {(sw_blur / 100.0) * 20:.2f}px !important;",
			f"    --swidget-label-color: {_sw_color(mode, 'label')} !important;",
			f"    --swidget-value-color: {_sw_color(mode, 'value')} !important;",
			f"    --swidget-value-scale: {sw_value_scale / 100.0:.2f} !important;",
		]
		for key in ("studied", "time", "pace", "retention"):
			accent = _sw_color(mode, key)
			rules.append(f"    --swidget-{key}-accent: {accent} !important;")
			# Pre-mixed tints. CSS color-mix() is not dependable in the Qt
			# WebEngine build Anki ships, so the alpha variants are computed
			# here the same way the heatmap ramp is.
			rules.append(f"    --swidget-{key}-chip: {_onigiri_css_color_with_alpha(accent, 0.16)} !important;")
			rules.append(f"    --swidget-{key}-wash: {_onigiri_css_color_with_alpha(accent, 0.10)} !important;")
			if key == "retention":
				# Retention stars have their own palette so the default filled
				# stars stay yellow instead of inheriting the metric's green accent.
				rules.append(f"    --swidget-retention-star: {_sw_color(mode, 'retention_star')} !important;")
				rules.append(f"    --swidget-retention-empty-star: {_sw_color(mode, 'retention_star_empty')} !important;")
		return rules

	overview_light_rules.extend(_sw_rules("light"))
	overview_dark_rules.extend(_sw_rules("dark"))

	# --- Hashi Notes dashboard widget ---
	hashi_widget_style = conf.get("hashi_widget_style", {}) if isinstance(conf.get("hashi_widget_style", {}), dict) else {}
	hw_colors = hashi_widget_style.get("colors", {}) if isinstance(hashi_widget_style.get("colors", {}), dict) else {}
	hw_sync = bool(hashi_widget_style.get("sync_box_effect", True))
	hw_dynamic = bool(hashi_widget_style.get("dynamic", True))
	hw_blur = box_effect_blur if hw_sync else max(0, min(100, int(hashi_widget_style.get("blur", 0) or 0)))
	hw_opacity = box_effect_opacity if hw_sync else max(0, min(100, int(hashi_widget_style.get("opacity", 100) or 100)))
	hw_radius = box_effect_radius if hw_sync else max(0, min(60, _int_style_value(hashi_widget_style.get("radius", 20), 20)))
	hw_stroke = box_effect_stroke if hw_sync else max(0, min(10, _int_style_value(hashi_widget_style.get("stroke", 1), 1)))

	hw_fallback_colors = {
		"light": {
			"box_bg": "#ffffff", "box_border": "#e0e0e0", "card_bg": "#f5f5f5",
			"title": "#212121", "excerpt": "#757575", "accent": "#0077C8",
		},
		"dark": {
			"box_bg": "#2c2c2c", "box_border": "#424242", "card_bg": "#363636",
			"title": "#f0f0f0", "excerpt": "#9c9c9c", "accent": "#4da3e8",
		},
	}

	def _hw_color(mode: str, key: str) -> str:
		source_mode = mode if hw_dynamic else "light"
		palette = hw_colors.get(source_mode, {})
		value = palette.get(key) if isinstance(palette, dict) else None
		if isinstance(value, str) and value:
			return value
		return hw_fallback_colors.get(source_mode, {}).get(key, "#808080")

	def _hw_rules(mode: str) -> list:
		if hw_sync:
			theme = light_colors if mode == "light" else dark_colors
			box_bg = theme.get("--canvas-inset", hw_fallback_colors[mode]["box_bg"])
			box_border = theme.get("--border", hw_fallback_colors[mode]["box_border"])
		else:
			box_bg = _hw_color(mode, "box_bg")
			alpha = hw_opacity / 100.0
			if hw_blur > 0:
				alpha = min(alpha, 0.62)
			if alpha < 1.0:
				box_bg = _onigiri_css_color_with_alpha(box_bg, alpha)
			box_border = _hw_color(mode, "box_border")
		return [
			f"    --hashiw-box-bg: {box_bg} !important;",
			f"    --hashiw-box-border: {box_border} !important;",
			f"    --hashiw-box-radius: {hw_radius}px !important;",
			f"    --hashiw-box-stroke: {hw_stroke}px !important;",
			f"    --hashiw-box-blur: {(hw_blur / 100.0) * 20:.2f}px !important;",
			f"    --hashiw-card-bg: {_hw_color(mode, 'card_bg')} !important;",
			f"    --hashiw-title-color: {_hw_color(mode, 'title')} !important;",
			f"    --hashiw-excerpt-color: {_hw_color(mode, 'excerpt')} !important;",
			f"    --hashiw-accent: {_hw_color(mode, 'accent')} !important;",
		]

	overview_light_rules.extend(_hw_rules("light"))
	overview_dark_rules.extend(_hw_rules("dark"))

	# --- START: Calculate Heatmap Colors (to avoid CSS color-mix) ---
	heatmap_style = conf.get("heatmap_style", {}) if isinstance(conf.get("heatmap_style", {}), dict) else {}
	heatmap_dynamic = bool(heatmap_style.get("dynamic", True))

	def _generate_heatmap_colors(colors_dict, is_night_mode):
		# Dynamic Mode off: both themes read the light entry, matching
		# sw_dynamic/deck_stats_dynamic's "source_mode = mode if dynamic else
		# light" rule above.
		source_dict = colors_dict if heatmap_dynamic else light_colors
		heatmap_color = source_dict.get("--heatmap-color", "#9be9a8")
		heatmap_color_zero = source_dict.get("--heatmap-color-zero", "#f0f0f0" if not is_night_mode else "#3a3a3a")

		colors_dict["--heatmap-level-0"] = heatmap_color_zero
		colors_dict["--heatmap-future-0"] = heatmap_color_zero

		h, s, _l = _hex_to_hsl(heatmap_color)

		for i in range(1, 9):
			t = i / 8.0

			if is_night_mode:
				level_l = 0.38 + t * 0.46
				level_s = s * max(0.75, 1.0 - t * 0.22)
			else:
				level_l = 0.90 - t * 0.53
				level_s = s * (0.55 + t * 0.45)

			colors_dict[f"--heatmap-level-{i}"] = _hsl_to_hex(h, level_s, level_l)

			future_ratio = 0.08 + t * 0.62
			if is_night_mode:
				colors_dict[f"--heatmap-future-{i}"] = _mix_colors("#ffffff", heatmap_color_zero, future_ratio)
			else:
				colors_dict[f"--heatmap-future-{i}"] = _mix_colors("#000000", heatmap_color_zero, future_ratio)

	_generate_heatmap_colors(light_colors, False)
	_generate_heatmap_colors(dark_colors, True)
	# --- END: Calculate Heatmap Colors ---

	# --- START: Calculate Tooltip Colors ---
	def _generate_tooltip_colors(colors_dict, raw_box, is_night_mode):
		"""Tooltips follow the box color, shifted 20% away from it (darker in
		dark mode, lighter in light mode) so they read as a separate surface."""
		mixed = _mix_colors("#000000" if is_night_mode else "#ffffff", raw_box, 0.20)
		parts = mixed[mixed.find("(") + 1:mixed.rfind(")")].split(",")
		colors_dict["--onigiri-tooltip-bg"] = (
			f"rgb({parts[0].strip()}, {parts[1].strip()}, {parts[2].strip()})"
		)
		colors_dict["--onigiri-tooltip-fg"] = colors_dict.get(
			"--fg", "#e0e0e0" if is_night_mode else "#333333"
		)
		colors_dict["--onigiri-tooltip-border"] = colors_dict.get(
			"--border", "#3a3a3a" if is_night_mode else "#d9d9d9"
		)

	_generate_tooltip_colors(light_colors, raw_box_light, False)
	_generate_tooltip_colors(dark_colors, raw_box_dark, True)
	# --- END: Calculate Tooltip Colors ---

	# Keep all colors, we'll apply them with proper scoping
	light_rules = []
	dark_rules = []
	
	# Non-card related styles (applied globally)
	non_card_related = {
		"--bg", "--bg-elevated", "--bg-hover", "--bg-active",
		"--border", "--border-hover", "--border-active",
		"--shadow-small", "--shadow-medium", "shadow-large",
		"--canvas-inset"
	}
	
	# Add non-card related styles to global rules
	for key, value in light_colors.items():
		if key in non_card_related:
			light_rules.append(f"    {key}: {value} !important;")
		
	for key, value in dark_colors.items():
		if key in non_card_related:
			dark_rules.append(f"    {key}: {value} !important;")
	
	# Add scoped styles for Onigiri UI elements
	onigiri_ui_light = []
	onigiri_ui_dark = []
	
	text_related = {
		"--fg", "--fg-subtle", "--fg-faint", "--fg-on-accent",
		"--accent", "--accent-hover", "--accent-pressed",
		"--text-on-accent", "--text-on-accent-hover", "--text-on-accent-pressed",
		"--accent-light", "--accent-lighter", "--accent-dark", "--accent-darker"
	}
	
	for key, value in light_colors.items():
		if key in text_related:
			onigiri_ui_light.append(f"    {key}: {value} !important;")
			
	for key, value in dark_colors.items():
		if key in text_related:
			onigiri_ui_dark.append(f"    {key}: {value} !important;")
	
	# Convert lists to strings
	light_rules = "\n".join(light_rules)
	dark_rules = "\n".join(dark_rules)
	onigiri_ui_light = "\n".join(onigiri_ui_light)
	onigiri_ui_dark = "\n".join(onigiri_ui_dark)

	# Special case: One setting for two CSS variables
	if "--button-primary-bg" in light_colors:
		light_colors["--button-primary-bg"] = light_colors["--button-primary-bg"]
	if "--button-primary-bg" in dark_colors:
		dark_colors["--button-primary-bg"] = dark_colors["--button-primary-bg"]

	light_rules = "\n".join([f"    {key}: {value} !important;" for key, value in light_colors.items()])
	dark_rules = "\n".join([f"    {key}: {value} !important;" for key, value in dark_colors.items()])
	
	dyn_bg = bool(mw.col.conf.get("modern_menu_profile_bg_dynamic_mode", True))
	profile_light_color = mw.col.conf.get("modern_menu_profile_bg_color_light", "#EEEEEE")
	profile_dark_color = mw.col.conf.get("modern_menu_profile_bg_color_dark", "#3C3C3C") if dyn_bg else profile_light_color
	light_rules += f"\n    --profile-bg-custom-color: {profile_light_color} !important;"
	dark_rules += f"\n    --profile-bg-custom-color: {profile_dark_color} !important;"

	# --- New frosted effect style block ---
	glass_style_block = ""
	if box_effect_blur > 0:
		blur_px = (box_effect_blur / 100.0) * 20
		# --- FIX: Added heatmap container IDs to the selectors ---
		glass_selectors = ".stat-card, #onigiri-heatmap-container, #onigiri-profile-heatmap-container, .prep-station-widget"
		glass_style_block = f"""
        <style id="onigiri-glass-effect">
        {glass_selectors} {{
            backdrop-filter: blur({blur_px}px);
            -webkit-backdrop-filter: blur({blur_px}px);
        }}
        </style>
        """

	box_selectors = ".stat-card, #onigiri-heatmap-container, #onigiri-profile-heatmap-container, .onigiri-favorites-widget, .onigimon-widget, .hex-land-widget, .prep-station-widget"
	box_shape_style_block = f"""
        <style id="onigiri-box-shape-effect">
        {box_selectors} {{
            border: {box_effect_stroke}px solid var(--border, rgba(128, 128, 128, 0.24)) !important;
            border-radius: {box_effect_radius}px !important;
        }}
        </style>
        """

	# MODIFIED to include scoped Onigiri UI styles and reset card styles
	return f"""
    {font_css_block}
    <style id="modern-menu-dynamic-styles">
    /* Global styles (non-text related) */
    :root {{ {light_rules} }}
    .night-mode, .nightMode {{ {dark_rules} }}

    :root {{
{chr(10).join(overview_light_rules)}
    }}
    .night-mode, .nightMode {{
{chr(10).join(overview_dark_rules)}
    }}
    
    /* Scoped Onigiri UI styles */
    .onigiri-ui, 
    [class*="onigiri-"],
    .modern-menu,
    .modern-menu *:not(.card, .card *),
    .onigiri-profile-page,
    .onigiri-profile-page *:not(.card, .card *),
    .onigiri-restaurant,
    .onigiri-restaurant *:not(.card, .card *) {{
        {onigiri_ui_light}
    }}
    
    .night-mode .onigiri-ui,
    .night-mode [class*="onigiri-"],
    .night-mode .modern-menu,
    .night-mode .modern-menu *:not(.card, .card *),
    .night-mode .onigiri-profile-page,
    .night-mode .onigiri-profile-page *:not(.card, .card *),
    .night-mode .onigiri-restaurant,
    .night-mode .onigiri-restaurant *:not(.card, .card *) {{
        {onigiri_ui_dark}
    }}
    </style>
    {glass_style_block}
    {box_shape_style_block}
    """

def _get_hook_name(hook):
    """Creates a unique, stable identifier for a hook function."""
    module_name = hook.__module__ if hasattr(hook, '__module__') else 'unknown_module'
    return f"{module_name}.{hook.__name__}"

def _get_external_hooks():
    """Returns the list of hooks that Onigiri is managing."""
    hooks = []
    seen = set()
    for hook in _managed_hooks:
        hook_id = _get_hook_name(hook)
        if hook_id not in seen:
            hooks.append(hook)
            seen.add(hook_id)
        if _is_synapsepro_hook(hook):
            for split_hook in _get_synapsepro_split_hooks(hook):
                split_hook_id = _get_hook_name(split_hook)
                if split_hook_id not in seen:
                    hooks.append(split_hook)
                    seen.add(split_hook_id)
    return hooks


def _new_MainWebView_eventFilter(self: MainWebView, obj: QObject, evt: QEvent) -> bool:
	"""Prevents Anki's default hover-to-show-toolbar behavior."""
	# Runs for every Qt event on the main webview (including each mouse move),
	# so it must never rebuild the config.
	conf = config.get_config_readonly()
	should_hide_setting = conf.get("hideNativeHeaderAndBottomBar", False)

	screens_to_interfere = ["deckBrowser", "overview", "review"]
	
	should_interfere = should_hide_setting and mw.state in screens_to_interfere

	if should_interfere:
		# On deck browser/overview, prevent Anki's native hover logic from showing toolbars
		if super(MainWebView, self).eventFilter(obj, evt):
			return True
		if evt.type() == QEvent.Type.Leave and self.mw.fullscreen:
			self.mw.show_menubar()
			return True
		# Block other events from reaching the original handler, which would show the toolbars.
		return False
	else:
		# On all other screens (like reviewer), or if the setting is off, use Anki's original logic.
		if _original_MainWebView_eventFilter:
			return _original_MainWebView_eventFilter(self, obj, evt)
		return super(MainWebView, self).eventFilter(obj, evt)


def _set_web_visible(web, visible: bool) -> None:
    """setVisible() on a webview costs several ms even when nothing changes,
    and every screen change asked for the same state twice. Skip the call when
    the widget is already in the requested state - but only once the main
    window itself is up, because before that isVisible() is False for every
    child and the explicit show/hide flag still has to be set."""
    try:
        if mw.isVisible() and web.isVisible() == visible:
            return
    except Exception:
        pass
    web.setVisible(visible)


def _update_toolbar_visibility(new_state: str, _old_state: str) -> None:
    """This function is called by a hook every time the screen changes."""
    conf = config.get_config_readonly()
    apply_synapsepro_sidebar_visibility(conf)
    # Re-hiding the SynapsePro dock is only needed when that add-on is around to
    # re-show it. Scheduling these unconditionally leaked two lambdas per screen
    # change and ran a full mw.findChild() object-tree walk each time.
    if conf.get("hideSynapseProSidebar", False):
        QTimer.singleShot(0, lambda: apply_synapsepro_sidebar_visibility(config.get_config_readonly()))
        QTimer.singleShot(250, lambda: apply_synapsepro_sidebar_visibility(config.get_config_readonly()))
    should_hide_setting = conf.get("hideNativeHeaderAndBottomBar", False)
    pro_hide = conf.get("proHide", False)
    max_hide = conf.get("maxHide", False)

    if new_state == "review":
        apply_reviewer_bottom_bar_height(conf)
    else:
        restore_bottom_web_height()

    if not should_hide_setting:
        # If the feature is disabled in settings, ensure toolbars are always visible
        _set_web_visible(mw.toolbar.web, True)
        _set_web_visible(mw.bottomWeb, True)
        return

    # Handle reviewer state first with new priority
    if new_state == "review":
        # Always show bottom bar in reviewer, regardless of hide mode
        if max_hide:
            # Max hide: Hide only top toolbar, keep bottom bar visible
            _set_web_visible(mw.toolbar.web, False)
            _set_web_visible(mw.bottomWeb, True)
        elif pro_hide:
            # Pro hide: Hide only top toolbar
            _set_web_visible(mw.toolbar.web, False)
            _set_web_visible(mw.bottomWeb, True)
        else:
            # Base hide mode: Hide top toolbar but keep bottom bar visible
            _set_web_visible(mw.toolbar.web, False)
            _set_web_visible(mw.bottomWeb, True)
        return

    # General hiding logic for other screens
    states_to_hide = ["deckBrowser", "overview"]
    if new_state in states_to_hide:
        # Hide both toolbars on the main menu and deck overview
        _set_web_visible(mw.toolbar.web, False)
        _set_web_visible(mw.bottomWeb, False)
    else:
        # Show toolbars on ALL other screens (this will now exclude the 'review' case when pro_hide is on)
        _set_web_visible(mw.toolbar.web, True)
        _set_web_visible(mw.bottomWeb, True)

def update_reviewer_chip():
    """Update the Restaurant Level chip in Onigiri's reviewer shadow header."""
    try:
        if getattr(mw, "state", None) != "review":
            return

        reviewer = getattr(mw, "reviewer", None)
        reviewer_web = reviewer and getattr(reviewer, "web", None)
        if not reviewer_web:
            return

        chip_html = _get_reviewer_nook_level_chip_html()
        script = f"""
        (function() {{
            const chipHtml = {json.dumps(chip_html)};
            const host = document.getElementById('onigiri-reviewer-ui-host');
            const root = host && host.shadowRoot;
            if (!root) return;

            const header = root.getElementById('onigiri-reviewer-header');
            const buttons = header && header.querySelector('.onigiri-reviewer-header-buttons');
            const existing = header && header.querySelector('.restaurant-level-chip');
            const trimmed = chipHtml.trim();

            if (!trimmed) {{
                if (existing) existing.remove();
            }} else {{
                const template = document.createElement('template');
                template.innerHTML = trimmed;
                const nextChip = template.content.firstElementChild;
                if (nextChip && existing) {{
                    existing.replaceWith(nextChip);
                }} else if (nextChip && buttons) {{
                    buttons.appendChild(nextChip);
                }}
            }}

            if (typeof window.onigiriRefreshReviewerHeaderOffset === 'function') {{
                window.onigiriRefreshReviewerHeaderOffset();
            }}
        }})();
        """
        reviewer_web.eval(script)
    except Exception as e:
        print(f"Onigiri: Error updating reviewer restaurant chip: {e}")

def on_reviewer_did_answer_card(reviewer, card, ease):
    """Update the level progress container when a card is answered."""
    update_reviewer_chip()



def _onigiri_render_deck_node(self, node, ctx) -> str:
    """
    A patched version of DeckBrowser._render_deck_node that creates the
    HTML structure Onigiri's CSS and JS expect (e.g., td.collapse-cell).
    """
    buf = []  # Use a list for efficient string building

    if node.collapsed:
        prefix = "+"
        state_class = "state-closed"
    else:
        prefix = "-"
        state_class = "state-open"

    conf = getattr(ctx, "onigiri_conf", None)
    if conf is None:
        conf = config.get_config_readonly()
        setattr(ctx, "onigiri_conf", conf)

    # --- ADD THIS BLOCK ---
    # --- Onigiri Favorites ---
    # This runs once per deck row, so both collection reads are cached on the
    # render context alongside onigiri_conf - a tree with 180 decks was paying
    # 360 backend round-trips per render for two values that cannot change
    # mid-render.
    favorites = getattr(ctx, "onigiri_favorites", None)
    if favorites is None:
        try:
            favorites = mw.col.get_config("onigiri_favorite_decks") or []
        except Exception:
            favorites = mw.col.conf.get("onigiri_favorite_decks", [])
        setattr(ctx, "onigiri_favorites", favorites)
    did_str = str(node.deck_id)
    is_favorite = did_str in favorites
    fav_attr = ' data-is-fav="1"' if is_favorite else ""

    deck_marks = getattr(ctx, "onigiri_deck_marks", None)
    if deck_marks is None:
        try:
            deck_marks = mw.col.get_config("onigiri_deck_marks") or {}
        except Exception:
            deck_marks = mw.col.conf.get("onigiri_deck_marks", {})
        setattr(ctx, "onigiri_deck_marks", deck_marks)
    mark_colors = conf.get("markerColors", {}) or {}
    default_mark_colors = {
        "red": "#FF4B4B",
        "blue": "#4488FF",
        "green": "#44BB66",
        "yellow": "#FFB800",
    }
    default_mark_colors.update({k: v for k, v in mark_colors.items() if isinstance(v, str) and v})
    mark_colors = default_mark_colors
    mark_key = deck_marks.get(did_str)
    mark_attr = f' data-mark="{mark_key}"' if mark_key in mark_colors else ""
    addon_pkg = getattr(ctx, "onigiri_addon_pkg", None)
    if addon_pkg is None:
        try:
            addon_pkg = mw.addonManager.addonFromModule(__name__)
        except Exception:
            addon_pkg = "1011095603"
        setattr(ctx, "onigiri_addon_pkg", addon_pkg)

    mark_icons = conf.get("markerIcons", {}) or {}
    mark_dot_html = ""
    if mark_key in mark_colors:
        bg_color = mark_colors[mark_key]
        icon_val = mark_icons.get(mark_key, "default")
        if icon_val and icon_val != "default":
            if str(icon_val).startswith("emoji:"):
                emoji_char = icon_val[len("emoji:"):]
                emoji_asset = asset_for_emoji(emoji_char)
                if emoji_asset:
                    icon_url = f"/_addons/{addon_pkg}/system_files/emojis/{emoji_asset}"
                    mark_dot_html = f'<span class="deck-mark-dot" style="background-color:transparent; background-image:url({icon_url}); background-size:contain; background-position:center; background-repeat:no-repeat; border-radius:0; width:14px; height:14px; min-width:14px; min-height:14px;"></span>'
                else:
                    mark_dot_html = f'<span class="deck-mark-dot" style="background-color:transparent; color:{bg_color}; font-size:14px; line-height:1; display:inline-flex; align-items:center; justify-content:center; box-shadow:none; width:auto; height:auto; min-width:auto; min-height:auto;">{emoji_char}</span>'
            else:
                if str(icon_val).startswith("system:"):
                    icon_url = f"/_addons/{addon_pkg}/system_files/system_icons/unavailable_for_users/{icon_val[7:]}"
                else:
                    icon_url = f"/_addons/{addon_pkg}/user_files/icons/{icon_val}"
                mark_dot_html = f'<span class="deck-mark-dot" style="background-color:{bg_color}; -webkit-mask-image:url({icon_url}); mask-image:url({icon_url}); -webkit-mask-size:contain; mask-size:contain; -webkit-mask-position:center; mask-position:center; -webkit-mask-repeat:no-repeat; mask-repeat:no-repeat; border-radius:0;"></span>'
        else:
            mark_dot_html = f'<span class="deck-mark-dot" style="background-color:{bg_color};"></span>'
    
    # --- End Onigiri Favorites ---
    # --- END OF BLOCK ---

    hide_all_deck_counts = conf.get("hideAllDeckCounts", False)

    new_count = node.new_count
    learn_count = node.learn_count
    review_count = node.review_count

    # --- Counts HTML ---
    counts_html = ""
    
    # Enhanced Deck Stats Logic
    # Enhanced Deck Stats Logic
    # 1. Try checking the instance directly (set by our new _render_deck_tree patch or deck_tree_updater)
    enhanced_stats = getattr(self, "_onigiri_enhanced_stats", None)
    
    # 2. Fallback to _render_data if not found (legacy/redundancy)
    if enhanced_stats is None and hasattr(self, "_render_data"):
         enhanced_stats = getattr(self._render_data, "enhanced_stats", None)

    show_enhanced = conf.get("enhancedDeckStats", False)
    
    # Debug Logging
    # print(f"Onigiri Debug: Deck {node.deck_id} | Show: {show_enhanced} | Has Stats: {enhanced_stats is not None} | In Stats: {node.deck_id in enhanced_stats if enhanced_stats else False}")

    
    if not hide_all_deck_counts:
        if show_enhanced and enhanced_stats and node.deck_id in enhanced_stats:
            # --- ENHANCED MODE ---
            stats = enhanced_stats[node.deck_id]
            stats_list = conf.get("enhancedDeckStatsList", ["total", "new", "learn", "review", "buried", "suspended"])
            show_bar = conf.get("enhancedDeckProportionBar", True)
            
            # 1. Stats Grid
            grid_items = []
            for key in stats_list:
                val = stats.get(key, 0)
                label = key.capitalize()
                # Special styling for zero values? Maybe opacity.
                zero_class = " zero" if val == 0 else ""
                grid_items.append(f'<div class="stat-item {key}{zero_class}"><span class="stat-label">{label}</span><span class="stat-value">{val}</span></div>')
            
            stats_grid_html = f'<div class="enhanced-stats-grid">{"".join(grid_items)}</div>'
            
            # 2. Proportion Bar
            bar_html = ""
            if show_bar:
                total = stats.get("total", 0)
                if total > 0:
                    # Calculate percentages
                    p_new = (stats.get("new", 0) / total) * 100
                    p_learn = (stats.get("learn", 0) / total) * 100
                    p_review = (stats.get("review", 0) / total) * 100
                    p_buried = (stats.get("buried", 0) / total) * 100
                    p_suspended = (stats.get("suspended", 0) / total) * 100
                    
                    # Build bar segments
                    segments = []
                    if p_new > 0: segments.append(f'<div class="bar-segment new" style="width: {p_new}%;"></div>')
                    if p_learn > 0: segments.append(f'<div class="bar-segment learn" style="width: {p_learn}%;"></div>')
                    if p_review > 0: segments.append(f'<div class="bar-segment review" style="width: {p_review}%;"></div>')
                    if p_buried > 0: segments.append(f'<div class="bar-segment buried" style="width: {p_buried}%;"></div>')
                    if p_suspended > 0: segments.append(f'<div class="bar-segment suspended" style="width: {p_suspended}%;"></div>')
                    
                    bar_html = f'<div class="enhanced-proportion-bar">{"".join(segments)}</div>'
                else:
                    bar_html = '<div class="enhanced-proportion-bar empty"></div>'
            
            # Combine into a container that uses container queries
            counts_html = f"""
            <div class="enhanced-deck-info">
                 <div class="standard-counts">
                    <span class="new-count-bubble{' zero' if new_count == 0 else ''}">{new_count}</span>
                    <span class="learn-count-bubble{' zero' if learn_count == 0 else ''}">{learn_count}</span>
                    <span class="review-count-bubble{' zero' if review_count == 0 else ''}">{review_count}</span>
                 </div>
                 <div class="expanded-details">
                    {stats_grid_html}
                    {bar_html}
                 </div>
            </div>
            """
        else:
            # --- STANDARD MODE ---
            counts_html_parts = []
            counts_html_parts.append(f'<span class="new-count-bubble{" zero" if new_count == 0 else ""}">{new_count}</span>')
            counts_html_parts.append(f'<span class="learn-count-bubble{" zero" if learn_count == 0 else ""}">{learn_count}</span>')
            counts_html_parts.append(f'<span class="review-count-bubble{" zero" if review_count == 0 else ""}">{review_count}</span>')
            counts_html = '<div class="deck-counts">' + ''.join(counts_html_parts) + '</div>'
    # --- Counts HTML ---

    def indent():
        mode = conf.get("deck_indentation_mode", "default")
        
        if mode == "default":
            return "&nbsp;" * 6 * (node.level - 1)
            
        custom_px = conf.get("deck_indentation_custom_px", 20)
        step = 20
        if mode == "smaller":
            step = 10
        elif mode == "bigger":
            step = 40
        elif mode == "custom":
            step = int(custom_px)

        px = step * (node.level - 1)
        if px <= 0:
            return ""
            
        return f"<span style='display:inline-block; width:{px}px;'></span>"

    klass = "deck current" if node.deck_id == ctx.current_deck_id else "deck"
    
    # Determine precise deck type for styling
    # Priority: 1) node.filtered (direct from tree node), 2) DB lookup
    is_filtered = False
    
    # First, try the direct node property (most reliable in modern Anki)
    if hasattr(node, 'filtered'):
        is_filtered = bool(node.filtered)
    
    # Fallback: database lookup if node.filtered not available or returned False
    if not is_filtered:
        try:
            did = int(node.deck_id)
            deck_obj = mw.col.decks.get(did)
            if deck_obj:
                if isinstance(deck_obj, dict):
                    is_filtered = bool(deck_obj.get("dyn", 0))
                elif hasattr(deck_obj, "dyn"):
                    is_filtered = bool(deck_obj.dyn)
        except Exception:
            pass  # Keep is_filtered as False
    
    if is_filtered:
        deck_type_class = "is-filtered"
    elif node.children:
        deck_type_class = "is-folder"
    elif node.level > 1:
        deck_type_class = "is-subdeck"
    else:
        deck_type_class = "is-deck"

    buf.append(f"<tr class='{klass} {deck_type_class}' id='{node.deck_id}' data-did='{node.deck_id}'{fav_attr}{mark_attr}>")

    if node.children:
        collapse_link = f"<a class='collapse {state_class}' href=# onclick='return pycmd(\"onigiri_collapse:{node.deck_id}\")'>{prefix}</a>"
    else:
        collapse_link = "<span class=collapse></span>"

    # Removed class='deck-prefix' as requested by user
    deck_prefix = f"<span>{indent()}{collapse_link}</span>"
    extraclass = "filtered" if node.filtered else ""
    display_name = html.escape(node.name.split("::")[-1])

    # --- START MODIFICATION: Update colspan and add counts_html ---
    buf.append(f"""
    <td class=decktd colspan=7>
        <div class="deck-info">
            {deck_prefix}
            <a class="deck {extraclass}" href=# onclick="return OnigiriEngine.openDeck(event, '{node.deck_id}');">
                <span class="deck-name">{display_name}</span>{mark_dot_html}
            </a>
        </div>
        {counts_html}
    </td>
    """)
    # --- END MODIFICATION ---

    # --- START MODIFICATION: Remove old count columns ---
    # The old count tds are removed from here.
    # --- END MODIFICATION ---

    buf.append(f"""
    <td align=center class=opts>
      <a onclick='pycmd("opts:{node.deck_id}"); return false;'>
        <img src='/_anki/imgs/gears.svg' class=gears>
      </a>
    </td>
    </tr>""")

    if not node.collapsed:
        for child in node.children:
            buf.append(self._render_deck_node(child, ctx))

    return "".join(buf) # Join the list into a single string at the end
    
def _on_sync_did_finish():
    """Removes the syncing animation from the sync button."""
    try:
        if mw.state == "deckBrowser" and hasattr(mw.deckBrowser, 'web') and mw.deckBrowser.web:
            mw.deckBrowser.web.eval("SyncStatusManager.setSyncing(false);")
        elif mw.state == "overview" and hasattr(mw.overview, 'web') and mw.overview.web:
             mw.overview.web.eval("SyncStatusManager.setSyncing(false);")
    except Exception as e:
        print(f"Onigiri: Error stopping sync animation: {e}")

def apply_patches():
    """
    Applies all legacy method patches (wrapping).
    """
    # ... (existing patches)
    
    # Menu styling disabled per user request
    # apply_menu_styling()
    
    # Menu patching disabled per user request
    # patch_qmenu()
    """Apply all patches to Anki's UI."""
    # Register the reviewer_did_answer_card hook
    from aqt import gui_hooks
    gui_hooks.sync_did_finish.append(_on_sync_did_finish)
    gui_hooks.reviewer_did_answer_card.append(on_reviewer_did_answer_card)
    
    # NOTE: DeckBrowser._render_deck_node is patched at top-level in __init__.py
    # to ensure it's applied before the first render (main_window_did_init is too late)
    
    # Patch the overview page
    # REMOVED: Called explicitly in __init__.py when profile is loaded to ensure mw.col exists
    # patch_overview()
    
    # Patch the congrats page
    # REMOVED: Called explicitly in __init__.py at top-level to ensure correct hook order
    # patch_congrats_page()
    
    # Patch the webview to handle our custom messages
    # REMOVED: This hook is already registered in __init__.py line 292
    # Keeping this line would cause double registration and duplicate dialogs
    # gui_hooks.webview_did_receive_js_message.append(on_webview_js_message)
    
    # Add hook for toolbar visibility changes
    gui_hooks.state_did_change.append(_update_toolbar_visibility)

    # Reviewer header progress bar. `did_show_question` is the repaint point:
    # by then the scheduler has re-counted, so the gauge and Anki's bottom bar
    # are always reading the same numbers.
    gui_hooks.state_did_change.append(_on_reviewer_progress_state_change)
    gui_hooks.reviewer_did_answer_card.append(_on_reviewer_progress_answered)
    gui_hooks.reviewer_did_show_question.append(_on_reviewer_progress_show_question)
    
    # Mark the hook as registered and update toolbar state
    mw._onigiri_restaurant_hook_registered = True
    mw.progress.single_shot(0, lambda: _update_toolbar_visibility(mw.state, "startup"))



def generate_reviewer_buttons_css(conf):
    """Generates CSS/JS for Onigiri reviewer bottom-bar buttons."""
    css = []
    scripts = []

    if conf.get("maxHide", False):
        return "<style>#outer { display: none !important; }</style>"

    custom_enabled = conf.get("onigiri_reviewer_btn_custom_enabled", True)
    radius = conf.get("onigiri_reviewer_btn_radius", 12)
    padding = conf.get("onigiri_reviewer_btn_padding", 5)
    btn_height = conf.get("onigiri_reviewer_btn_height", 40)
    bar_height = _reviewer_bottom_bar_height_px(conf)

    stattxt_mode = conf.get("onigiri_reviewer_stattxt_mode", "hover")
    if stattxt_mode not in {"hover", "inverted", "fixed", "off"}:
        stattxt_mode = "hover"
    interval_visible = stattxt_mode != "off"
    interval_color_light = conf.get("onigiri_reviewer_stattxt_color_light", "#666666")
    interval_color_dark = conf.get("onigiri_reviewer_stattxt_color_dark", "#aaaaaa")
    hover_numbers_display = "inline-flex" if interval_visible else "none"
    # Pre-answer counts (New/Learn/Review pills on the Show Answer button):
    # "fixed"    keeps them permanently visible (stacked under the label).
    # "inverted" shows them at rest and swaps them for the "Show Answer" label
    #            on hover - the mirror image of the default "hover" behavior.
    counts_shown_at_rest = stattxt_mode in ("fixed", "inverted")
    pre_answer_counts_base_opacity = "1" if counts_shown_at_rest else "0"
    pre_answer_counts_base_visibility = "visible" if counts_shown_at_rest else "hidden"
    pre_answer_counts_base_transform = "scale(1)" if counts_shown_at_rest else "scale(0.97)"
    # On hover every mode reveals/keeps the counts except "inverted", which hides
    # them again so the "Show Answer" label can take their place.
    pre_answer_counts_hover_opacity = "0" if stattxt_mode == "inverted" else "1"
    pre_answer_counts_hover_visibility = "hidden" if stattxt_mode == "inverted" else "visible"
    pre_answer_counts_hover_transform = "scale(0.97)" if stattxt_mode == "inverted" else "scale(1)"
    # "Show Answer" label. "inverted" hides it at rest (counts take its place)
    # and reveals it on hover; every other mode keeps it visible at rest.
    # On hover only plain "hover" fades the label out.
    show_answer_label_base_opacity = "0" if stattxt_mode == "inverted" else "1"
    show_answer_label_hover_opacity = "0" if stattxt_mode == "hover" else "1"
    # Ease button (Again/Hard/Good/Easy) label + interval number:
    # "hover"    swaps label -> number on hover (absolute overlay, legacy behavior).
    # "inverted" swaps number -> label on hover (the same overlay, reversed).
    # "fixed"    stacks label + number in normal flow, both always visible.
    # "off"      never shows the number.
    number_shown_at_rest = stattxt_mode in ("fixed", "inverted")
    answer_label_base_opacity = "0" if stattxt_mode == "inverted" else "1"
    answer_label_hover_opacity = "0" if stattxt_mode == "hover" else "1"
    answer_number_base_opacity = "1" if number_shown_at_rest else "0"
    answer_number_base_visibility = "visible" if number_shown_at_rest else "hidden"
    if stattxt_mode == "hover":
        answer_number_hover_opacity = "1"
        answer_number_hover_visibility = "visible"
    elif stattxt_mode == "inverted":
        answer_number_hover_opacity = "0"
        answer_number_hover_visibility = "hidden"
    else:
        answer_number_hover_opacity = answer_number_base_opacity
        answer_number_hover_visibility = answer_number_base_visibility
    answer_number_position = "static" if stattxt_mode == "fixed" else "absolute"
    answer_number_inset = "auto" if stattxt_mode == "fixed" else "0"
    # Overlay swap transforms: the "hidden" side rests slightly offset/scaled and
    # eases into place. "inverted" is shown at rest, so its base/hover transforms
    # are the reverse of "hover"; "fixed" is stacked and never transforms.
    if stattxt_mode == "fixed":
        answer_number_transform = "none"
        answer_number_hover_transform = "none"
    elif stattxt_mode == "inverted":
        answer_number_transform = "translateY(0) scale(1)"
        answer_number_hover_transform = "translateY(1px) scale(0.98)"
    else:
        answer_number_transform = "translateY(1px) scale(0.98)"
        answer_number_hover_transform = "translateY(0) scale(1)"
    answer_number_font_size = "0.66em" if stattxt_mode == "fixed" else "var(--onigiri-answer-number-font-size, 1em)"
    answer_hover_number_color_light = "currentColor" if str(interval_color_light).lower() == "#666666" else interval_color_light
    answer_hover_number_color_dark = "currentColor" if str(interval_color_dark).lower() == "#aaaaaa" else interval_color_dark
    native_number_display = "none" if custom_enabled else ("none" if stattxt_mode == "off" else "inline-block")

    # Timer adaptation (Anki deck options "Show answer timer"):
    # "right"/"left" show a neutral pill inside the Show Answer button, alongside the
    # New/Learn/Review counts. "out" moves the timer to the bottom bar itself, styled
    # like the other bottom-bar buttons (Edit/More), just to the left of Edit.
    timer_position = conf.get("onigiri_reviewer_timer_position", "right")
    if timer_position not in {"right", "left", "out", "off"}:
        timer_position = "right"
    timer_bg_light = conf.get("onigiri_reviewer_timer_bg_light", "#e5e5e5")
    timer_text_light = conf.get("onigiri_reviewer_timer_text_light", "#2c2c2c")
    timer_bg_dark = conf.get("onigiri_reviewer_timer_bg_dark", "#3a3a3a")
    timer_text_dark = conf.get("onigiri_reviewer_timer_text_dark", "#e0e0e0")

    # Stats bar background: the Show Answer button's own background while the
    # timer + New/Learn/Review pills panel is visible. Defaults to mirroring the
    # "Other" hover background so existing setups look unchanged; can be
    # decoupled into its own color via onigiri_reviewer_show_answer_bar_bg_sync.
    if conf.get("onigiri_reviewer_show_answer_bar_bg_sync", True):
        show_answer_bar_bg_light = conf.get("onigiri_reviewer_other_btn_hover_bg_light", "#2c2c2c")
        show_answer_bar_bg_dark = conf.get("onigiri_reviewer_other_btn_hover_bg_dark", "#e0e0e0")
    else:
        show_answer_bar_bg_light = conf.get("onigiri_reviewer_show_answer_bar_bg_light", "#2c2c2c")
        show_answer_bar_bg_dark = conf.get("onigiri_reviewer_show_answer_bar_bg_dark", "#e0e0e0")
    # Text must ride along with the stats bar background (not the button's idle
    # text color) so the "Show Answer" label stays legible against it in "fixed"
    # mode, where the button is never actually in its native :hover state.
    show_answer_bar_text_light = conf.get("onigiri_reviewer_other_btn_hover_text_light", "#f0f0f0")
    show_answer_bar_text_dark = conf.get("onigiri_reviewer_other_btn_hover_text_dark", "#3a3a3a")

    overview_style = conf.get("overview_style", {}) if isinstance(conf.get("overview_style", {}), dict) else {}
    overview_colors = overview_style.get("colors", {}) if isinstance(overview_style.get("colors", {}), dict) else {}
    palette_colors = conf.get("colors", {}) if isinstance(conf.get("colors", {}), dict) else {}

    def _overview_count_color(mode, overview_key, palette_key, fallback):
        mode_colors = overview_colors.get(mode, {}) if isinstance(overview_colors.get(mode, {}), dict) else {}
        palette_mode = palette_colors.get(mode, {}) if isinstance(palette_colors.get(mode, {}), dict) else {}
        return mode_colors.get(overview_key) or palette_mode.get(palette_key) or fallback

    css.append(f"""
        :root {{
            --onigiri-reviewer-new-count-bg: {_overview_count_color("light", "new_bubble", "--new-count-bubble-bg", "#1e8cff")};
            --onigiri-reviewer-new-count-fg: {_overview_count_color("light", "new_text", "--new-count-bubble-fg", "#ffffff")};
            --onigiri-reviewer-learn-count-bg: {_overview_count_color("light", "learn_bubble", "--learn-count-bubble-bg", "#ff5757")};
            --onigiri-reviewer-learn-count-fg: {_overview_count_color("light", "learn_text", "--learn-count-bubble-fg", "#ffffff")};
            --onigiri-reviewer-review-count-bg: {_overview_count_color("light", "review_bubble", "--review-count-bubble-bg", "#19c96b")};
            --onigiri-reviewer-review-count-fg: {_overview_count_color("light", "review_text", "--review-count-bubble-fg", "#ffffff")};
            --onigiri-answer-hover-number-color: {answer_hover_number_color_light};
        }}

        .nightMode,
        .night-mode {{
            --onigiri-reviewer-new-count-bg: {_overview_count_color("dark", "new_bubble", "--new-count-bubble-bg", "#0a84ff")};
            --onigiri-reviewer-new-count-fg: {_overview_count_color("dark", "new_text", "--new-count-bubble-fg", "#f7fbff")};
            --onigiri-reviewer-learn-count-bg: {_overview_count_color("dark", "learn_bubble", "--learn-count-bubble-bg", "#ff453a")};
            --onigiri-reviewer-learn-count-fg: {_overview_count_color("dark", "learn_text", "--learn-count-bubble-fg", "#fff5f5")};
            --onigiri-reviewer-review-count-bg: {_overview_count_color("dark", "review_bubble", "--review-count-bubble-bg", "#12b765")};
            --onigiri-reviewer-review-count-fg: {_overview_count_color("dark", "review_text", "--review-count-bubble-fg", "#f4fff8")};
            --onigiri-answer-hover-number-color: {answer_hover_number_color_dark};
        }}

        body .stattxt:not(.onigiri-count-pill),
        body .nobold:not(.onigiri-answer-hover-number) {{
            color: {interval_color_light} !important;
            opacity: 0.9 !important;
            font-weight: normal !important;
            font-size: 0.9em !important;
            display: {native_number_display} !important;
        }}

        .nightMode body .stattxt:not(.onigiri-count-pill),
        .nightMode body .nobold:not(.onigiri-answer-hover-number),
        .night-mode body .stattxt:not(.onigiri-count-pill),
        .night-mode body .nobold:not(.onigiri-answer-hover-number) {{
            color: {interval_color_dark} !important;
        }}

        #outer .onigiri-stattxt-source,
        .onigiri-stattxt-source,
        #outer .onigiri-native-number-source,
        .onigiri-native-number-source,
        #outer .onigiri-native-number-host,
        .onigiri-native-number-host,
        #outer .onigiri-native-number-empty-cell,
        .onigiri-native-number-empty-cell,
        #outer tr.onigiri-native-number-empty-row,
        tr.onigiri-native-number-empty-row {{
            display: none !important;
            width: 0 !important;
            height: 0 !important;
            max-width: 0 !important;
            max-height: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
            border: 0 !important;
            overflow: hidden !important;
            opacity: 0 !important;
            pointer-events: none !important;
        }}

        #outer button.onigiri-show-answer-btn {{
            position: relative !important;
            overflow: visible !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
        }}

        #outer button.onigiri-show-answer-btn.onigiri-has-pre-answer-counts {{
            min-width: min(74vw, 360px) !important;
        }}

        #outer .onigiri-show-answer-label {{
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            width: 100% !important;
            transition: opacity 0.16s ease !important;
        }}

        button[data-onigiri-ease] .onigiri-answer-label,
        #outer button[data-onigiri-ease] .onigiri-answer-label {{
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            width: 100% !important;
            opacity: {answer_label_base_opacity} !important;
            transition: opacity 90ms ease-out !important;
            animation: none !important;
        }}

        #outer .onigiri-pre-answer-counts {{
            position: absolute !important;
            inset: 6px !important;
            display: {hover_numbers_display} !important;
            align-items: center !important;
            justify-content: center !important;
            gap: 7px !important;
            padding: 0 !important;
            opacity: {pre_answer_counts_base_opacity} !important;
            visibility: {pre_answer_counts_base_visibility} !important;
            pointer-events: none !important;
            transform: {pre_answer_counts_base_transform} !important;
            transition: opacity 0.16s ease, transform 0.16s ease, visibility 0s linear 0.16s !important;
            z-index: 2 !important;
        }}

        #outer button.onigiri-show-answer-btn.onigiri-has-pre-answer-counts .onigiri-show-answer-label {{
            opacity: {show_answer_label_base_opacity} !important;
        }}

        #outer button.onigiri-show-answer-btn.onigiri-has-pre-answer-counts:hover .onigiri-show-answer-label {{
            opacity: {show_answer_label_hover_opacity} !important;
        }}

        #outer button.onigiri-show-answer-btn.onigiri-has-pre-answer-counts:hover .onigiri-pre-answer-counts {{
            opacity: {pre_answer_counts_hover_opacity} !important;
            visibility: {pre_answer_counts_hover_visibility} !important;
            transform: {pre_answer_counts_hover_transform} !important;
            transition-delay: 0s !important;
        }}

        #outer .onigiri-count-pill {{
            flex: 1 1 0 !important;
            min-width: 54px !important;
            height: 100% !important;
            border-radius: 999px !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            padding: 0 12px !important;
            font-weight: 800 !important;
            font-size: clamp(13px, 0.95em, 19px) !important;
            line-height: 1 !important;
            box-sizing: border-box !important;
            white-space: nowrap !important;
        }}

        #outer .onigiri-count-pill-new {{
            background: var(--onigiri-reviewer-new-count-bg) !important;
            color: var(--onigiri-reviewer-new-count-fg) !important;
        }}

        #outer .onigiri-count-pill-learn {{
            background: var(--onigiri-reviewer-learn-count-bg) !important;
            color: var(--onigiri-reviewer-learn-count-fg) !important;
        }}

        #outer .onigiri-count-pill-review {{
            background: var(--onigiri-reviewer-review-count-bg) !important;
            color: var(--onigiri-reviewer-review-count-fg) !important;
        }}

        /* The active card type is shown as a tiny dot inside its matching
           New/Learning/To Review box. */
        #outer .onigiri-count-pill.is-current-card {{
            gap: 5px !important;
        }}

        #outer .stat2 .onigiri-count-pill.is-current-card::before,
        #outer .onigiri-count-pill.is-current-card::before {{
            content: "" !important;
            display: inline-block !important;
            flex: 0 0 6px !important;
            width: 6px !important;
            height: 6px !important;
            border-radius: 50% !important;
            background: currentColor !important;
            box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.7) !important;
            pointer-events: none !important;
        }}

        /* Timer adaptation: neutral pill shown inside the Show Answer button
           (position "right"/"left"), grouped alongside the New/Learn/Review pills. */
        :root {{
            --onigiri-reviewer-timer-bg: {timer_bg_light};
            --onigiri-reviewer-timer-fg: {timer_text_light};
        }}

        .nightMode, .night-mode {{
            --onigiri-reviewer-timer-bg: {timer_bg_dark};
            --onigiri-reviewer-timer-fg: {timer_text_dark};
        }}

        #outer .onigiri-timer-pill {{
            flex: 1 1 0 !important;
            min-width: 54px !important;
            height: 100% !important;
            border-radius: 999px !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            padding: 0 12px !important;
            font-weight: 800 !important;
            font-size: clamp(13px, 0.95em, 19px) !important;
            line-height: 1 !important;
            box-sizing: border-box !important;
            white-space: nowrap !important;
            background: var(--onigiri-reviewer-timer-bg) !important;
            color: var(--onigiri-reviewer-timer-fg) !important;
        }}

        /* Timer adaptation: position "out" moves the timer into the bottom bar,
           to the left of Edit, styled exactly like the other bottom-bar buttons. */
        #outer .onigiri-timer-out-btn {{
            pointer-events: none !important;
            cursor: default !important;
        }}

        button[data-onigiri-ease],
        #outer button[data-onigiri-ease] {{
            position: relative !important;
            overflow: hidden !important;
            width: var(--onigiri-answer-button-width, auto) !important;
            min-width: var(--onigiri-answer-button-width, 0px) !important;
            max-width: var(--onigiri-answer-button-width, none) !important;
            flex: 0 0 var(--onigiri-answer-button-width, auto) !important;
            transform: none !important;
            transition: none !important;
            animation: none !important;
            box-shadow: none !important;
        }}

        button[data-onigiri-ease] *:not(.onigiri-answer-label):not(.onigiri-answer-hover-number),
        #outer button[data-onigiri-ease] *:not(.onigiri-answer-label):not(.onigiri-answer-hover-number) {{
            transition: none !important;
            animation: none !important;
        }}

        button[data-onigiri-ease] .onigiri-answer-hover-number,
        #outer button[data-onigiri-ease] .onigiri-answer-hover-number {{
            position: {answer_number_position} !important;
            inset: {answer_number_inset} !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            width: 100% !important;
            min-width: 0 !important;
            max-width: 100% !important;
            padding: 0 8px !important;
            box-sizing: border-box !important;
            opacity: {answer_number_base_opacity} !important;
            visibility: {answer_number_base_visibility} !important;
            transform: {answer_number_transform} !important;
            color: var(--onigiri-answer-hover-number-color, currentColor) !important;
            font-weight: 800 !important;
            font-size: {answer_number_font_size} !important;
            line-height: 1 !important;
            white-space: nowrap !important;
            transition: opacity 110ms ease-out, transform 110ms ease-out, visibility 0s linear 110ms !important;
            animation: none !important;
        }}

        button[data-onigiri-ease]:hover .onigiri-answer-label,
        #outer button[data-onigiri-ease]:hover .onigiri-answer-label {{
            opacity: {answer_label_hover_opacity} !important;
        }}

        button[data-onigiri-ease]:hover .onigiri-answer-hover-number,
        #outer button[data-onigiri-ease]:hover .onigiri-answer-hover-number {{
            opacity: {answer_number_hover_opacity} !important;
            visibility: {answer_number_hover_visibility} !important;
            transform: {answer_number_hover_transform} !important;
            transition-delay: 0s !important;
        }}
    """)

    if stattxt_mode == "fixed":
        # Stack "Show Answer" above the New/Learn/Review counts instead of
        # the hover swap-overlay used by "hover"/"inverted" mode.
        pre_answer_counts_fixed_height = max(16, int(btn_height * 0.5))
        css.append(f"""
        #outer .onigiri-pre-answer-counts {{
            position: static !important;
            inset: auto !important;
            width: 100% !important;
            height: {pre_answer_counts_fixed_height}px !important;
            margin: 2px 0 0 0 !important;
        }}
        """)

    if stattxt_mode in ("fixed", "inverted"):
        # Both modes keep the counts panel visible without hovering, so the
        # Show Answer button needs the stats bar background at all times, not
        # just on :hover. ("inverted" swaps counts for the label on hover but
        # keeps the same background so the transition stays seamless.)
        css.append(f"""
        #outer button.onigiri-show-answer-btn.onigiri-has-pre-answer-counts:not([onclick*="ease"]):not([data-cmd*="ease"]):not([data-onigiri-ease]) {{
            background: {show_answer_bar_bg_light} !important;
            background-color: {show_answer_bar_bg_light} !important;
            color: {show_answer_bar_text_light} !important;
        }}

        .nightMode #outer button.onigiri-show-answer-btn.onigiri-has-pre-answer-counts:not([onclick*="ease"]):not([data-cmd*="ease"]):not([data-onigiri-ease]) {{
            background: {show_answer_bar_bg_dark} !important;
            background-color: {show_answer_bar_bg_dark} !important;
            color: {show_answer_bar_text_dark} !important;
        }}
        """)

    if custom_enabled:
        css.append(f"""
        :root {{
            --onigiri-reviewer-bottom-bar-height: {bar_height}px;
        }}

        html, body {{
             height: var(--onigiri-reviewer-bottom-bar-height) !important;
             min-height: var(--onigiri-reviewer-bottom-bar-height) !important;
             max-height: var(--onigiri-reviewer-bottom-bar-height) !important;
             margin: 0 !important;
             padding: 0 !important;
             overflow: hidden !important;
        }}

        #outer {{
             height: var(--onigiri-reviewer-bottom-bar-height) !important;
             min-height: {bar_height}px !important;
             max-height: {bar_height}px !important;
             display: block !important;
             width: 100% !important;
             margin: 0 !important;
             padding: 0 !important;
             overflow: hidden !important;
             border: 0 !important;
             box-sizing: border-box !important;
        }}

        #outer > table {{
            width: 100% !important;
            height: 100% !important;
            min-height: 100% !important;
            display: table !important;
            border-collapse: collapse !important;
            background: transparent !important;
            background-color: transparent !important;
            border: 0 !important;
        }}

        #outer > table > tbody {{
            display: table-row-group !important;
            width: 100% !important;
            height: 100% !important;
            background: transparent !important;
            background-color: transparent !important;
            border: 0 !important;
        }}

        #outer > table tr {{
            display: flex !important;
            width: 100% !important;
            height: 100% !important;
            min-height: 100% !important;
            align-items: center !important;
            justify-content: space-between !important;
            background: transparent !important;
            background-color: transparent !important;
            border: 0 !important;
        }}

        /* Catch-all: vertically center EVERY top-level cell (including buttons
           injected by other add-ons such as Ankimon's "Defeat/Catch Pokemon"),
           so they line up with Show Answer instead of floating to the top of the
           row. Scoped to direct row children so nested tables inside the ease
           buttons are left untouched. */
        #outer > table > tbody > tr > td {{
            display: flex !important;
            flex: 0 0 auto !important;
            align-items: center !important;
            justify-content: center !important;
            height: 100% !important;
            background: transparent !important;
            background-color: transparent !important;
            border: 0 !important;
        }}

        #outer > table td:first-child {{
            display: flex !important;
            flex: 1 !important;
            justify-content: flex-start !important;
            align-items: center !important;
            padding-left: 10px !important;
            width: auto !important;
            height: 100% !important;
            background: transparent !important;
            background-color: transparent !important;
            border: 0 !important;
        }}

        #outer > table td:last-child {{
            display: flex !important;
            flex: 1 !important;
            justify-content: flex-end !important;
            align-items: center !important;
            padding-right: 10px !important;
            width: auto !important;
            height: 100% !important;
            background: transparent !important;
            background-color: transparent !important;
            border: 0 !important;
        }}

        #outer > table td:nth-child(2) {{
            display: flex !important;
            flex: 0 0 auto !important;
            justify-content: center !important;
            align-items: center !important;
            width: auto !important;
            height: 100% !important;
            background: transparent !important;
            background-color: transparent !important;
            border: 0 !important;
        }}

        button {{
            border: 2px solid transparent !important;
            border-radius: {radius}px !important;
            box-shadow: none !important;
            /* Only color/background transition (quick hover feedback) - no
               width/height/transform animation, so the Show Answer -> ease
               buttons swap (and any button resize from width-locking) is instant
               instead of visibly shrinking/growing. */
            transition: background-color 0.08s ease, color 0.08s ease, border-color 0.08s ease, transform 0.08s ease !important;
            box-sizing: border-box !important;
            cursor: pointer !important;
            padding: {padding}px 15px !important;
            margin: 0 5px !important;
            height: {btn_height}px !important;
            min-height: {btn_height}px !important;
        }}

        #outer button[data-onigiri-ease],
        #outer button[onclick*="ease"],
        #outer button[data-cmd*="ease"],
        #outer button[id^="ease"] {{
            transition: none !important;
            animation: none !important;
            transform: none !important;
            box-shadow: none !important;
        }}

        #outer button[data-onigiri-ease] *:not(.onigiri-answer-label):not(.onigiri-answer-hover-number),
        #outer button[onclick*="ease"] *:not(.onigiri-answer-label):not(.onigiri-answer-hover-number),
        #outer button[data-cmd*="ease"] *:not(.onigiri-answer-label):not(.onigiri-answer-hover-number),
        #outer button[id^="ease"] *:not(.onigiri-answer-label):not(.onigiri-answer-hover-number) {{
            transition: none !important;
            animation: none !important;
        }}

        #outer button[data-onigiri-ease]:hover,
        #outer button[onclick*="ease"]:hover,
        #outer button[data-cmd*="ease"]:hover,
        #outer button[id^="ease"]:hover {{
            transform: none !important;
            transition: none !important;
            animation: none !important;
            box-shadow: none !important;
        }}

        #outer button:not([onclick*="ease"]):not([data-cmd*="ease"]):not([data-onigiri-ease]) {{
            background: {conf.get("onigiri_reviewer_other_btn_bg_light", "#f0f0f0")} !important;
            background-color: {conf.get("onigiri_reviewer_other_btn_bg_light", "#f0f0f0")} !important;
            background-image: none !important;
            color: {conf.get("onigiri_reviewer_other_btn_text_light", "#2c2c2c")} !important;
        }}

        #outer button:not([onclick*="ease"]):not([data-cmd*="ease"]):not([data-onigiri-ease]):hover {{
            background: {conf.get("onigiri_reviewer_other_btn_hover_bg_light", "#2c2c2c")} !important;
            background-color: {conf.get("onigiri_reviewer_other_btn_hover_bg_light", "#2c2c2c")} !important;
            background-image: none !important;
            color: {conf.get("onigiri_reviewer_other_btn_hover_text_light", "#f0f0f0")} !important;
            transform: translateY(-2px) !important;
            box-shadow: none !important;
        }}

        .nightMode #outer button:not([onclick*="ease"]):not([data-cmd*="ease"]):not([data-onigiri-ease]) {{
            background: {conf.get("onigiri_reviewer_other_btn_bg_dark", "#3a3a3a")} !important;
            background-color: {conf.get("onigiri_reviewer_other_btn_bg_dark", "#3a3a3a")} !important;
            background-image: none !important;
            color: {conf.get("onigiri_reviewer_other_btn_text_dark", "#e0e0e0")} !important;
        }}

        .nightMode #outer button:not([onclick*="ease"]):not([data-cmd*="ease"]):not([data-onigiri-ease]):hover {{
            background: {conf.get("onigiri_reviewer_other_btn_hover_bg_dark", "#e0e0e0")} !important;
            background-color: {conf.get("onigiri_reviewer_other_btn_hover_bg_dark", "#e0e0e0")} !important;
            background-image: none !important;
            color: {conf.get("onigiri_reviewer_other_btn_hover_text_dark", "#3a3a3a")} !important;
            transform: translateY(-2px) !important;
            box-shadow: none !important;
        }}

        /* Stats bar background: overrides the generic "Other" hover background
           above, specifically for the Show Answer button while its pre-answer
           counts panel is present. */
        #outer button.onigiri-show-answer-btn.onigiri-has-pre-answer-counts:not([onclick*="ease"]):not([data-cmd*="ease"]):not([data-onigiri-ease]):hover {{
            background: {show_answer_bar_bg_light} !important;
            background-color: {show_answer_bar_bg_light} !important;
            color: {show_answer_bar_text_light} !important;
        }}

        .nightMode #outer button.onigiri-show-answer-btn.onigiri-has-pre-answer-counts:not([onclick*="ease"]):not([data-cmd*="ease"]):not([data-onigiri-ease]):hover {{
            background: {show_answer_bar_bg_dark} !important;
            background-color: {show_answer_bar_bg_dark} !important;
            color: {show_answer_bar_text_dark} !important;
        }}

        button:active {{
            transform: translateY(0);
            box-shadow: none !important;
        }}

        button[onclick*="ease"], button[data-cmd*="ease"], button[data-onigiri-ease] {{
            overflow: hidden !important;
            position: relative !important;
            width: var(--onigiri-answer-button-width, auto) !important;
            min-width: var(--onigiri-answer-button-width, 0px) !important;
            max-width: var(--onigiri-answer-button-width, none) !important;
            flex: 0 0 var(--onigiri-answer-button-width, auto) !important;
            display: inline-flex !important;
            flex-direction: column !important;
            justify-content: center !important;
            align-items: center !important;
            transition: none !important;
            animation: none !important;
            transform: none !important;
            box-shadow: none !important;
        }}

        button[onclick*="ease"] table, button[onclick*="ease"] tr, button[onclick*="ease"] td,
        button[data-cmd*="ease"] table, button[data-cmd*="ease"] tr, button[data-cmd*="ease"] td,
        button[data-onigiri-ease] table, button[data-onigiri-ease] tr, button[data-onigiri-ease] td {{
            background: transparent !important;
            border: none !important;
            margin: 0 !important;
            padding: 0 !important;
            color: inherit !important;
        }}
        """)

        defaults = {
            "again": ("#ffb3b3", "#4d0000", "#ffcccb", "#4a0000"),
            "hard": ("#ffe0b3", "#4d2600", "#ffd699", "#4d1d00"),
            "good": ("#b3ffb3", "#004d00", "#90ee90", "#004000"),
            "easy": ("#b3d9ff", "#00264d", "#add8e6", "#002952"),
        }
        for ease, key in {"1": "again", "2": "hard", "3": "good", "4": "easy"}.items():
            def_bg_l, def_txt_l, def_bg_d, def_txt_d = defaults[key]
            bg_light = conf.get(f"onigiri_reviewer_btn_{key}_bg_light", def_bg_l)
            text_light = conf.get(f"onigiri_reviewer_btn_{key}_text_light", def_txt_l)
            bg_dark = conf.get(f"onigiri_reviewer_btn_{key}_bg_dark", def_bg_d)
            text_dark = conf.get(f"onigiri_reviewer_btn_{key}_text_dark", def_txt_d)
            css.append(f"""
            #outer button[data-onigiri-ease="{ease}"],
            #outer button[onclick*="ease{ease}"],
            #outer button[data-cmd="ease{ease}"],
            #outer #ease{ease} {{
                background: {bg_light} !important;
                background-color: {bg_light} !important;
                background-image: none !important;
                color: {text_light} !important;
            }}
            #outer button[data-onigiri-ease="{ease}"]:hover,
            #outer button[onclick*="ease{ease}"]:hover,
            #outer button[data-cmd="ease{ease}"]:hover,
            #outer #ease{ease}:hover {{
                background: {bg_light} !important;
                background-color: {bg_light} !important;
                background-image: none !important;
                color: {text_light} !important;
                cursor: pointer !important;
                transition: none !important;
                animation: none !important;
                transform: none !important;
                box-shadow: none !important;
            }}

            .nightMode #outer button[data-onigiri-ease="{ease}"],
            .nightMode #outer button[onclick*="ease{ease}"],
            .nightMode #outer button[data-cmd="ease{ease}"],
            .nightMode #outer #ease{ease} {{
                background: {bg_dark} !important;
                background-color: {bg_dark} !important;
                background-image: none !important;
                color: {text_dark} !important;
            }}
            .nightMode #outer button[data-onigiri-ease="{ease}"]:hover,
            .nightMode #outer button[onclick*="ease{ease}"]:hover,
            .nightMode #outer button[data-cmd="ease{ease}"]:hover,
            .nightMode #outer #ease{ease}:hover {{
                background: {bg_dark} !important;
                background-color: {bg_dark} !important;
                background-image: none !important;
                color: {text_dark} !important;
                transition: none !important;
                animation: none !important;
                transform: none !important;
                box-shadow: none !important;
            }}
            """)

        _pre_answer_counts_script = """
        <script>
        (function() {
            const ANSWER_LABELS = {"1": "Again", "2": "Hard", "3": "Good", "4": "Easy"};
            const ONIGIRI_TIMER_POSITION = "__ONIGIRI_TIMER_POSITION__";
            const ONIGIRI_SHOW_ANSWER_LABEL = __ONIGIRI_SHOW_ANSWER_LABEL__;
            // Anki's native New/Learn/Review counts node lives inside the Show
            // Answer button and is only scraped successfully once per card (any
            // rebuild of the button wipes it for good). Cache the last real read so
            // a later empty scrape - caused by our own rebuild, not a real change -
            // doesn't blank the pills out.
            let onigiriLastKnownStats = null;

            function cleanText(value) {
                return (value || '').replace(/\\s+/g, ' ').trim();
            }

            function buttonTextWithoutOnigiri(btn) {
                const clone = btn.cloneNode(true);
                clone.querySelectorAll('.stattxt, .nobold, .onigiri-pre-answer-counts, .onigiri-answer-hover-number, .onigiri-answer-label, .onigiri-show-answer-label').forEach(node => node.remove());
                return cleanText(clone.textContent);
            }

            function stripBottomBarTooltips(root) {
                const scope = root && root.querySelectorAll ? root : document;
                const nodes = Array.from(scope.querySelectorAll('#outer [title], #outer button[title], button[title]'));
                if (scope !== document && scope.matches && scope.matches('#outer [title], #outer button[title], button[title]')) nodes.push(scope);
                nodes.forEach(node => node.removeAttribute('title'));
            }

            function easeFromButton(btn) {
                const onclick = btn.getAttribute('onclick') || '';
                const cmd = btn.getAttribute('data-cmd') || '';
                const id = btn.id || '';
                const text = cleanText(btn.innerText).toLowerCase();
                if (onclick.includes('ease1') || cmd === 'ease1' || id === 'ease1') return "1";
                if (onclick.includes('ease2') || cmd === 'ease2' || id === 'ease2') return "2";
                if (onclick.includes('ease3') || cmd === 'ease3' || id === 'ease3') return "3";
                if (onclick.includes('ease4') || cmd === 'ease4' || id === 'ease4') return "4";
                if (text.includes('again')) return "1";
                if (text.includes('hard')) return "2";
                if (text.includes('good')) return "3";
                if (text.includes('easy')) return "4";
                return null;
            }

            function nativeAnswerNumberNodes() {
                return Array.from(document.querySelectorAll('#outer .nobold, .nobold'))
                    .filter(node => !node.classList.contains('onigiri-answer-hover-number'))
                    .filter(node => !node.closest('.onigiri-answer-hover-number'))
                    .filter(node => cleanText(node.textContent));
            }

            function forceHideNativeNumberElement(node, className) {
                if (!node) return;
                if (className) node.classList.add(className);
                node.setAttribute('aria-hidden', 'true');
                ['display', 'width', 'height', 'max-width', 'max-height', 'padding', 'margin', 'border', 'overflow', 'opacity', 'pointer-events'].forEach(prop => {
                    const value = prop === 'display' ? 'none' : (prop === 'opacity' ? '0' : (prop === 'pointer-events' ? 'none' : '0'));
                    node.style.setProperty(prop, value, 'important');
                });
            }

            function markNativeNumberSource(node) {
                if (!node) return;
                const text = cleanText(node.textContent);
                forceHideNativeNumberElement(node, 'onigiri-native-number-source');
                let parent = node.parentElement;
                while (parent && parent !== document.body && parent.id !== 'outer' && !parent.matches('button') && !parent.querySelector('button') && cleanText(parent.textContent) === text) {
                    forceHideNativeNumberElement(parent, 'onigiri-native-number-host');
                    parent = parent.parentElement;
                }
                const cell = node.closest('td, th');
                if (cell && !cell.querySelector('button') && cleanText(cell.textContent) === text) {
                    forceHideNativeNumberElement(cell, 'onigiri-native-number-empty-cell');
                }
            }

            function collapseNativeNumberHosts() {
                document.querySelectorAll('#outer tr').forEach(row => {
                    if (row.querySelector('button')) return;
                    const cells = Array.from(row.querySelectorAll('td, th'));
                    if (!cells.length) return;
                    row.classList.toggle('onigiri-native-number-empty-row', cells.every(cell => cell.classList.contains('onigiri-native-number-empty-cell') || !cleanText(cell.textContent)));
                });
            }

            let onigiriCardTypeInfo = window.__onigiriPendingReviewerCardType || null;

            function renderOnigiriCardTypeIndicator() {
                const outer = document.getElementById('outer');
                if (!outer) return;

                const info = onigiriCardTypeInfo;
                const activeIndex = { new: 0, learn: 1, review: 2 }[info && info.key];
                outer.querySelectorAll('.onigiri-count-pill').forEach((pill, index) => {
                    const active = Number.isInteger(activeIndex) && index === activeIndex;
                    pill.classList.toggle('is-current-card', active);
                    if (active) pill.setAttribute('aria-label', info.label || 'Current card type');
                    else pill.removeAttribute('aria-label');
                });

            }

            window.onigiriSetReviewerCardType = function(info) {
                onigiriCardTypeInfo = info && info.key ? info : null;
                window.__onigiriPendingReviewerCardType = onigiriCardTypeInfo;
                renderOnigiriCardTypeIndicator();
            };
            if (onigiriCardTypeInfo) renderOnigiriCardTypeIndicator();

            function findNativeNumberInsideButton(btn) {
                return Array.from(btn.querySelectorAll('.nobold')).find(node => !node.classList.contains('onigiri-answer-hover-number'));
            }

            // Anki's own "Show answer timer" (deck options > Timers) renders a
            // ticking mm:ss counter somewhere in the bottom toolbar. We don't rely
            // on a fixed id/class (it has changed across Anki versions) - instead we
            // look for a leaf element whose own text matches the mm:ss shape, which
            // intervals/counts never do. Scoped to #outer so we never touch card text.
            function isOnigiriTimerText(text) {
                return /^\\d{1,2}:\\d{2}$/.test(text);
            }

            function findOnigiriNativeTimerNode() {
                const outer = document.getElementById('outer');
                if (!outer) return null;
                const nodes = outer.querySelectorAll('*');
                for (const el of nodes) {
                    if (el.closest('.onigiri-timer-pill, .onigiri-timer-out-btn')) continue;
                    if (el.children.length > 0) continue;
                    if (isOnigiriTimerText(cleanText(el.textContent))) return el;
                }
                return null;
            }

            // Standalone timer button in the bottom bar. "where" decides the slot:
            //   'left-of-more'  -> first child of the last cell (before the More
            //                      button). Used by "out" mode (always) and by
            //                      "right" mode after the card is flipped.
            //   'right-of-edit' -> last child of the first cell (after the Edit
            //                      button). Used by "left" mode after the flip.
            // The timer is NEVER placed among the answer buttons (middle cell).
            function ensureOnigiriTimerButton(where, text) {
                const outer = document.getElementById('outer');
                if (!outer) return;
                // Resolve the OUTER bottom-bar row's own cells only. A plain
                // "table td:last-child" would match a nested answer-buttons
                // table's last cell (in the middle, among the answers) - that is
                // exactly the misplacement we must avoid. The Edit cell is the
                // outer row's first cell; the More cell is its last cell.
                const outerTable = outer.querySelector('table');
                const row = outerTable && outerTable.querySelector(':scope > tbody > tr, :scope > tr');
                const cells = row ? Array.from(row.children).filter(el => el.tagName === 'TD' || el.tagName === 'TH') : [];
                if (!cells.length) return;
                const cell = where === 'right-of-edit' ? cells[0] : cells[cells.length - 1];
                if (!cell) return;
                let btn = document.querySelector('.onigiri-timer-out-btn');
                if (!btn) {
                    btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'onigiri-timer-out-btn onigiri-other-btn';
                    btn.setAttribute('tabindex', '-1');
                    btn.setAttribute('aria-hidden', 'true');
                }
                if (where === 'right-of-edit') {
                    // After Edit: keep it as the cell's last child.
                    if (btn.parentElement !== cell || cell.lastElementChild !== btn) cell.appendChild(btn);
                } else {
                    // Before More: keep it as the cell's first child.
                    if (btn.parentElement !== cell || cell.firstElementChild !== btn) cell.insertBefore(btn, cell.firstChild);
                }
                if (btn.textContent !== text) btn.textContent = text;
            }

            function removeOnigiriTimerOutButton() {
                document.querySelectorAll('.onigiri-timer-out-btn').forEach(el => el.remove());
            }

            function findAnswerNumber(btn, sourceNode) {
                if (sourceNode) return cleanText(sourceNode.textContent);
                const nativeInside = findNativeNumberInsideButton(btn);
                if (nativeInside) return cleanText(nativeInside.textContent);
                return cleanText(btn.getAttribute('data-onigiri-answer-number') || '');
            }

            function lockAnswerButtonWidth(btn) {
                if (!btn) return 0;
                const existing = parseFloat(btn.style.getPropertyValue('--onigiri-answer-button-width'));
                if (existing > 0) return existing;
                const rect = btn.getBoundingClientRect();
                const width = Math.ceil(rect.width || btn.offsetWidth || 0);
                if (width > 0) btn.style.setProperty('--onigiri-answer-button-width', width + 'px');
                return width;
            }

            function fitAnswerNumberFontSize(btn, text) {
                const width = lockAnswerButtonWidth(btn) || 72;
                const height = Math.max(24, btn.getBoundingClientRect().height || btn.offsetHeight || 40);
                const availableWidth = Math.max(20, width - 16);
                const computed = window.getComputedStyle(btn);
                const fontFamily = computed.fontFamily || 'sans-serif';
                const labelFontSize = parseFloat(computed.fontSize) || 14;
                const maxSize = Math.max(8, Math.min(labelFontSize, height * 0.46));
                const minSize = 8;
                const canvas = window.__onigiriAnswerNumberCanvas || document.createElement('canvas');
                window.__onigiriAnswerNumberCanvas = canvas;
                const context = canvas.getContext && canvas.getContext('2d');
                if (!context) return Math.max(minSize, Math.min(maxSize, availableWidth / Math.max(1, cleanText(text).length * 0.58)));
                for (let size = maxSize; size >= minSize; size -= 0.5) {
                    context.font = `800 ${size}px ${fontFamily}`;
                    if (context.measureText(text).width <= availableWidth) return size;
                }
                return minSize;
            }

            function updateAnswerNumberFontSize(btn, answerNumber) {
                btn.style.setProperty('--onigiri-answer-number-font-size', fitAnswerNumberFontSize(btn, answerNumber).toFixed(1) + 'px');
            }

            function prepareAnswerButton(btn, ease, sourceNode) {
                stripBottomBarTooltips(btn);
                lockAnswerButtonWidth(btn);
                const answerNumber = findAnswerNumber(btn, sourceNode);
                if (!answerNumber) return;
                updateAnswerNumberFontSize(btn, answerNumber);
                markNativeNumberSource(sourceNode || findNativeNumberInsideButton(btn));
                const currentLabel = buttonTextWithoutOnigiri(btn);
                const label = cleanText(btn.getAttribute('data-onigiri-answer-label') || currentLabel || ANSWER_LABELS[ease] || '');
                if (!label) return;
                if (btn.getAttribute('data-onigiri-answer-hover-ready') === '1' && btn.getAttribute('data-onigiri-answer-number') === answerNumber && btn.getAttribute('data-onigiri-answer-label') === label) {
                    updateAnswerNumberFontSize(btn, answerNumber);
                    return;
                }
                btn.setAttribute('data-onigiri-answer-hover-ready', '1');
                btn.setAttribute('data-onigiri-answer-number', answerNumber);
                btn.setAttribute('data-onigiri-answer-label', label);
                btn.textContent = '';
                const labelSpan = document.createElement('span');
                labelSpan.className = 'onigiri-answer-label';
                labelSpan.textContent = label;
                const numberSpan = document.createElement('span');
                numberSpan.className = 'onigiri-answer-hover-number';
                numberSpan.textContent = answerNumber;
                btn.append(labelSpan, numberSpan);
            }

            function findShowAnswerButton(buttons) {
                const all = Array.from(buttons);
                // If any ease (Again/Hard/Good/Easy) buttons are present, the
                // answer is revealed and there is NO Show Answer button. Never
                // fall back to another bottom-bar button in this state: doing so
                // builds the pre-answer counts/timer panel during the answer
                // state, which flickers as Anki re-renders the bottom bar on
                // every answer-timer tick. The pre-answer panel is a
                // question-state-only feature.
                if (all.some(btn => btn.getAttribute('data-onigiri-ease') || easeFromButton(btn))) return null;
                const candidates = all.filter(btn => !btn.getAttribute('data-onigiri-ease'));
                const direct = candidates.find(btn => {
                    const onclick = (btn.getAttribute('onclick') || '').toLowerCase();
                    const cmd = (btn.getAttribute('data-cmd') || '').toLowerCase();
                    const id = (btn.id || '').toLowerCase();
                    const text = buttonTextWithoutOnigiri(btn).toLowerCase();
                    return cmd === 'ans' || id.includes('ans') || onclick.includes('ans') || text.includes('show answer') || text.includes('mostrar resposta') || text.includes('mostrar respuesta') || text.includes('afficher la réponse');
                });
                if (direct) return direct;
                const nonUtility = candidates.filter(btn => {
                    const text = buttonTextWithoutOnigiri(btn).toLowerCase();
                    return text && !text.includes('edit') && !text.includes('more');
                });
                if (nonUtility.length === 1) return nonUtility[0];
                return nonUtility.sort((a, b) => buttonTextWithoutOnigiri(b).length - buttonTextWithoutOnigiri(a).length)[0] || null;
            }

            function collectPreAnswerCounts(timerNode, timerText) {
                // Anki can render the new/learn/review counts either as separate
                // .stattxt nodes ("7268", "+", "68", "+", "5") or as a single
                // .stattxt node whose textContent is already "7268 + 68 + 5" - and
                // on builds with the answer timer on, that same node (or a sibling
                // sharing the .stattxt class) can also carry the "0:09" timer text.
                // Rather than dropping a whole node when it merely contains the
                // timer text, cut just that substring out before splitting, so real
                // counts sharing a node with the timer still come through.
                const nodes = Array.from(document.querySelectorAll('#outer .stattxt'))
                    .filter(node => !node.closest('.onigiri-pre-answer-counts'));
                nodes.forEach(node => forceHideNativeNumberElement(node, 'onigiri-stattxt-source'));
                let combined = nodes.map(node => cleanText(node.textContent)).filter(Boolean).join(' ');
                if (timerNode && timerText) {
                    combined = combined.split(timerText).map(part => cleanText(part)).filter(Boolean).join(' ');
                }
                const scraped = combined.split('+').map(part => cleanText(part)).filter(Boolean).slice(0, 3);
                if (scraped.length > 0) {
                    onigiriLastKnownStats = scraped;
                    return scraped;
                }
                // Empty scrape: almost always means our own earlier rebuild already
                // wiped the native counts node for this card, not that the counts
                // themselves vanished. Fall back to the last real read instead of
                // reporting "no counts" (which would blank the pills every tick).
                return onigiriLastKnownStats || [];
            }

            function prepareShowAnswerCounts(buttons) {
                stripBottomBarTooltips(document);
                const showButton = findShowAnswerButton(buttons);
                document.querySelectorAll('#outer button.onigiri-show-answer-btn').forEach(btn => {
                    if (btn !== showButton) {
                        btn.classList.remove('onigiri-show-answer-btn', 'onigiri-has-pre-answer-counts');
                        const counts = btn.querySelector('.onigiri-pre-answer-counts');
                        if (counts) counts.remove();
                    }
                });

                // Answer revealed once the ease buttons (Again/Hard/Good/Easy)
                // are on screen.
                const answerButtonsPresent = Array.from(buttons)
                    .some(b => b.getAttribute('data-onigiri-ease') || easeFromButton(b));

                const timerNode = findOnigiriNativeTimerNode();
                const timerText = timerNode ? cleanText(timerNode.textContent) : '';
                const stats = collectPreAnswerCounts(timerNode, timerText);

                // "off" hides the timer entirely: no pill inside the Show Answer
                // button and no standalone button in the bottom bar. The native
                // timer element is still hidden below so it can't leak through.
                const timerEnabled = ONIGIRI_TIMER_POSITION !== 'off';

                // Decide where the ticking timer lives:
                //   - "out": standalone button left of More, in BOTH states.
                //   - "right"/"left" before the flip: a pill inside the Show
                //     Answer button (built further down via the pre-answer panel).
                //   - "right"/"left" after the flip: a standalone button that
                //     continues ticking - "right" to the right of Edit, "left"
                //     to the left of More. Never among the answer buttons.
                let standaloneTimerSlot = null;
                if (timerNode && timerEnabled) {
                    if (ONIGIRI_TIMER_POSITION === 'out') {
                        standaloneTimerSlot = 'left-of-more';
                    } else if (answerButtonsPresent) {
                        standaloneTimerSlot = ONIGIRI_TIMER_POSITION === 'right' ? 'left-of-more' : 'right-of-edit';
                    }
                }

                if (timerNode) forceHideNativeNumberElement(timerNode, 'onigiri-native-timer-source');
                if (standaloneTimerSlot) {
                    ensureOnigiriTimerButton(standaloneTimerSlot, timerText);
                } else {
                    removeOnigiriTimerOutButton();
                }

                // The inside-the-button timer pill only applies to the pre-flip
                // Show Answer button (right/left mode, question state).
                const hasInsideTimer = !!timerNode && timerEnabled && ONIGIRI_TIMER_POSITION !== 'out' && !answerButtonsPresent;

                if (!showButton || (stats.length === 0 && !hasInsideTimer)) {
                    if (showButton) {
                        const counts = showButton.querySelector('.onigiri-pre-answer-counts');
                        if (counts && !showButton.querySelector('.onigiri-count-pill')) counts.remove();
                    }
                    return;
                }

                // Only the counts and whether the timer is inside the button define
                // the button's *structure* - the timer's own ticking text must NOT
                // be part of this key. A structural rebuild wipes the button's
                // children (showButton.textContent = ''), which permanently destroys
                // Anki's native counts element nested inside it (it can only be
                // scraped once per card); if the timer text were included here, the
                // button would rebuild every second and lose the counts after the
                // very first tick. The timer text itself is still updated live,
                // in place, below, without triggering a rebuild.
                const structureKey = stats.join('|') + '::' + (hasInsideTimer ? '1' : '0');
                const nativeLabel = cleanText(showButton.getAttribute('data-onigiri-show-answer-label') || buttonTextWithoutOnigiri(showButton));
                const label = nativeLabel === 'Show Answer' ? ONIGIRI_SHOW_ANSWER_LABEL : nativeLabel;
                showButton.classList.add('onigiri-show-answer-btn', 'onigiri-has-pre-answer-counts');
                showButton.setAttribute('data-onigiri-show-answer-label', label || ONIGIRI_SHOW_ANSWER_LABEL);
                if (showButton.getAttribute('data-onigiri-pre-answer-counts') === structureKey && showButton.querySelector('.onigiri-pre-answer-counts')) {
                    if (hasInsideTimer) {
                        const timerPill = showButton.querySelector('.onigiri-timer-pill');
                        if (timerPill && timerPill.textContent !== timerText) timerPill.textContent = timerText;
                    }
                    return;
                }
                showButton.setAttribute('data-onigiri-pre-answer-counts', structureKey);
                showButton.textContent = '';
                const labelSpan = document.createElement('span');
                labelSpan.className = 'onigiri-show-answer-label';
                labelSpan.textContent = label || ONIGIRI_SHOW_ANSWER_LABEL;
                showButton.appendChild(labelSpan);

                const panel = document.createElement('span');
                panel.className = 'onigiri-pre-answer-counts';
                panel.setAttribute('aria-hidden', 'true');

                function appendCountPills(container) {
                    ['new', 'learn', 'review'].forEach((kind, index) => {
                        const pill = document.createElement('span');
                        pill.className = 'onigiri-count-pill onigiri-count-pill-' + kind;
                        pill.textContent = stats[index] || '0';
                        container.appendChild(pill);
                    });
                }

                function makeTimerPill() {
                    const timerPill = document.createElement('span');
                    timerPill.className = 'onigiri-timer-pill';
                    timerPill.textContent = timerText;
                    return timerPill;
                }

                if (hasInsideTimer && stats.length > 0) {
                    if (ONIGIRI_TIMER_POSITION === 'left') panel.appendChild(makeTimerPill());
                    appendCountPills(panel);
                    if (ONIGIRI_TIMER_POSITION === 'right') panel.appendChild(makeTimerPill());
                } else if (hasInsideTimer) {
                    panel.appendChild(makeTimerPill());
                } else {
                    appendCountPills(panel);
                }
                showButton.appendChild(panel);
            }

            function classifyButtons() {
                stripBottomBarTooltips(document);
                renderOnigiriCardTypeIndicator();
                const buttons = document.querySelectorAll('#outer button, button');
                const answerButtons = [];
                buttons.forEach(btn => {
                    const ease = easeFromButton(btn);
                    if (ease) {
                        btn.setAttribute('data-onigiri-ease', ease);
                        lockAnswerButtonWidth(btn);
                        answerButtons.push({ btn, ease });
                    } else {
                        btn.classList.add('onigiri-other-btn');
                    }
                });
                const nativeNumbers = nativeAnswerNumberNodes();
                nativeNumbers.forEach(markNativeNumberSource);
                answerButtons.forEach((item, index) => prepareAnswerButton(item.btn, item.ease, nativeNumbers[index] || null));
                collapseNativeNumberHosts();
                prepareShowAnswerCounts(buttons);
                renderOnigiriCardTypeIndicator();
            }

            setInterval(classifyButtons, 100);
            const observer = new MutationObserver(classifyButtons);
            observer.observe(document.body, { childList: true, subtree: true });
        })();
        </script>
        """
        scripts.append(
            _pre_answer_counts_script
            .replace("__ONIGIRI_TIMER_POSITION__", timer_position)
            .replace("__ONIGIRI_SHOW_ANSWER_LABEL__", json.dumps(tr_at("show_answer_label")))
        )

    scripts.append("""
    <script>
    (function() {
        if (window.__onigiriBottomBarTooltipsDisabled) return;
        window.__onigiriBottomBarTooltipsDisabled = true;
        function stripBottomBarTitles() {
            document.querySelectorAll('#outer [title], #outer button[title], button[title]').forEach(node => node.removeAttribute('title'));
        }
        function start() {
            stripBottomBarTitles();
            setInterval(stripBottomBarTitles, 500);
            if (document.body) {
                const observer = new MutationObserver(stripBottomBarTitles);
                observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['title'] });
            }
        }
        if (document.body) start();
        else document.addEventListener('DOMContentLoaded', start, { once: true });
    })();
    </script>
    """)

    return "<style>" + "\n".join(css) + "</style>" + "\n".join(scripts)
def _onigiri_render_deck_tree(self, *args, **kwargs):
    """
    Patched version of DeckBrowser._render_deck_tree to pre-fetch enhanced stats.
    """
    try:
        from . import config
        conf = config.get_config_readonly()
        if conf.get("enhancedDeckStats", False):
            # Pre-fetch stats
            try:
                # Same query as in deck_tree_updater.py
                rows = self.mw.col.db.all("select did, queue, count() from cards group by did, queue")
                enhanced_stats = {}
                for did, queue, count in rows:
                    if did not in enhanced_stats:
                        enhanced_stats[did] = {"total": 0, "buried": 0, "suspended": 0, "new": 0, "learn": 0, "review": 0}
                    
                    stats = enhanced_stats[did]
                    stats["total"] += count
                    
                    if queue < 0:
                        if queue == -1: stats["suspended"] += count
                        elif queue == -2 or queue == -3: stats["buried"] += count
                    elif queue == 0: stats["new"] += count
                    elif queue == 1 or queue == 3: stats["learn"] += count
                    elif queue == 2: stats["review"] += count
                
                # Attach to instance
                self._onigiri_enhanced_stats = enhanced_stats
                # print(f"Onigiri: Pre-fetched enhanced stats for {len(enhanced_stats)} decks")
            except Exception as e:
                print(f"Onigiri: Error pre-fetching enhanced stats: {e}")
                self._onigiri_enhanced_stats = None
        else:
             self._onigiri_enhanced_stats = None

    except Exception as e:
        print(f"Onigiri: Error in _onigiri_render_deck_tree wrapper: {e}")

    # Call original
    return _old_render_deck_tree(self, *args, **kwargs)

# Store original method
from aqt.deckbrowser import DeckBrowser
if not hasattr(DeckBrowser, '_onigiri_patched_render_tree'):
    if hasattr(DeckBrowser, '_render_deck_tree'):
        _old_render_deck_tree = DeckBrowser._render_deck_tree
        DeckBrowser._render_deck_tree = _onigiri_render_deck_tree
        DeckBrowser._onigiri_patched_render_tree = True
    else:
        print("Onigiri: Warning - DeckBrowser._render_deck_tree not found, enhanced stats patch optional skipped.")
