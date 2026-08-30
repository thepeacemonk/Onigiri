import os
import sys
import json
import signal
sys.dont_write_bytecode = True

# Anki is a GUI host, so add-on diagnostics must never be able to terminate the
# process when stdout/stderr or another inherited pipe has lost its reader.
# macOS recorded the deck-navigation exits as signal 13 (SIGPIPE), with no
# crash report.  Python normally ignores SIGPIPE, but the embedded application
# can inherit/reset the native disposition before add-ons are imported.
if hasattr(signal, "SIGPIPE"):
    try:
        signal.signal(signal.SIGPIPE, signal.SIG_IGN)
    except (OSError, RuntimeError, ValueError):
        pass

from aqt import mw, gui_hooks
from aqt.deckbrowser import DeckBrowser
from . import onigiri_renderer
from aqt.reviewer import Reviewer
from aqt.overview import Overview
from aqt.toolbar import Toolbar, BottomBar
from aqt.qt import QWidget, QHBoxLayout, QPushButton, Qt, QToolBar, QAction, QTimer
from . import patcher
from . import config
from . import safe_storage
from . import menu_buttons
from . import webview_handlers
from .decks import tree_updater as deck_tree_updater
from . import heatmap
from .api import sidebar as sidebar_api
from .api import bento as bento_api
from . import fsrs_helper_integration
from . import learner_stats_widget
from . import mac_titlebar
from .sync import onigiri_sync

addon_path = os.path.dirname(__file__)
addon_package = mw.addonManager.addonFromModule(__name__)
user_files_root = f"/_addons/{addon_package}/user_files"
web_assets_root = f"/_addons/{addon_package}/web"

# Make addon_path available to other modules
sys.modules[__name__].addon_path = addon_path

def generate_notification_position_css_text(conf):
    """Generates CSS text for notification positioning logic."""
    if conf.get("onigiri_reviewer_notification_mode", "classic") == "mini":
        return ""
        
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
    return css

def generate_notification_position_css(conf):
    """Generates CSS for notification positioning logic."""
    css = generate_notification_position_css_text(conf)
    return f"<style>{css}</style>"

def notification_duration_script(conf):
    """Injects the global notification duration chosen in settings."""
    try:
        duration = int(conf.get("onigiri_notification_duration_ms", 5200))
    except (TypeError, ValueError):
        duration = 5200
    duration = max(1000, min(30000, duration))
    return f"<script>window.onigiriNotificationDuration = {duration};</script>"


def quiet_state_change_css() -> str:
    """Briefly suppress page-level motion while Anki swaps webview screens."""
    return """
    <script>
        document.documentElement.classList.add('onigiri-state-settling');
        window.setTimeout(function() {
            document.documentElement.classList.remove('onigiri-state-settling');
        }, 260);
    </script>
    <style id="onigiri-quiet-state-change">
        html.onigiri-state-settling,
        html.onigiri-state-settling body,
        html.onigiri-state-settling * ,
        html.onigiri-state-settling *::before,
        html.onigiri-state-settling *::after {
            transition-duration: 0.001ms !important;
            transition-delay: 0s !important;
            animation-duration: 0.001ms !important;
            animation-delay: 0s !important;
            animation-iteration-count: 1 !important;
            scroll-behavior: auto !important;
        }
    </style>
    """

def versioned_web_asset(filename: str) -> str:
    """URL for a file in web/, cache-busted by its mtime."""
    try:
        # Keep sub-second precision: several quick CSS/JS edits can otherwise
        # share the same integer-second URL and Chromium will reuse the stale
        # stylesheet, making a freshly applied visual fix appear ineffective.
        version = os.stat(os.path.join(addon_path, "web", filename)).st_mtime_ns
        return f"{web_assets_root}/{filename}?v={version}"
    except OSError:
        return f"{web_assets_root}/{filename}"


def stylesheet_link(filename: str) -> str:
    """
    Link a stylesheet instead of inlining its text.

    Anki rebuilds the page HTML on every screen change, so an inlined
    stylesheet is re-parsed by Chromium each time. menu.css alone is ~80KB;
    inlining it made every deck browser/overview entry progressively slower the
    longer Anki stayed open. Served over a URL it is parsed once and reused.
    """
    return f'<link rel="stylesheet" href="{versioned_web_asset(filename)}">'


