import os
import json
from aqt import mw, gui_hooks
from aqt.deckbrowser import DeckBrowser
from aqt.reviewer import Reviewer
from aqt.overview import Overview
from aqt.toolbar import Toolbar, BottomBar
from aqt.qt import (QWidget, QHBoxLayout, QPushButton, Qt, QToolBar, QAction, QTimer,
                    QPainter, QPen, QColor, QEvent, QPropertyAnimation, QEasingCurve)
try:
    from PyQt6.QtCore import QRect
    from PyQt6.QtWidgets import QGraphicsOpacityEffect
except ImportError:
    try:
        from PyQt5.QtCore import QRect
        from PyQt5.QtWidgets import QGraphicsOpacityEffect
    except ImportError:
        QRect = None
        QGraphicsOpacityEffect = None

# Import local modules with proper error handling
try:
    from . import onigiri_renderer
    from . import patcher
    from . import settings, heatmap, fonts, gamification_settings
    from . import menu_buttons
    from . import welcome_dialog
    from . import credits_dialog
    from . import create_deck_dialog
    from . import manual_reset_restaurant_level
    from . import icon_chooser
    from . import coloris_picker
    from . import themes
    from . import sidebar_api
    from . import favorites_cleanup
    from .gamification import mochi_messages
    from .gamification import mod_transfer_window
    from .gamification import focus_dango
    from . import birthday_dialog
    from . import deck_tree_updater
    from . import webview_handlers
except ImportError as e:
    print(f"Warning: Could not import local modules: {e}")
    # Continue with available modules
    pass
from .gamification.taiyaki_store import open_taiyaki_store



addon_path = os.path.dirname(__file__)
addon_package = mw.addonManager.addonFromModule(__name__)
user_files_root = f"/_addons/{addon_package}/user_files"
web_assets_root = f"/_addons/{addon_package}/web"

# Make addon_path available to other modules
import sys
sys.modules[__name__].addon_path = addon_path

def generate_notification_position_css(conf):
    """Generates CSS for notification positioning logic."""
    pos = conf.get("onigiri_reviewer_notification_position", "top-right")
    
    css = ".onigiri-notification-stack { "
    
    # Defaults (resetting properties that might conflict)
    css += "top: auto; bottom: auto; left: auto; right: auto; transform: none; "
    
    # Base top offset calculation: Header Offset + 20px padding
    top_offset = "calc(var(--onigiri-reviewer-header-offset, 0px) + 5px)"
    
    if pos == "top-left":
        css += f"top: {top_offset}; left: 20px; align-items: flex-start; flex-direction: column; "
    elif pos == "top-center":
        css += f"top: {top_offset}; left: 50%; transform: translateX(-50%); align-items: center; flex-direction: column; "
    elif pos == "top-right":
        css += f"top: {top_offset}; right: 20px; align-items: flex-end; flex-direction: column; "
    elif pos == "bottom-left":
        css += "bottom: 20px; left: 20px; align-items: flex-start; flex-direction: column-reverse; "
    elif pos == "bottom-center":
        css += "bottom: 20px; left: 50%; transform: translateX(-50%); align-items: center; flex-direction: column-reverse; "
    elif pos == "bottom-right":
        css += "bottom: 20px; right: 20px; align-items: flex-end; flex-direction: column-reverse; "
    else:
        # Fallback to top-right
        css += f"top: {top_offset}; right: 20px; align-items: flex-end; flex-direction: column; "
        
    css += "}"
    return f"<style>{css}</style>"

