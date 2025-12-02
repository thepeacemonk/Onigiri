import os
import random
from aqt import mw, gui_hooks
from aqt.qt import QDialog, QVBoxLayout, QLabel, QPushButton, Qt, QPixmap, QEvent, QKeyEvent
from PyQt6 import QtCore
from aqt.reviewer import Reviewer
from aqt.utils import showInfo
from .. import config

_focus_dango_enabled = False
_dango_attempted_exit = False
_dialog_is_showing = False
_patched_methods = {}
_event_filter = None



def is_focus_dango_enabled():
    """Check if Focus Dango is currently enabled."""
    global _focus_dango_enabled
    conf = config.get_config()
    achievements_conf = conf.get("achievements", {})
    focus_dango_conf = achievements_conf.get("focusDango", {})
    _focus_dango_enabled = focus_dango_conf.get("enabled", False)
    return _focus_dango_enabled

def set_focus_dango_enabled(enabled):
    """Update the Focus Dango enabled state."""
    global _focus_dango_enabled, _dango_attempted_exit
    _focus_dango_enabled = enabled

    if not enabled:
        _dango_attempted_exit = False
        remove_event_filter()
    else:
        install_event_filter()

def intercept_exit_attempt(command):
    """
    Called by patcher.py to check if an exit should be blocked.
    Returns True to block, False to allow.
    """
    global _dango_attempted_exit, _dialog_is_showing
    

    
    if not is_focus_dango_enabled():

        return False
    
    if _dialog_is_showing:

        return True
        
    if _dango_attempted_exit:
        _dango_attempted_exit = False

        return False
    
    _dango_attempted_exit = True

    return True

def check_and_block_navigation(method_name):
    """
    Check if navigation should be blocked.
    Returns True if blocked, False if allowed.
    """
    global _dango_attempted_exit, _dialog_is_showing
    
    if not is_focus_dango_enabled():
        return False
    
    if not hasattr(mw, 'state') or mw.state != "review":
        return False
    

    
    if _dialog_is_showing:

        return True
    
    if not _dango_attempted_exit:
        _dango_attempted_exit = True

        show_dango_dialog()
        return True
    
    _dango_attempted_exit = False

    return False

class KeyEventFilter(QtCore.QObject):
    """Event filter to catch and log all keyboard events."""
    
    def eventFilter(self, obj, event):
        """Filter keyboard events."""
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            modifiers = event.modifiers()
            

            
            if not is_focus_dango_enabled() or not hasattr(mw, 'state') or mw.state != "review":
                return False
            
            # Check for specific navigation shortcuts
            navigation_keys = {
                Qt.Key.Key_D: 'onDeckBrowser',  # 'd' key
                Qt.Key.Key_B: 'onBrowse',       # 'b' key
                Qt.Key.Key_A: 'onAddCard',      # 'a' key
                Qt.Key.Key_T: 'onStats',        # 't' key
                Qt.Key.Key_O: 'onOverview',     # 'o' key
                Qt.Key.Key_E: 'onEditCurrent',  # 'e' key
                Qt.Key.Key_I: 'onCardInfo',     # 'i' key
            }
            
            # Only block if no modifiers (plain key press)
            if modifiers == Qt.KeyboardModifier.NoModifier and key in navigation_keys:
                method_name = navigation_keys[key]

                
                if check_and_block_navigation(f"shortcut_{method_name}"):

                    event.accept()
                    return True
        
        return False

def install_event_filter():
    """Install the event filter."""
    global _event_filter
    
    if _event_filter is not None:

        return
    
    _event_filter = KeyEventFilter()
    mw.app.installEventFilter(_event_filter)


def remove_event_filter():
    """Remove the event filter."""
    global _event_filter
    
    if _event_filter is None:
        return
    
    mw.app.removeEventFilter(_event_filter)
    _event_filter = None


