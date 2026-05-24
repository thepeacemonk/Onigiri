from .color_utils import normalize_color_string, parse_color_string


PROFILE_BG_MODE_ACCENT = "accent"
PROFILE_BG_MODE_CUSTOM = "custom"
PROFILE_BG_MODE_GRADIENT = "gradient"
PROFILE_BG_MODE_IMAGE = "image"

PROFILE_BG_SOLID_LIGHT_KEY = "modern_menu_profile_bg_color_light"
PROFILE_BG_SOLID_DARK_KEY = "modern_menu_profile_bg_color_dark"
PROFILE_BG_GRADIENT_LIGHT_START_KEY = "modern_menu_profile_bg_gradient_light_start"
PROFILE_BG_GRADIENT_LIGHT_END_KEY = "modern_menu_profile_bg_gradient_light_end"
PROFILE_BG_GRADIENT_DARK_START_KEY = "modern_menu_profile_bg_gradient_dark_start"
PROFILE_BG_GRADIENT_DARK_END_KEY = "modern_menu_profile_bg_gradient_dark_end"

PROFILE_BG_SOLID_DEFAULTS = {
    "light": "#EEEEEE",
    "dark": "#3C3C3C",
}

PROFILE_BG_GRADIENT_DEFAULTS = {
    "light_start": "#EEEEEE",
    "light_end": "#DADDE3",
    "dark_start": "#3C3C3C",
    "dark_end": "#2F343A",
}

PROFILE_BG_GRADIENT_KEYS = {
    "light_start": PROFILE_BG_GRADIENT_LIGHT_START_KEY,
    "light_end": PROFILE_BG_GRADIENT_LIGHT_END_KEY,
    "dark_start": PROFILE_BG_GRADIENT_DARK_START_KEY,
    "dark_end": PROFILE_BG_GRADIENT_DARK_END_KEY,
}


def normalize_profile_gradient_color(value, role):
    default = PROFILE_BG_GRADIENT_DEFAULTS[role]
    return normalize_color_string(value, fallback=default) or default


def get_profile_bg_gradient_colors(conf):
    conf = conf or {}
    return {
        role: normalize_profile_gradient_color(conf.get(key, PROFILE_BG_GRADIENT_DEFAULTS[role]), role)
        for role, key in PROFILE_BG_GRADIENT_KEYS.items()
    }


def get_profile_bg_gradient_pair(conf, is_dark):
    colors = get_profile_bg_gradient_colors(conf)
    prefix = "dark" if is_dark else "light"
    return colors[f"{prefix}_start"], colors[f"{prefix}_end"]


def get_profile_bg_gradient_style():
    return (
        "background-image: linear-gradient(to right, "
        f"var(--profile-bg-gradient-start, {PROFILE_BG_GRADIENT_DEFAULTS['light_start']}), "
        f"var(--profile-bg-gradient-end, {PROFILE_BG_GRADIENT_DEFAULTS['light_end']}));"
    )


def get_gradient_midpoint_color(start, end, fallback="#555555"):
    start_color = parse_color_string(start, fallback=fallback)
    end_color = parse_color_string(end, fallback=fallback)
    if not start_color.isValid() or not end_color.isValid():
        return parse_color_string(fallback, fallback="#555555")

    return parse_color_string(
        "#{:02X}{:02X}{:02X}".format(
            round((start_color.red() + end_color.red()) / 2),
            round((start_color.green() + end_color.green()) / 2),
            round((start_color.blue() + end_color.blue()) / 2),
        ),
        fallback=fallback,
    )
