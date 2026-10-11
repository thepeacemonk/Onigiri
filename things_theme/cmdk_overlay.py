"""Anki Design — keep embeds in place while the Cmd-K palette is up.

The palette is rendered in mw.web's DOM, and the embeds (Add/Browse/Stats/
Settings) are Qt frames overlaid on top of mw.web. Opening the palette while
an embed is up would normally leave the palette invisible behind the embed —
the original workaround (tearing the embed down) is what produced the
"switches to the decks page" complaint.

This module avoids the destroy/recreate and avoids the abrupt visual
swap that comes with just hiding the embed:

  1. Inject a stylesheet into mw.web that hides every body child except
     the sidebar and the palette, AND hides `body::before` (which carries
     the addon's `--rf-glow` radial gradient — a yellow blob at the top
     in light mode).
  2. Snapshot the embed (QWidget.grab() works on QWebEngineView via the
     backing store) and display the snapshot as a QLabel above the
     embed. Hide the embed underneath the snapshot.
  3. Fade the snapshot QLabel from opacity 1 → 0 over ~240ms while the
     palette springs in via its existing CSS animation. The user sees a
     smooth cross-fade from embed to paper-bg + palette, instead of
     an instant snap.
  4. On close: snapshot the (hidden) embed again, fade the snapshot from
     0 → 1, then swap to the real embed and strip the hide-content CSS.

QGraphicsOpacityEffect applied directly to the embed's QFrame would be
simpler, but the embed contains a QWebEngineView whose GPU-composited
surface doesn't honour QGraphicsEffect on macOS Qt6 — the chrome would
fade while the webview area stayed opaque, an ugly visual glitch. The
QLabel-pixmap approach sidesteps that entirely: a QLabel is plain Qt
and accepts opacity effects without surprises.
"""

from __future__ import annotations

import json
from typing import List

from aqt import mw
from aqt.qt import (
    QEasingCurve,
    QGraphicsOpacityEffect,
    QLabel,
    QPropertyAnimation,
    Qt,
    QTimer,
)


# Embed overlays that we hid when the palette opened (in stack order;
# in practice only one embed is ever up at a time).
_hidden: List = []

# Whether the hide-content CSS is currently injected into mw.web.
_css_active: bool = False

# Active QPropertyAnimations kept alive while running (Qt will GC them
# otherwise and the fade stops mid-way).
_animations: list = []

# Cross-fade duration. Matches the modal entrance long enough to feel
# continuous, short enough to stay snappy.
_FADE_MS = 280


def _embed_modules() -> List[str]:
    return ["addcard_embed", "browse_embed", "stats_embed", "settings_embed"]


def _start_fade(snap: QLabel, start: float, end: float, on_done=None) -> None:
    """Animate a QLabel's opacity from `start` to `end` over _FADE_MS,
    calling `on_done` when finished."""
    effect = QGraphicsOpacityEffect(snap)
    snap.setGraphicsEffect(effect)
    effect.setOpacity(start)
    anim = QPropertyAnimation(effect, b"opacity", snap)
    anim.setDuration(_FADE_MS)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _cleanup():
        try:
            _animations.remove(anim)
        except ValueError:
            pass
        if on_done is not None:
            try:
                on_done()
            except Exception:
                pass

    anim.finished.connect(_cleanup)
    _animations.append(anim)
    anim.start()


def _hide_embeds_with_fade() -> None:
    """Snapshot each visible embed, display the snapshot above it as a
    QLabel, hide the real embed, fade the snapshot out. The real embed is
    hidden immediately so cmdk can take focus; the snapshot is what the
    user actually sees fading."""
    for mod_name in _embed_modules():
        try:
            from importlib import import_module
            mod = import_module("." + mod_name, __package__)
            st = getattr(mod, "_state", None)
            if not isinstance(st, dict):
                continue
            overlay = st.get("overlay")
            if overlay is None or not overlay.isVisible():
                continue
            parent = overlay.parent()
            if parent is None:
                continue
            try:
                pixmap = overlay.grab()
                snap = QLabel(parent)
                # WA_NativeWindow forces the QLabel to have its own native
                # window so it stacks correctly above mw.web's QWebEngineView,
                # whose GPU-composited surface otherwise paints over sibling
                # Qt widgets that are technically above it in z-order.
                snap.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
                snap.setPixmap(pixmap)
                snap.setGeometry(overlay.geometry())
                snap.show()
                snap.raise_()
                overlay.hide()
                _start_fade(snap, 1.0, 0.0, on_done=snap.deleteLater)
                _hidden.append(overlay)
            except Exception:
                # Fall back to instant hide if grab/QLabel setup fails.
                try:
                    overlay.hide()
                    _hidden.append(overlay)
                except Exception:
                    pass
        except Exception:
            continue


