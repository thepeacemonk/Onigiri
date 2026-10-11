"""Anki Design — tiny colour helpers shared by the web injection
(__init__.py) and the Qt-side palettes (settings.py, addcard.py).

Kept dependency-free so it can be imported from anywhere in the add-on
without touching Anki."""

from typing import Any, Dict, Optional, Tuple


def hex_ok(value: Any) -> str:
    """Return a normalised ``#rrggbb`` string, or ``""`` if `value` isn't a
    usable 6-digit hex colour. Used to sanitise config before it lands in
    CSS / QSS, so a typo can never break a stylesheet."""
    s = str(value or "").strip()
    if not s:
        return ""
    if not s.startswith("#"):
        s = "#" + s
    if len(s) == 4:  # #abc → #aabbcc
        s = "#" + "".join(ch * 2 for ch in s[1:])
    if len(s) != 7:
        return ""
    try:
        int(s[1:], 16)
    except ValueError:
        return ""
    return s.lower()


def _rgb(hex_color: str) -> Tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def mix(a: str, b: str, t: float) -> str:
    """Linear blend of two hex colours, `t` toward `b` (0 → a, 1 → b)."""
    ar, ag, ab = _rgb(a)
    br, bg, bb = _rgb(b)
    t = max(0.0, min(1.0, float(t)))
    r = round(ar + (br - ar) * t)
    g = round(ag + (bg - ag) * t)
    bl = round(ab + (bb - ab) * t)
    return f"#{r:02x}{g:02x}{bl:02x}"


def luminance(hex_color: str) -> float:
    r, g, b = _rgb(hex_color)
    return (r * 299 + g * 587 + b * 114) / 1000.0 / 255.0


def derive_panel(bg: str, dark: bool) -> str:
    """The "panel" tone (today card, embed chrome) for a given page
    background. Panels sit a hair *above* the paper: lighter on dark
    themes, and on light themes lighter too — unless the paper is already
    near-white, where a lighter panel would vanish, so we nudge darker."""
    if dark:
        return mix(bg, "#ffffff", 0.045)
    if luminance(bg) > 0.96:
        return mix(bg, "#000000", 0.025)
    return mix(bg, "#ffffff", 0.5)


def background_override(cfg: Dict[str, Any], dark: bool) -> Optional[Tuple[str, str]]:
    """(paper, panel) from the user's background setting for this theme,
    or None when they're on the default paper."""
    key = "background_dark" if dark else "background_light"
    bg = hex_ok(cfg.get(key))
    if not bg:
        return None
    return bg, derive_panel(bg, dark)


def apply_background(palette: Dict[str, str], cfg: Dict[str, Any],
                     dark: bool) -> Dict[str, str]:
    """Copy of a Qt-side palette dict with paper/panel swapped for the
    user's background override (if any)."""
    ov = background_override(cfg, dark)
    if not ov:
        return palette
    out = dict(palette)
    out["paper"], out["panel"] = ov
    return out


def _rgba(hex_color: str, alpha: float) -> str:
    """Render a validated hex colour as a CSS/QSS rgba() value."""
    r, g, b = _rgb(hex_color)
    return f"rgba({r},{g},{b},{alpha:g})"


def onigiri_layout_config() -> Dict[str, Any]:
    """Return Kome's settings with Onigiri's shared appearance attached.

    Kome is a layout choice within Onigiri, so its dialogs must not consult a
    second add-on configuration or keep an independent accent colour.
    """
    try:
        from .. import config as onigiri_config

        root = onigiri_config.get_config_readonly()
        root = root if isinstance(root, dict) else {}
        nested = root.get("things_theme", {})
        cfg = dict(nested) if isinstance(nested, dict) else {}
        dark = onigiri_config.effective_night_mode(root)
        colors = root.get("colors", {})
        colors = colors if isinstance(colors, dict) else {}
        active = colors.get("dark" if dark else "light", {})
        active = active if isinstance(active, dict) else {}
        cfg["theme"] = root.get("onigiriThemeMode", "system")
        cfg["accent"] = active.get("--accent-color", "#0077c8")
        if str(cfg.get("background_light", "")).lower() == "#f6f3ec":
            cfg["background_light"] = ""
        if str(cfg.get("background_dark", "")).lower() == "#0b0c0f":
            cfg["background_dark"] = ""
        return cfg
    except Exception:
        return {}


def onigiri_palette() -> Tuple[Dict[str, str], bool]:
    """Build Kome's Qt palette from the active Onigiri colour tokens."""
    defaults = {
        "light": {
            "--bg": "#eeeeee", "--canvas-inset": "#ffffff",
            "--fg": "#212121", "--fg-subtle": "#757575",
        },
        "dark": {
            "--bg": "#171717", "--canvas-inset": "#2c2c2c",
            "--fg": "#e0e0e0", "--fg-subtle": "#9e9e9e",
        },
    }
    try:
        from .. import config as onigiri_config

        root = onigiri_config.get_config_readonly()
        root = root if isinstance(root, dict) else {}
        dark = onigiri_config.effective_night_mode(root)
        colors = root.get("colors", {})
        source = (
            colors.get("dark" if dark else "light", {})
            if isinstance(colors, dict)
            else {}
        )
    except Exception:
        dark = True
        source = {}

    mode = "dark" if dark else "light"
    source = source if isinstance(source, dict) else {}
    values = {
        token: hex_ok(source.get(token)) or fallback
        for token, fallback in defaults[mode].items()
    }
    # Kome's base canvas is deliberately fixed to Onigiri's exact light and
    # dark paper values; other shared tokens remain user-configurable.
    paper = "#171717" if dark else "#eeeeee"
    ink = values["--fg"]
    ink_dim = values["--fg-subtle"]
    return {
        "paper": paper,
        "panel": values["--canvas-inset"],
        "ink": ink,
        "ink_dim": ink_dim,
        "ink_faint": mix(ink_dim, paper, 0.45),
        "line": _rgba(ink, 0.10),
        "line2": _rgba(ink, 0.20),
        "hover": _rgba(ink, 0.05),
        "field_bg": values["--canvas-inset"],
    }, dark