def show_dango_dialog(on_confirm=None):
    """Show the Focus Dango dialog."""
    global _dango_attempted_exit, _dialog_is_showing

    
    if _dialog_is_showing:

        return
    
    if not is_focus_dango_enabled():

        return 
    
    _dialog_is_showing = True 
    
    conf = config.get_config()
    achievements_conf = conf.get("achievements", {})
    focus_dango_conf = achievements_conf.get("focusDango", {})
    
    dango_defaults = config.DEFAULTS.get("achievements", {}).get("focusDango", {})
    messages_list = focus_dango_conf.get("messages")

    if not messages_list:
        old_message = focus_dango_conf.get("message")
        if isinstance(old_message, str) and old_message:
            messages_list = [line.strip() for line in old_message.splitlines() if line.strip()]
        else:
            messages_list = dango_defaults.get("messages", [])
            if not messages_list:
                old_default_message = dango_defaults.get("message")
                if isinstance(old_default_message, str) and old_default_message:
                    messages_list = [old_default_message]
    
    if not messages_list:
        messages_list = ["Don't give up!", "Stay focused!", "Almost there!"]

    try:
        message = random.choice(messages_list)
    except (IndexError, TypeError):
        message = "Stay focused!"
    
    dialog = QDialog(mw)
    dialog.setObjectName("FocusDangoDialog")
    dialog.setWindowTitle("Focus Dango")
    dialog.setModal(True)
    
    try:
        major_version = int(QtCore.QT_VERSION_STR.split('.')[0])
    except:
        major_version = 5

    if major_version >= 6:
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
    else:
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowStaysOnTopHint)
        
    dialog.setMinimumSize(400, 300)
    
    addon_path = os.path.dirname(os.path.dirname(__file__))
    images_path = os.path.join(addon_path, "system_files", "gamification_images")
    
    bg_filename = "dango_bg_night.png" if mw.pm.night_mode else "dango_bg.png"
    bg_path = os.path.join(images_path, bg_filename)
    
    if os.path.exists(bg_path):
        qss_path = bg_path.replace("\\", "/")
        dialog.setStyleSheet(f"""
            QDialog#FocusDangoDialog {{
                background-image: url('{qss_path}');
                background-repeat: no-repeat;
                background-position: center;
            }}
        """)

    
    layout = QVBoxLayout(dialog)
    layout.setSpacing(20)
    layout.setContentsMargins(30, 30, 30, 30)
    
    dango_path = os.path.join(addon_path, "system_files", "gamification_images", "dango.png")
    
    if os.path.exists(dango_path):
        image_label = QLabel()
        pixmap = QPixmap(dango_path)
        scaled_pixmap = pixmap.scaled(120, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        image_label.setPixmap(scaled_pixmap)
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setStyleSheet("background-color: transparent;")
        layout.addWidget(image_label)

    
    message_label = QLabel(message)
    message_label.setWordWrap(True)
    message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    message_label.setStyleSheet("background-color: transparent; font-size: 14px;")
    layout.addWidget(message_label)
    
    close_button = QPushButton("Click me!")
    
    def on_button_click():
        global _dango_attempted_exit, _dialog_is_showing

        _dango_attempted_exit = False
        _dialog_is_showing = False
        dialog.close()
        if on_confirm:
            on_confirm()
    
    close_button.clicked.connect(on_button_click)
    close_button.setFocus()

    if mw.pm.night_mode:
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #7b464d;
                color: #eee;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:pressed {
                background-color: #A6646C;
            }
        """)
    else:
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #F8E8E8;
                color: #7b464d;
                border: 1px solid #A6646C;
                padding: 8px 16px;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:pressed {
                background-color: #F0DCDC;
            }
        """)

    layout.addWidget(close_button)
    
    mw._focus_dango_dialog = dialog
    

    dialog.show()
    dialog.raise_()
    dialog.activateWindow()


def create_blocking_wrapper(original_method, method_name):
    """Create a wrapper that blocks navigation when Focus Dango is enabled."""
    def wrapper(*args, **kwargs):
        if check_and_block_navigation(method_name):

            return None
        return original_method(*args, **kwargs)
    return wrapper

def setup_focus_dango():
    """Initialize Focus Dango by patching navigation methods and installing event filter."""

    
    conf = config.get_config()
    achievements_conf = conf.get("achievements", {})
    focus_dango_conf = achievements_conf.get("focusDango", {})
    enabled = focus_dango_conf.get("enabled", False)
    set_focus_dango_enabled(enabled)
    
    # Patch all navigation methods as backup
    navigation_methods = [
        'onDeckBrowser',
        'onOverview',
        'onStats',
        'onBrowse',
        'onAddCard',
        'onEditCurrent',
        'onCardInfo',
    ]
    
    for method_name in navigation_methods:
        if hasattr(mw, method_name):
            original = getattr(mw, method_name)
            _patched_methods[method_name] = original
            setattr(mw, method_name, create_blocking_wrapper(original, method_name))

    