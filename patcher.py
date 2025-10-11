import os
import re
import json
import base64
from aqt.qt import QFileDialog
from aqt import mw, gui_hooks, dialogs
from aqt import mw, gui_hooks, dialogs
from aqt.deckbrowser import DeckBrowser
from aqt.overview import Overview
from aqt.qt import QUrl, QEvent, QObject, QDialog, QVBoxLayout, QDesktopServices
from aqt.utils import tr
from aqt.toolbar import TopWebView, BottomWebView
from aqt.main import MainWebView
from aqt.webview import AnkiWebView
from . import config
from .config import DEFAULTS
from .constants import COLOR_LABELS
from aqt.utils import showInfo
from . import menu_buttons, settings, heatmap, fonts
from . import fonts
from .fonts import get_all_fonts

# --- Toolbar Patching ---
_managed_hooks = []
_toolbar_patched = False
_original_MainWebView_eventFilter = None


def _hex_to_rgba(hex_str: str, alpha: float) -> str:
	"""Converts a hex color string to an rgba string."""
	hex_str = hex_str.lstrip('#')
	if len(hex_str) != 6:
		return f"rgba(0,0,0,{alpha})" # Return a default for invalid hex
	try:
		r, g, b = tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
		return f"rgba({r}, {g}, {b}, {alpha})"
	except ValueError:
		return f"rgba(0,0,0,{alpha})"


def take_control_of_deck_browser_hook():
    """
    Finds external hooks, removes them from the main hook,
    and stores them for Onigiri to manage, preventing duplication.
    """
    global _managed_hooks
    if _managed_hooks: # Ensure this runs only once
        return

    onigiri_module_name = config.__name__.split('.')[0]
    # Make a copy of the list to modify it safely
    original_hooks = list(gui_hooks.deck_browser_will_render_content._hooks)

    for hook in original_hooks:
        hook_id = _get_hook_name(hook)
        if onigiri_module_name not in hook_id:
            _managed_hooks.append(hook)
            # Remove the hook so it doesn't run on its own
            gui_hooks.deck_browser_will_render_content.remove(hook)

def _render_background_css(selector, mode, light_color, dark_color, light_image_path, dark_image_path, blur_val, addon_path, style_id, opacity_val=100, background_position="center"):
	"""Internal helper to generate a complete <style> block for a given background configuration."""
	blur_px = blur_val * 0.2
	addon_name = os.path.basename(addon_path)

	def get_img_url(image_path):
		if not image_path:
			return None
		if image_path.startswith("user_files/"):
			return f"/_addons/{addon_name}/{image_path}"
		else:
			return f"/_addons/{addon_name}/user_files/{image_path}"

	if mode == "accent":
		return f"""<style id="{style_id}">{selector} {{ background: var(--accent-color) !important; }}</style>"""

	if mode == "color":
		return f"""<style id="{style_id}">
			{selector} {{ background-color: {light_color} !important; }}
			.night-mode {selector} {{ background-color: {dark_color} !important; }}
		</style>"""

	# --- START OF REVISED LOGIC ---

	elif mode == "image":
		light_img_url = get_img_url(light_image_path)
		dark_img_url = get_img_url(dark_image_path) if dark_image_path else light_img_url
		if not light_img_url: return ""

		opacity_float = opacity_val / 100.0
		outset = 0
		base_before_css = f"""
			content: ''; position: {'fixed' if 'body' in selector else 'absolute'};
			width: 100%; height: 100%; top: 0; left: 0;
			background-size: cover; background-position: {background_position};
			background-repeat: no-repeat; filter: blur({blur_px}px);
			opacity: {opacity_float}; z-index: -1;
		"""
		image_css = f"{selector}::before {{ {base_before_css} background-image: url('{light_img_url}'); }}"
		if dark_img_url and dark_img_url != light_img_url:
			image_css += f"\n.night-mode {selector}::before {{ background-image: url('{dark_img_url}'); }}"

		container_css = ""
		if "body" in selector:
			container_css += f"html {{ background: transparent !important; overflow: hidden !important; }} {selector} {{ background: transparent !important; }}"
		else:
			container_css += f"{selector} {{ background: transparent; }}"

		if "container" in selector or ".sidebar-left" in selector or "#outer" in selector:
			container_css += f"{selector} {{ position: relative; z-index: 1; overflow: hidden; }}"
		elif "body" in selector:
			container_css += f"{selector} {{ position: relative; z-index: 1; }}"

		return f"<style id='{style_id}'>{container_css}\n{image_css}</style>"

    # Located in patcher.py

	elif mode == "image_color":
		light_img_url = get_img_url(light_image_path)
		dark_img_url = get_img_url(dark_image_path) if dark_image_path else light_img_url

		# If no image, fallback to solid color
		if not light_img_url:
				return f"""<style id="{style_id}">
					{selector} {{ background-color: {light_color} !important; }}
					.night-mode {selector} {{ background-color: {dark_color} !important; }}
				</style>"""

		# --- START OF FIX ---
		image_opacity = opacity_val / 100.0
		blur_px = blur_val * 0.2

		# This pseudo-element holds the background image with its effects.
		base_before_css = f"""
			content: ''; position: absolute;
			top: 0; left: 0; right: 0; bottom: 0;
			background-size: cover; background-position: {background_position};
			background-repeat: no-repeat;
			filter: blur({blur_px}px);
			opacity: {image_opacity};
			z-index: -1;
		"""

		image_css = f"{selector}::before {{ {base_before_css} background-image: url('{light_img_url}'); }}"
		if dark_img_url and dark_img_url != light_img_url:
			image_css += f"\n.night-mode {selector}::before {{ background-image: url('{dark_img_url}'); }}"

		# The container gets the SOLID color and acts as a positioning context.
		container_css = f"""
			{selector} {{
				position: relative; z-index: 1; overflow: hidden;
				background-color: {light_color} !important;
			}}
			.night-mode {selector} {{
				background-color: {dark_color} !important;
			}}
		"""

		return f"<style id='{style_id}'>{container_css}\n{image_css}</style>"
	# --- END OF REVISED LOGIC ---

	return ""

# --- Profile Page Generation ---

_profile_dialog = None

def generate_profile_page_background_css():
    """Generates the CSS for the profile page's main container background."""
    # Reads the mode ("color" or "gradient") you set in the settings
    mode = mw.col.conf.get("onigiri_profile_page_bg_mode", "color")

    if mode == "gradient":
        # Uses the correct "gradient" color keys
        light1 = mw.col.conf.get("onigiri_profile_page_bg_light_color1", "#FFFFFF")
        light2 = mw.col.conf.get("onigiri_profile_page_bg_light_color2", "#E0E0E0")
        dark1 = mw.col.conf.get("onigiri_profile_page_bg_dark_color1", "#424242")
        dark2 = mw.col.conf.get("onigiri_profile_page_bg_dark_color2", "#212121")
        return f"""
        <style id="onigiri-profile-page-bg">
            .onigiri-profile-page {{
                background-image: linear-gradient(to bottom, {light1}, {light2});
                background-attachment: fixed;
            }}
            .night-mode .onigiri-profile-page {{
                background-image: linear-gradient(to bottom, {dark1}, {dark2});
            }}
        </style>
        """
    else: # Solid color
        # Uses the correct "solid color" keys
        light_color = mw.col.conf.get("onigiri_profile_page_bg_light_color1", "#F5F5F5")
        dark_color = mw.col.conf.get("onigiri_profile_page_bg_dark_color1", "#2c2c2c")
        return f"""
        <style id="onigiri-profile-page-bg">
            .onigiri-profile-page {{ background-color: {light_color} !important; }}
            .night-mode .onigiri-profile-page {{ background-color: {dark_color} !important; }}
        </style>
        """

def _get_profile_pill_html(conf, addon_package):
    user_name = conf.get("userName", "USER")
    
    # Profile Picture
    profile_pic_filename = mw.col.conf.get("modern_menu_profile_picture", "")
    if profile_pic_filename:
        pic_url = f"/_addons/{addon_package}/user_files/profile/{profile_pic_filename}"
        pic_html = f'<img src="{pic_url}" class="profile-pic-pill">'
    else:
        initial = user_name[0].upper() if user_name else "U"
        pic_html = f'<div class="profile-pic-placeholder-pill"><span>{initial}</span></div>'
    
    return f"""
    <div class="profile-pill">
        {pic_html}
        <span class="profile-name-pill">{user_name}</span>
    </div>
    """

def _get_theme_colors_html(mode, conf):
    colors = conf.get("colors", {}).get(mode, {})
    items_html = ""
    
    # Use COLOR_LABELS for ordering and friendly names
    for key, info in COLOR_LABELS.items():
        if key in colors:
            hex_val = colors[key]
            items_html += f"""
            <div class="color-item">
                <div class="color-swatch" style="background-color: {hex_val};"></div>
                <div class="color-info">
                    <span class="color-name">{info['label']}</span>
                    <span class="color-code">{hex_val.upper()}</span>
                </div>
            </div>
            """
            
    return f"""
    <h2 class="section-title">Theme colors ({mode})</h2>
    <div class="color-list">{items_html}</div>
    """

