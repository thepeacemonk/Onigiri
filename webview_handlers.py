import json
import os
import shutil
from datetime import datetime
from urllib.parse import unquote
from typing import Tuple, Any, List
from aqt.deckbrowser import DeckBrowser
from .decks import tree_updater as deck_tree_updater
from .decks import drag_drop as deck_drag_drop
from .decks import move as move_deck
from .onigiri_notifications import notify as tooltip
from aqt import mw
from aqt.qt import QApplication, QFileDialog, QInputDialog, QWidget, Qt
from aqt.utils import askUser
from anki.decks import DeckId
from . import config
from .translations import tr


# Every user-facing string the injected deck-browser scripts can show. The JS
# reads them off window.ONIGIRI_STRINGS through OnigiriI18n.t(key, fallback), so
# the dialogs follow the add-on language instead of being stuck in English.
_WEBVIEW_STRING_KEYS = (
    "add", "browse", "stats", "sync", "settings", "onigiri_games", "more",
    "home", "expand_sidebar", "collapse_sidebar", "drag_to_reorder_or_move",
    "cancel", "close", "save", "remove", "create_action", "move_action",
    "create_deck_title", "create_deck_subtitle", "deck_name_label",
    "deck_name_placeholder", "parent_deck_label", "search_decks",
    "no_matching_decks", "top_level", "add_subdeck_title", "subdeck_name_label",
    "subdeck_name_placeholder",
    "moving_label", "search_destination_decks", "rename_deck_title",
    "rename_leaf_name", "rename_full_path", "rename_editing_full_path",
    "deck_name_empty", "edit_icon", "type_your_own", "icon_label",
    "reset_to_default_tooltip", "search_icons_placeholder",
    "ctx_rename", "ctx_move_to", "ctx_change_icon", "markers",
    "ctx_remove_marker", "ctx_deadline", "ctx_deck_options", "ctx_export_deck",
    "ctx_copy_deck_id", "ctx_delete_deck", "ctx_favorite_selected",
    "ctx_remove_favorites", "delete_selected", "marker_red", "marker_blue",
    "marker_green", "marker_yellow", "get_shared", "create_deck", "import_file",
    "hashi_notes_title", "sort_default_order", "sort_a_to_z", "sort_z_to_a",
    "sort_most_due", "sort_most_new", "sort_most_reviews",
    "sort_favorites_first", "sort_custom_order",
)


def webview_strings_script() -> str:
    """Head script that publishes the translated strings to the page."""
    strings = {key: tr(key) for key in _WEBVIEW_STRING_KEYS}
    return (
        "<script>window.ONIGIRI_STRINGS=%s;"
        "window.OnigiriI18n={t:function(key,fallback){"
        "var table=window.ONIGIRI_STRINGS||{};"
        "return (table[key]||fallback||key);}};</script>"
        % json.dumps(strings, ensure_ascii=False)
    )


_ICON_PRIORITY = [
    "deck.svg", "folder.svg", "star.svg", "filtered-deck.svg",
    "add-card.svg", "add-deck.svg", "add-subdeck.svg",
    "add.svg", "browse.svg", "stats.svg", "sync.svg", "settings.svg",
    "rename.svg", "mark_circle.svg", "focus.svg", "gamepad.svg",
]

def _refresh_deck_browser(context) -> None:
    if isinstance(context, DeckBrowser):
        context._render_data = None
        deck_tree_updater.refresh_deck_tree_state(context)


# Pending deck deletion that can still be reverted from the undo toast.
# Holds the collection undo step recorded right after the deletion so we can
# verify nothing else happened before calling col.undo().
_PENDING_DECK_DELETE: dict = {}


def _open_delete_deck_dialog(context, deck_ids: List[int]) -> bool:
    if not isinstance(context, DeckBrowser) or not deck_ids:
        return False
    many = len(deck_ids) > 1
    deck_name = _deck_name(str(deck_ids[0])) if not many else ""
    card_count = None
    try:
        card_count = mw.col.decks.card_count(
            [DeckId(did) for did in deck_ids], include_subdecks=True
        )
    except Exception:
        pass
    strings = {
        "title": tr("del_deck_title_plural") if many else tr("del_deck_title"),
        "subtitle": tr("del_deck_selected").format(len(deck_ids)) if many else deck_name,
        # Template keeps a {} placeholder; JS swaps it for the bolded value.
        "message": tr("del_deck_message_plural") if many else tr("del_deck_message"),
        "messageValue": str(len(deck_ids)) if many else f"'{deck_name}'",
        "cards": tr("del_deck_cards_count").format(card_count) if card_count is not None else "",
        "subdecksNote": tr("del_deck_subdecks_note"),
        "cancel": tr("cancel"),
        "confirm": tr("del_deck_confirm"),
    }
    payload = json.dumps(
        {"deckIds": deck_ids, "deckName": deck_name, "strings": strings},
        ensure_ascii=False,
    )
    context.web.eval(
        f"if(window.OnigiriDeleteDeckDialog)OnigiriDeleteDeckDialog.open({payload});"
    )
    return True


def _delete_decks_with_undo(context, deck_ids: List[int]) -> None:
    many = len(deck_ids) > 1
    name = _deck_name(str(deck_ids[0])) if not many else ""
    undoable = True
    try:
        mw.col.decks.remove([DeckId(did) for did in deck_ids])
    except Exception:
        undoable = False
        for did in deck_ids:
            mw.col.decks.rem(did, cardsToo=True)
    mw.col.setMod()
    try:
        mw.update_undo_actions()
    except Exception:
        pass

    step = None
    if undoable:
        try:
            step = mw.col.undo_status().last_step
        except Exception:
            undoable = False
    _PENDING_DECK_DELETE.clear()
    if undoable and step is not None:
        _PENDING_DECK_DELETE.update(
            {"step": step, "name": name, "count": len(deck_ids)}
        )

    _refresh_deck_browser(context)
    if isinstance(context, DeckBrowser):
        toast = json.dumps(
            {
                "title": tr("del_deck_deleted_title_plural") if many else tr("del_deck_deleted_title"),
                "message": (
                    tr("del_deck_deleted_msg_plural").format(len(deck_ids))
                    if many
                    else tr("del_deck_deleted_msg").format(name)
                ),
                "undoLabel": tr("del_deck_undo"),
                "iconName": "trash.svg",
                "canUndo": bool(undoable and step is not None),
            },
            ensure_ascii=False,
        )
        context.web.eval(
            f"if(window.OnigiriDeleteDeckDialog)OnigiriDeleteDeckDialog.showUndoToast({toast});"
        )


