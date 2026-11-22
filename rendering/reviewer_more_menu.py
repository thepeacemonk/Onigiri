"""Modern Motion-inspired override for Anki's Reviewer 'More' context menu."""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Callable

try:
    from aqt import gui_hooks, mw
    from aqt.qt import QApplication, QEvent, QKeySequence, QMenu, QObject, Qt, QTimer, QWidget
    from aqt.reviewer import Reviewer
    from aqt.theme import theme_manager
    from aqt.utils import tr as anki_tr
except Exception:  # pragma: no cover - allows pure-helper unit tests without Anki
    gui_hooks = None
    mw = None
    QApplication = None
    QEvent = None
    QKeySequence = None
    QMenu = None
    QObject = object
    Qt = None
    QTimer = None
    QWidget = None
    Reviewer = None
    theme_manager = None
    anki_tr = None

from ..core import config
from . import reviewer_flags

_ADDON_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_MARKED_TAG = "marked"

_FLAG_FALLBACK_COLORS = {
    1: "#ff5a5f",
    2: "#ff9f0a",
    3: "#30d158",
    4: "#0a84ff",
    5: "#ff6482",
    6: "#40c8e0",
    7: "#bf5af2",
}

_FLAG_FALLBACK_LABELS = {
    1: "Red",
    2: "Orange",
    3: "Green",
    4: "Blue",
    5: "Pink",
    6: "Turquoise",
    7: "Purple",
}

_is_open = False
_active_qmenu = None
_custom_action_map: dict[int, Any] = {}
_dismiss_filter = None
_hooks_installed = False
_cached_css_mtime: int | None = None
_cached_css_text: str = ""


def _safe_anki_tr(attr: str, fallback: str, **kwargs: Any) -> str:
    if anki_tr is None:
        return fallback
    fn = getattr(anki_tr, attr, None)
    if not callable(fn):
        return fallback
    try:
        return str(fn(**kwargs))
    except Exception:
        return fallback


def _strip_mnemonic(text: str) -> str:
    """Remove Qt '&' keyboard mnemonic markers while preserving literal '&&'."""
    if not text:
        return ""
    sentinel = "\x00AMP\x00"
    cleaned = text.replace("&&", sentinel).replace("&", "").replace(sentinel, "&")
    return cleaned.strip()


def _strip_trailing_ellipsis(text: str) -> str:
    """Remove literal trailing '...' or '…' from menu labels."""
    if not text:
        return ""
    return re.sub(r"(?:\.{3}|…)+\s*$", "", text).strip()


def _format_shortcut(raw: str, is_mac: bool | None = None) -> str:
    """Format a Qt shortcut string into native human-readable glyphs."""
    if not raw:
        return ""
    if QKeySequence is not None:
        try:
            native = QKeySequence(raw).toString(QKeySequence.SequenceFormat.NativeText)
            if native:
                return native
        except Exception:
            pass
    if is_mac is None:
        is_mac = sys.platform == "darwin"
    if not is_mac:
        return raw
    parts = [part.strip() for part in raw.split("+") if part.strip()]
    if not parts:
        return raw
    key = parts[-1]
    mods = parts[:-1]
    mod_map = {"Ctrl": "⌘", "Alt": "⌥", "Shift": "⇧", "Meta": "⌃"}
    order = ("Meta", "Alt", "Shift", "Ctrl")
    mod_str = "".join(mod_map[m] for m in order if m in mods)
    key_map = {"Backspace": "⌫", "Delete": "⌦", "Return": "↩", "Enter": "⌤", "Space": "Space"}
    key_str = key_map.get(key, key.upper() if len(key) == 1 else key)
    return f"{mod_str}{key_str}"


def _read_menu_css_text() -> str:
    global _cached_css_mtime, _cached_css_text
    css_path = os.path.join(_ADDON_ROOT, "web", "reviewer_more_menu.css")
    try:
        mtime = os.stat(css_path).st_mtime_ns
        if _cached_css_mtime != mtime:
            with open(css_path, "r", encoding="utf-8") as handle:
                _cached_css_text = handle.read()
            _cached_css_mtime = mtime
    except OSError:
        return ""
    return _cached_css_text