def _get_backgrounds_html(addon_package):
    main_bg_style = ""
    main_text = ""
    sidebar_bg_style = ""
    sidebar_text = ""

    # --- 1. Process Main Background ---
    main_mode = mw.col.conf.get("modern_menu_background_mode", "color")

    if main_mode == "image" or main_mode == "image_color":
        if mw.col.conf.get("modern_menu_background_image_mode", "single") == "separate":
            main_img_file = mw.col.conf.get("modern_menu_background_image_light", "")
        else:
            main_img_file = mw.col.conf.get("modern_menu_background_image", "")
            
        if main_img_file:
            main_img_path = f"/_addons/{addon_package}/user_files/main_bg/{main_img_file}"
            main_bg_style = f"background-image: url('{main_img_path}');"
        else:
            main_bg_style = "" # Use default card color
            main_text = "Image mode selected, but no file chosen."
    
    if main_mode == "color" or main_mode == "image_color":
        # Use the correct color for the current theme in the preview swatch
        if mw.pm.night_mode():
            color = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
        else:
            color = mw.col.conf.get("modern_menu_bg_color_light", "#FFFFFF")
        # In combo mode, color is applied first, then image style.
        main_bg_style = f"background-color: {color}; {main_bg_style}"

    elif main_mode == "accent":
        main_bg_style = "background-color: var(--accent-color);"

    # --- 2. Process Sidebar Background ---
    sidebar_mode = mw.col.conf.get("modern_menu_sidebar_bg_mode", "main")

    if sidebar_mode == "main":
        sidebar_bg_style = "" # Use default card color
    else: # custom
        sidebar_type = mw.col.conf.get("modern_menu_sidebar_bg_type", "color")
        if sidebar_type == "image" or sidebar_type == "image_color":
            sidebar_img_file = mw.col.conf.get("modern_menu_sidebar_bg_image", "")
            if sidebar_img_file:
                sidebar_img_path = f"/_addons/{addon_package}/user_files/sidebar_bg/{sidebar_img_file}"
                sidebar_bg_style = f"background-image: url('{sidebar_img_path}');"
            else:
                sidebar_bg_style = ""
                sidebar_text = "Image mode selected, but no file chosen."
        
        if sidebar_type == "color" or sidebar_type == "image_color":
            if mw.pm.night_mode():
                color = mw.col.conf.get("modern_menu_sidebar_bg_color_dark", "#3C3C3C")
            else:
                color = mw.col.conf.get("modern_menu_sidebar_bg_color_light", "#EEEEEE")
            sidebar_bg_style = f"background-color: {color}; {sidebar_bg_style}"

        elif sidebar_type == "accent":
            sidebar_bg_style = "background-color: var(--accent-color);"

    # --- 3. Construct Final HTML ---
    # The title is changed to "Backgrounds" to be more accurate
    return f"""
    <h2 class="section-title">Backgrounds</h2>
    <div class="background-previews">
        <div class="preview-card">
            <div class="preview-image" style="{main_bg_style}">
                <span>{main_text}</span>
            </div>
            <div class="preview-info">Main Background</div>
        </div>
        <div class="preview-card">
            <div class="preview-image" style="{sidebar_bg_style}">
                 <span>{sidebar_text}</span>
            </div>
            <div class="preview-info">Sidebar Background</div>
        </div>
    </div>
    """

def _get_heatmap_data_and_config_for_profile():
    """Helper that calls the main heatmap data provider."""
    return heatmap.get_heatmap_and_config()

def _get_stats_html():
    conf = config.get_config()
    show_heatmap = conf.get("showHeatmapOnProfile", True)

    # 1. Calculate today's stats from the database
    cards_today, time_today_seconds = mw.col.db.first("select count(), sum(time)/1000 from revlog where id > ?", (mw.col.sched.dayCutoff - 86400) * 1000) or (0, 0)
    time_today_seconds = time_today_seconds if time_today_seconds is not None else 0
    cards_today = cards_today if cards_today is not None else 0
    time_today_minutes = time_today_seconds / 60
    seconds_per_card = time_today_seconds / cards_today if cards_today > 0 else 0
    
    # --- START: New Retention Calculation ---
    total_reviews, correct_reviews = mw.col.db.first(
        "select count(*), sum(case when ease > 1 then 1 else 0 end) from revlog where type = 1 and id > ?",
        (mw.col.sched.dayCutoff - 86400) * 1000
    ) or (0, 0)
    total_reviews = total_reviews or 0
    correct_reviews = correct_reviews or 0
    retention_percentage = (correct_reviews / total_reviews * 100) if total_reviews > 0 else 0

    if retention_percentage >= 90: stars = 5
    elif retention_percentage >= 70: stars = 4
    elif retention_percentage >= 50: stars = 3
    elif retention_percentage >= 30: stars = 2
    elif total_reviews > 0: stars = 1
    else: stars = 0
    
    star_html = "".join([f"<i class='star{' empty' if i >= stars else ''}'></i>" for i in range(5)])

    retention_stat_html = f"""
    <div class="stat-card retention-card">
        <h3>Retention</h3>
        <p>{retention_percentage:.0f}%</p>
        <div class="star-rating">{star_html}</div>
    </div>
    """
    # --- END: New Retention Calculation ---

    # 2. Generate the HTML for the stats grid
    stats_grid_parts = [] 
    if not conf.get("hideStudiedStat", False):
        stats_grid_parts.append(f"""<div class="stat-card studied-card"><h3>Studied</h3><p>{cards_today} cards</p></div>""")
    if not conf.get("hideTimeStat", False):
        stats_grid_parts.append(f"""<div class="stat-card time-card"><h3>Time</h3><p>{time_today_minutes:.1f} min</p></div>""")
    if not conf.get("hidePaceStat", False):
        stats_grid_parts.append(f"""<div class="stat-card pace-card"><h3>Pace</h3><p>{seconds_per_card:.1f} s/card</p></div>""")
    # Add the retention card to the grid
    if not conf.get("hideRetentionStat", False):
        stats_grid_parts.append(retention_stat_html)

    stats_grid_html = f"""<div class="stats-grid">{''.join(stats_grid_parts)}</div>""" if stats_grid_parts else ""

    heatmap_html = ""
    if show_heatmap:
        heatmap_html = "<div id='onigiri-profile-heatmap-container'></div>"

    # 3. Construct the final HTML for the stats section
    return f"""
    {stats_grid_html}
    <div id="onigiri-profile-heatmap-wrapper" style="margin-top: 20px;">
        {heatmap_html}
    </div>
    """

def _get_profile_header_html(conf, addon_package):
    # This function now ONLY creates the banner background
    bg_style = ""
    bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "accent")
    if bg_mode == "image":
        bg_image_file = mw.col.conf.get("modern_menu_profile_bg_image", "")
        if bg_image_file:
            bg_url = f"/_addons/{addon_package}/user_files/profile_bg/{bg_image_file}"
            bg_style = f"background-image: url('{bg_url}');"
    elif bg_mode == "custom":
        light_color = mw.col.conf.get("modern_menu_profile_bg_color_light", "#EEEEEE")
        dark_color = mw.col.conf.get("modern_menu_profile_bg_color_dark", "#3C3C3C")
        bg_style = f"background-color: {light_color};"
    else: # accent
        bg_style = "background-color: var(--accent-color);"

    return f'<div class="profile-header-banner" style="{bg_style}"></div>'

# In patcher.py

def _generate_profile_html_body():
    conf = config.get_config()
    addon_package = mw.addonManager.addonFromModule(__name__)

    # --- Page Components ---
    banner_html = _get_profile_header_html(conf, addon_package)
    profile_pill_html = _get_profile_pill_html(conf, addon_package)

    theme_page_content = ""
    stats_page_content = ""

    # --- THIS IS THE FIX ---
    # These variable definitions were missing and have been restored.
    show_light = mw.col.conf.get("onigiri_profile_show_theme_light", True)
    show_dark = mw.col.conf.get("onigiri_profile_show_theme_dark", True)
    show_bgs = mw.col.conf.get("onigiri_profile_show_backgrounds", True)
    # ----------------------

    if show_light: theme_page_content += _get_theme_colors_html("light", conf)
    if show_dark: theme_page_content += _get_theme_colors_html("dark", conf)
    if show_bgs: theme_page_content += _get_backgrounds_html(addon_package)
    if not theme_page_content:
        theme_page_content = '<p class="empty-section">Theme sections are hidden in settings.</p>'

    if mw.col.conf.get("onigiri_profile_show_stats", True):
        stats_page_content = _get_stats_html()
    else:
        stats_page_content = '<p class="empty-section">Stats section is hidden in settings.</p>'

    share_svg_icon = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92s2.92-1.31 2.92-2.92-1.31-2.92-2.92-2.92z"/></svg>"""
    export_button_html = f"""
    <button id="export-btn" class="page-export-button" title="Share Profile">
        {share_svg_icon}
    </button>
    """
    
    return f"""
    <div class="onigiri-profile-page">
        {banner_html}

        <div class="profile-controls">
            <div class="controls-spacer"></div>
            {profile_pill_html}
            
            <button id="nav-theme" class="nav-button">Themes</button>
            <button id="nav-stats" class="nav-button">Stats</button>
            
            {export_button_html}
        </div>

        <div class="profile-content-wrapper">
            <main>
                <div id="page-theme">{theme_page_content}</div>
                <div id="page-stats">{stats_page_content}</div>
            </main>
        </div>
    </div>
    """

class ProfileDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Your Onigiri Profile")
        self.setMinimumSize(500, 600)
        self.setMaximumSize(700, 900)
        self.web = AnkiWebView(self)
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.web)
        self.setLayout(layout)

        addon_package = mw.addonManager.addonFromModule(__name__)
        body_html = _generate_profile_html_body()
        
        # Inject the dynamic theme CSS and the custom profile page BG CSS
        head_html = generate_dynamic_css(config.get_config())
        head_html += generate_profile_page_background_css()

        css_files = [
            f"/_addons/{addon_package}/web/profile.css",
            f"/_addons/{addon_package}/web/heatmap.css" # Add heatmap CSS
        ]
        
        js_files = [
            f"/_addons/{addon_package}/web/lib/html2canvas.min.js", # ADD THIS LINE BACK
            f"/_addons/{addon_package}/web/profile_page.js",
            f"/_addons/{addon_package}/web/heatmap.js"
        ]

        self.web.stdHtml(body_html, css=css_files, js=js_files, head=head_html, context=self)
        
        # After webview is set up, run javascript to render heatmap
        heatmap_data, heatmap_config = _get_heatmap_data_and_config_for_profile()
        self.web.eval(f"""
            if (document.getElementById('onigiri-profile-heatmap-container')) {{
                OnigiriHeatmap.render('onigiri-profile-heatmap-container', {json.dumps(heatmap_data)}, {json.dumps(heatmap_config)});
            }}
        """)


