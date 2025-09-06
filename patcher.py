import os
import re
import json
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
from . import menu_buttons, settings, heatmap

# --- Toolbar Patching ---
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


def _render_background_css(selector, mode, light_color, dark_color, light_image_path, dark_image_path, blur_val, addon_path, style_id, opacity_val=100):
	"""Internal helper to generate a complete <style> block for a given background configuration."""
	blur_px = blur_val * 0.2
	addon_name = os.path.basename(addon_path)

	def get_img_url(image_path):
		if not image_path:
			return None
		# Anki's web server maps /_addons/{addon_package}/user_files to the user_files directory inside the addon.
		# So the URL should be constructed relative to that.
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

	elif mode == "image" or mode == "image_color":
		light_img_url = get_img_url(light_image_path)
		dark_img_url = get_img_url(dark_image_path) if dark_image_path else light_img_url

		# If no image is provided, handle fallbacks
		if not light_img_url:
			if mode == "image_color": # Fallback to solid color for combo mode
				return f"""<style id="{style_id}">
					{selector} {{ background-color: {light_color} !important; }}
					.night-mode {selector} {{ background-color: {dark_color} !important; }}
				</style>"""
			else: # image mode with no image = render nothing
				return ""

		# --- Common setup for modes with images ---
		opacity_float = opacity_val / 100.0 if mode == "image_color" else 1.0
		outset = -40 # in pixels

		# Base CSS for the ::before pseudo-element
		base_before_css = f"""
			content: '';
			position: {'fixed' if 'body' in selector else 'absolute'};
			top: {outset}px; left: {outset}px; right: {outset}px; bottom: {outset}px;
			background-size: cover;
			background-position: center;
			background-repeat: no-repeat;
			filter: blur({blur_px}px);
			opacity: {opacity_float};
			z-index: -1;
		"""

		# Image rules for the pseudo-element
		image_css = f"{selector}::before {{ {base_before_css} background-image: url('{light_img_url}'); }}"
		if dark_img_url and dark_img_url != light_img_url:
			image_css += f"\n.night-mode {selector}::before {{ background-image: url('{dark_img_url}'); }}"
		
		# CSS for the main element itself
		container_css = ""
		if mode == "image_color":
			# The element has a color background, and the pseudo-element image is layered on top.
			container_css += f"""
				{selector} {{ background-color: {light_color} !important; }}
				.night-mode {selector} {{ background-color: {dark_color} !important; }}
			"""
		elif mode == "image":
			# The element must be transparent for the pseudo-element to act as the background.
			if "body" in selector:
				container_css += f"html {{ background: transparent !important; overflow: hidden !important; }} {selector} {{ background: transparent !important; }}"
			else:
				container_css += f"{selector} {{ background: transparent; }}"

		# Common positioning rules to contain the oversized, blurred pseudo-element
		if "container" in selector or ".sidebar-left" in selector:
			container_css += f"{selector} {{ position: relative; z-index: 1; overflow: hidden; }}"
		elif "body" in selector: # for overview/reviewer
			container_css += f"{selector} {{ position: relative; z-index: 1; }}"

		return f"<style id='{style_id}'>{container_css}\n{image_css}</style>"

	return ""

# --- Profile Page Generation ---

_profile_dialog = None

def generate_profile_page_background_css():
    """Generates the CSS for the profile page's body background."""
    mode = mw.col.conf.get("onigiri_profile_page_bg_mode", "color")

    if mode == "gradient":
        light1 = mw.col.conf.get("onigiri_profile_page_bg_light_color1", "#FFFFFF")
        light2 = mw.col.conf.get("onigiri_profile_page_bg_light_color2", "#E0E0E0")
        dark1 = mw.col.conf.get("onigiri_profile_page_bg_dark_color1", "#424242")
        dark2 = mw.col.conf.get("onigiri_profile_page_bg_dark_color2", "#212121")
        return f"""
        <style id="onigiri-profile-page-bg">
            body {{
                background-image: linear-gradient(to bottom, {light1}, {light2});
                background-attachment: fixed;
            }}
            .night-mode body {{
                background-image: linear-gradient(to bottom, {dark1}, {dark2});
            }}
        </style>
        """
    else: # Solid color
        light_color = mw.col.conf.get("onigiri_profile_page_bg_light_color1", "#F5F5F5")
        dark_color = mw.col.conf.get("onigiri_profile_page_bg_dark_color1", "#2c2c2c")
        return f"""
        <style id="onigiri-profile-page-bg">
            body {{ background-color: {light_color} !important; }}
            .night-mode body {{ background-color: {dark_color} !important; }}
        </style>
        """

