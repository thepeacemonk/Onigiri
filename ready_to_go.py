"""Collection-wide reviewer shortcuts shared by Classic and Kome.

Each shortcut builds a small, named filtered deck from a search that spans the
whole collection.  Reusing one deck per action avoids changing the user's
selected normal deck and makes the actions safe to trigger repeatedly.
"""

from __future__ import annotations

import html
import os
import re
from typing import Any

from aqt import mw
from aqt.utils import tooltip

from . import config


READY_ACTIONS = {
    "inbox": {
        "label": "Inbox",
        "query": "is:new -is:suspended",
        "deck_name": "Onigiri Ready — Inbox",
        "icon": "lucide-inbox.svg",
    },
    "warm_up": {
        "label": "Warm up",
        "query": "is:learn is:due -is:suspended",
        "deck_name": "Onigiri Ready — Warm up",
        "icon": "lucide-flame.svg",
    },
    "today": {
        "label": "Today",
        "query": "is:review prop:due=0 -is:suspended",
        "deck_name": "Onigiri Ready — Today",
        "icon": "lucide-calendar-check.svg",
    },
    "cool_down": {
        "label": "Cool-Down",
        "query": "is:review prop:due<0 -is:suspended",
        "deck_name": "Onigiri Ready — Cool-Down",
        "icon": "lucide-droplet.svg",
    },
}

TAG_STUDY_DECK_NAME = "Onigiri Ready — Tags"
INTERNAL_DECK_NAMES = frozenset(
    [str(action["deck_name"]) for action in READY_ACTIONS.values()]
    + [TAG_STUDY_DECK_NAME]
)


def is_internal_deck_name(name: Any) -> bool:
    """Return whether *name* belongs to a Ready-to-go working deck."""
    return str(name or "") in INTERNAL_DECK_NAMES


def restore_internal_cards(col: Any = None) -> bool:
    """Return cards left in Ready-to-go decks to their original decks.

    Filtered decks temporarily change each matching card's deck id. Because
    these working decks are hidden from the deck browser, they must be emptied
    before the visible tree calculates its counts.
    """
    collection = col or getattr(mw, "col", None)
    if collection is None:
        return False

    from anki.decks import DeckId

    restored = False
    for deck_name in INTERNAL_DECK_NAMES:
        try:
            deck_id = collection.decks.id_for_name(deck_name)
            if not deck_id:
                continue
            deck = collection.decks.get(deck_id)
            if not deck or not bool(deck.get("dyn", 0)):
                continue
            has_cards = collection.db.scalar(
                "select 1 from cards where did = ? limit 1", deck_id
            )
            if has_cards:
                collection.sched.empty_filtered_deck(DeckId(deck_id))
                restored = True
        except Exception as exc:
            print(f"Onigiri: could not empty Ready-to-go deck {deck_name}: {exc}")
    return restored


def _addon_package() -> str:
    try:
        return mw.addonManager.addonFromModule(__package__ or __name__)
    except Exception:
        return "1011095603"


def _icon_url(action_id: str) -> str:
    """Resolve a sidebar icon selected in Settings, with a Lucide fallback."""
    action = READY_ACTIONS[action_id]
    try:
        value = config.get_collection_config(
            f"modern_menu_icon_ready_{action_id}", ""
        )
    except Exception:
        value = ""
    value = str(value or f"system:{action['icon']}")
    filename = os.path.basename(value.split(":", 1)[-1])
    package = _addon_package()
    if value.startswith("system:"):
        return (
            f"/_addons/{package}/system_files/system_icons/available_for_users/"
            f"{filename}"
        )
    return f"/_addons/{package}/user_files/icons/{filename}"


def _setting(key: str, default: Any = None) -> Any:
    try:
        return config.get_collection_config(key, default)
    except Exception:
        return default


def _number_setting(key: str, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(maximum, int(float(_setting(key, default)))))
    except (TypeError, ValueError):
        return default


def _color_setting(key: str, fallback: str) -> str:
    value = str(_setting(key, "") or "").strip()
    if re.fullmatch(r"#[0-9a-fA-F]{3,8}", value):
        return value
    return fallback


def _appearance_style() -> str:
    """CSS variables shared by the Classic sidebar and dashboard widget."""
    icon_size = _number_setting("modern_menu_ready_icon_size", 16, 8, 40)
    gap = _number_setting("modern_menu_ready_gap", 6, 0, 24)
    radius = _number_setting("modern_menu_ready_radius", 9, 0, 30)
    border_width = (
        1 if bool(_setting("modern_menu_ready_show_border", True)) else 0
    )
    text = _color_setting(
        "modern_menu_ready_text_color", "var(--fg-subtle)"
    )
    border = _color_setting(
        "modern_menu_ready_border_color", "var(--border)"
    )
    background = _color_setting(
        "modern_menu_ready_button_background", "transparent"
    )
    return (
        f"--onigiri-ready-icon-size:{icon_size}px;"
        f"--onigiri-ready-gap:{gap}px;"
        f"--onigiri-ready-radius:{radius}px;"
        f"--onigiri-ready-border-width:{border_width}px;"
        f"--onigiri-ready-text-color:{text};"
        f"--onigiri-ready-border-color:{border};"
        f"--onigiri-ready-button-bg:{background};"
    )