def inject_menu_files(web_content, context):
    conf = config.get_config()
    should_hide = conf.get("hideNativeHeaderAndBottomBar", False)
    is_deck_browser = isinstance(context, DeckBrowser)
    is_reviewer = isinstance(context, Reviewer)
    is_overview = isinstance(context, Overview)
    is_top_toolbar = isinstance(context, Toolbar)
    is_bottom_toolbar = isinstance(context, BottomBar)
    is_reviewer_bottom_bar = type(context).__name__ == "ReviewerBottomBar"
    # Inject global Onigiri CSS only for deck browser and overview, NOT reviewer
    # Reviewer has its own dedicated CSS and doesn't need text-related global styles
    if is_deck_browser or is_overview:
        web_content.head += patcher.generate_dynamic_css(conf)
    if is_deck_browser:
        css_path = os.path.join(addon_path, "web", "menu.css")
        try:
            with open(css_path, "r", encoding="utf-8") as f:
                web_content.head += f"<style>{f.read()}</style>"
        except FileNotFoundError:
            pass
        heatmap_css_path = os.path.join(addon_path, "web", "heatmap.css")
        try:
            with open(heatmap_css_path, "r", encoding="utf-8") as f:
                web_content.head += f"<style>{f.read()}</style>"
        except FileNotFoundError:
            pass
        web_content.head += patcher.generate_profile_bar_fix_css()
        web_content.head += patcher.generate_deck_browser_backgrounds(addon_path)
        web_content.head += patcher.generate_icon_css(addon_package, conf)
        web_content.head += patcher.generate_conditional_css(conf)
        web_content.head += patcher.generate_icon_size_css()
        web_content.head += f'<link rel="stylesheet" href="{web_assets_root}/notifications.css">'
        web_content.head += f'<script src="{web_assets_root}/injector.js"></script>'
        web_content.head += f'<script src="{web_assets_root}/engine.js"></script>'
        web_content.head += f'<script src="{web_assets_root}/heatmap.js"></script>'
        web_content.head += f'<script src="{web_assets_root}/notifications.js"></script>'
        
        # Inject heatmap data for robust rendering
        if "heatmap" in conf.get("onigiriWidgetLayout", {}).get("grid", {}):
            try:
                h_data, h_conf = heatmap.get_heatmap_and_config()
                web_content.head += f"""
                <script>
                    window.onigiriHeatmapData = {json.dumps(h_data)};
                    window.onigiriHeatmapConfig = {json.dumps(h_conf)};
                </script>
                """
            except Exception:
                pass
        
    elif is_reviewer:
        silent_notifs = "true" if conf.get("onigiri_reviewer_silent_notifications", False) else "false"
        web_content.head += f'<script>window.onigiriSilentNotifications = {silent_notifs};</script>'
        web_content.head += f'<link rel="stylesheet" href="{web_assets_root}/notifications.css">'
        web_content.head += generate_notification_position_css(conf)
        web_content.head += patcher.generate_reviewer_background_css(addon_path)
        web_content.head += patcher.generate_reviewer_buttons_css(conf)
        top_bar_html, top_bar_css = patcher.generate_reviewer_top_bar_html_and_css()
        web_content.head += top_bar_css
        escaped_top_bar_html = top_bar_html.replace("`", "\\`")
        js_injector = f"""
        <script>
            document.addEventListener('DOMContentLoaded', function() {{
                if (!document.getElementById('onigiri-background-div')) {{
                    const bgDiv = document.createElement('div');
                    bgDiv.id = 'onigiri-background-div';
                    document.body.prepend(bgDiv);
                }}

                const insertTopBar = () => {{
                    const topBarHtml = `{escaped_top_bar_html}`;
                    if (!topBarHtml.trim()) {{
                        return null;
                    }}
                    let headerEl = document.getElementById('onigiri-reviewer-header');
                    if (!headerEl) {{
                        document.body.insertAdjacentHTML('afterbegin', topBarHtml);
                        headerEl = document.getElementById('onigiri-reviewer-header');
                    }}
                    return headerEl;
                }};

                const headerEl = insertTopBar();
                if (!headerEl) {{
                    return;
                }}

                const updateHeaderOffset = () => {{
                    const header = document.getElementById('onigiri-reviewer-header');
                    if (!header) {{
                        return;
                    }}
                    const styles = window.getComputedStyle(header);
                    const marginTop = parseFloat(styles.marginTop) || 0;
                    const marginBottom = parseFloat(styles.marginBottom) || 0;
                    const offset = header.offsetHeight + marginTop + marginBottom;
                    document.body.style.setProperty('--onigiri-reviewer-header-offset', `${{Math.ceil(offset)}}px`);
                }};

                updateHeaderOffset();
                window.addEventListener('resize', updateHeaderOffset);

                if ('ResizeObserver' in window) {{
                    const resizeObserver = new ResizeObserver(updateHeaderOffset);
                    resizeObserver.observe(headerEl);
                }} else {{
                    // As a fallback, re-run after layout-affecting mutations.
                    const mutationObserver = new MutationObserver(updateHeaderOffset);
                    mutationObserver.observe(document.body, {{ attributes: true, childList: false, subtree: false }});
                }}
            }});
        </script>
        """
        web_content.head += js_injector
        web_content.head += f'<script src="{web_assets_root}/notifications.js"></script>'
    elif is_overview:
        web_content.head += f'<link rel="stylesheet" href="{web_assets_root}/notifications.css">'
        web_content.head += patcher.generate_overview_background_css(addon_path)
        _top_bar_html, top_bar_css = patcher.generate_reviewer_top_bar_html_and_css()
        web_content.head += top_bar_css
        css_path = os.path.join(addon_path, "web", "overview.css")
        try:
            with open(css_path, "r", encoding="utf-8") as f:
                web_content.head += f"<style>{f.read()}</style>"
        except FileNotFoundError:
            pass
        web_content.head += f'<script src="{web_assets_root}/notifications.js"></script>'
    if is_reviewer_bottom_bar:
        web_content.head += patcher.generate_reviewer_bottom_bar_background_css(addon_path)
        web_content.head += patcher.generate_reviewer_buttons_css(conf)
    elif (is_top_toolbar or is_bottom_toolbar):
        if not should_hide:
            web_content.head += patcher.generate_toolbar_background_css(addon_path)

