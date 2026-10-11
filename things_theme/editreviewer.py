"""Anki Design — inline reviewer editing.

Replaces the standalone `EditCurrent` QMainWindow with editing-in-place:
the card's field text becomes contenteditable directly inside the reviewer
webview, with a small floating toolbar (Done / Cancel / Open in full editor
/ basic formatting). The card stays exactly where it was; only the field
spans gain an outline and a caret.

How it works
============

1.  `card_will_show` post-processes the rendered Q/A HTML, wrapping each
    non-empty field's value in `<span data-ba-field="Name">…</span>`.
    Wrapping happens longest-first via placeholder substitution so a short
    field's value can't accidentally match inside a longer field.

2.  `pycmd('edit')` is captured by intercepting `mw.onEditCurrent` (the
    one entry point both the pencil button and the `e` shortcut go
    through after our `state_shortcuts_will_change` rewrite). The patched
    function asks the reviewer webview to enter inline edit mode.

3.  Inside the webview, `web/reviewer.js`:
      • flips every `[data-ba-field]` span to `contenteditable="true"`
      • shows a floating toolbar at the bottom (Cmd+Return saves)
      • captures escape / cmd+s / cmd+enter / cmd+. as save/cancel
      • disables the click-to-reveal handler while editing

4.  On save, JS collects each span's `innerHTML` and posts back via
    `pycmd('ba:edit-save:<json>')`. We update the note, persist via
    `mw.col.update_note`, then re-render the current card so the changes
    are visible in the rendered template too.

5.  The "Open in full editor" button posts `pycmd('ba:edit-full')`, which
    saves any pending inline changes and then opens Anki's native
    `EditCurrent` dialog as the escape hatch.

Fallbacks
---------
Fields that don't appear literally in the rendered template (cloze,
`{{type:Field}}`, `{{tts:Field}}`, etc.) are silently skipped during
wrapping. JS notices when no `[data-ba-field]` spans exist and routes
straight to the full editor instead of presenting an empty edit mode.
"""

from __future__ import annotations

import html
import json
from typing import Dict, List, Tuple

from aqt import gui_hooks, mw


# --------------------------------------------------------------------------- #
# Render-time: wrap field values so JS can locate them.
# --------------------------------------------------------------------------- #
def _field_pairs(card) -> List[Tuple[str, str]]:
    """Return [(field_name, field_value), …] for the current note, longest
    value first so substring-overlapping fields wrap in a safe order."""
    try:
        note = card.note()
    except Exception:
        return []
    try:
        keys = list(note.keys())
    except Exception:
        return []
    pairs: List[Tuple[str, str]] = []
    for name in keys:
        try:
            val = note[name]
        except Exception:
            continue
        if val:
            pairs.append((str(name), str(val)))
    pairs.sort(key=lambda kv: -len(kv[1]))
    return pairs


def _wrap_fields(text: str, card, kind: str) -> str:
    """For each non-empty field, wrap its FIRST literal occurrence in the
    rendered HTML with a marker div. Idempotent: if the wrap is already
    present (we re-render after a save) we skip that field.

    Strategy: substitute each field's value with a unique placeholder in
    a single first pass, then swap placeholders for the wrapped divs in
    a second pass. This stops nested matches (Field B's value contains
    Field A's value as a substring) from producing wrap-inside-wrap.
    """
    if kind not in ("reviewQuestion", "reviewAnswer", "previewQuestion",
                    "previewAnswer"):
        return text
    if not text or not card:
        return text

    pairs = _field_pairs(card)
    if not pairs:
        return text

    placeholders: Dict[str, Tuple[str, str]] = {}
    for idx, (name, val) in enumerate(pairs):
        marker = f"\x00BA_FIELD_{idx}\x00"
        pos = text.find(val)
        if pos < 0:
            continue
        text = text[:pos] + marker + text[pos + len(val):]
        placeholders[marker] = (name, val)

    for marker, (name, val) in placeholders.items():
        safe_name = html.escape(name, quote=True)
        # We wrap with a DIV (not SPAN) because Anki's webview.js
        # registers a document-level keydown handler that calls
        # preventDefault on Backspace unless the event target is an
        # <input>, <textarea>, or a contenteditable <div>. A
        # contenteditable <span> doesn't satisfy that check, so Backspace
        # gets swallowed and editing feels broken. The CSS forces inline
        # flow so the layout reads the same as the original span wrap.
        wrapped = (
            f'<div data-ba-field="{safe_name}" '
            f'class="ba-rv-field">{val}</div>'
        )
        text = text.replace(marker, wrapped)
    return text


# --------------------------------------------------------------------------- #
# Shortcut rewrite: route "e" / "ㄷ" to our inline editor.
# --------------------------------------------------------------------------- #
def _on_state_shortcuts_will_change(state: str, shortcuts: list) -> None:
    if state != "review":
        return
    try:
        for i, item in enumerate(shortcuts):
            if not isinstance(item, tuple) or len(item) != 2:
                continue
            key, _fn = item
            if key in ("e", "ㄷ"):
                shortcuts[i] = (key, _enter_inline_edit)
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Enter / exit edit mode.
# --------------------------------------------------------------------------- #
def _inline_edit_enabled() -> bool:
    try:
        cfg = mw.addonManager.getConfig(__name__.split(".")[0]) or {}
        return bool(cfg.get("inline_edit", True))
    except Exception:
        return True


