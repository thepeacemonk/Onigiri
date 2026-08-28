"""macOS-only: dissolve Anki's window title bar into the Onigiri canvas.

Qt exposes no API for the three NSWindow properties that make a title bar
disappear, so we reach the real window through the Objective-C runtime with
ctypes:

    mw.winId()  ->  NSView*  ->  [view window]  ->  NSWindow*

and then set:

    styleMask |= NSWindowStyleMaskFullSizeContentView  (page paints to the top edge)
    titlebarAppearsTransparent = YES                   (no grey chrome, no separator)
    titleVisibility = NSWindowTitleHidden              (drops the "Deck - Anki" text)

The title bar itself still exists, so dragging, resizing, double-click-to-zoom
and the close/minimise/zoom buttons keep working -- the traffic lights simply
float over Onigiri's background. Because that strip stays a window-drag region,
the web pages reserve `TITLEBAR_INSET` points at the top (see `inset_css`) so no
Onigiri button ends up underneath it.

Everything here is a no-op off macOS.
"""

import ctypes
import ctypes.util
import sys

from aqt import mw

# Points reserved at the top of every Onigiri page for the floating traffic
# lights. macOS lays them out inside a 28pt title bar.
TITLEBAR_INSET = 28

_NS_WINDOW_STYLE_MASK_FULL_SIZE_CONTENT_VIEW = 1 << 15
_NS_WINDOW_TITLE_VISIBLE = 0
_NS_WINDOW_TITLE_HIDDEN = 1
_NS_TITLEBAR_SEPARATOR_AUTOMATIC = 0
_NS_TITLEBAR_SEPARATOR_NONE = 1

_objc = None
_objc_failed = False


class _NSPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class _NSSize(ctypes.Structure):
    _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]


class _NSRect(ctypes.Structure):
    _fields_ = [("origin", _NSPoint), ("size", _NSSize)]


def is_supported() -> bool:
    return sys.platform == "darwin"


def _runtime():
    """Load libobjc once; None if it is unavailable for any reason."""
    global _objc, _objc_failed
    if _objc is not None or _objc_failed:
        return _objc
    try:
        path = ctypes.util.find_library("objc")
        lib = ctypes.CDLL(path)
        lib.sel_registerName.restype = ctypes.c_void_p
        lib.sel_registerName.argtypes = [ctypes.c_char_p]
        lib.object_getClassName.restype = ctypes.c_char_p
        lib.object_getClassName.argtypes = [ctypes.c_void_p]
        _objc = lib
    except Exception as exc:
        print(f"[Onigiri] macOS title bar: objc runtime unavailable: {exc}")
        _objc_failed = True
    return _objc


def _send(obj, selector, *args, argtypes=None, restype=ctypes.c_void_p):
    """Call an Objective-C method.

    objc_msgSend is variadic in its C declaration, and on arm64 variadic and
    regular arguments use different registers -- so every call has to be
    prototyped with the receiving method's real signature rather than reusing
    one generic function pointer.
    """
    objc = _runtime()
    if objc is None:
        return None
    proto = ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p, *(argtypes or []))
    fn = proto(ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value)
    return fn(obj, objc.sel_registerName(selector.encode()), *args)


def _responds_to(obj, selector: str) -> bool:
    """Guard for selectors that only exist on newer macOS versions -- sending an
    unimplemented one raises an Objective-C exception, which is fatal here."""
    objc = _runtime()
    if objc is None or obj is None:
        return False
    try:
        return bool(_send(obj, "respondsToSelector:",
                          ctypes.c_void_p(objc.sel_registerName(selector.encode())),
                          argtypes=[ctypes.c_void_p], restype=ctypes.c_bool))
    except Exception:
        return False


def _nswindow(widget):
    objc = _runtime()
    if objc is None or widget is None:
        return None
    try:
        view = ctypes.c_void_p(int(widget.winId()))
    except Exception:
        return None
    if not view.value:
        return None
    window = _send(view, "window")
    return ctypes.c_void_p(window) if window else None