# Delegate to the webview_handlers module
_on_webview_cmd = webview_handlers.handle_webview_cmd

def maybe_show_welcome_popup():
    """Shows the welcome pop-up if it hasn't been disabled by the user."""
    conf = config.get_config()
    
    # Check if we should force show based on version
    last_seen_version = conf.get("lastSeenWelcomeVersion", "")
    current_version = welcome_dialog.CURRENT_WELCOME_VERSION
    
    # Force show if version doesn't match, OR if user hasn't opted out
    should_show = (last_seen_version != current_version) or conf.get("showWelcomePopup", True)
    
    if should_show:
        welcome_dialog.show_welcome_dialog()

# --- SHOP MENU SETUP ---
def setup_shop_menu():
    """Adds the Shop entry to the Tools menu."""

    


def verify_coin_integrity():
    """Verify coin integrity on startup to prevent cheating."""
    try:
        from .gamification.taiyaki_store import verify_coin_data, generate_coin_token

        # Resolve the profile-specific gamification file (same logic as GamificationData)
        try:
            profile_name = mw.pm.name or "default"
        except Exception:
            profile_name = "default"
        gamification_file = os.path.join(addon_path, 'user_files', f'gamification_{profile_name}.json')
        if os.path.exists(gamification_file):
            with open(gamification_file, 'r+', encoding='utf-8') as f:
                data = json.load(f)
                restaurant_data = data.get('restaurant_level', {})
                coins = int(restaurant_data.get('taiyaki_coins', 0))
                security_token = restaurant_data.get('_security_token')
                
                if security_token is None:
                    # First time - generate token
                    print("[ONIGIRI SECURITY] Generating initial security token")
                    security_token = generate_coin_token(coins)
                    restaurant_data['_security_token'] = security_token
                    f.seek(0)
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.truncate()
                elif not verify_coin_data(coins, security_token):
                    # Tampering detected!
                    print(f"[ONIGIRI SECURITY] ⚠️ TAMPERING DETECTED! Coins: {coins}, Invalid token")
                    restaurant_data['taiyaki_coins'] = 0
                    restaurant_data['_security_token'] = generate_coin_token(0)
                    f.seek(0)
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.truncate()
                    
                    # Also remove from config.json if present
                    conf = config.get_config()
                    if 'achievements' in conf and 'restaurant_level' in conf['achievements']:
                        if 'taiyaki_coins' in conf['achievements']['restaurant_level']:
                            del conf['achievements']['restaurant_level']['taiyaki_coins']
                            config.write_config(conf)
                    
                    print("[ONIGIRI SECURITY] Coins reset to 0 due to tampering")
                else:
                    # Token is valid - ensure config.json does NOT have coins
                    # Check RAW config to see if it exists on disk
                    raw_conf = mw.addonManager.getConfig(addon_package)
                    needs_save = False
                    
                    if raw_conf and 'achievements' in raw_conf and 'restaurant_level' in raw_conf['achievements']:
                        if 'taiyaki_coins' in raw_conf['achievements']['restaurant_level']:
                            print("[ONIGIRI SECURITY] Removing taiyaki_coins from config.json (cleanup)")
                            # We use config.get_config() to get the clean version (which already strips it)
                            # and then save that to overwrite the dirty file.
                            conf = config.get_config()
                            
                            # Sync items/theme to config just in case
                            conf['achievements']['restaurant_level']['owned_items'] = restaurant_data.get('owned_items', ['default'])
                            conf['achievements']['restaurant_level']['current_theme_id'] = restaurant_data.get('current_theme_id', 'default')
                            
                            config.write_config(conf)
                            needs_save = True
                            
                    if not needs_save:
                        # If we didn't need to clean up coins, check if we need to sync items
                        # This is optional but good for consistency
                        pass
    except Exception as e:
        print(f"[ONIGIRI SECURITY] Error verifying coin integrity: {e}")


