import os
import random
from aqt import mw, gui_hooks
from aqt.qt import QDialog, QVBoxLayout, QLabel, QPushButton, Qt, QPixmap, QEvent, QHBoxLayout, QLineEdit, QWidget
from PyQt6 import QtCore
from aqt.reviewer import Reviewer
from .. import config

_focus_dango_enabled = False
_dialog_is_showing = False
_patched_methods = {}
_event_filter = None
_navigation_is_suspended = False
_exit_attempt_count = 0
_LIGHT_MODE_ATTEMPTS_TO_UNLOCK = 3
_DEFAULT_UNLOCK_PIN = "000000"


class PinDigitBoxes(QWidget):
    unlockRequested = QtCore.pyqtSignal()

    def __init__(self, value="", object_name="FocusDangoPinBox", parent=None):
        super().__init__(parent)
        self._boxes = []
        self._object_name = object_name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        digits = "".join(ch for ch in str(value or "") if ch.isdigit())[:6]
        digits = digits.ljust(6)

        for index in range(6):
            box = QLineEdit(digits[index].strip())
            box.setObjectName(object_name)
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.setMaxLength(1)
            box.setFixedSize(38, 44)
            box.textEdited.connect(lambda text, i=index: self._handle_text_edited(i, text))
            layout.addWidget(box)
            self._boxes.append(box)

    def _handle_text_edited(self, index, text):
        digits = "".join(ch for ch in text if ch.isdigit())
        if len(digits) > 1:
            self.set_pin(digits)
            focus_index = min(len(digits), 5)
            self._boxes[focus_index].setFocus()
            if len(self.pin()) == 6:
                self.unlockRequested.emit()
            return

        box = self._boxes[index]
        if box.text() != digits:
            box.setText(digits)
        if digits and index < 5:
            self._boxes[index + 1].setFocus()
            self._boxes[index + 1].selectAll()
        if len(self.pin()) == 6:
            self.unlockRequested.emit()

    def keyPressEvent(self, event):
        focused = self.focusWidget()
        if focused in self._boxes:
            index = self._boxes.index(focused)
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.unlockRequested.emit()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Backspace and not focused.text() and index > 0:
                previous = self._boxes[index - 1]
                previous.clear()
                previous.setFocus()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Left and index > 0:
                self._boxes[index - 1].setFocus()
                event.accept()
                return
            if event.key() == Qt.Key.Key_Right and index < 5:
                self._boxes[index + 1].setFocus()
                event.accept()
                return
        super().keyPressEvent(event)

    def set_pin(self, value):
        digits = "".join(ch for ch in str(value or "") if ch.isdigit())[:6]
        for index, box in enumerate(self._boxes):
            box.setText(digits[index] if index < len(digits) else "")

    def pin(self):
        return "".join(box.text() for box in self._boxes)

    def select_all(self):
        for box in self._boxes:
            box.selectAll()
        if self._boxes:
            self._boxes[0].setFocus()

    def clear(self):
        for box in self._boxes:
            box.clear()
        if self._boxes:
            self._boxes[0].setFocus()

    def focus_first_empty(self):
        for box in self._boxes:
            if not box.text():
                box.setFocus()
                return
        if self._boxes:
            self._boxes[-1].setFocus()


def _focus_dango_config():
    conf = config.get_config()
    achievements_conf = conf.get("achievements", {})
    focus_dango_conf = achievements_conf.get("focusDango", {})
    if not isinstance(focus_dango_conf, dict):
        focus_dango_conf = {}
    return focus_dango_conf

def is_focus_dango_enabled():
    """Check if Focus Dango is currently enabled."""
    global _focus_dango_enabled
    focus_dango_conf = _focus_dango_config()
    _focus_dango_enabled = focus_dango_conf.get("enabled", False)
    return _focus_dango_enabled

def is_self_sabotage_enabled():
    """Return whether Focus Dango should use the stricter lock-down mode."""
    focus_dango_conf = _focus_dango_config()
    return bool(focus_dango_conf.get("self_sabotage", False))

def unlock_pin():
    """Return the configured six-digit Focus Dango unlock PIN."""
    focus_dango_conf = _focus_dango_config()
    pin = "".join(ch for ch in str(focus_dango_conf.get("unlock_pin", "") or "") if ch.isdigit())
    if len(pin) != 6:
        pin = _DEFAULT_UNLOCK_PIN
    return pin

def set_focus_dango_enabled(enabled):
    """Update the Focus Dango enabled state."""
    global _focus_dango_enabled, _exit_attempt_count
    _focus_dango_enabled = enabled

    if enabled:
        install_event_filter()
    else:
        _exit_attempt_count = 0
        remove_event_filter()

def _should_allow_light_mode_exit():
    global _exit_attempt_count
    _exit_attempt_count += 1
    if _exit_attempt_count >= _LIGHT_MODE_ATTEMPTS_TO_UNLOCK:
        _exit_attempt_count = 0
        return True
    return False