def _class_name(obj) -> str:
    objc = _runtime()
    if objc is None or not obj:
        return ""
    try:
        return objc.object_getClassName(ctypes.c_void_p(obj)).decode()
    except Exception:
        return ""


def _subviews(view):
    subviews = _send(ctypes.c_void_p(view), "subviews")
    if not subviews:
        return []
    count = _send(ctypes.c_void_p(subviews), "count", restype=ctypes.c_ulong)
    return [_send(ctypes.c_void_p(subviews), "objectAtIndex:", ctypes.c_ulong(i),
                  argtypes=[ctypes.c_ulong])
            for i in range(count)]


def _set_titlebar_decoration_hidden(window, hidden: bool) -> None:
    """Hide the 1px line AppKit draws along the window's top edge.

    A transparent title bar with no separator still leaves a hairline: it comes
    from `_NSTitlebarDecorationView`, a sibling of the view that holds the
    traffic lights. Caching the title bar container to a bitmap shows the top two
    device pixels at (140,140,140) and (63,63,63) with the rest fully
    transparent, and hiding this one view zeroes them -- the buttons are in
    `NSTitlebarView` and stay untouched.
    """
    try:
        content = _send(window, "contentView")
        if not content:
            return
        frame_view = _send(ctypes.c_void_p(content), "superview")
        if not frame_view:
            return
        for view in _subviews(frame_view):
            if "TitlebarContainer" not in _class_name(view):
                continue
            for child in _subviews(view):
                if "TitlebarDecoration" in _class_name(child):
                    _send(ctypes.c_void_p(child), "setHidden:", ctypes.c_bool(bool(hidden)),
                          argtypes=[ctypes.c_bool], restype=None)
    except Exception as exc:
        print(f"[Onigiri] macOS title bar: decoration line left alone: {exc}")


def _set_safe_area_respected(widget, respected: bool) -> None:
    """Let the widget's layout paint into the title bar strip (or stop it).

    Qt 6 treats the title bar as a safe area: with fullSizeContentView on, the
    NSView really does cover the whole window, but QMainWindow still lays its
    central widget out 28pt lower, leaving a band of bare window background --
    the exact grey strip this mode is supposed to remove. Turning
    WA_ContentsMarginsRespectsSafeArea off makes the layout use the full height.
    """
    try:
        from aqt.qt import Qt
        widget.setAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea, respected)
        layout = widget.layout()
        if layout is not None:
            layout.invalidate()
            layout.activate()
    except Exception as exc:
        print(f"[Onigiri] macOS title bar: safe-area margins unchanged: {exc}")


def apply(enabled: bool, widget=None) -> bool:
    """Merge (or restore) the title bar of `widget` -- the main window by default.

    Returns True when the window was actually touched.
    """
    if not is_supported():
        return False
    target = widget if widget is not None else mw
    window = _nswindow(target)
    if window is None:
        return False
    try:
        mask = _send(window, "styleMask", restype=ctypes.c_ulong)
        if enabled:
            new_mask = mask | _NS_WINDOW_STYLE_MASK_FULL_SIZE_CONTENT_VIEW
        else:
            new_mask = mask & ~_NS_WINDOW_STYLE_MASK_FULL_SIZE_CONTENT_VIEW
        if new_mask != mask:
            # Toggling fullSizeContentView keeps the *content* size fixed, so
            # AppKit resizes the window frame by the title bar's height instead.
            # Anki saves that shrunken frame on quit and reopens smaller every
            # time, so put the frame back exactly where it was.
            frame = _send(window, "frame", restype=_NSRect)
            _send(window, "setStyleMask:", ctypes.c_ulong(new_mask),
                  argtypes=[ctypes.c_ulong], restype=None)
            _send(window, "setFrame:display:", frame, ctypes.c_bool(True),
                  argtypes=[_NSRect, ctypes.c_bool], restype=None)
        _send(window, "setTitlebarAppearsTransparent:", ctypes.c_bool(bool(enabled)),
              argtypes=[ctypes.c_bool], restype=None)
        _send(window, "setTitleVisibility:",
              ctypes.c_long(_NS_WINDOW_TITLE_HIDDEN if enabled else _NS_WINDOW_TITLE_VISIBLE),
              argtypes=[ctypes.c_long], restype=None)
        # Kill the hairline AppKit draws where the title bar meets the content.
        # A transparent title bar still gets it unless the separator is off.
        if _responds_to(window, "setTitlebarSeparatorStyle:"):
            _send(window, "setTitlebarSeparatorStyle:",
                  ctypes.c_long(_NS_TITLEBAR_SEPARATOR_NONE if enabled
                                else _NS_TITLEBAR_SEPARATOR_AUTOMATIC),
                  argtypes=[ctypes.c_long], restype=None)
        _set_titlebar_decoration_hidden(window, enabled)
        _set_safe_area_respected(target, not enabled)
        return True
    except Exception as exc:
        print(f"[Onigiri] macOS title bar: could not update the window: {exc}")
        return False


