"""Shared, data-preserving visibility rules for Study Tools."""

TOOL_IDS = ("prep_station", "hashi_notes", "pomodoro")


def tool_visible(tool_id, conf=None):
    if conf is None:
        from . import config

        conf = config.get_config_readonly()
    visibility = conf.get("study_tools_visibility", {})
    if not isinstance(visibility, dict):
        visibility = {}
    return visibility.get(tool_id, True) is not False


def reviewer_button_visible(tool_id, conf=None):
    if conf is None:
        from . import config

        conf = config.get_config_readonly()
    if not tool_visible(tool_id, conf):
        return False
    if tool_id == "hashi_notes":
        return (conf.get("hashi_notes", {}) or {}).get("show_in_reviewer_header", True)
    if tool_id == "pomodoro":
        return conf.get("onigiri_pomodoro_show_in_reviewer_header", True)
    return False


def hide_open_tools(conf):
    """Close only loaded hidden tools; flush notes and pause an active timer."""
    import sys

    package = __package__.rsplit(".", 1)[0]
    windows = {
        "prep_station": ("_dialog",),
        "hashi_notes": ("_popup", "_gallery"),
        "pomodoro": ("_widget", "_stats_dialog"),
    }
    for tool_id, attributes in windows.items():
        if tool_visible(tool_id, conf):
            continue
        module = sys.modules.get(f"{package}.study_tools.{tool_id}")
        if module is None:
            continue
        if tool_id == "pomodoro":
            timer = getattr(module, "_timer", None)
            if timer is not None:
                timer.pause()
        for attribute in attributes:
            window = getattr(module, attribute, None)
            if window is not None:
                window.close()
