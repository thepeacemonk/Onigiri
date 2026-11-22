"""Stable controls shared by Bento, Sake Nigiri, and beta installations."""
import copy
import base64
import sys
from pathlib import Path
from . import service

_root = None
_context = None
_capture_error = None
_dialog = None
_action = None
_registered = False


def _json_snapshot(value):
    from aqt.qt import QByteArray

    # Anki's profile includes binary window geometry. Keep it recoverable
    # without asking json.dump to serialize bytes or changing the profile.
    if isinstance(value, (bytes, bytearray, QByteArray)):
        return {"__bytes_base64__": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, dict):
        return {key: _json_snapshot(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_snapshot(item) for item in value]
    return copy.deepcopy(value)


def capture_context():
    from aqt import mw
    if mw.col is None:
        raise RuntimeError("Open an Anki profile before switching Onigiri versions")
    export = getattr(mw.col, "all_config", None)
    config = export() if callable(export) else mw.col.conf
    if not isinstance(config, dict):
        raise TypeError("Could not export collection settings; version switch cancelled")
    return {"profile": mw.pm.name, "collection_config": copy.deepcopy(config),
            "profile_config": _json_snapshot(mw.pm.profile),
            "addon_config": copy.deepcopy(mw.addonManager.getConfig(service.PACKAGE))}


def _on_profile_close():
    global _context, _capture_error
    try:
        if service.pending_switch(_root):
            _context = capture_context()
            _capture_error = None
    except Exception as exc:
        _capture_error = exc


def _on_quit():
    """Only switch once Anki has finished every profile save/close callback."""
    try:
        if not service.pending_switch(_root):
            return
        if _capture_error:
            raise _capture_error
        # Current Bento coalesces game/settings writes. Old releases write
        # immediately. Never import Current code into a legacy installation.
        storage = sys.modules.get(__package__.split(".")[0] + ".core.safe_storage")
        if storage is not None and not storage.flush_pending():
            raise RuntimeError("Some Onigiri saves could not be written; switch cancelled")
        service.commit_switch(_root, _context)
    except Exception as exc:
        print("[Onigiri] version switch was not completed: " + str(exc))
        # Persist the failure for the next launch; the active release stays
        # available and the user can cancel/retry through the same controls.
        try:
            pending = service.pending_switch(_root)
            if pending:
                pending["error"] = str(exc)
                service.write_json(service.control_dir(_root) / "pending.json", pending)
        except Exception as save_error:
            print("[Onigiri] could not record switch failure: " + str(save_error))


def open_dialog(parent=None, root=None):
    global _dialog
    from aqt import mw
    from .ui import VersionDialog
    if _dialog is None:
        _dialog = VersionDialog(Path(root or _root), parent or mw)
        _dialog.finished.connect(_release_dialog)
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()
    return _dialog


def _release_dialog(*_args):
    global _dialog
    if _dialog is not None:
        _dialog.deleteLater()
        _dialog = None


def add_menu_action(menu):
    """Keep the same entry point in every release's own Onigiri menu."""
    from aqt.qt import QAction
    from .strings import translate
    for action in menu.actions():
        if action.objectName() == "onigiriSelectVersion":
            return action
    action = QAction(translate("menu_label", _root), menu)
    action.setObjectName("onigiriSelectVersion")
    action.triggered.connect(lambda _checked=False: open_dialog())
    before = next((item for item in menu.actions() if item.isSeparator()), None)
    if before is not None:
        menu.insertAction(before, action)
    else:
        menu.addAction(action)
    menu.aboutToShow.connect(lambda: action.setText(translate("menu_label", _root)))
    return action


def _install_controls():
    global _action
    from aqt import mw, gui_hooks
    from aqt.qt import QAction, QTimer
    from .strings import translate
    _action = QAction("Onigiri · " + translate("menu_label", _root), mw)
    _action.triggered.connect(lambda _checked=False: open_dialog())
    mw.form.menuTools.addAction(_action)
    mw.form.menuTools.aboutToShow.connect(
        lambda: _action.setText("Onigiri · " + translate("menu_label", _root)))
    # Register last, after this release's own profile-save hooks.
    gui_hooks.profile_will_close.append(_on_profile_close)

    def show_failed_switch():
        try:
            pending = service.pending_switch(_root)
            if pending and pending.get("error"):
                QTimer.singleShot(0, open_dialog)
        except Exception as exc:
            print("[Onigiri] could not read the prepared version switch: " + str(exc))

    gui_hooks.profile_did_open.append(show_failed_switch)


def setup(entry_file):
    global _root, _registered
    if _registered:
        return
    _root = Path(entry_file).resolve().parent
    from aqt import gui_hooks
    from aqt.qt import QCoreApplication
    gui_hooks.main_window_did_init.append(_install_controls)
    QCoreApplication.instance().aboutToQuit.connect(_on_quit)
    _registered = True
