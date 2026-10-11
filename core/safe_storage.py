"""
Crash-safe persistence for everything Onigiri keeps in ``user_files``.

Anki preserves ``user_files`` across add-on updates (it renames the folder
aside, deletes the add-on, then renames it back), so a normal AnkiWeb update
should never cost the user their setup. The ways a setup *does* disappear are:

1. A truncated write. ``open(path, "w")`` empties the file before the new
   contents land, so a crash or a hard quit mid-write leaves a zero-byte or
   half-written JSON file. Every loader here used to answer that by silently
   falling back to defaults, which reads to the user as "the update wiped me".
2. A manual install: unzipping an ``.ankiaddon`` over the folder by hand does
   not go through Anki's updater and takes ``user_files`` with it.
3. A renamed Anki profile, which leaves ``settings_<old>.json`` orphaned.

So: writes go out atomically, every write rotates a ``.bak``, readers walk a
chain of fallbacks before they ever admit defeat, and a mirror of the critical
files lives *outside* ``addons21`` where a manual reinstall cannot reach it.
"""

import copy
import hashlib
import json
import os
import shutil
import time
import zipfile
from dataclasses import asdict, fields

# Files whose loss would visibly undo the user's setup. Everything else in
# user_files (caches, generated icons) can be rebuilt, so it stays out of the
# external mirror to keep the copy cheap.
CRITICAL_PREFIXES = (
    "settings_",
    "gamification_",
    "onigimon_",
    "hexagon_land_",
    "mochi_history_",
    "communications_",
)
CRITICAL_SUBDIRS = ("hashi_notes", "user_themes", "prep_station", "pomodoro")
_UPGRADE_BACKUPS = set()


def dataclass_from_dict(cls, data):
    """Load known fields without throwing away older or extension fields."""
    names = {item.name for item in fields(cls)}
    state = cls(**{key: value for key, value in data.items() if key in names})
    state._onigiri_extra_fields = copy.deepcopy(
        {key: value for key, value in data.items() if key not in names}
    )
    return state


def dataclass_payload(state):
    payload = copy.deepcopy(getattr(state, "_onigiri_extra_fields", {}))
    payload.update(asdict(state))
    return payload


def collection_config_snapshot(collection):
    """Read all keys without iterating Anki's non-iterable ConfigManager.

    Modern Anki exposes a JSON dictionary through Collection.all_config().
    Only old collections with a real dict may use the legacy interface.
    Fail explicitly instead of backing up or syncing an empty substitute.
    """
    if collection is None:
        return {}
    export = getattr(collection, "all_config", None)
    data = export() if callable(export) else collection.conf
    if not isinstance(data, dict):
        raise TypeError("Anki did not provide a collection configuration dictionary")
    return copy.deepcopy(data)


def backup_before_upgrade(shared_config=None):
    """Keep one untouched copy of legacy saves and assets outside addons21.

    The archive is never refreshed by later launches or saves. It therefore
    remains useful even after a migration has written new-format data.
    """
    target = os.path.join(external_backup_dir(), "before_progress_upgrade_v2.zip")
    try:
        from aqt import mw
        profile = str(getattr(getattr(mw, "pm", None), "name", "") or "")
        collection = getattr(mw, "col", None)
    except Exception:
        profile, collection = "", None
    if shared_config is None:
        try:
            shared_config = mw.addonManager.getConfig(mw.addonManager.addonFromModule(__name__))
        except Exception:
            pass
    identity = (target, profile, collection is not None)
    if identity in _UPGRADE_BACKUPS:
        return target
    # Collection settings are profile-specific, unlike the shared asset tree.
    # Capture each profile before any startup migration changes its config.
    if collection is not None and profile:
        suffix = hashlib.sha256(profile.encode("utf-8")).hexdigest()[:16]
        collection_path = os.path.join(external_backup_dir(),
                                       f"before_progress_upgrade_v2_{suffix}.json")
        if not os.path.exists(collection_path):
            try:
                data = {"profile": profile, "collection_config": collection_config_snapshot(collection)}
                if not atomic_write_json(collection_path, data, mirror=False):
                    return None
            except Exception as exc:
                _note(f"Onigiri could not back up your collection settings. Your saved settings were not changed. Details: {exc}",
                      key="storage_collection_backup_error", error=str(exc))
                return None
    if os.path.exists(target):
        _UPGRADE_BACKUPS.add(identity)
        return target
    tmp = target + ".tmp"
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            root = user_files_dir()
            for current, dirs, files in os.walk(root):
                dirs[:] = [name for name in dirs if name != "__pycache__"]
                for name in files:
                    if name.endswith(".log") or ".tmp" in name:
                        continue
                    source = os.path.join(current, name)
                    archive.write(source, "user_files/" + os.path.relpath(source, root))
            if isinstance(shared_config, dict):
                archive.writestr("legacy_addon_config.json", json.dumps(shared_config))
            for name in (".onigiri_sync_state.json", "onigiri_layout.json"):
                source = os.path.join(addon_root(), name)
                if os.path.isfile(source):
                    archive.write(source, name)
        os.replace(tmp, target)
        _UPGRADE_BACKUPS.add(identity)
        return target
    except Exception as exc:
        _cleanup(tmp)
        _note(f"The pre-upgrade backup could not be created: {exc}",
              key="storage_upgrade_backup_error", error=str(exc))
        return None