def open_profile():
    """Wrapper function to open the profile page dialog."""
    global _profile_dialog
    if _profile_dialog is not None:
        _profile_dialog.close()
    _profile_dialog = ProfileDialog(mw)
    _profile_dialog.show()

show_profile_page = open_profile

def on_webview_js_message(handled, message, context):
    """
    Unified handler for messages from all webviews.
    """
    if message.startswith("saveImage:") and _profile_dialog and _profile_dialog.isVisible():
        try:
            header, data = message.split(",", 1)
            image_data = base64.b64decode(data)

            filename, _ = QFileDialog.getSaveFileName(
                _profile_dialog, "Save Profile Image", "onigiri-profile.png", "PNG Images (*.png)"
            )

            if filename:
                with open(filename, "wb") as f:
                    f.write(image_data)
        except Exception as e:
            print(f"Onigiri: An error occurred during image save: {e}")

        return (True, None)

    if isinstance(context, DeckBrowser):
        cmd = message
        if cmd == "showUserProfile":
            open_profile()
            return (True, None)
        if cmd == "add":
            mw.onAddCard()
            return (True, None)
        if cmd == "browse":
            mw.onBrowse()
            return (True, None)
        if cmd == "stats":
            mw.onStats()
            return (True, None)
        if cmd == "sync":
            mw.onSync()
            return (True, None)
        if cmd == "openOnigiriSettings":
            settings.open_settings(0)
            return (True, None)
        if cmd == "shared":
            QDesktopServices.openUrl(QUrl("https://ankiweb.net/shared/decks"))
            return (True, None)
        if cmd == "create":
            mw.deckBrowser._on_create()
            return (True, None)
        if cmd == "import":
            mw.onImport()
            return (True, None)
        if cmd.startswith("saveSidebarWidth:"):
            try:
                width = int(cmd.split(":")[1])
                mw.col.conf["modern_menu_sidebar_width"] = width
                mw.col.setMod()
            except:
                pass
            return (True, None)
        if cmd.startswith("saveSidebarState:"):
            try:
                is_collapsed = cmd.split(":")[1] == 'true'
                mw.col.conf["onigiri_sidebar_collapsed"] = is_collapsed
                mw.col.setMod()
            except Exception as e:
                print(f"Onigiri: Error saving sidebar state: {e}")
            return (True, None)

    elif isinstance(context, Overview):
        cmd = message
        if cmd == "deckBrowser":
            mw.moveToState("deckBrowser")
            return (True, None)
        if cmd in ["study", "opts", "refresh", "empty"]:
            return handled
        if cmd == "showUserProfile":
            open_profile()
            return (True, None)
        if cmd == "decks":
            mw.moveToState("deckBrowser")
            return (True, None)
        if cmd == "add":
            mw.onAddCard()
            return (True, None)
        if cmd == "browse":
            mw.onBrowse()
            return (True, None)
        if cmd == "stats":
            mw.onStats()
            return (True, None)
        if cmd == "sync":
            mw.onSync()
            return (True, None)

    return handled

def patch_overview():
	"""Replaces the HTML generation for the overview screen."""
	
	conf = config.get_config()
	show_toolbar_replacements = conf.get("hideNativeHeaderAndBottomBar", False)
	pro_hide = conf.get("proHide", False)
    
	overview_style = mw.col.conf.get("onigiri_overview_style", "pro")
	style_class = "mini-overview" if overview_style == "mini" else ""

	mini_css = ""
	if overview_style == "mini":
		mini_css = """
        <style id="onigiri-mini-overview-style">
            /* --- THE DEFINITIVE FIX: Target the body tag directly --- */
            body.mini-overview {
                align-items: flex-start; /* Override the vertical centering */
                padding-top: 5vh;      /* Add space from the top */
            }

            /* --- The rest of the styling for the mini-overview components --- */
            .mini-overview .overview-title { font-size: 20px; font-weight: 600; margin-bottom: 10px; text-align: center; }
            .mini-overview .stats-container { width: 280px; margin: 0 auto 20px auto; background: var(--canvas-inset); padding: 6px; border: 1px solid var(--border); border-radius: 12px}
            .mini-overview .stats-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; font-size: 14px; }
            .mini-overview .stats-row span:first-child { color: var(--fg-subtle); }
            .mini-overview .new-count-bubble, .mini-overview .learn-count-bubble, .mini-overview .review-count-bubble { font-size: 12px; font-weight: bold; padding: 3px 10px; border-radius: 12px; min-width: 30px; text-align: center; }
            .mini-overview #study { width: 280px; margin: 0 auto; padding: 10px; font-size: 16px; border-radius: 9999px; }
            .mini-overview .overview-bottom-actions { width: 280px; margin: 15px auto 0 auto; display: flex; justify-content: center; gap: 10px; }
            .mini-overview .overview-bottom-actions .overview-button { background: rgba(255, 255, 255, 0.08); color: var(--fg) !important; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; text-decoration: none; font-size: 13px; padding: 5px 12px; box-shadow: none; transition: background-color 0.2s ease, border-color 0.2s ease; }
            .mini-overview .overview-bottom-actions .overview-button:hover { background: rgba(255, 255, 255, 0.15); border-color: rgba(255, 255, 255, 0.2); }
        </style>
        """
    
	def new_table(self) -> str:
		counts = list(self.mw.col.sched.counts())
		
		count_data = [
			{"label": tr.actions_new(), "count": counts[0], "class": "new-count-bubble"},
			{"label": tr.scheduling_learning(), "count": counts[1], "class": "learn-count-bubble"},
			{"label": tr.studying_to_review(), "count": counts[2], "class": "review-count-bubble"},
		]

		rows_html = ""
		for item in count_data:
			rows_html += (
				'<div class="stats-row">'
				f"<span>{item['label']}</span>"
				f"<span class=\"{item['class']}\">{item['count']}</span>"
				'</div>'
			)
		
		study_now_text = mw.col.conf.get("modern_menu_studyNowText") or tr.studying_study_now()

		bottom_actions_html = ""
		if show_toolbar_replacements:
			bottom_actions_html = (
				'<div class="overview-bottom-actions">'
				'<a href="#" key=O onclick="pycmd(\'opts\'); return false;" class="overview-button">Options</a>'
				'<a href="#" key=R onclick="pycmd(\'refresh\'); return false;" class="overview-button">Rebuild</a>'
				'<a href="#" key=E onclick="pycmd(\'empty\'); return false;" class="overview-button">Empty</a>'
				'</div>'
			)

		return (
			'<div class="overview-container">'
				'<div class="stats-container">'
					f'{rows_html}'
				'</div>'
				f'<button id="study" class="add-button-dashed" onclick="pycmd(\'study\'); return false;" autofocus>'
					f'{study_now_text}'
				'</button>'
				f'{bottom_actions_html}'
			'</div>'
		)

	Overview._table = new_table
	
	header_html = ""
	if show_toolbar_replacements and not pro_hide:
		header_html = """
    <div class="overview-header">
        <div class="onigiri-reviewer-header-buttons">
            <a href="#" onclick="pycmd('decks'); return false;" class="onigiri-reviewer-button">Decks</a>
            <a href="#" onclick="pycmd('add'); return false;" class="onigiri-reviewer-button">Add</a>
            <a href="#" onclick="pycmd('browse'); return false;" class="onigiri-reviewer-button">Browse</a>
            <a href="#" onclick="pycmd('stats'); return false;" class="onigiri-reviewer-button">Stats</a>
            <a href="#" onclick="pycmd('sync'); return false;" class="onigiri-reviewer-button">Sync</a>
        </div>
    </div>
"""

	Overview._body = f"""
{mini_css}
<div class="overview-center-container {style_class}">
    {header_html}
	<h3 class="overview-title">%(deck)s</h3>
	<div style="display:none">%(shareLink)s</div>
	<div style="display:none">%(desc)s</div>
	%(table)s
</div>
<script>
    document.addEventListener("DOMContentLoaded", function() {{
        // --- START: Onigiri Deck Title Fix ---
        const titleElement = document.querySelector('.overview-title');
        if (titleElement) {{
            // Anki provides the full deck path, so we split it by "::" and take the last part.
            const fullTitle = titleElement.textContent;
            const shortTitle = fullTitle.split('::').pop();
            titleElement.textContent = shortTitle;
        }}
        // --- END: Onigiri Deck Title Fix ---
        
        if (!document.getElementById('onigiri-background-div')) {{
            const bgDiv = document.createElement('div');
            bgDiv.id = 'onigiri-background-div';
            document.body.prepend(bgDiv);
        }} 
        // --- END OF FIX ---

        // --- NEW SCRIPT TO ADD CLASS TO BODY ---
        // This allows our CSS to target the body tag and override the alignment
        if (document.querySelector('.overview-center-container.mini-overview')) {{ 
            document.body.classList.add('mini-overview');
        }}
    }});
</script>
"""
    

# --- Congrats Page Patcher ---