def apply_full_hide_mode():
    """Hide the menu bar on Windows and Linux if Full Hide Mode is enabled"""
    import platform
    conf = config.get_config()
    full_hide = conf.get("fullHideMode", False)
    
    # Only hide menu bar on Windows and Linux, not macOS
    system = platform.system()
    if full_hide and system in ["Windows", "Linux"]:
        if hasattr(mw, 'menuBar') and mw.menuBar():
            mw.menuBar().hide()
    else:
        if hasattr(mw, 'menuBar') and mw.menuBar():
            mw.menuBar().show()


def setup_global_hooks():
    """
    Sets up global hooks and initial patches that do NOT depend on a loaded profile.
    This runs when the main window initializes.
    """
    # Show the native Qt overlay immediately — covers toolbar + webview during startup
    _create_qt_overlay()

    # Move UI patching to initial_setup so it happens after mw.col is initialized.
    # We rely on using 'wrap' for compatibility, so it's safe to run this later.
    patcher.apply_patches()
    menu_buttons.setup_onigiri_menu(addon_path)
    
    # Install the toolbar bridge AFTER other addons have loaded their hooks
    from . import sidebar_api
    sidebar_api.ensure_capture_hook_is_last()

def on_profile_did_open():
    """
    Runs when a profile is successfully loaded.
    Logic that requires access to `mw.col` (collection/database/config) goes here.
    """
    # Update the Qt startup overlay's background color now that mw.col is available,
    # so it accurately matches the user's configured theme color.
    global _qt_startup_overlay
    if _qt_startup_overlay and not _startup_render_done:
        try:
            is_night = mw.pm.night_mode() if mw.pm else False
            if is_night:
                bg = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
            else:
                bg = mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
            _qt_startup_overlay._bg_color = QColor(bg)
            _qt_startup_overlay.update()
        except Exception:
            pass
        # Safety net: if deck_browser_did_render never fires for any reason,
        # force-dismiss the overlay after 8 seconds so Anki isn't locked out.
        QTimer.singleShot(8000, _dismiss_qt_overlay)

    # Now it is safe to patch overview since mw.col is available
    patcher.patch_overview()

    # Apply Full Hide Mode (hide menu bar on Windows/Linux)
    apply_full_hide_mode()

    # Verify coin integrity on startup (requires mw.col)
    verify_coin_integrity()
    
    # Initialize the Shop Menu Item (requires mw.col)
    setup_shop_menu()

    # Show welcome popup if needed (requires mw.col)
    # Delayed to avoid conflicting with Anki's sync/conflict dialog on startup
    QTimer.singleShot(500, maybe_show_welcome_popup)

    # Show birthday popup if it's the user's birthday (requires mw.col)
    # Delay by 1s to ensure main window is fully rendered for screenshot blur
    QTimer.singleShot(1000, lambda: birthday_dialog.maybe_show_birthday_popup())

    # Menu styling disabled per user request
    # patcher.apply_menu_styling()

    # Ensure our sidebar hook runs last (again) just in case other add-ons loaded late
    sidebar_api.ensure_capture_hook_is_last()
    # Force toolbar redraw so our hook (now last) captures all external links
    try:
        mw.toolbar.draw()
    except Exception as e:
        pass

