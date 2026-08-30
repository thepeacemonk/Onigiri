# Bridge between the WebUI Games pages and the gamification managers.
#
# Most game settings are plain addon-config keys and go through Store's normal
# `config` bindings. A handful are not: the Nook's name, the Onigimon companion
# and its nickname, and the island name all live inside a game manager's own
# persisted state, which owns validation and side effects the config file knows
# nothing about. Those are exposed here as named accessors and reached from the
# schema with a `{"kind": "game", "key": ...}` bind.
#
# The same module also builds the read-only context the pages display (Ankimon
# status, the companion roster, the island balance, the detected Bento games)
# and performs the page's push-button actions, so store.py, dialog.py and
# render.py never import a gamification module directly.

import os
from dataclasses import asdict

from ..translations import tr


def _nook():
    from ..gamification import nook_level

    return nook_level


def _onigimon():
    from ..gamification import onigimon

    return onigimon


def _hexagon():
    from ..gamification import hexagon_land

    return hexagon_land


# ── accessors (bind kind "game") ──────────────────────────────────────────────


def _read_nook_name():
    try:
        progress = _nook().manager.get_progress()
        return str(getattr(progress, "name", "") or "")
    except Exception:
        return ""


def _write_nook_name(value):
    _nook().manager.set_restaurant_name(str(value or ""))


def _read_onigimon_companion():
    try:
        return str(_onigimon().manager.load().active_companion_id or "")
    except Exception:
        return ""


def _write_onigimon_companion(value):
    value = str(value or "")
    if value:
        _onigimon().manager.set_active_companion(value)


def _read_onigimon_nickname():
    try:
        manager = _onigimon().manager
        companion = manager.active_companion()
        if not companion:
            return ""
        return str(manager.companion_display_name(companion) or "")
    except Exception:
        return ""


def _write_onigimon_nickname(value):
    _onigimon().manager.rename_active_companion(str(value or "").strip())


def _read_island_name():
    try:
        manager = _hexagon().manager
        return str(manager.island_display_name(manager.load()) or "")
    except Exception:
        return ""


def _write_island_name(value):
    # Only owners of the Keys may rename the island; the manager enforces that
    # and answers with a message, which the page shows via _refresh_island().
    state = _hexagon().manager.load()
    if getattr(state, "keys_of_the_island", False):
        _hexagon().manager.set_island_name(str(value or ""))


ACCESSORS = {
    "nook_name": (_read_nook_name, _write_nook_name),
    "onigimon_companion": (_read_onigimon_companion, _write_onigimon_companion),
    "onigimon_nickname": (_read_onigimon_nickname, _write_onigimon_nickname),
    "hexagon_island_name": (_read_island_name, _write_island_name),
}


def read(key, default=None):
    entry = ACCESSORS.get(str(key or ""))
    if entry is None:
        return default
    try:
        value = entry[0]()
    except Exception as exc:  # noqa: BLE001 - a broken game must not blank the page
        print(f"[Onigiri] settings_web games: could not read {key!r}: {exc}")
        return default
    # A manager that has nothing yet (no companion picked, no island named)
    # answers with "", which is the field's empty state, not an error.
    return value


def write(key, value):
    entry = ACCESSORS.get(str(key or ""))
    if entry is None:
        raise KeyError(f"unknown game accessor {key!r}")
    entry[1](value)


# ── page context ──────────────────────────────────────────────────────────────


def nook_context():
    """Level and name, so the page can gate the custom-name row the same way
    the classic dialog did (rename unlocks at level 5)."""
    try:
        progress = _nook().manager.get_progress()
        return {
            "level": int(getattr(progress, "level", 0) or 0),
            "name": str(getattr(progress, "name", "") or ""),
        }
    except Exception as exc:  # noqa: BLE001
        print(f"[Onigiri] settings_web games: Nook progress unavailable: {exc}")
        return {"level": 0, "name": ""}


