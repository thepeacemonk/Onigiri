import copy
import hashlib
import json
import os
import shutil
import sys
import time
import zipfile

from aqt import mw

from . import config
from . import safe_storage


SYNC_MANIFEST = "_onigiri_sync_manifest.json"
SYNC_FORMAT_VERSION = 2

SYNC_CATEGORY_FLAGS = {
    "theme": "ankiweb_sync_theme",
    "profile": "ankiweb_sync_profile",
    "games": "ankiweb_sync_games",
    "study_tools": "ankiweb_sync_study_tools",
    "assets": "ankiweb_sync_assets",
    "layout": "ankiweb_sync_layout",
}

GAME_CONFIG_KEYS = {
    "achievements", "daily_special", "focusDango", "gamification",
    "hexagon_land", "hexagon_world", "mochi_messages", "onigimon",
    "restaurant_level",
}
PROFILE_CONFIG_KEYS = {
    "lastBirthdayShown", "onigiriProfile", "showCongratsProfileBar",
    "showHeatmapOnProfile", "showOverviewProfileBar", "userBirthday", "userName",
}
STUDY_TOOL_CONFIG_KEYS = {
    "hashi_notes", "onigiri_pomodoro_show_in_reviewer_header", "prep_station",
    "study_tools_visibility",
}
LAYOUT_CONFIG_KEYS = {
    "externalWidgetIdentity", "externalWidgetLayout", "onigiriDecklineAutoEmbed",
    "onigiriWidgetLayout", "sidebarButtonLayout", "sidebarCollapsed",
    "sidebarPosition", "unifiedGridRows",
}
LOCAL_CONFIG_KEYS = {
    "settings_complexity", "settings_sidebar_collapsed", "window_settings",
}
LAYOUT_TOKENS = (
    "_collapsed", "_font_size", "_gap", "_grid", "_height", "_layout", "_margin",
    "_position", "_scale", "_spacing", "_span", "_width",
)
NESTED_LAYOUT_KEYS = {
    "column", "column_count", "columns", "font_size", "font_scale", "gap",
    "height", "margin", "offset", "orientation", "padding", "position", "row",
    "row_span", "rows", "scale", "size", "spacing", "width",
}

ASSET_DIRS = {
    "custom_deck_icons", "fonts", "icons", "main_bg", "profile", "profile_bg",
    "mochi_messenger", "onigimon_backgrounds", "reviewer_bar_bg", "reviewer_bg",
    "sidebar_bg", "sprites", "toolbar_bg", "user_themes", "prep_station_bg",
    "prep_station_thumbnails",
}
GAME_FILE_PREFIXES = (
    "gamification_", "hexagon_land_", "mochi_history_", "onigimon_",
)
STUDY_TOOL_DIRS = {"hashi_notes", "pomodoro", "pomodoro_sounds", "prep_station"}


def _deep_merge(target, source):
    for key, value in (source or {}).items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge(target[key], value)
        else:
            target[key] = copy.deepcopy(value)


def _is_layout_key(key):
    lowered = str(key or "").lower()
    return key in LAYOUT_CONFIG_KEYS or any(token in lowered for token in LAYOUT_TOKENS)


def _addon_config_category(key):
    if key in LOCAL_CONFIG_KEYS or str(key).startswith("ankiweb_sync_"):
        return None
    if key in GAME_CONFIG_KEYS:
        return "games"
    if key in PROFILE_CONFIG_KEYS:
        return "profile"
    if key in STUDY_TOOL_CONFIG_KEYS or str(key).startswith("onigiri_pomodoro_"):
        return "study_tools"
    if _is_layout_key(key):
        return "layout"
    return "theme"


def _nested_layout_key(key):
    lowered = str(key or "").lower()
    return lowered in NESTED_LAYOUT_KEYS or any(token in lowered for token in LAYOUT_TOKENS)


