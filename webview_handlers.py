import os
import json
import shutil
from typing import Tuple, Any
from aqt.deckbrowser import DeckBrowser
from . import deck_tree_updater
from . import create_deck_dialog
from aqt import mw
from aqt.qt import QFileDialog
from aqt.utils import tooltip
from . import sort_dialog

def handle_webview_cmd(handled: Tuple[bool, Any], cmd: str, context) -> Tuple[bool, Any]:
    """
    Centralized handler for webview commands from the deck browser.
    """
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
            js = f"var s=document.querySelector('.sidebar-left');if(s){{s.classList.toggle('deck-focus-mode',{str(new_state).lower()});}}"
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

    if cmd.startswith("onigiri_ctx_rename:"):
        try:
            from . import rename_dialog as _rd
            did = cmd.split(":", 1)[1]
            deck = mw.col.decks.get(int(did))
            if not deck:
                return (True, None)
            current_name = deck["name"]
            leaf = current_name.split("::")[-1]
            parent_prefix = "::".join(current_name.split("::")[:-1])

            new_name = _rd.show_rename_dialog(mw, leaf, current_name, parent_prefix)
            if new_name and new_name.strip():
                new_name = new_name.strip()
                # If the user edited the full path, use it directly;
                # otherwise prepend the existing parent prefix.
                if "::" in new_name:
                    new_full = new_name
                else:
                    new_full = (parent_prefix + "::" + new_name) if parent_prefix else new_name
                mw.col.decks.rename(deck, new_full)
                mw.col.setMod()
                if isinstance(context, DeckBrowser):
                    deck_tree_updater.refresh_deck_tree_state(context)
        except Exception as e:
            tooltip(f"Rename failed: {e}")
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
            from anki.decks import DeckId as _DeckId
            payload = _json.loads(cmd.split(":", 1)[1])
            source_did = _DeckId(int(payload["source_did"]))
            target_did = _DeckId(int(payload["target_did"]))
            drop_type = payload.get("type", "nest")

            if drop_type == "nest":
                # Reparent source deck as a child of target deck
                mw.col.decks.reparent([source_did], target_did)
                mw.col.setMod()
            else:
                # Reorder (before/after): if source and target have different
                # parents, move source to target's parent level first.
                source_deck = mw.col.decks.get(source_did)
                target_deck = mw.col.decks.get(target_did)
                if source_deck and target_deck:
                    source_name = source_deck["name"]
                    target_name = target_deck["name"]
                    source_parent = "::".join(source_name.split("::")[:-1])
                    target_parent = "::".join(target_name.split("::")[:-1])
                    if source_parent != target_parent:
                        source_leaf = source_name.split("::")[-1]
                        new_full_name = (target_parent + "::" + source_leaf) if target_parent else source_leaf
                        existing = mw.col.decks.by_name(new_full_name)
                        if existing is None or existing["id"] == int(source_did):
                            mw.col.decks.rename(source_deck, new_full_name)
                            mw.col.setMod()

                # Save the new visual order as the custom sort
                new_order = payload.get("new_order", [])
                if new_order:
                    mw.col.conf["onigiri_sort_mode"] = "custom"
                    mw.col.conf["onigiri_deck_sort"] = "custom"  # sync ellipsis checkmark
                    mw.col.conf["onigiri_custom_deck_order"] = new_order
                    mw.col.setMod()

            if isinstance(context, DeckBrowser):
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
            custom_icons = mw.col.conf.get("onigiri_custom_deck_icons", {})
            custom_icons[did] = {"icon": data.get("icon", ""), "color": data.get("color", "#888888")}
            mw.col.conf["onigiri_custom_deck_icons"] = custom_icons
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                context._renderPage()  # full reload so loading overlay appears
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
                context._renderPage()  # full reload so loading overlay appears
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
                # Full re-render so ONIGIRI_GLOBAL_DATA.ellipsis_actions is rebuilt
                # with the updated checkmark, and the loading overlay appears briefly.
                context._renderPage()
        except Exception as e:
            tooltip(f"Sort failed: {e}")
        return (True, None)

    if cmd == "onigiri_filter_favourites":
        try:
            current = bool(mw.col.conf.get("onigiri_show_favourites", False))
            mw.col.conf["onigiri_show_favourites"] = not current
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                # Full re-render so the Favourites tick and deck list both update correctly.
                context._renderPage()
        except Exception as e:
            tooltip(f"Filter failed: {e}")
        return (True, None)

    if cmd == "onigiri_filter_marked":
        try:
            current = bool(mw.col.conf.get("onigiri_show_marked", False))
            mw.col.conf["onigiri_show_marked"] = not current
            mw.col.setMod()
            if isinstance(context, DeckBrowser):
                # Full re-render so the Marked tick and deck list both update correctly.
                context._renderPage()
        except Exception as e:
            tooltip(f"Filter failed: {e}")
        return (True, None)

    if cmd.startswith("onigiri_deck_search:"):
        try:
            import json as _json
            query = cmd.split(":", 1)[1].strip().lower()
            if not isinstance(context, DeckBrowser):
                return (True, None)

            if not query:
                # Empty query — restore the normal tree
                new_html = deck_tree_updater._render_deck_tree_html_only(context)
                context.web.eval(
                    "OnigiriEngine.updateDeckTree({});".format(_json.dumps(new_html))
                )
                return (True, None)

            # Search ALL deck names (including collapsed children)
            all_decks = mw.col.decks.all()
            matched_ids = set()
            for d in all_decks:
                name = d.get("name", "")
                leaf = name.split("::")[-1]
                if query in name.lower() or query in leaf.lower():
                    matched_ids.add(str(d["id"]))

            # Re-render the full tree but only emit rows whose deck_id is in matched_ids
            from aqt.deckbrowser import RenderDeckNodeContext
            from . import onigiri_renderer

            tree_data = mw.col.sched.deck_due_tree()
            ctx = RenderDeckNodeContext(current_deck_id=mw.col.decks.get_current_id())

            rows = []
            def collect_matching(nodes):
                for node in nodes:
                    if str(node.deck_id) in matched_ids:
                        rows.append(context._render_deck_node(node, ctx))
                    collect_matching(node.children)

            collect_matching(tree_data.children)
            new_html = "".join(rows)

            context.web.eval(
                "OnigiriEngine.updateDeckTree({});".format(_json.dumps(new_html))
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
        if onigiri_renderer._onigiri_refresh_deferred:
            onigiri_renderer._onigiri_refresh_deferred = False
            if isinstance(context, DeckBrowser):
                context.refresh()
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
            "color": current.get("color", "#888888"),
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

    if isinstance(context, DeckBrowser):
        payload = _icon_payload(did)
        payload_js = json.dumps(payload, ensure_ascii=True)
        context.web.eval(f"if(window.OnigiriIconChooser)OnigiriIconChooser.refreshData({payload_js});")