def inject_menu_files(web_content, context):
    conf = config.get_config_readonly()
    should_hide = conf.get("hideNativeHeaderAndBottomBar", False)
    is_deck_browser = isinstance(context, DeckBrowser)
    is_reviewer = isinstance(context, Reviewer)
    is_overview = isinstance(context, Overview)
    is_top_toolbar = isinstance(context, Toolbar)
    is_bottom_toolbar = isinstance(context, BottomBar)
    is_reviewer_bottom_bar = type(context).__name__ == "ReviewerBottomBar"
    # Inject global Onigiri CSS only for deck browser and overview.
    # The reviewer card webview owns Anki's question/answer element; Onigiri
    # must not inject CSS, JS, or DOM there so card templates remain untouched.
    if is_deck_browser or is_overview:
        web_content.head += quiet_state_change_css()
        web_content.head += patcher.generate_dynamic_css(conf)
        web_content.head += patcher.generate_box_effect_button_vars_css(conf)

        if conf.get("showWelcomePopup", True):
            web_content.head += f"""
            <script>
            window.addEventListener("DOMContentLoaded", function() {{
                if (document.getElementById("onigiri-welcome-overlay")) return;
                
                const style = document.createElement("style");
                style.id = "onigiri-welcome-style";
                style.innerHTML = `
                    @font-face {{
                        font-family: 'OnigiriPoppins';
                        src: url('/_addons/{addon_package}/system_files/fonts/system_fonts/Poppins/Poppins-Regular.ttf');
                        font-weight: 400;
                    }}
                    @font-face {{
                        font-family: 'OnigiriPoppins';
                        src: url('/_addons/{addon_package}/system_files/fonts/system_fonts/Poppins/Poppins-Medium.ttf');
                        font-weight: 500 900;
                    }}
                    #onigiri-welcome-overlay {{
                        position: fixed; inset: 0; z-index: 2147483647;
                        display: flex; flex-direction: column; align-items: center; justify-content: center;
                        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
                        background: rgba(0, 0, 0, 0.55);
                        color: white;
                        font-family: 'OnigiriPoppins', -apple-system, BlinkMacSystemFont, sans-serif;
                        opacity: 0; transition: opacity 0.4s ease;
                    }}
                    #onigiri-welcome-overlay .btn-continue {{
                        margin-top: 36px; padding: 16px 48px; font-size: 21px; font-weight: 700;
                        font-family: 'OnigiriPoppins', sans-serif; color: #123034; background: white;
                        border: none; border-radius: 40px; cursor: pointer;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.2); transition: transform 0.2s, box-shadow 0.2s;
                    }}
                    #onigiri-welcome-overlay .btn-continue:hover {{
                        transform: scale(1.05); box-shadow: 0 6px 16px rgba(0,0,0,0.3);
                    }}
                `;
                document.head.appendChild(style);

                const overlay = document.createElement("div");
                overlay.id = "onigiri-welcome-overlay";
                overlay.innerHTML = `
                    <img src="/_addons/{addon_package}/onigiri_logo.png" style="width: 290px; height: auto; margin-bottom: 32px; filter: drop-shadow(0 6px 16px rgba(0,0,0,0.3));" />
                    <h1 style="margin: 0 0 20px 0; font-size: 49px; font-weight: 700; text-shadow: 0 2px 6px rgba(0,0,0,0.5);">Welcome!</h1>
                    <p style="margin: 0; font-size: 26px; font-weight: 500; text-shadow: 0 1px 4px rgba(0,0,0,0.5);">Proceed to Settings to start customizing</p>
                    <button class="btn-continue">Continue</button>
                `;
                
                const btn = overlay.querySelector('.btn-continue');
                btn.addEventListener("click", function() {{
                    overlay.style.opacity = "0";
                    setTimeout(() => {{
                        overlay.remove();
                        const s = document.getElementById("onigiri-welcome-style");
                        if (s) s.remove();
                        pycmd("onigiri_welcome_dismissed");
                    }}, 400);
                }});
                
                document.body.appendChild(overlay);
                setTimeout(() => {{ overlay.style.opacity = "1"; }}, 50);
            }});
            </script>
            """
    if is_deck_browser:
        # Some embedded dashboard add-ons create off-DOM WebGL canvases. Qt's
        # shared main webview can retain those contexts across repeated
        # DeckBrowser -> Overview page replacements unless they are explicitly
        # lost, eventually terminating the renderer (and, on macOS, Anki).
        # Install this before external web assets execute so every context is
        # tracked without requiring changes to the other add-on.
        graphics_lifecycle_script = """
        <script id="onigiri-webgl-context-lifecycle">
        (function () {
            if (window.__onigiriWebGLTrackerInstalled) return;
            window.__onigiriWebGLTrackerInstalled = true;

            const originalGetContext = HTMLCanvasElement.prototype.getContext;
            const trackedContexts = new Set();
            HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
                const context = originalGetContext.call(this, kind, ...args);
                if (context && /^(webgl|webgl2|experimental-webgl)$/i.test(String(kind))) {
                    trackedContexts.add(context);
                }
                return context;
            };

            window.__onigiriReleasePageGraphics = function () {
                trackedContexts.forEach(function (context) {
                    try {
                        const extension = context.getExtension('WEBGL_lose_context');
                        if (extension) extension.loseContext();
                    } catch (_) {}
                });
                trackedContexts.clear();

                document.querySelectorAll('canvas').forEach(function (canvas) {
                    try { canvas.width = 1; canvas.height = 1; } catch (_) {}
                });
            };

            window.addEventListener('pagehide', window.__onigiriReleasePageGraphics, { once: true });
            window.addEventListener('beforeunload', window.__onigiriReleasePageGraphics, { once: true });
        })();
        </script>
        """
        # Prepend rather than append: another add-on may already have placed a
        # WebGL script in the head by the time our hook runs.
        web_content.head = graphics_lifecycle_script + web_content.head
        web_content.head += stylesheet_link("menu.css")
        web_content.head += stylesheet_link("heatmap.css")
        web_content.head += stylesheet_link("learner_stats.css")
        patcher.set_main_webview_background_color(patcher._deckbrowser_base_bg_color())
        web_content.head += patcher.generate_profile_bar_fix_css()
        web_content.head += patcher.generate_deck_browser_backgrounds(addon_path)
        web_content.head += patcher.generate_icon_css(addon_package, conf)
        web_content.head += patcher.generate_conditional_css(conf)
        web_content.head += patcher.generate_icon_size_css()
        web_content.head += f'<link rel="stylesheet" href="{web_assets_root}/notifications.css">'
        web_content.head += notification_duration_script(conf)
        # Must precede the scripts below: they read window.ONIGIRI_STRINGS.
        web_content.head += webview_handlers.webview_strings_script()
        web_content.head += f'<script src="{versioned_web_asset("injector.js")}"></script>'
        web_content.head += f'<script src="{versioned_web_asset("engine.js")}"></script>'
        web_content.head += f'<script src="{web_assets_root}/rename_modal.js"></script>'
        web_content.head += f'<script src="{web_assets_root}/icon_modal.js"></script>'
        web_content.head += f'<script src="{web_assets_root}/rename_dialog.js"></script>'
        web_content.head += f'<script src="{web_assets_root}/move_to_dialog.js"></script>'
        web_content.head += f'<script src="{web_assets_root}/add_subdeck_dialog.js"></script>'
        web_content.head += f'<script src="{web_assets_root}/create_deck_dialog.js"></script>'
        web_content.head += f'<script src="{web_assets_root}/delete_deck_dialog.js"></script>'
        web_content.head += f'<script src="{web_assets_root}/heatmap.js"></script>'
        web_content.head += f'<script src="{web_assets_root}/notifications.js"></script>'
        web_content.head += mac_titlebar.inset_css("deck_browser")

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
        patcher.set_main_webview_background_color(patcher._reviewer_base_bg_color(conf))
        web_content.head += notification_duration_script(conf)
        web_content.head += patcher.generate_reviewer_background_css(addon_path)
        top_bar_html, top_bar_css = patcher.generate_reviewer_top_bar_html_and_css(include_overview_class=False)
        reviewer_shadow_css = (
            patcher.generate_scoped_main_font_css(addon_package, "#onigiri-reviewer-header")
            + patcher.generate_box_effect_button_vars_css(
                conf,
                selector="#onigiri-reviewer-header",
                night_selector=":host(.night-mode) #onigiri-reviewer-header",
            )
            + top_bar_css
        )
        reviewer_shadow_css = reviewer_shadow_css.replace(
            ".night_mode #onigiri-reviewer-header",
            ":host(.night-mode) #onigiri-reviewer-header",
        )
        notification_css_text = ""
        try:
            with open(os.path.join(addon_path, "web", "notifications.css"), "r", encoding="utf-8") as f:
                notification_css_text = f.read()
        except FileNotFoundError:
            pass
            
        reviewer_shadow_css += f"\n<style id=\"onigiri-notification-shadow-css\">\n{notification_css_text}\n</style>"
        
        js_injector = f"""
        <script>
            window.onigiriIsReviewerCardWebview = true;
            window.onigiriSilentNotifications = {silent_notifs};
            window.onigiriNotificationCssText = {json.dumps(notification_css_text)};
            window.onigiriNotificationPositionCssText = {json.dumps(generate_notification_position_css_text(conf))};
            window.onigiriNotificationMode = {json.dumps(conf.get("onigiri_reviewer_notification_mode", "classic"))};

            document.addEventListener('DOMContentLoaded', function() {{
                const hostId = 'onigiri-reviewer-ui-host';
                const topBarHtml = {json.dumps(top_bar_html)};
                const topBarCss = {json.dumps(reviewer_shadow_css)};

                const isNightMode = () => {{
                    const root = document.documentElement;
                    const body = document.body;
                    return [root, body].some((el) => el && (
                        el.classList.contains('night-mode') ||
                        el.classList.contains('nightMode') ||
                        el.classList.contains('night_mode')
                    ));
                }};

                const ensureHost = () => {{
                    let host = document.getElementById(hostId);
                    if (!host) {{
                        host = document.createElement('div');
                        host.id = hostId;
                        document.body.appendChild(host);
                    }}
                    host.style.cssText = [
                        'all: initial !important',
                        'position: fixed !important',
                        'inset: 0 !important',
                        'display: block !important',
                        'width: auto !important',
                        'height: auto !important',
                        'margin: 0 !important',
                        'padding: 0 !important',
                        'border: 0 !important',
                        'background: transparent !important',
                        'z-index: 2147483000 !important',
                        'pointer-events: none !important',
                        'contain: layout style paint !important'
                    ].join(';');
                    host.classList.toggle('night-mode', isNightMode());
                    return host;
                }};

                const insertTopBar = () => {{
                    if (!topBarHtml.trim()) {{
                        return null;
                    }}
                    const host = ensureHost();
                    const shadow = host.shadowRoot || host.attachShadow({{ mode: 'open' }});
                    let headerEl = shadow.getElementById('onigiri-reviewer-header');
                    if (!headerEl) {{
                        shadow.innerHTML = `
                            <style id="onigiri-reviewer-shadow-host-style">
                                :host {{
                                    all: initial;
                                    position: fixed !important;
                                    inset: 0 !important;
                                    display: block !important;
                                    z-index: 2147483000 !important;
                                    pointer-events: none !important;
                                    contain: layout style paint !important;
                                }}
                            </style>
                            ${{topBarCss}}
                            ${{topBarHtml}}
                        `;
                        headerEl = shadow.getElementById('onigiri-reviewer-header');
                    }}
                    return headerEl;
                }};

                const headerEl = insertTopBar();
                if (!headerEl) {{
                    return;
                }}

                const updateHeaderOffset = () => {{
                    const host = document.getElementById(hostId);
                    const shadow = host && host.shadowRoot;
                    const header = shadow && shadow.getElementById('onigiri-reviewer-header');
                    if (!header) {{
                        return;
                    }}
                    const styles = window.getComputedStyle(header);
                    const marginTop = parseFloat(styles.marginTop) || 0;
                    const marginBottom = parseFloat(styles.marginBottom) || 0;
                    const offset = header.offsetHeight + marginTop + marginBottom;
                    window.onigiriReviewerHeaderOffsetPx = Math.ceil(offset);
                    window.dispatchEvent(new CustomEvent('onigiri-reviewer-header-offset', {{
                        detail: {{ offset: window.onigiriReviewerHeaderOffsetPx }}
                    }}));
                    applyQaOffset(window.onigiriReviewerHeaderOffsetPx);
                }};
                window.onigiriRefreshReviewerHeaderOffset = updateHeaderOffset;

                const applyQaOffset = (offset) => {{
                    const qa = document.getElementById('qa');
                    if (!qa) {{
                        return;
                    }}
                    if (!qa.dataset.onigiriBaseMarginTop) {{
                        const marginTop = parseFloat(window.getComputedStyle(qa).marginTop) || 0;
                        qa.dataset.onigiriBaseMarginTop = `${{marginTop}}px`;
                    }}
                    qa.style.setProperty(
                        'margin-top',
                        `calc(${{qa.dataset.onigiriBaseMarginTop}} + ${{Math.max(0, offset)}}px)`,
                        'important'
                    );
                }};

                const updateHostTheme = () => {{
                    const host = document.getElementById(hostId);
                    if (host) {{
                        host.classList.toggle('night-mode', isNightMode());
                    }}
                }};

                updateHostTheme();
                updateHeaderOffset();
                window.addEventListener('resize', updateHeaderOffset);

                if ('ResizeObserver' in window) {{
                    const resizeObserver = new ResizeObserver(updateHeaderOffset);
                    resizeObserver.observe(headerEl);
                }}

                const themeObserver = new MutationObserver(() => {{
                    updateHostTheme();
                    updateHeaderOffset();
                }});
                themeObserver.observe(document.documentElement, {{ attributes: true, attributeFilter: ['class'] }});
                if (document.body) {{
                    themeObserver.observe(document.body, {{ attributes: true, attributeFilter: ['class'] }});
                }}

                const qaObserver = new MutationObserver(() => {{
                    applyQaOffset(window.onigiriReviewerHeaderOffsetPx || 0);
                }});
                if (document.body) {{
                    qaObserver.observe(document.body, {{ childList: true, subtree: true }});
                }}
            }});
        </script>
        """
        web_content.head += js_injector
        web_content.head += f'<script src="{web_assets_root}/notifications.js"></script>'
    elif is_overview:
        patcher.set_main_webview_background_color(patcher._overview_base_bg_color(conf))
        web_content.head += f'<link rel="stylesheet" href="{web_assets_root}/notifications.css">'
        web_content.head += notification_duration_script(conf)
        web_content.head += patcher.generate_overview_background_css(addon_path)
        _top_bar_html, top_bar_css = patcher.generate_reviewer_top_bar_html_and_css()
        web_content.head += top_bar_css
        web_content.head += stylesheet_link("overview.css")
        web_content.head += f'<script src="{web_assets_root}/notifications.js"></script>'
        web_content.head += mac_titlebar.inset_css("page")
    if is_reviewer_bottom_bar:
        patcher.apply_reviewer_bottom_bar_height(conf)
        web_content.head += patcher.generate_reviewer_bottom_bar_background_css(addon_path)
        web_content.head += patcher.generate_reviewer_buttons_css(conf)
    elif (is_top_toolbar or is_bottom_toolbar):
        if not should_hide:
            web_content.head += patcher.generate_toolbar_background_css(addon_path)
            if is_top_toolbar:
                # Anki's own toolbar is still on screen; keep it clear of the
                # traffic lights now that the page starts at the window's edge.
                web_content.head += mac_titlebar.inset_css("toolbar")