def _split_nested_layout(value):
    """Return (portable, layout) copies of a nested config value."""
    if not isinstance(value, dict):
        return copy.deepcopy(value), None
    portable = {}
    layout = {}
    for key, child in value.items():
        if _nested_layout_key(key):
            layout[key] = copy.deepcopy(child)
            continue
        portable_child, layout_child = _split_nested_layout(child)
        if portable_child is not None:
            portable[key] = portable_child
        if layout_child:
            layout[key] = layout_child
    return (portable or None), (layout or None)


def _is_onigiri_collection_key(key):
    text = str(key or "")
    return text.startswith(("modern_menu_", "onigiri_")) or text in {
        "heatmapDefaultView", "heatmapShowMonths", "heatmapShowStreak",
        "heatmapShowWeekHeader", "heatmapShowWeekdays", "heatmapWeekStart",
        "heatmapParticlesAnimation",
    }


def _collection_config_category(key):
    text = str(key or "")
    if text.startswith(("modern_menu_profile_", "onigiri_profile_")) or text in {
        "modern_menu_hide_profile_bar", "modern_menu_userName",
    }:
        return "profile"
    if text.startswith(("onigiri_prep_station_", "onigiri_hashi_", "onigiri_pomodoro_")):
        return "study_tools"
    if _is_layout_key(text):
        return "layout"
    return "theme"


def _file_category(relative_path):
    path = str(relative_path or "").replace("\\", "/").lstrip("/")
    if not path or path == SYNC_MANIFEST:
        return None
    parts = path.split("/")
    name = parts[-1]
    top = parts[0]
    if (
        name.startswith("settings_")
        or name in {"sync_state.json", ".DS_Store"}
        or name.endswith((".bak", ".corrupt", ".log"))
        or ".tmp" in name
        or top == "_qss_icon_cache"
    ):
        return None
    if top in ASSET_DIRS:
        return "assets"
    if top in STUDY_TOOL_DIRS:
        return "study_tools"
    if any(name.startswith(prefix) for prefix in GAME_FILE_PREFIXES):
        return "games"
    return None


