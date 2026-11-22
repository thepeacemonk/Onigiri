"""Release switching without importing Anki, Qt, or a release's settings code.

Downloads/staging happen while Anki runs. The host commits only at aboutToQuit,
after profile writers finish, so two generations of code never run together.
"""
import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

PACKAGE = "1011095603"
RELEASES = {
    # Stable picker identity; resolve the current Bento release on each switch.
    "2.0-Bento": None,
    "1.0-Sake-Nigiri": ("v.1.0", "d559daeb6c8e5c34b053e66fb7e2fcdf20fd63a68a3772d461e952811b8e7e16"),
    "0.9-legacy": ("v1.0.9-beta", "87663e021207f62a2f01619c88e519e3a90a9a0dc0cf284e81fdd0ae544303b7"),
}
MAX_DOWNLOAD = 64 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
RELEASES_API = "https://api.github.com/repos/thepeacemonk/Onigiri/releases"
BENTO_TAG = re.compile(r"v\.?([0-9]+(?:\.[0-9]+)+-Bento)", re.IGNORECASE)
BOOT_MARKER = "# Onigiri version controls (retained across release switches)"
BOOT = '\n' + BOOT_MARKER + '\nfrom .version_manager import setup as _setup_version_controls\n_setup_version_controls(__file__)\n'


def read_json(path):
    with Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object: " + str(path))
    return data


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".onigiri-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def control_dir(root):
    return Path(root).resolve().parent.parent / "onigiri_backups" / "version_switches" / PACKAGE


def installed_version(root):
    return str(read_json(Path(root) / "manifest.json").get("version", "Unknown"))


def installed_release(root):
    """Map historical names and Bento maintenance releases to picker choices."""
    version = installed_version(root)
    if version in RELEASES:
        return version
    if version.casefold().endswith("-bento"):
        return "2.0-Bento"
    return {"1.0 - Sake nigiri": "1.0-Sake-Nigiri",
            "1.0.9-beta": "0.9-legacy"}.get(version)


def release_label(target):
    return "Bento" if target == "2.0-Bento" else target


def resolve_release(target):
    """Resolve Bento afresh; historical releases retain their pinned checksums.

    A lookup or verification failure cancels the switch instead of silently
    downloading an older Bento. GitHub supplies the published asset digest.
    """
    if target not in RELEASES:
        raise ValueError("Unsupported Onigiri release")
    if target != "2.0-Bento":
        tag, digest = RELEASES[target]
        version = {"1.0-Sake-Nigiri": "1.0 - Sake nigiri", "0.9-legacy": "1.0.9-beta"}[target]
        return tag, digest, version
    candidates = []
    for page in range(1, 11):
        request = urllib.request.Request(
            RELEASES_API + "?per_page=100&page=" + str(page),
            headers={"User-Agent": "Onigiri-Version-Manager", "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28"})
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError("Release metadata exceeds the size limit")
        releases = json.loads(raw)
        if not isinstance(releases, list):
            raise ValueError("Could not read the published Bento releases")
        for release in releases:
            match = BENTO_TAG.fullmatch(release.get("tag_name", ""))
            if match and not release.get("draft") and not release.get("prerelease"):
                version = match.group(1)
                number = tuple(int(part) for part in version.split("-")[0].split("."))
                candidates.append((number, release, version))
        if len(releases) < 100:
            break
    else:
        raise ValueError("Could not finish checking the published Bento releases")
    if not candidates:
        raise ValueError("No published stable Bento release was found")
    _, release, version = max(candidates, key=lambda candidate: candidate[0])
    assets = [asset for asset in release.get("assets", [])
              if asset.get("name") == "Onigiri.ankiaddon" and asset.get("state") == "uploaded"]
    if len(assets) != 1:
        raise ValueError("The latest Bento release has no complete Onigiri download")
    digest = assets[0].get("digest") or ""
    if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
        raise ValueError("The latest Bento download has no SHA-256 checksum; switch cancelled")
    if assets[0].get("size", 0) > MAX_DOWNLOAD:
        raise ValueError("The release download exceeds the size limit")
    return release["tag_name"], digest.split(":", 1)[1].lower(), version


def updates_enabled(root):
    path = Path(root) / "meta.json"
    return bool(read_json(path).get("update_enabled", True)) if path.exists() else True