# Delegate to the webview_handlers module
_on_webview_cmd = webview_handlers.handle_webview_cmd

def maybe_show_welcome_popup():
    """Legacy welcome popup disabled."""
    return

# --- SHOP MENU SETUP ---
def setup_shop_menu():
    """Adds the Shop entry to the Tools menu."""

    


def initialize_enabled_gamification_hooks():
    """Load gamification modules with answer/state hooks only when they are enabled."""
    try:
        conf = config.get_config_readonly()
        restaurant_conf = conf.get("restaurant_level", {})
        if not restaurant_conf:
            restaurant_conf = conf.get("achievements", {}).get("restaurant_level", {})
        if restaurant_conf.get("enabled", False):
            from .gamification import nook_level  # noqa: F401

        onigimon_conf = conf.get("onigimon", {})
        if onigimon_conf.get("enabled", False):
            from .gamification import onigimon  # noqa: F401

        mochi_conf = conf.get("mochi_messages", {})
        if mochi_conf.get("enabled", False):
            from .gamification import mochi_messages  # noqa: F401

        focus_conf = conf.get("achievements", {}).get("focusDango", {})
        if focus_conf.get("enabled", False):
            from .gamification import focus_dango

            focus_dango.setup_focus_dango()
    except Exception as e:
        print(f"Onigiri: Error initializing enabled gamification hooks: {e}")