def _undo_deck_delete(context) -> None:
    pending = dict(_PENDING_DECK_DELETE)
    _PENDING_DECK_DELETE.clear()
    if not pending:
        tooltip(tr("del_deck_nothing_restore"))
        return
    try:
        if mw.col.undo_status().last_step != pending.get("step"):
            tooltip(tr("del_deck_cannot_restore"))
            return
        mw.col.undo()
    except Exception as e:
        print(f"Onigiri: Error undoing deck deletion: {e}")
        tooltip(tr("del_deck_restore_failed"))
        return
    try:
        mw.update_undo_actions()
    except Exception:
        pass
    _refresh_deck_browser(context)
    if isinstance(context, DeckBrowser):
        count = int(pending.get("count", 1))
        toast = json.dumps(
            {
                "title": tr("del_deck_restored_title"),
                "message": (
                    tr("del_deck_restored_msg_plural").format(count)
                    if count > 1
                    else tr("del_deck_restored_msg").format(pending.get("name", ""))
                ),
                "iconName": "undo-2.svg",
                "canUndo": False,
            },
            ensure_ascii=False,
        )
        context.web.eval(
            f"if(window.OnigiriDeleteDeckDialog)OnigiriDeleteDeckDialog.showUndoToast({toast});"
        )




def _deck_name(deck_id: str) -> str:
    try:
        return mw.col.decks.name(DeckId(int(deck_id)))
    except Exception:
        deck = mw.col.decks.get(DeckId(int(deck_id)))
        return deck.get("name", "") if isinstance(deck, dict) else ""


def _rename_deck(deck_id: str, new_name: str) -> None:
    deck = mw.col.decks.get(DeckId(int(deck_id)))
    if not deck:
        raise ValueError("Deck not found")
    try:
        mw.col.decks.rename(deck, new_name)
    except TypeError:
        mw.col.decks.rename(DeckId(int(deck_id)), new_name)
    mw.col.setMod()


def _addon_path() -> str:
    return os.path.dirname(__file__)


def _addon_package() -> str:
    return mw.addonManager.addonFromModule(__name__)


def _custom_icon_dir() -> str:
    path = os.path.join(_addon_path(), "user_files", "custom_deck_icons")
    os.makedirs(path, exist_ok=True)
    return path


def _user_icons_dir() -> str:
    path = os.path.join(_addon_path(), "user_files", "icons")
    os.makedirs(path, exist_ok=True)
    return path


def _icon_label(filename: str) -> str:
    stem = os.path.splitext(filename)[0]
    return stem.replace("_", " ").replace("-", " ").title()


def _icon_payload(deck_id: str) -> dict:
    addon_package = _addon_package()
    addon_path = _addon_path()
    system_dir = os.path.join(addon_path, "system_files", "system_icons", "available_for_users")
    custom_dir = _custom_icon_dir()

    icons = []
    seen_icon_names = set()
    for directory, url_prefix in (
        (custom_dir, f"/_addons/{addon_package}/user_files/custom_deck_icons"),
        (_user_icons_dir(), f"/_addons/{addon_package}/user_files/icons"),
    ):
        if os.path.isdir(directory):
            for name in sorted(os.listdir(directory), key=str.lower):
                lower = name.lower()
                if lower.endswith(".svg") and name not in seen_icon_names:
                    seen_icon_names.add(name)
                    icons.append({
                        "name": name,
                        "label": _icon_label(name),
                        "url": f"{url_prefix}/{name}",
                        "system": False,
                    })

    if os.path.isdir(system_dir):
        system_files = [
            name for name in os.listdir(system_dir)
            if name.lower().endswith(".svg")
        ]
        priority = {name: index for index, name in enumerate(_ICON_PRIORITY)}
        for name in sorted(system_files, key=lambda item: (priority.get(item, 999), item.lower())):
            icons.append({
                "name": f"system:{name}",
                "label": _icon_label(name),
                "url": f"/_addons/{addon_package}/system_files/system_icons/available_for_users/{name}",
                "system": True,
            })

    images = []
    seen_image_names = set()
    for directory, url_prefix in (
        (custom_dir, f"/_addons/{addon_package}/user_files/custom_deck_icons"),
        (_user_icons_dir(), f"/_addons/{addon_package}/user_files/icons"),
    ):
        if os.path.isdir(directory):
            for name in sorted(os.listdir(directory), key=str.lower):
                if name.lower().endswith(".png") and name not in seen_image_names:
                    seen_image_names.add(name)
                    images.append({
                        "name": name,
                        "label": _icon_label(name),
                        "url": f"{url_prefix}/{name}",
                        "system": False,
                    })

    custom_icons = mw.col.conf.get("onigiri_custom_deck_icons", {})
    current = custom_icons.get(str(deck_id), {})
    # "" means "follow the theme's --icon-color", the default for decks that
    # have never had an explicit colour picked. Entries saved before the
    # light/dark split only ever wrote "color" — colorDark falls back to it so
    # those decks keep reading as one linked colour instead of picking up a
    # blank dark slot.
    light_color = current.get("color", "")
    dark_color = current.get("colorDark", light_color)
    return {
        "deckId": str(deck_id),
        "current": {
            "icon": current.get("icon", ""),
            "color": light_color,
            "colorDark": dark_color,
        },
        "emojiBaseUrl": f"/_addons/{addon_package}/system_files/emojis",
        "icons": icons,
        "images": images,
    }


def _open_icon_modal(context, deck_id: str) -> None:
    payload = json.dumps(_icon_payload(deck_id))
    context.web.eval(f"if(window.OnigiriIconChooser){{OnigiriIconChooser.open({payload});}}")