def reviewer_head_assets(addon_package: str, conf: dict[str, Any]) -> str:
    """Return CSS/JS payload injected into the Reviewer card webview head."""
    from . import patcher

    css_text = _read_menu_css_text()
    try:
        font_css = patcher.generate_scoped_main_font_css(
            addon_package, "#onigiri-more-menu-root"
        )
        font_css = re.sub(r"@font-face\s*\{[^{}]*\}", "", font_css)
        font_css = re.sub(r"</?style[^>]*>", "", font_css)
        css_text = font_css + "\n" + css_text
    except Exception:
        pass
    return f"<script>window.onigiriMoreMenuCssText = {json.dumps(css_text)};</script>"


def bottom_bar_assets() -> str:
    """Return lightweight styling & click/state sync injected into ReviewerBottomBar."""
    return r"""
    <style id="onigiri-more-menu-bottom-bar-style">
        #outer button[onclick*="more"].onigiri-more-btn,
        button[onclick*="more"].onigiri-more-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 4px;
        }
        #outer button[onclick*="more"] .onigiri-more-chevron,
        button[onclick*="more"] .onigiri-more-chevron {
            width: 0.95em;
            height: 0.95em;
            flex: 0 0 auto;
            opacity: 0.72;
            transition: transform 180ms cubic-bezier(0.2, 0.9, 0.3, 1), opacity 140ms ease;
        }
        #outer button[onclick*="more"].onigiri-more-menu-open .onigiri-more-chevron,
        button[onclick*="more"].onigiri-more-menu-open .onigiri-more-chevron {
            transform: rotate(180deg);
            opacity: 1;
        }
        #outer button[onclick*="more"].onigiri-more-menu-open {
            box-shadow: inset 0 0 0 1.5px rgba(128, 128, 128, 0.42) !important;
            filter: brightness(0.95);
        }
        .nightMode #outer button[onclick*="more"].onigiri-more-menu-open {
            box-shadow: inset 0 0 0 1.5px rgba(255, 255, 255, 0.35) !important;
            filter: brightness(1.12);
        }
        @media (prefers-reduced-motion: reduce) {
            #outer button[onclick*="more"] .onigiri-more-chevron,
            button[onclick*="more"] .onigiri-more-chevron {
                transition: none;
            }
        }
    </style>
    <script>
    (function () {
        if (window.__onigiriMoreMenuBottomBridge) return;
        window.__onigiriMoreMenuBottomBridge = true;
        let isOpen = false;
        const ARROW_RE = /[▾▼▴▲]/g;
        const SVG_NS = 'http://www.w3.org/2000/svg';

        function findMoreButton() {
            return document.querySelector('#outer button[onclick*="more"], button[onclick*="more"]');
        }

        function createMoreChevron() {
            const svg = document.createElementNS(SVG_NS, 'svg');
            svg.setAttribute('viewBox', '0 0 24 24');
            svg.setAttribute('fill', 'none');
            svg.setAttribute('stroke', 'currentColor');
            svg.setAttribute('stroke-width', '2.1');
            svg.setAttribute('stroke-linecap', 'round');
            svg.setAttribute('stroke-linejoin', 'round');
            svg.setAttribute('aria-hidden', 'true');
            svg.setAttribute('class', 'lucide lucide-chevron-down onigiri-more-chevron');
            const path = document.createElementNS(SVG_NS, 'path');
            path.setAttribute('d', 'm6 9 6 6 6-6');
            svg.appendChild(path);
            return svg;
        }

        function upgradeMoreButtonArrow() {
            const btn = findMoreButton();
            if (!btn) return;
            btn.classList.add('onigiri-more-btn');
            const walker = document.createTreeWalker(btn, NodeFilter.SHOW_TEXT);
            const matchedNodes = [];
            let node;
            while ((node = walker.nextNode())) {
                ARROW_RE.lastIndex = 0;
                if (ARROW_RE.test(node.nodeValue || '')) {
                    matchedNodes.push(node);
                }
            }
            matchedNodes.forEach(function (tn) {
                ARROW_RE.lastIndex = 0;
                const cleaned = (tn.nodeValue || '').replace(ARROW_RE, '').replace(/\s+$/, '');
                if (cleaned) {
                    tn.nodeValue = cleaned;
                } else if (tn.parentNode && tn.parentNode !== btn && tn.parentNode.childNodes.length === 1) {
                    const parentEl = tn.parentNode;
                    const prev = parentEl.previousSibling;
                    parentEl.remove();
                    if (prev && prev.nodeType === Node.TEXT_NODE && prev.nodeValue) {
                        prev.nodeValue = prev.nodeValue.replace(/\s+$/, '');
                    }
                } else {
                    tn.nodeValue = '';
                }
            });
            if (!btn.querySelector('.onigiri-more-chevron')) {
                btn.appendChild(createMoreChevron());
            }
            btn.classList.toggle('onigiri-more-menu-open', isOpen);
        }

        function startObserver() {
            upgradeMoreButtonArrow();
            if (typeof MutationObserver === 'function' && document.documentElement) {
                const obs = new MutationObserver(upgradeMoreButtonArrow);
                obs.observe(document.documentElement, { childList: true, subtree: true });
            }
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', startObserver, { once: true });
        } else {
            startObserver();
        }

        window.onigiriSetMoreMenuOpen = function (open) {
            isOpen = Boolean(open);
            const btn = findMoreButton();
            if (btn) {
                upgradeMoreButtonArrow();
                btn.classList.toggle('onigiri-more-menu-open', isOpen);
                btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
            }
        };

        document.addEventListener('pointerdown', function (e) {
            if (!isOpen) return;
            const target = e.target;
            if (target && typeof target.closest === 'function' && target.closest('button[onclick*="more"]')) {
                return;
            }
            if (typeof window.pycmd === 'function') {
                window.pycmd('onigiri_more_menu:close');
            }
        }, true);
    })();
    </script>
    """