def verify_coin_integrity():
    """Verify coin integrity on startup to prevent cheating."""
    try:
        import hashlib

        def generate_coin_token(coins: int) -> str:
            data = f"{coins}:onigiri_secret_salt_2024"
            return hashlib.sha256(data.encode()).hexdigest()

        def verify_coin_data(coins: int, token: str) -> bool:
            return token == generate_coin_token(coins)

        # Resolve the profile-specific gamification file (same logic as GamificationData)
        try:
            profile_name = mw.pm.name or "default"
        except Exception:
            profile_name = "default"
        gamification_file = os.path.join(addon_path, 'user_files', f'gamification_{profile_name}.json')
        if os.path.exists(gamification_file):
            # Go through safe_storage rather than a raw r+/truncate: this is the
            # progress file, so it deserves the same atomic swap, .bak and
            # mirror every other writer uses. A half-written file here read as
            # "no progress" on the next launch.
            safe_storage.flush_pending(gamification_file)
            data = safe_storage.read_json(
                gamification_file, default={}, label="Your Onigiri progress"
            ) or {}
            if data:
                restaurant_data = data.setdefault('restaurant_level', {})
                coins = int(restaurant_data.get('taiyaki_coins', 0))
                security_token = restaurant_data.get('_security_token')
                
                if security_token is None:
                    # First time - generate token
                    print("[ONIGIRI SECURITY] Generating initial security token")
                    security_token = generate_coin_token(coins)
                    restaurant_data['_security_token'] = security_token
                    safe_storage.atomic_write_json(gamification_file, data)
                elif not verify_coin_data(coins, security_token):
                    # Tampering detected!
                    print(f"[ONIGIRI SECURITY] ⚠️ TAMPERING DETECTED! Coins: {coins}, Invalid token")
                    restaurant_data['taiyaki_coins'] = 0
                    restaurant_data['_security_token'] = generate_coin_token(0)
                    safe_storage.atomic_write_json(gamification_file, data)
                    
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
    conf = config.get_config_readonly()
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
    # Move UI patching to initial_setup so it happens after mw.col is initialized.
    # We rely on using 'wrap' for compatibility, so it's safe to run this later.
    patcher.apply_patches()
    bento_api.register_api()
    bento_api.ensure_bento_shortcut()
    menu_buttons.setup_onigiri_menu(addon_path)
    
    # Install the toolbar bridge AFTER other addons have loaded their hooks
    sidebar_api.ensure_capture_hook_is_last()
    learner_stats_widget.init()