# --- INITIALIZATION ---

# Move UI patching to top-level so it happens during module load.
# This ensures Onigiri's hooks and wraps are established before other add-ons
# might overwrite them, and prevents unstyled flashes.
# NOTE: patch_congrats_page is safe to run here as it doesn't access mw.col immediately.
patcher.patch_congrats_page()

# Initialize renderer immediately
DeckBrowser._renderPage = onigiri_renderer.render_onigiri_deck_browser

# Patch _render_deck_node at top-level to ensure it's applied before first render
# This is critical - if done later (in apply_patches via main_window_did_init),
# the initial deck browser render would use Anki's default, missing icons/counts
DeckBrowser._render_deck_node = patcher._onigiri_render_deck_node

# ── Qt-level startup overlay ──────────────────────────────────────────────────
# Shows a solid-color native widget that covers the ENTIRE main window
# (toolbar + webview) during startup. Dismissed after first deck browser render.

class _OnigiriStartupOverlay(QWidget):
    """Lightweight Qt widget that paints a full-window splash during startup."""

    def __init__(self, parent, bg_color="#2C2C2C", accent_color="#007aff"):
        super().__init__(parent)
        import time as _time
        self._time = _time          # cache module ref — avoid re-import every tick
        self._start_time = _time.perf_counter()
        self._angle = 0.0           # float so arc is sub-degree smooth, no stepping
        self._bg_color = QColor(bg_color)
        self._accent_color = QColor(accent_color)
        self._dismissed = False
        self._anim = None  # keep alive
        # Cover entire parent immediately
        self.setGeometry(parent.rect())
        self.raise_()
        # Install resize filter so we stay full-window
        parent.installEventFilter(self)
        # ~60 fps spinner — PreciseTimer reduces OS scheduling jitter on Windows
        self._timer = QTimer(self)
        try:
            self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        except AttributeError:
            try:
                self._timer.setTimerType(Qt.PreciseTimer)  # PyQt5
            except AttributeError:
                pass
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)
        self.show()

    def _tick(self):
        if not self._dismissed:
            # Time-based float angle: perfectly smooth regardless of timer jitter.
            # 270°/s = 0.75 rev/s. Float keeps sub-degree precision — no int-step stutter.
            elapsed = self._time.perf_counter() - self._start_time
            self._angle = (elapsed * 270.0) % 360.0
            self.update()

    def paintEvent(self, event):
        try:
            round_cap = Qt.PenCapStyle.RoundCap
        except AttributeError:
            round_cap = Qt.RoundCap  # PyQt5 compat
        try:
            aa_hint = QPainter.RenderHint.Antialiasing
        except AttributeError:
            aa_hint = QPainter.Antialiasing  # PyQt5 compat

        p = QPainter(self)
        p.setRenderHint(aa_hint)
        # Solid background
        p.fillRect(self.rect(), self._bg_color)
        # Spinner
        cx, cy = self.width() // 2, self.height() // 2
        r = 18
        if QRect is None:
            p.end()
            return
        rect = QRect(cx - r, cy - r, r * 2, r * 2)
        # Track
        track_color = QColor(self._bg_color)
        if track_color.lightness() < 128:
            track_color = track_color.lighter(160)
        else:
            track_color = track_color.darker(130)
        track_color.setAlpha(120)
        pen = QPen(track_color)
        pen.setWidth(3)
        pen.setCapStyle(round_cap)
        p.setPen(pen)
        p.drawEllipse(rect)
        # Arc
        pen2 = QPen(self._accent_color)
        pen2.setWidth(3)
        pen2.setCapStyle(round_cap)
        p.setPen(pen2)
        # Qt drawArc uses 1/16th-degree units. Multiply the float angle
        # before converting to int for maximum sub-degree precision.
        start_angle = round((90.0 - self._angle) * 16)
        span_angle  = -270 * 16
        p.drawArc(rect, start_angle, span_angle)
        p.end()

    def eventFilter(self, obj, event):
        if obj is self.parent() and event.type() == QEvent.Type.Resize:
            self.setGeometry(self.parent().rect())
            self.raise_()
        return super().eventFilter(obj, event)

    def dismiss(self):
        if self._dismissed:
            return
        self._dismissed = True
        self._timer.stop()
        try:
            if QGraphicsOpacityEffect is not None:
                effect = QGraphicsOpacityEffect(self)
                self.setGraphicsEffect(effect)
                anim = QPropertyAnimation(effect, b"opacity")
                anim.setDuration(350)
                anim.setStartValue(1.0)
                anim.setEndValue(0.0)
                try:
                    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
                except AttributeError:
                    anim.setEasingCurve(QEasingCurve.OutCubic)
                anim.finished.connect(self.deleteLater)
                try:
                    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
                except AttributeError:
                    anim.start(QPropertyAnimation.DeleteWhenStopped)
                self._anim = anim  # prevent GC
            else:
                # No opacity effect available — just hide immediately
                QTimer.singleShot(0, self.deleteLater)
        except Exception:
            QTimer.singleShot(0, self.deleteLater)

