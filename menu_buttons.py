# --- Onigiri ---
# Handles the creation of the top-level Onigiri menu.

import os
import json
from aqt import mw
from aqt.qt import QAction, QMenu

from .translations import tr

# A module-level variable to hold the addon path, set once on setup.
_addon_path = None

def get_onigiri_version():
    """Reads the version from manifest.json file."""
    global _addon_path
    if not _addon_path:
        return "Unknown"

    manifest_path = os.path.join(_addon_path, "manifest.json")
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            return manifest.get("version", "Unknown")
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return "Unknown"

def open_settings(page_index=0):
    """
    Opens the Onigiri settings dialog to a specific page.
    This function now accepts a page_index to open to a specific tab.
    """
    global _addon_path
    if not _addon_path:
        # This should not happen if setup_onigiri_menu is called correctly.
        print("Onigiri Error: addon_path not set. Cannot open settings.")
        return
        
    from . import settings

    dialog = settings.SettingsDialog(mw, _addon_path, initial_page_index=page_index)
    dialog.exec()


def _open_nook_level_dialog():
    from . import patcher

    patcher.open_nook_level_dialog()


def _open_taiyaki_store():
    from .gamification.taiyaki_store import open_taiyaki_store

    open_taiyaki_store()


def _open_onigimon_care():
    from . import patcher

    patcher.open_onigimon_care_dialog()


def _open_hexagon_land():
    from .gamification.hexagon_land import open_hexagon_land_dialog

    open_hexagon_land_dialog()


def _open_onigimon_sandbox():
    from .gamification.onigimon_sandbox import open_sandbox

    open_sandbox()


def _show_guide_dialog():
    from . import guide_dialog

    guide_dialog.show_guide_dialog()


def _show_donations_dialog():
    from . import donations_dialog

    donations_dialog.show_donations_dialog()


def _show_credits_dialog():
    from . import credits_dialog

    credits_dialog.show_credits_dialog()


def _open_prep_station():
    from . import prep_station

    prep_station.open_prep_station(mw)


def _open_hashi_notes():
    from . import hashi_notes

    hashi_notes.open_hashi_gallery(mw)

def setup_onigiri_menu(addon_path):
    """
    Creates and adds the 'Onigiri' top-level menu to Anki's main window.
    This menu will contain actions for general settings, profile settings, and viewing the profile.
    """
    global _addon_path
    _addon_path = addon_path

    # Create the top-level menu with the Onigiri icon
    onigiri_menu = QMenu(tr("onigiri_menu"), mw)

    # Create Gamification submenu
    gamification_menu = QMenu(tr("gamification"), mw)

    nook_level_action = QAction(tr("restaurant_level"), mw)
    nook_level_action.triggered.connect(_open_nook_level_dialog)
    gamification_menu.addAction(nook_level_action)

    store_action = QAction(tr("taiyaki_store"), mw)
    store_action.triggered.connect(_open_taiyaki_store)
    gamification_menu.addAction(store_action)

    onigimon_action = QAction("Onigimon", mw)
    onigimon_action.triggered.connect(_open_onigimon_care)
    gamification_menu.addAction(onigimon_action)

    hexagon_land_action = QAction(tr("hexland_title", "Hexagon Land"), mw)
    hexagon_land_action.triggered.connect(_open_hexagon_land)
    gamification_menu.addAction(hexagon_land_action)
    
    sandbox_action = QAction("Onigimon Sandbox (Debug)", mw)
    sandbox_action.triggered.connect(_open_onigimon_sandbox)
    gamification_menu.addAction(sandbox_action)
    
    # Add the Gamification submenu to the main menu
    onigiri_menu.addMenu(gamification_menu)

    # Create Study Tools submenu
    study_tools_menu = QMenu("Study Tools", mw)

    prep_station_action = QAction(tr("prep_station_title"), mw)
    prep_station_action.triggered.connect(_open_prep_station)
    study_tools_menu.addAction(prep_station_action)

    hashi_notes_action = QAction(tr("hashi_notes_title", "Hashi Notes"), mw)
    hashi_notes_action.triggered.connect(_open_hashi_notes)
    study_tools_menu.addAction(hashi_notes_action)

    onigiri_menu.addMenu(study_tools_menu)

    # Create the 'Settings' action (opens settings to General tab, index 0)
    settings_action = QAction(tr("onigiri_settings"), mw)
    settings_action.triggered.connect(lambda _: open_settings(0))
    onigiri_menu.addAction(settings_action)

    onigiri_menu.addSeparator()

    # --- ADD THIS BLOCK ---
    guide_action = QAction(tr("onigiri_guide") if "onigiri_guide" in tr("onigiri_guide") else "Onigiri Guide", mw)
    guide_action.triggered.connect(_show_guide_dialog)
    onigiri_menu.addAction(guide_action)

    donations_action = QAction(tr("donations_title", "Donations"), mw)
    donations_action.triggered.connect(_show_donations_dialog)
    onigiri_menu.addAction(donations_action)

    credits_action = QAction(tr("credits"), mw)
    credits_action.triggered.connect(_show_credits_dialog)
    onigiri_menu.addAction(credits_action)
    # --- END: ADD THIS BLOCK ---

    # Add version info at the bottom (disabled)
    version_action = QAction(f"{tr('version_label')}: {get_onigiri_version()}", mw)
    version_action.setEnabled(False)  # Make it non-clickable
    onigiri_menu.addAction(version_action)

    # Add the newly created menu to the main window's menubar
    mw.form.menubar.addMenu(onigiri_menu)