def _enter_inline_edit() -> None:
    """Ask the reviewer webview to enter inline edit mode. If anything
    goes wrong (no reviewer, no card, or the JS hasn't loaded yet) — or
    the user switched inline editing off — open Anki's native EditCurrent
    dialog instead."""
    if not _inline_edit_enabled():
        _open_full_editor()
        return
    rv = getattr(mw, "reviewer", None)
    if rv is None or getattr(rv, "card", None) is None:
        _open_full_editor()
        return
    web = getattr(rv, "web", None)
    if web is None:
        _open_full_editor()
        return
    try:
        web.eval(
            "(function(){"
            "if (window.__baEnterEdit) { window.__baEnterEdit(); }"
            "else { pycmd('ba:edit-full'); }"
            "})();"
        )
    except Exception:
        _open_full_editor()


def _open_full_editor() -> None:
    """Open Anki's native EditCurrent dialog (the escape hatch)."""
    try:
        # Call the ORIGINAL onEditCurrent — not our patched one or we'd
        # bounce straight back to inline edit and never reach the dialog.
        orig = getattr(mw, "_ba_orig_on_edit_current", None)
        if orig is not None:
            orig()
        else:
            mw.onEditCurrent()
    except Exception:
        pass


def _patch_on_edit_current() -> None:
    """Replace `mw.onEditCurrent` with our inline launcher. The original
    is stashed at `mw._ba_orig_on_edit_current` so the escape hatch can
    still get to it."""
    try:
        if getattr(mw, "_ba_orig_on_edit_current", None) is not None:
            return  # already patched
        mw._ba_orig_on_edit_current = mw.onEditCurrent  # type: ignore
        mw.onEditCurrent = _enter_inline_edit  # type: ignore[assignment]
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# Save / cancel / open-full handlers, dispatched from _on_js_message.
# --------------------------------------------------------------------------- #
def handle_edit_save(payload: str) -> bool:
    """Apply field updates from the JS payload. Returns True if anything
    actually changed. The JS sends a JSON object of {field_name: html, …}
    — only the names we recognise on the current note are applied."""
    rv = getattr(mw, "reviewer", None)
    if rv is None or getattr(rv, "card", None) is None:
        return False
    try:
        data = json.loads(payload or "{}")
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    try:
        note = rv.card.note()
    except Exception:
        return False

    changed = False
    try:
        keys = set(note.keys())
    except Exception:
        return False
    for name, val in data.items():
        if not isinstance(name, str) or name not in keys:
            continue
        if not isinstance(val, str):
            continue
        try:
            if note[name] != val:
                note[name] = val
                changed = True
        except Exception:
            continue
    if not changed:
        return False
    try:
        mw.col.update_note(note)
    except Exception:
        try:
            note.flush()
        except Exception:
            return False
    # The reviewer caches the rendered card output on the Card object —
    # _showQuestion / _showAnswer would happily re-display that cached
    # render even though the underlying field values have changed. Bust
    # the cache so the next render pulls fresh from the (now updated)
    # note. card.note() also stays in sync because we modified rv.card._note
    # in place above.
    try:
        rv.card._render_output = None  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        if getattr(rv, "state", "") == "answer":
            rv._showAnswer()
        else:
            rv._showQuestion()
    except Exception:
        pass
    return True


def handle_edit_full(payload: str) -> None:
    """User asked to escalate to the full editor. Save anything pending
    first (so the dialog opens with current state), then open it."""
    if payload:
        handle_edit_save(payload)
    _open_full_editor()


def set_edit_active(active: bool) -> None:
    """JS calls this on edit-mode enter/exit. While editing, Anki's reviewer
    state shortcuts must be disabled — otherwise typing 'e' re-triggers
    edit, 'm' opens the More menu, ⌘+Backspace deletes the note, etc.
    QShortcuts intercept keys at the Qt level before Chromium dispatches
    them to the contenteditable, so JS handlers alone can't make this work.

    Stash the original enabled flag on each shortcut so a stray double
    enter/exit doesn't permanently disable anything."""
    try:
        shortcuts = list(getattr(mw, "stateShortcuts", []) or [])
    except Exception:
        return
    for sc in shortcuts:
        try:
            if active:
                if not hasattr(sc, "_ba_orig_enabled"):
                    sc._ba_orig_enabled = sc.isEnabled()  # type: ignore
                sc.setEnabled(False)
            else:
                orig = getattr(sc, "_ba_orig_enabled", True)
                sc.setEnabled(bool(orig))
                try:
                    delattr(sc, "_ba_orig_enabled")
                except Exception:
                    pass
        except Exception:
            continue


# --------------------------------------------------------------------------- #
# Registration.
# --------------------------------------------------------------------------- #
def register() -> None:
    try:
        gui_hooks.card_will_show.append(_wrap_fields)
    except Exception:
        pass
    try:
        gui_hooks.state_shortcuts_will_change.append(
            _on_state_shortcuts_will_change
        )
    except Exception:
        pass
    try:
        gui_hooks.main_window_did_init.append(_patch_on_edit_current)
    except Exception:
        # Fallback: try to patch immediately (mw might already be ready).
        _patch_on_edit_current()
