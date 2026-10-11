# The WebUI settings window: a thin QDialog hosting one AnkiWebView.
#
# All layout, animation and hover behaviour lives in web/settings.{html,css,js}.
# Python's only jobs here are: render the page, answer bridge commands, run the
# native pickers (which stay Qt because other modules share them), and commit.

import json
import re

from aqt import mw
from aqt.qt import (
    QColor,
    QDialog,
    QFileDialog,
    QLabel,
    Qt,
    QTimer,
    QVBoxLayout,
    QWidget,
)
from aqt.utils import openLink
from aqt.webview import AnkiWebView

from .. import mac_titlebar
from ..translations import tr
from . import gallery, render, schema, side_effects, theme_store
from .store import Store

BRIDGE_PREFIX = "osw:"

# The native picker accepts Qt colour names, while several CSS-facing add-on
# settings store translucent colours as ``rgba(r, g, b, alpha)``. Convert that
# representation before opening the picker and restore its alpha after a new
# hue is chosen, so a Gallery swatch always opens on the colour it shows.
_CSS_RGBA = re.compile(
    r"^rgba\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*"
    r"(0(?:\.\d+)?|1(?:\.0+)?)\s*\)$",
    re.IGNORECASE,
)


def _picker_color_value(value):
    """Return a Qt-compatible initial value for CSS ``rgba(...)`` strings."""
    match = _CSS_RGBA.match(str(value or ""))
    if not match:
        return value
    red, green, blue = (
        max(0, min(255, int(channel))) for channel in match.groups()[:3]
    )
    return f"#{red:02X}{green:02X}{blue:02X}"


def _with_original_alpha(original, chosen):
    """Keep a CSS colour's opacity when the picker returns its opaque hex."""
    match = _CSS_RGBA.match(str(original or ""))
    if not match or not re.fullmatch(r"#[0-9A-Fa-f]{6}", str(chosen or "")):
        return chosen
    alpha = match.group(4)
    return "rgba({}, {}, {}, {})".format(
        int(chosen[1:3], 16), int(chosen[3:5], 16), int(chosen[5:7], 16), alpha
    )


# The classic dialog's page order. Callers (api/bento.open_settings, the
# openSettings bridge command) may still pass one of its integer indices, so an
# int is resolved through this list rather than against the new page order —
# otherwise "open settings on page 9" would silently land somewhere else.
# "Search" has no WebUI equivalent and falls through to the first page.
LEGACY_PAGE_ORDER = [
    "Search", "Profile", "Modes", "Languages", "Fonts", "Themes", "Main menu",
    "Sidebar", "Overviewer", "Reviewer", "Prep Station", "Hashi Notes",
    "Pomodoro", "Gallery", "Sync",
]

_dialog = None


