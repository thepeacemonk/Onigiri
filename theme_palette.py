"""Shared, Qt-independent palette completion and heatmap contrast helpers."""

import re


def rgb(color):
    """Read the hex and rgb colors accepted by the theme editor."""
    value = str(color or "").strip().lstrip("#")
    if len(value) in (3, 4):
        value = "".join(char * 2 for char in value[:3])
    if re.fullmatch(r"[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", value):
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    if value.startswith("rgb"):
        parts = re.findall(r"[\d.]+", value)[:3]
        if len(parts) == 3:
            return tuple(max(0, min(255, round(float(v)))) for v in parts)
    return (128, 128, 128)


def mix(first, second, weight):
    channels = [round(a * weight + b * (1 - weight))
                for a, b in zip(rgb(first), rgb(second))]
    return "#" + "".join(f"{c:02x}" for c in channels)


def luminance(color):
    channels = [c / 255 for c in rgb(color)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + .055) / 1.055) ** 2.4
              for c in channels]
    return sum(c * w for c, w in zip(linear, (.2126, .7152, .0722)))


def contrast(first, second):
    a, b = sorted((luminance(first), luminance(second)))
    return (b + .05) / (a + .05)


def readable_text(background):
    return max(("#000000", "#ffffff"), key=lambda c: contrast(c, background))


def visible_color(color, background, minimum=1.7):
    """Keep the hue where possible, moving only enough to meet contrast."""
    if contrast(color, background) >= minimum:
        return color
    target = readable_text(background)
    for step in range(1, 101):
        candidate = mix(target, color, step / 100)
        if contrast(candidate, background) >= minimum:
            return candidate
    return target


def heatmap_zero_color(palette):
    """Return a distinct zero-review cell color for a completed palette.

    A number of bundled themes historically use the card inset for both the
    heatmap surface and level zero. That makes real zero-review cells disappear
    into the widget, even though the Settings preview still draws their grid.
    Keep an intentionally distinct color untouched; otherwise lift it just
    enough toward the palette foreground for the empty-cell pattern to remain
    visible in every themed view.
    """
    inset = palette.get("--canvas-inset", "#2c2c2c")
    zero = palette.get("--heatmap-color-zero", inset)
    return visible_color(zero, inset, minimum=1.7)


def complete_palette(palette, defaults):
    """Expand legacy 13-token themes without retaining the previous theme.

    Explicit tokens from imported themes always take precedence over derived
    colors. Status colors keep distinct hues, softened by the theme accent.
    """
    result = dict(defaults)
    result.update(palette)
    accent = result["--accent-color"]
    bg, inset = result["--bg"], result["--canvas-inset"]
    fg, subtle = result["--fg"], result["--fg-subtle"]
    highlight = result.get("--highlight-bg", inset)
    derived = {
        "--button-primary-bg": accent,
        "--button-primary-gradient-start": mix(accent, inset, .8),
        "--button-primary-gradient-end": accent,
        "--font-small-title-color": fg, "--stats-fg": fg,
        "--highlight-fg": fg, "--profile-page-bg": bg,
        "--profile-card-bg": inset, "--profile-export-btn-bg": highlight,
        "--profile-export-btn-fg": fg,
        "--profile-export-btn-border": result["--border"],
        "--profile-pill-placeholder-bg": highlight,
        "--profile-pic-border": result["--border"],
        "--overlay-close-btn-bg": highlight, "--overlay-close-btn-fg": fg,
        "--deck-hover-bg": highlight, "--deck-dragging-bg": highlight,
        "--deck-edit-mode-bg": inset, "--empty-star-color": subtle,
    }
    for role, seed in (("new", "#3984c6"), ("learn", "#c15d65"),
                       ("review", "#41946b")):
        key = f"--{role}-count-bubble-bg"
        fill = palette.get(key) or mix(mix(seed, accent, .55), inset, .65)
        derived[key] = fill
        derived[f"--{role}-count-bubble-fg"] = readable_text(fill)
    result.update({k: v for k, v in derived.items() if k not in palette})
    return result


def chrome_palette(palette, dark=False):
    """Guide-aligned Settings surfaces with the theme's accent.

    Dashboard palettes belong inside the previews. Settings chrome keeps its
    own light/dark surfaces, text, and borders when a theme is applied.
    """
    if dark:
        result = {
            "outer": "#171717", "panel": "#202020",
            # Field cards and control rows need their own visible depth inside
            # the shell. Keep inset distinct from the card surface so rounded
            # divisions remain visible in dark mode too.
            "surface": "#1d1d1d", "surface_alt": "#202020",
            "inset": "#2a2a2a", "inset_hover": "#303030",
            "hairline": "#45464b", "hairline_soft": "#35363a",
            "fg": "#f1f2f4", "fg_muted": "#b0b3ba",
            "fg_faint": "#8f9299", "shadow": "rgba(0, 0, 0, 0.35)",
            "danger": "#ef6461",
        }
    else:
        # Keep the light defaults in step with web/settings.css and the Guide.
        result = {
            # The canvas deliberately uses the Guide's soft surface rather
            # than the panel white. That separation keeps the rail and page
            # as two floating islands instead of one flat white window.
            "outer": "#f7f7f6", "panel": "#ffffff",
            # White is the island, not its cards. Reuse the Guide's soft
            # surface here so Sync, Languages, and Games retain visible,
            # rounded containers within the content island.
            "surface": "#f7f7f6", "surface_alt": "#f1f1f0",
            # Compact settings controls sit one level below cards: neutral
            # grey tracks restore their individual boxes without borrowing
            # the accent hue. Raised values and selected segments stay white.
            "inset": "#efefee", "inset_hover": "#e5e5e4",
            "hairline": "#e3e4e7", "hairline_soft": "#ededec",
            "fg": "#202124", "fg_muted": "#63666c",
            "fg_faint": "#8f9299", "shadow": "rgba(15, 23, 42, 0.12)",
            "danger": "#d64545",
        }
    result.update({
        "surface_solid": result["surface"], "muted": result["fg_muted"],
        "accent": palette.get("--accent-color") or "#00A982", "dark": dark,
    })
    return result


def utility_chrome_palette(palette, dark=False):
    """Settings chrome under the legacy tokens used by study utilities.

    Keep these aliases together so web editors, native planner dialogs and
    both timer layouts share Settings' surfaces and typography contrast.
    Feature-specific user colors are applied by callers after these defaults.
    """
    result = chrome_palette(palette, dark)
    result.update({
        "bg": result["outer"], "shell": result["panel"],
        "surface2": result["inset"], "hover": result["inset_hover"],
        "border": result["hairline"], "border2": result["hairline"],
        "fg2": result["fg_muted"], "fg3": result["fg_faint"],
        "input_bg": result["surface"], "chip": result["inset"],
    })
    return result
