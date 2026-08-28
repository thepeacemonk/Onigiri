# Post-save side effects for the WebUI settings dialog.
#
# Writing a config key is rarely the whole job: hiding the macOS title bar has to
# call into mac_titlebar, changing the language has to update the profile's
# language code, and so on. Pages name the hooks they need via their `post_save`
# list in schema.py; each hook here takes the Store and is run inside its own
# try/except so one failing page can never abort the rest of the save.

from aqt import mw

from ..translations import LANGUAGES
from .store import _col_set


def _modes(store):
    from .. import mac_titlebar, patcher

    patcher.apply_synapsepro_sidebar_visibility(store.config)
    mac_titlebar.apply(bool(store.read("hideMacTitleBar")))


def _language(store):
    lang_name = store.read("language") or "English (Default)"
    code = LANGUAGES.get(lang_name, "en")
    if mw.pm.profile.get("onigiri_language") != code:
        mw.pm.profile["onigiri_language"] = code


def _profile(store):
    user_name = store.read("userName")
    if user_name is not None and mw and mw.col:
        _col_set(mw.col, "modern_menu_userName", user_name)


def _sidebar(store):
    """Two things the Sidebar page's keys can't express on their own.

    `sidebarPosition` (addon config) mirrors `modern_menu_sidebar_position`
    (collection config): both are read by different parts of the deck browser,
    and the legacy page wrote both on every save. Picking "center" also puts the
    deck cycle into its centered state, which is what made the choice visible at
    all (settings/_page_sidebar.py:1549-1561).

    `modern_menu_sidebar_bg_transparency` is zeroed because this page always
    edits the custom background; a value left over from the pre-designer page
    would otherwise keep the frame semi-transparent."""
    if not mw or not mw.col:
        return
    position = store.read("modern_menu_sidebar_position") or "left"
    if position not in {"left", "right", "center"}:
        position = "left"
    if store.config.get("sidebarPosition") != position:
        store.config["sidebarPosition"] = position
        # Hooks run *after* apply_now() has already written the config file, so a
        # mutation made here has to persist itself or it would sit in memory
        # until some later patch happened to flush it.
        store.write_config()
    from .store import _col_get

    if _col_get(mw.col, "modern_menu_sidebar_bg_transparency", 0):
        _col_set(mw.col, "modern_menu_sidebar_bg_transparency", 0)
    if position == "center":
        _col_set(mw.col, "onigiri_deck_cycle_state", 4)
        _col_set(mw.col, "onigiri_deck_focus_mode", False)
    elif _col_get(mw.col, "onigiri_deck_cycle_state") == 4:
        _col_set(mw.col, "onigiri_deck_cycle_state", 0)
        _col_set(mw.col, "onigiri_deck_focus_mode", False)


def _stats_widgets(store):
    """Keep the legacy `hideRetentionStars` switch in step with the Stats
    Widgets toggle that replaced it.

    onigiri_renderer.py:1071-1075 and patcher.py:1689 still consult
    `hideRetentionStars` and it *wins* over `stats_widgets_style.
    show_retention_stars`. Without this mirror a collection that ever had the
    old Hide Modes switch on would hide its stars forever, with no control left
    anywhere to turn them back on."""
    show = store.read("swidget_show_retention_stars")
    if show is None:
        return
    hide = not bool(show)
    if bool(store.config.get("hideRetentionStars", False)) != hide:
        store.config["hideRetentionStars"] = hide
        # Hooks run after apply_now() has already written the config file.
        store.write_config()


def _pomodoro(_store):
    """Keep Pomodoro's disk mirror, live timer, and open island in sync."""
    from .. import pomodoro

    settings = pomodoro.get_settings()
    pomodoro.save_settings(settings)
    pomodoro.get_timer().settings = settings
    pomodoro.reload_open_widget()


# A page's hooks run on every patch that touches any of its fields, and these
# two reach into the game managers. Dragging a slider must not re-run them on
# every frame, so each remembers the state it last acted on and returns early
# when nothing it cares about moved. None means "not yet observed".
_GAME_STATE = {"enabled": None, "nook": None}


