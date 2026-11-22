"""Application-wide hold shortcut for Onigiri settings."""

from aqt import mw
from aqt.qt import QEvent, QObject, Qt, QTimer


class SettingsHoldShortcut(QObject):
    def __init__(self, parent):
        super().__init__(parent)
        self._held = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self._open_settings)

    def _cancel(self):
        self._held = False
        self._timer.stop()

    def _open_settings(self):
        if self._held and mw.col is not None:
            from ..api.bento import open_settings

            open_settings()

    def eventFilter(self, watched, event):
        kind = event.type()
        if kind == QEvent.Type.ApplicationDeactivate:
            self._cancel()
        elif kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            # Qt emits synthetic releases/presses while a key repeats.
            if event.isAutoRepeat():
                return False
            key = event.key()
            if kind == QEvent.Type.KeyRelease:
                if key in (Qt.Key.Key_S, Qt.Key.Key_Shift):
                    self._cancel()
            elif key == Qt.Key.Key_S and event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                if not self._held:
                    self._held = True
                    self._timer.start()
            elif key != Qt.Key.Key_Shift:
                self._cancel()
        return False


def install_settings_shortcut():
    """Keep one filter alive for the lifetime of the Anki main window."""
    if getattr(mw, "_onigiri_settings_hold_shortcut", None) is None:
        shortcut = SettingsHoldShortcut(mw)
        mw.app.installEventFilter(shortcut)
        mw._onigiri_settings_hold_shortcut = shortcut
