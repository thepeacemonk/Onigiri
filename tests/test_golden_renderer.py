"""Golden-file snapshots of onigiri_renderer output.

Renders the full Onigiri deck-browser page headlessly (fake collection,
recording webview) and compares the produced HTML against committed
golden files in tests/golden/.

Volatile content (cache-busting query strings, absolute paths) is
normalized before comparison - see _normalize().

Regenerate goldens intentionally after a deliberate HTML change:

    pytest tests/test_golden_renderer.py --regen-golden

then review the diff before committing.
"""

import os
import re

import pytest

from conftest import load_module
from fake_anki import make_deck_browser, make_render_mw

GOLDEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden")


def _normalize(html: str) -> str:
    """Strip volatile bits so goldens only capture structural output."""
    html = re.sub(r"\?v=\d+", "?v=NORM", html)
    html = re.sub(r"onigiri_under_test", "ADDON_PKG", html)
    # Normalize Windows/POSIX path separators inside src/href attributes.
    html = html.replace("\\\\", "/").replace("\\", "/")
    return html


def _render_page(config_overrides=None):
    """Render the deck browser with the given config overrides."""
    renderer = load_module("onigiri_renderer")
    patcher = load_module("patcher")
    config_mod = load_module("config")
    translations_mod = load_module("translations")
    heatmap_mod = load_module("heatmap")
    tree_updater = load_module("decks.tree_updater")

    mw = make_render_mw()
    if config_overrides:
        mw.col.conf.update(config_overrides)

    for mod in (renderer, patcher, config_mod, translations_mod, heatmap_mod, tree_updater):
        mod.mw = mw

    deck_browser = make_deck_browser(mw)
    renderer.render_onigiri_deck_browser(deck_browser)
    assert deck_browser.web.calls, "renderer did not emit any page"
    return _normalize(deck_browser.web.last_body)


def _golden_path(name):
    return os.path.join(GOLDEN_DIR, f"{name}.html")


def _assert_matches_golden(name: str, actual: str, request):
    path = _golden_path(name)
    regen = request.config.getoption("--regen-golden") or not os.path.exists(path)

    if regen:
        os.makedirs(GOLDEN_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(actual)
        pytest.fail(f"Golden '{name}' written. Re-run to compare, and review the diff before committing intentional changes.")

    with open(path, encoding="utf-8") as f:
        expected = f.read()

    import difflib

    if actual != expected:
        diff = "\n".join(
            list(
                difflib.unified_diff(
                    expected.splitlines(),
                    actual.splitlines(),
                    fromfile=f"golden/{name}",
                    tofile="actual",
                    lineterm="",
                )
            )[:80]
        )
        pytest.fail(f"Renderer output drifted from golden '{name}':\n{diff}")


def test_golden_deck_browser_default_grid(request):
    """Default layout: stats title, studied/time/pace/retention, heatmap."""
    _assert_matches_golden("deckbrowser_default", _render_page(), request)


def test_golden_deck_browser_dark_theme(request):
    """Theme mode forced dark; layout unchanged."""
    _assert_matches_golden(
        "deckbrowser_dark",
        _render_page({"onigiriThemeMode": "dark"}),
        request,
    )
