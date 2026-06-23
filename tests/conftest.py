"""
Test bootstrap that lets pure Onigiri logic be imported and unit-tested
*without* a running Anki (no `aqt`, no Qt, no display).

The only thing that stops `special_days.py` from importing outside Anki is its
module-level `from aqt import mw` plus its relative imports of sibling modules
that do the same. We don't need any of that machinery to exercise the engine's
pure logic (date math, occasion detection, guards, payload merging), so here we:

  1. stub the one Anki symbol it imports at load time (`aqt.mw`);
  2. register `onigiri` as a package *without* running its heavy __init__.py; and
  3. fake the sibling modules it imports, so `special_days` loads in isolation.

This is the reusable "Tier 1" harness: any future pure-logic module can be
tested the same way. Anything that genuinely needs the collection (revlog
queries) or the GUI belongs in a separate Tier 2/Tier 3 suite, not here.
"""

import os
import sys
import types
from unittest.mock import MagicMock

# 1. Stub the single Anki symbol special_days imports at module load time.
#    A MagicMock tolerates any attribute/call chain (mw.col.db.scalar(...)),
#    which is all we need for *import* to succeed.
_aqt = types.ModuleType("aqt")
_aqt.mw = MagicMock()
sys.modules.setdefault("aqt", _aqt)

# 2. Register `onigiri` as a package pointing at the repo dir, but DON'T execute
#    the real (heavy, Anki-coupled) __init__.py. Because the name is now present
#    in sys.modules, `import onigiri.special_days` finds special_days.py via this
#    __path__ and never re-imports the package init.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_pkg = types.ModuleType("onigiri")
_pkg.__path__ = [_REPO]
sys.modules["onigiri"] = _pkg


def _fake_module(name, **attrs):
    """Register a stand-in for one of special_days' sibling modules."""
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[name] = mod
    return mod


# 3. Fake the siblings special_days imports. These are faithful to the call
#    signatures special_days uses, but do nothing (or echo a default) — the
#    pure logic under test never depends on their real behaviour.
_fake_module("onigiri.config", get_config=lambda: {}, write_config=lambda conf: None)
_fake_module("onigiri.translations", tr=lambda key, default="", *a, **k: default)
_fake_module("onigiri.onigiri_notifications", notify=lambda *a, **k: None)
_fake_module("onigiri.birthday_dialog", show_birthday_dialog=lambda *a, **k: None)
