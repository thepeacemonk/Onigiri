"""Shared test fixtures for testing Onigiri outside Anki.

Modules are loaded through a stub package ("onigiri_under_test") so the
add-on's Anki-bound __init__.py never executes. Because Onigiri modules
bind ``mw`` at import time (``from aqt import mw`` -> None headlessly),
tests inject fakes by assigning to the module global::

    mod = load_module("heatmap")
    mod.mw = fake_mw

The fakes model only the surface Onigiri actually touches:
mw.col.db (sqlite-backed), mw.col.conf, mw.col.sched, mw.pm,
mw.addonManager.
"""

import os
import sqlite3
import sys
import time
import types
from datetime import datetime, timedelta

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STUB_PACKAGE = "onigiri_under_test"


@pytest.fixture(scope="session")
def stub_package():
    pkg = types.ModuleType(STUB_PACKAGE)
    pkg.__path__ = [REPO_ROOT]
    sys.modules[STUB_PACKAGE] = pkg
    return pkg


def load_module(module_name):
    """Import (or fetch cached) an Onigiri submodule under the stub package."""
    import importlib

    if STUB_PACKAGE not in sys.modules:
        pkg = types.ModuleType(STUB_PACKAGE)
        pkg.__path__ = [REPO_ROOT]
        sys.modules[STUB_PACKAGE] = pkg
    return importlib.import_module(f"{STUB_PACKAGE}.{module_name}")


class FakeDb:
    """Anki-like db facade over a real in-memory SQLite database."""

    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript(
            """
            CREATE TABLE revlog (
                id INTEGER PRIMARY KEY,   -- epoch ms of the review
                cid INTEGER,
                type INTEGER              -- 0..3 real reviews, 4 manual
            );
            CREATE TABLE cards (
                id INTEGER PRIMARY KEY,
                queue INTEGER,
                due INTEGER               -- relative day number
            );
            """
        )
        self.conn.commit()

    def execute(self, query, args=()):
        return self.conn.execute(query, args)

    def all(self, query, *args):
        return self.execute(query, args).fetchall()

    def list(self, query, *args):
        return [row[0] for row in self.execute(query, args).fetchall()]

    def scalar(self, query, *args):
        row = self.execute(query, args).fetchone()
        return row[0] if row else None


class FakeSched:
    def __init__(self, day_cutoff=None, today=0):
        # Default: the upcoming local midnight (rollover at 00:00).
        if day_cutoff is None:
            tomorrow = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            day_cutoff = int(tomorrow.timestamp())
        self.day_cutoff = day_cutoff
        self.today = today


class FakeCol:
    def __init__(self, conf=None, sched=None, db=None):
        self.conf = conf if conf is not None else {}
        self.sched = sched or FakeSched()
        self.db = db or FakeDb()


class FakePm:
    def __init__(self, name="TestProfile", night_mode=False, profile=None):
        self.name = name
        self._night_mode = night_mode
        self.profile = profile if profile is not None else {}

    def night_mode(self):
        return self._night_mode


class FakeAddonManager:
    def __init__(self, legacy_config=None):
        self._legacy_config = legacy_config
        self.written = {}

    def addonFromModule(self, _module):
        return "onigiri_under_test"

    def getConfig(self, _addon_id):
        return self._legacy_config

    def writeConfig(self, _addon_id, data):
        self.written["config"] = data


class FakeMw:
    def __init__(self, col=None, pm=None, addon_manager=None, legacy_config=None):
        self.col = col if col is not None else FakeCol()
        self.pm = pm or FakePm()
        self.addonManager = addon_manager or FakeAddonManager(legacy_config)


@pytest.fixture()
def fake_mw():
    """A fresh FakeMw wired to a live sqlite collection."""
    return FakeMw()


@pytest.fixture(autouse=True)
def _reset_module_caches():
    """Clear cross-test caches on config/heatmap after every test."""
    yield
    heatmap = sys.modules.get(f"{STUB_PACKAGE}.heatmap")
    if heatmap is not None:
        heatmap.invalidate_heatmap_cache()
    config_mod = sys.modules.get(f"{STUB_PACKAGE}.config")
    if config_mod is not None:
        config_mod.invalidate_config_cache()
        config_mod.config_id = None


# --- helpers shared by heatmap tests ---------------------------------------


def local_midnight(day_offset=0):
    """Local midnight timestamp (seconds) for today +/- day_offset."""
    base = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return int((base + timedelta(days=day_offset)).timestamp())


def revlog_rows_at_local_noon(*day_offsets):
    """Revlog ids at local noon of the given day offsets (type 0 = review)."""
    return [(local_midnight(off) + 12 * 3600) * 1000 for off in day_offsets]


@pytest.fixture()
def heatmap_clock():
    """Timestamps aligned with how heatmap.py derives 'today'.

    today_start_seconds = sched.day_cutoff - 86400, so we hand back the
    same value the production code will compute for the given cutoff.
    """

    class Clock:
        def __init__(self):
            self.day_cutoff = local_midnight(1)  # upcoming midnight
            self.today_start = self.day_cutoff - 86400

        def key(self, day_offset):
            return datetime.fromtimestamp(self.today_start + day_offset * 86400).strftime("%Y-%m-%d")

        def epoch_ms_now(self):
            return int(time.time() * 1000)

    return Clock()
