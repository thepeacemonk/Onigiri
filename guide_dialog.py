import os
from aqt import mw, utils
from aqt.qt import QDialog, QVBoxLayout, QDialogButtonBox, QHBoxLayout, QWidget, Qt
from aqt.webview import AnkiWebView
from .translations import tr

class GuideDialog(QDialog):
    """
    A pop-up dialog that shows the Onigiri Guide.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Using a fallback to 'Onigiri Guide' in case translation is missing for some language
        title = tr("onigiri_guide") if "onigiri_guide" in tr("onigiri_guide") else "Onigiri Guide"
        self.setWindowTitle(title)
        self.setMinimumSize(600, 650)
        self.setMaximumSize(700, 800)
        self.setModal(True)

        # Main layout
        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        self.setLayout(vbox)

        # Webview for the content
        self.web = AnkiWebView(self)
        vbox.addWidget(self.web, 1)

        addon_package = mw.addonManager.addonFromModule(__name__)

        # Load the HTML content from the file
        html_path = os.path.join(os.path.dirname(__file__), "web", "guide.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Replace placeholders in HTML content
        html_content = html_content.replace("%%ADDON_PACKAGE%%", addon_package)
        html_content = html_content.replace("%%ONIGIRI_GUIDE%%", title)

        self.web.stdHtml(html_content)
        self.web.set_bridge_command(self._on_bridge_cmd, self)

        # --- Native Qt Controls ---
        controls_widget = QWidget(self)
        controls_layout = QHBoxLayout(controls_widget)
        controls_layout.setContentsMargins(10, 5, 10, 5)

        controls_layout.addStretch()

        # Button Box
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        # Close fallback
        btn_text = tr("close") if "close" in tr("close") else "Close"
        button_box.button(QDialogButtonBox.StandardButton.Ok).setText(btn_text)
        button_box.accepted.connect(self.accept)
        controls_layout.addWidget(button_box)

        vbox.addWidget(controls_widget)
    
    def _on_bridge_cmd(self, cmd: str):
        """Handles commands sent from the webview's JavaScript."""
        if cmd.startswith("open_link:"):
            url = cmd.split(":", 1)[1]
            utils.openLink(url)

_dialog: GuideDialog = None

def show_guide_dialog():
    """Creates and shows the guide dialog."""
    global _dialog
    if _dialog:
        _dialog.close()

    _dialog = GuideDialog(mw)
    _dialog.show()
