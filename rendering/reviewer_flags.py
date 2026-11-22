"""Resolve Onigiri reviewer flag glyphs without changing Anki's card flags."""

import json
from pathlib import Path
from urllib.parse import quote


def icon_urls(conf, addon_root, package):
    """Every flag uses Onigiri's bundled glyph unless a valid choice exists."""
    root = Path(addon_root)
    choices = conf.get("onigiri_reviewer_flag_icons", {})
    if not isinstance(choices, dict):
        choices = {}
    urls = {}
    default = root / "system_files/system_icons/available_for_users/flag.svg"
    default_url = (
        f"/_addons/{quote(str(package), safe='')}/"
        "system_files/system_icons/available_for_users/flag.svg"
    )
    if default.is_file():
        default_url += f"?v={default.stat().st_mtime_ns}"
    for number in range(1, 8):
        urls[str(number)] = default_url
        value = choices.get(str(number), "")
        if not isinstance(value, str) or not value:
            continue
        system = value.startswith("system:")
        name = value[7:] if system else value
        if Path(name).name != name or "\\" in name:
            continue
        if Path(name).suffix.lower() not in (".svg", ".png"):
            continue
        folders = (
            ("system_files/system_icons/available_for_users",
             "system_files/system_icons/unavailable_for_users",
             "system_files/system_icons") if system else
            ("user_files/icons", "user_files/custom_deck_icons")
        )
        for folder in folders:
            path = root / folder / name
            if path.is_file():
                urls[str(number)] = (
                    f"/_addons/{quote(str(package), safe='')}/{folder}/"
                    f"{quote(name, safe='')}?v={path.stat().st_mtime_ns}"
                )
                break
    return urls


def settings_script(conf, addon_root, package):
    payload = json.dumps(icon_urls(conf, addon_root, package)).replace("</", "<\\/")
    return (
        f"window.onigiriReviewerFlagIcons={payload};"
        "if(window.OnigiriReviewerFlags){"
        "window.OnigiriReviewerFlags.setIcons(window.onigiriReviewerFlagIcons);}"
    )


def refresh(conf):
    """Apply a settings edit to the current card without showing it again."""
    from aqt import mw

    if not mw or mw.state != "review" or not getattr(mw, "reviewer", None):
        return
    root = Path(__file__).resolve().parents[1]
    package = mw.addonManager.addonFromModule(__name__)
    mw.reviewer.web.eval(settings_script(conf, root, package))
