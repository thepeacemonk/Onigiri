# --- Onigiri ---
# Handles the creation of the top-level Onigiri menu.

import os
import json
from aqt import mw
from aqt.qt import QAction, QKeySequence, QMenu, QShortcut

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
    """Opens the Onigiri settings dialog to a specific page."""
    global _addon_path
    if not _addon_path:
        print("Onigiri Error: addon_path not set. Cannot open settings.")
        return

    from . import settings

    dialog = settings.SettingsDialog(mw, _addon_path, initial_page_index=page_index)
    dialog.exec()


def _open_profile():
    from . import patcher

    patcher.show_profile_page()


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


def _open_prep_station():
    from . import prep_station

    prep_station.open_prep_station(mw)


def _open_hashi_notes():
    from . import hashi_notes

    hashi_notes.open_hashi_gallery(mw)


def _toggle_pomodoro():
    from . import pomodoro

    pomodoro.toggle_widget(mw)


def _open_pomodoro_stats():
    from . import pomodoro

    pomodoro.open_stats_dialog(mw)


def _open_onigiri_guide():
    from aqt.utils import openLink

    openLink("https://onigiri-addon-guide.notion.site/")


def _show_welcome_dialog():
    from . import welcome_dialog

    welcome_dialog.show_welcome_dialog()


def _show_donations_dialog():
    from . import donations_dialog

    donations_dialog.show_donations_dialog()


def _show_credits_dialog():
    from . import credits_dialog

    credits_dialog.show_credits_dialog()


def setup_onigiri_menu(addon_path):
    """Creates and adds the 'Onigiri' top-level menu to Anki's main window."""
    global _addon_path
    _addon_path = addon_path

    onigiri_menu = QMenu(tr("onigiri_menu", "Onigiri"), mw)

    profile_action = QAction(tr("profile", "Profile"), mw)
    profile_action.triggered.connect(_open_profile)
    onigiri_menu.addAction(profile_action)

    # --- Games submenu ---
    gamification_menu = QMenu(tr("gamification", "Gamification"), mw)

    nook_level_action = QAction(tr("restaurant_level", "Nook Level"), mw)
    nook_level_action.triggered.connect(_open_nook_level_dialog)
    gamification_menu.addAction(nook_level_action)

    store_action = QAction(tr("taiyaki_store", "Mr. Taiyaki Store"), mw)
    store_action.triggered.connect(_open_taiyaki_store)
    gamification_menu.addAction(store_action)

    onigimon_action = QAction("Onigimon", mw)
    onigimon_action.triggered.connect(_open_onigimon_care)
    gamification_menu.addAction(onigimon_action)

    hexagon_land_action = QAction(tr("hexland_title", "Hexagon Land"), mw)
    hexagon_land_action.triggered.connect(_open_hexagon_land)
    gamification_menu.addAction(hexagon_land_action)

    onigiri_menu.addMenu(gamification_menu)

    # --- Study Tools submenu ---
    study_tools_menu = QMenu(tr("study_tools", "Study Tools"), mw)

    prep_station_action = QAction(tr("prep_station_title", "Prep Station"), mw)
    prep_station_action.triggered.connect(_open_prep_station)
    study_tools_menu.addAction(prep_station_action)

    hashi_notes_action = QAction(tr("hashi_notes_title", "Hashi Notes"), mw)
    hashi_notes_action.triggered.connect(_open_hashi_notes)
    study_tools_menu.addAction(hashi_notes_action)

    pomodoro_action = QAction(tr("pomodoro_title", "Pomodoro"), mw)
    pomodoro_action.triggered.connect(_toggle_pomodoro)
    study_tools_menu.addAction(pomodoro_action)

    pomodoro_stats_action = QAction(tr("pomodoro_stats_title", "Pomodoro Stats"), mw)
    pomodoro_stats_action.triggered.connect(_open_pomodoro_stats)
    study_tools_menu.addAction(pomodoro_stats_action)

    onigiri_menu.addMenu(study_tools_menu)

    # Shift+P toggles the Pomodoro floating island from anywhere in the main
    # window - a window-wide shortcut fires regardless of focused child widget.
    pomodoro_shortcut = QShortcut(QKeySequence("Shift+P"), mw)
    pomodoro_shortcut.activated.connect(_toggle_pomodoro)

    settings_action = QAction(tr("onigiri_settings", "Onigiri Settings"), mw)
    settings_action.triggered.connect(lambda _: open_settings(0))
    onigiri_menu.addAction(settings_action)

    onigiri_menu.addSeparator()

    # --- Info submenu ---
    info_menu = onigiri_menu.addMenu(tr("info", "Info"))

    guide_action = QAction(tr("onigiri_guide", "Onigiri Guide"), mw)
    guide_action.triggered.connect(_open_onigiri_guide)
    info_menu.addAction(guide_action)

    welcome_action = QAction(tr("welcome_screen", "Welcome Screen"), mw)
    welcome_action.triggered.connect(_show_welcome_dialog)
    info_menu.addAction(welcome_action)

    donations_action = QAction(tr("donations_title", "Donations"), mw)
    donations_action.triggered.connect(_show_donations_dialog)
    info_menu.addAction(donations_action)

    credits_action = QAction(tr("credits", "Credits"), mw)
    credits_action.triggered.connect(_show_credits_dialog)
    info_menu.addAction(credits_action)

    # Add version info at the bottom (disabled)
    version_action = QAction(f"{tr('version_label', 'Version')}: {get_onigiri_version()}", mw)
    version_action.setEnabled(False)
    onigiri_menu.addAction(version_action)

    mw.form.menubar.addMenu(onigiri_menu)
