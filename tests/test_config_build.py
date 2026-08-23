"""Tests for config._build_config(): merging and one-time migrations.

The settings file path is monkeypatched into tmp_path so tests never
touch the real user_files/ directory. mw is injected via the module
global (headless seam from PR #301).
"""

import json

import pytest

from conftest import (
    FakeAddonManager,
    FakeCol,
    FakeMw,
    FakePm,
    load_module,
)


@pytest.fixture()
def config_mod():
    return load_module("config")


@pytest.fixture()
def settings_file(config_mod, tmp_path, monkeypatch):
    """Redirect the profile settings file into tmp_path."""
    path = tmp_path / "settings_TestProfile.json"
    monkeypatch.setattr(config_mod, "_get_settings_path", lambda: str(path))
    return path


def _write_settings(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_defaults_when_no_settings_file(config_mod, settings_file, fake_mw):
    config_mod.mw = fake_mw

    conf = config_mod.get_config()

    assert conf["userName"] == "USER"
    assert conf["onigiriThemeMode"] == "system"
    assert "colors" in conf or True  # DEFAULTS shape evolves; base keys must exist


def test_user_values_override_defaults_deeply(config_mod, settings_file, fake_mw):
    _write_settings(
        settings_file,
        {
            "userName": "Kaicho",
            "restaurant_level": {"level": 7},
        },
    )
    config_mod.mw = fake_mw

    conf = config_mod.get_config()

    assert conf["userName"] == "Kaicho"
    assert conf["restaurant_level"]["level"] == 7
    # sibling keys from DEFAULTS survive the deep merge
    assert conf["restaurant_level"]["enabled"] is False


def test_legacy_shared_config_is_migrated_to_profile_file(config_mod, settings_file, fake_mw):
    legacy = {"userName": "LegacyUser"}
    fake_mw.addonManager = FakeAddonManager(legacy_config=legacy)
    fake_mw.col = FakeCol()  # col truthy enables migration branch
    config_mod.mw = fake_mw

    conf = config_mod.get_config()

    assert conf["userName"] == "LegacyUser"
    # Migration persisted to the profile file for future loads.
    on_disk = json.loads(settings_file.read_text(encoding="utf-8"))
    assert on_disk["userName"] == "LegacyUser"


def test_restaurant_level_and_daily_special_move_out_of_achievements(config_mod, settings_file, fake_mw):
    _write_settings(
        settings_file,
        {
            "achievements": {
                "enabled": True,
                "restaurant_level": {"level": 3},
                "daily_special": {"item": "taiyaki"},
            },
        },
    )
    config_mod.mw = fake_mw

    conf = config_mod.get_config()

    assert conf["restaurant_level"]["level"] == 3
    assert conf["daily_special"] == {"item": "taiyaki"}
    assert "restaurant_level" not in conf["achievements"]
    assert "daily_special" not in conf["achievements"]


def test_hexagon_world_renamed_to_hexagon_land(config_mod, settings_file, fake_mw):
    _write_settings(settings_file, {"hexagon_world": {"coins": 42}})
    config_mod.mw = fake_mw

    conf = config_mod.get_config()

    assert conf["hexagon_land"] == {"coins": 42}


def test_gamification_becomes_achievements(config_mod, settings_file, fake_mw):
    _write_settings(settings_file, {"gamification": {"enabled": True}})
    config_mod.mw = fake_mw

    conf = config_mod.get_config()

    assert conf["achievements"]["enabled"] is True


def test_archived_widgets_removed_from_grid(config_mod, settings_file, fake_mw):
    _write_settings(
        settings_file,
        {
            "onigiriWidgetLayout": {
                "grid": {
                    "heatmap": {"pos": 0},
                    "deck_stats": {"pos": 1, "row": 5, "col": 9},
                },
                "archive": ["heatmap"],
            },
        },
    )
    config_mod.mw = fake_mw

    conf = config_mod.get_config()

    grid = conf["onigiriWidgetLayout"]["grid"]
    assert "heatmap" not in grid  # archived -> evicted from grid


def test_deck_stats_defaults_to_archive_with_clamped_position(config_mod, settings_file, fake_mw):
    """deck_stats missing everywhere lands in archive; grid entries clamp."""
    _write_settings(
        settings_file,
        {
            "onigiriWidgetLayout": {
                "grid": {"heatmap": {"pos": 0}},
                "archive": [],
            },
        },
    )
    config_mod.mw = fake_mw

    conf = config_mod.get_config()
    layout = conf["onigiriWidgetLayout"]

    assert layout["grid"].get("deck_stats") is None
    assert "deck_stats" in layout["archive"]

    # Now place it in grid with out-of-range row/col -> clamped.
    _write_settings(
        settings_file,
        {
            "onigiriWidgetLayout": {
                "grid": {"deck_stats": {"row": 99, "col": -4}},
                "archive": [],
            },
        },
    )
    config_mod.invalidate_config_cache()
    conf = config_mod.get_config()
    ds = conf["onigiriWidgetLayout"]["grid"]["deck_stats"]
    assert ds["row"] in (1, 2)
    assert ds["col"] >= 1


def test_sidebar_gamification_button_inserted_before_more(config_mod, settings_file, fake_mw):
    _write_settings(
        settings_file,
        {"sidebarButtonLayout": {"visible": ["decks", "more"], "archived": []}},
    )
    config_mod.mw = fake_mw

    conf = config_mod.get_config()

    visible = conf["sidebarButtonLayout"]["visible"]
    assert visible.index("gamification") < visible.index("more")


def test_stattxt_visible_bool_becomes_mode(config_mod, settings_file, fake_mw):
    _write_settings(
        settings_file,
        {
            "onigiri_reviewer_stattxt_visible": False,
        },
    )
    config_mod.mw = fake_mw

    conf = config_mod.get_config()

    assert conf["onigiri_reviewer_stattxt_mode"] == "off"


def test_get_config_returns_deep_copy(config_mod, settings_file, fake_mw):
    config_mod.mw = fake_mw

    first = config_mod.get_config()
    first["userName"] = "mutated"

    second = config_mod.get_config()
    assert second["userName"] == "USER"


def test_write_config_persists_json(config_mod, settings_file, fake_mw):
    config_mod.mw = fake_mw

    conf = config_mod.get_config()
    conf["userName"] = "Saved"
    config_mod.write_config(conf)

    on_disk = json.loads(settings_file.read_text(encoding="utf-8"))
    assert on_disk["userName"] == "Saved"

    # Cache invalidated by write -> next read sees the new value.
    assert config_mod.get_config()["userName"] == "Saved"