def migrate_nook_level_names():
    """One-time rename: the level system used to be called "Restaurant Level".
    Saved configs and per-profile game state still carry that title, so the UI
    keeps saying Restaurant Level even though every default is Nook Level now.
    Normalize it in the add-on config, in the saved widget-layout tile name, and
    in the profile's gamification state. Idempotent — only writes when it finds
    a stale value."""
    try:
        conf = config.get_config()
        needs_write = False

        rl_conf = conf.get("restaurant_level")
        if isinstance(rl_conf, dict) and rl_conf.get("name") == "Restaurant Level":
            rl_conf["name"] = "Nook Level"
            needs_write = True

        rl_tile = conf.get("onigiriWidgetLayout", {}).get("grid", {}).get("restaurant_level")
        if isinstance(rl_tile, dict) and rl_tile.get("display_name") == "Restaurant Level":
            rl_tile["display_name"] = "Nook Level"
            needs_write = True

        if needs_write:
            config.write_config(conf)

        profile_name = mw.pm.name if mw.pm else None
        if profile_name:
            gam_path = os.path.join(addon_path, "user_files", f"gamification_{profile_name}.json")
            if os.path.exists(gam_path):
                gam_data = safe_storage.read_json(
                    gam_path, default={}, label="Your Onigiri progress"
                )
                rl_state = gam_data.get("restaurant_level")
                if isinstance(rl_state, dict) and rl_state.get("name") == "Restaurant Level":
                    rl_state["name"] = "Nook Level"
                    safe_storage.atomic_write_json(gam_path, gam_data)
    except Exception as e:
        print(f"[Onigiri] Nook Level name migration skipped: {e}")


