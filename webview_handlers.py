import json
import os
import shutil
from urllib.parse import unquote
from typing import Tuple, Any
from aqt.deckbrowser import DeckBrowser
from . import deck_tree_updater
from . import create_deck_dialog
from aqt import mw
from aqt.qt import QApplication, QFileDialog, QInputDialog
from aqt.utils import askUser, tooltip
from anki.decks import DeckId


_ICON_PRIORITY = [
    "deck.svg", "folder.svg", "star_filled.svg", "filtered-deck.svg",
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


def _icon_label(filename: str) -> str:
    stem = os.path.splitext(filename)[0]
    return stem.replace("_", " ").replace("-", " ").title()


def _icon_payload(deck_id: str) -> dict:
    addon_package = _addon_package()
    addon_path = _addon_path()
    system_dir = os.path.join(addon_path, "system_files", "system_icons")
    custom_dir = _custom_icon_dir()

    icons = []
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
                "url": f"/_addons/{addon_package}/system_files/system_icons/{name}",
                "system": True,
            })

    if os.path.isdir(custom_dir):
        for name in sorted(os.listdir(custom_dir), key=str.lower):
            lower = name.lower()
            if lower.endswith(".svg"):
                icons.append({
                    "name": name,
                    "label": _icon_label(name),
                    "url": f"/_addons/{addon_package}/user_files/custom_deck_icons/{name}",
                    "system": False,
                })

    images = []
    if os.path.isdir(custom_dir):
        for name in sorted(os.listdir(custom_dir), key=str.lower):
            if name.lower().endswith(".png"):
                images.append({
                    "name": name,
                    "label": _icon_label(name),
                    "url": f"/_addons/{addon_package}/user_files/custom_deck_icons/{name}",
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
        f"if(window.OnigiriRenameDeckModal){{OnigiriRenameDeckModal.open({payload});}}"
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

def handle_webview_cmd(handled: Tuple[bool, Any], cmd: str, context) -> Tuple[bool, Any]:
    """
    Centralized handler for webview commands from the deck browser.
    """
    if cmd.startswith("onigimon_feed:"):
        try:
            from .gamification import onigimon
            item_key = cmd.split(":", 1)[1]
            message = onigimon.manager.use_item(item_key)
            if message:
                tooltip(message)
            else:
                tooltip("No Onigimon item available.")
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error feeding Onigimon: {e}")
            return (True, None)

    if cmd == "onigimon_play":
        try:
            from .gamification import onigimon
            message = onigimon.manager.play()
            if message:
                tooltip(message)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error playing with Onigimon: {e}")
            return (True, None)

    if cmd == "onigimon_daily_gift":
        try:
            from .gamification import onigimon
            message = onigimon.manager.claim_daily_gift()
            tooltip(message or "Today's Onigimon gift is already claimed.")
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
                tooltip(f"Renamed to {name}.")
            else:
                tooltip("Choose an Onigimon companion first.")
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error renaming Onigimon: {e}")
            return (True, None)

    if cmd == "onigiri_create_deck":
        try:
             # tooltip("Debug: Opening Create Deck Dialog...")
             if not hasattr(create_deck_dialog, 'CreateDeckDialog'):
                 tooltip("Error: CreateDeckDialog class not found in module.")
                 return (True, None)

             dialog = create_deck_dialog.CreateDeckDialog(mw)
             dialog.exec()
             return (True, None) # Handled
        except Exception as e:
             import traceback
             error_msg = f"Onigiri Error: {str(e)}\n{traceback.format_exc()}"
             print(error_msg)
             tooltip(f"Error showing create deck dialog: {e}")
             return (True, None)

    if cmd == "onigiri_toggle_sidebar":
        if isinstance(context, DeckBrowser):
            context.web.eval(
                "var s=document.querySelector('.sidebar-left');"
                "if(s){"
                "  if(s.classList.contains('sidebar-collapsed')){"
                "    if(typeof onigiriExpandSidebar==='function')onigiriExpandSidebar();"
                "    else{s.classList.remove('sidebar-collapsed');pycmd('saveSidebarState:false');}"
                "  }else{"
                "    if(typeof onigiriCollapseSidebar==='function')onigiriCollapseSidebar();"
                "    else{s.classList.add('sidebar-collapsed');pycmd('saveSidebarState:true');}"
                "  }"
                "}"
            )
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
            _, deck_id, payload = cmd.split(":", 2)
            data = json.loads(unquote(payload))
            new_leaf = (data.get("name") or "").strip()
            if not new_leaf:
                tooltip("Deck name cannot be empty.")
                return (True, None)
            full_name = _deck_name(deck_id)
            parent_prefix = full_name.rsplit("::", 1)[0] if "::" in full_name else ""
            new_name = new_leaf if "::" in new_leaf or not parent_prefix else f"{parent_prefix}::{new_leaf}"
            _rename_deck(deck_id, new_name)
            _refresh_deck_browser(context)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error saving renamed deck: {e}")
            tooltip(f"Could not rename deck: {e}")
            return (True, None)

    if cmd.startswith("onigiri_ctx_subdeck:"):
        try:
            deck_id = cmd.split(":", 1)[1]
            parent_name = _deck_name(deck_id)
            child_name, ok = QInputDialog.getText(mw, "Add Subdeck", "Name:")
            if ok:
                child_name = child_name.strip()
                if child_name:
                    full_name = child_name if "::" in child_name else f"{parent_name}::{child_name}"
                    mw.col.decks.id(full_name)
                    mw.col.setMod()
                    _refresh_deck_browser(context)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error adding subdeck: {e}")
            tooltip(f"Could not add subdeck: {e}")
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
            source_did = DeckId(int(payload["source_did"]))
            target_did = DeckId(int(payload["target_did"]))
            drop_type = payload.get("type", "nest")

            if drop_type == "nest":
                mw.col.decks.reparent([source_did], target_did)
            else:
                source_deck = mw.col.decks.get(source_did)
                target_deck = mw.col.decks.get(target_did)
                if source_deck and target_deck:
                    source_name = source_deck["name"]
                    target_name = target_deck["name"]
                    source_parent = "::".join(source_name.split("::")[:-1])
                    target_parent = "::".join(target_name.split("::")[:-1])
                    if source_parent != target_parent:
                        leaf = source_name.split("::")[-1]
                        new_name = f"{target_parent}::{leaf}" if target_parent else leaf
                        existing = mw.col.decks.by_name(new_name)
                        if existing is None or int(existing["id"]) == int(source_did):
                            mw.col.decks.rename(source_deck, new_name)

                new_order = [str(did) for did in payload.get("new_order", [])]
                if new_order:
                    mw.col.conf["onigiri_sort_mode"] = "custom"
                    mw.col.conf["onigiri_deck_sort"] = "custom"
                    mw.col.conf["onigiri_custom_deck_order"] = new_order
            mw.col.setMod()
            _refresh_deck_browser(context)
            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error moving deck: {e}")
            import traceback
            traceback.print_exc()
            tooltip(f"Could not move deck: {e}")
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
            from . import mod_transfer_window
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

    return handled