def patch_congrats_page():
    """Replaces the default congratulations screen with a custom, stylable one."""
    
    def new_show_finished_screen(self: Overview):
        addon_path = os.path.dirname(__file__)
        conf = config.get_config()
        addon_package = mw.addonManager.addonFromModule(__name__)

        # Check for hide mode to determine if the header should be shown
        show_toolbar_replacements = conf.get("hideNativeHeaderAndBottomBar", False)
        pro_hide = conf.get("proHide", False)

        header_html = ""
        if show_toolbar_replacements and not pro_hide:
            header_html = """
            <div class="overview-header">
                <div class="onigiri-reviewer-header-buttons">
                    <a href="#" onclick="pycmd('decks'); return false;" class="onigiri-reviewer-button">Decks</a>
                    <a href="#" onclick="pycmd('add'); return false;" class="onigiri-reviewer-button">Add</a>
                    <a href="#" onclick="pycmd('browse'); return false;" class="onigiri-reviewer-button">Browse</a>
                    <a href="#" onclick="pycmd('stats'); return false;" class="onigiri-reviewer-button">Stats</a>
                    <a href="#" onclick="pycmd('sync'); return false;" class="onigiri-reviewer-button">Sync</a>
                </div>
            </div>
            """

        # 1. Build Profile Bar HTML (if enabled)
        profile_bar_html = ""
        if conf.get("showCongratsProfileBar", True):
            user_name = conf.get("userName", "USER")
            profile_pic_filename = mw.col.conf.get("modern_menu_profile_picture", "")
            if profile_pic_filename:
                profile_pic_url = f"/_addons/{addon_package}/user_files/profile/{profile_pic_filename}"
                profile_pic_html = f'<img src="{profile_pic_url}" class="profile-pic">'
            else:
                initial = user_name[0].upper() if user_name else "U"
                profile_pic_html = f'<div class="profile-pic-placeholder"><span>{initial}</span></div>'

            profile_bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "accent")
            profile_bg_image = mw.col.conf.get("modern_menu_profile_bg_image", "")
            bg_style_str = ""
            bg_class_str = ""

            if profile_bg_mode == "image" and profile_bg_image:
                bg_image_url = f"/_addons/{addon_package}/user_files/profile_bg/{profile_bg_image}"
                bg_style_str = f"background-image: url('{bg_image_url}'); background-size: cover; background-position: center;"
                bg_class_str = "with-image-bg"
            elif profile_bg_mode == "custom":
                bg_style_str = "background-color: var(--profile-bg-custom-color);"
            else: # accent
                bg_style_str = "background-color: var(--accent-color);"
            
            profile_bar_html = f"""
            <div class="profile-bar {bg_class_str}" style="{bg_style_str}" onclick="pycmd('showUserProfile')">
                {profile_pic_html}
                <span class="profile-name">{user_name}</span>
            </div>
            """

        # 2. Get Custom Message
        message = conf.get("congratsMessage", DEFAULTS["congratsMessage"])

        # 3. Build Bottom Actions HTML for filtered decks
        bottom_actions_html = ""
        current_deck = self.mw.col.decks.current()
        if current_deck and current_deck.get("dyn"):
            bottom_actions_html = """
            <div class="congrats-bottom-actions">
                <a href="#" key=O onclick="pycmd('opts'); return false;" class="overview-button">Options</a>
                <a href="#" key=R onclick="pycmd('refresh'); return false;" class="overview-button">Rebuild</a>
                <a href="#" key=E onclick="pycmd('empty'); return false;" class="overview-button">Empty</a>
            </div>
            """

        # 4. Construct Final HTML Body
        body_html = f"""
        <div class="congrats-container">
            {header_html}
            {profile_bar_html}
            <div class="congrats-card">
                <h1>{message}</h1>
            </div>
            {bottom_actions_html}
        </div>
        """
        
        # 5. Generate Head Content (CSS)
        head_html = generate_dynamic_css(conf)
        head_html += generate_overview_background_css(addon_path)
        
        # 6. Render the page
        self.web.stdHtml(
            body_html,
            css=[f"/_addons/{addon_package}/web/congrats.css"],
            js=[], # JS messages are handled by the hook, no need to inject a file
            head=head_html,
            context=self,
        )
        # --- START OF FIX ---
        # Manually run JS to create the background div after the page is loaded.
        self.web.eval("""
            if (!document.getElementById('onigiri-background-div')) {
                const bgDiv = document.createElement('div');
                bgDiv.id = 'onigiri-background-div';
                document.body.prepend(bgDiv);
            }
        """)
        # --- END OF FIX ---

    Overview._show_finished_screen = new_show_finished_screen


def generate_deck_browser_backgrounds(addon_path):
    """Generates CSS for the main container background and sidebar."""
    conf = config.get_config()
    
    main_mode = mw.col.conf.get("modern_menu_background_mode", "color")
    main_image_mode = mw.col.conf.get("modern_menu_background_image_mode", "single")
    main_light_color = mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
    main_dark_color = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
    main_blur = mw.col.conf.get("modern_menu_background_blur", 0)
    main_opacity = mw.col.conf.get("modern_menu_background_opacity", 100)

    if main_image_mode == "separate":
        main_light_img_filename = mw.col.conf.get("modern_menu_background_image_light", "")
        main_dark_img_filename = mw.col.conf.get("modern_menu_background_image_dark", "")
    else:
        main_light_img_filename = mw.col.conf.get("modern_menu_background_image", "")
        main_dark_img_filename = main_light_img_filename

    main_light_img = f"user_files/main_bg/{main_light_img_filename}" if main_light_img_filename else ""
    main_dark_img = f"user_files/main_bg/{main_dark_img_filename}" if main_dark_img_filename else ""

    sidebar_mode = mw.col.conf.get("modern_menu_sidebar_bg_mode", "main")
    
    main_container_css = _render_background_css(
        ".container.modern-main-menu", main_mode, main_light_color, main_dark_color, 
        main_light_img, main_dark_img, main_blur, addon_path, "modern-menu-main-background-style", main_opacity
    )
    main_container_css += "<style>.main-content { background: transparent !important; }</style>"

    sidebar_css = ""
    if sidebar_mode == 'custom':
        #  REPLACE EVERYTHING INSIDE THIS IF BLOCK with the code below ðŸ”½
        side_mode = mw.col.conf.get("modern_menu_sidebar_bg_type", "color")
        side_light_color = mw.col.conf.get("modern_menu_sidebar_bg_color_light", "#F3F3F3")
        side_dark_color = mw.col.conf.get("modern_menu_sidebar_bg_color_dark", "#2C2C2C")
        side_blur = mw.col.conf.get("modern_menu_sidebar_bg_blur", 0)
        side_img_filename = mw.col.conf.get("modern_menu_sidebar_bg_image", "")
        side_img = f"user_files/sidebar_bg/{side_img_filename}" if side_img_filename else ""
        
        side_opacity = mw.col.conf.get("modern_menu_sidebar_bg_opacity", 100)
        side_transparency = mw.col.conf.get("modern_menu_sidebar_bg_transparency", 0)
        addon_name = os.path.basename(addon_path)

        if side_mode == "color" or side_mode == "accent":
            alpha = (100 - side_transparency) / 100.0
            
            if side_mode == "accent":
                 sidebar_css = f"""<style id='modern-menu-sidebar-background-style'>
                    .sidebar-left {{ position: relative; background: transparent !important; }}
                    .sidebar-left::before {{
                        content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 100%;
                        background: var(--accent-color);
                        opacity: {alpha};
                        z-index: -1;
                    }}
                </style>"""
            else: # solid color
                if side_transparency > 0:
                    light_rgba = _hex_to_rgba(side_light_color, alpha)
                    dark_rgba = _hex_to_rgba(side_dark_color, alpha)
                    sidebar_css = f"""<style id='modern-menu-sidebar-background-style'>
                        .sidebar-left {{ background-color: {light_rgba} !important; }}
                        .night-mode .sidebar-left {{ background-color: {dark_rgba} !important; }}
                    </style>"""
                else: # No transparency
                    sidebar_css = f"""<style id='modern-menu-sidebar-background-style'>
                        .sidebar-left {{ background-color: {side_light_color} !important; }}
                        .night-mode .sidebar-left {{ background-color: {side_dark_color} !important; }}
                    </style>"""

        elif side_mode == "image_color" and side_img:
            img_url = f"/_addons/{addon_name}/{side_img}"
            opacity_float = side_opacity / 100.0
            blur_px = side_blur * 0.2

            sidebar_css = f"""
            <style id='modern-menu-sidebar-background-style'>
                .sidebar-left {{
                    position: relative;
                    background-color: {side_light_color} !important;
                    overflow: hidden;
                    z-index: 1;
                }}
                .night-mode .sidebar-left {{
                    background-color: {side_dark_color} !important;
                }}
                .sidebar-left::before {{
                    content: '';
                    position: absolute;
                    top: 0; right: 0; bottom: 0; left: 0;
                    background-image: url('{img_url}');
                    background-size: cover;
                    background-position: center;
                    background-repeat: no-repeat;
                    opacity: {opacity_float};
                    filter: blur({blur_px}px);
                    z-index: -1;
                }}
            </style>
            """
    else: # sidebar_mode == 'main'
        effect_mode = mw.col.conf.get("onigiri_sidebar_main_bg_effect_mode", "opaque")
        
        if effect_mode == "glassmorphism":
            intensity = mw.col.conf.get("onigiri_sidebar_main_bg_effect_intensity", 50)
            blur_px = (intensity / 100.0) * 15.0
            alpha = (intensity / 100.0) * 0.3
            
            sidebar_css = f"""
            <style id='modern-menu-sidebar-background-style'>
                .sidebar-left {{
                    background-color: rgba(255, 255, 255, {alpha}) !important;
                    backdrop-filter: blur({blur_px}px);
                    -webkit-backdrop-filter: blur({blur_px}px);
                }}
                .night-mode .sidebar-left {{
                    background-color: rgba(0, 0, 0, {alpha}) !important;
                }}
            </style>
            """
        else: # opaque color overlay
            intensity = mw.col.conf.get("onigiri_sidebar_opaque_tint_intensity", 30)
            alpha = intensity / 100.0
            
            light_color_hex = mw.col.conf.get("onigiri_sidebar_opaque_tint_color_light", "#FFFFFF")
            dark_color_hex = mw.col.conf.get("onigiri_sidebar_opaque_tint_color_dark", "#1D1D1D")
            
            light_rgba = _hex_to_rgba(light_color_hex, alpha)
            dark_rgba = _hex_to_rgba(dark_color_hex, alpha)

            sidebar_css = f"""
            <style id='modern-menu-sidebar-background-style'>
                .sidebar-left {{
                    background-color: {light_rgba} !important;
                }}
                .night-mode .sidebar-left {{
                    background-color: {dark_rgba} !important;
                }}
            </style>
            """
        
    return main_container_css + sidebar_css

