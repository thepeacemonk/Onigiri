"""Screenshot Onigiri's PyQt screens (settings dialog etc.) without Anki.

    python tools/shoot_qt.py settings --tab 0 --out .shots/settings_0.png

Runs the real SettingsDialog class under an offscreen Qt platform with a
fake mw (same fakes as the test suite), grabs the rendered widget via
QWidget.grab() and saves a PNG. No Anki launch involved.
"""

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR = os.path.join(REPO_ROOT, "tests")
sys.path.insert(0, TESTS_DIR)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _prepare_fontdir():
    """Offscreen Qt ships no fonts and QT_QPA_FONTDIR is non-recursive.

    Flatten every TTF bundled with the add-on (including fonts inside
    subfolders such as system_fonts/Poppins/) into one cache directory
    so text rasterizes with the real families instead of tofu/serif.
    """
    import shutil

    src_root = os.path.join(REPO_ROOT, "system_files", "fonts", "system_fonts")
    cache = os.path.join(REPO_ROOT, ".shots", "_qt_fonts")
    os.makedirs(cache, exist_ok=True)
    for dirpath, _dirnames, filenames in os.walk(src_root):
        for name in filenames:
            if name.lower().endswith((".ttf", ".otf")):
                dest = os.path.join(cache, name)
                src = os.path.join(dirpath, name)
                if not os.path.exists(dest) or os.path.getmtime(dest) < os.path.getmtime(src):
                    shutil.copy2(src, dest)
    return cache


os.environ.setdefault("QT_QPA_FONTDIR", _prepare_fontdir())

from conftest import load_module  # noqa: E402
from fake_anki import make_render_mw  # noqa: E402


def inject_mw():
    """Wire the fake collection into every module the dialog touches."""
    mw = make_render_mw()

    modules = [
        "config",
        "themes",
        "translations",
        "heatmap",
        "patcher",
        "onigiri_renderer",
        "decks.tree_updater",
    ]
    for name in modules:
        load_module(name).mw = mw

    # Import the full dialog (pulls in every settings submodule), then
    # rebind mw on all of them - each submodule holds its own global.
    load_module("settings._legacy")

    import sys as _sys

    prefix = "onigiri_under_test.settings"
    for name, mod in list(_sys.modules.items()):
        if name.startswith(prefix) and mod is not None:
            try:
                mod.mw = mw
            except (AttributeError, TypeError):
                pass
    return mw


def ensure_qapp():
    from aqt.qt import QApplication, QFont

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    # Offscreen Qt picks a serif fallback; the real UI runs Poppins.
    font = QFont("Poppins")
    font.setPointSize(10)
    app.setFont(font)
    return app


def shoot_settings(tab_index, out_path, width=None, height=None):
    mw = inject_mw()
    app = ensure_qapp()
    mw.app = app

    settings_dialog_cls = load_module("settings._legacy").SettingsDialog
    dialog = settings_dialog_cls(parent=None, addon_path=REPO_ROOT,
                                 initial_page_index=tab_index)
    if width and height:
        dialog.resize(width, height)
    dialog.show()
    for _ in range(8):
        app.processEvents()

    pixmap = dialog.grab()
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    ok = pixmap.save(out_path)
    dialog.close()
    if not ok:
        sys.exit(f"failed to save {out_path}")
    print(f"shot  -> {out_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("screen", choices=("settings",))
    parser.add_argument("--tab", type=int, default=0,
                        help="initial_page_index of the settings dialog")
    parser.add_argument("--viewport", default=None,
                        help="WxH window size override, e.g. 1280x800")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    size = None
    if args.viewport:
        size = tuple(int(x) for x in args.viewport.lower().split("x"))
    out_path = args.out or os.path.join(
        ".shots", f"{args.screen}_tab{args.tab}.png"
    )

    if args.screen == "settings":
        if size:
            shoot_settings(args.tab, out_path, size[0], size[1])
        else:
            shoot_settings(args.tab, out_path)


if __name__ == "__main__":
    main()
