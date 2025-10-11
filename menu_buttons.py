# --- Onigiri ---
# Handles the creation of the top-level Onigiri menu.

from aqt import mw
from . import welcome_dialog
from aqt.qt import QAction, QMenu

# Import the necessary components from other add-on files
from . import settings
from . import patcher

# A module-level variable to hold the addon path, set once on setup.
_addon_path = None

def open_settings(page_index=0):
    """
    Opens the Onigiri settings dialog to a specific page and resets the UI upon save.
    This function now accepts a page_index to open to a specific tab.
    """
    global _addon_path
    if not _addon_path:
        # This should not happen if setup_onigiri_menu is called correctly.
        print("Onigiri Error: addon_path not set. Cannot open settings.")
        return
        
    dialog = settings.SettingsDialog(mw, _addon_path, initial_page_index=page_index)
    if dialog.exec():
        mw.reset()

def setup_onigiri_menu(addon_path):
    """
    Creates and adds the 'Onigiri' top-level menu to Anki's main window.
    This menu will contain actions for general settings, profile settings, and viewing the profile.
    """
    global _addon_path
    _addon_path = addon_path

    # The function to open the profile page is already defined in the patcher module.
    open_profile = patcher.show_profile_page

    # Create the top-level menu with the Onigiri icon
    onigiri_menu = QMenu("Onigiri", mw)

    # Create the 'Profile' action (for viewing)
    profile_action = QAction("Profile", mw)
    profile_action.triggered.connect(open_profile)
    onigiri_menu.addAction(profile_action)

    # Create the 'Add-on Settings' action (opens settings to General tab, index 0)
    settings_action = QAction("Onigiri Settings", mw)
    settings_action.setShortcut("Ctrl+Shift+S") 
    settings_action.triggered.connect(lambda: open_settings(0))
    onigiri_menu.addAction(settings_action)

    onigiri_menu.addSeparator()

    # --- START: ADD THIS BLOCK ---
    welcome_action = QAction("Welcome Screen", mw)
    welcome_action.triggered.connect(welcome_dialog.show_welcome_dialog)
    onigiri_menu.addAction(welcome_action)
    # --- END: ADD THIS BLOCK ---

    # Add the newly created menu to the main window's menubar
    mw.form.menubar.addMenu(onigiri_menu)