def set_updates_enabled(root, enabled):
    """Anki's authoritative flag; preserve config and all unrelated metadata."""
    path = Path(root) / "meta.json"
    meta = read_json(path) if path.exists() else {}
    meta["update_enabled"] = bool(enabled)
    write_json(path, meta)


def pending_switch(root):
    path = control_dir(root) / "pending.json"
    return read_json(path) if path.exists() else None


def _stage_path(root, pending):
    path = Path(pending["stage"]).resolve()
    if path.parent != control_dir(root).resolve() or not path.name.startswith("staged-"):
        raise ValueError("Invalid staged installation path")
    if pending.get("target") not in RELEASES:
        raise ValueError("Unsupported Onigiri release")
    return path


def cancel_switch(root):
    pending = pending_switch(root)
    if pending:
        path = _stage_path(root, pending)
        (control_dir(root) / "pending.json").unlink()
        shutil.rmtree(path, ignore_errors=True)


def _extract(archive, stage, expected_version):
    with zipfile.ZipFile(archive) as package:
        entries = package.infolist()
        if len(entries) > 12000 or sum(item.file_size for item in entries) > MAX_EXPANDED:
            raise ValueError("Release archive exceeds the extraction limit")
        seen = set()
        for item in entries:
            name = item.filename
            parts = PurePosixPath(name).parts
            if (not parts or name.startswith("/") or "\\" in name
                    or ".." in parts or ":" in name or name in seen
                    or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError("Unsafe release archive entry: " + name)
            seen.add(name)
            # Published packages have no user_files. Never import somebody
            # else's saves, Anki metadata, cache, or macOS resource forks.
            if parts[0] in {"user_files", "__MACOSX"} or name == "meta.json" or "__pycache__" in parts:
                continue
            package.extract(item, stage)
    manifest = read_json(stage / "manifest.json")
    if str(manifest.get("package")) != PACKAGE or manifest.get("version") != expected_version:
        raise ValueError("The package does not match the selected Onigiri release")
    if not (stage / "__init__.py").is_file():
        raise ValueError("The release has no add-on entry point")


def prepare_release(root, target, *, archive=None):
    """Return a complete, verified stage; never modify the active installation."""
    if target not in RELEASES:
        raise ValueError("Unsupported Onigiri release")
    folder = control_dir(root)
    folder.mkdir(parents=True, exist_ok=True)
    stage = folder / ("staged-" + uuid.uuid4().hex)
    stage.mkdir()
    downloaded = stage / "download.ankiaddon"
    try:
        tag, digest, expected_version = resolve_release(target)
        if archive is None:
            url = "https://github.com/thepeacemonk/Onigiri/releases/download/" + tag + "/Onigiri.ankiaddon"
            request = urllib.request.Request(url, headers={"User-Agent": "Onigiri-Version-Manager"})
            with urllib.request.urlopen(request, timeout=45) as response, downloaded.open("wb") as output:
                count = 0
                while True:
                    chunk = response.read(256 * 1024)
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > MAX_DOWNLOAD:
                        raise ValueError("The release download exceeds the size limit")
                    output.write(chunk)
            archive = downloaded
        archive = Path(archive)
        if archive.stat().st_size > MAX_DOWNLOAD or hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
            raise ValueError("Release checksum verification failed; no files were changed")
        _extract(archive, stage, expected_version)
        downloaded.unlink(missing_ok=True)
        # Keep the agreed product names in the historical menu/version labels,
        # while the verified download still comes from its original tag.
        manifest = read_json(stage / "manifest.json")
        if target != "2.0-Bento":
            manifest["version"] = target
        write_json(stage / "manifest.json", manifest)
        # New Bento packages already carry a manager. Retain these current
        # controls (including fixes) when switching to any packaged release.
        if (stage / "version_manager").exists():
            shutil.rmtree(stage / "version_manager")
        shutil.copytree(Path(__file__).parent, stage / "version_manager",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        entry = stage / "__init__.py"
        source = entry.read_text(encoding="utf-8-sig")
        if BOOT_MARKER not in source:
            entry.write_text(BOOT + source, encoding="utf-8")
        _retain_menu_access(stage)
        if target != "2.0-Bento":
            _protect_legacy_progress(stage)
        return stage
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def _retain_menu_access(stage):
    """The controller alone does not add an item to historical Onigiri menus."""
    stage = Path(stage)
    menu = stage / "menu_buttons.py"
    relative = "."
    if not menu.is_file():
        menu = stage / "ui_kit/menu_buttons.py"
        relative = ".."
    text = menu.read_text(encoding="utf-8-sig")
    marker = "# Retain Select version in this release's Onigiri menu."
    if marker in text:
        return
    anchor = "    mw.form.menubar.addMenu(onigiri_menu)"
    if text.count(anchor) != 1:
        raise ValueError("The release menu changed; switch cancelled to preserve version access")
    addition = ("    " + marker + "\n    from " + relative +
                "version_manager import add_menu_action\n    add_menu_action(onigiri_menu)\n")
    menu.write_text(text.replace(anchor, addition + anchor), encoding="utf-8")


def _protect_legacy_progress(stage):
    """Older dataclasses reject newer achievement fields and can reset progress."""
    game = stage / "gamification" / "gamification.py"
    text = game.read_text(encoding="utf-8")
    text = text.replace("from dataclasses import dataclass, asdict", "from dataclasses import dataclass, asdict\nfrom ..version_manager.compat import from_dict, payload, merge_payload")
    for old, new in (("AchievementData(**ach)", "from_dict(AchievementData, ach)"),
                     ("DailySpecialData(**special)", "from_dict(DailySpecialData, special)"),
                     ("asdict(ach)", "payload(ach)"), ("asdict(special)", "payload(special)"),
                     ("final_data.update(new_data)", "final_data = merge_payload(final_data, new_data)")):
        if old not in text:
            raise ValueError("The legacy progress format changed; switch cancelled")
        text = text.replace(old, new)
    game.write_text(text, encoding="utf-8")


def queue_switch(root, target, stage, context):
    if pending_switch(root):
        raise ValueError("A version switch is already pending")
    data = {"target": target, "target_version": installed_version(stage), "stage": str(stage),
            "source_version": installed_version(root), "context": context}
    _stage_path(root, data)
    # Both writes precede replacing any code. Failure leaves this installation
    # intact; a pending switch is removable from the dialog.
    write_json(control_dir(root) / "pending.json", data)
    try:
        set_updates_enabled(root, False)
    except Exception:
        (control_dir(root) / "pending.json").unlink(missing_ok=True)
        raise


def commit_switch(root, context=None):
    """Called at process exit, after saves. Retain a full external installation.

    A failed second rename rolls back to the original directory. Backups are
    never deleted. Collection/profile configuration is read-only throughout.
    """
    root = Path(root).resolve()
    pending = pending_switch(root)
    if not pending:
        return None
    stage = _stage_path(root, pending)
    if installed_version(root) != pending["source_version"]:
        raise ValueError("Onigiri changed since the switch was prepared; cancel and choose again")
    if not (stage / "version_manager" / "service.py").is_file():
        raise ValueError("The prepared release is incomplete; cancel and choose again")
    saved = root / "user_files"
    if (stage / "user_files").exists():
        shutil.rmtree(stage / "user_files")
    if saved.exists():
        shutil.copytree(saved, stage / "user_files")
    for name in ("meta.json", "onigiri_layout.json", ".onigiri_sync_state.json"):
        if (root / name).exists():
            shutil.copy2(root / name, stage / name)
    # Keep the user's Anki metadata/config, while dropping compatibility bounds
    # from the current release. All three verified historical manifests omit
    # bounds; AnkiWeb can repopulate them in the usual way on a manual check.
    meta_path = stage / "meta.json"
    meta = read_json(meta_path) if meta_path.exists() else {}
    for key in ("min_point_version", "max_point_version"):
        meta.pop(key, None)
    meta["update_enabled"] = False
    target_version = installed_version(stage)
    meta["human_version"] = target_version
    write_json(meta_path, meta)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = control_dir(root) / ("backup-" + stamp + "-" + uuid.uuid4().hex[:8])
    backup.mkdir()
    write_json(backup / "context.json", context if context is not None else pending["context"])
    write_json(backup / "switch.json", {"from": pending["source_version"], "to": target_version})
    original = backup / "installation"
    os.replace(root, original)
    try:
        os.replace(stage, root)
    except BaseException:
        os.replace(original, root)
        raise
    # A cleanup failure must not label a completed installation as failed.
    try:
        (control_dir(root) / "pending.json").unlink(missing_ok=True)
    except OSError:
        pass
    return backup