def _run_deck_icon_color_picker(context, current: str):
    """Onigiri's native colour picker, floated in its own always-on-top
    translucent top-level window. Mirrors hashi_notes._open_color_dialog: the
    webview's native surface would otherwise paint over a picker parented to
    it directly."""
    from .onigiri_color_picker import OnigiriColorDialog

    host = QWidget(None)
    host.setWindowFlags(
        Qt.WindowType.Tool
        | Qt.WindowType.FramelessWindowHint
        | Qt.WindowType.WindowStaysOnTopHint
    )
    host.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    host.setGeometry(mw.frameGeometry())
    host.show()
    host.raise_()
    host.activateWindow()
    try:
        return OnigiriColorDialog.getColor(current, host)
    finally:
        host.close()
        host.deleteLater()
        mw.raise_()
        mw.activateWindow()


def _open_rename_modal(context, deck_id: str) -> None:
    full_name = _deck_name(deck_id)
    leaf_name = full_name.split("::")[-1]
    parent_prefix = full_name.rsplit("::", 1)[0] if "::" in full_name else ""
    payload = json.dumps({
        "deckId": str(deck_id),
        "fullName": full_name,
        "leafName": leaf_name,
        "parentPrefix": parent_prefix,
    })
    context.web.eval(
        f"if(window.OnigiriRenameDialog){{OnigiriRenameDialog.open({payload});}}"
        f"else if(window.OnigiriRenameDeckModal){{OnigiriRenameDeckModal.open({payload});}}"
    )


def _refresh_icon_modal(context, deck_id: str) -> None:
    payload = json.dumps(_icon_payload(deck_id))
    context.web.eval(f"if(window.OnigiriIconChooser){{OnigiriIconChooser.refreshData({payload});}}")


def _unique_dest_path(directory: str, filename: str) -> str:
    base, ext = os.path.splitext(os.path.basename(filename))
    candidate = os.path.join(directory, base + ext)
    index = 2
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base}-{index}{ext}")
        index += 1
    return candidate


def _add_icon_files(context, deck_id: str, file_type: str) -> None:
    if file_type == "image":
        title = "Select PNG images"
        pattern = "PNG Images (*.png)"
    else:
        title = "Select SVG icons"
        pattern = "SVG Icons (*.svg)"

    files, _ = QFileDialog.getOpenFileNames(mw, title, "", pattern)
    if not files:
        return

    dest_dir = _custom_icon_dir()
    for path in files:
        if not os.path.isfile(path):
            continue
        dest = _unique_dest_path(dest_dir, os.path.basename(path))
        try:
            shutil.copy2(path, dest)
        except Exception as e:
            print(f"Onigiri: Error importing icon {path}: {e}")
            tooltip(tr("err_import_icon").format(e))

    _refresh_icon_modal(context, deck_id)


def _delete_icon_file(context, deck_id: str, filename: str) -> None:
    if filename.startswith("system:"):
        return
    safe_name = os.path.basename(filename)
    if safe_name != filename:
        return
    path = os.path.join(_custom_icon_dir(), safe_name)
    try:
        if os.path.exists(path):
            os.remove(path)
        _refresh_icon_modal(context, deck_id)
    except Exception as e:
        print(f"Onigiri: Error deleting icon {safe_name}: {e}")
        tooltip(tr("err_delete_icon").format(e))


def _conf_list(key: str) -> List[str]:
    return [str(value) for value in mw.col.conf.get(key, [])]


def _build_create_deck_payload() -> dict:
    deck_names = deck_drag_drop._deck_names_by_id()
    addon_package = _addon_package()
    icon_cache = {}

    def icon_url(icon_key: str) -> str:
        if icon_key not in icon_cache:
            filename = {
                "deck": "deck.svg",
                "subdeck": "subdeck.svg",
                "folder": "folder.svg",
                "filtered_deck": "filtered-deck.svg",
            }.get(icon_key, f"{icon_key}.svg")
            icon_cache[icon_key] = f"/_addons/{addon_package}/system_files/system_icons/unavailable_for_users/{filename}"
        return icon_cache[icon_key]

    folder_names = set()
    for name in deck_names.values():
        parts = name.split("::")
        for index in range(1, len(parts)):
            folder_names.add("::".join(parts[:index]))

    filtered_ids = set()
    try:
        for deck in mw.col.decks.all():
            if deck.get("dyn", 0):
                filtered_ids.add(str(int(deck.get("id", 0))))
    except Exception:
        pass

    destinations = [{
        "id": "__root__",
        "name": tr("top_level"),
        "path": tr("top_level"),
        "depth": 0,
        "kind": "root",
        "iconUrl": icon_url("folder"),
    }]

    for did, name in sorted(deck_names.items(), key=lambda item: (item[1].count("::"), item[1].lower())):
        if did in filtered_ids:
            continue
        icon_key = "folder" if name in folder_names else ("subdeck" if "::" in name else "deck")
        destinations.append({
            "id": did,
            "name": deck_drag_drop._leaf_name(name),
            "path": name,
            "depth": name.count("::"),
            "kind": "deck",
            "iconUrl": icon_url(icon_key),
        })

    return {"destinations": destinations}