def _extract_custom_items(
    menu: Any, builtin_actions: set[Any] | None = None
) -> tuple[list[dict[str, Any]], dict[int, Any]]:
    """Serialize any non-built-in QActions/submenus added via reviewer_will_show_context_menu."""
    builtin = builtin_actions or set()
    action_map: dict[int, Any] = {}
    counter = [0]

    def walk(qmenu: Any, filter_builtin: bool) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for action in qmenu.actions():
            if filter_builtin and action in builtin:
                continue
            if action.isSeparator():
                if items and items[-1].get("type") != "separator":
                    items.append({"type": "separator"})
                continue
            sub = action.menu()
            label = _strip_trailing_ellipsis(_strip_mnemonic(str(action.text() or "")))
            if sub is not None:
                children = walk(sub, False)
                if children:
                    items.append(
                        {
                            "type": "submenu",
                            "label": label,
                            "disabled": not bool(action.isEnabled()),
                            "items": children,
                        }
                    )
                continue
            item_id = counter[0]
            counter[0] += 1
            action_map[item_id] = action
            shortcut_text = ""
            try:
                sc = action.shortcut()
                if sc and not sc.isEmpty():
                    shortcut_text = sc.toString(QKeySequence.SequenceFormat.NativeText)
            except Exception:
                shortcut_text = ""
            items.append(
                {
                    "type": "action",
                    "id": item_id,
                    "label": label,
                    "shortcut": shortcut_text,
                    "checkable": bool(action.isCheckable()),
                    "checked": bool(action.isChecked()),
                    "disabled": not bool(action.isEnabled()),
                }
            )
        while items and items[-1].get("type") == "separator":
            items.pop()
        return items

    return walk(menu, True), action_map