def _get_profile_header_html(conf, addon_package):
    user_name = conf.get("userName", "USER")
    
    # Profile Picture
    profile_pic_filename = mw.col.conf.get("modern_menu_profile_picture", "")
    if profile_pic_filename:
        pic_url = f"/_addons/{addon_package}/user_files/profile/{profile_pic_filename}"
        pic_html = f'<img src="{pic_url}" class="profile-pic-large">'
    else:
        initial = user_name[0].upper() if user_name else "U"
        pic_html = f'<div class="profile-pic-placeholder-large"><span>{initial}</span></div>'
        
    # Profile Background
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
        bg_style = f"background-color: {light_color};" # JS will swap this for dark mode
    else: # accent
        bg_style = "background-color: var(--accent-color);"

    return f"""
    <div class="profile-header" style="{bg_style}">
        <div class="profile-header-content">
            {pic_html}
            <h1 class="profile-name-large">{user_name}</h1>
        </div>
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
        sidebar_text = "Uses Main Background Settings"
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

    # --- START: Code copied from the main page ---
    # 1. Calculate today's stats from the database. Note: "deck_browser.mw" was changed to just "mw".
    cards_today, time_today_seconds = mw.col.db.first("select count(), sum(time)/1000 from revlog where id > ?", (mw.col.sched.dayCutoff - 86400) * 1000) or (0, 0)
    time_today_seconds = time_today_seconds if time_today_seconds is not None else 0
    cards_today = cards_today if cards_today is not None else 0
    time_today_minutes = time_today_seconds / 60
    seconds_per_card = time_today_seconds / cards_today if cards_today > 0 else 0
    
    # 2. Generate the HTML for the stats grid.
    stats_grid_parts = [] 
    if not conf.get("hideStudiedStat", False):
        stats_grid_parts.append(f"""<div class="stat-card"><h3>Studied</h3><p>{cards_today} cards</p></div>""")
    if not conf.get("hideTimeStat", False):
        stats_grid_parts.append(f"""<div class="stat-card"><h3>Time</h3><p>{time_today_minutes:.1f} min</p></div>""")
    if not conf.get("hidePaceStat", False):
        stats_grid_parts.append(f"""<div class="stat-card"><h3>Pace</h3><p>{seconds_per_card:.1f} s/card</p></div>""")

    stats_grid_html = f"""<div class="stats-grid">{''.join(stats_grid_parts)}</div>""" if stats_grid_parts else ""
    # --- END: Code copied from the main page ---

    heatmap_html = ""
    if show_heatmap:
        heatmap_html = "<div id='onigiri-profile-heatmap-container'></div>"

    # 3. Add the new "stats_grid_html" above the heatmap wrapper.
    # The outer div has been removed as the copied HTML provides its own "stats-grid" container.
    return f"""
    {stats_grid_html}
    <div id="onigiri-profile-heatmap-wrapper" style="margin-top: 20px;">
        {heatmap_html}
    </div>
    """

def _generate_profile_html_body():
    conf = config.get_config()
    addon_package = mw.addonManager.addonFromModule(__name__)

    # --- Page Components ---
    header_html = _get_profile_header_html(conf, addon_package)
    theme_page_content = ""
    stats_page_content = ""

    # Page 1: Theme
    show_light = mw.col.conf.get("onigiri_profile_show_theme_light", True)
    show_dark = mw.col.conf.get("onigiri_profile_show_theme_dark", True)
    show_bgs = mw.col.conf.get("onigiri_profile_show_backgrounds", True)
    if show_light: theme_page_content += _get_theme_colors_html("light", conf)
    if show_dark: theme_page_content += _get_theme_colors_html("dark", conf)
    if show_bgs: theme_page_content += _get_backgrounds_html(addon_package)
    if not theme_page_content:
        theme_page_content = '<p class="empty-section">Theme sections are hidden in settings.</p>'

    # Page 2: Stats
    if mw.col.conf.get("onigiri_profile_show_stats", True):
        stats_page_content = _get_stats_html()
    else:
        stats_page_content = '<p class="empty-section">Stats section is hidden in settings.</p>'

    # Return ONLY the content for the <body> tag
    return f"""
    <div class="profile-container">
        {header_html}
        <nav>
            <button id="nav-theme" class="nav-button">Theme</button>
            <button id="nav-stats" class="nav-button">Stats</button>
        </nav>
        <main>
            <div id="page-theme">
                {theme_page_content}
            </div>
            <div id="page-stats">{stats_page_content}</div>
        </main>
    </div>
    """

class ProfileDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Your Onigiri Profile")
        self.setMinimumSize(500, 600)
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
            f"/_addons/{addon_package}/web/profile_page.js",
            f"/_addons/{addon_package}/web/heatmap.js" # Add heatmap JS
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

# Alias the function for clarity based on user feedback
show_profile_page = open_profile


def on_webview_js_message(handled, message, context):
    """
    Unified handler for messages from all webviews. It checks the 'context'
    to see which screen sent the message and runs the appropriate logic.
    """
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
            # --- FIX: Use the correct snake_case action name ---
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

    elif isinstance(context, Overview):
        cmd = message
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
	ultra_hide = conf.get("ultraHide", False)
    
    
	def new_table(self) -> str:
		counts = list(self.mw.col.sched.counts())
		
		count_data = [
			{"label": tr.actions_new(), "count": counts[0], "class": "new-count-bubble"},
			{"label": tr.scheduling_learning(), "count": counts[1], "class": "learn-count-bubble"},
			{"label": tr.studying_to_review(), "count": counts[2], "class": "review-count-bubble"},
		]

		rows_html = ""
		for item in count_data:
			rows_html += f"""
			<div class="stats-row">
				<span>{item['label']}</span>
				<span class="{item['class']}">{item['count']}</span>
			</div>
			"""
		
		study_now_text = mw.col.conf.get("modern_menu_studyNowText") or tr.studying_study_now()

		bottom_actions_html = ""
		if show_toolbar_replacements:
			bottom_actions_html = """
            <div class="overview-bottom-actions">
                <a href="#" key=O onclick="pycmd('opts'); return false;" class="overview-button">Options</a>
                <a href="#" key=R onclick="pycmd('refresh'); return false;" class="overview-button">Rebuild</a>
                <a href="#" key=E onclick="pycmd('empty'); return false;" class="overview-button">Empty</a>
            </div>
            """

		return f"""
		<div class="overview-container">
			<div class="stats-container">
				{rows_html}
			</div>
			<button id="study" class="add-button-dashed" onclick="pycmd('study'); return false;" autofocus>
				{study_now_text} 
			</button>
			{bottom_actions_html}
		</div>
		"""

	Overview._table = new_table
	
	header_html = ""
	if show_toolbar_replacements and not ultra_hide:
		header_html = """
    <div class="overview-header">
        <a href="#" onclick="pycmd('decks'); return false;" class="overview-button">Decks</a>
        <a href="#" onclick="pycmd('add'); return false;" class="overview-button">Add</a>
        <a href="#" onclick="pycmd('browse'); return false;" class="overview-button">Browse</a>
        <a href="#" onclick="pycmd('stats'); return false;" class="overview-button">Stats</a>
        <a href="#" onclick="pycmd('sync'); return false;" class="overview-button">Sync</a>
    </div>