class SyncManager:
    """Category-aware Onigiri data sync through Anki's media bridge."""

    def __init__(self):
        self._sync_filename = None
        self._media_dir = None
        self._user_files_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "user_files")
        self._state_file = os.path.join(self._user_files_dir, "sync_state.json")
        self._migrate_legacy_state_file()

    def _migrate_legacy_state_file(self):
        legacy = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".onigiri_sync_state.json")
        if os.path.exists(legacy) and not os.path.exists(self._state_file):
            try:
                os.makedirs(self._user_files_dir, exist_ok=True)
                shutil.copy2(legacy, self._state_file)
            except OSError as exc:
                print(f"Onigiri Sync: could not migrate sync state: {exc}")

    def _ensure_init(self):
        if not mw.col:
            return False
        profile_name = mw.pm.name
        self._sync_filename = f"_onigiri_sync_{profile_name}.zip"
        self._media_dir = mw.col.media.dir()
        return True

    def _load_state(self):
        if os.path.exists(self._state_file):
            try:
                state = safe_storage.read_json(self._state_file, default={})
                if isinstance(state, dict):
                    state.setdefault("last_zip_mtime", {})
                    state.setdefault("last_zip_size", {})
                    state.setdefault("last_zip_hash", {})
                    state.setdefault("last_local_signature", {})
                    return state
            except Exception:
                pass
        return {
            "last_zip_mtime": {}, "last_zip_size": {},
            "last_zip_hash": {}, "last_local_signature": {},
        }

    @staticmethod
    def _file_hash(path):
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _save_state(self, mtime, size, local_signature=None):
        if not self._ensure_init():
            return
        state = self._load_state()
        profile_name = mw.pm.name
        state["last_zip_mtime"][profile_name] = mtime
        state["last_zip_size"][profile_name] = size
        sync_path = self.get_sync_file_path()
        if sync_path and os.path.exists(sync_path):
            state["last_zip_hash"][profile_name] = self._file_hash(sync_path)
        if local_signature is None:
            local_signature = self._content_signature()
        state["last_local_signature"][profile_name] = local_signature
        safe_storage.atomic_write_json(self._state_file, state)

    def is_enabled(self):
        return bool(config.get_config_readonly().get("ankiweb_sync_enabled", False))

    def categories(self, conf=None):
        conf = conf if isinstance(conf, dict) else config.get_config_readonly()
        return {
            category: bool(conf.get(flag, category != "layout"))
            for category, flag in SYNC_CATEGORY_FLAGS.items()
        }

    def get_sync_file_path(self):
        if not self._ensure_init():
            return None
        return os.path.join(self._media_dir, self._sync_filename)

    def _settings_manifest(self, conf, enabled):
        addon_groups = {category: {} for category in SYNC_CATEGORY_FLAGS}
        for key, value in conf.items():
            category = _addon_config_category(key)
            if not category:
                continue
            if category == "layout":
                if enabled.get("layout"):
                    addon_groups["layout"][key] = copy.deepcopy(value)
                continue
            portable, layout = _split_nested_layout(value)
            if enabled.get(category) and portable is not None:
                addon_groups[category][key] = portable
            if enabled.get("layout") and layout is not None:
                addon_groups["layout"][key] = layout

        collection_groups = {category: {} for category in SYNC_CATEGORY_FLAGS}
        collection_conf = safe_storage.collection_config_snapshot(mw.col)
        for key, value in collection_conf.items():
            if not _is_onigiri_collection_key(key):
                continue
            category = _collection_config_category(key)
            if enabled.get(category):
                collection_groups[category][key] = copy.deepcopy(value)

        return {
            "format": SYNC_FORMAT_VERSION,
            "created_at": time.time(),
            "profile": str(getattr(mw.pm, "name", "") or ""),
            "categories": enabled,
            "addon_config": {key: value for key, value in addon_groups.items() if value},
            "collection_config": {key: value for key, value in collection_groups.items() if value},
        }

    def _content_signature(self, conf=None, enabled=None, manifest=None):
        conf = conf if isinstance(conf, dict) else config.get_config_readonly()
        enabled = enabled if isinstance(enabled, dict) else self.categories(conf)
        manifest = manifest or self._settings_manifest(conf, enabled)
        stable_manifest = {
            "categories": enabled,
            "addon_config": manifest.get("addon_config", {}),
            "collection_config": manifest.get("collection_config", {}),
        }
        digest = hashlib.sha256(
            json.dumps(
                stable_manifest, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), default=str,
            ).encode("utf-8")
        )
        selected_files = []
        for root, _, files in os.walk(self._user_files_dir):
            for filename in files:
                source = os.path.join(root, filename)
                relative = os.path.relpath(source, self._user_files_dir).replace(os.sep, "/")
                category = _file_category(relative)
                if category and enabled.get(category):
                    selected_files.append((relative, source))
        for relative, source in sorted(selected_files):
            digest.update(relative.encode("utf-8"))
            try:
                with open(source, "rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
            except OSError:
                continue
        return digest.hexdigest()

    def pack_user_files(self, force=False):
        """Build a media zip containing only this device's enabled categories."""
        if not self._ensure_init():
            return False
        if not safe_storage.flush_pending():
            return False
        sync_path = self.get_sync_file_path()
        # A first launch after an upgrade may have no sync bookkeeping (older
        # releases kept it outside user_files). Do not overwrite the existing
        # media archive before the user resolves which saved copy to keep.
        if not force and self.check_conflict() != "none":
            return False
        temp_zip = sync_path + ".tmp"
        conf = config.get_config_readonly()
        enabled = self.categories(conf)
        try:
            manifest = self._settings_manifest(conf, enabled)
            local_signature = self._content_signature(conf, enabled, manifest)
        except Exception as exc:
            print(f"Onigiri Sync: Could not read collection settings; existing sync archive retained: {exc}")
            return False
        state = self._load_state()
        profile_name = mw.pm.name
        if (
            os.path.exists(sync_path)
            and state["last_local_signature"].get(profile_name) == local_signature
        ):
            return True

        try:
            with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(SYNC_MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
                for root, _, files in os.walk(self._user_files_dir):
                    for filename in files:
                        source = os.path.join(root, filename)
                        relative = os.path.relpath(
                            source, self._user_files_dir
                        ).replace(os.sep, "/")
                        category = _file_category(relative)
                        if category and enabled.get(category):
                            archive.write(source, relative)
            os.replace(temp_zip, sync_path)
            stat = os.stat(sync_path)
            self._save_state(stat.st_mtime, stat.st_size, local_signature)
            return True
        except Exception as exc:
            print(f"Onigiri Sync: Failed to pack files: {exc}")
            try:
                if os.path.exists(temp_zip):
                    os.remove(temp_zip)
            except OSError:
                pass
            return False

    def _read_manifest(self, archive):
        try:
            payload = json.loads(archive.read(SYNC_MANIFEST).decode("utf-8"))
            return payload if isinstance(payload, dict) else None
        except Exception:
            return None

    def _legacy_manifest(self, archive):
        """Convert a pre-v2 full-folder archive into selective config groups."""
        settings_names = [
            name for name in archive.namelist()
            if os.path.basename(name).startswith("settings_") and name.endswith(".json")
            and not name.endswith((".bak", ".corrupt"))
        ]
        if not settings_names:
            return {"addon_config": {}, "collection_config": {}}
        preferred = f"settings_{getattr(mw.pm, 'name', '')}.json"
        settings_name = next(
            (name for name in settings_names if os.path.basename(name) == preferred),
            settings_names[0] if len(settings_names) == 1 else None,
        )
        if settings_name is None:
            return {"addon_config": {}, "collection_config": {}}
        try:
            legacy_conf = json.loads(archive.read(settings_name).decode("utf-8"))
        except Exception:
            legacy_conf = {}
        groups = {category: {} for category in SYNC_CATEGORY_FLAGS}
        for key, value in (legacy_conf.items() if isinstance(legacy_conf, dict) else ()):
            category = _addon_config_category(key)
            if not category:
                continue
            if category == "layout":
                groups["layout"][key] = value
                continue
            portable, layout = _split_nested_layout(value)
            if portable is not None:
                groups[category][key] = portable
            if layout is not None:
                groups["layout"][key] = layout
        return {"addon_config": groups, "collection_config": {}}

    def _apply_manifest(self, manifest, enabled):
        local_conf = config.get_config()
        for category, patch in (manifest.get("addon_config") or {}).items():
            if enabled.get(category) and isinstance(patch, dict):
                _deep_merge(local_conf, patch)
        config.write_config(local_conf)

        for category, patch in (manifest.get("collection_config") or {}).items():
            if not enabled.get(category) or not isinstance(patch, dict):
                continue
            for key, value in patch.items():
                if _is_onigiri_collection_key(key):
                    config.set_collection_config(key, value)

    def _extract_selected_files(self, archive, enabled):
        root = os.path.realpath(self._user_files_dir)
        os.makedirs(root, exist_ok=True)
        for info in archive.infolist():
            if info.is_dir():
                continue
            relative = info.filename.replace("\\", "/").lstrip("/")
            category = _file_category(relative)
            if not category or not enabled.get(category):
                continue
            target = os.path.realpath(os.path.join(root, *relative.split("/")))
            if target != root and not target.startswith(root + os.sep):
                print(f"Onigiri Sync: skipped unsafe archive path {relative!r}")
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            temp_target = target + ".sync-tmp"
            with archive.open(info, "r") as source, open(temp_target, "wb") as destination:
                shutil.copyfileobj(source, destination)
            os.replace(temp_target, target)

    def unpack_user_files(self):
        """Merge enabled cloud categories while preserving local-only layout."""
        if not self._ensure_init():
            return False
        sync_path = self.get_sync_file_path()
        if not sync_path or not os.path.exists(sync_path):
            return False
        enabled = self.categories(config.get_config_readonly())
        try:
            if not safe_storage.flush_pending():
                return False
            safe_storage.backup_before_upgrade()
            with zipfile.ZipFile(sync_path, "r") as archive:
                manifest = self._read_manifest(archive) or self._legacy_manifest(archive)
                self._apply_manifest(manifest, enabled)
                self._extract_selected_files(archive, enabled)
            self._invalidate_loaded_state()
            stat = os.stat(sync_path)
            self._save_state(stat.st_mtime, stat.st_size)
            return True
        except Exception as exc:
            print(f"Onigiri Sync: Failed to unpack files: {exc}")
            return False

    @staticmethod
    def _invalidate_loaded_state():
        """Prevent a pre-sync in-memory game from saving over imported data."""
        config.invalidate_config_cache()
        addon = __package__.rsplit(".", 1)[0]
        module = sys.modules.get(addon + ".gamification.gamification")
        game = getattr(module, "_gamification_data", None)
        if game is not None:
            game.reload()
        for name, attribute in (("onigimon", "_state"), ("hexagon_land", "_state_cache")):
            module = sys.modules.get(addon + ".gamification." + name)
            manager = getattr(module, "manager", None)
            if manager is not None:
                setattr(manager, attribute, None)
        module = sys.modules.get(addon + ".gamification.mochi_messages")
        if module is not None:
            module._HISTORY_CACHE = None
        module = sys.modules.get(addon + ".gamification.nook_level")
        manager = getattr(module, "manager", None)
        if manager is not None:
            manager.invalidate_daily_cache()

    def get_local_mtime(self):
        """Latest selected source timestamp, excluding local sync bookkeeping."""
        enabled = self.categories(config.get_config_readonly())
        latest = 0
        for root, _, files in os.walk(self._user_files_dir):
            for filename in files:
                source = os.path.join(root, filename)
                relative = os.path.relpath(source, self._user_files_dir).replace(os.sep, "/")
                category = _file_category(relative)
                if category and enabled.get(category):
                    try:
                        latest = max(latest, os.path.getmtime(source))
                    except OSError:
                        pass
        settings_categories = (
            "theme", "profile", "games", "study_tools", "layout",
        )
        if any(enabled.get(category) for category in settings_categories):
            try:
                latest = max(latest, os.path.getmtime(config._get_settings_path()))
            except OSError:
                pass
        return latest

    def get_cloud_mtime(self):
        sync_path = self.get_sync_file_path()
        if sync_path and os.path.exists(sync_path):
            return os.path.getmtime(sync_path)
        return 0

    def check_conflict(self):
        if not self._ensure_init():
            return "none"
        sync_path = self.get_sync_file_path()
        if not os.path.exists(sync_path):
            return "none"
        stat = os.stat(sync_path)
        state = self._load_state()
        profile_name = mw.pm.name
        last_mtime = state["last_zip_mtime"].get(profile_name, 0)
        last_size = state["last_zip_size"].get(profile_name, 0)
        last_hash = state["last_zip_hash"].get(profile_name, "")
        if last_hash:
            try:
                if self._file_hash(sync_path) == last_hash:
                    return "none"
            except OSError:
                pass
            # The media payload genuinely changed on another device. Always
            # ask which side should win; timestamps cannot safely distinguish
            # a local-only layout edit from a portable theme/data edit.
            return "cloud_newer"
        if abs(stat.st_mtime - last_mtime) < 1.0 and stat.st_size == last_size:
            return "none"
        return "cloud_newer"


onigiri_sync = SyncManager()