def _resolve_flag_icon_urls(mw_ref: Any) -> dict[str, str]:
    """Resolve user-selected Onigiri flag icon URLs for flags 1..7."""
    try:
        addon_mgr = getattr(mw_ref, "addonManager", None)
        if addon_mgr is None or not callable(getattr(addon_mgr, "addonFromModule", None)):
            return {}
        package = addon_mgr.addonFromModule(__name__)
        if not package:
            return {}
        get_conf = getattr(config, "get_config_readonly", None) or getattr(config, "get_config", None)
        conf = get_conf() if callable(get_conf) else {}
        if not isinstance(conf, dict):
            conf = {}
        return reviewer_flags.icon_urls(conf, _ADDON_ROOT, package)
    except Exception:
        return {}


def _build_flags_list(mw_ref: Any) -> list[dict[str, Any]]:
    """Return the 7 Anki flags with localized/custom labels, colors, icons, and shortcuts."""
    icon_urls = _resolve_flag_icon_urls(mw_ref)
    flags_out: list[dict[str, Any]] = []
    flag_mgr = getattr(mw_ref, "flags", None)
    if flag_mgr is not None and callable(getattr(flag_mgr, "all", None)):
        try:
            for flag in flag_mgr.all():
                idx = int(flag.index)
                flags_out.append(
                    {
                        "index": idx,
                        "label": str(flag.label),
                        "color": f"var(--flag-{idx}, {_FLAG_FALLBACK_COLORS.get(idx, '#ff5a5f')})",
                        "shortcut": _format_shortcut(f"Ctrl+{idx}"),
                        "iconUrl": icon_urls.get(str(idx), ""),
                    }
                )
            if flags_out:
                return flags_out
        except Exception:
            pass
    for idx in range(1, 8):
        flags_out.append(
            {
                "index": idx,
                "label": _FLAG_FALLBACK_LABELS[idx],
                "color": _FLAG_FALLBACK_COLORS[idx],
                "shortcut": _format_shortcut(f"Ctrl+{idx}"),
                "iconUrl": icon_urls.get(str(idx), ""),
            }
        )
    return flags_out


def _localized_labels() -> dict[str, str]:
    reset_base = _strip_trailing_ellipsis(_safe_anki_tr("actions_forget_card", "Reset Card"))
    due_base = _strip_trailing_ellipsis(_safe_anki_tr("actions_set_due_date", "Set Due Date"))
    copy_base = _strip_trailing_ellipsis(_safe_anki_tr("actions_create_copy", "Create Copy"))
    return {
        "flagCard": _safe_anki_tr("studying_flag_card", "Flag Card"),
        "clearFlag": _safe_anki_tr("actions_clear", "Clear"),
        "markNote": _safe_anki_tr("studying_mark_note", "Mark Note"),
        "autoAdvance": _safe_anki_tr("actions_auto_advance", "Auto Advance"),
        "options": _safe_anki_tr("actions_options", "Options"),
        "cardInfo": _safe_anki_tr("actions_card_info", "Card Info"),
        "previousCardInfo": _safe_anki_tr("actions_previous_card_info", "Previous Card Info"),
        "buryGroup": _safe_anki_tr("studying_bury", "Bury"),
        "suspendGroup": _safe_anki_tr("studying_suspend", "Suspend"),
        "cardWord": _safe_anki_tr("browsing_card", "Card"),
        "noteWord": _safe_anki_tr("browsing_note", "Note"),
        "setDueDate": due_base,
        "resetCard": reset_base,
        "createCopy": copy_base,
        "deleteNote": _safe_anki_tr("studying_delete_note", "Delete Note"),
        "replayAudio": _safe_anki_tr("actions_replay_audio", "Replay Audio"),
        "replayShort": _safe_anki_tr("actions_replay", "Replay"),
        "pauseAudio": _safe_anki_tr("studying_pause_audio", "Pause Audio"),
        "audioBack": _safe_anki_tr("studying_audio_5s", "Audio -5s"),
        "audioForward": _safe_anki_tr("studying_audio_and5s", "Audio +5s"),
        "recordVoice": _safe_anki_tr("studying_record_own_voice", "Record Own Voice"),
        "recordShort": "Record",
        "replayVoice": _safe_anki_tr("studying_replay_own_voice", "Replay Own Voice"),
        "playVoiceShort": "Replay",
        "extensions": "Add-ons",
    }