def ankimon_status():
    """(state, title, detail) for the Onigimon dependency banner. `state` is
    ok | warn | error and only picks the banner colour."""
    try:
        status = _onigimon().manager.bridge.status()
    except Exception as exc:  # noqa: BLE001
        return {
            "state": "error",
            "title": tr("ankimon_status_unknown", "Could not check Ankimon"),
            "detail": str(exc),
        }

    if status == "missing":
        return {
            "state": "error",
            "title": tr("ankimon_status_missing_title", "Ankimon is not installed"),
            "detail": tr(
                "ankimon_status_missing_detail",
                "Onigimon runs on top of Ankimon. Install the Ankimon add-on, restart "
                "Anki, then choose a Pokémon in Ankimon's Pokémon PC.",
            ),
        }
    if status in ("starter_needed", "no_collection"):
        return {
            "state": "warn",
            "title": tr("ankimon_status_no_pokemon_title", "No Pokémon chosen yet"),
            "detail": tr(
                "ankimon_status_no_pokemon_detail",
                "Ankimon is installed. Open Ankimon's Pokémon PC and pick a Pokémon — "
                "that Pokémon becomes your Onigimon companion.",
            ),
        }
    return {
        "state": "ok",
        "title": tr("ankimon_status_ready_title", "Ankimon is installed"),
        "detail": tr(
            "ankimon_status_ready_detail",
            "The active Pokémon in Ankimon's Pokémon PC is your Onigimon companion.",
        ),
    }


def sprite_url(raw_url):
    """Ankimon serves its sprites from its own add-on folder, so the URL it
    hands out (`/_addons/<id>/...`) is already loadable inside a webview — the
    classic dialog only had to resolve it to a local path because QPixmap
    cannot read a URL. Anything else is passed through untouched."""
    return str(raw_url or "")


def companions(refresh=False):
    """The Onigimon roster, in the order the classic grid used: the active one
    first, then favourites, then alphabetically."""
    onigimon = _onigimon()
    manager = onigimon.manager
    if refresh:
        try:
            manager.bridge.clear_cache()
        except Exception:
            pass
    try:
        manager.sync_active_companion_from_ankimon()
    except Exception:
        pass

    try:
        status = manager.bridge.status()
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": str(exc), "active": "", "companions": []}

    active = ""
    try:
        active = str(manager.load().active_companion_id or "")
    except Exception:
        pass

    messages = {
        "missing": tr("onigimon_status_missing", ""),
        "starter_needed": tr("onigimon_status_starter_needed", ""),
        "no_collection": tr("onigimon_status_no_collection", ""),
    }
    if status != "ready":
        return {
            "status": status,
            "message": messages.get(status, tr("onigimon_status_open_page", "")),
            "active": active,
            "companions": [],
        }

    try:
        roster = list(manager.get_available_companions())
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": str(exc), "active": active, "companions": []}

    roster.sort(key=lambda p: (
        str(p.get("ankimon_id")) != str(active),
        not bool(p.get("is_favorite")),
        str(p.get("name", "")).lower(),
    ))
    items = [
        {
            "id": str(pokemon.get("ankimon_id", "")),
            "name": str(pokemon.get("name", "") or "?"),
            "level": int(pokemon.get("level", 1) or 1),
            "sprite": sprite_url(pokemon.get("sprite_url")),
            "favorite": bool(pokemon.get("is_favorite")),
        }
        for pokemon in roster
    ]
    return {
        "status": "ready" if items else "no_companions",
        "message": tr("onigimon_status_ready", "") if items else tr("onigimon_status_no_companions", ""),
        "active": active,
        "companions": items,
    }


def active_companion_preview():
    """Companion details and both sprite modes for the live scene preview."""
    try:
        manager = _onigimon().manager
        companion = manager.active_companion()
        if not companion:
            return {
                "name": "Onigimon",
                "level": 1,
                "sprite": "",
                "staticSprites": [],
                "animatedSprites": [],
            }
        companion_data = asdict(companion)
        static_sprites = [
            sprite_url(url)
            for url in manager.sprite_urls_for_companion(companion_data, motion="static")
            if url
        ]
        animated_sprites = [
            sprite_url(url)
            for url in manager.sprite_urls_for_companion(companion_data, motion="gif")
            if url
        ]
        return {
            "name": str(manager.companion_display_name(companion) or "Onigimon"),
            "level": int(getattr(companion, "level", 1) or 1),
            # `sprite` remains for older settings.js copies still loaded in an
            # already-open dialog. New previews choose the matching list as
            # soon as Static/Animated changes, without waiting for auto-save.
            "sprite": static_sprites[0] if static_sprites else sprite_url(
                getattr(companion, "sprite_url", "")
            ),
            "staticSprites": static_sprites,
            "animatedSprites": animated_sprites,
        }
    except Exception:
        return {
            "name": "Onigimon",
            "level": 1,
            "sprite": "",
            "staticSprites": [],
            "animatedSprites": [],
        }


