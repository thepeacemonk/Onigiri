import os

from aqt import mw, utils
from aqt.qt import QDialog, QVBoxLayout
from aqt.webview import AnkiWebView

from .translations import tr


class DonationsDialog(QDialog):
    """A pop-up webview that shows Onigiri donation channels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("donations_title", "Donations"))
        self.setMinimumSize(640, 760)
        self.setMaximumSize(760, 820)
        self.setModal(True)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.web = AnkiWebView(self)
        layout.addWidget(self.web)

        addon_package = mw.addonManager.addonFromModule(__name__)
        html_path = os.path.join(os.path.dirname(__file__), "web", "donations.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        html_content = html_content.replace("%%ADDON_PACKAGE%%", addon_package)
        self.web.stdHtml(html_content)
        self.web.set_bridge_command(self._on_bridge_cmd, self)

    def _on_bridge_cmd(self, cmd: str):
        if cmd.startswith("open_link:"):
            url = cmd.split(":", 1)[1]
            utils.openLink(url)
        elif cmd == "close":
            self.accept()


_donations_dialog: DonationsDialog = None


def show_donations_dialog():
    """Creates and shows the donations dialog."""
    global _donations_dialog
    if _donations_dialog:
        _donations_dialog.close()

    _donations_dialog = DonationsDialog(mw)
    _donations_dialog.show()