def generate_reviewer_background_css(addon_path):
    """Generates CSS for the reviewer using a dedicated background div."""
    mode = mw.col.conf.get("modern_menu_background_mode", "color")

    # If not using an image, use a simple background color and stop.
    if mode not in ["image", "image_color"]:
        light_color = mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
        dark_color = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
        return f"""<style>
            body {{ background-color: {light_color} !important; }}
            .night-mode body {{ background-color: {dark_color} !important; }}
        </style>"""

    # --- New logic for image backgrounds ---
    image_mode = mw.col.conf.get("modern_menu_background_image_mode", "single")
    blur_val = mw.col.conf.get("modern_menu_background_blur", 0)
    opacity_val = mw.col.conf.get("modern_menu_background_opacity", 100)
    addon_name = os.path.basename(addon_path)

    # Determine image URLs
    if image_mode == "separate":
        light_img_file = mw.col.conf.get("modern_menu_background_image_light", "")
        dark_img_file = mw.col.conf.get("modern_menu_background_image_dark", "")
    else:
        light_img_file = mw.col.conf.get("modern_menu_background_image", "")
        dark_img_file = light_img_file

    light_img_url = f"/_addons/{addon_name}/user_files/main_bg/{light_img_file}" if light_img_file else "none"
    dark_img_url = f"/_addons/{addon_name}/user_files/main_bg/{dark_img_file}" if dark_img_file else "none"

    # Generate the final CSS
    return f"""
    <style id="onigiri-reviewer-background-style">
        #onigiri-background-div {{
            position: fixed;
            left: 0; top: 0;
            width: 100vw; height: 100vh;
            background-position: center;
            background-size: cover;
            background-repeat: no-repeat;
            z-index: -1;
            filter: blur({blur_val * 0.2}px);
            opacity: {opacity_val / 100.0};
            pointer-events: none;
            background-image: url('{light_img_url}');
        }}
        .night-mode #onigiri-background-div {{
            background-image: url('{dark_img_url}');
        }}
        html, body, #middle, .card, #qa {{
            background: transparent !important;
        }}
    </style>
    """

def generate_overview_background_css(addon_path):
    """Generates CSS for the overview screen using a dedicated background div."""
    mode = mw.col.conf.get("modern_menu_background_mode", "color")

    if mode not in ["image", "image_color"]:
        light_color = mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
        dark_color = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
        return f"""<style>
            body {{ background-color: {light_color} !important; }}
            .night-mode body {{ background-color: {dark_color} !important; }}
        </style>"""

    image_mode = mw.col.conf.get("modern_menu_background_image_mode", "single")
    blur_val = mw.col.conf.get("modern_menu_background_blur", 0)
    opacity_val = mw.col.conf.get("modern_menu_background_opacity", 100)
    addon_name = os.path.basename(addon_path)

    if image_mode == "separate":
        light_img_file = mw.col.conf.get("modern_menu_background_image_light", "")
        dark_img_file = mw.col.conf.get("modern_menu_background_image_dark", "")
    else:
        light_img_file = mw.col.conf.get("modern_menu_background_image", "")
        dark_img_file = light_img_file

    light_img_url = f"/_addons/{addon_name}/user_files/main_bg/{light_img_file}" if light_img_file else "none"
    dark_img_url = f"/_addons/{addon_name}/user_files/main_bg/{dark_img_file}" if dark_img_file else "none"

    return f"""
    <style id="onigiri-overview-background-style">
        #onigiri-background-div {{
            position: fixed;
            left: 0; top: 0;
            width: 100vw; height: 100vh;
            background-position: center;
            background-size: cover;
            background-repeat: no-repeat;
            z-index: -1;
            filter: blur({blur_val * 0.2}px);
            opacity: {opacity_val / 100.0};
            pointer-events: none;
            background-image: url('{light_img_url}');
        }}
        .night-mode #onigiri-background-div {{
            background-image: url('{dark_img_url}');
        }}
        html, body, .overview-center-container, .congrats-container {{
            background: transparent !important;
        }}
    </style>
    """

def generate_toolbar_background_css(addon_path):
	"""Generates background CSS for the top and bottom toolbars based on user settings."""
	toolbar_mode = mw.col.conf.get("onigiri_toolbar_bg_mode", "main")

	if toolbar_mode == "main":
		# Use main background settings
		mode = mw.col.conf.get("modern_menu_background_mode", "color")
		light = mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
		dark = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
		image = mw.col.conf.get("modern_menu_background_image", "")
		blur = mw.col.conf.get("modern_menu_background_blur", 0)
		opacity = 100 # Opacity not supported for toolbar custom bg yet
		image_path = f"user_files/{image}" if image else ""
	else:
		# Use toolbar-specific settings
		mode = toolbar_mode
		light = mw.col.conf.get("onigiri_toolbar_bg_color_light", "#FFFFFF")
		dark = mw.col.conf.get("onigiri_toolbar_bg_color_dark", "#2C2C2C")
		image = mw.col.conf.get("onigiri_toolbar_bg_image", "")
		blur = mw.col.conf.get("onigiri_toolbar_bg_blur", 0)
		opacity = 100 # Opacity not supported for toolbar custom bg yet
		image_path = f"user_files/toolbar_bg/{image}" if image else ""

	return _render_background_css("body", mode, light, dark, image_path, image_path, blur, addon_path, "onigiri-toolbar-bg-style", opacity)

# <<< START NEW CODE >>>
def generate_reviewer_top_bar_background_css(addon_path: str) -> str:
    """Generates CSS for the custom reviewer top bar."""
    bar_mode = mw.col.conf.get("onigiri_reviewer_top_bar_bg_mode", "transparent")
    blur_val = mw.col.conf.get("onigiri_reviewer_top_bar_bg_blur", 0)
    opacity_val = mw.col.conf.get("onigiri_reviewer_top_bar_bg_opacity", 100)
    
    selector = "#onigiri-reviewer-header"
    blur_px = blur_val * 0.2

    if bar_mode == "transparent":
        alpha = opacity_val / 100.0
        return f"""<style id="onigiri-reviewer-top-bar-bg-style">
            {selector} {{
                background-color: rgba(255, 255, 255, {alpha}) !important;
                backdrop-filter: blur({blur_px}px);
                -webkit-backdrop-filter: blur({blur_px}px);
            }}
            .night-mode {selector} {{
                background-color: rgba(0, 0, 0, {alpha}) !important;
            }}
        </style>"""

    if bar_mode == "color":
        alpha = opacity_val / 100.0
        light_color_hex = mw.col.conf.get("onigiri_reviewer_top_bar_bg_light_color", "#FFFFFF")
        dark_color_hex = mw.col.conf.get("onigiri_reviewer_top_bar_bg_dark_color", "#2C2C2C")
        light_rgba = _hex_to_rgba(light_color_hex, alpha)
        dark_rgba = _hex_to_rgba(dark_color_hex, alpha)

        return f"""<style id="onigiri-reviewer-top-bar-bg-style">
            {selector} {{
                background-color: {light_rgba} !important;
                backdrop-filter: blur({blur_px}px);
                -webkit-backdrop-filter: blur({blur_px}px);
            }}
            .night-mode {selector} {{
                background-color: {dark_rgba} !important;
            }}
        </style>"""

    if bar_mode in ["image", "image_color"]:
        mode = "image_color"
        bg_position = "center top"
        light_color = mw.col.conf.get("onigiri_reviewer_top_bar_bg_light_color", "#FFFFFF")
        dark_color = mw.col.conf.get("onigiri_reviewer_top_bar_bg_dark_color", "#2C2C2C")
        img_filename = mw.col.conf.get("onigiri_reviewer_top_bar_bg_image", "")
        img = f"user_files/reviewer_top_bar_bg/{img_filename}" if img_filename else ""

        return _render_background_css(
            selector, mode, light_color, dark_color, img, img, blur_val,
            addon_path, "onigiri-reviewer-top-bar-bg-style", opacity_val,
            background_position=bg_position
        )
        
    return "" # Fallback for unknown modes
def generate_reviewer_top_bar_html_and_css():
    """Generates the HTML and basic structural CSS for the new web-based reviewer top bar."""

    conf = config.get_config()
    is_base_hide_mode = (
        conf.get("hideNativeHeaderAndBottomBar", False)
        and not conf.get("proHide", False)
    )
    if not is_base_hide_mode:
        return "", ""

    html = """
    <div id="onigiri-reviewer-header">
        <div class="onigiri-reviewer-header-buttons">
            <a href="#" onclick="pycmd('deckBrowser'); return false;" class="onigiri-reviewer-button">Decks</a>
            <a href="#" onclick="pycmd('add'); return false;" class="onigiri-reviewer-button">Add</a>
            <a href="#" onclick="pycmd('browse'); return false;" class="onigiri-reviewer-button">Browse</a>
            <a href="#" onclick="pycmd('stats'); return false;" class="onigiri-reviewer-button">Stats</a>
            <a href="#" onclick="pycmd('sync'); return false;" class="onigiri-reviewer-button">Sync</a>
        </div>
    </div>
    """

    css = """
    <style id="onigiri-reviewer-top-bar-structure">
        #onigiri-reviewer-header, .overview-header {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            width: 35%;
            margin: 10px auto;
            margin-top: 5px;
            border-radius: 12px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0 10px;
            box-sizing: border-box;
            -webkit-font-smoothing: antialiased;
        }

        .onigiri-reviewer-header-buttons {
            display: flex;
            gap: 10px;
        }

        .onigiri-reviewer-button {
            color: var(--fg);
            background: rgba(247, 247, 247);
            padding: 5px 12px;
            border-radius: 8px;
            border: 1px solid rgba(128, 128, 128, 0.2);
            font-size: 13px;
            text-decoration: none;
            transition: background-color 0.2s ease, border-color 0.2s ease;
        }

        .night_mode .onigiri-reviewer-button {
            color: var(--fg);
            background: rgba(42, 42, 42);
            padding: 5px 12px;
            border-radius: 8px;
            font-size: 13px;
            font-color: white;
            text-decoration: none;
            transition: background-color 0.2s ease, border-color 0.2s ease;
        }

        .onigiri-reviewer-button:hover {
            background: rgba(128, 128, 128, 0.25);
            color: white;
        }

        body.card {
            padding-top: 40px;
        }
    </style>
    """

    return html, css