def _shortcut_map(is_mac: bool | None = None) -> dict[str, str]:
    if is_mac is None:
        is_mac = sys.platform == "darwin"
    delete_raw = "Ctrl+Backspace" if is_mac else "Ctrl+Delete"
    return {
        "mark": "*",
        "autoAdvance": _format_shortcut("Shift+A", is_mac=is_mac),
        "options": "O",
        "cardInfo": "I",
        "previousCardInfo": _format_shortcut("Ctrl+Alt+I", is_mac=is_mac),
        "buryCard": "-",
        "buryNote": "=",
        "suspendCard": "@",
        "suspendNote": "!",
        "setDueDate": _format_shortcut("Ctrl+Shift+D", is_mac=is_mac),
        "resetCard": _format_shortcut("Ctrl+Alt+N", is_mac=is_mac),
        "createCopy": _format_shortcut("Ctrl+Alt+E", is_mac=is_mac),
        "deleteNote": _format_shortcut(delete_raw, is_mac=is_mac),
        "replayAudio": "R",
        "pauseAudio": "5",
        "audioBack": "6",
        "audioForward": "7",
        "recordVoice": _format_shortcut("Shift+V", is_mac=is_mac),
        "replayVoice": "V",
    }


def build_menu_payload(
    reviewer: Any,
    mw_ref: Any = None,
    custom_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble the complete JSON state payload for the Reviewer More menu."""
    card = getattr(reviewer, "card", None)
    flag_val = 0
    marked_val = False
    if card is not None:
        try:
            flag_val = int(card.user_flag() or 0)
        except Exception:
            flag_val = 0
        try:
            marked_val = bool(card.note().has_tag(_MARKED_TAG))
        except Exception:
            marked_val = False

    night_mode = False
    if theme_manager is not None:
        try:
            night_mode = bool(theme_manager.night_mode)
        except Exception:
            night_mode = False
    if not night_mode:
        try:
            night_mode = bool(config.effective_night_mode())
        except Exception:
            pass

    return {
        "flag": flag_val,
        "marked": marked_val,
        "autoAdvance": bool(getattr(reviewer, "auto_advance_enabled", False)),
        "hasPreviousCard": bool(getattr(reviewer, "previous_card", None)),
        "dark": night_mode,
        "anchorRight": 15,
        "flags": _build_flags_list(mw_ref),
        "labels": _localized_labels(),
        "shortcuts": _shortcut_map(),
        "customItems": custom_items or [],
    }


def _is_descendant(widget: Any, ancestor: Any) -> bool:
    if widget is None or ancestor is None:
        return False
    cur = widget
    while cur is not None:
        if cur is ancestor:
            return True
        parent_fn = getattr(cur, "parent", None)
        cur = parent_fn() if callable(parent_fn) else None
    return False


if QObject is not object and QEvent is not None:
    class _MenuDismissFilter(QObject):
        """Close the floating menu on Escape, window deactivation, or outside clicks."""

        def eventFilter(self, obj: Any, event: Any) -> bool:
            if not _is_open:
                return False
            etype = event.type()
            if etype == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Escape:
                    close_menu()
                    return True
            elif etype == QEvent.Type.WindowDeactivate:
                if obj is mw:
                    close_menu()
            elif etype == QEvent.Type.MouseButtonPress:
                if isinstance(obj, QWidget):
                    r_web = getattr(getattr(mw, "reviewer", None), "web", None)
                    b_web = getattr(mw, "bottomWeb", None)
                    if not _is_descendant(obj, r_web) and not _is_descendant(obj, b_web):
                        close_menu()
            return False
else:
    class _MenuDismissFilter:
        pass


def _install_dismiss_filter() -> None:
    global _dismiss_filter
    app = QApplication.instance() if QApplication is not None else None
    if app is None:
        return
    if _dismiss_filter is None:
        _dismiss_filter = _MenuDismissFilter(app)
    app.removeEventFilter(_dismiss_filter)
    app.installEventFilter(_dismiss_filter)


def _remove_dismiss_filter() -> None:
    app = QApplication.instance() if QApplication is not None else None
    if app is not None and _dismiss_filter is not None:
        try:
            app.removeEventFilter(_dismiss_filter)
        except Exception:
            pass


def _cleanup_qmenu() -> None:
    global _active_qmenu, _custom_action_map
    _custom_action_map = {}
    qmenu = _active_qmenu
    _active_qmenu = None
    if qmenu is not None:
        try:
            qmenu.deleteLater()
        except Exception:
            pass


def _sync_bottom_button_state(open_state: bool) -> None:
    b_web = getattr(mw, "bottomWeb", None) if mw is not None else None
    if b_web is not None:
        try:
            b_web.eval(
                f"window.onigiriSetMoreMenuOpen && window.onigiriSetMoreMenuOpen({json.dumps(bool(open_state))});"
            )
        except Exception:
            pass


def close_menu(from_js: bool = False, immediate: bool = False) -> None:
    """Dismiss the custom Reviewer More menu and clean up transient state."""
    global _is_open
    was_open = _is_open
    _is_open = False
    _remove_dismiss_filter()
    _cleanup_qmenu()
    if was_open or not from_js:
        _sync_bottom_button_state(False)
    if not from_js and mw is not None:
        r_web = getattr(getattr(mw, "reviewer", None), "web", None)
        if r_web is not None:
            fn = "closeImmediate" if immediate else "close"
            try:
                r_web.eval(
                    f"window.OnigiriReviewerMoreMenu && window.OnigiriReviewerMoreMenu.{fn}();"
                )
            except Exception:
                pass


def open_menu(reviewer: Any) -> None:
    """Build live state and open the modern Reviewer More menu (or toggle closed)."""
    global _is_open, _active_qmenu, _custom_action_map
    if _is_open:
        close_menu()
        return
    if reviewer is None or getattr(reviewer, "card", None) is None:
        return
    mw_ref = getattr(reviewer, "mw", mw)
    if mw_ref is None or getattr(mw_ref, "state", None) != "review":
        return

    _cleanup_qmenu()
    custom_items: list[dict[str, Any]] = []
    action_map: dict[int, Any] = {}
    if QMenu is not None and gui_hooks is not None:
        try:
            temp_menu = QMenu(mw_ref)
            reviewer._addMenuItems(temp_menu, reviewer._contextMenu())
            builtin_actions = set(temp_menu.actions())
            gui_hooks.reviewer_will_show_context_menu(reviewer, temp_menu)
            custom_items, action_map = _extract_custom_items(temp_menu, builtin_actions)
            _active_qmenu = temp_menu
            _custom_action_map = action_map
        except Exception as exc:
            print(f"[Onigiri] Could not inspect reviewer context hooks: {exc}")

    payload = build_menu_payload(reviewer, mw_ref=mw_ref, custom_items=custom_items)
    focus_keyboard = False
    if QApplication is not None and Qt is not None:
        try:
            focus_keyboard = QApplication.mouseButtons() == Qt.MouseButton.NoButton
        except Exception:
            focus_keyboard = False

    _is_open = True
    _install_dismiss_filter()
    _sync_bottom_button_state(True)

    r_web = getattr(reviewer, "web", None)
    if r_web is not None:
        if focus_keyboard:
            try:
                r_web.setFocus()
            except Exception:
                pass
        r_web.eval(
            f"window.OnigiriReviewerMoreMenu && window.OnigiriReviewerMoreMenu.open({json.dumps(payload)}, {json.dumps(focus_keyboard)});"
        )


def _run_reviewer_action(reviewer: Any, action_id: str) -> bool:
    """Execute a standard Reviewer action from the custom More menu."""
    if reviewer is None or getattr(reviewer, "card", None) is None:
        return False
    if action_id.startswith("flag:"):
        try:
            flag_idx = int(action_id.split(":", 1)[1])
        except ValueError:
            return False
        if flag_idx == 0:
            # Calling set_flag_on_current_card(0) works, or force clear if already 0.
            if reviewer.card.user_flag() != 0:
                reviewer.set_flag_on_current_card(0)
        else:
            reviewer.set_flag_on_current_card(flag_idx)
        return True

    dispatch: dict[str, Callable[[], Any]] = {
        "mark": reviewer.toggle_mark_on_current_note,
        "auto_advance": reviewer.toggle_auto_advance,
        "options": reviewer.onOptions,
        "card_info": reviewer.on_card_info,
        "prev_card_info": reviewer.on_previous_card_info,
        "bury_card": reviewer.bury_current_card,
        "bury_note": reviewer.bury_current_note,
        "suspend_card": reviewer.suspend_current_card,
        "suspend_note": reviewer.suspend_current_note,
        "set_due": reviewer.on_set_due,
        "reset_card": reviewer.forget_current_card,
        "create_copy": reviewer.on_create_copy,
        "delete_note": reviewer.delete_current_note,
        "replay_audio": reviewer.replayAudio,
        "pause_audio": reviewer.on_pause_audio,
        "seek_back": reviewer.on_seek_backward,
        "seek_fwd": reviewer.on_seek_forward,
        "record_voice": reviewer.onRecordVoice,
        "replay_voice": reviewer.onReplayRecorded,
    }
    fn = dispatch.get(action_id)
    if fn is None:
        return False
    fn()
    return True


def handle_command(cmd: str) -> bool:
    """Handle pycmd messages emitted by the Reviewer More menu UI."""
    global _is_open
    if not isinstance(cmd, str) or not cmd.startswith("onigiri_more_menu:"):
        return False

    sub = cmd[len("onigiri_more_menu:"):]
    if sub == "closed":
        close_menu(from_js=True)
        return True
    if sub == "close":
        close_menu(from_js=False)
        return True

    reviewer = getattr(mw, "reviewer", None) if mw is not None else None
    if sub.startswith("act:"):
        action_id = sub[len("act:"):]
        keep_open = action_id in {"replay_audio", "pause_audio", "seek_back", "seek_fwd", "replay_voice"}
        delayed_close = action_id.startswith("flag:") or action_id in {"mark", "auto_advance"}
        if not keep_open and not delayed_close:
            close_menu(from_js=True)
        _run_reviewer_action(reviewer, action_id)
        return True

    if sub.startswith("custom:"):
        try:
            item_id = int(sub[len("custom:"):])
        except ValueError:
            close_menu(from_js=True)
            return True
        action = _custom_action_map.get(item_id)
        # Keep the QMenu/QAction alive until trigger() finishes, then clean up.
        if _is_open:
            _is_open = False
            _remove_dismiss_filter()
            _sync_bottom_button_state(False)
        try:
            if action is not None:
                action.trigger()
        finally:
            if QTimer is not None:
                QTimer.singleShot(0, _cleanup_qmenu)
            else:
                _cleanup_qmenu()
        return True

    return False


def install_reviewer_more_menu_override() -> None:
    """Override Reviewer.showContextMenu and bind lifecycle close hooks."""
    global _hooks_installed
    if Reviewer is not None and not getattr(Reviewer, "_onigiri_more_menu_patched", False):
        Reviewer._onigiri_orig_showContextMenu = Reviewer.showContextMenu

        def _onigiri_show_context_menu(self: Any) -> None:
            open_menu(self)

        Reviewer.showContextMenu = _onigiri_show_context_menu
        Reviewer._onigiri_more_menu_patched = True

    if not _hooks_installed and gui_hooks is not None:
        gui_hooks.reviewer_did_show_question.append(lambda *_: close_menu(immediate=True))
        gui_hooks.reviewer_did_show_answer.append(lambda *_: close_menu(immediate=True))
        gui_hooks.reviewer_will_end.append(lambda *_: close_menu(immediate=True))
        gui_hooks.state_did_change.append(lambda *_: close_menu(immediate=True))
        _hooks_installed = True