_qt_startup_overlay = None
_startup_render_done = False


def _create_qt_overlay():
    """Create the native Qt overlay over the full Anki main window."""
    global _qt_startup_overlay
    if _qt_startup_overlay is not None:
        return
    if QRect is None:
        return  # Qt imports unavailable — skip overlay
    try:
        # Determine bg color — mw.col is not yet available at main_window_did_init time,
        # so fall back to night-mode detection via the profile manager only.
        is_night = False
        try:
            if mw.pm:
                is_night = mw.pm.night_mode()
        except Exception:
            pass

        # Try to get the user's configured color (may fail if col not loaded yet)
        bg = "#2C2C2C" if is_night else "#F5F5F5"
        try:
            if mw.col:
                if is_night:
                    bg = mw.col.conf.get("modern_menu_bg_color_dark", bg)
                else:
                    bg = mw.col.conf.get("modern_menu_bg_color_light", bg)
        except Exception:
            pass

        _qt_startup_overlay = _OnigiriStartupOverlay(mw, bg_color=bg, accent_color="#007aff")
    except Exception as e:
        print(f"Onigiri: Could not create Qt startup overlay: {e}")


def _dismiss_qt_overlay():
    """Fade out and destroy the native Qt overlay."""
    global _qt_startup_overlay
    if _qt_startup_overlay:
        try:
            _qt_startup_overlay.dismiss()
        except Exception:
            pass
        _qt_startup_overlay = None


def on_deck_browser_did_render(deck_browser: DeckBrowser):
    global _startup_render_done
    conf = config.get_config()
    grid_layout = conf.get("onigiriWidgetLayout", {}).get("grid", {})
    if "heatmap" in grid_layout:
        # Data is now injected via globals in inject_menu_files for reliability.
        # This call handles refreshes or dynamic layout changes.
        deck_browser.web.eval("if (window.OnigiriHeatmap && typeof window.OnigiriHeatmap.autoRender === 'function') { window.OnigiriHeatmap.autoRender(); }")

    if not _startup_render_done:
        # First render on startup: dismiss the Qt overlay (which covers the toolbar)
        # after a short delay so the fully-styled content is visible first.
        _startup_render_done = True
        QTimer.singleShot(400, _dismiss_qt_overlay)
    else:
        # Subsequent re-renders (D-key return, settings change, icon save, sort…):
        # The webview overlay (onigiri-loading-overlay) is the sole overlay for these.
        # Its JS controller auto-dismisses when the engine signals ready; this eval
        # provides a fast-path fallback in case the signal fires very late.
        deck_browser.web.eval("""
(function(){
    var ol = document.getElementById('onigiri-loading-overlay');
    if (ol) {
        ol.classList.add('dismissed');
        setTimeout(function(){ if(ol.parentNode) ol.parentNode.removeChild(ol); }, 420);
    }
})();
""")

    # Update sync status indicator
    update_sync_status_indicator()

