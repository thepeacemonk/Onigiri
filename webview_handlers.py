import os
import json
import shutil
from typing import Tuple, Any, List
from urllib.parse import unquote
from aqt.deckbrowser import DeckBrowser
from . import deck_tree_updater
from . import deck_drag_drop
from . import create_deck_dialog
from . import move_deck
from aqt import mw
from aqt.qt import QFileDialog
from aqt.utils import tooltip
from . import sort_dialog
from .color_utils import normalize_color_string

def _refresh_dynamic_icon_css(context) -> None:
    """Refresh the generated deck-icon CSS without rebuilding the whole page."""
    if not isinstance(context, DeckBrowser):
        return
    try:
        from . import config, patcher
        addon_package = mw.addonManager.addonFromModule(__package__ or __name__)
        css_html = patcher.generate_icon_css(addon_package, config.get_config())
        context.web.eval(
            """
            (function(html){
                var existing = document.getElementById('modern-menu-icon-styles');
                if (existing) existing.outerHTML = html;
                else document.head.insertAdjacentHTML('beforeend', html);
            })(%s);
            """ % json.dumps(css_html)
        )
    except Exception as e:
        print(f"Onigiri: could not refresh dynamic icon CSS: {e}")


def _refresh_deck_browser_locally(context, *, refresh_icon_css: bool = False) -> None:
    """Refresh the deck tree without triggering Anki's full webview loading UI."""
    if isinstance(context, DeckBrowser):
        if refresh_icon_css:
            _refresh_dynamic_icon_css(context)
        deck_tree_updater.refresh_deck_tree_state(context)


def _sync_organise_menu_state(context, sort_key=None, favorites=None, marked=None, archived=None) -> None:
    """Keep in-memory Organise checkmarks correct after no-reload refreshes."""
    if not isinstance(context, DeckBrowser):
        return
    updates = {
        "sort_key": sort_key,
        "favorites": favorites,
        "marked": marked,
        "archived": archived,
    }
    context.web.eval(
        """
        (function(update){
            var cfg = window.ONIGIRI_CONFIG;
            if (!cfg) return;
            if (!Array.isArray(cfg.organiseActions)) return;
            cfg.organiseActions.forEach(function(child){
                if (!child || !child.key) return;
                if (child.key.indexOf('sort_') === 0 && update.sort_key !== null) {
                    child.selected = child.key === ('sort_' + update.sort_key);
                } else if (child.key === 'filter_favorites' && update.favorites !== null) {
                    child.selected = !!update.favorites;
                } else if (child.key === 'filter_marked' && update.marked !== null) {
                    child.selected = !!update.marked;
                } else if (child.key === 'filter_archived' && update.archived !== null) {
                    child.selected = !!update.archived;
                }
            });
        })(%s);
        """ % json.dumps(updates)
    )


def _conf_list(key: str) -> List[str]:
    return [str(value) for value in mw.col.conf.get(key, [])]