def is_enabled() -> bool:
    if not is_supported():
        return False
    try:
        from . import config
        return bool(config.get_config_readonly().get("hideMacTitleBar", False))
    except Exception:
        return False


def refresh() -> None:
    """Re-assert the current setting on the main window.

    Qt drops these flags whenever it recreates the native window (profile
    switches, full-screen toggles), so this is called from a few lifecycle
    points rather than only once at startup.
    """
    if not is_supported():
        return
    apply(is_enabled())


def inset_css(context_kind: str = "page") -> str:
    """Top inset for the web pages, so nothing hides behind the traffic lights.

    The inset goes on the *content* containers, never on `body`: the background
    image is a `body::before` layer and body's own background-color paints on top
    of the padding box, so padding the body draws an opaque band across the top of
    the picture -- exactly the strip this mode is meant to get rid of. Padding the
    (transparent) containers instead lets the background run to the window's top
    edge with the sidebar and the widget grid sitting below the traffic lights.

    `context_kind` picks the containers to inset:
      "deck_browser" - the main menu flex row (sidebar + widget grid).
      "toolbar"      - Anki's own top toolbar, which has no background layer of
                       its own to protect, so body padding is the right tool.
      "page"         - overview/congrats: vertically centred layouts, and a top
                       bar that is horizontally centred, so the traffic lights
                       (top left) never reach any of it. Only the seam fix.
    """
    if not (is_supported() and is_enabled()):
        return ""
    # The background layer is a full-viewport pseudo-element centred with a
    # transform. At the window's top edge its half-pixel rounding can fall one
    # device pixel short and let the page's light background show through as a
    # hairline right under the traffic lights. Overshooting it a couple of pixels
    # on every side hides the seam without disturbing the centring.
    rules = """
    body::before,
    body::after {
        width: calc(100vw + 4px) !important;
        height: calc(100vh + 4px) !important;
    }
    """
    if context_kind == "deck_browser":
        rules += """
        .container.modern-main-menu {
            padding-top: var(--onigiri-mac-titlebar-inset) !important;
            box-sizing: border-box !important;
        }
        /* Stacked layout sizes the sidebar against the full viewport; without
           this it would run past the bottom by exactly the inset. */
        .container.modern-main-menu.onigiri-cycle-stacked .sidebar-left {
            max-height: calc(100vh - 30px - var(--onigiri-mac-titlebar-inset)) !important;
        }
        """
    elif context_kind == "toolbar":
        rules += """
        body {
            padding-top: var(--onigiri-mac-titlebar-inset) !important;
            box-sizing: border-box !important;
        }
        """
    return f"""
    <style id="onigiri-mac-titlebar-inset">
        :root {{ --onigiri-mac-titlebar-inset: {TITLEBAR_INSET}px; }}
        {rules}
    </style>
    """


# The reviewer/overview top bar deliberately gets no inset. It is horizontally
# centred and the traffic lights sit in the left corner, so the two never meet;
# offsetting it only opened a gap above the buttons. Clicks land fine up there --
# with fullSizeContentView on, AppKit hit-tests the whole window down to Qt's
# view, title-bar strip included.