def hexagon_context():
    """Island name, key ownership and the coin balance versus the key price."""
    try:
        hexagon_land = _hexagon()
        state = hexagon_land.manager.load()
        cost = int(hexagon_land.KEYS_OF_THE_ISLAND_COST)
        coins = int(getattr(state, "hex_coins", 0) or 0)
        owns = bool(getattr(state, "keys_of_the_island", False))
        return {
            "owns_keys": owns,
            "coins": coins,
            "cost": cost,
            "affordable": coins >= cost,
            "name": str(hexagon_land.manager.island_display_name(state) or ""),
        }
    except Exception as exc:  # noqa: BLE001
        print(f"[Onigiri] settings_web games: Hexagon Land state unavailable: {exc}")
        return {"owns_keys": False, "coins": 0, "cost": 0, "affordable": False, "name": ""}


BENTO_GAME_STYLE = {
    # add-on id -> (logo file under system_files/peace_logos, accent)
    "516325516": ("Focumon.png", "#F2B705"),
    "1799253175": ("lofi_town.png", "#9EAC32"),
    "585575504": ("Senchado.png", "#58A866"),
    "Byte": ("byte.png", "#7A4A55"),
}


def bento_games(asset_url):
    """The Bento mini-games, detected or not, with the buttons each exposes.

    `asset_url` turns an addon-relative path into something the webview can
    load — passed in so this module needs no knowledge of the media server."""
    from ..api import bento as bento_api

    try:
        detected = bento_api.get_game_widgets()
    except Exception as exc:  # noqa: BLE001
        print(f"[Onigiri] settings_web games: Bento probe failed: {exc}")
        detected = {}

    out = []
    for addon_id, fallback_name in bento_api.GAME_ADDONS.items():
        game = detected.get(addon_id)
        logo, accent = BENTO_GAME_STYLE.get(addon_id, ("", ""))
        out.append({
            "id": addon_id,
            "name": (game or {}).get("name") or fallback_name,
            "detected": game is not None,
            "accent": accent,
            "logo": asset_url(f"system_files/peace_logos/{logo}") if logo else "",
            "has_settings": callable((game or {}).get("settings_callback")),
            "has_open": callable((game or {}).get("open_callback")),
        })
    return out


# ── actions (bridge command "games_action") ───────────────────────────────────


def _confirm(parent, title, question):
    from aqt.qt import QMessageBox
    from aqt.theme import theme_manager

    # Keep the confirmation native (it remains a real Qt modal dialog, so it
    # correctly owns focus above the WebView) while matching Onigiri's flat,
    # minimal surfaces instead of the platform's legacy bright button chrome.
    dark = bool(getattr(theme_manager, "night_mode", False))
    panel = "#242424" if dark else "#ffffff"
    inset = "#303030" if dark else "#f2f2f2"
    border = "#454545" if dark else "#dcdde1"
    fg = "#f4f4f5" if dark else "#202124"
    muted = "#a1a1a4" if dark else "#63666c"
    accent = "#00A982"
    box = QMessageBox(parent)
    box.setWindowTitle("Onigiri")
    box.setText(title or "Confirm action")
    box.setInformativeText(question or "This action cannot be undone.")
    box.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    box.setDefaultButton(QMessageBox.StandardButton.No)
    box.setStyleSheet(f"""
        QMessageBox {{ background: {panel}; color: {fg}; }}
        QMessageBox QLabel {{ color: {fg}; background: transparent; }}
        QMessageBox QLabel#qt_msgbox_informativelabel {{ color: {muted}; }}
        QMessageBox QPushButton {{
            min-width: 72px; min-height: 32px; padding: 0 14px;
            border: 1px solid {border}; border-radius: 10px;
            background: {inset}; color: {fg};
        }}
        QMessageBox QPushButton:hover {{ background: {inset}; border-color: {accent}; }}
        QMessageBox QPushButton:default {{ background: {accent}; color: #ffffff; border-color: {accent}; }}
    """)
    return box.exec() == QMessageBox.StandardButton.Yes


def _info(message):
    from ..onigiri_notifications import notify_info

    notify_info(message)


