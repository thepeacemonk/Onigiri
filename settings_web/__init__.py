# Editable WebUI settings surface.
#
# Pages are declared in schema.py, persisted through store.py, rendered by
# web/settings.{html,css,js}, and hosted by dialog.py.

__all__ = ["open_settings", "SettingsWebDialog"]


def open_settings(initial_page=0, parent=None, addon_path=None):
    from .dialog import open_settings as _open

    return _open(initial_page, parent=parent, addon_path=addon_path)


def __getattr__(name):
    if name == "SettingsWebDialog":
        from .dialog import SettingsWebDialog

        return SettingsWebDialog
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
