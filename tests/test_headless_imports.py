"""Headless import regression test.

Every Onigiri module listed here must be importable WITHOUT a running
Anki instance. This is the foundation for all unit and visual testing:
if a new top-level import breaks headless loading (e.g. importing an
aqt module whose class body needs the Rust backend), this test fails
and the seam pattern (try/except with placeholder, see
webview_handlers.py) must be applied.

Modules are loaded through a stub package so the add-on's Anki-bound
__init__.py is never executed.
"""

import importlib
import os
import sys
import types

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STUB_PACKAGE = "onigiri_under_test"

# Modules that must import cleanly outside Anki.
TARGET_MODULES = [
    "config",
    "constants",
    "themes",
    "translations",
    "heatmap",
    "templates",
    "fonts",
    "emoji_sprites",
    "onigiri_renderer",
    "webview_handlers",
    "sync",
    "gamification",
    "gamification.onigimon",
    "gamification.nook_level",
    "gamification.hexagon_land",
    "gamification.taiyaki_store",
    "patcher",
]


@pytest.fixture(scope="module")
def stub_package():
    pkg = types.ModuleType(STUB_PACKAGE)
    pkg.__path__ = [REPO_ROOT]
    sys.modules[STUB_PACKAGE] = pkg
    yield pkg


@pytest.mark.parametrize("module_name", TARGET_MODULES)
def test_headless_import(module_name, stub_package):
    mod = importlib.import_module(f"{STUB_PACKAGE}.{module_name}")
    assert mod is not None
