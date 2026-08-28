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

import json
import os
import shutil
import time

# Files whose loss would visibly undo the user's setup. Everything else in
# user_files (caches, generated icons) can be rebuilt, so it stays out of the
# external mirror to keep the copy cheap.
CRITICAL_PREFIXES = (
    "settings_",
    "gamification_",
    "onigimon_",
    "hexagon_land_",
    "mochi_history_",
)
CRITICAL_SUBDIRS = ("hashi_notes", "user_themes", "prep_station", "pomodoro")

# Recovery notices collected during load, drained once by the startup check so
# the user hears about a rescued file instead of quietly seeing defaults.
_pending_notices = []

_MAX_SNAPSHOTS = 5
_SNAPSHOT_INTERVAL = 60 * 60 * 12  # at most two dated snapshots per file/day


def addon_root():
    return os.path.dirname(os.path.abspath(__file__))


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
    return notices


def _note(message):
    print(f"Onigiri storage: {message}")
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
    if not _looks_usable(current):
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
    _PENDING_WRITES[path] = data

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
        flush_pending(path)
    return True


def pending_payload(path):
    """The queued-but-unwritten payload for ``path``, or None."""
    return _PENDING_WRITES.get(path)


def flush_pending(path=None):
    """Write queued payloads. Without ``path``, flushes every pending file."""
    paths = [path] if path is not None else list(_PENDING_WRITES.keys())
    for target in paths:
        data = _PENDING_WRITES.pop(target, None)
        if data is None:
            continue
        atomic_write_json(target, data)


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


def read_json(path, default=None, label=None):
    """
    Load ``path``, falling back through ``.bak``, dated snapshots and the
    external mirror before giving up.

    Only returns ``default`` when every candidate is gone or unreadable, and
    says so out loud rather than letting a corrupt file read as a fresh start.
    """
    label = label or os.path.basename(path)

    # A write queued by schedule_write_json() is newer than anything on disk.
    queued = _PENDING_WRITES.get(path)
    if queued is not None:
        try:
            return json.loads(json.dumps(queued))
        except Exception:
            flush_pending(path)

    candidates = [(path, None), (path + ".bak", "backup file")]
    candidates.extend((snap, "dated snapshot") for snap in _snapshots_for(path))
    mirrored = _mirror_path_for(path)
    if mirrored:
        candidates.append((mirrored, "external backup"))

    fallback = None  # a candidate that parses but is empty
    for candidate, source in candidates:
        data, ok = _try_load(candidate)
        if not ok:
            continue
        if _looks_usable(data):
            if source:
                _note(
                    f"{label} was unreadable, so it was restored from the {source}."
                )
                _repair(path, candidate)
            return data
        if fallback is None:
            fallback = data

    if fallback is not None:
        return fallback

    if os.path.exists(path):
        # The file is there but nothing in the chain parsed - do not overwrite
        # it on the next save without keeping the evidence around.
        _quarantine(path)
        _note(
            f"{label} was damaged and no backup could be read. "
            "Onigiri fell back to defaults; the damaged file was kept as .corrupt."
        )
    return default if default is not None else {}


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
    directory = _snapshot_dir()
    try:
        entries = [
            os.path.join(directory, entry)
            for entry in os.listdir(directory)
            if entry.startswith(name + ".") and entry.endswith(".json")
        ]
    except OSError:
        return []
    return sorted(entries, key=os.path.getmtime, reverse=True)


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
    target = os.path.join(_snapshot_dir(), f"{os.path.basename(path)}.{stamp}.json")
    try:
        shutil.copy2(path, target)
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
    if relative.startswith(os.pardir):
        return None
    return os.path.join(external_backup_dir(), "user_files", relative)


def mirror_file(path):
    target = _mirror_path_for(path)
    if not target:
        return
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(path, target)
    except OSError as exc:
        print(f"Onigiri storage: could not mirror {path}: {exc}")


def mirror_all():
    """Copy every critical file to the external mirror. Cheap enough to run
    on profile close, which is the last moment we are sure the data is final."""
    root = user_files_dir()
    copied = 0
    for current, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith((".tmp", ".bak", ".corrupt", ".log")):
                continue
            source = os.path.join(current, name)
            if not _is_critical(source):
                continue
            target = _mirror_path_for(source)
            if not target:
                continue
            try:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                shutil.copy2(source, target)
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
    if not known:
        # Without the profile list we cannot tell a rename from a second
        # profile, and guessing wrong would leak one profile's setup into
        # another. Do nothing.
        return []

    adopted = []
    for prefix in CRITICAL_PREFIXES:
        target = os.path.join(root, f"{prefix}{current_profile}.json")
        if os.path.exists(target):
            continue

        orphans = []
        try:
            entries = os.listdir(root)
        except OSError:
            continue
        for entry in entries:
            if not entry.startswith(prefix) or not entry.endswith(".json"):
                continue
            owner = entry[len(prefix) : -len(".json")]
            if owner and owner not in known:
                orphans.append(entry)

        if len(orphans) != 1:
            # Zero means nothing to carry over; more than one means we cannot
            # tell which profile was renamed into this one.
            continue

        try:
            shutil.copy2(os.path.join(root, orphans[0]), target)
            adopted.append(orphans[0])
        except OSError as exc:
            print(f"Onigiri storage: could not adopt {orphans[0]}: {exc}")

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

    messages.extend(take_notices())
    return messages
