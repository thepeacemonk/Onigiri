import html
import os
from aqt import mw, utils
from aqt.qt import QDialog, QVBoxLayout
from aqt.webview import AnkiWebView

class CreditsDialog(QDialog):
    """
    A pop-up dialog that shows the Credits and Acknowledgements.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Credits and Acknowledgements")
        self.setMinimumSize(600, 500)
        self.setMaximumSize(700, 600)
        self.setModal(True)

        # Main layout
        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        self.setLayout(vbox)

        # Webview for the content
        self.web = AnkiWebView(self)
        vbox.addWidget(self.web)

        addon_package = mw.addonManager.addonFromModule(__name__)

        html_path = os.path.join(os.path.dirname(__file__), "web", "credits.html")
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            html_content = html_content.replace("%%ADDON_PACKAGE%%", addon_package)
        except Exception as e:
            print(f"Onigiri: Failed to read credits.html: {e}")
            html_content = (
                "<!DOCTYPE html><html><head><meta charset=\"utf-8\"></head>"
                "<body style=\"font-family:system-ui,sans-serif;padding:24px;"
                "color:#e0e0e0;background:#2c2c2c;\">"
                "<h2>Credits and Acknowledgements</h2>"
                "<p>Could not load credits content. The file may be missing or unreadable.</p>"
                f"<p><code>{html.escape(html_path)}</code></p>"
                "</body></html>"
            )

        self.web.stdHtml(html_content)
        self.web.set_bridge_command(self._on_bridge_cmd, self)
    
    def _on_bridge_cmd(self, cmd: str):
        """Handles commands sent from the webview's JavaScript."""
        if cmd.startswith("open_link:"):
            url = cmd.split(":", 1)[1]
            utils.openLink(url)
        elif cmd == "close":
            self.accept()

_credits_dialog: CreditsDialog = None

def show_credits_dialog():
    """Creates and shows the credits dialog."""
    global _credits_dialog
    if _credits_dialog:
        _credits_dialog.close()

    _credits_dialog = CreditsDialog(mw)
    _credits_dialog.show()