def on_profile_did_open():
    """
    Runs when a profile is successfully loaded.
    Logic that requires access to `mw.col` (collection/database/config) goes here.
    """
    # Register Poppins (the add-on's default typeface) into Qt so native
    # dialogs that set font-family: 'Poppins' in QSS resolve it.
    try:
        from .fonts import register_poppins_qt
        register_poppins_qt(addon_path)
    except Exception as e:
        print(f"[Onigiri] Could not register Poppins fonts: {e}")

    migrate_nook_level_names()

    # Now it is safe to patch overview since mw.col is available
    patcher.patch_overview()
    patcher.ensure_synapsepro_overview_bridge_hook()
    QTimer.singleShot(700, patcher.ensure_synapsepro_overview_bridge_hook)
    QTimer.singleShot(1500, patcher.ensure_synapsepro_overview_bridge_hook)
    QTimer.singleShot(3000, patcher.ensure_synapsepro_overview_bridge_hook)
    QTimer.singleShot(6000, patcher.ensure_synapsepro_overview_bridge_hook)
    patcher.apply_synapsepro_sidebar_visibility()

    # Apply Full Hide Mode (hide menu bar on Windows/Linux)
    apply_full_hide_mode()

    # Merge the macOS window title bar into the page (macOS only). Qt only has
    # the native window handle once the window is on screen, so give it a beat.
    mac_titlebar.refresh()
    QTimer.singleShot(300, mac_titlebar.refresh)

    # Verify coin integrity after the initial UI has had a chance to render.
    QTimer.singleShot(1500, verify_coin_integrity)
    
    # Initialize the Shop Menu Item (requires mw.col)
    setup_shop_menu()

    # Register optional game hooks after startup, and only for enabled features.
    QTimer.singleShot(1000, initialize_enabled_gamification_hooks)

    # Check for sync conflicts on startup
    if onigiri_sync.is_enabled():
        QTimer.singleShot(3000, on_sync_did_finish)

    # Show birthday popup if it's the user's birthday (requires mw.col)
    # Delay to ensure the main window is fully rendered before opening a dialog.
    def maybe_show_birthday_popup():
        from . import birthday_dialog

        try:
            birthday_dialog.maybe_show_birthday_popup()
        except Exception as e:
            print(f"[Onigiri] Could not show birthday popup: {e}")

    QTimer.singleShot(6500, maybe_show_birthday_popup)

    # Menu styling disabled per user request
    # patcher.apply_menu_styling()

    # Ensure our sidebar hook runs last (again) just in case other add-ons loaded late
    sidebar_api.ensure_capture_hook_is_last()
    # Force toolbar redraw so our hook (now last) captures all external links
    try:
        mw.toolbar.draw()
    except Exception as e:
        pass

    # Register FSRS4Anki Helper's sidebar entry, if the addon is installed
    fsrs_helper_integration.setup_fsrs_helper_integration()

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

def on_deck_browser_did_render(deck_browser: DeckBrowser):
    conf = config.get_config_readonly()
    grid_layout = conf.get("onigiriWidgetLayout", {}).get("grid", {})
    if "heatmap" in grid_layout:
        # Data is now injected via globals in inject_menu_files for reliability.
        # This call handles refreshes or dynamic layout changes.
        deck_browser.web.eval("if (window.OnigiriHeatmap && typeof window.OnigiriHeatmap.autoRender === 'function') { window.OnigiriHeatmap.autoRender(); }")
    
    # Update sync status indicator
    update_sync_status_indicator()
    _update_card_editing_dim_state()