def generate_reviewer_bottom_bar_background_css(addon_path: str) -> str:
    """Generates CSS for the reviewer's bottom bar background."""
    bar_mode = mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_mode", "main")

    offset_x_str = mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_offset_x", "-3.25")
    try:
        offset_x = float(offset_x_str)
    except (ValueError, TypeError):
        offset_x = -3.25

    bg_position = f"calc(50% + {offset_x}px) bottom"

    css = ""
    selector = "body"

    if bar_mode == "main":
        mode = mw.col.conf.get("modern_menu_background_mode", "color")
        image_mode = mw.col.conf.get("modern_menu_background_image_mode", "single")
        light_color = mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
        dark_color = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")

        if image_mode == "separate":
            light_img_filename = mw.col.conf.get("modern_menu_background_image_light", "")
            dark_img_filename = mw.col.conf.get("modern_menu_background_image_dark", "")
        else:
            light_img_filename = mw.col.conf.get("modern_menu_background_image", "")
            dark_img_filename = light_img_filename

        light_img = f"user_files/main_bg/{light_img_filename}" if light_img_filename else ""
        dark_img = f"user_files/main_bg/{dark_img_filename}" if dark_img_filename else ""

        blur_val = mw.col.conf.get("onigiri_reviewer_bottom_bar_match_main_blur", 5)
        opacity_val = mw.col.conf.get("onigiri_reviewer_bottom_bar_match_main_opacity", 90)

        css += "<style>#outer { background: transparent !important; border-top: none !important; }</style>"
        css += f"<style>#outer {{ opacity: {opacity_val / 100.0}; }}</style>"
        css += _render_background_css(selector, mode, light_color, dark_color, light_img, dark_img, blur_val, addon_path, "onigiri-reviewer-bottom-bar-bg-style", 100, background_position=bg_position)

    else: # Custom settings for the bar
        mode = bar_mode
        light_color = mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_light_color", "#FFFFFF")
        dark_color = mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_dark_color", "#2C2C2C")
        img_filename = mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_image", "")
        img = f"user_files/reviewer_bar_bg/{img_filename}" if img_filename else ""
        blur_val = mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_blur", 0)
        opacity_val = mw.col.conf.get("onigiri_reviewer_bottom_bar_bg_opacity", 100)

        css += _render_background_css(selector, mode, light_color, dark_color, img, img, blur_val, addon_path, "onigiri-reviewer-bottom-bar-bg-style", opacity_val, background_position=bg_position)
        css += "<style>#outer { background: transparent !important; border-top: none !important; }</style>"

    return css

def generate_profile_bar_fix_css():
    """Generates responsive CSS to ensure the profile picture fits within the profile bar."""
    return """
<style id="onigiri-profile-bar-fix">
/* --- NEW RULES START --- */
.profile-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    overflow: hidden;
    box-sizing: border-box;
    
    position: relative; /* Establishes a positioning context for the picture */
    flex-shrink: 0;     /* Prevents the bar itself from shrinking vertically */
    
    /* Top, Right, Bottom, Left padding. Left padding makes space for the picture. */
    padding: 6px 8px 6px 50px; 
    min-height: 50px; /* Ensures the bar has a minimum size */
}

.profile-pic, .profile-pic-placeholder {
    position: absolute;   /* Positions the picture relative to the bar */
    top: 5px;             /* 5px from the top of the bar */
    left: 5px;            /* 5px from the left of the bar */
    
    /* Forces the height to be the container's height minus 10px (for padding) */
    height: calc(100% - 10px);
    width: auto;          /* Width will follow height due to aspect-ratio */
    aspect-ratio: 1 / 1;  /* Guarantees it is a perfect circle */
    
    border-radius: 50%;
}
/* --- NEW RULES END --- */

.profile-pic {
    object-fit: cover;
}

.profile-pic-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: clamp(14px, 4vw, 20px);
    background-color: rgba(0,0,0,0.1);
    border: 1px solid rgba(255,255,255,0.1);
}

.profile-name {
    font-weight: 500;
    font-size: 16px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
</style>
"""

def generate_icon_size_css():
    """
    Generates CSS to control the size of various icons based on user settings.
    """
    # These keys correspond to the settings in the "Icons" tab.
    icon_configs = {
        "deck_folder": {
            "selector": "a.deck::before",
            "default": 18,
        },
        "action_button": {
            "selector": ".menu-item .icon, .add-button-dashed .icon",
            "default": 16,
        },
        "collapse": {
            "selector": "a.collapse, span.collapse",
            "default": 16,
        },
        "options_gear": {
            "selector": "td.opts a",
            "default": 16,
        },
    }

    css_rules = []
    for key, config in icon_configs.items():
        config_key = f"modern_menu_icon_size_{key}"
        size = mw.col.conf.get(config_key, config["default"])
        selector = config["selector"]
        css_rules.append(f"{selector} {{ width: {size}px; height: {size}px; }}")

    return f"<style id='modern-menu-icon-size-styles'>{''.join(css_rules)}</style>"

def generate_icon_css(addon_package, conf):
    all_icon_selectors = {
        "options": "td.opts a", "folder": "tr.is-folder a.deck::before",
        "deck_child": "tr.deck:has(span.collapse) a.deck::before", "add": "#add-btn .icon",
        "browse": "#browser-btn .icon", "stats": "#stats-btn .icon", "sync": "#sync-btn .icon",
        "settings": "#onigiri-settings-btn .icon", "more": "summary.menu-item .icon",
        "get_shared": "#get-shared-btn .icon", "create_deck": "#create-deck-btn .icon",
        "import_file": "#import-file-btn .icon",
        "retention_star": ".star",
    }
    
    css_rules = []
    for key, selector in all_icon_selectors.items():
        filename = mw.col.conf.get(f"modern_menu_icon_{key}", "")
        url = ""
        if filename:
            url = f"url('/_addons/{addon_package}/user_files/icons/{filename}')"
        else:
            system_icon_name = 'star' if key == 'retention_star' else key
            url = f"url('/_addons/{addon_package}/user_files/icons/system_icons/{system_icon_name}.svg')"
        
        css_rules.append(f"{selector} {{ mask-image: {url}; -webkit-mask-image: {url}; }}")

    # --- Get URLs for collapse icons ---
    closed_icon_file = mw.col.conf.get("modern_menu_icon_collapse_closed", "")
    open_icon_file = mw.col.conf.get("modern_menu_icon_collapse_open", "")

    closed_icon_url = f"url('/_addons/{addon_package}/user_files/icons/{closed_icon_file}')" if closed_icon_file \
        else f"url('/_addons/{addon_package}/user_files/icons/system_icons/collapse_closed.svg')"

    open_icon_url = f"url('/_addons/{addon_package}/user_files/icons/{open_icon_file}')" if open_icon_file \
        else f"url('/_addons/{addon_package}/user_files/icons/system_icons/collapse_open.svg')"
        
    # Create a list of selectors for the background color, EXCLUDING the star
    bg_color_selectors = {k: v for k, v in all_icon_selectors.items() if k != "retention_star"}
    bg_selectors_str = ", ".join(bg_color_selectors.values())

    return f"""
<style id="modern-menu-icon-styles">
    /* Hide the original '+' or '-' text from the link. */
    a.collapse {{
        font-size: 0 !important;
    }}

    /* Create the icon using a pseudo-element on the link. */
    a.collapse::before {{
        content: '';
        display: inline-block;
        width: 100%;
        height: 100%;
        /* START FIX: Set background to transparent by default to prevent flash */
        background-color: transparent;
        transition: background-color 0.1s ease;
        /* END FIX */
        mask-size: contain;
        mask-repeat: no-repeat;
        mask-position: center;
        -webkit-mask-size: contain;
        -webkit-mask-repeat: no-repeat;
        -webkit-mask-position: center;
    }}

    /* Apply the correct SVG icon and background color only when the state class is present. */
    a.collapse.state-closed::before {{
        mask-image: {closed_icon_url};
        -webkit-mask-image: {closed_icon_url};
        background-color: var(--icon-color, #888888);
        /* END FIX */
    }}
    a.collapse.state-open::before {{
        mask-image: {open_icon_url};
        -webkit-mask-image: {open_icon_url};
        /* START FIX: Apply background color here */
        background-color: var(--icon-color, #888888);
        /* END FIX */
    }}

    /* General rules for other icons (Unchanged) */
    {bg_selectors_str} {{
        background-color: var(--icon-color, #888888);
        mask-size: contain;
        mask-repeat: no-repeat;
        mask-position: center;
        -webkit-mask-size: contain;
        -webkit-mask-repeat: no-repeat;
        -webkit-mask-position: center;
        display: inline-block;
    }}
    /* Individual mask images for other icons (Unchanged) */
    {''.join(css_rules)}
</style>
"""

def generate_conditional_css(conf):
	styles = []
	if conf.get("hideTodaysStats", False):
		styles.append(".stats-grid { display: none !important; }")
	if conf.get("hideProfileBar", False):
		styles.append(".profile-bar { display: none !important; }")
	# -- The old, unreliable CSS rule for the header and bottom bar has been removed. --
	if not styles: return ""
	return f"<style id='modern-menu-conditional-styles'>{' '.join(styles)}</style>"

