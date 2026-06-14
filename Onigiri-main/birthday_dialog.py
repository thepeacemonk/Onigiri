import os
from datetime import datetime
from aqt import mw
from aqt.qt import QDialog, QVBoxLayout, Qt, QPoint, QUrl, QPixmap
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
from aqt.webview import AnkiWebView
from aqt.theme import theme_manager
from . import config


class BirthdayDialog(QDialog):
    """
    A festive pop-up dialog that wishes the user a happy birthday
    with confetti animation and displays their age.
    """

    def __init__(self, user_name: str, user_age: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎂 Happy Birthday!")
        
        # Make the dialog frameless and transparent
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        if parent:
            self.resize(parent.width(), parent.height())
            self.move(parent.mapToGlobal(QPoint(0,0)))
        else:
            self.resize(800, 600)
            
        # Birthday Icon (keep this)
        icon_data = ""
        icon_path = os.path.join(os.path.dirname(__file__), "system_files", "gamification_images", "birthday.png")
        if os.path.exists(icon_path):
            icon_pixmap = QPixmap(icon_path)
            if not icon_pixmap.isNull():
                icon_data = self._pixmap_to_base64(icon_pixmap)
            
        self.setModal(True)

        # Main layout
        vbox = QVBoxLayout()
        vbox.setContentsMargins(0, 0, 0, 0)
        self.setLayout(vbox)

        # Webview for the content
        self.web = AnkiWebView(self)
        self.web.setStyleSheet("background: transparent;")
        self.web.page().setBackgroundColor(Qt.GlobalColor.transparent)
        
        vbox.addWidget(self.web)

        # Content Setup
        html_path = os.path.join(os.path.dirname(__file__), "web", "birthday.html")
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
        except FileNotFoundError:
            html_content = self._get_fallback_html()

        # Get Theme Colors
        conf = config.get_config()
        is_night_mode = theme_manager.night_mode
        mode_key = "dark" if is_night_mode else "light"
        
        # Default colors
        accent_color = "#007aff"
        bg_card = "#ffffff"
        text_color = "#333333"
        
        # Try to fetch from config
        if "colors" in conf and mode_key in conf["colors"]:
            colors = conf["colors"][mode_key]
            accent_color = colors.get("--accent-color", accent_color)
            if is_night_mode:
                bg_card = colors.get("--profile-card-bg", "#2c2c2c")
                text_color = "#e0e0e0"
            else:
                bg_card = "#ffffff"
                text_color = "#333333"

        # Replace placeholders
        html_content = html_content.replace("%%USER_NAME%%", user_name)
        html_content = html_content.replace("%%USER_AGE%%", str(user_age))
        html_content = html_content.replace("%%ACCENT_COLOR%%", accent_color)
        html_content = html_content.replace("%%BG_CARD%%", bg_card)
        html_content = html_content.replace("%%TEXT_COLOR%%", text_color)
        html_content = html_content.replace("%%IS_DARK%%", "true" if is_night_mode else "false")
        
        # Inject images
        html_content = html_content.replace("%%ICON_DATA%%", f"data:image/png;base64,{icon_data}")

        self.web.stdHtml(html_content)
        
        # Bridge for the close button
        self.web.set_bridge_command(self._on_bridge_cmd, self)
        
    def _pixmap_to_base64(self, pixmap: QPixmap) -> str:
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buf, "PNG")
        return ba.toBase64().data().decode()

    def _on_bridge_cmd(self, cmd: str):
        if cmd == "close_dialog":
            self.accept()
            
    # Allow closing by clicking outside (optional, but handled better in HTML overlay)
    # or Escape key (handled by QDialog automatically)

    def _get_fallback_html(self) -> str:
        """Returns a simple fallback HTML if the template file is not found."""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: white;
                    text-align: center;
                }
                .content { padding: 40px; }
                h1 { font-size: 48px; margin-bottom: 20px; }
                p { font-size: 24px; }
            </style>
        </head>
        <body>
            <div class="content">
                <h1>🎂 Happy Birthday!</h1>
                <p>Wishing you an amazing day!</p>
            </div>
        </body>
        </html>
        """


_dialog: BirthdayDialog = None


def calculate_age(birthday_str: str) -> int:
    """
    Calculate age from a birthday string in YYYY-MM-DD format.
    Returns the age the user is turning today.
    """
    try:
        birthday = datetime.strptime(birthday_str, "%Y-%m-%d")
        today = datetime.now()
        age = today.year - birthday.year
        # If birthday hasn't occurred yet this year, subtract 1
        # But since we're only showing this ON their birthday, they ARE turning this age
        return age
    except ValueError:
        return 0


def is_birthday_today(birthday_str: str) -> bool:
    """
    Check if the given birthday (YYYY-MM-DD) matches today's month and day.
    """
    if not birthday_str:
        return False
    try:
        birthday = datetime.strptime(birthday_str, "%Y-%m-%d")
        today = datetime.now()
        return birthday.month == today.month and birthday.day == today.day
    except ValueError:
        return False


def show_birthday_dialog(user_name: str, user_age: int):
    """Creates and shows the birthday dialog."""
    global _dialog
    if _dialog:
        _dialog.close()

    _dialog = BirthdayDialog(user_name, user_age, mw)
    _dialog.show()


def maybe_show_birthday_popup():
    """
    Shows the birthday popup if:
    1. User has set their birthday
    2. Today is the user's birthday
    3. The popup hasn't been shown this year yet
    """
    conf = config.get_config()
    
    birthday_str = conf.get("userBirthday", "")
    if not birthday_str:
        return  # No birthday set
    
    if not is_birthday_today(birthday_str):
        return  # Not the user's birthday
    
    # Check if we already showed the popup this year
    current_year = str(datetime.now().year)
    last_shown = conf.get("lastBirthdayShown", "")
    if last_shown == current_year:
        return  # Already shown this year
    
    # It's the user's birthday and we haven't shown the popup yet!
    user_name = conf.get("userName", "User")
    user_age = calculate_age(birthday_str)
    
    # Update the last shown year
    conf["lastBirthdayShown"] = current_year
    config.write_config(conf)
    
    # Show the popup
    show_birthday_dialog(user_name, user_age)