# Recovery notices collected during load, drained once by the startup check so
# the user hears about a rescued file instead of quietly seeing defaults.
_pending_notices = []

_MAX_SNAPSHOTS = 5
_SNAPSHOT_INTERVAL = 60 * 60 * 12  # at most two dated snapshots per file/day


def addon_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def user_files_dir():
    path = os.path.join(addon_root(), "user_files")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def anki_base_dir():
    """The Anki2 folder. Parent of addons21, so it survives add-on removal."""
    try:
        from aqt import mw

        base = mw.pm.base
        if base and os.path.isdir(base):
            return base
    except Exception:
        pass
    # addon_root is <base>/addons21/<package>
    return os.path.dirname(os.path.dirname(addon_root()))


def external_backup_dir():
    """Mirror location outside addons21 - a manual reinstall cannot touch it."""
    path = os.path.join(anki_base_dir(), "onigiri_backups")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def take_notices():
    """Drain recovery messages queued while loading files."""
    global _pending_notices
    notices, _pending_notices = _pending_notices, []
    return [_notice_copy(*_notice_localization.pop(message))
            if message in _notice_localization else message for message in notices]


_notice_localization = {}


def _notice_copy(key, fallback, values):
    # Config loading uses this module. Resolve language only when notices are
    # displayed, after loading has finished, to avoid a config import cycle.
    try:
        from .translations import tr, tr_literal
        values = dict(values)
        for name in ("label", "source"):
            if name in values:
                values[name] = tr_literal(values[name])
        return tr(key, fallback).format(**values)
    except Exception:
        return fallback


def _note(message, *, key="", **values):
    print(f"Onigiri storage: {message}")
    if key:
        _notice_localization[message] = (key, message, values)
    if message not in _pending_notices:
        _pending_notices.append(message)


# ─── Atomic writes ────────────────────────────────────────────────────────────


def _looks_usable(data):
    """Empty containers parse fine but are what a wiped setup looks like."""
    if data is None:
        return False
    if isinstance(data, (dict, list, str)) and len(data) == 0:
        return False
    return True


def _rotate_backup(path):
    """Copy the current file to ``.bak`` - but never over a better ``.bak``."""
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as handle:
            current = json.load(handle)
    except Exception:
        # The file on disk is already corrupt; keeping the older .bak is the
        # whole point, so leave it alone.
        return
    if current is None:
        return
    try:
        shutil.copy2(path, path + ".bak")
    except OSError as exc:
        print(f"Onigiri storage: could not rotate backup for {path}: {exc}")


def atomic_write_json(path, data, mirror=True):
    """
    Write ``data`` to ``path`` so the file is either the old contents or the
    new ones, never a truncated mix.

    Returns True on success. Failures are reported and swallowed so a read-only
    disk cannot take the UI down mid-save.
    """
    directory = os.path.dirname(path)
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError:
        pass

    tmp = f"{path}.tmp{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception as exc:
        print(f"Onigiri storage: failed writing {path}: {exc}")
        _cleanup(tmp)
        return False

    _rotate_backup(path)

    try:
        os.replace(tmp, path)
    except OSError as exc:
        print(f"Onigiri storage: failed replacing {path}: {exc}")
        _cleanup(tmp)
        return False

    # The very first save has no previous file to rotate, which would leave a
    # new user with no .bak at all until their second save. Seed it.
    if not os.path.exists(path + ".bak"):
        try:
            shutil.copy2(path, path + ".bak")
        except OSError:
            pass

    if mirror and _is_critical(path):
        _snapshot(path)
        mirror_file(path)
    # A queued older save must never overwrite an explicit, immediate save.
    _PENDING_WRITES.pop(path, None)
    return True


