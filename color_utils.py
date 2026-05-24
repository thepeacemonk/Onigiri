import re

from aqt.qt import QColor


HEX_COLOR_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
RGB_COLOR_RE = re.compile(r"^rgba?\((.+)\)$", re.IGNORECASE)


def _clamp_byte(value):
    return max(0, min(int(round(value)), 255))


def _parse_rgb_channel(value):
    text = str(value).strip()
    if not text:
        raise ValueError("Empty RGB channel")
    if text.endswith("%"):
        return _clamp_byte(float(text[:-1]) * 255.0 / 100.0)
    return _clamp_byte(float(text))


def _parse_alpha_channel(value):
    text = str(value).strip()
    if not text:
        raise ValueError("Empty alpha channel")
    if text.endswith("%"):
        return _clamp_byte(float(text[:-1]) * 255.0 / 100.0)

    alpha = float(text)
    if alpha <= 1.0:
        return _clamp_byte(alpha * 255.0)
    return _clamp_byte(alpha)


def qcolor_to_hex(color):
    qcolor = QColor(color)
    if not qcolor.isValid():
        return None

    base = f"#{qcolor.red():02X}{qcolor.green():02X}{qcolor.blue():02X}"
    if qcolor.alpha() < 255:
        return f"{base}{qcolor.alpha():02X}"
    return base


def qcolor_to_rgba_css(color):
    qcolor = QColor(color)
    if not qcolor.isValid():
        return None

    alpha = qcolor.alpha() / 255.0
    alpha_text = f"{alpha:.3f}".rstrip("0").rstrip(".")
    if not alpha_text:
        alpha_text = "0"
    return f"rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()}, {alpha_text})"


def parse_color_string(value, fallback=None):
    if isinstance(value, QColor):
        qcolor = QColor(value)
        if qcolor.isValid():
            return qcolor

    text = "" if value is None else str(value).strip()
    if not text:
        return QColor(fallback) if fallback is not None else QColor()

    hex_match = HEX_COLOR_RE.match(text)
    if hex_match:
        digits = hex_match.group(1)
        if len(digits) == 3:
            digits = "".join(ch * 2 for ch in digits)
            return QColor(int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))
        if len(digits) == 4:
            digits = "".join(ch * 2 for ch in digits)
            return QColor(
                int(digits[0:2], 16),
                int(digits[2:4], 16),
                int(digits[4:6], 16),
                int(digits[6:8], 16),
            )
        if len(digits) == 6:
            return QColor(int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))
        return QColor(
            int(digits[0:2], 16),
            int(digits[2:4], 16),
            int(digits[4:6], 16),
            int(digits[6:8], 16),
        )

    rgb_match = RGB_COLOR_RE.match(text)
    if rgb_match:
        parts = [part.strip() for part in rgb_match.group(1).split(",")]
        if len(parts) in (3, 4):
            try:
                red = _parse_rgb_channel(parts[0])
                green = _parse_rgb_channel(parts[1])
                blue = _parse_rgb_channel(parts[2])
                alpha = _parse_alpha_channel(parts[3]) if len(parts) == 4 else 255
                return QColor(red, green, blue, alpha)
            except (TypeError, ValueError):
                pass

    qcolor = QColor(text)
    if qcolor.isValid():
        return qcolor

    return QColor(fallback) if fallback is not None else QColor()


def normalize_color_string(value, fallback=None, allow_empty=False):
    text = "" if value is None else str(value).strip()
    if not text:
        if allow_empty:
            return ""
        if fallback is None:
            return None
        return normalize_color_string(fallback, allow_empty=False)

    qcolor = parse_color_string(text)
    if qcolor.isValid():
        return qcolor_to_hex(qcolor)

    if fallback is None:
        return None

    fallback_color = parse_color_string(fallback)
    return qcolor_to_hex(fallback_color) if fallback_color.isValid() else None


def get_contrast_text_color(hex_color):
    """Returns #ffffff or #000000 for maximum contrast against the given background color.
    Uses WCAG relative luminance (threshold ~0.179) to pick the most readable text color.
    Accepts hex string (#RRGGBB or #RGB) or QColor."""
    try:
        if isinstance(hex_color, QColor):
            if not hex_color.isValid():
                return "#ffffff"
            r, g, b = hex_color.red() / 255.0, hex_color.green() / 255.0, hex_color.blue() / 255.0
        else:
            h = str(hex_color or "").strip().lstrip('#')
            if len(h) == 3:
                h = h[0] * 2 + h[1] * 2 + h[2] * 2
            if len(h) != 6:
                return "#ffffff"
            r, g, b = (int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))

        def _lin(c):
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        lum = 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)
        return "#000000" if lum > 0.179 else "#ffffff"
    except Exception:
        return "#ffffff"
