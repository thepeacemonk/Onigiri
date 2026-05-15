import os
import json
import shutil
import sys
from aqt import mw
from aqt.qt import *
from aqt.webview import AnkiWebView


class IconChooserDialog(QDialog):
    def __init__(self, deck_id, parent=None):
        super().__init__(parent)
        self.deck_id = str(deck_id)
        self.setWindowTitle("Choose Deck Icon")
        self.setMinimumSize(600, 500)

        self.addon_package = mw.addonManager.addonFromModule(__name__)
        self.addon_path = mw.addonManager.addonsFolder(self.addon_package)
        self.icons_dir = os.path.join(self.addon_path, "user_files", "custom_deck_icons")

        os.makedirs(self.icons_dir, exist_ok=True)

        # Current Config
        self.custom_icons = mw.col.conf.get("onigiri_custom_deck_icons", {})
        self.current_setting = self.custom_icons.get(self.deck_id, {})
        self.current_color = self.current_setting.get("color", "#888888")
        self.current_icon = self.current_setting.get("icon", "")

        # parent=self is required so Qt's WebChannel initialises correctly in a
        # standalone QDialog. WelcomeDialog (the proven working reference) does
        # the same — AnkiWebView(self).
        self.web = AnkiWebView(parent=self, title="Icon Chooser")

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.setLayout(layout)

        # Bridge must be wired BEFORE the page loads so pycmd is available the
        # moment any script runs.
        self.web.set_bridge_command(self._on_bridge_cmd, self)

        # Load content
        self.render()

    def render(self):
        """
        Build the icon-chooser page using the same pattern as WelcomeDialog:
          1. Read the HTML template.
          2. Inject CSS via <link> and JS via <script src> using Anki's addon
             URL scheme — no inline embedding to avoid </script> boundary bugs.
          3. Pre-inject ONIGIRI_ICON_INIT as a separate tiny <script> block
             BEFORE icon_chooser.js loads, so init data is always available.
          4. Pass the complete HTML document to stdHtml() with no extra params
             (exactly what WelcomeDialog does).
        """
        html_path = os.path.join(self.addon_path, "web", "icon_chooser.html")
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
        except Exception as e:
            print(f"[Onigiri IconChooser] Failed to read HTML: {e}")
            return

        # Build the init payload as a standalone <script> block so it is
        # NEVER embedded inside another script (no </script> boundary risk).
        init_payload = json.dumps({
            "icons": self._get_icon_data_list(),
            "images": self._get_image_data_list(),
            "current": {
                "icon": self.current_icon,
                "color": self.current_color,
            },
            "accentColor": mw.col.conf.get("colors", {}).get("light", {}).get("--accent-color", "#007aff"),
            "system_icons": {
                "add": f"/_addons/{self.addon_package}/system_files/system_icons/add.svg",
                "delete": f"/_addons/{self.addon_package}/system_files/system_icons/xmark-simple.svg",
            },
        }, ensure_ascii=True)   # ensure_ascii=True → all non-ASCII as \uXXXX, 100% safe inline

        css_url = f"/_addons/{self.addon_package}/web/icon_chooser.css"
        js_url  = f"/_addons/{self.addon_package}/web/icon_chooser.js"

        # Inject CSS link into <head>
        html_content = html_content.replace(
            "</head>",
            f'<link rel="stylesheet" href="{css_url}">\n</head>',
            1
        )
        # Inject init data (tiny, safe script) then the full JS file — both
        # immediately before </body> so the DOM is parsed before scripts run.
        init_script = f'<script>window.ONIGIRI_ICON_INIT = {init_payload};</script>'
        js_script   = f'<script src="{js_url}"></script>'
        html_content = html_content.replace(
            "</body>",
            f'{init_script}\n{js_script}\n</body>',
            1
        )

        # Pass complete HTML to stdHtml() — identical to WelcomeDialog's call.
        # No css=, js=, or head= args; Anki supplies its default theme vars/CSS
        # which makes var(--canvas) / var(--fg) etc. resolve correctly.
        self.web.stdHtml(html_content)

    # ------------------------------------------------------------------ #
    #  Data helpers                                                        #
    # ------------------------------------------------------------------ #

    def _get_icon_data_list(self):
        data_list = []
        if os.path.exists(self.icons_dir):
            files = [f for f in os.listdir(self.icons_dir)
                     if f.strip().lower().endswith(".svg")]
            files.sort()
            for f in files:
                url = f"/_addons/{self.addon_package}/user_files/custom_deck_icons/{f}"
                data_list.append({"name": f, "url": url})
        return data_list

    def _get_image_data_list(self):
        data_list = []
        if os.path.exists(self.icons_dir):
            files = [f for f in os.listdir(self.icons_dir)
                     if f.strip().lower().endswith(".png")]
            files.sort()
            for f in files:
                url = f"/_addons/{self.addon_package}/user_files/custom_deck_icons/{f}"
                data_list.append({"name": f, "url": url})
        return data_list

    # ------------------------------------------------------------------ #
    #  Bridge handler                                                      #
    # ------------------------------------------------------------------ #

    def _on_bridge_cmd(self, cmd):
        print(f"[Onigiri IconChooser] Bridge CMD: {cmd}")

        if cmd == "get_init_data":
            # Fallback if pre-injected data wasn't available on load
            payload = {
                "icons": self._get_icon_data_list(),
                "images": self._get_image_data_list(),
                "current": {
                    "icon": self.current_icon,
                    "color": self.current_color
                },
                "accentColor": mw.col.conf.get("colors", {}).get("light", {}).get("--accent-color", "#007aff"),
                "system_icons": {
                    "add": f"/_addons/{self.addon_package}/system_files/system_icons/add.svg",
                    "delete": f"/_addons/{self.addon_package}/system_files/system_icons/xmark-simple.svg"
                }
            }
            self.web.eval(f"updateData({json.dumps(payload)})")

        elif cmd == "reset":
            if self.deck_id in self.custom_icons:
                del self.custom_icons[self.deck_id]
                mw.col.conf["onigiri_custom_deck_icons"] = self.custom_icons
                mw.col.setMod()
            self.accept()

        elif cmd == "cancel":
            self.close()

        elif cmd.startswith("update_color:"):
            new_color = cmd.split(":", 1)[1]
            self.current_color = new_color

        elif cmd == "add_icon":
            self.add_icon_file()

        elif cmd == "add_image":
            self.add_image_file()

        elif cmd.startswith("save:"):
            data = json.loads(cmd.split(":", 1)[1])
            self.custom_icons[self.deck_id] = {
                "icon": data["icon"],
                "color": data["color"]
            }
            mw.col.conf["onigiri_custom_deck_icons"] = self.custom_icons
            mw.col.setMod()
            self.accept()

        elif cmd.startswith("delete_icon:"):
            filename = cmd.split(":", 1)[1]
            file_path = os.path.join(self.icons_dir, filename)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"[Onigiri IconChooser] Deleted: {filename}")
                    payload = {
                        "icons": self._get_icon_data_list(),
                        "images": self._get_image_data_list(),
                        "current": {
                            "icon": self.current_icon,
                            "color": self.current_color
                        },
                        "system_icons": {
                            "add": f"/_addons/{self.addon_package}/system_files/system_icons/add.svg",
                            "delete": f"/_addons/{self.addon_package}/system_files/system_icons/xmark-simple.svg"
                        }
                    }
                    self.web.eval(f"updateData({json.dumps(payload)})")
                except Exception as e:
                    print(f"[Onigiri IconChooser] Delete error: {e}")

    # ------------------------------------------------------------------ #
    #  File import helpers                                                 #
    # ------------------------------------------------------------------ #

    def add_icon_file(self):
        """Open file dialog to import SVG icon(s)."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Select SVG Icon(s)", "", "SVG Files (*.svg)"
        )
        if file_paths:
            for src_path in file_paths:
                filename = os.path.basename(src_path)
                dest_path = os.path.join(self.icons_dir, filename)
                try:
                    shutil.copy2(src_path, dest_path)
                except Exception as e:
                    print(f"[Onigiri IconChooser] Import error: {e}")
            payload = {
                "icons": self._get_icon_data_list(),
                "images": self._get_image_data_list(),
                "current": {"icon": self.current_icon, "color": self.current_color},
                "mode": "icon"
            }
            self.web.eval(f"updateData({json.dumps(payload)})")

    def add_image_file(self):
        """Open file dialog to import PNG image(s)."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "Select PNG Image(s)", "", "Image Files (*.png)"
        )
        if file_paths:
            for src_path in file_paths:
                filename = os.path.basename(src_path)
                dest_path = os.path.join(self.icons_dir, filename)
                try:
                    shutil.copy2(src_path, dest_path)
                except Exception as e:
                    print(f"[Onigiri IconChooser] Import Image error: {e}")
            payload = {
                "icons": self._get_icon_data_list(),
                "images": self._get_image_data_list(),
                "current": {"icon": self.current_icon, "color": self.current_color},
                "mode": "image"
            }
            self.web.eval(f"updateData({json.dumps(payload)})")