# Writes queued by schedule_write_json(), keyed by path: the newest payload for
# a file wins. Answering a card used to fsync and copy game-state files three
# times per review; coalescing those into one write a moment later keeps the
# reviewer responsive without giving up the atomic write itself.
_PENDING_WRITES = {}
_SCHEDULED_PATHS = set()
_DEFAULT_WRITE_DELAY_MS = 1500


def schedule_write_json(path, data, delay_ms=_DEFAULT_WRITE_DELAY_MS):
    """Queue an atomic write for ``path`` instead of performing it now.

    The payload is kept in memory and written by flush_pending(), which also
    runs on profile close, before a sync and on screen changes, so nothing is
    lost. Callers that must see the file on disk immediately (or that are about
    to hand the file to another process) should call atomic_write_json().
    """
    _PENDING_WRITES[path] = copy.deepcopy(data)

    if path in _SCHEDULED_PATHS:
        return True
    _SCHEDULED_PATHS.add(path)

    def run():
        _SCHEDULED_PATHS.discard(path)
        flush_pending(path)

    try:
        from aqt import mw

        mw.progress.single_shot(int(delay_ms), run, False)
    except Exception:
        # No Qt loop (tests, headless tools): fall back to writing right away.
        _SCHEDULED_PATHS.discard(path)
        return flush_pending(path)
    return True


def pending_payload(path):
    """The queued-but-unwritten payload for ``path``, or None."""
    return _PENDING_WRITES.get(path)


def flush_pending(path=None):
    """Write queued payloads. Without ``path``, flushes every pending file."""
    paths = [path] if path is not None else list(_PENDING_WRITES.keys())
    success = True
    for target in paths:
        data = _PENDING_WRITES.get(target)
        if data is None:
            continue
        if not atomic_write_json(target, data):
            success = False
    return success


def _cleanup(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


# ─── Resilient reads ──────────────────────────────────────────────────────────


def _try_load(path):
    if not path or not os.path.exists(path):
        return None, False
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle), True
    except Exception:
        return None, False


def read_json(path, default=None, label=None, validator=None):
    """
    Load ``path``, falling back through ``.bak``, dated snapshots and the
    external mirror before giving up.

    Only returns ``default`` when every candidate is gone or unreadable, and
    says so out loud rather than letting a corrupt file read as a fresh start.
    """
    label = label or os.path.basename(path)
    if validator is None and isinstance(default, (dict, list)):
        validator = lambda value: isinstance(value, type(default))

    def valid(value):
        try:
            return validator(value) if validator else True
        except Exception:
            return False

    # A write queued by schedule_write_json() is newer than anything on disk.
    queued = _PENDING_WRITES.get(path)
    if queued is not None and valid(queued):
        try:
            return json.loads(json.dumps(queued))
        except Exception:
            flush_pending(path)

    recoveries = [(path + ".bak", "backup file")]
    recoveries.extend((snap, "dated snapshot") for snap in _snapshots_for(path))
    mirrored = _mirror_path_for(path)
    if mirrored:
        recoveries.append((mirrored, "external backup"))
    # The external mirror can hold the latest successful save while .bak is
    # one edit older. Recover the freshest valid copy, including valid clears.
    def modified(candidate):
        try:
            return os.stat(candidate[0]).st_mtime_ns
        except OSError:
            return -1
    candidates = [(path, None)] + sorted(recoveries, key=modified, reverse=True)

    for candidate, source in candidates:
        data, ok = _try_load(candidate)
        if not ok or not valid(data):
            continue
        # Valid empty containers are intentional clears/resets. Resurrecting a
        # nonempty .bak here undoes the user's deletion on the next launch.
        if source:
            _note(
                f"{label} was unreadable, so it was restored from the {source}.",
                key="storage_restored", label=label, source=source,
            )
            _repair(path, candidate)
        return data

    if os.path.exists(path):
        # The file is there but nothing in the chain parsed - do not overwrite
        # it on the next save without keeping the evidence around.
        _quarantine(path)
        _note(
            f"{label} was damaged and no backup could be read. "
            "Onigiri fell back to defaults; the damaged file was kept as .corrupt.",
            key="storage_damaged", label=label,
        )
    return copy.deepcopy(default) if default is not None else {}


def _repair(path, source):
    """Put a recovered copy back in place so the next read is clean."""
    if source == path:
        return
    try:
        if os.path.exists(path):
            shutil.copy2(path, path + ".corrupt")
        shutil.copy2(source, path)
    except OSError as exc:
        print(f"Onigiri storage: could not repair {path}: {exc}")