def _buttons_html(class_name: str, circles: bool = False) -> str:
    buttons = []
    for action_id, action in READY_ACTIONS.items():
        label = html.escape(action["label"])
        icon = html.escape(_icon_url(action_id), quote=True)
        icon_color = html.escape(
            config.themed_icon_color(f"modern_menu_icon_color_ready_{action_id}")
            or "var(--onigiri-ready-text-color)",
            quote=True,
        )
        content = (
            f'<i class="onigiri-ready-icon" style="mask-image:url(\'{icon}\');'
            f'-webkit-mask-image:url(\'{icon}\');background-color:{icon_color};"></i>'
        )
        if circles:
            content = (
                f'<span class="mag-skin">{content}</span>'
                f'<span class="mag-label" aria-hidden="true">{label}</span>'
            )
        else:
            content += f'<span>{label}</span>'
        title_attribute = "" if circles else f'title="{label}" '
        buttons.append(
            f'<button type="button" class="onigiri-ready-action '
            f'onigiri-ready-{action_id}" '
            f'{title_attribute}aria-label="{label}" '
            f'onclick="pycmd(\'onigiri_ready:{action_id}\')">'
            f'{content}</button>'
        )
    return f'<div class="{class_name}">{"".join(buttons)}</div>'


def render_sidebar_html() -> str:
    """Classic sidebar section, placed between actions and the deck list."""
    title = html.escape(str(_setting("modern_menu_ready_title", "Ready to go")))
    layout_mode = str(_setting("modern_menu_ready_layout_mode", "list"))
    if layout_mode == "hidden":
        return ""
    layout_class = " is-collapsed" if layout_mode == "collapsed" else ""
    heading = (
        f"<h3>{title}</h3>"
        if bool(_setting("modern_menu_ready_show_title", True))
        else ""
    )
    return (
        f'<section class="onigiri-ready-sidebar{layout_class}" '
        f'aria-label="Ready to go" '
        f'style="{_appearance_style()}">'
        f'{heading}'
        f'{_buttons_html("onigiri-ready-actions")}'
        '</section>'
    )


def render_widget_html(design: str = "squares") -> str:
    """Classic dashboard widget added through Organize Widgets."""
    title = html.escape(str(_setting("modern_menu_ready_title", "Ready to go")))
    heading = (
        f'<div class="onigiri-widget-head"><h3>{title}</h3></div>'
        if bool(_setting("modern_menu_ready_show_title", True))
        else ""
    )
    circles = design == "circles"
    actions = _buttons_html("mag" if circles else "onigiri-ready-actions", circles)
    if circles:
        actions = f'<div class="onigiri-ready-magnetic-stage">{actions}</div>'
    return (
        f'<section class="onigiri-ready-widget{" is-circles" if circles else ""}" aria-label="Ready to go" '
        f'style="{_appearance_style()}">'
        f'{heading}'
        f'{actions}'
        '</section>'
    )


def handle_command(command: str) -> bool:
    """Build the requested filtered deck then take the user into Reviewer."""
    action = READY_ACTIONS.get(command)
    if action is None:
        return False
    try:
        _build_and_study(action)
    except Exception as exc:
        _report_error(exc)
    return True


def study_tag(tag: str) -> bool:
    """Build a reusable filtered deck for *tag* and start reviewing it."""
    tag = str(tag or "").strip()
    if not tag:
        return False
    try:
        from anki.collection import SearchNode

        tag_search = mw.col.build_search_string(SearchNode(tag=tag))
        _build_and_study({
            "query": f"{tag_search} -is:suspended",
            "deck_name": TAG_STUDY_DECK_NAME,
        })
    except Exception as exc:
        _report_error(exc)
    return True


def _build_and_study(action: dict[str, str]) -> None:
    """Use Anki's current asynchronous filtered-deck operations.

    Anki 25.07+ returns a mutable ``FilteredDeckForUpdate`` through the query
    operation.  Saving it via ``add_or_update_filtered_deck`` builds the deck,
    then its returned id is selected and reviewed on the UI thread.
    """
    from anki.decks import DeckId, FilteredDeckConfig
    from aqt.operations import QueryOp
    from aqt.operations.scheduling import add_or_update_filtered_deck

    def get_deck(col: Any) -> Any:
        # A different Ready action may still contain unfinished cards. Empty
        # every working deck first so this query always spans the collection.
        restore_internal_cards(col)
        deck_id = DeckId(0)
        try:
            existing_id = col.decks.id_for_name(action["deck_name"])
            existing = col.decks.get(existing_id) if existing_id else None
            if existing and bool(existing.get("dyn", 0)):
                deck_id = DeckId(existing_id)
        except Exception:
            pass
        return col.sched.get_or_create_filtered_deck(deck_id=deck_id)

    def save_deck(deck: Any) -> None:
        deck.name = action["deck_name"]
        deck.allow_empty = True
        terms = deck.config.search_terms
        del terms[:]
        # Random order interleaves matching cards from every deck.
        terms.append(
            FilteredDeckConfig.SearchTerm(
                search=action["query"], limit=9999, order=1
            )
        )
        add_or_update_filtered_deck(parent=mw, deck=deck).success(
            lambda out: _start_studying(DeckId(out.id))
        ).failure(_report_error).run_in_background()

    QueryOp(parent=mw, op=get_deck, success=save_deck).failure(
        _report_error
    ).run_in_background()


def _start_studying(deck_id: Any) -> None:
    """Select the temporary deck and enter/repaint the reviewer."""
    try:
        mw.col.decks.select(deck_id)
        try:
            mw.col.startTimebox()
        except Exception:
            pass
        reviewer = getattr(mw, "reviewer", None)
        if getattr(mw, "state", None) == "review" and reviewer is not None:
            reviewer._showQuestion()
        else:
            mw.moveToState("review")
    except Exception as exc:
        _report_error(exc)


def _report_error(error: Exception) -> None:
    """Surface operation failures instead of silently ignoring a click."""
    print(f"Onigiri: Ready to go failed: {error}")
    try:
        tooltip(f"Ready to go: {error}", parent=mw)
    except Exception:
        pass