def generate_font_css(addon_package):
    """Generates @font-face rules and CSS variables for selected fonts."""
    main_font_key = mw.col.conf.get("onigiri_font_main", "system")
    subtle_font_key = mw.col.conf.get("onigiri_font_subtle", "system")
    
    # <<< MODIFIED: Use get_all_fonts to include user-added fonts >>>
    all_fonts = get_all_fonts(os.path.dirname(__file__))
    main_font_info = all_fonts.get(main_font_key)
    subtle_font_info = all_fonts.get(subtle_font_key)
    # <<< END MODIFIED >>>

    if not main_font_info or not subtle_font_info:
        return ""

    font_faces = ""
    # Use a set to avoid generating duplicate @font-face rules
    fonts_to_load = {main_font_key, subtle_font_key}
    
    # <<< MODIFIED: Loop through all fonts to generate @font-face rules >>>
    for font_key in fonts_to_load:
        font_info = all_fonts.get(font_key)
        if font_info and font_info.get("file"):
            # Handle different paths for user vs system fonts
            if font_info.get("user"):
                font_url = f"/_addons/{addon_package}/user_files/fonts/{font_info['file']}"
            else:
                font_url = f"/_addons/{addon_package}/user_files/fonts/system_fonts/{font_info['file']}"
            
            font_faces += f"""
                @font-face {{
                    font-family: '{font_info['family']}';
                    src: url('{font_url}');
                }}
            """
    # <<< END MODIFIED >>>

    # Generate the final CSS block
    font_css = f"""
    <style id="onigiri-font-styles">
        {font_faces}
        :root {{
            --font-main: {main_font_info['family']};
            --font-subtle: {subtle_font_info['family']};
        }}
        
        body {{
            font-family: var(--font-main), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        }}
        
        .sidebar-left h2, .stat-card h3 {{
            font-family: var(--font-subtle), -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        }}
    </style>
    """
    
    return font_css

def generate_dynamic_css(conf):
	# ADDED to get the add-on's path for font files
	addon_package = mw.addonManager.addonFromModule(__name__)
	# ADDED to generate the font-specific CSS
	font_css_block = generate_font_css(addon_package)

	effect_mode = mw.col.conf.get("onigiri_canvas_inset_effect_mode", "none")
	effect_intensity = mw.col.conf.get("onigiri_canvas_inset_effect_intensity", 50)

	def _apply_canvas_inset_effect(colors: dict):
		"""Applies opacity or glassmorphism effect to --canvas-inset color."""
		if "--canvas-inset" not in colors:
			return

		if effect_mode in ["opacity", "glassmorphism"]:
			original_hex = colors["--canvas-inset"]
			
			# Intensity to alpha mapping (0-100 -> 1.0-0.0)
			# For glassmorphism, higher intensity means more transparency.
			alpha = (100 - effect_intensity) / 100.0
			
			# For simple opacity, higher intensity means more opacity.
			if effect_mode == "opacity":
				alpha = effect_intensity / 100.0

			colors["--canvas-inset"] = _hex_to_rgba(original_hex, alpha)

	colors = conf.get("colors", {})
	light_colors = colors.get("light", {}).copy()
	dark_colors = colors.get("dark", {}).copy()

	# Apply effects if enabled
	_apply_canvas_inset_effect(light_colors)
	_apply_canvas_inset_effect(dark_colors)

	# Special case: One setting for two CSS variables
	if "--button-primary-bg" in light_colors:
		light_colors["--button-primary-bg"] = light_colors["--button-primary-bg"]
	if "--button-primary-bg" in dark_colors:
		dark_colors["--button-primary-bg"] = dark_colors["--button-primary-bg"]
	light_rules = "\n".join([f"    {key}: {value} !important;" for key, value in light_colors.items()])
	dark_rules = "\n".join([f"    {key}: {value} !important;" for key, value in dark_colors.items()])
	
	profile_light_color = mw.col.conf.get("modern_menu_profile_bg_color_light", "#EEEEEE")
	profile_dark_color = mw.col.conf.get("modern_menu_profile_bg_color_dark", "#3C3C3C")
	light_rules += f"\n    --profile-bg-custom-color: {profile_light_color} !important;"
	dark_rules += f"\n    --profile-bg-custom-color: {profile_dark_color} !important;"

	# --- New Glassmorphism Style Block ---
	glass_style_block = ""
	if effect_mode == "glassmorphism":
		# Map intensity (0-100) to blur radius (0-20px)
		blur_px = (effect_intensity / 100.0) * 20
		# --- FIX: Added heatmap container IDs to the selectors ---
		glass_selectors = ".stats-container, .congrats-card, .stat-card, #onigiri-heatmap-container, #onigiri-profile-heatmap-container"
		glass_style_block = f"""
        <style id="onigiri-glass-effect">
        {glass_selectors} {{
            backdrop-filter: blur({blur_px}px);
            -webkit-backdrop-filter: blur({blur_px}px);
        }}
        </style>
        """

	# MODIFIED to prepend the new font CSS
	return f"""
    {font_css_block}
    <style id="modern-menu-dynamic-styles">
    :root {{ {light_rules} }}
    .night-mode {{ {dark_rules} }}
    </style>
    {glass_style_block}
    """

# (Deleted the old prepend_custom_stats function and add this block)

def _get_hook_name(hook):
    """Creates a unique, stable identifier for a hook function."""
    module_name = hook.__module__ if hasattr(hook, '__module__') else 'unknown_module'
    return f"{module_name}.{hook.__name__}"

def _get_external_hooks():
    """Returns the list of hooks that Onigiri is managing."""
    return _managed_hooks

def _get_onigiri_stat_card_html(label: str, value: str, widget_id: str) -> str:
    return f"""<div class="stat-card {widget_id}-card"><h3>{label}</h3><p>{value}</p></div>"""

def _get_onigiri_retention_html() -> str:
    total_reviews, correct_reviews = mw.col.db.first(
        "select count(*), sum(case when ease > 1 then 1 else 0 end) from revlog where type = 1 and id > ?",
        (mw.col.sched.dayCutoff - 86400) * 1000
    ) or (0, 0)
    total_reviews = total_reviews or 0
    correct_reviews = correct_reviews or 0
    retention_percentage = (correct_reviews / total_reviews * 100) if total_reviews > 0 else 0

    if retention_percentage >= 90: stars = 5
    elif retention_percentage >= 70: stars = 4
    elif retention_percentage >= 50: stars = 3
    elif retention_percentage >= 30: stars = 2
    elif total_reviews > 0: stars = 1
    else: stars = 0
    
    star_html = "".join([f"<i class='star{' empty' if i >= stars else ''}'></i>" for i in range(5)])

    return f"""
    <div class="stat-card retention-card">
        <h3>Retention</h3>
        <p>{retention_percentage:.0f}%</p>
        <div class="star-rating">{star_html}</div>
    </div>
    """

def _get_onigiri_heatmap_html() -> str:
    skeleton_cells = "".join(["<div class='skeleton-cell'></div>" for _ in range(371)])
    return f"""
    <div id='onigiri-heatmap-container'>
        <div class="heatmap-header-skeleton"><div class="header-left-skeleton"><div class="skeleton-title"></div><div class="skeleton-nav"></div></div><div class="header-right-skeleton"><div class="skeleton-streak"></div><div class="skeleton-filters"></div></div></div>
        <div class="heatmap-grid-skeleton">{skeleton_cells}</div>
    </div>"""