def intercept_exit_attempt(command):
    """
    Called by patcher.py to check if an exit should be blocked.
    Returns True to block, False to allow.
    """
    global _dialog_is_showing
    
    if not is_focus_dango_enabled():
        return False

    if not hasattr(mw, 'state') or mw.state != "review":
        return False

    if _navigation_is_suspended:
        return False

    if is_self_sabotage_enabled():
        return True

    return not _should_allow_light_mode_exit()

def check_and_block_navigation(method_name):
    """
    Check if navigation should be blocked.
    Returns True if blocked, False if allowed.
    """
    global _dialog_is_showing
    
    if not is_focus_dango_enabled():
        return False
    
    if not hasattr(mw, 'state') or mw.state != "review":
        return False

    if _navigation_is_suspended:
        return False

    if _dialog_is_showing:
        return True

    if not is_self_sabotage_enabled() and _should_allow_light_mode_exit():
        return False

    show_dango_dialog(method_name)

    return True

class KeyEventFilter(QtCore.QObject):
    """Event filter for navigation shortcuts while Focus Dango is active."""
    
    def eventFilter(self, obj, event):
        """Filter keyboard events."""
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            modifiers = event.modifiers()

            if (
                not is_focus_dango_enabled()
                or not hasattr(mw, 'state')
                or mw.state != "review"
            ):
                return False

            navigation_keys = {
                Qt.Key.Key_D: 'onDeckBrowser',  # 'd' key
                Qt.Key.Key_B: 'onBrowse',       # 'b' key
                Qt.Key.Key_A: 'onAddCard',      # 'a' key
                Qt.Key.Key_T: 'onStats',        # 't' key
                Qt.Key.Key_O: 'onOverview',     # 'o' key
                Qt.Key.Key_E: 'onEditCurrent',  # 'e' key
                Qt.Key.Key_I: 'onCardInfo',     # 'i' key
            }

            command_modifiers = (
                Qt.KeyboardModifier.ControlModifier
                | Qt.KeyboardModifier.MetaModifier
                | Qt.KeyboardModifier.AltModifier
            )
            has_command_modifier = bool(modifiers & command_modifiers)

            strict_mode = is_self_sabotage_enabled()
            should_block_key = (
                strict_mode
                or has_command_modifier
            )

            if should_block_key and key in navigation_keys:
                method_name = navigation_keys[key]

                command = f"shortcut_{method_name}"
                if check_and_block_navigation(command):
                    event.accept()
                    return True
                event.accept()
                QtCore.QTimer.singleShot(0, lambda cmd=command: _run_exit_command(cmd))
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


def _normalized_command(command):
    if isinstance(command, str) and command.startswith("shortcut_"):
        return command[len("shortcut_"):]
    return command


def _exit_button_label(command):
    command = _normalized_command(command)
    labels = {
        "decks": "Exit to Decks",
        "onDeckBrowser": "Exit to Decks",
        "add": "Open Add",
        "onAddCard": "Open Add",
        "browse": "Open Browser",
        "onBrowse": "Open Browser",
        "stats": "Open Stats",
        "onStats": "Open Stats",
        "sync": "Sync Now",
        "overview": "Open Overview",
        "onOverview": "Open Overview",
        "onEditCurrent": "Edit Current Card",
        "onCardInfo": "Open Card Info",
    }
    return labels.get(command, "Leave Focus Dango")


def _run_exit_command(command):
    global _navigation_is_suspended, _exit_attempt_count
    command = _normalized_command(command)
    if not command:
        return

    _navigation_is_suspended = True
    _exit_attempt_count = 0
    try:
        if command in ("decks", "onDeckBrowser"):
            mw.moveToState("deckBrowser")
            return
        if command == "sync":
            mw.onSync()
            return

        method_map = {
            "add": "onAddCard",
            "browse": "onBrowse",
            "stats": "onStats",
            "overview": "onOverview",
            "onAddCard": "onAddCard",
            "onBrowse": "onBrowse",
            "onStats": "onStats",
            "onOverview": "onOverview",
            "onEditCurrent": "onEditCurrent",
            "onCardInfo": "onCardInfo",
        }
        method_name = method_map.get(command)
        if not method_name:
            return
        method = _patched_methods.get(method_name) or getattr(mw, method_name, None)
        if callable(method):
            method()
    finally:
        _navigation_is_suspended = False