"""

	Overview._body = f"""
<div class="overview-center-container">
    {header_html}
	<h3 class="overview-title">%(deck)s</h3>
	<div style="display:none">%(shareLink)s</div>
	<div style="display:none">%(desc)s</div>
	%(table)s
</div>
<script>
    document.addEventListener("DOMContentLoaded", function() {{
        const titleEl = document.querySelector('.overview-title');
        if (titleEl) {{
            const fullName = titleEl.textContent.trim();
            const shortName = fullName.split('::').pop().trim();
            titleEl.textContent = shortName;
        }}

        if (typeof anki !== "undefined") {{
            anki.setupOverview();
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
        ultra_hide = conf.get("ultraHide", False)

        header_html = ""
        if show_toolbar_replacements and not ultra_hide:
            header_html = """
            <div class="overview-header">
                <a href="#" onclick="pycmd('decks'); return false;" class="overview-button">Decks</a>
                <a href="#" onclick="pycmd('add'); return false;" class="overview-button">Add</a>
                <a href="#" onclick="pycmd('browse'); return false;" class="overview-button">Browse</a>
                <a href="#" onclick="pycmd('stats'); return false;" class="overview-button">Stats</a>
                <a href="#" onclick="pycmd('sync'); return false;" class="overview-button">Sync</a>
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

    Overview._show_finished_screen = new_show_finished_screen


def generate_deck_browser_backgrounds(addon_path):
    """Generates CSS for the main container background and sidebar."""
    conf = config.get_config() # Get addon config for colors
    
    # --- 1. Get Main Background Settings ---
    main_mode = mw.col.conf.get("modern_menu_background_mode", "color")
    main_image_mode = mw.col.conf.get("modern_menu_background_image_mode", "single")
    main_light_color = mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
    main_dark_color = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
    main_blur = mw.col.conf.get("modern_menu_background_blur", 0)
    main_opacity = mw.col.conf.get("modern_menu_background_opacity", 100)

    if main_image_mode == "separate":
        main_light_img_filename = mw.col.conf.get("modern_menu_background_image_light", "")
        main_dark_img_filename = mw.col.conf.get("modern_menu_background_image_dark", "")
    else: # single mode
        main_light_img_filename = mw.col.conf.get("modern_menu_background_image", "")
        main_dark_img_filename = main_light_img_filename

    # Construct the full path for the background image
    main_light_img = f"user_files/main_bg/{main_light_img_filename}" if main_light_img_filename else ""
    main_dark_img = f"user_files/main_bg/{main_dark_img_filename}" if main_dark_img_filename else ""

    # --- 2. Get Sidebar Background Settings ---
    sidebar_mode = mw.col.conf.get("modern_menu_sidebar_bg_mode", "main")
    
    # --- 3. Generate CSS for the Main Container ---
    # Apply the main background to the parent container to span the whole view.
    main_container_css = _render_background_css(
        ".container.modern-main-menu", main_mode, main_light_color, main_dark_color, 
        main_light_img, main_dark_img, main_blur, addon_path, "modern-menu-main-background-style", main_opacity
    )
    # Ensure .main-content is also transparent so the container background shows through.
    main_container_css += "<style>.main-content { background: transparent !important; }</style>"

    # --- 4. Generate CSS for Sidebar ---
    sidebar_css = ""
    if sidebar_mode == 'custom':
        # Use custom sidebar settings
        side_mode = mw.col.conf.get("modern_menu_sidebar_bg_type", "color")
        side_light_color = mw.col.conf.get("modern_menu_sidebar_bg_color_light", "#FFFFFF")
        side_dark_color = mw.col.conf.get("modern_menu_sidebar_bg_color_dark", "#2C2C2C")
        side_blur = mw.col.conf.get("modern_menu_sidebar_bg_blur", 0)
        side_opacity = mw.col.conf.get("modern_menu_sidebar_bg_opacity", 100)
        side_img_filename = mw.col.conf.get("modern_menu_sidebar_bg_image", "")
        side_img = f"user_files/sidebar_bg/{side_img_filename}" if side_img_filename else ""
        
        sidebar_css = _render_background_css(
            ".sidebar-left", side_mode, side_light_color, side_dark_color,
            side_img, side_img, side_blur, addon_path, "modern-menu-sidebar-background-style", side_opacity
        )

        # --- Generate CSS for the content box ---
        box_enabled = mw.col.conf.get("modern_menu_sidebar_content_box_enabled", False)
        if box_enabled:
            opacity_percent = mw.col.conf.get("modern_menu_sidebar_content_box_opacity", 80)
            opacity_float = opacity_percent / 100.0
            
            # Get the main background colors from the addon config
            light_bg_hex = conf.get("colors", {}).get("light", {}).get("--bg", "#F5F5F5")
            dark_bg_hex = conf.get("colors", {}).get("dark", {}).get("--bg", "#2C2C2C")

            light_rgba = _hex_to_rgba(light_bg_hex, opacity_float)
            dark_rgba = _hex_to_rgba(dark_bg_hex, opacity_float)

            sidebar_css += f"""
            <style id='modern-menu-sidebar-content-box-style'>
                .sidebar-left {{
                    position: relative; /* Needed to contain the absolutely positioned box */
                }}
                .sidebar-content-box {{
                    position: absolute;
                    top: 10px;
                    left: 10px;
                    right: 10px;
                    bottom: 10px;
                    z-index: 0; /* Position it behind content but above sidebar bg */
                    background-color: {light_rgba};
                    border-radius: 12px;
                }}
                .night-mode .sidebar-content-box {{
                    background-color: {dark_rgba};
                }}
                /* Make sure the actual content sits on top of the new box */
                .sidebar-left > *:not(.sidebar-content-box) {{
                    position: relative;
                    z-index: 1;
                }}
            </style>
            """

    else:
        # If using main settings, just make the sidebar transparent.
        # The main background is already on the parent container.
        sidebar_css = "<style id='modern-menu-sidebar-background-style'>.sidebar-left { background: transparent !important; }</style>"
        
    return main_container_css + sidebar_css

def generate_reviewer_background_css(addon_path):
	mode = mw.col.conf.get("modern_menu_background_mode", "color")
	image_mode = mw.col.conf.get("modern_menu_background_image_mode", "single")
	light_color = mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
	dark_color = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
	blur_val = mw.col.conf.get("modern_menu_background_blur", 0)
	opacity_val = mw.col.conf.get("modern_menu_background_opacity", 100)

	if image_mode == "separate":
		light_img_filename = mw.col.conf.get("modern_menu_background_image_light", "")
		dark_img_filename = mw.col.conf.get("modern_menu_background_image_dark", "")
	else: # single mode
		light_img_filename = mw.col.conf.get("modern_menu_background_image", "")
		dark_img_filename = light_img_filename
	
	light_img = f"user_files/main_bg/{light_img_filename}" if light_img_filename else ""
	dark_img = f"user_files/main_bg/{dark_img_filename}" if dark_img_filename else ""
	
	css = _render_background_css("body", mode, light_color, dark_color, light_img, dark_img, blur_val, addon_path, "modern-menu-reviewer-background-style", opacity_val)
	if mode == "image" or mode == "image_color":
		css += "<style>#qa { background-color: transparent !important; }</style>"
	return css

# patcher.py

def generate_overview_background_css(addon_path):
	mode = mw.col.conf.get("modern_menu_background_mode", "color")
	image_mode = mw.col.conf.get("modern_menu_background_image_mode", "single")
	light_color = mw.col.conf.get("modern_menu_bg_color_light", "#F5F5F5")
	dark_color = mw.col.conf.get("modern_menu_bg_color_dark", "#2C2C2C")
	blur_val = mw.col.conf.get("modern_menu_background_blur", 0)
	opacity_val = mw.col.conf.get("modern_menu_background_opacity", 100)
	
	if image_mode == "separate":
		light_img_filename = mw.col.conf.get("modern_menu_background_image_light", "")
		dark_img_filename = mw.col.conf.get("modern_menu_background_image_dark", "")
	else: # single mode
		light_img_filename = mw.col.conf.get("modern_menu_background_image", "")
		dark_img_filename = light_img_filename

	light_img = f"user_files/main_bg/{light_img_filename}" if light_img_filename else ""
	dark_img = f"user_files/main_bg/{dark_img_filename}" if dark_img_filename else ""

	return _render_background_css("body", mode, light_color, dark_color, light_img, dark_img, blur_val, addon_path, "modern-menu-overview-background-style", opacity_val)

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

def generate_profile_bar_fix_css():
    """Generates responsive CSS to ensure the profile picture fits within the profile bar."""
    return """
<style id="onigiri-profile-bar-fix">
.profile-bar {
    display: flex;
    align-items: center;
    gap: 10px; /* Slightly reduced gap */
    padding: 4px; /* Reduced padding for a smaller bar */
    overflow: hidden;
    box-sizing: border-box;
    /* Removed min-height, letting content define the height */
}

.profile-pic, .profile-pic-placeholder {
    width: 16%; /* Slightly smaller percentage width */
    max-width: 50px; /* Reduced max size */
    min-width: 32px; /* Reduced min size, still looks good */
    
    aspect-ratio: 1 / 1;
    height: auto;
    
    border-radius: 50%;
    flex-shrink: 0;
}

.profile-pic {
    object-fit: cover;
}

.profile-pic-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: clamp(14px, 4vw, 20px); /* Adjusted responsive font size */
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
        "options": "td.opts a", "folder": "tr.deck:has(a.collapse) a.deck::before",
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
	if conf.get("hideStudiedToday", False):
		styles.append("#studiedToday { display: none !important; }")
	if conf.get("hideTodaysStats", False):
		styles.append(".stats-grid { display: none !important; }")
	if conf.get("hideProfileBar", False):
		styles.append(".profile-bar { display: none !important; }")
	# -- The old, unreliable CSS rule for the header and bottom bar has been removed. --
	if not styles: return ""
	return f"<style id='modern-menu-conditional-styles'>{' '.join(styles)}</style>"

def generate_dynamic_css(conf):
	colors = conf.get("colors", {})
	light_colors = colors.get("light", {}).copy()
	dark_colors = colors.get("dark", {}).copy()

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

	return f"""
<style id="modern-menu-dynamic-styles">
:root {{ {light_rules} }}
.night-mode {{ {dark_rules} }}
</style>
"""

def prepend_custom_stats(deck_browser, content):
    # FIX: Define the HTML template directly inside the function
    custom_body_template = """
    <div class="container modern-main-menu">
        <div class="sidebar-left skeleton-loading" style="{sidebar_style}">
            {content_box}
            <h2>{welcome_message}</h2>
            {profile_bar}
            <div class="add-button-dashed" id="add-btn" onclick="pycmd('add')">
                <i class="icon"></i>
                <span>Add</span>
            </div>
            <div class="menu-item" id="browser-btn" onclick="pycmd('browse')">
                <i class="icon"></i>
                <span>Browser</span>
            </div>
            <div class="menu-item" id="stats-btn" onclick="pycmd('stats')">
                <i class="icon"></i>
                <span>Stats</span>
            </div>
            <div class="menu-item" id="sync-btn" onclick="pycmd('sync')">
                <i class="icon"></i>
                <span>Sync</span>
            </div>
            <div class="menu-item" id="onigiri-settings-btn" onclick="pycmd('openOnigiriSettings')">
                <i class="icon"></i>
                <span>Settings</span>
            </div>
            
            <details class="menu-group">
                <summary class="menu-item">
                    <i class="icon"></i>
                    <span>More</span>
                </summary>
                <div class="menu-group-items">
                    <div class="menu-item" id="get-shared-btn" onclick="pycmd('shared')">
                        <i class="icon"></i>
                        <span>Get Shared</span>
                    </div>
                    <div class="menu-item" id="create-deck-btn" onclick="pycmd('create')">
                        <i class="icon"></i>
                        <span>Create Deck</span>
                    </div>
                    <div class="menu-item" id="import-file-btn" onclick="pycmd('import')">
                        <i class="icon"></i>
                        <span>Import File</span>
                    </div>
                </div>
            </details>
            
            <h2>DECKS</h2>
            <div id="deck-list-container">
                <table class="deck-table">
                    <tbody>
                        %(tree)s
                    </tbody>
                </table>
            </div>
        </div>
        <div class="resize-handle"></div>
        <div class="main-content">
            <div class="injected-stats-block">
                %(stats)s
            </div>
        </div>
    </div>
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        if (typeof anki !== 'undefined' && anki.setupDeckBrowser) {{
            anki.setupDeckBrowser();
        }}
    }});
    </script>
    """

    conf = config.get_config()
    addon_package = mw.addonManager.addonFromModule(__name__)

    user_name = conf.get("userName", "USER") 
    profile_pic_filename = mw.col.conf.get("modern_menu_profile_picture", "")
    if profile_pic_filename:
        profile_pic_url = f"/_addons/{addon_package}/user_files/profile/{profile_pic_filename}"
        profile_pic_html = f'<img src="{profile_pic_url}" class="profile-pic">'
    else:
        profile_pic_html = f'<div class="profile-pic-placeholder"><span>{user_name[0] if user_name else "U"}</span></div>'

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
    else:
        bg_style_str = "background-color: var(--accent-color);"

    profile_bar_html = f"""
	<div class="profile-bar {bg_class_str}" style="{bg_style_str}" onclick="pycmd('showUserProfile')">
		{profile_pic_html}
		<span class="profile-name">{user_name}</span>
	</div>
	"""

    welcome_message = ""
    if not conf.get("hideWelcomeMessage", False):
        welcome_message = f"WELCOME {user_name.upper()}!"

    content_box_html = ""
    sidebar_mode = mw.col.conf.get("modern_menu_sidebar_bg_mode", "main")
    box_enabled = mw.col.conf.get("modern_menu_sidebar_content_box_enabled", False)
    if sidebar_mode == 'custom' and box_enabled:
        content_box_html = '<div class="sidebar-content-box"></div>'

    saved_width = mw.col.conf.get("modern_menu_sidebar_width", 260)
    sidebar_style = f"width: {saved_width}px;"
    
    DeckBrowser._body = custom_body_template.format(
        content_box=content_box_html,
        welcome_message=welcome_message,
        sidebar_style=sidebar_style,
        profile_bar=profile_bar_html
    )

    # --- SKELETON LOADER CHANGE START ---
    heatmap_html = ""
    if not conf.get("hideHeatmapOnMain", False):
        skeleton_cells = "".join(["<div class='skeleton-cell'></div>" for _ in range(371)])
        
        heatmap_html = f"""
        <div id='onigiri-heatmap-container'>
            <div class="heatmap-header-skeleton">
                <div class="header-left-skeleton">
                    <div class="skeleton-title"></div>
                    <div class="skeleton-nav"></div>
                </div>
                <div class="header-right-skeleton">
                    <div class="skeleton-streak"></div>
                    <div class="skeleton-filters"></div>
                </div>
            </div>
            <div class="heatmap-grid-skeleton">
                {skeleton_cells}
            </div>
        </div>
        """
    # --- SKELETON LOADER CHANGE END ---

    # --- Stats Grid ---
    cards_today, time_today_seconds = deck_browser.mw.col.db.first("select count(), sum(time)/1000 from revlog where id > ?", (deck_browser.mw.col.sched.dayCutoff - 86400) * 1000) or (0, 0)
    time_today_seconds = time_today_seconds if time_today_seconds is not None else 0
    cards_today = cards_today if cards_today is not None else 0
    time_today_minutes = time_today_seconds / 60
    seconds_per_card = time_today_seconds / cards_today if cards_today > 0 else 0

    # --- Retention Calculation ---
    total_reviews, correct_reviews = deck_browser.mw.col.db.first(
        "select count(*), sum(case when ease > 1 then 1 else 0 end) from revlog where type = 1 and id > ?",
        (deck_browser.mw.col.sched.dayCutoff - 86400) * 1000
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

    stats_title = mw.col.conf.get("modern_menu_statsTitle", config.DEFAULTS["statsTitle"])
    title_html = f'<h1 style="text-align: left;">{stats_title}</h1>' if stats_title else ""
    stats_grid_parts = []
    if not conf.get("hideStudiedStat", False):
        stats_grid_parts.append(f"""<div class="stat-card"><h3>Studied</h3><p>{cards_today} cards</p></div>""")
    if not conf.get("hideTimeStat", False):
        stats_grid_parts.append(f"""<div class="stat-card"><h3>Time</h3><p>{time_today_minutes:.1f} min</p></div>""")
    if not conf.get("hidePaceStat", False):
        stats_grid_parts.append(f"""<div class="stat-card"><h3>Pace</h3><p>{seconds_per_card:.1f} s/card</p></div>""")
    if not conf.get("hideRetentionStat", False):
        stats_grid_parts.append(retention_stat_html)

    # Only render the grid if there's at least one card to show
    stats_grid_html = f"""<div class="stats-grid">{''.join(stats_grid_parts)}</div>""" if stats_grid_parts else ""
    # Combine stats and heatmap
    my_stats_html = title_html + stats_grid_html + heatmap_html

    content.stats = my_stats_html + content.stats


def _new_MainWebView_eventFilter(self: MainWebView, obj: QObject, evt: QEvent) -> bool:
	"""Prevents Anki's default hover-to-show-toolbar behavior."""
	conf = config.get_config()
	should_hide_setting = conf.get("hideNativeHeaderAndBottomBar", False)
	ultra_hide = conf.get("ultraHide", False)

	screens_to_interfere = ["deckBrowser", "overview"]
	if ultra_hide:
		screens_to_interfere.append("review")
	
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
    ultra_hide = conf.get("ultraHide", False)

    if not should_hide_setting:
        # If the feature is disabled in settings, ensure toolbars are always visible
        mw.toolbar.web.setVisible(True)
        mw.bottomWeb.setVisible(True)
        return

    # Special case for ultra hide in reviewer
    if ultra_hide and new_state == "review":
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
        # Show toolbars on ALL other screens (this will now exclude the 'review' case when ultra_hide is on)
        mw.toolbar.web.setVisible(True)
        mw.bottomWeb.setVisible(True)

def _onigiri_render_deck_node(self, node, ctx) -> str:
    """
    A patched version of DeckBrowser._render_deck_node that creates the
    HTML structure Onigiri's CSS and JS expect (e.g., td.collapse-cell).
    """
    if node.collapsed:
        prefix = "+"
    else:
        prefix = "-"

    due = node.review_count + node.learn_count

    def indent():
        return "&nbsp;" * 6 * (node.level - 1)

    klass = "deck current" if node.deck_id == ctx.current_deck_id else "deck"

    # --- MODIFICATION START ---
    # Add a specific class for folders (has children) vs decks (no children)
    deck_type_class = "is-folder" if node.children else "is-deck"
    # Begin row
    buf = f"<tr class='{klass} {deck_type_class}' id='{node.deck_id}'>"
    # --- MODIFICATION END ---
    
    # Begin row
    

    # --- Onigiri Fix Start ---
    # Group indentation and collapse icon together in a span
    if node.children:
        collapse_link = f"<a class=collapse href=# onclick='return pycmd(\"collapse:{node.deck_id}\")'>{prefix}</a>"
    else:
        collapse_link = "<span class=collapse></span>"
    
    deck_prefix = f"<span class='deck-prefix'>{indent()}{collapse_link}</span>"

    extraclass = "filtered" if node.filtered else ""
    buf += f"""
    <td class=decktd colspan=5>
        {deck_prefix}
        <a class="deck {extraclass}" href=# onclick="return pycmd('open:{node.deck_id}')">
            {node.name}
        </a>
    </td>
    """
    # --- Onigiri Fix End ---

    # Due counts (unchanged from original)
    def nonzeroColour(cnt, klass):
        if not cnt:
            klass = "zero-count"
        return f'<span class="{klass}">{cnt}</span>'

    buf += f"""
    <td align=right>{nonzeroColour(due, "review-count")}</td>
    <td align=right>{nonzeroColour(node.new_count, "new-count")}</td>
    """

    # Options gear (unchanged from original)
    buf += f"""
    <td align=center class=opts>
      <a onclick='return pycmd("opts:{node.deck_id}");'>
        <img src='/_anki/imgs/gears.svg' class=gears>
      </a>
    </td>
    </tr>"""
    
    # Render children if not collapsed
    if not node.collapsed:
        for child in node.children:
            buf += self._render_deck_node(child, ctx) # type: ignore
            
    return buf

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

	# This new line is the crucial part of the fix.
	# It replaces Anki's deck row renderer with our custom one.
	DeckBrowser._render_deck_node = _onigiri_render_deck_node

	if not _toolbar_patched:
		# Patch event filter to prevent hover-to-show on specific screens
		_original_MainWebView_eventFilter = MainWebView.eventFilter
		MainWebView.eventFilter = _new_MainWebView_eventFilter
		
		# Use the state_did_change hook for robust visibility control
		gui_hooks.state_did_change.append(_update_toolbar_visibility)
		
		# Run once on startup to set the initial state correctly
		mw.progress.single_shot(0, lambda: _update_toolbar_visibility(mw.state, "startup"))

		_toolbar_patched = True 
    
    # --- ADD THIS LINE ---
	gui_hooks.deck_browser_did_render.append(_render_main_page_heatmap)
	# ---------------------
	
	patch_overview()