def _quarantine(path):
    try:
        shutil.copy2(path, path + ".corrupt")
    except OSError:
        pass


# ─── Snapshots and the external mirror ────────────────────────────────────────


def _is_critical(path):
    # Imported artwork, fonts, sounds, databases and pending redemptions are
    # user data too. Only generated caches are safe to leave out of recovery.
    relative = os.path.relpath(path, user_files_dir())
    if relative != os.pardir and not relative.startswith(os.pardir + os.sep):
        return not any(part in {"__pycache__", "_qss_icon_cache", "_icon_cache"}
                       for part in relative.split(os.sep))
    name = os.path.basename(path)
    if any(name.startswith(prefix) for prefix in CRITICAL_PREFIXES):
        return True
    parent = os.path.basename(os.path.dirname(path))
    return parent in CRITICAL_SUBDIRS


def _snapshot_dir():
    path = os.path.join(external_backup_dir(), "snapshots")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def _snapshots_for(path):
    """Dated snapshots for ``path``, newest first."""
    name = os.path.basename(path)
    directory = _file_snapshot_dir(path)
    try:
        entries = [
            os.path.join(directory, entry)
            for entry in os.listdir(directory)
            if entry.startswith(name + ".") and entry.endswith(".json")
        ]
    except OSError:
        return []
    return sorted(entries, key=os.path.getmtime, reverse=True)


def _file_snapshot_dir(path):
    relative = os.path.relpath(path, user_files_dir())
    parent = os.path.dirname(relative)
    if parent and parent != os.pardir and not parent.startswith(os.pardir + os.sep):
        directory = os.path.join(_snapshot_dir(), parent)
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError:
            pass
        return directory
    return _snapshot_dir()


def _snapshot(path):
    """Keep a small dated history, throttled so saves stay cheap."""
    existing = _snapshots_for(path)
    if existing:
        try:
            if time.time() - os.path.getmtime(existing[0]) < _SNAPSHOT_INTERVAL:
                return
        except OSError:
            pass

    stamp = time.strftime("%Y%m%d_%H%M%S")
    target = os.path.join(_file_snapshot_dir(path), f"{os.path.basename(path)}.{stamp}.json")
    try:
        shutil.copy2(path, target)
        os.utime(target, None)
    except OSError as exc:
        print(f"Onigiri storage: could not snapshot {path}: {exc}")
        return

    for stale in _snapshots_for(path)[_MAX_SNAPSHOTS:]:
        _cleanup(stale)


def _mirror_path_for(path):
    """Where ``path`` lives inside the external mirror, or None if untracked."""
    root = user_files_dir()
    try:
        relative = os.path.relpath(path, root)
    except ValueError:
        return None
    if relative == os.pardir or relative.startswith(os.pardir + os.sep):
        return None
    return os.path.join(external_backup_dir(), "user_files", relative)


def mirror_file(path):
    target = _mirror_path_for(path)
    if not target:
        return
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        temporary = target + ".tmp"
        shutil.copy2(path, temporary)
        os.replace(temporary, target)
    except OSError as exc:
        print(f"Onigiri storage: could not mirror {path}: {exc}")


def mirror_all():
    """Copy every critical file to the external mirror. Cheap enough to run
    on profile close, which is the last moment we are sure the data is final."""
    root = user_files_dir()
    copied = 0
    for current, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith((".tmp", ".bak", ".corrupt", ".log")) or ".tmp" in name:
                continue
            source = os.path.join(current, name)
            if not _is_critical(source):
                continue
            if name.endswith(".json") and not _try_load(source)[1]:
                continue
            target = _mirror_path_for(source)
            if not target:
                continue
            try:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                if os.path.isfile(target):
                    old, new = os.stat(target), os.stat(source)
                    if old.st_size == new.st_size and old.st_mtime_ns == new.st_mtime_ns:
                        continue
                temporary = target + ".tmp"
                shutil.copy2(source, temporary)
                os.replace(temporary, target)
                copied += 1
            except OSError:
                continue
    return copied


def restore_from_mirror():
    """
    Copy the external mirror back into ``user_files``, skipping anything that
    already exists locally. Used when a manual reinstall wiped the folder.
    """
    source_root = os.path.join(external_backup_dir(), "user_files")
    if not os.path.isdir(source_root):
        return 0
    restored = 0
    for current, _dirs, files in os.walk(source_root):
        for name in files:
            source = os.path.join(current, name)
            relative = os.path.relpath(source, source_root)
            target = os.path.join(user_files_dir(), relative)
            if os.path.exists(target):
                continue
            try:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(source, target)
                restored += 1
            except OSError:
                continue
    return restored