def _enabled_flags(conf):
    return (
        bool((conf.get("restaurant_level", {}) or {}).get("enabled", False)),
        bool((conf.get("onigimon", {}) or {}).get("enabled", False)),
        bool((conf.get("mochi_messages", {}) or {}).get("enabled", False)),
        bool(((conf.get("achievements", {}) or {}).get("focusDango", {}) or {}).get("enabled", False)),
    )


def _gamification(store):
    """Bring the games that were just switched on to life without a restart.

    Each game installs its Anki hooks at import time, and the classic dialog
    imported them after saving for exactly this reason."""
    from . import games_state

    flags = _enabled_flags(store.config)
    if _GAME_STATE["enabled"] == flags:
        return
    _GAME_STATE["enabled"] = flags
    games_state.initialize_enabled_hooks(store.config)


def _nook_level(store):
    """The Nook manager keeps its own copy of the three visibility flags; the
    config alone does not reach it after the first migration."""
    from . import games_state

    restaurant = store.config.get("restaurant_level", {}) or {}
    flags = (
        bool(restaurant.get("enabled", False)),
        bool(restaurant.get("notifications_enabled", True)),
        bool(restaurant.get("show_profile_bar_progress", True)),
    )
    if _GAME_STATE["nook"] == flags:
        return
    _GAME_STATE["nook"] = flags
    games_state.sync_nook_flags(store.config)


def _mochi_messages(store):
    """Fall back to Mochi when the custom messenger image is gone.

    The picture lives in user_files and can be deleted from outside Anki, so
    "custom" has to be verified rather than trusted — the classic dialog did the
    same check on every save."""
    from . import games_state

    conf = store.config.setdefault("mochi_messages", {})
    if conf.get("icon_choice") != "custom":
        return
    if not games_state.mochi_icon_exists(conf.get("custom_icon")):
        conf["icon_choice"] = "mochi"
        # Hooks run after apply_now() has already written the config file.
        store.write_config()


def _reviewer_progress(_store):
    """The header gauge reads its settings once per reviewer entry and reuses
    them for every card, so a save has to drop that cache — and repaint, since
    the user may well be sitting in the reviewer with the dialog open."""
    from .. import patcher

    patcher.invalidate_reviewer_progress_settings()
    patcher.update_reviewer_progress()


def _hexagon_land(store):
    """`theme` is not a user setting — it is the one theme that exists — but the
    reader still expects the key beside `enabled`."""
    conf = store.config.setdefault("hexagon_land", {})
    if conf.get("theme") != "island":
        conf["theme"] = "island"
        store.write_config()


HOOKS = {
    "modes": _modes,
    "language": _language,
    "profile": _profile,
    "sidebar": _sidebar,
    "stats_widgets": _stats_widgets,
    "pomodoro": _pomodoro,
    "gamification": _gamification,
    "nook_level": _nook_level,
    "mochi_messages": _mochi_messages,
    "hexagon_land": _hexagon_land,
    "reviewer_progress": _reviewer_progress,
}


def run(names, store):
    """Runs the named hooks. Returns [(name, error)] for the ones that failed."""
    failures = []
    for name in names:
        hook = HOOKS.get(name)
        if hook is None:
            continue
        try:
            hook(store)
        except Exception as exc:  # noqa: BLE001 - logged, never fatal
            import traceback

            print(f"[Onigiri] settings_web post-save hook {name!r} failed:\n{traceback.format_exc()}")
            failures.append((name, repr(exc)))
    return failures


def refresh_anki():
    """Everything the legacy dialog did after config.write_config()."""
    try:
        from .. import heatmap

        heatmap.invalidate_heatmap_cache()
    except Exception:
        pass
    try:
        from ..api import sidebar

        sidebar._ICON_OVERRIDE_CACHE.clear()
    except Exception:
        pass
    try:
        if hasattr(mw.col, "setMod"):
            mw.col.setMod()
        if hasattr(mw.col, "mark_changed"):
            mw.col.mark_changed()
    except Exception:
        pass
    try:
        from ..refresh import schedule_ui_refresh

        schedule_ui_refresh()
    except Exception:
        pass
