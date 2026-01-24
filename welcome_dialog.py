import os
from aqt import mw, utils
from aqt.qt import QDialog, QVBoxLayout, QDialogButtonBox, QCheckBox, QHBoxLayout, QWidget
from aqt.webview import AnkiWebView
from . import config
from . import settings

CURRENT_WELCOME_VERSION = "1.0.8.3-beta"

class WelcomeDialog(QDialog):
    """
    A pop-up dialog that shows a welcome message to new users.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Onigiri")
        self.setMinimumSize(500, 450)
        self.setMaximumSize(500, 450)
        self.setModal(True)

        # Main layout
        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        self.setLayout(vbox)

        # Webview for the content
        self.web = AnkiWebView(self)
        vbox.addWidget(self.web, 1) # The '1' makes it take up available space

        addon_package = mw.addonManager.addonFromModule(__name__)

        # Load the HTML content from the file
        html_path = os.path.join(os.path.dirname(__file__), "web", "welcome.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Replace placeholder
        html_content = html_content.replace("%%ADDON_PACKAGE%%", addon_package)

        self.web.stdHtml(html_content)
        self.web.set_bridge_command(self._on_bridge_cmd, self)

        # --- Native Qt Controls ---
        controls_widget = QWidget(self)
        controls_layout = QHBoxLayout(controls_widget)
        controls_layout.setContentsMargins(10, 5, 10, 5)

        # Checkbox
        self.dont_show_again_checkbox = QCheckBox("Don't show this again")

        # Set initial state from config
        conf = config.get_config()
        # If showWelcomePopup is False, the box should be checked.
        is_checked = not conf.get("showWelcomePopup", True)
        self.dont_show_again_checkbox.setChecked(is_checked)
        
        controls_layout.addWidget(self.dont_show_again_checkbox)

        controls_layout.addStretch() # Pushes the button to the right

        # Button Box
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Got it!")
        button_box.accepted.connect(self._on_accept)
        controls_layout.addWidget(button_box)

        vbox.addWidget(controls_widget)
    
    def _on_bridge_cmd(self, cmd: str):
        """Handles commands sent from the webview's JavaScript."""
        if cmd.startswith("open_link:"):
            url = cmd.split(":", 1)[1]
            utils.openLink(url)

    def _on_accept(self):
        """Handle saving config and closing the dialog."""
        conf = config.get_config()
        # If the box is checked, showWelcomePopup should be False.
        # If it's unchecked, showWelcomePopup should be True.
        conf["showWelcomePopup"] = not self.dont_show_again_checkbox.isChecked()
        conf["lastSeenWelcomeVersion"] = CURRENT_WELCOME_VERSION
        config.write_config(conf)
        self.accept() # Close the dialog

    def done(self, r):
        super().done(r)
        
        # Open Settings when the welcome dialog is closed (via "Got it" or "X")
        addon_path = os.path.dirname(__file__)
        dialog = settings.SettingsDialog(mw, addon_path, initial_page_index=0)
        if dialog.exec():
            mw.reset()

    def accept(self):
        super().accept()

    def reject(self):
        super().reject()

_dialog: WelcomeDialog = None

def show_welcome_dialog():
    """Creates and shows the welcome dialog."""
    global _dialog
    if _dialog:
        _dialog.close()

    _dialog = WelcomeDialog(mw)
    _dialog.show()