class SettingsWebDialog(QDialog):
    def __init__(self, parent=None, addon_path=None, initial_page=None):
        super().__init__(parent or mw)
        self.addon_path = addon_path or render.ADDON_ROOT
        self.store = Store()
        self.store.register(
            "settings_sidebar_collapsed",
            {"kind": "config", "key": "settings_sidebar_collapsed"},
            False,
        )
        self.store.register(
            "settings_complexity",
            {"kind": "config", "key": "settings_complexity"},
            "advanced",
        )
        self.pages = schema.build_pages()
        self._page_by_id = {page["id"]: page for page in self.pages}
        self._refresh_timer = None
        self._initial_page = self._resolve_initial_page(initial_page)
        self._page_ready = False
        self._startup_failed = False
        self._closed = False

        self.setWindowTitle("Onigiri Settings")
        self._apply_proportional_size()

        # Prevent Qt 6 on macOS from inserting safe-area margins/padding at the top of the dialog
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea, False)
        except Exception:
            pass

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self.web = AnkiWebView(self)
        try:
            self.web.setAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea, False)
        except Exception:
            pass

        for _page, _section, field in schema.iter_fields(self.pages):
            self.store.register(field["id"], field.get("bind"), field.get("default"))

        # Set webview background color matching palette to eliminate white flash/gap
        try:
            pal = render.palette(render.is_dark())
            self.web.page().setBackgroundColor(QColor(pal.get("outer", "#ffffff")))
        except Exception:
            try:
                self.web.page().setBackgroundColor(Qt.GlobalColor.transparent)
            except Exception:
                pass

        if mac_titlebar.is_supported():
            # Settings must always remain a conventional macOS dialog.  In
            # particular, the global Seamless mode belongs to Anki's main
            # window, not this configuration surface: removing this dialog's
            # native title bar also removes its visible title and makes the
            # traffic-light controls float over the web content.
            mac_titlebar.apply(False, self)

        self._layout.addWidget(self.web, 1)

        # Register both channels before navigation begins. Qt's load signal owns
        # startup; Anki's pycmd bridge is intentionally not part of readiness,
        # because it may become available only after the inline page boot ends.
        self.web.set_bridge_command(self._on_bridge, self)
        self.web.loadFinished.connect(self._on_load_finished)
        page_html = render.render(
            self.store, self.pages, initial_page=self._initial_page
        )
        # Do not leave a broken script as an invisible, apparently unresponsive
        # command. A native error surface is guaranteed to replace the webview if
        # the page does not complete its boot handshake.
        self._load_watchdog = QTimer(self)
        self._load_watchdog.setSingleShot(True)
        self._load_watchdog.timeout.connect(self._show_load_error)
        self._load_watchdog.start(5000)
        self.web.stdHtml(page_html)

    # ─── window ────────────────────────────────────────────────────────────────

    def _apply_proportional_size(self):
        screen = (self.screen() if hasattr(self, "screen") else None) or (mw.app.primaryScreen() if mw and mw.app else None)
        if screen is None:
            self.setMinimumSize(1080, 480)
            self.resize(self.minimumWidth(), 510)
            return
        available = screen.availableGeometry()
        width, height = available.width(), available.height()
        # 980 let a preview card's own header row (STYLE/CHART segmented
        # control + Sync/Dynamic + light/dark + Reset) run out of room and
        # wrap to two lines — that row has no CSS min-width of its own since
        # it has to fit sidebar-collapsed layouts too, so the floor here is
        # what actually keeps it on one line.
        self.setMinimumWidth(min(max(1080, int(width * 0.58)), width))
        self.setMinimumHeight(min(max(480, int(height * 0.46)), height))
        self.setMaximumHeight(height)
        # No page's own content grows past .osw-page's 940px cap, so once the
        # window is wider than rail + gutters + that 940px there is nothing
        # left to fill — just dead background to the right of every preview
        # card. This is that width, with a little slack for borders/scrollbar.
        # Open at the maximum useful width. The content is designed around a
        # 1260px-wide canvas, and narrower widths make dense settings pages
        # needlessly cramped.
        max_dialog_width = 1260
        self.setMaximumWidth(min(max_dialog_width, width))
        default_w = self.maximumWidth()
        # Keep enough vertical room for the UI's minimum layout, then let the
        # web page scroll for longer settings sections. Deliberately do not
        # restore the last window height here: macOS can report a green-button
        # zoomed window as a normal window, which used to persist a full-height
        # value and make every subsequent opening look maximized.
        default_h = min(max(self.minimumHeight(), int(height * 0.65)), height)
        self.resize(default_w, default_h)
        # Centered on the screen the dialog is opening on — not wherever Qt's
        # own default placement (often relative to the main window, or the
        # last-focused app) happens to land it.
        self.move(
            available.x() + (width - default_w) // 2,
            available.y() + (height - default_h) // 2,
        )

    def _resolve_initial_page(self, initial_page):
        """Accepts a page id, a legacy page name, or a legacy integer index."""
        first = self.pages[0]["id"] if self.pages else None
        if initial_page in (None, ""):
            return first
        if isinstance(initial_page, bool):
            return first
        if isinstance(initial_page, int):
            if not 0 <= initial_page < len(LEGACY_PAGE_ORDER):
                return first
            initial_page = LEGACY_PAGE_ORDER[initial_page]
        if initial_page in self._page_by_id:
            return initial_page
        for page in self.pages:
            if page.get("legacy_name") == initial_page:
                return page["id"]
        return first

    # ─── bridge ────────────────────────────────────────────────────────────────

    def _on_bridge(self, cmd):
        if not isinstance(cmd, str) or not cmd.startswith(BRIDGE_PREFIX):
            return None
        body = cmd[len(BRIDGE_PREFIX):]
        name, _, arg = body.partition(":")
        try:
            handler = getattr(self, f"_cmd_{name}", None)
            if handler is None:
                return None
            return handler(arg)
        except Exception:  # noqa: BLE001 - a bad command must not kill the dialog
            import traceback

            print(f"[Onigiri] settings_web bridge error ({body[:60]}):\n{traceback.format_exc()}")
            return None

    def _on_load_finished(self, ok):
        """Verify the synchronous WebUI boot after Chromium finishes loading."""
        if self._closed or self._page_ready or self._startup_failed:
            return
        if not ok:
            self._show_load_error()
            return
        # This callback is provided directly by QWebEnginePage. Unlike pycmd it
        # is available during startup and cannot lose a one-shot ready message.
        self.web.page().runJavaScript(
            "Boolean(document.documentElement.classList.contains('osw-ready') "
            "&& window.onigiriSettings)",
            self._on_boot_checked,
        )

    def _on_boot_checked(self, ready):
        if self._closed or self._page_ready or self._startup_failed:
            return
        if not ready:
            self._show_load_error()
            return
        self._page_ready = True
        self._load_watchdog.stop()
        # Leave the JavaScript result callback before showing a top-level window.
        # Chromium has already completed the DOM build at this point.
        QTimer.singleShot(0, self._reveal)

    def _reveal(self):
        if self._closed or not self._page_ready:
            return
        self.show()
        self.raise_()
        self.activateWindow()
        # Measurements made while a WebView is hidden can be stale on some Qt
        # builds. Re-run only the cheap layout measurements after the first show.
        self._eval_js(
            "window.onigiriSettings && "
            "window.onigiriSettings.afterNativeShow && "
            "window.onigiriSettings.afterNativeShow();"
        )

    def bring_to_front(self, initial_page=None):
        """Reuse a live dialog instead of restarting its WebEngine load."""
        if self._closed or self._startup_failed:
            return False
        if self._page_ready:
            target = self._resolve_initial_page(initial_page)
            if target:
                self._eval_js(
                    "window.onigiriSettings && window.onigiriSettings.showPage(%s);"
                    % json.dumps(target)
                )
            self._reveal()
        # While loading there is deliberately nothing else to do: keeping this
        # instance alive lets its imminent loadFinished signal complete startup.
        return True

    def _show_load_error(self):
        """Show a styled native failure state instead of a blank WebView."""
        if self._closed or self._page_ready:
            return
        self._startup_failed = True
        self.web.hide()
        palette = render.palette(render.is_dark())
        message = QLabel(
            "Onigiri Settings could not finish loading.\n\n"
            "Close this window and try opening Settings again.",
            self,
        )
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setWordWrap(True)
        message.setStyleSheet(
            "QLabel {"
            f"background: {palette['outer']};"
            f"color: {palette['fg']};"
            "font-size: 15px; padding: 48px;"
            "}"
        )
        self._layout.addWidget(message, 1)
        self.show()
        self.raise_()
        self.activateWindow()

    def _cmd_patch(self, arg):
        """Auto-save: apply and persist a small patch as the user edits.

        The page coalesces edits (immediately for discrete controls, debounced
        for typing/dragging) and sends them here, so there is no unsaved window
        and no Save button. Returns a JSON-able dict — Anki hands the handler's
        return value back to the pycmd callback — so the page can toast a real
        error instead of silently losing a value."""
        try:
            values = json.loads(arg or "{}")
        except ValueError:
            return {"ok": False, "error": "Malformed patch"}
        if not isinstance(values, dict) or not values:
            return {"ok": True, "applied": []}

        touched, failures = self.store.apply_now(values)
        hooks = self._hooks_for(touched)
        hook_failures = side_effects.run(hooks, self.store)
        
        is_profile_patch = any(
            k.startswith(("modern_menu_profile_", "g_rl_chip_")) or k in (
                "userName", "userBirthday", "profile_bio", "profile_music",
                "g_profile_level_game", "g_rl_dynamic_chip_colors",
                "g_nook_enabled", "g_nook_profile_bar", "g_onigimon_enabled", "g_hexagon_enabled",
            )
            for k in touched
        )
        if is_profile_patch:
            try:
                from ..refresh import schedule_ui_refresh
                schedule_ui_refresh(0)
            except Exception:
                self._schedule_refresh()
        else:
            self._schedule_refresh()

        errors = [f"{name}: {error}" for name, error in list(failures) + list(hook_failures)]
        if errors:
            return {"ok": False, "error": "; ".join(errors), "applied": sorted(touched)}
        result = {"ok": True, "applied": sorted(touched)}
        if is_profile_patch:
            result["profilePreview"] = render.profile_preview_context()
        if "onigiri_theme_mode" in touched:
            dark = render.is_dark()
            palette = render.palette(dark)
            self.web.page().setBackgroundColor(QColor(palette["outer"]))
            result["appearance"] = {
                "dark": dark,
                "palette": palette,
                "accent": render.accent_color(),
            }
        return result

    def _cmd_profile_context(self, _arg):
        return render.profile_preview_context()

    def _cmd_grid_background(self, _arg):
        """Mirror the displayed menu backdrop, including its slideshow frame."""
        if self._closed or mw is None or not getattr(mw, "web", None):
            return None

        def push_background(background):
            if self._closed:
                return
            self._eval_js(
                "window.onigiriSettings && "
                "window.onigiriSettings.setGridBackground(%s);"
                % json.dumps(background)
            )

        # Read the actual rendered layers rather than starting another
        # slideshow clock in Settings. The two views then show the same image
        # even when the menu was opened long before this dialog.
        mw.web.page().runJavaScript(
            r"""
            (function () {
                const menu = document.querySelector('.container.modern-main-menu');
                if (!menu) return null;
                const style = getComputedStyle(menu);
                function layer(pseudo) {
                    const css = getComputedStyle(menu, pseudo);
                    const matrix = /^matrix\(([^,]+)/.exec(css.transform);
                    return {
                        image: css.backgroundImage,
                        position: css.backgroundPosition,
                        size: css.backgroundSize,
                        opacity: css.opacity,
                        filter: css.filter,
                        scale: matrix ? Number(matrix[1]) : 1
                    };
                }
                return {
                    dark: document.documentElement.classList.contains('night-mode')
                        || document.body.classList.contains('night-mode'),
                    color: style.backgroundColor,
                    base: layer('::before'),
                    next: layer('::after')
                };
            })();
            """,
            push_background,
        )
        return {"ok": True}

    def _cmd_close(self, _arg):
        self.close()
        return {"ok": True}

    def _cmd_rail(self, arg):
        """Rail collapsed/expanded. Window chrome rather than a setting, but it
        rides the same auto-save path so it is remembered next open."""
        _touched, failures = self.store.apply_now({"settings_sidebar_collapsed": arg == "1"})
        for name, error in failures:
            print(f"[Onigiri] settings_web: could not persist rail state ({name}): {error}")
        return {"ok": not failures}

    def _cmd_complexity(self, arg):
        """Persist the settings UI's Simple/Advanced presentation locally."""
        mode = "advanced" if arg == "advanced" else "simple"
        _touched, failures = self.store.apply_now({"settings_complexity": mode})
        for name, error in failures:
            print(f"[Onigiri] settings_web: could not persist complexity ({name}): {error}")
        if not failures:
            self._schedule_refresh()
        return {"ok": not failures}

    # ─── Study Tools actions ────────────────────────────────────────────────

    def _cmd_open_prep_station(self, _arg):
        from .. import prep_station

        prep_station.open_prep_station(self)
        return "ok"

    def _cmd_open_hashi_notes(self, _arg):
        from .. import hashi_notes

        hashi_notes.open_hashi_gallery(self)
        return "ok"

    def _cmd_open_pomodoro(self, _arg):
        from .. import pomodoro

        pomodoro.toggle_widget(self)
        return "ok"

    def _cmd_pomodoro_choose_sound(self, _arg):
        from .. import pomodoro

        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("pomodoro_choose_sound", "Choose Sound File…"),
            "",
            "Audio Files (*.mp3 *.wav *.ogg *.m4a *.flac)",
        )
        if not path:
            return "ok"
        try:
            filename = pomodoro.import_sound_file(path)
            self._push_value("pomodoro_sound_file", filename)
            self._push_value("pomodoro_end_sound", "custom")
            pomodoro.play_test_sound("end", filename)
        except Exception as exc:  # noqa: BLE001
            print(f"[Onigiri] settings_web: Pomodoro sound import failed: {exc}")
        return "ok"

    def _pomodoro_preview_settings(self, arg):
        """Use current WebUI values without waiting for its auto-save."""
        payload = json.loads(arg) if arg else {}
        if not isinstance(payload, dict):
            payload = {}
        return {
            key: payload.get(key, self.store.read("pomodoro_" + key))
            for key in ("start_sound", "end_sound", "sound_file")
        }

    def _cmd_pomodoro_test_start_sound(self, arg):
        from .. import pomodoro

        pomodoro.play_test_sound(
            "start", settings_override=self._pomodoro_preview_settings(arg)
        )
        return "ok"

    def _cmd_pomodoro_test_end_sound(self, arg):
        from .. import pomodoro

        pomodoro.play_test_sound(
            "end", settings_override=self._pomodoro_preview_settings(arg)
        )
        return "ok"

    # ─── Games actions ──────────────────────────────────────────────────────
    #
    # The Games pages' buttons (reset the Nook, buy the island Keys, open a
    # Bento mini-game) all arrive as one command with the action name in the
    # argument, because each of them is a single call into a game manager and
    # not something the page needs its own protocol for.

    def _cmd_games_action(self, arg):
        from . import games_state

        name, _, extra = (arg or "").partition(":")
        # Confirmations are real Qt dialogs, so they need the same overlay host
        # the colour picker uses or they open behind the webview.
        host = self._picker_host()
        try:
            return games_state.run_action(name, parent=host, arg=extra)
        finally:
            self._release_picker_host(host)

    def _cmd_games_context(self, _arg):
        """The Games pages' live state, fetched when one of them is first
        opened. Kept off the initial render because reading it imports the game
        modules — the two biggest files in the add-on — which every other page
        would otherwise pay for."""
        return {"ok": True, "games": render.games_live_context()}

    def _cmd_games_companions(self, arg):
        """Re-reads the Onigimon roster from Ankimon (the Refresh button)."""
        from . import games_state

        return {
            "ok": True,
            "companions": games_state.companions(refresh=arg == "1"),
            "preview": games_state.active_companion_preview(),
        }

    def _cmd_games_pick_companion(self, arg):
        """Selecting a companion is not a plain config write: the manager picks
        up its nickname, which the page then shows in its own field."""
        from . import games_state

        self.store.apply_now({"g_onigimon_companion": str(arg or "")})
        nickname = self.store.read("g_onigimon_nickname")
        self._push_value("g_onigimon_nickname", nickname)
        self._schedule_refresh()
        return {
            "ok": True,
            "nickname": nickname,
            "preview": games_state.active_companion_preview(),
        }

    def _cmd_color(self, arg):
        field_id, _, current = arg.partition(":")
        chosen, ok = self._run_color_picker(_picker_color_value(current) or "#00A982")
        if ok and chosen:
            self._push_value(field_id, _with_original_alpha(current, chosen))
        return "ok"

    def _cmd_font(self, arg):
        field_id, _, current = arg.partition(":")
        try:
            from ..ui_kit.font_picker import FontPickerDialog
        except Exception as exc:  # noqa: BLE001
            print(f"[Onigiri] settings_web: font picker unavailable: {exc}")
            return None
        host = self._picker_host()
        try:
            accent_field = "gal_accent_dark" if render.is_dark() else "gal_accent_light"
            picker_accent = self.store.read(accent_field) or render.accent_color()
            dlg = FontPickerDialog(
                current or "system",
                self.addon_path,
                host,
                sample_text="Onigiri",
                title=tr("fonts", "Fonts"),
                accent_color=picker_accent,
            )
            dlg.fontSelected.connect(lambda key: self._push_value(field_id, key))
            dlg.exec()
        finally:
            self._release_picker_host(host)
        return "ok"

    # ─── icon popover ───────────────────────────────────────────────────────────
    #
    # Same shape as the image gallery above: an in-page popover, Python's job
    # limited to the filesystem. The bundled system icons are shipped once in
    # the page context (render.pickable_icons_context) since they never change;
    # these commands only ever touch user_files/icons.

    def _icon_reply(self, **extra):
        reply = {
            "ok": True,
            "icons": gallery.list_images("icons", url_for=render.gallery_url, extensions=gallery.ICON_EXTENSIONS),
        }
        reply.update(extra)
        return reply

    def _cmd_icon_list(self, _arg):
        return self._icon_reply()

    def _cmd_icon_import(self, arg):
        kind = (arg or "svg").strip().lower()
        extensions = (".svg",) if kind == "svg" else (".png",)
        host = self._picker_host()
        try:
            added, error = gallery.import_images(
                "icons",
                parent=host,
                title=tr("import_image", "Import image"),
                extensions=extensions,
                filter_label="SVG" if kind == "svg" else "PNG",
            )
        finally:
            self._release_picker_host(host)
        if error:
            return {"ok": False, "error": error}
        return self._icon_reply(added=added)

    def _cmd_icon_delete(self, arg):
        name = arg or ""
        error = gallery.delete_image("icons", name)
        if error:
            return {"ok": False, "error": error}
        return self._icon_reply()

    def _cmd_donate(self, _arg):
        try:
            from ..donations_dialog import DonationsDialog

            DonationsDialog(self).exec()
        except Exception as exc:  # noqa: BLE001
            print(f"[Onigiri] settings_web: donations dialog failed: {exc}")
        return "ok"

    def _cmd_bugs(self, _arg):
        openLink("https://github.com/thepeacemonk/Onigiri")
        return "ok"

    def _cmd_link(self, arg):
        if arg.startswith("https://") or arg.startswith("http://"):
            openLink(arg)
        return "ok"

    def _cmd_haptic(self, arg):
        try:
            pattern = int(arg) if arg and arg.isdigit() else 0
        except Exception:
            pattern = 0
        self._trigger_mac_haptic(pattern)
        return "ok"

    # ─── image gallery ─────────────────────────────────────────────────────────
    #
    # The page owns the gallery UI (an in-webview popover, not a Qt dialog), so
    # Python's whole job is the filesystem: list, import, delete. Each command
    # answers with the folder's *current* contents, which means the page never
    # has to guess what changed or ask again.

    def _gallery_arg(self, arg):
        try:
            payload = json.loads(arg or "{}")
        except ValueError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _gallery_reply(self, folder, **extra):
        reply = {
            "ok": True,
            "folder": folder,
            "images": gallery.list_images(folder, url_for=render.gallery_url),
        }
        reply.update(extra)
        return reply

    def _cmd_gallery_list(self, arg):
        return self._gallery_reply(self._gallery_arg(arg).get("folder", ""))

    def _cmd_gallery_import(self, arg):
        payload = self._gallery_arg(arg)
        folder = payload.get("folder", "")
        # A native chooser can still open behind Anki's WebEngine surface on
        # macOS after returning from Review. Use the same temporary top-level
        # host as the color/font pickers so the dialog is always visible.
        host = self._picker_host()
        try:
            added, error = gallery.import_images(
                folder,
                parent=host,
                title=tr("import_image", "Import image"),
            )
        finally:
            self._release_picker_host(host)
        if error:
            return {"ok": False, "error": error, "folder": folder}
        return self._gallery_reply(folder, added=added)

    def _cmd_gallery_delete(self, arg):
        payload = self._gallery_arg(arg)
        folder = payload.get("folder", "")
        name = payload.get("name", "")
        error = gallery.delete_image(folder, name)
        if error:
            return {"ok": False, "error": error, "folder": folder}

        # A deleted file must stop being referenced, including by settings the
        # WebUI has not ported yet — hence the sweep over both stores rather
        # than only the fields this dialog knows about. store.config is the
        # dialog's live copy, so it is mutated in place: writing the file from
        # a fresh read would be undone by the next auto-save patch.
        stores = [self.store.config]
        try:
            if mw and mw.col:
                stores.append(mw.col.conf)
        except Exception:
            pass
        changed_keys = gallery.clear_references(folder, name, stores)
        if changed_keys:
            try:
                self.store.write_config()
            except Exception as exc:  # noqa: BLE001
                print(f"[Onigiri] settings_web gallery: config write failed: {exc}")
            self._schedule_refresh()

        return self._gallery_reply(
            folder,
            deleted=name,
            # Field ids the page should blank locally. Python already persisted
            # the change, so the page updates its copy without echoing a patch.
            cleared=self._field_ids_for_keys(changed_keys),
        )

    def _field_ids_for_keys(self, keys):
        """Registered field ids whose bind resolves to one of `keys`.

        Matches a plain `{"key": ...}` bind directly, and a nested
        `{"path": [...]}` bind (e.g. a Fonts color pair bound to
        colors.light.--fg) on its last path segment — the theme apply/reset
        keys are raw color tokens like "--fg", which *are* that segment."""
        if not keys:
            return []
        wanted = set(keys)
        out = []
        for _page, _section, field in schema.iter_fields(self.pages):
            bind = field.get("bind") or {}
            key = bind.get("key")
            if key is None:
                path = bind.get("path")
                key = path[-1] if path else None
            if key in wanted:
                out.append(field["id"])
        return out

    # ─── themes ─────────────────────────────────────────────────────────────────
    #
    # A theme touches dozens of config/mw.col.conf keys spanning pages this
    # dialog has and hasn't ported yet, so applying one bypasses Store's
    # field-id-keyed patch path entirely (see theme_store.apply_theme) and
    # writes store.config / mw.col.conf directly — the same thing
    # _cmd_gallery_delete already does when a deleted file's references live on
    # unported pages. `refresh` preserves the narrow control update path, while
    # `preview` returns every bound WebUI value as one coherent snapshot so all
    # Settings previews repaint from the same theme at the same time.
    #
    # There is no _cmd_theme_list: the grid seeds from CTX.themeGallery (like
    # the gallery popover's initial paint) and only changes through this same
    # dialog's own import/delete replies from here on.

    def _theme_arg(self, arg):
        try:
            payload = json.loads(arg or "{}")
        except ValueError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _theme_refresh_payload(self, touched_keys):
        return {
            field_id: self.store.read(field_id)
            for field_id in self._field_ids_for_keys(touched_keys)
        }

    def _theme_preview_payload(self):
        """Return a coherent snapshot for every Settings preview.

        Applying a theme writes both add-on and collection config directly. A
        preview can depend on either store, so its fields are not necessarily
        among the raw keys reported as touched. Sending all bound fields
        together prevents a preview from mixing values from two themes.
        """
        return {
            field["id"]: self.store.read(field["id"])
            for _page, _section, field in schema.iter_fields(self.pages)
            if field.get("bind")
        }

    def _cmd_theme_apply(self, arg):
        payload = self._theme_arg(arg)
        kind, name = payload.get("kind", ""), payload.get("name", "")
        theme_data = theme_store.get_theme(kind, name)
        if theme_data is None:
            return {"ok": False, "error": f"theme not found: {name!r}"}
        touched = theme_store.apply_theme(self.store, theme_data)
        self._schedule_refresh()
        return {"ok": True, "name": name, "refresh": self._theme_refresh_payload(touched),
                "preview": self._theme_preview_payload(),
                "accent": render.accent_color(),
                "palettes": self.store.config.get("colors", {})}

    def _cmd_theme_reset(self, _arg):
        touched = theme_store.reset_theme_to_default(self.store)
        self._schedule_refresh()
        return {"ok": True, "refresh": self._theme_refresh_payload(touched),
                "preview": self._theme_preview_payload(),
                "accent": render.accent_color(),
                "palettes": self.store.config.get("colors", {})}

    def _cmd_theme_import(self, _arg):
        # Parented to the dialog itself, not _picker_host(): same reasoning as
        # _cmd_gallery_import — a native QFileDialog is its own top-level
        # window and is never painted over by the webview.
        summary, error = theme_store.import_theme(parent=self)
        if error:
            return {"ok": False, "error": error}
        if summary is None:
            return {"ok": True, "cancelled": True}
        return {"ok": True, "theme": summary}

    def _cmd_theme_export(self, arg):
        payload = self._theme_arg(arg)
        name = str(payload.get("name", "")).strip()
        if not name:
            return {"ok": False, "error": "Name your theme first."}
        path, error = theme_store.export_theme(self.store, name, parent=self)
        if error:
            return {"ok": False, "error": error}
        if path is None:
            return {"ok": True, "cancelled": True}
        return {"ok": True, "name": name}

    def _cmd_theme_delete(self, arg):
        payload = self._theme_arg(arg)
        error = theme_store.delete_user_theme(payload.get("name", ""))
        if error:
            return {"ok": False, "error": error}
        return {"ok": True, "user": theme_store.list_user_themes()}

    def _trigger_mac_haptic(self, pattern=0):
        _trigger_mac_haptic_native(pattern)

    # ─── native pickers ────────────────────────────────────────────────────────

    def _picker_host(self):
        """A transparent always-on-top window laid over this dialog.

        An AnkiWebView owns a native surface that paints over sibling widgets, so
        a picker parented directly to this dialog would appear *behind* the page.
        Giving it its own top-level host puts it above. (Same trick as the Hashi
        Notes editor — see hashi_notes._HashiNoteEditorMixin._open_color_dialog.)
        """
        host = QWidget(None)
        host.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        host.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        host.setGeometry(self.frameGeometry())
        host.show()
        host.raise_()
        host.activateWindow()
        return host

    def _release_picker_host(self, host):
        try:
            host.close()
            host.deleteLater()
        except Exception:
            pass
        self.raise_()
        self.activateWindow()

    def _run_color_picker(self, current):
        from ..onigiri_color_picker import OnigiriColorDialog

        host = self._picker_host()
        try:
            return OnigiriColorDialog.getColor(current, host)
        finally:
            self._release_picker_host(host)

    # ─── page <-> python ───────────────────────────────────────────────────────

    def _eval_js(self, code):
        try:
            self.web.eval(code)
        except Exception:
            pass

    def _push_value(self, field_id, value):
        """Writes a value chosen in a native picker back into the page."""
        self._eval_js(
            "window.onigiriSettings && window.onigiriSettings.setFieldValue(%s, %s);"
            % (json.dumps(field_id), json.dumps(value))
        )

    def _toast(self, message):
        self._eval_js(
            "window.onigiriSettings && window.onigiriSettings.toast(%s);" % json.dumps(message)
        )

    # ─── saving ────────────────────────────────────────────────────────────────

    def _hooks_for(self, touched):
        """Post-save hooks of every page that owns one of the touched fields."""
        hooks = []
        for page in self.pages:
            page_field_ids = {
                field["id"]
                for section in page.get("sections", [])
                for field in section.get("fields", [])
            }
            if page_field_ids & set(touched):
                hooks.extend(page.get("post_save", []))
        return list(dict.fromkeys(hooks))

    def _schedule_refresh(self):
        """Coalesces the Anki-side refresh across a burst of patches.

        refresh.schedule_ui_refresh() re-renders the deck browser, which is far
        too heavy to run per keystroke even though it de-dupes internally."""
        if self._refresh_timer is None:
            self._refresh_timer = QTimer(self)
            self._refresh_timer.setSingleShot(True)
            self._refresh_timer.timeout.connect(side_effects.refresh_anki)
        self._refresh_timer.start(600)

    def closeEvent(self, event):
        global _dialog
        self._closed = True
        try:
            self._load_watchdog.stop()
        except Exception as exc:  # noqa: BLE001
            print(f"[Onigiri] settings_web: could not stop load watchdog: {exc}")
        # A pending coalesced refresh must still land once the window is gone.
        if self._refresh_timer is not None and self._refresh_timer.isActive():
            self._refresh_timer.stop()
            side_effects.refresh_anki()
        if _dialog is self:
            _dialog = None
        super().closeEvent(event)


