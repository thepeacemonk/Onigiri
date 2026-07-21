import os
import json
from pathlib import Path

from aqt import mw

"""
Manual Nook Level Reset Utility

Usage from Anki's debug console:
    import importlib
    reset = importlib.import_module("1011095603.tools.manual_reset_nook_level")
    reset.main()
"""

ADDON_ID = "1011095603"
ADDON_ROOT = Path(__file__).resolve().parents[1]


def _profile_name():
    try:
        return mw.pm.name or "default"
    except Exception:
        return "default"


def _gamification_file():
    user_files = ADDON_ROOT / "user_files"
    profile_path = user_files / f"gamification_{_profile_name()}.json"
    legacy_path = user_files / "gamification.json"
    return profile_path if profile_path.exists() else legacy_path


def _reset_config():
    config = mw.addonManager.getConfig(ADDON_ID)
    if not config or "achievements" not in config:
        print("Could not find config achievements")
        return

    config["achievements"].setdefault("restaurant_level", {})
    config["achievements"]["restaurant_level"]["total_xp"] = 0
    config["achievements"]["restaurant_level"]["level"] = 0

    mw.addonManager.writeConfig(ADDON_ID, config)
    print("Config updated - level and XP reset to 0")


def _reset_gamification_file():
    path = _gamification_file()
    if not path.exists():
        print(f"Gamification file not found: {path}")
        return

    try:
        with path.open("r+", encoding="utf-8") as f:
            data = json.load(f)
            nook_level_data = data.setdefault("restaurant_level", {})
            nook_level_data["level"] = 0
            nook_level_data["total_xp"] = 0
            nook_level_data["migrated"] = True

            f.seek(0)
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.truncate()

        print(f"Gamification data updated: {os.path.relpath(path, ADDON_ROOT)}")
    except Exception as exc:
        print(f"Error updating gamification data: {exc}")


def main():
    _reset_config()
    _reset_gamification_file()

    if mw.col:
        mw.col.setMod()
        print("Collection marked as modified")

    mw.reset()
    print("UI refreshed")
    print("\n=== RESET COMPLETE ===")
    print("Your Nook Level should now be 0")


if __name__ == "__main__":
    main()