def handle_webview_cmd(handled: Tuple[bool, Any], cmd: str, context) -> Tuple[bool, Any]:
    """
    Centralized handler for webview commands from the deck browser.
    """
    # The dedicated Onigimon WebUI owns its commands and pushes its own state.
    if type(context).__name__ == "OnigimonWebDialog":
        return handled
    parent = getattr(context, "parent", None)
    if parent and callable(parent) and type(parent()).__name__ == "OnigimonWebDialog":
        return handled

    if cmd == "onigiri_welcome_dismissed":
        try:
            from . import config
            conf = config.get_config()
            conf["showWelcomePopup"] = False
            config.write_config(conf)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error dismissing welcome: {e}")
            return (True, None)

    if cmd.startswith("onigiri_heatmap_browse:"):
        try:
            from aqt import dialogs
            from . import heatmap

            date_key = cmd[len("onigiri_heatmap_browse:"):]
            today_start = mw.col.sched.day_cutoff - 86400
            today_date_key = datetime.fromtimestamp(today_start).strftime("%Y-%m-%d")
            search = heatmap.browser_search_for_date(date_key, today_date_key)
            dialogs.open("Browser", mw, search=(search,))
        except Exception as e:
            print(f"Onigiri: Error browsing heatmap date: {e}")
            tooltip(tr("err_open_browser").format(e))
        return (True, None)

    if cmd == "openGamificationSettings":
        try:
            from . import settings_web
            settings_web.open_settings("gamification")
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error opening gamification settings: {e}")
            return (True, None)

    if cmd == "openOnigimonSettings":
        try:
            from . import settings_web
            settings_web.open_settings("onigimon")
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error opening Onigimon settings: {e}")
            return (True, None)

    if cmd == "openHashiGallery":
        try:
            from . import hashi_notes
            hashi_notes.open_hashi_gallery(mw)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error opening Hashi Notes gallery: {e}")
            return (True, None)

    if cmd.startswith("hashiWidget:open:"):
        # The dashboard widget opens a note straight into the editor pop-up;
        # a note that has since been trashed falls back to the gallery.
        try:
            from . import hashi_notes
            note = hashi_notes.get_note(cmd[len("hashiWidget:open:"):])
            if note and not note.get("trashed_at"):
                hashi_notes.open_hashi_note_popup("deckbrowser", mw, note=note)
            else:
                hashi_notes.open_hashi_gallery(mw)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error opening Hashi note from widget: {e}")
            return (True, None)

    if cmd == "openPrepStation":
        try:
            from . import prep_station
            prep_station.open_prep_station()
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error opening Prep Station: {e}")
            return (True, None)

    if cmd == "openHexagonLand":
        try:
            from .gamification import hexagon_land
            hexagon_land.open_hexagon_land_dialog()
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error opening Hexagon Land: {e}")
            return (True, None)

    if cmd == "buyHexCoins":
        try:
            from .gamification import hexagon_land
            hexagon_land.open_buy_hex_coins()
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error opening Hex Coin link: {e}")
            return (True, None)

    if cmd.startswith("onigimon_feed:"):
        try:
            from .gamification import onigimon
            item_key = cmd.split(":", 1)[1]
            message = onigimon.manager.use_item(item_key)
            _refresh_deck_browser(context)
            if message:
                tooltip(message, context=context, title="", variant="onigimon", hide_icon=True, hide_title=True, centered=True)
            else:
                tooltip(tr("no_onigimon_item"), context=context, title="", variant="onigimon", hide_icon=True, hide_title=True, centered=True)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error feeding Onigimon: {e}")
            return (True, None)

    if cmd.startswith("onigimon_category:"):
        try:
            from .gamification import onigimon
            category_id = cmd.split(":", 1)[1]
            message = onigimon.manager.category_status_message(category_id)
            if message:
                tooltip(message, context=context, title="", variant="onigimon", hide_icon=True, hide_title=True, centered=True)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error reading Onigimon category: {e}")
            return (True, None)

    if cmd == "onigimon_play":
        try:
            from .gamification import onigimon
            message = onigimon.manager.play()
            _refresh_deck_browser(context)
            if message:
                tooltip(message, context=context, title="", variant="onigimon", hide_icon=True, hide_title=True, centered=True)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error playing with Onigimon: {e}")
            return (True, None)

    if cmd == "onigimon_daily_gift":
        try:
            from .gamification import onigimon
            message = onigimon.manager.claim_daily_gift()
            _refresh_deck_browser(context)
            tooltip(message or "Today's Onigimon gift is already claimed.", context=context, title="", variant="onigimon", hide_icon=True, hide_title=True, centered=True)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error claiming Onigimon gift: {e}")
            return (True, None)

    if cmd.startswith("onigimon_rename:"):
        try:
            from .gamification import onigimon
            name = unquote(cmd.split(":", 1)[1]).strip()
            if not name:
                tooltip(tr("onigimon_choose_name_first"))
                return (True, None)
            if onigimon.manager.rename_active_companion(name):
                tooltip(tr("onigimon_renamed_to").format(name), context=context, title="", variant="onigimon", hide_icon=True, hide_title=True, centered=True)
            else:
                tooltip(tr("onigimon_choose_companion_first"), context=context, title="", variant="onigimon", hide_icon=True, hide_title=True, centered=True)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error renaming Onigimon: {e}")
            return (True, None)

    if cmd == "onigiri_create_deck":
        try:
            payload = _build_create_deck_payload()
            if isinstance(context, DeckBrowser):
                context.web.eval(
                    "if(window.OnigiriCreateDeckDialog)OnigiriCreateDeckDialog.open(%s);"
                    % json.dumps(payload, ensure_ascii=True)
                )
        except Exception as e:
            print(f"Onigiri: Error opening Create Deck dialog: {e}")
            tooltip(tr("err_create_deck_dialog").format(e))
            if isinstance(context, DeckBrowser):
                context.web.eval("if(window.OnigiriEngine)OnigiriEngine.clearDialogFocus();")
        return (True, None)

    if cmd == "onigiri_toggle_sidebar":
        if isinstance(context, DeckBrowser):
            context.web.eval(
                "var s=document.querySelector('.sidebar-left');"
                "if(s){"
                "  if(typeof onigiriToggleSidebar==='function'){onigiriToggleSidebar();}"
                "  else if(s.classList.contains('sidebar-collapsed')){"
                "    if(typeof onigiriExpandSidebar==='function')onigiriExpandSidebar();"
                "    else{s.classList.remove('sidebar-collapsed');pycmd('saveSidebarState:false');}"
                "  }else{"
                "    if(typeof onigiriCollapseSidebar==='function')onigiriCollapseSidebar();"
                "    else{s.classList.add('sidebar-collapsed');pycmd('saveSidebarState:true');}"
                "  }"
                "}"
            )
        return (True, None)

    if cmd.startswith("saveSidebarState:"):
        try:
            value = cmd.split(":", 1)[1].lower() == "true"
            mw.col.conf["onigiri_sidebar_collapsed"] = value
            mw.col.setMod()
        except Exception as e:
            print(f"Onigiri: Error saving sidebar state: {e}")
        return (True, None)

    if cmd.startswith("saveDeckFocusState:"):
        try:
            value = cmd.split(":", 1)[1].lower() == "true"
            mw.col.conf["onigiri_deck_focus_mode"] = value
            mw.col.conf["onigiri_deck_cycle_state"] = 1 if value else 0
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

    if cmd.startswith("saveSidebarWidth:"):
        try:
            value = int(float(cmd.split(":", 1)[1]))
            if value > 0:
                mw.col.conf["modern_menu_sidebar_width"] = value
                mw.col.setMod()
        except Exception as e:
            print(f"Onigiri: Error saving sidebar width: {e}")
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
        except Exception as e:
            print(f"Onigiri: Error saving sidebar size: {e}")
        return (True, None)

    if cmd in ("onigiri_filter_favourites", "onigiri_filter_favorites"):
        try:
            current = bool(
                mw.col.conf.get("onigiri_show_favourites", False)
                or mw.col.conf.get("onigiri_show_favorites", False)
            )
            next_value = not current
            mw.col.conf["onigiri_show_favourites"] = next_value
            mw.col.conf["onigiri_show_favorites"] = next_value
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                context._render_data = None
                context._renderPage()
        except Exception as e:
            print(f"Onigiri: Error toggling favorites filter: {e}")
            tooltip(tr("err_filter_failed").format(e))
        return (True, None)

    if cmd == "onigiri_filter_marked":
        try:
            current = bool(mw.col.conf.get("onigiri_show_marked", False))
            mw.col.conf["onigiri_show_marked"] = not current
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                context._render_data = None
                context._renderPage()
        except Exception as e:
            print(f"Onigiri: Error toggling marked filter: {e}")
            tooltip(tr("err_filter_failed").format(e))
        return (True, None)

    if cmd.startswith("onigiri_deck_search:"):
        try:
            query = cmd.split(":", 1)[1]
            if isinstance(context, DeckBrowser):
                new_html = deck_tree_updater._render_deck_search_html(context, query)
                context.web.eval(
                    "OnigiriEngine.updateDeckTree({});".format(json.dumps(new_html))
                )
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error searching decks: {e}")
            return (True, None)

    if cmd.startswith("onigiri_collapse:"):
        try:
            deck_id = cmd.split(":", 1)[1]
            if isinstance(context, DeckBrowser):
                deck_tree_updater.on_deck_collapse(context, deck_id)
                return (True, None)
        except Exception as e:
            print(f"Onigiri: Error handling deck collapse: {e}")
        return (True, None)

    if cmd.startswith("onigiri_toggle_favorite:"):
        try:
            deck_id = cmd.split(":", 1)[1] # Keep as string for consistency
            
            # Validate that the deck exists before toggling
            try:
                deck = mw.col.decks.get(DeckId(int(deck_id)))
            except Exception:
                deck = mw.col.decks.get(deck_id)
            if not deck:
                tooltip(tr("err_favorite_deck_missing"))
                return (True, None)
            
            favorites = mw.col.conf.get("onigiri_favorite_decks", [])
            
            if deck_id in favorites:
                favorites.remove(deck_id)
            else:
                if len(favorites) >= 10:
                    tooltip(tr("err_favorites_limit"))
                    return (True, None) # Stop execution, don't refresh
                favorites.append(deck_id)
            
            # Save the change to Anki's configuration
            mw.col.conf["onigiri_favorite_decks"] = favorites
            mw.col.setMod() # This line is CRITICAL
            
            # Force a full refresh of the deck browser
            if isinstance(context, DeckBrowser):
                deck_tree_updater.refresh_deck_tree_state(context)
            
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error handling favorite toggle: {e}")
            import traceback
            traceback.print_exc()
            return (True, None) # Still handle the command

    if cmd.startswith("onigiri_sort:"):
        try:
            sort_mode = cmd.split(":", 1)[1] or "default"
            valid_modes = {
                "default", "alphabetical_az", "alphabetical_za",
                "most_due", "most_new", "most_reviews", "favorites_first", "custom",
            }
            if sort_mode not in valid_modes:
                sort_mode = "default"
            mw.col.conf["onigiri_sort_mode"] = sort_mode
            mw.col.conf["onigiri_deck_sort"] = sort_mode
            mw.col.setMod()
            _refresh_deck_browser(context)
            labels = {
                "default": tr("sort_default_order"),
                "alphabetical_az": tr("sort_a_to_z"),
                "alphabetical_za": tr("sort_z_to_a"),
                "most_due": tr("sort_most_due"),
                "most_new": tr("sort_most_new"),
                "most_reviews": tr("sort_most_reviews"),
                "favorites_first": tr("sort_favorites_first"),
                "custom": tr("sort_custom_order"),
            }
            tooltip(tr("deck_sort_toast").format(labels.get(sort_mode, sort_mode)))
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error handling sort command: {e}")
            return (True, None)

    if cmd.startswith("onigiri_ctx_rename:"):
        try:
            deck_id = cmd.split(":", 1)[1]
            if isinstance(context, DeckBrowser):
                _open_rename_modal(context, deck_id)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error renaming deck: {e}")
            tooltip(tr("err_rename_deck").format(e))
            return (True, None)

    if cmd.startswith("onigiri_rename_deck:"):
        try:
            rest = cmd.split(":", 1)[1]
            if ":" in rest and not rest.lstrip().startswith("%7B") and not rest.lstrip().startswith("{"):
                deck_id, payload = rest.split(":", 1)
                data = json.loads(unquote(payload))
            else:
                data = json.loads(unquote(rest))
                deck_id = str(data.get("deckId") or "")

            new_value = (data.get("name") or "").strip()
            if not deck_id or not new_value:
                tooltip(tr("deck_name_empty"))
                return (True, None)
            full_name = _deck_name(deck_id)
            parent_prefix = full_name.rsplit("::", 1)[0] if "::" in full_name else ""
            if data.get("fullPath"):
                new_name = new_value
            else:
                new_name = new_value if "::" in new_value or not parent_prefix else f"{parent_prefix}::{new_value}"
            _rename_deck(deck_id, new_name)
            _refresh_deck_browser(context)
            if isinstance(context, DeckBrowser):
                context.web.eval("if(window.OnigiriRenameDialog)OnigiriRenameDialog.close();")
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error saving renamed deck: {e}")
            tooltip(tr("err_rename_deck").format(e))
            if isinstance(context, DeckBrowser):
                context.web.eval(
                    "if(window.OnigiriRenameDialog)OnigiriRenameDialog.showError(%s);"
                    % json.dumps(f"Rename failed: {e}")
                )
            return (True, None)

    if cmd.startswith("onigiri_ctx_subdeck:"):
        try:
            deck_id = cmd.split(":", 1)[1]
            payload = {"deckId": str(deck_id), "parentName": _deck_name(deck_id)}
            if isinstance(context, DeckBrowser):
                context.web.eval(
                    "if(window.OnigiriAddSubdeckDialog)OnigiriAddSubdeckDialog.open(%s);"
                    % json.dumps(payload, ensure_ascii=True)
                )
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error adding subdeck: {e}")
            tooltip(tr("err_add_subdeck").format(e))
            return (True, None)

    if cmd.startswith("onigiri_create_subdeck:"):
        try:
            payload = json.loads(unquote(cmd.split(":", 1)[1]))
            deck_id = str(payload.get("deckId") or "")
            child_name = str(payload.get("name") or "").strip()
            if not deck_id or not child_name:
                raise ValueError("Enter a subdeck name.")
            parent_name = _deck_name(deck_id)
            if not parent_name:
                raise ValueError("Parent deck no longer exists.")
            full_name = child_name if "::" in child_name else f"{parent_name}::{child_name}"
            new_did = mw.col.decks.id(full_name)
            mw.col.decks.select(new_did)
            mw.col.setMod()
            _refresh_deck_browser(context)
            if isinstance(context, DeckBrowser):
                context.web.eval("if(window.OnigiriAddSubdeckDialog)OnigiriAddSubdeckDialog.close();")
            tooltip(tr("deck_created_toast").format(full_name))
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error creating subdeck: {e}")
            tooltip(tr("err_add_subdeck").format(e))
            if isinstance(context, DeckBrowser):
                context.web.eval(
                    "if(window.OnigiriAddSubdeckDialog)OnigiriAddSubdeckDialog.showError(%s);"
                    % json.dumps(f"Create subdeck failed: {e}")
                )
            return (True, None)

    if cmd.startswith("onigiri_create_deck_submit:"):
        try:
            payload = json.loads(unquote(cmd.split(":", 1)[1]))
            name = str(payload.get("name") or "").strip()
            if not name:
                raise ValueError("Enter a deck name.")
            parent_did = payload.get("parentDid")
            if not parent_did or parent_did == "__root__":
                full_name = name
            else:
                parent_name = _deck_name(str(parent_did))
                if not parent_name:
                    raise ValueError("Parent deck no longer exists.")
                full_name = name if "::" in name else f"{parent_name}::{name}"
            new_did = mw.col.decks.id(full_name)
            mw.col.decks.select(new_did)
            mw.col.setMod()
            _refresh_deck_browser(context)
            if isinstance(context, DeckBrowser):
                context.web.eval("if(window.OnigiriCreateDeckDialog)OnigiriCreateDeckDialog.close();")
            tooltip(tr("deck_created_toast").format(full_name))
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error creating deck: {e}")
            tooltip(tr("err_create_deck").format(e))
            if isinstance(context, DeckBrowser):
                context.web.eval(
                    "if(window.OnigiriCreateDeckDialog)OnigiriCreateDeckDialog.showError(%s);"
                    % json.dumps(f"Create deck failed: {e}")
                )
            return (True, None)

    if cmd.startswith("onigiri_ctx_options:"):
        try:
            deck_id = int(cmd.split(":", 1)[1])
            try:
                from aqt.deckoptions import display_options_for_deck_id
                display_options_for_deck_id(DeckId(deck_id))
            except Exception:
                if hasattr(mw.deckBrowser, "_show_options_for_deck_id"):
                    mw.deckBrowser._show_options_for_deck_id(deck_id)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error opening deck options: {e}")
            return (True, None)

    if cmd.startswith("onigiri_ctx_export:"):
        try:
            deck_id = int(cmd.split(":", 1)[1])
            try:
                from aqt.exporting import ExportDialog
                ExportDialog(mw, did=DeckId(deck_id))
            except Exception:
                if hasattr(mw, "onExport"):
                    mw.onExport(did=DeckId(deck_id))
                else:
                    tooltip(tr("err_export_unavailable"))
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error exporting deck: {e}")
            tooltip(tr("err_export_deck").format(e))
            return (True, None)

    if cmd.startswith("onigiri_ctx_copy_id:"):
        deck_id = cmd.split(":", 1)[1]
        QApplication.clipboard().setText(deck_id)
        tooltip(tr("deck_id_copied"))
        return (True, None)

    if cmd.startswith("onigiri_ctx_delete:"):
        try:
            deck_id = int(cmd.split(":", 1)[1])
            if _open_delete_deck_dialog(context, [deck_id]):
                return (True, None)
            # Fallback for contexts without the Onigiri dialog (non deck browser).
            deck_name = _deck_name(str(deck_id))
            if not askUser(tr("del_deck_message").format(f"'{deck_name}'")):
                return (True, None)
            _delete_decks_with_undo(context, [deck_id])
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error deleting deck: {e}")
            tooltip(tr("err_delete_deck").format(e))
            return (True, None)

    if cmd.startswith("onigiri_delete_deck_confirmed:"):
        try:
            payload = json.loads(unquote(cmd.split(":", 1)[1]))
            deck_ids = [int(did) for did in payload.get("deckIds", [])]
            if deck_ids:
                _delete_decks_with_undo(context, deck_ids)
        except Exception as e:
            print(f"Onigiri: Error deleting deck: {e}")
            tooltip(tr("err_delete_deck").format(e))
        return (True, None)

    if cmd == "onigiri_undo_delete_deck":
        try:
            _undo_deck_delete(context)
        except Exception as e:
            print(f"Onigiri: Error restoring deck: {e}")
            tooltip(tr("err_restore_deck").format(e))
        return (True, None)

    if cmd.startswith("onigiri_ctx_mark:"):
        try:
            _, deck_id, mark_key = cmd.split(":", 2)
            valid_marks = {"red", "blue", "green", "yellow"}
            marks = mw.col.conf.get("onigiri_deck_marks", {})
            if mark_key in valid_marks:
                marks[str(deck_id)] = mark_key
            else:
                marks.pop(str(deck_id), None)
            mw.col.conf["onigiri_deck_marks"] = marks
            mw.col.setMod()
            _refresh_deck_browser(context)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error marking deck: {e}")
            tooltip(tr("err_mark_deck").format(e))
            return (True, None)

    if cmd.startswith("onigiri_drag_drop:"):
        try:
            payload = json.loads(cmd.split(":", 1)[1])
            changed = deck_drag_drop.apply_drag_drop(payload)
            if changed:
                _refresh_deck_browser(context)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error moving deck: {e}")
            import traceback
            traceback.print_exc()
            tooltip(tr("err_move_deck").format(e))
            return (True, None)

    if cmd.startswith("onigiri_ctx_move_to:"):
        try:
            raw = unquote(cmd.split(":", 1)[1])
            try:
                source_dids = json.loads(raw)
            except Exception:
                source_dids = raw
            payload = move_deck.build_move_to_payload(source_dids)
            if isinstance(context, DeckBrowser):
                context.web.eval(
                    "if(window.OnigiriMoveToDialog)OnigiriMoveToDialog.open(%s);"
                    % json.dumps(payload, ensure_ascii=True)
                )
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error opening Move To dialog: {e}")
            tooltip(tr("err_open_move_to").format(e))
            if isinstance(context, DeckBrowser):
                context.web.eval("if(window.OnigiriEngine)OnigiriEngine.clearDialogFocus();")
            return (True, None)

    if cmd.startswith("onigiri_move_deck:"):
        try:
            payload = unquote(cmd.split(":", 1)[1])
            changed, message = move_deck.move_deck_from_payload(payload)
            if changed:
                _refresh_deck_browser(context)
                if isinstance(context, DeckBrowser):
                    context.web.eval("if(window.OnigiriMoveToDialog)OnigiriMoveToDialog.close();")
            if message:
                tooltip(message)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error moving deck: {e}")
            tooltip(tr("err_move_deck").format(e))
            if isinstance(context, DeckBrowser):
                context.web.eval(
                    "if(window.OnigiriMoveToDialog)OnigiriMoveToDialog.showError(%s);"
                    % json.dumps(f"Move failed: {e}")
                )
            return (True, None)

    if cmd.startswith("onigiri_ctx_change_icon:"):
        try:
            deck_id = cmd.split(":", 1)[1]
            _open_icon_modal(context, deck_id)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error opening icon chooser: {e}")
            tooltip(tr("err_open_icon_chooser").format(e))
            return (True, None)

    if cmd.startswith("onigiri_icon_chooser_save:"):
        try:
            _, deck_id, payload = cmd.split(":", 2)
            data = json.loads(payload)
            icon_name = data.get("icon", "")
            custom_icons = mw.col.conf.get("onigiri_custom_deck_icons", {})
            if icon_name:
                light_color = data.get("color", "")
                dark_color = data.get("colorDark", light_color)
                entry = {"icon": icon_name, "color": light_color}
                # Only write colorDark when it actually diverges from the
                # light value — a linked pair should keep reading as one
                # colour for decks that never touched the dark slot.
                if dark_color != light_color:
                    entry["colorDark"] = dark_color
                custom_icons[str(deck_id)] = entry
            else:
                custom_icons.pop(str(deck_id), None)
            mw.col.conf["onigiri_custom_deck_icons"] = custom_icons
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                context.show()
            else:
                _refresh_deck_browser(context)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error saving deck icon: {e}")
            tooltip(tr("err_save_icon").format(e))
            return (True, None)

    if cmd.startswith("onigiri_icon_chooser_color:"):
        try:
            _, deck_id, role, current = cmd.split(":", 3)
            chosen, ok = _run_deck_icon_color_picker(context, current or "#00A982")
            if ok and chosen:
                context.web.eval(
                    "if(window.OnigiriIconChooser)OnigiriIconChooser.applyColor(%s, %s);"
                    % (json.dumps(role), json.dumps(chosen))
                )
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error picking icon color: {e}")
            tooltip(tr("err_open_color_picker").format(e))
            return (True, None)

    if cmd.startswith("onigiri_icon_chooser_reset:"):
        try:
            deck_id = cmd.split(":", 1)[1]
            custom_icons = mw.col.conf.get("onigiri_custom_deck_icons", {})
            custom_icons.pop(str(deck_id), None)
            mw.col.conf["onigiri_custom_deck_icons"] = custom_icons
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                context.show()
            else:
                _refresh_deck_browser(context)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error resetting deck icon: {e}")
            tooltip(tr("err_reset_icon").format(e))
            return (True, None)

    if cmd.startswith("onigiri_icon_chooser_add_icon:"):
        try:
            deck_id = cmd.split(":", 1)[1]
            _add_icon_files(context, deck_id, "icon")
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error adding icon: {e}")
            tooltip(tr("err_add_icon").format(e))
            return (True, None)

    if cmd.startswith("onigiri_icon_chooser_add_image:"):
        try:
            deck_id = cmd.split(":", 1)[1]
            _add_icon_files(context, deck_id, "image")
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error adding image: {e}")
            tooltip(tr("err_add_image").format(e))
            return (True, None)

    if cmd.startswith("onigiri_icon_chooser_delete_icon:"):
        try:
            _, deck_id, filename = cmd.split(":", 2)
            _delete_icon_file(context, deck_id, filename)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error deleting icon: {e}")
            tooltip(tr("err_delete_icon").format(e))
            return (True, None)
        
    if cmd.startswith("onigiri_show_transfer_window:"):
        try:
            from .gamification import mod_transfer_window

            json_payload = cmd.split(":", 1)[1]
            mod_transfer_window.show_transfer_window(json_payload)
            return (True, None)
        except Exception as e:
            return (True, None)

    if cmd.startswith("onigiri_move_decks:"):
        try:
            json_payload = cmd.split(":", 1)[1]
            deck_tree_updater.on_decks_move(json_payload)
            return (True, None)
        except Exception as e:
            return (True, None)

    if cmd == "onigiri_ui_open":
        return (True, None)

    if cmd == "onigiri_ui_close":
        if isinstance(context, DeckBrowser):
            context.web.eval("if(window.OnigiriEngine)OnigiriEngine.clearDialogFocus();")
        return (True, None)

    if cmd.startswith("onigiri_ctx_bulk_delete:"):
        try:
            payload = json.loads(unquote(cmd.split(":", 1)[1]))
            deck_ids = [int(did) for did in payload.get("dids", [])]
            if not deck_ids:
                return (True, None)
            if _open_delete_deck_dialog(context, deck_ids):
                return (True, None)
            if not askUser(tr("del_deck_message_plural").format(len(deck_ids))):
                return (True, None)
            _delete_decks_with_undo(context, deck_ids)
        except Exception as e:
            print(f"Onigiri: Error bulk deleting decks: {e}")
            tooltip(tr("err_bulk_delete").format(e))
        return (True, None)

    if cmd.startswith("onigiri_ctx_bulk_favorite:"):
        try:
            payload = json.loads(unquote(cmd.split(":", 1)[1]))
            dids = [str(did) for did in payload.get("dids", [])]
            favorites = _conf_list("onigiri_favorite_decks")
            for did in dids:
                if did not in favorites and len(favorites) < 10:
                    favorites.append(did)
            mw.col.conf["onigiri_favorite_decks"] = favorites
            mw.col.setMod()
            _refresh_deck_browser(context)
        except Exception as e:
            print(f"Onigiri: Error bulk favoriting decks: {e}")
            tooltip(tr("err_bulk_favorite").format(e))
        return (True, None)

    if cmd.startswith("onigiri_ctx_bulk_unfavorite:"):
        try:
            payload = json.loads(unquote(cmd.split(":", 1)[1]))
            dids = {str(did) for did in payload.get("dids", [])}
            mw.col.conf["onigiri_favorite_decks"] = [
                did for did in _conf_list("onigiri_favorite_decks") if did not in dids
            ]
            mw.col.setMod()
            _refresh_deck_browser(context)
        except Exception as e:
            print(f"Onigiri: Error bulk unfavoriting decks: {e}")
            tooltip(tr("err_bulk_unfavorite").format(e))
        return (True, None)

    if cmd.startswith("onigiri_ctx_bulk_mark:"):
        try:
            payload = json.loads(unquote(cmd.split(":", 1)[1]))
            dids = [str(did) for did in payload.get("dids", [])]
            mark_key = str(payload.get("mark", "none"))
            valid_marks = {"red", "blue", "green", "yellow"}
            marks = mw.col.conf.get("onigiri_deck_marks", {})
            for did in dids:
                if mark_key in valid_marks:
                    marks[did] = mark_key
                else:
                    marks.pop(did, None)
            mw.col.conf["onigiri_deck_marks"] = marks
            mw.col.setMod()
            _refresh_deck_browser(context)
        except Exception as e:
            print(f"Onigiri: Error bulk marking decks: {e}")
            tooltip(tr("err_bulk_mark").format(e))
        return (True, None)

    if cmd.startswith("onigiri_learner_stats_select_deck:"):
        try:
            raw_payload = cmd.split(":", 1)[1]
            try:
                data = json.loads(unquote(raw_payload))
                widget_id = str(data.get("widgetId") or "")
                deck_id = str(data.get("deckId") or "all")
            except Exception:
                _prefix, widget_id, deck_id = cmd.split(":", 2)

            saved_decks = mw.col.conf.get("onigiri_learner_stats_decks", {})
            if not isinstance(saved_decks, dict):
                saved_decks = {}
            saved_decks[widget_id] = deck_id

            mw.col.conf["onigiri_learner_stats_decks"] = saved_decks
            mw.col.setMod()

            try:
                from . import learner_stats_widget
                updated_html = learner_stats_widget._render_widget(context, widget_id)
                context.web.eval(
                    "if(window.OnigiriLearnerStatsDialog&&typeof OnigiriLearnerStatsDialog.finish==='function')"
                    f"{{OnigiriLearnerStatsDialog.finish({json.dumps(widget_id)}, {json.dumps(updated_html)});}}"
                    "else{pycmd('onigiri_learner_stats_refresh_fallback');}"
                )
            except Exception as render_error:
                print(f"Onigiri: Error updating learner stats widget in place: {render_error}")
                _refresh_deck_browser(context)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error saving learner stats deck: {e}")
            return (True, None)

    if cmd.startswith("onigiri_learner_stats_select_view:"):
        try:
            raw_payload = cmd.split(":", 1)[1]
            data = json.loads(unquote(raw_payload))
            widget_id = str(data.get("widgetId") or "")
            view = str(data.get("view") or "grouped")
            if view not in ("grouped", "bars", "donut"):
                view = "grouped"

            saved_views = mw.col.conf.get("onigiri_learner_stats_view", {})
            if not isinstance(saved_views, dict):
                saved_views = {}
            saved_views[widget_id] = view

            mw.col.conf["onigiri_learner_stats_view"] = saved_views
            mw.col.setMod()
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error saving learner stats view: {e}")
            return (True, None)

    if cmd == "onigiri_learner_stats_refresh_fallback":
        try:
            _refresh_deck_browser(context)
        except Exception as e:
            print(f"Onigiri: Error refreshing learner stats fallback: {e}")
        return (True, None)

    return handled