def update_sync_status_indicator():
    """Updates the sync status indicator in the Onigiri menu."""
    try:
        sync_status = patcher.get_sync_status()
        # Update in deck browser
        if hasattr(mw, 'deckBrowser') and hasattr(mw.deckBrowser, 'web') and mw.deckBrowser.web:
            mw.deckBrowser.web.eval(f"if (typeof SyncStatusManager !== 'undefined') {{ SyncStatusManager.setSyncStatus('{sync_status}'); }}")
    except Exception as e:
        pass

def on_sync_will_start():
    """Called before Anki syncs - pack Onigiri data."""
    update_sync_status_indicator()
    # Game state writes are queued off the reviewer's hot path; the zip must
    # not pick up a stale copy of them.
    try:
        safe_storage.flush_pending()
    except Exception as e:
        print(f"[Onigiri] storage flush failed: {e}")
    if onigiri_sync.is_enabled():
        onigiri_sync.pack_user_files()

def on_sync_did_finish():
    """Called after Anki sync finishes - check for new Onigiri data."""
    update_sync_status_indicator()
    if not onigiri_sync.is_enabled():
        return

    conflict = onigiri_sync.check_conflict()
    if conflict == 'cloud_newer':
        from .sync_ui import show_sync_conflict_dialog

        # Cloud data is newer, ask user what to do
        choice = show_sync_conflict_dialog(mw)
        if choice == 'cloud':
            onigiri_sync.unpack_user_files()
            # Reload Onigiri modules or notify user to restart? For now, just tool tip
            from .onigiri_notifications import notify_info as showInfo
            showInfo("Onigiri data has been updated from AnkiWeb. Some changes may require a restart to take effect.")
        elif choice == 'local':
            # User wants to keep local, so pack it again to set as definitive
            onigiri_sync.pack_user_files()
    elif conflict == 'local_newer':
        # This shouldn't happen immediately after sync unless something is weird
        # but we can pack just in case
        onigiri_sync.pack_user_files()

def on_state_change(new_state, old_state):
    """Called when Anki's state changes - update sync indicator."""
    update_sync_status_indicator()
    # Leaving a screen is a natural, cheap moment to land the game-state
    # writes that were queued while answering cards.
    try:
        safe_storage.flush_pending()
    except Exception as e:
        print(f"[Onigiri] storage flush failed: {e}")
      
def on_deck_browser_will_show(deck_browser: DeckBrowser):
    """
    Ensures that Onigiri takes control of external hooks at the last possible moment,
    right before the deck browser is displayed for the first time. This guarantees
    that other add-ons have had time to register their hooks.
    """
    patcher.take_control_of_deck_browser_hook()

def on_show_icon_chooser(deck_id):
    """Opens the in-page icon chooser for the deck."""
    if getattr(mw, "deckBrowser", None):
        webview_handlers._open_icon_modal(mw.deckBrowser, str(deck_id))

def on_deck_options_shown(menu, deck_id):
    """Appends the 'Change Icon' action to the deck options menu."""
    a = menu.addAction("Change Icon")
    a.triggered.connect(lambda _, did=deck_id: on_show_icon_chooser(did))

def _storage_integrity_check():
    """
    Repairs anything that would otherwise look like "the update wiped my
    setup": an orphaned settings file left by a profile rename, a user_files
    folder emptied by a manual reinstall, or a half-finished Anki update.

    Registered before every other profile hook so the repairs land before
    anything reads the config.
    """
    try:
        profile_name = mw.pm.name if mw.pm else None
        messages = safe_storage.run_startup_check(profile_name)
        # Anything restored on disk predates the cached config, so drop it.
        config.invalidate_config_cache()
        if messages:
            from aqt.utils import showInfo

            showInfo("\n\n".join(messages), title="Onigiri")
    except Exception as e:
        print(f"[Onigiri] storage integrity check failed: {e}")


def _storage_mirror_on_close():
    """
    Copy the critical user_files to the backup outside addons21. Profile close
    is the last moment the data is final, and it is the copy that survives a
    manual reinstall or someone deleting the add-on folder.
    """
    try:
        safe_storage.flush_pending()
    except Exception as e:
        print(f"[Onigiri] storage flush failed: {e}")
    try:
        safe_storage.mirror_all()
    except Exception as e:
        print(f"[Onigiri] storage mirror failed: {e}")


# Card Adding / Editing Dim Effect logic
_active_card_editors = set()

def _is_card_editing_active() -> bool:
    try:
        from aqt import dialogs
        for name in ("AddCards", "EditCurrent"):
            if name in dialogs._dialogs:
                inst = dialogs._dialogs[name][1]
                if inst is not None:
                    return True
    except Exception:
        pass

    global _active_card_editors
    valid = set()
    for win in list(_active_card_editors):
        try:
            if win:
                valid.add(win)
        except Exception:
            pass
    _active_card_editors = valid
    return len(_active_card_editors) > 0

