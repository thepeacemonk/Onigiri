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





def _open_onigiri_guide():
    from aqt.utils import openLink

    openLink(
        "https://onigiri-addon-guide.notion.site/"
    )


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


def _toggle_pomodoro():
    from . import pomodoro

    pomodoro.toggle_widget(mw)


def _open_pomodoro_stats():
    from . import pomodoro

    pomodoro.open_stats_dialog(mw)

def _show_welcome_message():
    from . import config
    conf = config.get_config()
    conf["showWelcomePopup"] = True
    config.write_config(conf)
    
    if mw.state == "deckBrowser" and mw.deckBrowser.web:
        mw.deckBrowser.web.eval("""
            if (!document.getElementById("onigiri-welcome-overlay")) {
                const style = document.createElement("style");
                style.id = "onigiri-welcome-style";
                style.innerHTML = `
                    @font-face {
                        font-family: 'OnigiriPoppins';
                        src: url('/_addons/1011095603/system_files/fonts/system_fonts/Poppins/Poppins-Regular.ttf');
                        font-weight: 400;
                    }
                    @font-face {
                        font-family: 'OnigiriPoppins';
                        src: url('/_addons/1011095603/system_files/fonts/system_fonts/Poppins/Poppins-Medium.ttf');
                        font-weight: 500 900;
                    }
                    #onigiri-welcome-overlay {
                        position: fixed; inset: 0; z-index: 2147483647;
                        display: flex; flex-direction: column; align-items: center; justify-content: center;
                        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
                        background: rgba(0, 0, 0, 0.55);
                        color: white;
                        font-family: 'OnigiriPoppins', -apple-system, BlinkMacSystemFont, sans-serif;
                        opacity: 0; transition: opacity 0.4s ease;
                    }
                    #onigiri-welcome-overlay .btn-continue {
                        margin-top: 36px; padding: 16px 48px; font-size: 21px; font-weight: 700;
                        font-family: 'OnigiriPoppins', sans-serif; color: #123034; background: white;
                        border: none; border-radius: 40px; cursor: pointer;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.2); transition: transform 0.2s, box-shadow 0.2s;
                    }
                    #onigiri-welcome-overlay .btn-continue:hover {
                        transform: scale(1.05); box-shadow: 0 6px 16px rgba(0,0,0,0.3);
                    }
                `;
                document.head.appendChild(style);

                const overlay = document.createElement("div");
                overlay.id = "onigiri-welcome-overlay";
                overlay.innerHTML = `
                    <img src="/_addons/1011095603/onigiri_logo.png" style="width: 290px; height: auto; margin-bottom: 32px; filter: drop-shadow(0 6px 16px rgba(0,0,0,0.3));" />
                    <h1 style="margin: 0 0 20px 0; font-size: 49px; font-weight: 700; text-shadow: 0 2px 6px rgba(0,0,0,0.5);">Welcome!</h1>
                    <p style="margin: 0; font-size: 26px; font-weight: 500; text-shadow: 0 1px 4px rgba(0,0,0,0.5);">Proceed to Settings to start customizing</p>
                    <button class="btn-continue">Continue</button>
                `;
                
                const btn = overlay.querySelector('.btn-continue');
                btn.addEventListener("click", function() {
                    overlay.style.opacity = "0";
                    setTimeout(() => {
                        overlay.remove();
                        const s = document.getElementById("onigiri-welcome-style");
                        if (s) s.remove();
                        pycmd("onigiri_welcome_dismissed");
                    }, 400);
                });
                
                document.body.appendChild(overlay);
                setTimeout(() => { overlay.style.opacity = "1"; }, 50);
            }
        """)
    elif mw.state == "overview":
        mw.moveToState("deckBrowser")
    elif mw.state == "review":
        mw.moveToState("deckBrowser")

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
    

    # Add the Gamification submenu to the main menu
    onigiri_menu.addMenu(gamification_menu)

    # Create Study Tools submenu
    study_tools_menu = QMenu(tr("study_tools", "Study Tools"), mw)

    prep_station_action = QAction(tr("prep_station_title"), mw)
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
    # window (deck browser, reviewer, etc.) - a window-wide shortcut fires
    # regardless of which child widget currently has focus.
    pomodoro_shortcut = QShortcut(QKeySequence("Shift+P"), mw)
    pomodoro_shortcut.activated.connect(_toggle_pomodoro)

    # Create the 'Settings' action (opens settings to General tab, index 0)
    settings_action = QAction(tr("onigiri_settings"), mw)
    settings_action.triggered.connect(lambda _: open_settings(0))
    onigiri_menu.addAction(settings_action)

    onigiri_menu.addSeparator()

    # --- ADD THIS BLOCK ---
    info_menu = onigiri_menu.addMenu("Info")

    guide_action = QAction(tr("onigiri_guide", "Onigiri Guide"), mw)
    guide_action.triggered.connect(_open_onigiri_guide)
    info_menu.addAction(guide_action)

    welcome_action = QAction("Welcome Message", mw)
    welcome_action.triggered.connect(_show_welcome_message)
    info_menu.addAction(welcome_action)

    donations_action = QAction(tr("donations_title", "Donations"), mw)
    donations_action.triggered.connect(_show_donations_dialog)
    info_menu.addAction(donations_action)

    credits_action = QAction(tr("credits"), mw)
    credits_action.triggered.connect(_show_credits_dialog)
    info_menu.addAction(credits_action)
    # --- END: ADD THIS BLOCK ---

    # Add version info at the bottom (disabled)
    version_action = QAction(f"{tr('version_label')}: {get_onigiri_version()}", mw)
    version_action.setEnabled(False)  # Make it non-clickable
    onigiri_menu.addAction(version_action)

    # Add the newly created menu to the main window's menubar
    mw.form.menubar.addMenu(onigiri_menu)
