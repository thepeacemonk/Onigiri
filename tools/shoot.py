"""Screenshot any Onigiri web screen without launching Anki.

The agent/dev loop:

    python tools/shoot.py deckbrowser --theme dark --out .shots/deck.png

Renders the real Onigiri markup (same code path as the golden tests),
serves the repository over a local HTTP server so the genuine web/
assets load, stubs the pycmd bridge, then screenshots the page with
headless Chromium (Playwright).

Requirements:  pip install -r requirements-dev.txt && playwright install chromium
"""

import argparse
import functools
import http.server
import json
import os
import socket
import sys
import threading

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(REPO_ROOT, "tests")
sys.path.insert(0, TESTS_DIR)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from conftest import STUB_PACKAGE, load_module  # noqa: E402
from fake_anki import make_deck_browser, make_render_mw  # noqa: E402

SCREENS = {
    "deckbrowser": "_render_deckbrowser",
}

# Standalone web pages shown in QDialog webviews (birthday_dialog.py,
# guide_dialog.py, ...). Each entry: (file, placeholder map factory,
# default viewport). Rendered without the deck-browser injection head.
ADDON_PLACEHOLDERS = {"%%ADDON_PACKAGE%%": STUB_PACKAGE}


def _birthday_placeholders(theme):
    if theme == "dark":
        accent, card, text, dark = "#F472B6", "#1F2937", "#F9FAFB", "true"
    else:
        accent, card, text, dark = "#EC4899", "#FFFFFF", "#1F2937", "false"
    logo_path = os.path.join(REPO_ROOT, "onigiri_logo.png")
    if os.path.exists(logo_path):
        import base64

        with open(logo_path, "rb") as f:
            icon = "data:image/png;base64," + base64.b64encode(f.read()).decode()
    else:
        icon = ""
    return {
        "%%ACCENT_COLOR%%": accent,
        "%%BG_CARD%%": card,
        "%%TEXT_COLOR%%": text,
        "%%IS_DARK%%": dark,
        "%%USER_NAME%%": "Kaicho",
        "%%USER_AGE%%": "3",
        "%%ICON_DATA%%": icon,
        **ADDON_PLACEHOLDERS,
    }


WEB_PAGES = {
    "birthday": ("birthday.html", _birthday_placeholders, (480, 640)),
    "guide": ("guide.html", lambda theme: {**ADDON_PLACEHOLDERS}, (720, 900)),
    "credits": ("credits.html", lambda theme: {**ADDON_PLACEHOLDERS}, (640, 720)),
    "donations": ("donations.html", lambda theme: {**ADDON_PLACEHOLDERS}, (640, 780)),
}

HARNESS_TEMPLATE = """<!doctype html>
<html lang="en" class="{theme_class}">
<head>
<meta charset="utf-8">
<title>Onigiri shoot: {screen}</title>
<script>
    // Bridge stub: record every pycmd call instead of talking to Anki.
    window.__pycmd_log = [];
    window.pycmd = function (cmd) {{
        window.__pycmd_log.push(String(cmd));
        return false;
    }};
</script>
{head}
<style>
    /* The real page scrolls inside Anki's webview; give the harness a canvas. */
    html, body {{ margin: 0; min-height: 100vh; }}
</style>
</head>
<body>{body}</body>
</html>
"""