def show_dango_dialog(command=None, on_confirm=None):
    """Show the Focus Dango dialog."""
    global _dialog_is_showing

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
    
    strict_mode = is_self_sabotage_enabled()
    dark_mode = bool(getattr(mw.pm, "night_mode", False))
    if dark_mode:
        dialog_bg = "#321722"
        message_color = "#ffd7e6"
        hint_color = "#e7a7bf"
        error_color = "#ffb4c8"
    else:
        dialog_bg = "#fff1f6"
        message_color = "#8f3156"
        hint_color = "#8b5967"
        error_color = "#b4234b"

    dialog = QDialog(mw)
    dialog.setObjectName("FocusDangoDialog")
    dialog.setWindowTitle("Focus Dango")
    dialog.setModal(True)
    dialog.setStyleSheet(f"""
        QDialog#FocusDangoDialog {{
            background-color: {dialog_bg};
        }}
    """)
    
    try:
        major_version = int(QtCore.QT_VERSION_STR.split('.')[0])
    except:
        major_version = 5

    if major_version >= 6:
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
    else:
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowStaysOnTopHint)
        
    dialog.setMinimumSize(420, 300)
    
    addon_path = os.path.dirname(os.path.dirname(__file__))
    layout = QVBoxLayout(dialog)
    layout.setSpacing(16)
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
    message_label.setStyleSheet(f"background-color: transparent; font-size: 15px; font-weight: 600; color: {message_color};")
    layout.addWidget(message_label)

    attempts_left = max(0, _LIGHT_MODE_ATTEMPTS_TO_UNLOCK - _exit_attempt_count)
    hint = (
        "Enter your six-digit PIN to leave Focus Dango."
        if strict_mode
        else f"Focus Dango will let you leave after {_LIGHT_MODE_ATTEMPTS_TO_UNLOCK} attempts. Attempts left: {attempts_left}."
    )
    hint_label = QLabel(hint)
    hint_label.setWordWrap(True)
    hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hint_label.setStyleSheet(f"background-color: transparent; font-size: 12px; color: {hint_color};")
    layout.addWidget(hint_label)

    pin_input = None
    pin_error_label = None
    if strict_mode:
        pin_input = PinDigitBoxes(object_name="FocusDangoPinInput")
        pin_input.setStyleSheet(f"""
            QLineEdit#FocusDangoPinInput {{
                background-color: {"#4a2232" if dark_mode else "#ffffff"};
                color: {message_color};
                border: 1px solid {"#9c5870" if dark_mode else "#e4a9bd"};
                border-radius: 10px;
                padding: 0px;
                font-size: 20px;
                font-weight: 700;
            }}
            QLineEdit#FocusDangoPinInput:focus {{
                border-color: {"#f0a9c4" if dark_mode else "#9D3D64"};
            }}
        """)
        pin_error_label = QLabel("")
        pin_error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pin_error_label.setStyleSheet(f"background-color: transparent; font-size: 12px; color: {error_color};")
        layout.addWidget(pin_input, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(pin_error_label)
    
    button_row = QHBoxLayout()
    button_row.setSpacing(10)

    close_button = QPushButton("Keep studying")
    
    def on_button_click():
        global _dialog_is_showing

        _dialog_is_showing = False
        dialog.close()
        if on_confirm:
            on_confirm()

    def on_exit_click():
        global _dialog_is_showing

        _dialog_is_showing = False
        dialog.close()
        QtCore.QTimer.singleShot(0, lambda: _run_exit_command(command))

    def on_pin_unlock():
        if pin_input is None:
            return
        typed_pin = pin_input.pin()
        if typed_pin == unlock_pin():
            on_exit_click()
            return
        if pin_error_label is not None:
            pin_error_label.setText("Incorrect PIN.")
        pin_input.clear()
    
    close_button.clicked.connect(on_button_click)
    close_button.setFocus()
    if pin_input is not None:
        pin_input.focus_first_empty()

    exit_button = None
    if command and strict_mode:
        if pin_input is not None:
            pin_input.unlockRequested.connect(on_pin_unlock)
    elif command and not strict_mode and _exit_attempt_count >= _LIGHT_MODE_ATTEMPTS_TO_UNLOCK:
        exit_button = QPushButton(_exit_button_label(command))
        exit_button.clicked.connect(on_exit_click)

    if dark_mode:
        primary_button_style = """
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
        """
        secondary_button_style = """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                color: #f1d6df;
                border: 1px solid rgba(241, 174, 202, 0.35);
                padding: 8px 16px;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.14);
            }
        """
    else:
        primary_button_style = """
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
        """
        secondary_button_style = """
            QPushButton {
                background-color: #fff7fa;
                color: #9D3D64;
                border: 1px solid #E7B8CA;
                padding: 8px 16px;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:pressed {
                background-color: #F6E2EA;
            }
        """

    close_button.setStyleSheet(primary_button_style)
    button_row.addWidget(close_button)
    if exit_button is not None:
        exit_button.setStyleSheet(secondary_button_style)
        button_row.addWidget(exit_button)

    def on_dialog_finished(_result):
        global _dialog_is_showing
        _dialog_is_showing = False

    dialog.finished.connect(on_dialog_finished)
    layout.addLayout(button_row)
    
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

    
    focus_dango_conf = _focus_dango_config()
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
        if method_name in _patched_methods:
            continue
        if hasattr(mw, method_name):
            original = getattr(mw, method_name)
            _patched_methods[method_name] = original
            setattr(mw, method_name, create_blocking_wrapper(original, method_name))

    