def handle_webview_cmd(handled: Tuple[bool, Any], cmd: str, context) -> Tuple[bool, Any]:
    """
    Centralized handler for webview commands from the deck browser.
    """
    if cmd.startswith("onigimon_feed:"):
        try:
            from .gamification import onigimon
            item_key = cmd.split(":", 1)[1]
            message = onigimon.manager.use_item(item_key)
            tooltip(message or "No Onigimon item available.")
        except Exception as e:
            print(f"Onigiri: Error feeding Onigimon: {e}")
        return (True, None)

    if cmd == "onigimon_play":
        try:
            from .gamification import onigimon
            message = onigimon.manager.play()
            if message:
                tooltip(message)
        except Exception as e:
            print(f"Onigiri: Error playing with Onigimon: {e}")
        return (True, None)

    if cmd == "onigimon_daily_gift":
        try:
            from .gamification import onigimon
            message = onigimon.manager.claim_daily_gift()
            tooltip(message or "Today's Onigimon gift is already claimed.")
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

    if cmd == "onigiri_show_sort_dialog":
        sort_dialog.show_sort_dialog()
        return (True, None)

    if cmd == "onigiri_force_deck_refresh":
        if isinstance(context, DeckBrowser):
            _refresh_deck_browser_locally(context)
        return (True, None)

    if cmd == "onigiri_toggle_sidebar":
        if isinstance(context, DeckBrowser):
            # Use the proper collapse/expand helpers that handle inline width removal
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

    if cmd == "onigiri_toggle_deck_focus":
        if isinstance(context, DeckBrowser):
            current = mw.col.conf.get("onigiri_deck_focus_mode", False)
            new_state = not current
            mw.col.conf["onigiri_deck_focus_mode"] = new_state
            mw.col.setMod()
            js = f"""
            (function(){{
                var s=document.querySelector('.sidebar-left');
                if(s) s.classList.toggle('deck-focus-mode',{str(new_state).lower()});
                var cfg=window.ONIGIRI_CONFIG;
                if(cfg&&Array.isArray(cfg.ellipsisActions)){{
                    cfg.ellipsisActions.forEach(function(action){{
                        if(action&&action.key==='focus') action.selected={str(new_state).lower()};
                    }});
                }}
                if(typeof updateDeckFocusLayout==='function') updateDeckFocusLayout();
            }})();
            """
            context.web.eval(js)
        return (True, None)

    if cmd == "onigiri_toggle_deck_edit":
        if isinstance(context, DeckBrowser):
            context.web.eval("if(typeof OnigiriEditor!=='undefined'){if(OnigiriEditor.EDIT_MODE)OnigiriEditor.exitEditMode();else OnigiriEditor.enterEditMode();}")
        return (True, None)

    if cmd == "onigiri_toggle_transfer":
        if isinstance(context, DeckBrowser):
            context.web.eval("if(typeof OnigiriEditor!=='undefined'&&OnigiriEditor.EDIT_MODE){var cb=document.querySelectorAll('input[type=checkbox]:checked');if(cb.length>0){var ids=[];cb.forEach(function(c){var r=c.closest('[data-did]');if(r)ids.push(r.dataset.did);});if(ids.length)pycmd('onigiri_show_transfer_window:'+JSON.stringify(ids));}else{alert('Enter Edit Mode first, then select decks to transfer.');}}")
        return (True, None)

    if cmd.startswith("onigiri_collapse:"):
        try:
            parts = cmd.split(":", 2)
            deck_id = unquote(parts[1]) if len(parts) > 1 else ""
            search_query = unquote(parts[2]).strip() if len(parts) > 2 else ""
            if isinstance(context, DeckBrowser):
                deck_tree_updater.on_deck_collapse(context, deck_id, search_query)
                return (True, None)
        except Exception as e:
            print(f"Onigiri: Error handling deck collapse: {e}")
        return (True, None)

    if cmd.startswith("onigiri_toggle_favorite:"):
        try:
            deck_id = cmd.split(":", 1)[1] # Keep as string for consistency
            
            # Validate that the deck exists before toggling
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

    if cmd.startswith("onigiri_toggle_archive:"):
        try:
            deck_id = cmd.split(":", 1)[1]
            deck = mw.col.decks.get(deck_id)
            if not deck:
                tooltip("Cannot archive: Deck no longer exists.")
                return (True, None)

            archived = _conf_list(deck_tree_updater.ARCHIVED_DECKS_CONF_KEY)
            if deck_id in archived:
                archived.remove(deck_id)
            else:
                archived.append(deck_id)

            mw.col.conf[deck_tree_updater.ARCHIVED_DECKS_CONF_KEY] = archived
            mw.col.setMod()

            if isinstance(context, DeckBrowser):
                deck_tree_updater.refresh_deck_tree_state(context)

            return (True, None)
        except Exception as e:
            print(f"Onigiri: Error handling archive toggle: {e}")
            import traceback
            traceback.print_exc()
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

    # --- Deck right-click context menu actions ---

    if cmd.startswith("onigiri_ctx_move_to:"):
        try:
            did = unquote(cmd.split(":", 1)[1])
            payload = move_deck.build_move_to_payload(did)
            if isinstance(context, DeckBrowser):
                context.web.eval(
                    "if(window.OnigiriMoveToDialog)OnigiriMoveToDialog.open(%s);"
                    % json.dumps(payload, ensure_ascii=True)
                )
        except Exception as e:
            tooltip(f"Could not open Move Deck dialog: {e}")
            if isinstance(context, DeckBrowser):
                context.web.eval("if(window.OnigiriEngine)OnigiriEngine.clearDialogFocus();")
        return (True, None)

    if cmd.startswith("onigiri_move_deck:"):
        try:
            payload = unquote(cmd.split(":", 1)[1])
            changed, message = move_deck.move_deck_from_payload(payload)
            if changed and isinstance(context, DeckBrowser):
                deck_tree_updater.refresh_deck_tree_state(context)
                context.web.eval(
                    "if(window.OnigiriMoveToDialog)OnigiriMoveToDialog.close();"
                )
                tooltip(message)
            elif isinstance(context, DeckBrowser):
                context.web.eval(
                    "if(window.OnigiriMoveToDialog)OnigiriMoveToDialog.showError(%s);"
                    % json.dumps(message or "Could not move deck.")
                )
            else:
                tooltip(message or "Could not move deck.")
        except Exception as e:
            tooltip(f"Move failed: {e}")
            if isinstance(context, DeckBrowser):
                context.web.eval(
                    "if(window.OnigiriMoveToDialog)OnigiriMoveToDialog.showError(%s);"
                    % json.dumps(f"Move failed: {e}")
                )
        return (True, None)

    if cmd.startswith("onigiri_ctx_rename:"):
        try:
            did = unquote(cmd.split(":", 1)[1])
            deck = mw.col.decks.get(int(did))
            if not deck:
                return (True, None)
            current_name = deck["name"]
            leaf = current_name.split("::")[-1]
            parent_prefix = "::".join(current_name.split("::")[:-1])
            payload = {
                "deckId": str(did),
                "leafName": leaf,
                "fullName": current_name,
                "parentPrefix": parent_prefix,
            }
            if isinstance(context, DeckBrowser):
                context.web.eval(
                    "if(window.OnigiriRenameDialog)OnigiriRenameDialog.open(%s);"
                    % json.dumps(payload, ensure_ascii=True)
                )
        except Exception as e:
            tooltip(f"Could not open Rename Deck dialog: {e}")
            if isinstance(context, DeckBrowser):
                context.web.eval("if(window.OnigiriEngine)OnigiriEngine.clearDialogFocus();")
        return (True, None)

    if cmd.startswith("onigiri_rename_deck:"):
        try:
            payload = json.loads(unquote(cmd.split(":", 1)[1]))
            did = payload.get("deckId")
            deck = mw.col.decks.get(int(did))
            if not deck:
                raise ValueError("Deck no longer exists.")
            new_name = str(payload.get("name") or "").strip()
            if not new_name:
                raise ValueError("Enter a deck name.")

            current_name = deck["name"]
            parent_prefix = "::".join(current_name.split("::")[:-1])
            if payload.get("fullPath"):
                new_full = new_name
            elif "::" in new_name:
                new_full = new_name
            else:
                new_full = (parent_prefix + "::" + new_name) if parent_prefix else new_name

            mw.col.decks.rename(deck, new_full)
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                deck_tree_updater.refresh_deck_tree_state(context)
                context.web.eval(
                    "if(window.OnigiriRenameDialog)OnigiriRenameDialog.close();"
                )
                tooltip("Deck renamed.")
        except Exception as e:
            tooltip(f"Rename failed: {e}")
            if isinstance(context, DeckBrowser):
                context.web.eval(
                    "if(window.OnigiriRenameDialog)OnigiriRenameDialog.showError(%s);"
                    % json.dumps(f"Rename failed: {e}")
                )
        return (True, None)

    if cmd.startswith("onigiri_ctx_subdeck:"):
        try:
            from aqt.qt import QInputDialog
            did = cmd.split(":", 1)[1]
            deck = mw.col.decks.get(int(did))
            if not deck:
                return (True, None)
            parent_name = deck["name"]
            sub_name, ok = QInputDialog.getText(mw, "Add Subdeck", f"Subdeck name under '{parent_name}':")
            if ok and sub_name.strip():
                full_name = parent_name + "::" + sub_name.strip()
                mw.col.decks.id(full_name)
                mw.col.setMod()
                if isinstance(context, DeckBrowser):
                    deck_tree_updater.refresh_deck_tree_state(context)
        except Exception as e:
            tooltip(f"Create subdeck failed: {e}")
        if isinstance(context, DeckBrowser):
            context.web.eval("OnigiriEngine.clearDialogFocus();")
        return (True, None)

    if cmd.startswith("onigiri_ctx_copy_id:"):
        try:
            from aqt.qt import QApplication
            did = cmd.split(":", 1)[1]
            QApplication.clipboard().setText(did)
            tooltip(f"Deck ID {did} copied to clipboard.")
        except Exception as e:
            tooltip(f"Copy failed: {e}")
        return (True, None)

    if cmd.startswith("onigiri_ctx_options:"):
        try:
            did = int(cmd.split(":", 1)[1])
            from anki.decks import DeckId as _DeckId
            _did = _DeckId(did)
            # Modern Anki (2.1.45+): aqt.deckoptions.display_options_for_deck_id
            try:
                from aqt.deckoptions import display_options_for_deck_id
                display_options_for_deck_id(_did)
            except (ImportError, Exception):
                # Older Anki: DeckBrowser has _show_options_for_deck_id
                try:
                    mw.deckBrowser._show_options_for_deck_id(did)
                except (AttributeError, Exception):
                    # Fallback: direct DeckConf dialog
                    deck = mw.col.decks.get(did)
                    if deck:
                        from aqt.deckconf import DeckConf
                        DeckConf(mw, deck)
        except Exception as e:
            tooltip(f"Could not open deck options: {e}")
        return (True, None)

    if cmd.startswith("onigiri_ctx_export:"):
        try:
            from anki.decks import DeckId as _DeckId
            did = int(cmd.split(":", 1)[1])
            try:
                from aqt.exporting import ExportDialog
                ExportDialog(mw, did=_DeckId(did))
            except (ImportError, TypeError):
                try:
                    mw.onExport(did=_DeckId(did))
                except AttributeError:
                    tooltip("Deck export is not available in this Anki version.")
        except Exception as e:
            tooltip(f"Export failed: {e}")
        return (True, None)

    if cmd.startswith("onigiri_drag_drop:"):
        try:
            import json as _json
            payload = _json.loads(cmd.split(":", 1)[1])
            changed = deck_drag_drop.apply_drag_drop(payload)
            if changed and isinstance(context, DeckBrowser):
                deck_tree_updater.refresh_deck_tree_state(context)
        except Exception as e:
            print(f"Onigiri: drag_drop error: {e}")
            import traceback
            traceback.print_exc()
        return (True, None)

    if cmd.startswith("onigiri_ctx_change_icon:"):
        try:
            did = cmd.split(":", 1)[1]
            _open_icon_chooser_modal(context, did)
        except Exception as e:
            tooltip(f"Could not open icon chooser: {e}")
        return (True, None)

    # --- Deck mark (coloured dot) ---
    if cmd.startswith("onigiri_ctx_mark:"):
        try:
            parts = cmd.split(":", 2)
            if len(parts) == 3:
                did = parts[1]
                mark_key = parts[2]  # 'red'|'blue'|'green'|'yellow'|'none'
                marks = mw.col.conf.get("onigiri_deck_marks", {})
                if mark_key == 'none':
                    marks.pop(did, None)
                else:
                    marks[did] = mark_key
                mw.col.conf["onigiri_deck_marks"] = marks
                mw.col.setMod()
                # Sync JS state so next context-menu open reflects new mark
                if isinstance(context, DeckBrowser):
                    context.web.eval(
                        f"window.ONIGIRI_DECK_MARKS = {json.dumps(marks)};"
                    )
                    deck_tree_updater.refresh_deck_tree_state(context)
        except Exception as e:
            tooltip(f"Mark failed: {e}")
        return (True, None)

    # --- In-page icon chooser commands ---
    if cmd.startswith("onigiri_icon_chooser_save:"):
        try:
            rest = cmd.split(":", 1)[1]
            # Format: DECK_ID:JSON_PAYLOAD
            sep = rest.index(":")
            did = rest[:sep]
            data = json.loads(rest[sep+1:])
            icon = data.get("icon", "")
            raw_color = data.get("color", "")
            custom_icons = mw.col.conf.get("onigiri_custom_deck_icons", {})
            if not icon and not raw_color:
                custom_icons.pop(did, None)
            else:
                custom_icons[did] = {
                    "icon": icon,
                    "color": normalize_color_string(raw_color, fallback="#888888") or "#888888",
                }
            mw.col.conf["onigiri_custom_deck_icons"] = custom_icons
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                _refresh_deck_browser_locally(context, refresh_icon_css=True)
        except Exception as e:
            tooltip(f"Icon chooser save failed: {e}")
        return (True, None)

    if cmd.startswith("onigiri_icon_chooser_reset:"):
        try:
            did = cmd.split(":", 1)[1]
            custom_icons = mw.col.conf.get("onigiri_custom_deck_icons", {})
            custom_icons.pop(did, None)
            mw.col.conf["onigiri_custom_deck_icons"] = custom_icons
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                _refresh_deck_browser_locally(context, refresh_icon_css=True)
        except Exception as e:
            tooltip(f"Icon chooser reset failed: {e}")
        return (True, None)

    if cmd.startswith("onigiri_icon_chooser_add_icon:") or cmd.startswith("onigiri_icon_chooser_add_svg:"):
        try:
            did = cmd.split(":", 1)[1]
            _icon_chooser_add_file(context, did, file_type='icon')
        except Exception as e:
            tooltip(f"Icon chooser add failed: {e}")
        return (True, None)

    if cmd.startswith("onigiri_icon_chooser_add_image:") or cmd.startswith("onigiri_icon_chooser_add_png:"):
        try:
            did = cmd.split(":", 1)[1]
            _icon_chooser_add_file(context, did, file_type='image')
        except Exception as e:
            tooltip(f"Icon chooser add image failed: {e}")
        return (True, None)

    if cmd.startswith("onigiri_icon_chooser_delete_icon:"):
        try:
            rest = cmd.split(":", 1)[1]
            sep = rest.index(":")
            did = rest[:sep]
            filename = rest[sep+1:]
            _icon_chooser_delete_file(context, did, filename)
        except Exception as e:
            tooltip(f"Icon chooser delete failed: {e}")
        return (True, None)

    # update_color: sent by the icon chooser color picker — handled fully in JS,
    # just mark as handled so it doesn't fall through to Anki's default handler.
    if cmd.startswith("update_color:"):
        return (True, None)

    if cmd.startswith("onigiri_ctx_delete:"):
        try:
            from aqt.utils import askUser
            did = cmd.split(":", 1)[1]
            deck = mw.col.decks.get(int(did))
            if not deck:
                return (True, None)
            deck_name = deck["name"]
            if not askUser(f"Delete '{deck_name}' and all its cards? This cannot be undone."):
                return (True, None)
            try:
                from anki.decks import DeckId as _DeckId
                mw.col.decks.remove([_DeckId(int(did))])
            except Exception:
                mw.col.decks.rem(int(did), cardsToo=True)
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                deck_tree_updater.refresh_deck_tree_state(context)
        except Exception as e:
            tooltip(f"Delete failed: {e}")
        return (True, None)

    # --- Bulk context menu handlers for multi-selection ---

    if cmd.startswith("onigiri_ctx_bulk_delete:"):
        try:
            from aqt.qt import QMessageBox
            import json as _json
            payload = _json.loads(cmd.split(":", 1)[1])
            dids = payload.get("dids", [])
            if not dids:
                return (True, None)
            count = len(dids)
            reply = QMessageBox.question(
                mw,
                "Delete Decks",
                f"Delete {count} decks and all their cards?\nThis cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                from anki.decks import DeckId as _DeckId
                mw.col.decks.remove([_DeckId(int(d)) for d in dids])
                mw.col.setMod()
                if isinstance(context, DeckBrowser):
                    deck_tree_updater.refresh_deck_tree_state(context)
        except Exception as e:
            tooltip(f"Bulk delete failed: {e}")
        return (True, None)

    if cmd.startswith("onigiri_ctx_bulk_favorite:"):
        try:
            import json as _json
            payload = _json.loads(cmd.split(":", 1)[1])
            dids = payload.get("dids", [])
            if not dids:
                return (True, None)
            favorites = set(mw.col.conf.get("onigiri_favorite_decks", []))
            favorites |= set(str(d) for d in dids)
            mw.col.conf["onigiri_favorite_decks"] = list(favorites)
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                deck_tree_updater.refresh_deck_tree_state(context)
        except Exception as e:
            tooltip(f"Bulk favorite failed: {e}")
        return (True, None)

    if cmd.startswith("onigiri_ctx_bulk_unfavorite:"):
        try:
            import json as _json
            payload = _json.loads(cmd.split(":", 1)[1])
            dids = payload.get("dids", [])
            if not dids:
                return (True, None)
            favorites = set(mw.col.conf.get("onigiri_favorite_decks", []))
            favorites -= set(str(d) for d in dids)
            mw.col.conf["onigiri_favorite_decks"] = list(favorites)
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                deck_tree_updater.refresh_deck_tree_state(context)
        except Exception as e:
            tooltip(f"Bulk unfavorite failed: {e}")
        return (True, None)

    if cmd.startswith("onigiri_ctx_bulk_archive:"):
        try:
            import json as _json
            payload = _json.loads(cmd.split(":", 1)[1])
            dids = payload.get("dids", [])
            if not dids:
                return (True, None)
            archived = set(mw.col.conf.get("onigiri_archived_decks", []))
            archived |= set(str(d) for d in dids)
            mw.col.conf["onigiri_archived_decks"] = list(archived)
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                deck_tree_updater.refresh_deck_tree_state(context)
        except Exception as e:
            tooltip(f"Bulk archive failed: {e}")
        return (True, None)

    if cmd.startswith("onigiri_ctx_bulk_unarchive:"):
        try:
            import json as _json
            payload = _json.loads(cmd.split(":", 1)[1])
            dids = payload.get("dids", [])
            if not dids:
                return (True, None)
            archived = set(mw.col.conf.get("onigiri_archived_decks", []))
            archived -= set(str(d) for d in dids)
            mw.col.conf["onigiri_archived_decks"] = list(archived)
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                deck_tree_updater.refresh_deck_tree_state(context)
        except Exception as e:
            tooltip(f"Bulk unarchive failed: {e}")
        return (True, None)

    if cmd.startswith("onigiri_ctx_bulk_mark:"):
        try:
            import json as _json
            rest = cmd.split(":", 1)[1]
            payload = _json.loads(rest)
            dids = payload.get("dids", [])
            mark_key = payload.get("mark", "none")
            if not dids:
                return (True, None)
            marks = mw.col.conf.get("onigiri_deck_marks", {})
            for did in dids:
                if mark_key == 'none':
                    marks.pop(str(did), None)
                else:
                    marks[str(did)] = mark_key
            mw.col.conf["onigiri_deck_marks"] = marks
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                deck_tree_updater.refresh_deck_tree_state(context)
        except Exception as e:
            tooltip(f"Bulk mark failed: {e}")
        return (True, None)

    if cmd == "onigiri_undo":
        try:
            mw.col.undo()
            if isinstance(context, DeckBrowser):
                deck_tree_updater.refresh_deck_tree_state(context)
        except Exception as e:
            tooltip(f"Undo failed: {e}")
        return (True, None)

    if cmd.startswith("onigiri_sort:"):
        try:
            sort_key = cmd.split(":", 1)[1]  # "default", "most_reviews", or "custom"
            # Map UI sort key to the internal sort_mode used by deck_tree_updater
            sort_mode_map = {
                "default":      "",             # Anki's native order (no custom sort)
                "most_reviews": "most_reviews", # Sort by review count descending
                "custom":       "custom",       # User's drag-drop order
            }
            internal_mode = sort_mode_map.get(sort_key, "")
            mw.col.conf["onigiri_sort_mode"] = internal_mode
            mw.col.conf["onigiri_deck_sort"] = sort_key  # for renderer checkmarks
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                _sync_organise_menu_state(context, sort_key=sort_key)
                deck_tree_updater.refresh_deck_tree_state(context, force=True)
        except Exception as e:
            tooltip(f"Sort failed: {e}")
        return (True, None)

    if cmd == "onigiri_filter_favorites":
        try:
            current = bool(mw.col.conf.get("onigiri_show_favorites", False))
            new_state = not current
            mw.col.conf["onigiri_show_favorites"] = new_state
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                _sync_organise_menu_state(
                    context,
                    favorites=new_state,
                )
                deck_tree_updater.refresh_deck_tree_state(context, force=True)
        except Exception as e:
            tooltip(f"Filter failed: {e}")
        return (True, None)

    if cmd == "onigiri_filter_marked":
        try:
            current = bool(mw.col.conf.get("onigiri_show_marked", False))
            new_state = not current
            mw.col.conf["onigiri_show_marked"] = new_state
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                _sync_organise_menu_state(
                    context,
                    marked=new_state,
                )
                deck_tree_updater.refresh_deck_tree_state(context, force=True)
        except Exception as e:
            tooltip(f"Filter failed: {e}")
        return (True, None)

    if cmd == "onigiri_filter_archived":
        try:
            current = bool(mw.col.conf.get(deck_tree_updater.SHOW_ARCHIVED_CONF_KEY, False))
            new_state = not current
            mw.col.conf[deck_tree_updater.SHOW_ARCHIVED_CONF_KEY] = new_state
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                _sync_organise_menu_state(
                    context,
                    archived=new_state,
                )
                deck_tree_updater.refresh_deck_tree_state(context, force=True)
        except Exception as e:
            tooltip(f"Filter failed: {e}")
        return (True, None)

    if cmd.startswith("onigiri_deck_search:"):
        try:
            import json as _json
            query = unquote(cmd.split(":", 1)[1]).strip()
            if not isinstance(context, DeckBrowser):
                return (True, None)

            if not query:
                # Empty query — restore the normal tree
                new_html = deck_tree_updater._render_deck_tree_html_only(context)
                context.web.eval(
                    "OnigiriEngine.updateDeckTree({}, {{force: true}});".format(_json.dumps(new_html))
                )
                return (True, None)

            new_html = deck_tree_updater._render_deck_search_tree_html_only(context, query)

            context.web.eval(
                "OnigiriEngine.updateDeckTree({}, {{force: true}});".format(_json.dumps(new_html))
            )
        except Exception as e:
            print(f"Onigiri: deck search error: {e}")
            import traceback
            traceback.print_exc()
        return (True, None)

    if cmd == "onigiri_ui_open":
        from . import onigiri_renderer
        onigiri_renderer._onigiri_ui_open = True
        return (True, None)

    if cmd == "onigiri_ui_close":
        from . import onigiri_renderer
        onigiri_renderer._onigiri_ui_open = False
        full_deferred = onigiri_renderer._onigiri_refresh_deferred
        tree_deferred = onigiri_renderer._onigiri_tree_refresh_deferred
        onigiri_renderer._onigiri_refresh_deferred = False
        onigiri_renderer._onigiri_tree_refresh_deferred = False

        if isinstance(context, DeckBrowser):
            if full_deferred:
                context.refresh()
            elif tree_deferred:
                deck_tree_updater.refresh_deck_tree_state(context)
        return (True, None)

    return handled


# ── Icon Chooser helpers ──────────────────────────────────────────────────────

def _get_icons_dir() -> str:
    addon_package = mw.addonManager.addonFromModule(__name__)
    addon_path = mw.addonManager.addonsFolder(addon_package)
    icons_dir = os.path.join(addon_path, "user_files", "custom_deck_icons")
    os.makedirs(icons_dir, exist_ok=True)
    return icons_dir


def _icon_payload(did: str) -> dict:
    """Build the data payload sent to OnigiriIconChooser.open()."""
    addon_package = mw.addonManager.addonFromModule(__name__)
    icons_dir = _get_icons_dir()

    def _list(ext):
        files = sorted(f for f in os.listdir(icons_dir) if f.lower().endswith(ext))
        return [{"name": f, "url": f"/_addons/{addon_package}/user_files/custom_deck_icons/{f}"} for f in files]

    custom_icons = mw.col.conf.get("onigiri_custom_deck_icons", {})
    current = custom_icons.get(str(did), {})
    return {
        "deckId": str(did),
        "icons":  _list(".svg"),
        "images": _list(".png"),
        "current": {
            "icon":  current.get("icon",  ""),
            "color": normalize_color_string(current.get("color", "#888888"), fallback="#888888") or "#888888",
        },
    }


def _open_icon_chooser_modal(context, did: str):
    """Inject the icon chooser modal directly into the deck browser webview."""
    if not isinstance(context, DeckBrowser):
        return
    payload = _icon_payload(did)
    payload_js = json.dumps(payload, ensure_ascii=True)
    context.web.eval(f"if(window.OnigiriIconChooser)OnigiriIconChooser.open({payload_js});")


def _icon_chooser_add_file(context, did: str, file_type: str):
    """Open a file dialog, copy selected files, and refresh the modal grid."""
    icons_dir = _get_icons_dir()
    if file_type == 'icon':
        paths, _ = QFileDialog.getOpenFileNames(mw, "Select SVG Icon(s)", "", "SVG Files (*.svg)")
    else:
        paths, _ = QFileDialog.getOpenFileNames(mw, "Select PNG Image(s)", "", "PNG Files (*.png)")

    if not paths:
        return
    for src in paths:
        dest = os.path.join(icons_dir, os.path.basename(src))
        try:
            shutil.copy2(src, dest)
        except Exception as e:
            print(f"[Onigiri IconChooser] Copy error: {e}")

    if isinstance(context, DeckBrowser):
        payload = _icon_payload(did)
        payload_js = json.dumps(payload, ensure_ascii=True)
        context.web.eval(f"if(window.OnigiriIconChooser)OnigiriIconChooser.refreshData({payload_js});")


def _icon_chooser_delete_file(context, did: str, filename: str):
    """Delete an icon/image file and refresh the modal grid."""
    icons_dir = _get_icons_dir()
    path = os.path.join(icons_dir, filename)
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f"[Onigiri IconChooser] Delete error: {e}")

    custom_icons = mw.col.conf.get("onigiri_custom_deck_icons", {})
    current = custom_icons.get(str(did), {})
    should_refresh_deck = current.get("icon") == filename
    if should_refresh_deck:
        custom_icons.pop(str(did), None)
        mw.col.conf["onigiri_custom_deck_icons"] = custom_icons
        mw.col.setMod()

    if isinstance(context, DeckBrowser):
        payload = _icon_payload(did)
        payload_js = json.dumps(payload, ensure_ascii=True)
        context.web.eval(f"if(window.OnigiriIconChooser)OnigiriIconChooser.refreshData({payload_js});")
        if should_refresh_deck:
            _refresh_deck_browser_locally(context, refresh_icon_css=True)