def _show_embeds_with_fade() -> None:
    """For each previously-hidden embed: snapshot its current state,
    display the snapshot at opacity 0 above where the embed will appear,
    fade snapshot to opacity 1, then swap the snapshot for the real
    embed (visually identical at opacity 1, so the swap is invisible)."""
    while _hidden:
        overlay = _hidden.pop()
        try:
            parent = overlay.parent()
            if parent is None:
                # No parent to host the snapshot — just show the embed.
                overlay.show()
                overlay.raise_()
                continue
            try:
                # grab() on a hidden widget renders to a pixmap regardless
                # of its visibility — perfect for a fade-in snapshot.
                pixmap = overlay.grab()
                snap = QLabel(parent)
                snap.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
                snap.setPixmap(pixmap)
                snap.setGeometry(overlay.geometry())
                snap.show()
                snap.raise_()

                def _swap(ov=overlay, sn=snap):
                    try:
                        ov.show()
                        ov.raise_()
                    except Exception:
                        pass
                    try:
                        sn.deleteLater()
                    except Exception:
                        pass

                _start_fade(snap, 0.0, 1.0, on_done=_swap)
            except Exception:
                # Fall back to instant show if grab/QLabel setup fails.
                try:
                    overlay.show()
                    overlay.raise_()
                except Exception:
                    pass
        except RuntimeError:
            # Embed was destroyed (e.g. action torn it down). Nothing to do.
            pass
        except Exception:
            pass


# CSS injected into mw.web while the palette is open. Two rules:
#   1. Hide body's direct children except the sidebar and palette so
#      mw.web reads as a blank paper page once the embed is hidden.
#   2. Hide `body::before`, which paints the addon's --rf-glow radial
#      gradient over the whole viewport (visible as a big yellow blob
#      at the top in light mode). Pseudo-elements aren't matched by
#      the first rule's `body > *` selector, hence the separate
#      `display:none`.
# visibility (not display) on body children so the layout isn't reflowed.
_INJECT_CSS_JS = (
    "(function(){if(document.getElementById('ba-cmdk-overlay-mode'))return true;"
    "var s=document.createElement('style');s.id='ba-cmdk-overlay-mode';"
    "s.textContent='body>*:not(.ba-side):not(.ba-cmdk-back)"
    "{visibility:hidden !important;}"
    "body::before{display:none !important;}';"
    "document.head.appendChild(s);return true;})();"
)

_REMOVE_CSS_JS = (
    "(function(){var s=document.getElementById('ba-cmdk-overlay-mode');"
    "if(s)s.remove();})();"
)


def open(initial: str = "") -> None:
    """Inject the hide-content CSS, snapshot+fade the embed out, then open
    the palette. Sequenced via evalWithCallback so the stylesheet is in
    the DOM before the embed disappears — without that ordering, mw.web
    becomes visible for one paint frame with the deck-browser content
    still painted, which is the flash this module is built to avoid."""
    global _css_active
    target = getattr(mw, "web", None)
    if target is None:
        return

    palette_js = (
        "if (window.__baCmdkOpen) window.__baCmdkOpen("
        + json.dumps(initial or "") + ");"
    )

    def _continue() -> None:
        _hide_embeds_with_fade()
        try:
            target.eval(palette_js)
        except Exception:
            pass

    def _on_inject(_r) -> None:
        global _css_active
        _css_active = True
        _continue()

    try:
        target.evalWithCallback(_INJECT_CSS_JS, _on_inject)
    except Exception:
        # No callback support — synchronous inject (may show 1-frame flash).
        try:
            target.eval(_INJECT_CSS_JS)
        except Exception:
            pass
        _css_active = True
        _continue()


def close() -> None:
    """Snapshot+fade the embed back in while the palette CSS-animates
    closed; once the embed snapshot is fully opaque (covers mw.web), strip
    the hide-content CSS. The defer keeps the deck-browser content from
    becoming visible during the cross-fade."""
    global _css_active
    _show_embeds_with_fade()
    if not _css_active:
        return
    target = getattr(mw, "web", None)
    if target is None:
        _css_active = False
        return
    # Wait for the snapshot fade-in (+ a small buffer) so the body content
    # in mw.web's DOM is always covered when the CSS hide rule drops.
    QTimer.singleShot(_FADE_MS + 40, lambda: _strip_css(target))


def _strip_css(target) -> None:
    global _css_active
    try:
        target.eval(_REMOVE_CSS_JS)
    except Exception:
        pass
    _css_active = False


def webview():
    """For symmetry with the earlier AnkiWebView-backed version: no
    dedicated webview exists in this implementation, so cmdk.py's
    `_push_results` correctly skips it."""
    return None


def is_visible() -> bool:
    return bool(_hidden) or _css_active