def open_settings(initial_page=0, parent=None, addon_path=None):
    global _dialog
    try:
        if _dialog is not None:
            if _dialog.bring_to_front(initial_page):
                return _dialog
            stale = _dialog
            _dialog = None
            stale.close()
            stale.deleteLater()
    except Exception:
        _dialog = None
    _dialog = SettingsWebDialog(parent or mw, addon_path=addon_path, initial_page=initial_page)
    return _dialog


def _trigger_mac_haptic_native(pattern=0):
    if not mac_titlebar.is_supported():
        return
    try:
        import ctypes
        import ctypes.util

        pattern = int(pattern)
        if pattern not in (0, 1, 2):
            return
        appkit = ctypes.cdll.LoadLibrary(ctypes.util.find_library("AppKit"))
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p

        # ctypes defaults untyped integer arguments to C int, truncating
        # Objective-C pointers on 64-bit macOS.  Each objc_msgSend call also
        # needs the method's fixed signature for the Apple ARM64 ABI.
        address = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
        send_object = ctypes.CFUNCTYPE(
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p
        )(address)
        send_feedback = ctypes.CFUNCTYPE(
            None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long, ctypes.c_ulong
        )(address)

        cls = objc.objc_getClass(b"NSHapticFeedbackManager")
        if not cls:
            return
        performer = send_object(cls, objc.sel_registerName(b"defaultPerformer"))
        if performer:
            send_feedback(
                performer,
                objc.sel_registerName(b"performFeedbackPattern:performanceTime:"),
                pattern,
                0,
            )
    except Exception:
        pass