def run_action(name, parent=None, arg=""):
    """Performs one page button. Returns a JSON-able reply for the page."""
    name = str(name or "")

    if name == "nook_rush_sync":
        if not _confirm(
            parent,
            tr("recipe_rush_sync_title", "Nook Rush Sync"),
            tr(
                "recipe_rush_sync_confirm",
                "Pick a fresh Nook Rush for the currently equipped Nook, "
                "replacing today's ticket? Today's card progress is kept.",
            ),
        ):
            return {"ok": True, "cancelled": True}
        success, message = _nook().manager.force_resync_recipe_rush()
        if success:
            _info(tr("recipe_rush_sync_success", "Synced! New Rush: {name}").format(name=message))
        else:
            _info(message)
        return {"ok": True}

    if name == "nook_reset_progress":
        if not _confirm(parent, tr("reset", "Reset"), tr("reset_restaurant_confirm", "")):
            return {"ok": True, "cancelled": True}
        _nook().manager.reset_progress()
        _info(tr("restaurant_level_reset_info", ""))
        return {"ok": True, "reload": True}

    if name == "nook_reset_coins":
        if not _confirm(parent, tr("reset", "Reset"), tr("reset_coins_confirm", "")):
            return {"ok": True, "cancelled": True}
        _nook().manager.reset_coins()
        _info(tr("coins_reset_info", ""))
        return {"ok": True}

    if name == "nook_reset_purchases":
        if not _confirm(parent, tr("reset", "Reset"), tr("reset_purchases_confirm", "")):
            return {"ok": True, "cancelled": True}
        _nook().manager.reset_purchases()
        _info(tr("purchases_reset_info", ""))
        return {"ok": True}

    if name == "hexagon_open":
        _hexagon().open_hexagon_land_dialog()
        return {"ok": True}

    if name == "hexagon_buy_coins":
        _hexagon().open_buy_hex_coins()
        return {"ok": True}

    if name == "hexagon_buy_keys":
        _info(_hexagon().manager.buy_keys_of_the_island())
        return {"ok": True, "hexagon": hexagon_context()}

    if name == "bento_settings" or name == "bento_open":
        from ..api import bento as bento_api

        game = bento_api.get_game_widgets().get(str(arg or ""))
        callback = (game or {}).get(
            "settings_callback" if name == "bento_settings" else "open_callback"
        )
        if callable(callback):
            callback()
        return {"ok": True}

    return {"ok": False, "error": f"unknown action {name!r}"}


# ── post-save hooks ───────────────────────────────────────────────────────────


def sync_nook_flags(conf):
    """get_progress() only reads the config on its first migration; after that
    it trusts its own state. Without pushing these three flags across, the chip
    stays stuck at whatever it was the first time it ran."""
    restaurant = conf.get("restaurant_level", {}) or {}
    manager = _nook().manager
    manager.set_enabled(bool(restaurant.get("enabled", False)))
    manager.set_notifications_enabled(bool(restaurant.get("notifications_enabled", True)))
    manager.set_profile_bar_visibility(bool(restaurant.get("show_profile_bar_progress", True)))


def initialize_enabled_hooks(conf):
    """Import (and therefore install the Anki hooks of) every game the user has
    just switched on, so it starts working without a restart."""
    try:
        if (conf.get("restaurant_level", {}) or {}).get("enabled", False):
            from ..gamification import nook_level  # noqa: F401
        if (conf.get("onigimon", {}) or {}).get("enabled", False):
            from ..gamification import onigimon  # noqa: F401
        if (conf.get("mochi_messages", {}) or {}).get("enabled", False):
            from ..gamification import mochi_messages  # noqa: F401
        if ((conf.get("achievements", {}) or {}).get("focusDango", {}) or {}).get("enabled", False):
            from ..gamification import focus_dango

            focus_dango.setup_focus_dango()
    except Exception as exc:  # noqa: BLE001
        print(f"[Onigiri] settings_web games: could not refresh gamification hooks: {exc}")


def mochi_icon_exists(relative_path):
    """True when a custom messenger image is still on disk. The classic dialog
    fell back to Mochi whenever the file went missing; the schema's icon-source
    choice does the same through this check."""
    path = str(relative_path or "").strip()
    if not path:
        return False
    if not os.path.isabs(path):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, path)
    return os.path.exists(path)
