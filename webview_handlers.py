import json
import os
import shutil
from urllib.parse import unquote
from typing import Tuple, Any, List
from aqt.deckbrowser import DeckBrowser
from .decks import tree_updater as deck_tree_updater
from .decks import drag_drop as deck_drag_drop
from .decks import move as move_deck
from .onigiri_notifications import notify as tooltip
from aqt import mw
from aqt.qt import QApplication, QFileDialog, QInputDialog
from aqt.utils import askUser
from anki.decks import DeckId
from . import config


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
    return {
        "deckId": str(deck_id),
        "current": {
            "icon": current.get("icon", ""),
            "color": current.get("color", "#888888"),
        },
        "emojiBaseUrl": f"/_addons/{addon_package}/system_files/emojis",
        "icons": icons,
        "images": images,
    }


def _open_icon_modal(context, deck_id: str) -> None:
    payload = json.dumps(_icon_payload(deck_id))
    context.web.eval(f"if(window.OnigiriIconChooser){{OnigiriIconChooser.open({payload});}}")


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
            tooltip(f"Could not import icon: {e}")

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
        tooltip(f"Could not delete icon: {e}")


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
        "name": "Top level",
        "path": "Top level",
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
    # Ignore commands originating from OnigimonCareDialog to avoid double execution/tooltips
    if type(context).__name__ == "OnigimonCareDialog":
        return handled
    parent = getattr(context, "parent", None)
    if parent and callable(parent) and type(parent()).__name__ == "OnigimonCareDialog":
        return handled

    if cmd == "openGamificationSettings":
        try:
            from . import gamification_settings
            gamification_settings.open_gamification_settings()
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error opening gamification settings: {e}")
            return (True, None)

    if cmd == "openOnigimonSettings":
        try:
            from . import gamification_settings
            gamification_settings.open_gamification_settings("Onigimon")
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error opening Onigimon settings: {e}")
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
                tooltip("No Onigimon item available.", context=context, title="", variant="onigimon", hide_icon=True, hide_title=True, centered=True)
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
                tooltip("Choose a name first.")
                return (True, None)
            if onigimon.manager.rename_active_companion(name):
                tooltip(f"Renamed to {name}.", context=context, title="", variant="onigimon", hide_icon=True, hide_title=True, centered=True)
            else:
                tooltip("Choose an Onigimon companion first.", context=context, title="", variant="onigimon", hide_icon=True, hide_title=True, centered=True)
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
            tooltip(f"Error showing create deck dialog: {e}")
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
            tooltip(f"Filter failed: {e}")
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
            tooltip(f"Filter failed: {e}")
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
                tooltip("Cannot favorite: Deck no longer exists.")
                return (True, None)
            
            favorites = mw.col.conf.get("onigiri_favorite_decks", [])
            
            if deck_id in favorites:
                favorites.remove(deck_id)
            else:
                if len(favorites) >= 10:
                    tooltip("You can only have up to 10 favorite decks.")
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
                "default": "Default order",
                "alphabetical_az": "A to Z",
                "alphabetical_za": "Z to A",
                "most_due": "Most due",
                "most_new": "Most new",
                "most_reviews": "Most reviews",
                "favorites_first": "Favorites first",
                "custom": "Custom order",
            }
            tooltip(f"Deck sort: {labels.get(sort_mode, sort_mode)}")
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
            tooltip(f"Could not rename deck: {e}")
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
                tooltip("Deck name cannot be empty.")
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
            tooltip(f"Could not rename deck: {e}")
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
            tooltip(f"Could not add subdeck: {e}")
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
            tooltip(f"Created deck: {full_name}")
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error creating subdeck: {e}")
            tooltip(f"Could not add subdeck: {e}")
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
            tooltip(f"Created deck: {full_name}")
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error creating deck: {e}")
            tooltip(f"Could not create deck: {e}")
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
                    tooltip("Deck export is not available in this Anki version.")
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error exporting deck: {e}")
            tooltip(f"Could not export deck: {e}")
            return (True, None)

    if cmd.startswith("onigiri_ctx_copy_id:"):
        deck_id = cmd.split(":", 1)[1]
        QApplication.clipboard().setText(deck_id)
        tooltip("Deck ID copied.")
        return (True, None)

    if cmd.startswith("onigiri_ctx_delete:"):
        try:
            deck_id = int(cmd.split(":", 1)[1])
            deck_name = _deck_name(str(deck_id))
            if not askUser(f"Delete '{deck_name}' and all of its cards? This cannot be undone."):
                return (True, None)
            try:
                mw.col.decks.remove([DeckId(deck_id)])
            except Exception:
                mw.col.decks.rem(deck_id, cardsToo=True)
            mw.col.setMod()
            _refresh_deck_browser(context)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error deleting deck: {e}")
            tooltip(f"Could not delete deck: {e}")
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
            tooltip(f"Could not mark deck: {e}")
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
            tooltip(f"Could not move deck: {e}")
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
            tooltip(f"Could not open Move To: {e}")
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
            tooltip(f"Could not move deck: {e}")
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
            tooltip(f"Could not open icon chooser: {e}")
            return (True, None)

    if cmd.startswith("onigiri_icon_chooser_save:"):
        try:
            _, deck_id, payload = cmd.split(":", 2)
            data = json.loads(payload)
            icon_name = data.get("icon", "")
            custom_icons = mw.col.conf.get("onigiri_custom_deck_icons", {})
            if icon_name:
                custom_icons[str(deck_id)] = {
                    "icon": icon_name,
                    "color": data.get("color", "#888888"),
                }
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
            tooltip(f"Could not save icon: {e}")
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
            tooltip(f"Could not reset icon: {e}")
            return (True, None)

    if cmd.startswith("onigiri_icon_chooser_add_icon:"):
        try:
            deck_id = cmd.split(":", 1)[1]
            _add_icon_files(context, deck_id, "icon")
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error adding icon: {e}")
            tooltip(f"Could not add icon: {e}")
            return (True, None)

    if cmd.startswith("onigiri_icon_chooser_add_image:"):
        try:
            deck_id = cmd.split(":", 1)[1]
            _add_icon_files(context, deck_id, "image")
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error adding image: {e}")
            tooltip(f"Could not add image: {e}")
            return (True, None)

    if cmd.startswith("onigiri_icon_chooser_delete_icon:"):
        try:
            _, deck_id, filename = cmd.split(":", 2)
            _delete_icon_file(context, deck_id, filename)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error deleting icon: {e}")
            tooltip(f"Could not delete icon: {e}")
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
            dids = [str(did) for did in payload.get("dids", [])]
            if not dids:
                return (True, None)
            if not askUser(f"Delete {len(dids)} decks and all of their cards? This cannot be undone."):
                return (True, None)
            mw.col.decks.remove([DeckId(int(did)) for did in dids])
            mw.col.setMod()
            _refresh_deck_browser(context)
        except Exception as e:
            print(f"Onigiri: Error bulk deleting decks: {e}")
            tooltip(f"Bulk delete failed: {e}")
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
            tooltip(f"Bulk favorite failed: {e}")
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
            tooltip(f"Bulk unfavorite failed: {e}")
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
            tooltip(f"Bulk mark failed: {e}")
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

    if cmd == "onigiri_learner_stats_refresh_fallback":
        try:
            _refresh_deck_browser(context)
        except Exception as e:
            print(f"Onigiri: Error refreshing learner stats fallback: {e}")
        return (True, None)

    return handled
