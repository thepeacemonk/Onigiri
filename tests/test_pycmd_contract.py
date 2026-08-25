"""Contract test: every pycmd bridge command has both halves.

Two failure directions are checked:

1. *Emitted but never handled* - a JS call into the void. This is the
   silent-bug class: clicking does nothing, no error anywhere.
2. *Handled but never emitted* - dead handler code rotting until
   someone wires it up expecting old behaviour.

Extraction is static:

- strong handled: ``cmd.startswith("prefix")`` in the Python bridge
- weak handled:   the command literal appears in a Python bridge file
                  (equality checks, tuple membership, dict dispatch).
                  translations.py is excluded - UI label strings would
                  false-positive.
- emitted:        literal ``pycmd("...")`` calls in web/*.js plus
                  inline pycmd occurrences inside generated HTML
                  strings in Python sources

Commands that are only weakly handled are pinned in EXPECTED_SOFT so
handler removal or emitter drift is noticed in review instead of
silently passing.

Scope: Onigiri-owned command namespaces only; native Anki commands are
out of scope.
"""

import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB_ROOT = os.path.join(REPO_ROOT, "web")

SKIP_DIRS = {".venv", ".git", "__pycache__", ".shots", "user_files", "tests", "tools"}
NON_BRIDGE_FILES = {"translations.py"}

NAMESPACE_RE = re.compile(
    r"^(?:onigiri_|onigimon|hex_land|hashi|save(?:Deck|Sidebar)|"
    r"buy_item|equip_item|redeem_code|open_link)"
)

WILDCARD_HANDLERS = {"onigiri_"}

# Handlers whose emitters are data-driven: the command string is built
# in Python templates (context menus, icon chooser, deck sort menu...)
# and fired via pycmd(item.command) in JS, so no literal
# pycmd("<token>") call exists. If one of these features is removed,
# drop it here too.
DATA_DRIVEN_HANDLERS = {
    "onigiri_collapse",
    "onigiri_ctx_bulk_delete",
    "onigiri_ctx_bulk_favorite",
    "onigiri_ctx_bulk_mark",
    "onigiri_ctx_bulk_unfavorite",
    "onigiri_ctx_change_icon",
    "onigiri_ctx_copy_id",
    "onigiri_ctx_delete",
    "onigiri_ctx_export",
    "onigiri_ctx_mark",
    "onigiri_ctx_move_to",
    "onigiri_ctx_options",
    "onigiri_ctx_rename",
    "onigiri_ctx_subdeck",
    "onigiri_icon_chooser_add_icon",
    "onigiri_icon_chooser_add_image",
    "onigiri_icon_chooser_delete_icon",
    "onigiri_icon_chooser_reset",
    "onigiri_icon_chooser_save",
    "onigiri_move_decks",
    "onigiri_show_transfer_window",
    "onigiri_sort",
    "onigiri_toggle_favorite",
    "onigimon_interact",
    "onigimon_rename",
    "onigimon_status",
    "open_link",
    "saveDeckFocusState",
}

# Commands dispatched without cmd.startswith() (equality checks, tuple
# membership, ...). Kept explicit so removing their handler or emitter
# shows up in review.
EXPECTED_SOFT = {
    "hex_land_buy",
    "hex_land_guide",
    "onigimon_comet_shop",
    "onigimon_market_gift",
    "onigiri_create_deck",
    "onigiri_learner_stats_refresh_fallback",
    "onigiri_ui_close",
    "onigiri_ui_open",
    "onigiri_welcome_dismissed",
    "redeem_code",
}


def _repo_py_files():
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def _web_js_files():
    for dirpath, _dirnames, filenames in os.walk(WEB_ROOT):
        for name in filenames:
            if name.endswith(".js"):
                yield os.path.join(dirpath, name)


def _normalize(token: str) -> str:
    """Reduce 'onigiri_drag_drop:{json}' / 'buy_item:${id}' to its prefix."""
    return re.split(r"[:${]", token, 1)[0].strip()


def extract_handled_strong():
    pattern = re.compile(r"\bcmd\.startswith\(\s*[\"']([^\"']+)[\"']")
    handled = set()
    for path in _repo_py_files():
        with open(path, encoding="utf-8", errors="ignore") as f:
            for match in pattern.finditer(f.read()):
                prefix = _normalize(match.group(1))
                if prefix in WILDCARD_HANDLERS:
                    continue
                if NAMESPACE_RE.match(prefix):
                    handled.add(prefix)
    return handled


def _py_texts():
    for path in _repo_py_files():
        rel = os.path.basename(path)
        with open(path, encoding="utf-8", errors="ignore") as f:
            yield rel, f.read()


def extract_handled_weak(tokens):
    """Which tokens appear as literals in non-translation Python files?"""
    weak = set()
    for token in tokens:
        literal = re.compile(rf"[\"']{re.escape(token)}(?:[:\"'])")
        for rel, text in _py_texts():
            if rel in NON_BRIDGE_FILES:
                continue
            if literal.search(text):
                weak.add(token)
                break
    return weak


def extract_emitted():
    emitted = set()
    js_call = re.compile(r"pycmd\(\s*[\"'`]([^\"'`]+)[\"'`]")
    for path in _web_js_files():
        with open(path, encoding="utf-8", errors="ignore") as f:
            for match in js_call.finditer(f.read()):
                token = _normalize(match.group(1))
                if NAMESPACE_RE.match(token):
                    emitted.add(token)

    # Inline pycmd('...') inside generated HTML strings in Python files.
    py_call = re.compile(r"pycmd\(\s*(?:&quot;|[\"'])((?:(?!&quot;)[^\"'\\])+)")
    for _rel, text in _py_texts():
        for match in py_call.finditer(text):
            token = _normalize(match.group(1))
            if NAMESPACE_RE.match(token):
                emitted.add(token)
    return emitted


def test_no_orphan_emissions():
    """Emitted commands must be handled strongly or weakly - no orphans."""
    emitted = extract_emitted()
    strong = extract_handled_strong()
    weak = extract_handled_weak(emitted - strong)

    orphans = sorted(emitted - strong - weak)
    assert not orphans, (
        "pycmd commands emitted but NEVER HANDLED (clicks silently do "
        f"nothing): {orphans}"
    )


def test_soft_handlers_are_pinned():
    """Weakly-handled commands must stay pinned in EXPECTED_SOFT."""
    emitted = extract_emitted()
    strong = extract_handled_strong()
    soft = (emitted - strong) & (extract_handled_weak(emitted - strong))

    drifted = sorted(soft ^ EXPECTED_SOFT)
    assert not drifted, (
        "Soft-handled command surface changed; update EXPECTED_SOFT "
        f"after review. Diff: {drifted}"
    )


def test_no_dead_handlers():
    """Every strongly-handled command must have a static emitter."""
    handled = extract_handled_strong()
    emitted = extract_emitted()
    dead = sorted(handled - emitted - EXPECTED_SOFT - DATA_DRIVEN_HANDLERS)
    assert not dead, (
        "handled pycmd commands with no static emitter (dead handlers): "
        f"{dead}"
    )


def test_bridge_has_meaningful_surface():
    """Guard against the extraction regexes rotting to empty sets."""
    assert len(extract_handled_strong()) >= 40
    assert len(extract_emitted()) >= 30