def looks_wiped():
    """
    True when ``user_files`` has no per-profile settings file at all. That is
    what a manual reinstall (unzipping over the folder) leaves behind, and it
    is the only situation where a bulk restore is the right move - restoring
    file-by-file at every launch would resurrect themes the user deleted on
    purpose.
    """
    root = user_files_dir()
    try:
        entries = os.listdir(root)
    except OSError:
        return False
    return not any(entry.startswith("settings_") for entry in entries)


def mirror_has_data():
    source_root = os.path.join(external_backup_dir(), "user_files")
    if not os.path.isdir(source_root):
        return False
    for _current, _dirs, files in os.walk(source_root):
        if files:
            return True
    return False


# ─── Orphaned profile files ───────────────────────────────────────────────────


def _known_profiles():
    try:
        from aqt import mw

        return set(mw.pm.profiles() or [])
    except Exception:
        return set()


def adopt_orphaned_profile_files(current_profile):
    """
    Renaming an Anki profile leaves ``settings_<old>.json`` behind and Onigiri
    starts from defaults under the new name. If exactly one leftover file
    belongs to a profile Anki no longer knows about, it is that rename - so
    carry it over instead of letting the user think the update ate it.

    Returns the list of adopted filenames.
    """
    if not current_profile:
        return []

    root = user_files_dir()
    known = _known_profiles()
    if known != {current_profile}:
        # With multiple profiles, an orphan could belong to a deleted profile
        # rather than this renamed one. Never mix two learners' data by guess.
        return []

    try:
        entries = os.listdir(root)
    except OSError:
        return []
    owners = [entry[len("settings_"):-len(".json")]
              for entry in entries if entry.startswith("settings_") and entry.endswith(".json")
              and entry[len("settings_"):-len(".json")] not in known | {"default"}]
    if len(owners) != 1 or os.path.exists(os.path.join(root, f"settings_{current_profile}.json")):
        return []
    owner = owners[0]
    adopted = []
    for prefix in CRITICAL_PREFIXES:
        target = os.path.join(root, f"{prefix}{current_profile}.json")
        if os.path.exists(target):
            continue

        orphan = f"{prefix}{owner}.json"
        if not os.path.isfile(os.path.join(root, orphan)):
            continue

        try:
            shutil.copy2(os.path.join(root, orphan), target)
            adopted.append(orphan)
        except OSError as exc:
            print(f"Onigiri storage: could not adopt {orphan}: {exc}")

    return adopted


# ─── Startup integrity check ──────────────────────────────────────────────────


def stale_anki_backup_path():
    """
    Anki stages ``user_files`` at ``addons21/files_backup`` during an update -
    one shared path for every add-on, not one per add-on. A leftover folder
    there means an install died halfway, and the next add-on install can
    restore those files into the wrong add-on.
    """
    path = os.path.join(os.path.dirname(addon_root()), "files_backup")
    return path if os.path.isdir(path) else None


def run_startup_check(profile_name=None):
    """
    Returns a list of human-readable messages about anything repaired or worth
    warning about. Safe to call on every profile open.
    """
    messages = []

    adopted = adopt_orphaned_profile_files(profile_name)
    if adopted:
        messages.append(
            "Your Anki profile appears to have been renamed. Onigiri carried "
            f"your settings over from: {', '.join(adopted)}"
        )

    if looks_wiped() and mirror_has_data():
        restored = restore_from_mirror()
        if restored:
            messages.append(
                f"Onigiri's data folder was empty, so {restored} file(s) were "
                "restored from the backup kept outside the add-on folder. This "
                "usually means the add-on was reinstalled by hand instead of "
                "through Anki's updater."
            )

    stale = stale_anki_backup_path()
    if stale:
        messages.append(
            "Anki left an unfinished add-on update behind at "
            f"'{stale}'. Installing another add-on may restore those files into "
            "the wrong place - it is worth deleting that folder."
        )

    # Integrity-check messages have variable paths/profile names. Preserve
    # those values while translating the source-authored explanation.
    if adopted:
        messages[0] = _notice_copy("storage_profile_renamed", messages[0],
                                  {"profiles": ", ".join(adopted)})
    for index, message in enumerate(messages):
        if message.startswith("Onigiri's data folder was empty"):
            messages[index] = _notice_copy("storage_folder_restored", message,
                                          {"amount": restored})
        elif message.startswith("Anki left an unfinished"):
            messages[index] = _notice_copy("storage_stale_update", message,
                                          {"path": stale})
    messages.extend(take_notices())
    return messages
