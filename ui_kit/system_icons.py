"""Catalog of bundled icons offered by the icon pickers."""

import os


# Retain these assets at their existing paths for feature defaults and saved icons.
_RESERVED_ICONS = frozenset({
    "lucide-calendar-check.svg",
    "lucide-droplet.svg",
    "lucide-flame.svg",
    "lucide-inbox.svg",
    "lucide-moon.svg",
    "lucide-sunrise.svg",
    "moon.svg",
    "onigiri.svg",
    "pomodoro.svg",
    "stats-widget-pace.svg",
    "stats-widget-retention.svg",
    "stats-widget-studied.svg",
    "stats-widget-time.svg",
})


def pickable_system_icons(directory):
    """List the selectable SVG filenames in the public icon directory."""
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    return sorted(
        name for name in names
        if name.lower().endswith(".svg")
        and name.lower() not in _RESERVED_ICONS
        and os.path.isfile(os.path.join(directory, name))
    )