def update_sync_status_indicator():
    """Updates the sync status indicator in the Onigiri menu."""
    try:
        sync_status = patcher.get_sync_status()
        # Update in deck browser
        if hasattr(mw, 'deckBrowser') and hasattr(mw.deckBrowser, 'web') and mw.deckBrowser.web:
            mw.deckBrowser.web.eval(f"if (typeof SyncStatusManager !== 'undefined') {{ SyncStatusManager.setSyncStatus('{sync_status}'); }}")
    except Exception as e:
        pass

def on_state_change(new_state, old_state):
    """Called when Anki's state changes - update sync indicator."""
    # When transitioning TO the deck browser from another screen, immediately
    # inject a lightweight overlay onto the current page so the user sees an
    # instant visual response while Python builds the full deck browser HTML.
    # The injected overlay is automatically destroyed when setContent() replaces
    # the page, and the deck browser's own onigiri-loading-overlay takes over.
    if new_state == 'deckBrowser' and old_state in ('reviewer', 'overview', 'resetRequired'):
        try:
            _bg = mw.deckBrowser.web.eval("""
                (function(){
                    if(document.getElementById('onigiri-transition-overlay'))return;
                    var bg=getComputedStyle(document.documentElement).getPropertyValue('--canvas')||'#1a1a1a';
                    var d=document.createElement('div');
                    d.id='onigiri-transition-overlay';
                    d.style.cssText='position:fixed;inset:0;z-index:2147483647;background:'+bg.trim()+';pointer-events:none;';
                    document.body&&document.body.appendChild(d);
                })();
            """)
        except Exception:
            pass
    update_sync_status_indicator()
      
def on_deck_browser_will_show(deck_browser: DeckBrowser):
    """
    Ensures that Onigiri takes control of external hooks at the last possible moment,
    right before the deck browser is displayed for the first time. This guarantees
    that other add-ons have had time to register their hooks.
    """
    patcher.take_control_of_deck_browser_hook()

def on_show_icon_chooser(deck_id):
    """Opens the in-page icon chooser modal inside the deck browser webview."""
    try:
        from . import webview_handlers
        webview_handlers._open_icon_chooser_modal(mw.deckBrowser, str(deck_id))
    except Exception as e:
        from aqt.utils import tooltip
        tooltip(f"Could not open icon chooser: {e}")

def on_deck_options_shown(menu, deck_id):
    """Appends the 'Change Icon' action to the deck options menu."""
    a = menu.addAction("Change Icon")
    a.triggered.connect(lambda _, did=deck_id: on_show_icon_chooser(did))

# Kick off the Qt startup overlay as early as possible — a 0ms single-shot
# fires on the next event-loop iteration, before main_window_did_init.
# This gets the spinner on screen sooner so the user sees it immediately.
QTimer.singleShot(0, _create_qt_overlay)

# Hook Registration
gui_hooks.main_window_did_init.append(setup_global_hooks)
gui_hooks.profile_did_open.append(on_profile_did_open)
gui_hooks.webview_will_set_content.append(inject_menu_files)
gui_hooks.deck_browser_did_render.append(on_deck_browser_did_render)
gui_hooks.webview_did_receive_js_message.append(patcher.on_webview_js_message)
# MODIFICATION: Use the current, correct hook instead of the outdated one.
gui_hooks.webview_did_receive_js_message.append(_on_webview_cmd)
# Update sync status when state changes
gui_hooks.state_did_change.append(on_state_change)
# Update sync status after sync completes
gui_hooks.sync_did_finish.append(lambda: update_sync_status_indicator())
# Update sync status after operations that modify the collection
gui_hooks.operation_did_execute.append(lambda *args: update_sync_status_indicator())
# Update sync status when sync status changes
gui_hooks.sync_will_start.append(lambda: update_sync_status_indicator())
gui_hooks.deck_browser_will_show_options_menu.append(on_deck_options_shown)
# Menu styling disabled per user request
# gui_hooks.theme_did_change.append(patcher.apply_menu_styling)
mw.addonManager.setWebExports(__name__, r"(.*)")