def _apply_card_editing_dim(dimmed: bool):
    js = f"if (window.OnigiriEngine && typeof window.OnigiriEngine.setCardEditingDim === 'function') {{ window.OnigiriEngine.setCardEditingDim({'true' if dimmed else 'false'}); }} else {{ document.body.classList.toggle('is-card-editing', {'true' if dimmed else 'false'}); }}"
    for attr in ('web',):
        if hasattr(mw, attr) and getattr(mw, attr):
            try:
                getattr(mw, attr).eval(js)
            except Exception:
                pass
    if hasattr(mw, 'deckBrowser') and hasattr(mw.deckBrowser, 'web') and mw.deckBrowser.web:
        try:
            mw.deckBrowser.web.eval(js)
        except Exception:
            pass
    if hasattr(mw, 'overview') and hasattr(mw.overview, 'web') and mw.overview.web:
        try:
            mw.overview.web.eval(js)
        except Exception:
            pass
    if hasattr(mw, 'reviewer') and hasattr(mw.reviewer, 'web') and mw.reviewer.web:
        try:
            mw.reviewer.web.eval(js)
        except Exception:
            pass

def _update_card_editing_dim_state():
    is_dimmed = _is_card_editing_active()
    _apply_card_editing_dim(is_dimmed)

def _schedule_dim_update():
    _update_card_editing_dim_state()
    try:
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(50, _update_card_editing_dim_state)
        QTimer.singleShot(200, _update_card_editing_dim_state)
    except Exception:
        try:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(50, _update_card_editing_dim_state)
            QTimer.singleShot(200, _update_card_editing_dim_state)
        except Exception:
            pass

def _register_card_editor_window(win):
    if not win or win in _active_card_editors:
        _schedule_dim_update()
        return
    _active_card_editors.add(win)
    _schedule_dim_update()

    def _on_closed(*args):
        _active_card_editors.discard(win)
        _schedule_dim_update()

    try:
        if hasattr(win, 'destroyed'):
            win.destroyed.connect(_on_closed)
    except Exception:
        pass

    try:
        if hasattr(win, 'finished'):
            win.finished.connect(_on_closed)
    except Exception:
        pass

    for m_name in ('closeEvent', 'reject', 'accept', 'cleanup'):
        if hasattr(win, m_name):
            try:
                orig_m = getattr(win, m_name)
                def make_wrapper(orig):
                    def wrapper(*args, **kwargs):
                        try:
                            return orig(*args, **kwargs)
                        finally:
                            _on_closed()
                    return wrapper
                setattr(win, m_name, make_wrapper(orig_m))
            except Exception:
                pass

def _on_add_cards_did_init(add_cards):
    _register_card_editor_window(add_cards)

def _on_editor_did_init(editor):
    parent_win = None
    if hasattr(editor, 'parentWindow') and editor.parentWindow:
        parent_win = editor.parentWindow
    elif hasattr(editor, 'widget') and editor.widget:
        try:
            parent_win = editor.widget.window()
        except Exception:
            pass
    if parent_win and parent_win != mw:
        _register_card_editor_window(parent_win)

gui_hooks.add_cards_did_init.append(_on_add_cards_did_init)
gui_hooks.editor_did_init.append(_on_editor_did_init)

# Hook Registration
gui_hooks.main_window_did_init.append(setup_global_hooks)
gui_hooks.profile_did_open.append(_storage_integrity_check)
gui_hooks.profile_will_close.append(_storage_mirror_on_close)
gui_hooks.profile_did_open.append(on_profile_did_open)

def _hashi_notes_purge():
    """Runs the Hashi Notes retention/trash sweep once per collection load."""
    try:
        from . import hashi_notes
        hashi_notes.purge_expired()
    except Exception as e:
        print(f"Hashi Notes: purge hook error: {e}")
gui_hooks.profile_did_open.append(_hashi_notes_purge)
gui_hooks.webview_will_set_content.append(inject_menu_files)
gui_hooks.deck_browser_did_render.append(on_deck_browser_did_render)
def _invalidate_heatmap_cache_on_answer(*args):
    from . import heatmap
    heatmap.invalidate_heatmap_cache()
gui_hooks.reviewer_did_answer_card.append(_invalidate_heatmap_cache_on_answer)
gui_hooks.webview_did_receive_js_message.append(patcher.on_webview_js_message)
# MODIFICATION: Use the current, correct hook instead of the outdated one.
gui_hooks.webview_did_receive_js_message.append(_on_webview_cmd)
# Update sync status when state changes
gui_hooks.state_did_change.append(on_state_change)
# Update sync status after sync completes
gui_hooks.sync_did_finish.append(on_sync_did_finish)
# Update sync status after operations that modify the collection
gui_hooks.operation_did_execute.append(lambda *args: update_sync_status_indicator())
# Update sync status when sync status changes
gui_hooks.sync_will_start.append(on_sync_will_start)
gui_hooks.deck_browser_will_show_options_menu.append(on_deck_options_shown)
# Menu styling disabled per user request
# gui_hooks.theme_did_change.append(patcher.apply_menu_styling)
mw.addonManager.setWebExports(__name__, r"(.*)")
