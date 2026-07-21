from ._flow_layout import FlowLayout

__all__ = ["FlowLayout", "SettingsDialog", "open_settings"]


def __getattr__(name):
    if name in {"SettingsDialog", "open_settings"}:
        from . import _legacy

        value = getattr(_legacy, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