def render_custom_main_screen(deck_browser, content):
    """
    The new hook function that builds the entire main screen layout based on user settings.
    """
    conf = config.get_config()
    addon_package = mw.addonManager.addonFromModule(__name__)

    # --- 1. Set up the main HTML template (from the old function) ---
    is_collapsed = mw.col.conf.get("onigiri_sidebar_collapsed", False)
    sidebar_initial_class = "sidebar-collapsed" if is_collapsed else ""
    user_name = conf.get("userName", "USER") 
    profile_pic_filename = mw.col.conf.get("modern_menu_profile_picture", "")
    if profile_pic_filename:
        profile_pic_url = f"/_addons/{addon_package}/user_files/profile/{profile_pic_filename}"
        profile_pic_html = f'<img src="{profile_pic_url}" class="profile-pic">'
    else:
        profile_pic_html = f'<div class="profile-pic-placeholder"><span>{user_name[0] if user_name else "U"}</span></div>'
    profile_bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "accent")
    profile_bg_image = mw.col.conf.get("modern_menu_profile_bg_image", "")
    bg_style_str = ""; bg_class_str = ""
    if profile_bg_mode == "image" and profile_bg_image:
        bg_image_url = f"/_addons/{addon_package}/user_files/profile_bg/{profile_bg_image}"; bg_style_str = f"background-image: url('{bg_image_url}'); background-size: cover; background-position: center;"; bg_class_str = "with-image-bg"
    elif profile_bg_mode == "custom": bg_style_str = "background-color: var(--profile-bg-custom-color);"
    else: bg_style_str = "background-color: var(--accent-color);"
    profile_bar_html = f"""<div class="profile-bar {bg_class_str}" style="{bg_style_str}" onclick="pycmd('showUserProfile')">{profile_pic_html}<span class="profile-name">{user_name}</span></div>"""
    welcome_message = ""
    if not conf.get("hideWelcomeMessage", False): welcome_message = f"WELCOME {user_name.upper()}!"
    saved_width = mw.col.conf.get("modern_menu_sidebar_width", 260)
    sidebar_style = f"width: {saved_width}px;"

    from .templates import custom_body_template 
    DeckBrowser._body = custom_body_template.format(welcome_message=welcome_message, sidebar_style=sidebar_style, profile_bar=profile_bar_html, sidebar_initial_class=sidebar_initial_class, tree="")

    # --- 2. Build Onigiri Widgets Grid ---
    onigiri_layout = conf.get("onigiriWidgetLayout", {}).get("grid", {})
    onigiri_grid_html = ""

    # Generate stats data once
    cards_today, time_today_seconds = deck_browser.mw.col.db.first("select count(), sum(time)/1000 from revlog where id > ?", (deck_browser.mw.col.sched.dayCutoff - 86400) * 1000) or (0, 0)
    time_today_seconds = time_today_seconds or 0
    cards_today = cards_today or 0
    time_today_minutes = time_today_seconds / 60
    seconds_per_card = time_today_seconds / cards_today if cards_today > 0 else 0

    # Map widget IDs to their HTML generation logic
    widget_html_generators = {
        "studied": lambda: _get_onigiri_stat_card_html("Studied", f"{cards_today} cards", "studied"),
        "time": lambda: _get_onigiri_stat_card_html("Time", f"{time_today_minutes:.1f} min", "time"),
        "pace": lambda: _get_onigiri_stat_card_html("Pace", f"{seconds_per_card:.1f} s/card", "pace"),
        "retention": _get_onigiri_retention_html,
        "heatmap": _get_onigiri_heatmap_html,
    }
            
    for widget_id, widget_config in onigiri_layout.items():
        if widget_id in widget_html_generators:
            pos = widget_config.get("pos", 0)
            row_span = widget_config.get("row", 1)
            col_span = widget_config.get("col", 1)
            row = pos // 4 + 1
            col = pos % 4 + 1
            style = f"grid-area: {row} / {col} / span {row_span} / span {col_span};"
            onigiri_grid_html += f'<div class="onigiri-widget-container" style="{style}">{widget_html_generators[widget_id]()}</div>'

    # --- 3. Build External Add-on Widgets Grid ---
    external_hooks = _get_external_hooks()
    external_layout = conf.get("externalWidgetLayout", {})
    grid_config = external_layout.get("grid", {})
    archive_list = external_layout.get("archive", [])
    external_widgets_html = ""
    
    # Isolate and capture HTML from each external hook
    external_widgets_data = {}
    for hook in external_hooks:
        hook_id = _get_hook_name(hook)
        class TempContent: stats = ""
        temp_content = TempContent()
        try:
            hook(deck_browser, temp_content)
            external_widgets_data[hook_id] = temp_content.stats
        except Exception as e:
            external_widgets_data[hook_id] = f"<div style='color: red;'>Error in {hook_id}:<br>{e}</div>"

    # Place external widgets according to layout
    placed_hooks = set()
    for hook_id, widget_config in grid_config.items():
        if hook_html := external_widgets_data.get(hook_id):
            pos = widget_config.get("grid_position", 0)
            row = pos // 4 + 1; col = pos % 4 + 1
            row_span = widget_config.get("row_span", 1); col_span = widget_config.get("column_span", 1)
            style = f"grid-area: {row} / {col} / span {row_span} / span {col_span};"
            external_widgets_html += f'<div class="external-widget-container" style="{style}">{hook_html}</div>'
            placed_hooks.add(hook_id)

    # Add archived hooks to placed_hooks so they aren't rendered as "unplaced"
    for hook_id in archive_list:
        placed_hooks.add(hook_id)

    # --- 4. Assemble the Final HTML ---
    stats_title = mw.col.conf.get("modern_menu_statsTitle", config.DEFAULTS["statsTitle"])
    title_html = f'<h1 class="onigiri-widget-title">{stats_title}</h1>' if stats_title else ""

    final_html = f"""
    <style>
        .onigiri-grid, .external-grid {{
            display: grid;
            gap: 15px;
            align-items: start;
        }}
        .onigiri-grid {{
            grid-template-columns: repeat(4, 1fr);
            margin-bottom: 20px;
        }}
        .external-grid {{
            grid-template-columns: repeat(4, 1fr);
        }}
        .onigiri-widget-container, .external-widget-container {{
            overflow: hidden;
            min-height: 50px;
        }}
    </style>
    {title_html}
    <div class="onigiri-grid">
        {onigiri_grid_html}
    </div>
    <div class="external-grid">
        {external_widgets_html}
    </div>
    """

    content.stats = final_html

def _new_MainWebView_eventFilter(self: MainWebView, obj: QObject, evt: QEvent) -> bool:
	"""Prevents Anki's default hover-to-show-toolbar behavior."""
	conf = config.get_config()
	should_hide_setting = conf.get("hideNativeHeaderAndBottomBar", False)

	screens_to_interfere = ["deckBrowser", "overview", "review"]
	
	should_interfere = should_hide_setting and mw.state in screens_to_interfere

	if should_interfere:
		# On deck browser/overview, prevent Anki's native hover logic from showing toolbars
		if super(MainWebView, self).eventFilter(obj, evt):
			return True
		if evt.type() == QEvent.Type.Leave and self.mw.fullscreen:
			self.mw.show_menubar()
			return True
		# Block other events from reaching the original handler, which would show the toolbars.
		return False
	else:
		# On all other screens (like reviewer), or if the setting is off, use Anki's original logic.
		if _original_MainWebView_eventFilter:
			return _original_MainWebView_eventFilter(self, obj, evt)
		return super(MainWebView, self).eventFilter(obj, evt)


def _update_toolbar_visibility(new_state: str, _old_state: str) -> None:
    """This function is called by a hook every time the screen changes."""
    conf = config.get_config()
    should_hide_setting = conf.get("hideNativeHeaderAndBottomBar", False)
    pro_hide = conf.get("proHide", False)
    max_hide = conf.get("maxHide", False)

    if not should_hide_setting:
        # If the feature is disabled in settings, ensure toolbars are always visible
        mw.toolbar.web.setVisible(True)
        mw.bottomWeb.setVisible(True)
        return

    # Handle reviewer state first with new priority
    if new_state == "review":
        if max_hide:
            # Max hide: Hide both top and bottom toolbars
            mw.toolbar.web.setVisible(False)
            mw.bottomWeb.setVisible(False)
        elif pro_hide:
            # Pro hide: Hide only top toolbar
            mw.toolbar.web.setVisible(False)
            mw.bottomWeb.setVisible(True)
        else:
            # Base hide mode on reviewer screen: Show both
            mw.toolbar.web.setVisible(False)
            mw.bottomWeb.setVisible(True)
        return

    # General hiding logic for other screens
    states_to_hide = ["deckBrowser", "overview"]
    if new_state in states_to_hide:
        # Hide both toolbars on the main menu and deck overview
        mw.toolbar.web.setVisible(False)
        mw.bottomWeb.setVisible(False)
    else:
        # Show toolbars on ALL other screens (this will now exclude the 'review' case when pro_hide is on)
        mw.toolbar.web.setVisible(True)
        mw.bottomWeb.setVisible(True)

def _onigiri_render_deck_node(self, node, ctx) -> str:
    """
    A patched version of DeckBrowser._render_deck_node that creates the
    HTML structure Onigiri's CSS and JS expect (e.g., td.collapse-cell).
    """
    buf = []  # Use a list for efficient string building

    if node.collapsed:
        prefix = "+"
    else:
        prefix = "-"

    due = node.review_count + node.learn_count

    def indent():
        return "&nbsp;" * 6 * (node.level - 1)

    klass = "deck current" if node.deck_id == ctx.current_deck_id else "deck"
    deck_type_class = "is-folder" if node.children else "is-deck"
    
    buf.append(f"<tr class='{klass} {deck_type_class}' id='{node.deck_id}'>")

    if node.children:
        collapse_link = f"<a class=collapse href=# onclick='return pycmd(\"collapse:{node.deck_id}\")'>{prefix}</a>"
    else:
        collapse_link = "<span class=collapse></span>"
    
    deck_prefix = f"<span class='deck-prefix'>{indent()}{collapse_link}</span>"
    extraclass = "filtered" if node.filtered else ""
    
    buf.append(f"""
    <td class=decktd colspan=5>
        {deck_prefix}
        <a class="deck {extraclass}" href=# onclick="return pycmd('open:{node.deck_id}')">
            {node.name}
        </a>
    </td>
    """)

    def nonzeroColour(cnt, klass):
        if not cnt:
            klass = "zero-count"
        return f'<span class="{klass}">{cnt}</span>'

    buf.append(f"""
    <td align=right>{nonzeroColour(due, "review-count")}</td>
    <td align=right>{nonzeroColour(node.new_count, "new-count")}</td>
    """)
    
    buf.append(f"""
    <td align=center class=opts>
      <a onclick='return pycmd("opts:{node.deck_id}");'>
        <img src='/_anki/imgs/gears.svg' class=gears>
      </a>
    </td>
    </tr>""")
    
    if not node.collapsed:
        for child in node.children:
            buf.append(self._render_deck_node(child, ctx))
            
    return "".join(buf) # Join the list into a single string at the end

# --- ADD THIS ENTIRE NEW FUNCTION ---
def _render_main_page_heatmap(deck_browser):
    """
    Fetches heatmap data and calls the JS render function after the deck browser has loaded.
    """
    conf = config.get_config()
    # Only run if the heatmap is supposed to be visible
    if not conf.get("hideHeatmapOnMain", False):
        try:
            # Get the data and config from heatmap.py
            heatmap_data, heatmap_config = heatmap.get_heatmap_and_config()
            
            # Call the JavaScript render function
            deck_browser.web.eval(f"""
                if (typeof OnigiriHeatmap !== 'undefined' && document.getElementById('onigiri-heatmap-container')) {{
                    OnigiriHeatmap.render('onigiri-heatmap-container', {json.dumps(heatmap_data)}, {json.dumps(heatmap_config)});
                }}
            """)
        except Exception as e:
            print(f"Onigiri heatmap failed to render: {e}")
# ------------------------------------

def apply_patches():
	global _toolbar_patched, _original_MainWebView_eventFilter

	DeckBrowser._render_deck_node = _onigiri_render_deck_node

	if not _toolbar_patched:
		_original_MainWebView_eventFilter = MainWebView.eventFilter
		MainWebView.eventFilter = _new_MainWebView_eventFilter
		gui_hooks.state_did_change.append(_update_toolbar_visibility)
		mw.progress.single_shot(0, lambda: _update_toolbar_visibility(mw.state, "startup"))
		_toolbar_patched = True 
    
	gui_hooks.deck_browser_did_render.append(_render_main_page_heatmap)

	patch_overview()