def _safe(fn, *args, **kwargs):
    """Run an injection generator; degrade to empty string on failure."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print(f"[shoot] injector {getattr(fn, '__name__', fn)} failed: {e}")
        return ""


def build_deckbrowser_head(conf):
    """Replicate Onigiri's deck-browser injections from __init__.py.

    Mirrors inject_menu_files()'s is_deck_browser branch so the harness
    loads exactly what a real Anki page would.
    """
    patcher = load_module("patcher")
    translations_mod = load_module("translations")
    heatmap_mod = load_module("heatmap")

    parts = [
        '<link rel="stylesheet" href="/web/menu.css">',
        '<link rel="stylesheet" href="/web/heatmap.css">',
        '<link rel="stylesheet" href="/web/learner_stats.css">',
        '<link rel="stylesheet" href="/web/notifications.css">',
    ]

    for generator, args_ in (
        (patcher.generate_dynamic_css, (conf,)),
        (patcher.generate_box_effect_button_vars_css, (conf,)),
        (patcher.generate_profile_bar_fix_css, ()),
        (patcher.generate_deck_browser_backgrounds, (REPO_ROOT,)),
    ):
        parts.append(_safe(generator, *args_))

    parts.append(_safe(patcher.generate_icon_css, STUB_PACKAGE, conf))
    parts.append(_safe(patcher.generate_conditional_css, conf))
    parts.append(_safe(patcher.generate_icon_size_css))

    # Heatmap runtime data (heatmap.js reads these globals).
    try:
        h_data, h_conf = heatmap_mod.get_heatmap_and_config()
        import json as _json

        parts.append("<script>window.onigiriHeatmapData=" + _json.dumps(h_data) + ";window.onigiriHeatmapConfig=" + _json.dumps(h_conf) + ";</script>")
    except Exception as e:
        print(f"[shoot] heatmap data skipped: {e}")

    for js in (
        "injector.js",
        "engine.js",
        "rename_modal.js",
        "icon_modal.js",
        "rename_dialog.js",
        "move_to_dialog.js",
        "add_subdeck_dialog.js",
        "create_deck_dialog.js",
        "heatmap.js",
        "notifications.js",
    ):
        parts.append(f'<script src="/web/{js}"></script>')

    del translations_mod
    return "\n".join(parts)


def render_deckbrowser(config_overrides, theme):
    """Produce the deck-browser body exactly like the golden tests do."""
    renderer = load_module("onigiri_renderer")
    patcher = load_module("patcher")
    config_mod = load_module("config")
    translations_mod = load_module("translations")
    heatmap_mod = load_module("heatmap")
    tree_updater = load_module("decks.tree_updater")

    mw = make_render_mw()
    overrides = {"onigiriThemeMode": theme, "showWelcomePopup": False}
    if config_overrides:
        overrides.update(config_overrides)
    mw.col.conf.update(overrides)

    for mod in (
        renderer,
        patcher,
        config_mod,
        translations_mod,
        heatmap_mod,
        tree_updater,
    ):
        mod.mw = mw

    deck_browser = make_deck_browser(mw)
    renderer.render_onigiri_deck_browser(deck_browser)
    if not deck_browser.web.calls:
        raise RuntimeError("renderer produced no page")

    conf = config_mod.get_config()
    conf.update(overrides)
    return deck_browser.web.last_body, conf


def serve_repo():
    """Serve REPO_ROOT on an ephemeral localhost port; return base URL.

    Paths are aliased so the genuine assets resolve without Anki:
      /_addons/<pkg>/... -> repo root   (system_files/, user_files/, web/)
    """
    addon_prefix = f"/_addons/{STUB_PACKAGE}"

    class AliasHandler(http.server.SimpleHTTPRequestHandler):
        def translate_path(self, path):
            if path.startswith(addon_prefix):
                path = path[len(addon_prefix) :] or "/"
            return super().translate_path(path)

    handler = functools.partial(AliasHandler, directory=REPO_ROOT)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return f"http://127.0.0.1:{port}", server


def shoot(url, out_path, viewport):
    from playwright.sync_api import sync_playwright

    width, height = viewport
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        errors = []
        page.on(
            "console",
            lambda msg: errors.append(msg.text) if msg.type == "error" else None,
        )
        page.goto(url)
        page.wait_for_timeout(1200)  # let engine.js settle
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        page.screenshot(path=out_path, full_page=False)
        pycmds = page.evaluate("window.__pycmd_log || []")
        browser.close()
    return errors, pycmds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    all_screens = sorted(list(SCREENS) + list(WEB_PAGES))
    parser.add_argument("screen", choices=all_screens)
    parser.add_argument("--theme", choices=("light", "dark"), default="light")
    parser.add_argument("--viewport", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument(
        "--config",
        default="{}",
        help="JSON dict merged into the collection conf, e.g. '{\"hideDeckCounts\": true}'",
    )
    args = parser.parse_args()

    try:
        config_overrides = json.loads(args.config)
    except json.JSONDecodeError as e:
        sys.exit(f"--config is not valid JSON: {e}")

    entry = WEB_PAGES.get(args.screen)
    default_viewport = entry[2] if entry else (1440, 900)
    viewport_arg = args.viewport or f"{default_viewport[0]}x{default_viewport[1]}"
    width, height = (int(x) for x in viewport_arg.lower().split("x"))
    out_path = args.out or os.path.join(".shots", f"{args.screen}_{args.theme}.png")

    if entry:
        filename, placeholder_fn, _ = entry
        with open(os.path.join(REPO_ROOT, "web", filename), encoding="utf-8") as f:
            html = f.read()
        for key, value in placeholder_fn(args.theme).items():
            html = html.replace(key, value)
        # Stub the bridge before any page script runs.
        stub = (
            "<script>window.__pycmd_log=[];window.pycmd=function(c){"
            "window.__pycmd_log.push(String(c));return false;};</script>"
        )
        html = html.replace("<head>", "<head>" + stub, 1)
    else:
        body, conf = render_deckbrowser(config_overrides, args.theme)
        head = build_deckbrowser_head(conf)
        theme_class = "night-mode" if args.theme == "dark" else ""
        html = HARNESS_TEMPLATE.format(
            screen=args.screen, theme_class=theme_class, body=body, head=head
        )

    build_path = os.path.join(".shots", "_harness", f"{args.screen}.html")
    os.makedirs(os.path.dirname(build_path), exist_ok=True)
    with open(build_path, "w", encoding="utf-8") as f:
        f.write(html)

    base_url, server = serve_repo()
    try:
        errors, pycmds = shoot(f"{base_url}/{build_path}", out_path, (width, height))
    finally:
        server.shutdown()

    print(f"shot  -> {out_path}")
    if pycmds:
        print(f"pycmd -> {pycmds}")
    for err in errors[:10]:
        print(f"console error: {err}")


if __name__ == "__main__":
    main()
