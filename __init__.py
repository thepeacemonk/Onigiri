import os
import json
from aqt import mw, gui_hooks
from aqt.deckbrowser import DeckBrowser
from aqt.reviewer import Reviewer
from aqt.overview import Overview
from aqt.toolbar import Toolbar, BottomBar
from . import patcher
from . import settings
from . import config
from . import menu_buttons
from . import heatmap

addon_path = os.path.dirname(__file__)

addon_package = mw.addonManager.addonFromModule(__name__)
user_files_root = f"/_addons/{addon_package}/user_files"
web_assets_root = f"/_addons/{addon_package}/web"


def inject_menu_files(web_content, context):
    conf = config.get_config()
    should_hide = conf.get("hideNativeHeaderAndBottomBar", False)

    is_deck_browser = isinstance(context, DeckBrowser)
    is_reviewer = isinstance(context, Reviewer)
    is_overview = isinstance(context, Overview)
    is_top_toolbar = isinstance(context, Toolbar)
    is_bottom_toolbar = isinstance(context, BottomBar)

    # --- Screen-Specific Injections ---
    if is_deck_browser or is_reviewer or is_overview:
        web_content.head += patcher.generate_dynamic_css(conf)

    if is_deck_browser:
        # Inject main menu CSS
        css_path = os.path.join(addon_path, "web", "menu.css")
        try:
            with open(css_path, "r", encoding="utf-8") as f:
                web_content.head += f"<style>{f.read()}</style>"
        except FileNotFoundError:
            print(f"Onigiri Error: Could not find menu.css at {css_path}")

        # Inject heatmap CSS
        heatmap_css_path = os.path.join(addon_path, "web", "heatmap.css")
        try:
            with open(heatmap_css_path, "r", encoding="utf-8") as f:
                web_content.head += f"<style>{f.read()}</style>"
        except FileNotFoundError:
            print(f"Onigiri Error: Could not find heatmap.css at {heatmap_css_path}")

        web_content.head += patcher.generate_profile_bar_fix_css()
        web_content.head += patcher.generate_deck_browser_backgrounds(addon_path)
        web_content.head += patcher.generate_icon_css(addon_package, conf)
        web_content.head += patcher.generate_conditional_css(conf)
        web_content.head += patcher.generate_icon_size_css()
        
        # Inject JavaScript
        web_content.head += f'<script src="{web_assets_root}/injector.js"></script>'
        web_content.head += f'<script src="{web_assets_root}/heatmap.js"></script>'

    elif is_reviewer:
        web_content.head += patcher.generate_reviewer_background_css(addon_path)
        
    elif is_overview:
        web_content.head += patcher.generate_overview_background_css(addon_path)
        css_path = os.path.join(addon_path, "web", "overview.css")
        try:
            with open(css_path, "r", encoding="utf-8") as f:
                web_content.head += f"<style>{f.read()}</style>"
        except FileNotFoundError:
            print(f"Onigiri Error: Could not find overview.css at {css_path}")

    # --- Toolbar-Specific Injections ---
    if is_top_toolbar or is_bottom_toolbar:
        if not should_hide:
            web_content.head += patcher.generate_toolbar_background_css(addon_path)

def initial_setup():
    """Performs all initial patching and setup for the add-on."""
    patcher.apply_patches()
    patcher.patch_overview()
    patcher.patch_congrats_page()
    menu_buttons.setup_onigiri_menu(addon_path)

def on_deck_browser_did_render(deck_browser: DeckBrowser):
    """Render the heatmap after the deck browser content is loaded."""
    conf = config.get_config()
    if conf.get("showHeatmapOnMain"):
        heatmap_data, heatmap_config = heatmap.get_heatmap_and_config()
        js = f"OnigiriHeatmap.render('onigiri-heatmap-container', {json.dumps(heatmap_data)}, {json.dumps(heatmap_config)});"
        deck_browser.web.eval(js)

# Hook setup
gui_hooks.main_window_did_init.append(initial_setup)
gui_hooks.webview_will_set_content.append(inject_menu_files)
gui_hooks.deck_browser_will_render_content.append(patcher.prepend_custom_stats)
gui_hooks.deck_browser_did_render.append(on_deck_browser_did_render)

# --- FIX: Use the single, correct hook for all webview messages ---
gui_hooks.webview_did_receive_js_message.append(patcher.on_webview_js_message)


mw.addonManager.setWebExports(__name__, r"(user_files|web)/.*")