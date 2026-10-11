"""Build a distributable without personal saves or the attached snapshots.

Usage: python3 tools/build_addon.py /absolute/path/Onigiri.ankiaddon
"""
from pathlib import Path
import argparse
import json
import zipfile


ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIRS = {
    "api", "core", "decks", "dialogs", "gamification", "integrations",
    "rendering", "settings_web", "study_tools", "system_files", "things_stats",
    "things_theme", "ui_kit", "web",
}
RELEASE_FILES = {"__init__.py", "sidebar_api.py", "manifest.json", "LICENSE.txt", "README.md"}


def build_addon(destination, root=ROOT):
    root = Path(root).resolve()
    destination = Path(destination).resolve()
    if destination == root or root in destination.parents:
        raise ValueError("Write the release outside the installed add-on directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for source in sorted(root.rglob("*")):
                if not source.is_file() or source.is_symlink():
                    continue
                relative = source.relative_to(root)
                if relative.parts[0] not in RELEASE_DIRS and relative.as_posix() not in RELEASE_FILES:
                    continue
                if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
                    continue
                if source.suffix in {".pyc", ".bak", ".log", ".corrupt", ".ankiaddon"} or ".tmp" in source.name:
                    continue
                archive.write(source, relative.as_posix())
            # Anki keeps each user's meta.json and existing user_files when
            # upgrading. Never distribute the developer's values for either.
            archive.writestr("config.json", json.dumps({}))
            archive.writestr("user_files/README.txt",
                             "Onigiri stores your personal settings and imported files here.\n"
                             "Anki preserves this folder when updating the same add-on.\n")
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    print(build_addon(args.destination))
