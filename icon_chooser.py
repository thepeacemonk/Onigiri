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

        # Initial Web View Setup
        self.web = AnkiWebView(title="Icon Chooser")
        self.web.set_bridge_command(self._on_bridge_cmd, self)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.setLayout(layout)
        
        # Load Content
        self.render()

    def render(self):
        html_path = os.path.join(self.addon_path, "web", "icon_chooser.html")
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
            
        # Inject standard Anki webview content (night mode class etc)
        self.web.stdHtml(
            html_content,
            css=[f"/_addons/{self.addon_package}/web/icon_chooser.css"],
            js=[f"/_addons/{self.addon_package}/web/icon_chooser.js"],
            context=self
        )

    def _get_icon_data_list(self):
        data_list = []
        if os.path.exists(self.icons_dir):
            files = [f for f in os.listdir(self.icons_dir) if f.strip().lower().endswith(".svg")]
            files.sort()
            for f in files:
                # Use Direct URL access via Anki's web server
                url = f"/_addons/{self.addon_package}/user_files/custom_deck_icons/{f}"
                data_list.append({"name": f, "url": url})
        return data_list

    def _on_bridge_cmd(self, cmd):
        print(f"[Onigiri IconChooser] Bridge CMD: {cmd}")
        
        if cmd == "get_init_data":
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
            print("[Onigiri IconChooser] Cancel requested. Closing dialog.")
            self.close()
            
        elif cmd.startswith("update_color:"):
            new_color = cmd.split(":", 1)[1]
            self.current_color = new_color
            print(f"[Onigiri IconChooser] Color updated to: {new_color}")
        
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
                    
                    # Refresh the icon list
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

    def add_icon_file(self):
        """Open file dialog to import SVG icon(s)."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select SVG Icon(s)",
            "",
            "SVG Files (*.svg)"
        )
        if file_paths:
            for src_path in file_paths:
                filename = os.path.basename(src_path)
                dest_path = os.path.join(self.icons_dir, filename)
                try:
                    shutil.copy2(src_path, dest_path)
                    print(f"[Onigiri IconChooser] Imported: {filename}")
                except Exception as e:
                    print(f"[Onigiri IconChooser] Import error: {e}")
            # Refresh the icon list
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

    def add_icon_file(self):
        """Open file dialog to import SVG icon(s)."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select SVG Icon(s)",
            "",
            "SVG Files (*.svg)"
        )
        if file_paths:
            for src_path in file_paths:
                filename = os.path.basename(src_path)
                dest_path = os.path.join(self.icons_dir, filename)
                try:
                    shutil.copy2(src_path, dest_path)
                    print(f"[Onigiri IconChooser] Imported: {filename}")
                except Exception as e:
                    print(f"[Onigiri IconChooser] Import error: {e}")
            # Refresh the icon list
            payload = {
                "icons": self._get_icon_data_list(),
                "images": self._get_image_data_list(),
                "current": {
                    "icon": self.current_icon,
                    "color": self.current_color
                },
                "mode": "icon"
            }
            self.web.eval(f"updateData({json.dumps(payload)})")

    def _get_image_data_list(self):
        data_list = []
        if os.path.exists(self.icons_dir):
            files = [f for f in os.listdir(self.icons_dir) if f.strip().lower().endswith(".png")]
            files.sort()
            for f in files:
                # Use Direct URL access via Anki's web server
                url = f"/_addons/{self.addon_package}/user_files/custom_deck_icons/{f}"
                data_list.append({"name": f, "url": url})
        return data_list

    def add_image_file(self):
        """Open file dialog to import PNG image(s)."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PNG Image(s)",
            "",
            "Image Files (*.png)"
        )
        if file_paths:
            for src_path in file_paths:
                filename = os.path.basename(src_path)
                dest_path = os.path.join(self.icons_dir, filename)
                try:
                    shutil.copy2(src_path, dest_path)
                    print(f"[Onigiri IconChooser] Imported Image: {filename}")
                except Exception as e:
                    print(f"[Onigiri IconChooser] Import Image error: {e}")
            # Refresh the icon list
            payload = {
                "icons": self._get_icon_data_list(),
                "images": self._get_image_data_list(),
                "current": {
                    "icon": self.current_icon,
                    "color": self.current_color
                },
                "mode": "image"
            }
            self.web.eval(f"updateData({json.dumps(payload)})")
