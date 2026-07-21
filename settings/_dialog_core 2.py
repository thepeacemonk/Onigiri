# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._icon_picker import *
from ._widgets import *
from ._layout_base import *
from ._layout_main import *
from ._layout_sidebar import *
from ._widgets import _TooltipSuppressor



class DialogCoreMixin:
    def __init__(self, parent=None, addon_path=None, initial_page_index=0):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Disable native OS tooltips for the whole settings UI while it is open.
        self._tooltip_suppressor = _TooltipSuppressor(self)
        if mw is not None and mw.app is not None:
            mw.app.installEventFilter(self._tooltip_suppressor)
        self.addon_path = addon_path
        # <<< IMPORT/EXPORT THEMES >>>
        self.user_themes_path = os.path.join(self.addon_path, "user_files", "user_themes")
        os.makedirs(self.user_themes_path, exist_ok=True)
        self.block_card_click = False
        self._pending_theme_data = None
        self._theme_prepare_save_in_progress = False
        self._theme_preparing_overlay = None
        self._theme_selected_toast = None
        self.setWindowTitle("Onigiri Settings")
        
        # --- Screen Proportional Sizing ---
        screen = mw.app.primaryScreen()
        if screen:
            available_geometry = screen.availableGeometry()
            screen_width = available_geometry.width()
            screen_height = available_geometry.height()
            
            min_w = min(max(980, int(screen_width * 0.58)), screen_width)
            min_h = min(max(480, int(screen_height * 0.46)), screen_height)
            default_w = min(max(1240, int(screen_width * 0.74)), screen_width)
            default_h = min(max(780, int(screen_height * 0.78)), screen_height)
            
            self.setMinimumWidth(min_w)
            self.setMinimumHeight(min_h)
            self.resize(default_w, default_h)
            
            # Set maximum height to avoid going off-screen
            self.setMaximumHeight(screen_height)
        else:
            # Fallback if screen detection fails
            self.setMinimumWidth(980)
            self.setMinimumHeight(480)
            self.resize(1240, 780)
        
        self.current_config = config.get_config()
        
        # [NEW] Sync profile language code with config language name
        current_lang_name = self.current_config.get("language", "English (Default)")
        lang_code = LANGUAGES.get(current_lang_name, "en")
        if mw.pm.profile.get('onigiri_language') != lang_code:
            mw.pm.profile['onigiri_language'] = lang_code

        # --- RESTORE WINDOW SIZE ---
        window_settings = self.current_config.get("window_settings", {})
        if window_settings:
            w = window_settings.get("width")
            h = window_settings.get("height")
            if w and h:
                # Basic validation
                w = max(self.minimumWidth(), w)
                h = max(self.minimumHeight(), h)
                if screen:
                     w = min(w, screen.availableGeometry().width())
                     h = min(h, screen.availableGeometry().height())
                self.resize(w, h)
        # ---------------------------
        self.custom_goal_cooldown_label = None

        achievements_conf = self.current_config.get("achievements")
        if not isinstance(achievements_conf, dict):
            achievements_conf = copy.deepcopy(config.DEFAULTS["achievements"])
            self.current_config["achievements"] = achievements_conf
        else:
            defaults = config.DEFAULTS["achievements"]
            for key, value in defaults.items():
                if isinstance(value, dict):
                    achievements_conf.setdefault(key, copy.deepcopy(value))
                else:
                    achievements_conf.setdefault(key, value)

        custom_goal_defaults = config.DEFAULTS["achievements"].get("custom_goals", {})
        custom_goals_conf = achievements_conf.setdefault("custom_goals", copy.deepcopy(custom_goal_defaults))
        custom_goals_conf.setdefault("last_modified_at", custom_goal_defaults.get("last_modified_at"))
        for goal_key, goal_defaults in custom_goal_defaults.items():
            if not isinstance(goal_defaults, dict):
                continue
            goal_conf = custom_goals_conf.setdefault(goal_key, {})
            for sub_key, default_value in goal_defaults.items():
                if isinstance(default_value, dict):
                    goal_conf.setdefault(sub_key, copy.deepcopy(default_value))
                else:
                    goal_conf.setdefault(sub_key, default_value)

        self.achievements_config = achievements_conf
        mochi_defaults = config.DEFAULTS.get("mochi_messages", {})
        self.mochi_messages_config = self.current_config.setdefault("mochi_messages", copy.deepcopy(mochi_defaults))
        for key, value in mochi_defaults.items():
            if key not in self.mochi_messages_config:
                self.mochi_messages_config[key] = copy.deepcopy(value)
        light_bg = mw.col.conf.get("modern_menu_bg_color_light")
        dark_bg = mw.col.conf.get("modern_menu_bg_color_dark")

        # --- ADD THIS LINE ---
        self.reviewer_bottom_bar_mode = self.current_config.get("onigiri_reviewer_bottom_bar_bg_mode", "match_reviewer_bg")
        if self.reviewer_bottom_bar_mode == "image":
            self.reviewer_bottom_bar_mode = "image_color"
        # --- END OF ADDITION ---

        self.color_widgets = {"light": {}, "dark": {}}
        self._color_sync_groups = {}
        self._color_sync_guard = None
        self.icon_assignment_widgets = []
        self.icon_size_widgets = {}
        self.galleries = {}
        self.tabs_loaded = {}
        self._page_transition_animation = None
        self._page_nav_sections = {}
        self._building_page_name = None
        self._current_page_name = None
        self._navigating_page = False
        self._font_family_cache = {}
        self._gallery_population_timers = {}
        self._pending_stylesheet_timer = QTimer(self)
        self._pending_stylesheet_timer.setSingleShot(True)
        self._pending_stylesheet_timer.timeout.connect(self.apply_stylesheet)

        conf = config.get_config()
        if theme_manager.night_mode:
            self.accent_color = conf.get("colors", {}).get("dark", {}).get("--accent-color", DEFAULTS["colors"]["dark"]["--accent-color"])
        else:
            self.accent_color = conf.get("colors", {}).get("light", {}).get("--accent-color", DEFAULTS["colors"]["light"]["--accent-color"])

        # ankiweb_sync toggle — must be after self.accent_color is set
        self.ankiweb_sync_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.ankiweb_sync_toggle.setChecked(
            bool(self.current_config.get("ankiweb_sync_enabled", True))
        )

        custom_goals_conf = self.achievements_config.get("custom_goals", {})
        daily_conf = custom_goals_conf.get("daily", {})
        weekly_conf = custom_goals_conf.get("weekly", {})

        self.daily_goal_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.daily_goal_toggle.setChecked(bool(daily_conf.get("enabled", False)))

        self.daily_goal_spinbox = QSpinBox()
        self.daily_goal_spinbox.setMinimum(0)
        self.daily_goal_spinbox.setMaximum(5000)
        self.daily_goal_spinbox.setSingleStep(10)
        self.daily_goal_spinbox.setSuffix(" cards")
        self.daily_goal_spinbox.setValue(int(daily_conf.get("target", 100) or 0))
        self.daily_goal_spinbox.setToolTip("Cards to review each day to hit your personal goal.")
        self.daily_goal_spinbox.setEnabled(self.daily_goal_toggle.isChecked())
        self.daily_goal_toggle.toggled.connect(self.daily_goal_spinbox.setEnabled)

        self.weekly_goal_toggle = AnimatedToggleButton(accent_color=self.accent_color)
        self.weekly_goal_toggle.setChecked(bool(weekly_conf.get("enabled", False)))

        self.weekly_goal_spinbox = QSpinBox()
        self.weekly_goal_spinbox.setMinimum(0)
        self.weekly_goal_spinbox.setMaximum(50000)
        self.weekly_goal_spinbox.setSingleStep(50)
        self.weekly_goal_spinbox.setSuffix(" cards")
        self.weekly_goal_spinbox.setValue(int(weekly_conf.get("target", 700) or 0))
        self.weekly_goal_spinbox.setToolTip("Cards to review across the current calendar week.")
        self.weekly_goal_spinbox.setEnabled(self.weekly_goal_toggle.isChecked())
        self.weekly_goal_toggle.toggled.connect(self.weekly_goal_spinbox.setEnabled)

        # Initialize widgets that have been moved so they are always available for saving
        self.hide_native_header_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_native_header_checkbox.setChecked(self.current_config.get("hideNativeHeaderAndBottomBar", True))
        
        self.max_hide_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.max_hide_checkbox.setChecked(self.current_config.get("maxHide", False))
        self.max_hide_checkbox.setToolTip("Hides the bottom toolbar on the reviewer screen for the most immersive experience.")

        self.flow_mode_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.flow_mode_checkbox.setChecked(self.current_config.get("flowMode", False))
        self.flow_mode_checkbox.setToolTip("Enables 'Flow Mode' which hides the bottom toolbar on the reviewer screen until you hover over it.")

        self.full_hide_mode_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.full_hide_mode_checkbox.setChecked(self.current_config.get("fullHideMode", False))
        self.full_hide_mode_checkbox.setToolTip("Hides the top menu bar (File, Edit, View, Tools, Help) on Windows and Linux for the most immersive experience.")

        self.hide_synapsepro_sidebar_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_synapsepro_sidebar_checkbox.setChecked(self.current_config.get("hideSynapseProSidebar", False))
        self.hide_synapsepro_sidebar_checkbox.setToolTip("Hides the SynapsePro launcher sidebar when SynapsePro is installed.")

        self.hide_native_header_checkbox.toggled.connect(self._on_hide_toggled)
        self.flow_mode_checkbox.toggled.connect(self._on_flow_toggled)
        self.max_hide_checkbox.toggled.connect(self._on_max_hide_toggled)
        self.full_hide_mode_checkbox.toggled.connect(self._on_full_hide_toggled)

        # Backing store for the Stats Title widget's phrase. It has no row on the
        # Main Menu page any more — the widget's "Edit Title" dialog writes here,
        # and _save_main_menu_settings persists it with everything else.
        # None == never set (fresh install) -> prefill welcome default; "" == user cleared it -> keep blank.
        _saved_stats_title = mw.col.conf.get("modern_menu_statsTitle")
        self.stats_title_input = QLineEdit(DEFAULTS["statsTitle"] if _saved_stats_title is None else _saved_stats_title)
        self.selected_stats_title_font_key = mw.col.conf.get("modern_menu_statsTitleFont", "sync") or "sync"



        self.hide_deck_counts_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_deck_counts_checkbox.setChecked(self.current_config.get("hideDeckCounts", True))

        self.hide_all_deck_counts_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_all_deck_counts_checkbox.setChecked(self.current_config.get("hideAllDeckCounts", False))

        self.sidebar_position_group = QButtonGroup(self)
        self.sidebar_position_left_radio = AnimatedRadioButton(
            tr("sidebar_position_left", "Sidebar on the left"),
            accent_color=self.accent_color,
        )
        self.sidebar_position_right_radio = AnimatedRadioButton(
            tr("sidebar_position_right", "Sidebar on the right"),
            accent_color=self.accent_color,
        )
        self.sidebar_position_center_radio = AnimatedRadioButton(
            tr("sidebar_position_center", "Sidebar centered (Top Sidebar and Widgets)"),
            accent_color=self.accent_color,
        )
        for radio, position in (
            (self.sidebar_position_left_radio, "left"),
            (self.sidebar_position_right_radio, "right"),
            (self.sidebar_position_center_radio, "center"),
        ):
            radio.setProperty("sidebar_position", position)
            self.sidebar_position_group.addButton(radio)
        sidebar_position = mw.col.conf.get(
            "modern_menu_sidebar_position",
            self.current_config.get("sidebarPosition", "left"),
        )
        if sidebar_position not in {"left", "right", "center"}:
            sidebar_position = "left"
        {
            "left": self.sidebar_position_left_radio,
            "right": self.sidebar_position_right_radio,
            "center": self.sidebar_position_center_radio,
        }[sidebar_position].setChecked(True)

        self.study_now_input = QLineEdit(mw.col.conf.get("modern_menu_studyNowText", DEFAULTS["studyNowText"]))
        self.show_congrats_profile_bar_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.show_congrats_profile_bar_checkbox.setChecked(self.current_config.get("showCongratsProfileBar", True))
        self.show_overview_profile_bar_checkbox = AnimatedToggleButton(accent_color=self.accent_color)
        self.show_overview_profile_bar_checkbox.setChecked(self.current_config.get("showOverviewProfileBar", True))
        self.congrats_message_input = QLineEdit(self.current_config.get("congratsMessage", DEFAULTS["congratsMessage"]))
        self.congrats_message_input.setCursorPosition(0)

        self.action_button_icon_widgets = []
        self.retention_star_widget = None

        main_layout = QVBoxLayout(self); main_layout.setContentsMargins(0, 0, 0, 0); main_layout.setSpacing(0)
        
        content_area_layout = QHBoxLayout()
        content_area_layout.setSpacing(0)
        content_area_layout.setContentsMargins(0, 0, 0, 0)
        
        # Sidebar wrapper — flush left, full height
        sidebar_wrapper = QWidget()
        sidebar_wrapper.setObjectName("settingsSidebarWrapper")
        sidebar_wrapper.setMinimumWidth(144)
        sidebar_wrapper.setMaximumWidth(240)
        sidebar_wrapper_layout = QVBoxLayout(sidebar_wrapper)
        sidebar_wrapper_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_wrapper_layout.setSpacing(0)

        # Scroll area for sidebar nav buttons
        self.sidebar_scroll_area = RoundedScrollArea(radius=0)
        self.sidebar_scroll_area.setObjectName("sidebarNavScrollArea")
        self.sidebar_scroll_area.setWidgetResizable(True)
        self.sidebar_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.sidebar_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sidebar_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sidebar_scroll_area.setMinimumWidth(144)
        self.sidebar_scroll_area.setMaximumWidth(240)
        self.sidebar_scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.sidebar_scroll_area.setStyleSheet("QScrollArea#sidebarNavScrollArea { background: transparent; border: none; }")

        sidebar_widget = QWidget()
        sidebar_widget.setObjectName("sidebarContainer")
        sidebar_widget.setMinimumWidth(144)
        
        self.sidebar_scroll_area.setWidget(sidebar_widget)
        sidebar_wrapper_layout.addWidget(self.sidebar_scroll_area)

        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(12, 4, 12, 12)
        # (top kept minimal so the search bar sits close to the first nav section)
        sidebar_layout.setSpacing(2)
        sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentStack")
        self.content_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.content_stack.setMinimumWidth(0)

        content_shell = QWidget()
        content_shell.setObjectName("settingsContentShell")
        content_shell.setMinimumWidth(0)
        content_shell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_shell_layout = QVBoxLayout(content_shell)
        content_shell_layout.setContentsMargins(20, 18, 20, 0)
        content_shell_layout.setSpacing(10)

        header_row = QWidget()
        header_row.setObjectName("settingsPageHeader")
        header_row.setMinimumHeight(44)
        self.settings_page_header = header_row
        header_layout = QHBoxLayout(header_row)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.page_title_label = QLabel(tr("settings_title"))
        self.page_title_label.setObjectName("settingsPageTitle")
        self.page_title_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(self.page_title_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self.page_nav_bar = QWidget()
        self.page_nav_bar.setObjectName("pageNavBar")
        self.page_nav_bar.setFixedHeight(32)
        self.page_nav_bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.page_nav_layout = FlowLayout(self.page_nav_bar, margin=0, spacing=6)
        self.page_nav_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(self.page_nav_bar, 1, Qt.AlignmentFlag.AlignVCenter)

        self.page_header_actions = QWidget()
        self.page_header_actions.setObjectName("pageHeaderActions")
        self.page_header_actions_layout = QHBoxLayout(self.page_header_actions)
        self.page_header_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.page_header_actions_layout.setSpacing(0)
        self.page_header_actions.setVisible(False)
        header_layout.addWidget(self.page_header_actions, 0, Qt.AlignmentFlag.AlignVCenter)
        content_shell_layout.addWidget(header_row)
        content_shell_layout.addWidget(self.content_stack)

        content_area_layout.addWidget(sidebar_wrapper)
        content_shell_outer = QWidget()
        content_shell_outer.setObjectName("settingsContentOuter")
        content_shell_outer.setMinimumWidth(0)
        content_shell_outer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_shell_outer_layout = QVBoxLayout(content_shell_outer)
        content_shell_outer_layout.setContentsMargins(8, 10, 8, 0)
        content_shell_outer_layout.setSpacing(0)
        content_shell_outer_layout.addWidget(content_shell)
        content_area_layout.addWidget(content_shell_outer)

        self.pages = {
            "Search": self.create_search_page,
            "Profile": self.create_profile_tab,
            "Modes": self.create_hide_modes_page,
            "Languages": self.create_languages_page,
            "Fonts": self.create_fonts_page,
            "Themes": self.create_themes_page,
            "Main menu": self.create_main_menu_page,
            "Sidebar": self.create_sidebar_page,
            "Overviewer": self.create_overviews_page,
            "Reviewer": self.create_reviewer_tab,
            "Prep Station": self.create_prep_station_page,
            "Hashi Notes": self.create_hashi_notes_page,
            "Pomodoro": self.create_pomodoro_page,
            "Gallery": self.create_gallery_page,
            "Sync": self.create_sync_page,
        }
        self.page_order = list(self.pages.keys())

        for name in self.page_order:
            self.content_stack.addWidget(QWidget())

        user_name = self.current_config.get("userName", DEFAULTS["userName"])
        is_dark = theme_manager.night_mode
        pic_dynamic = bool(mw.col.conf.get("modern_menu_profile_picture_dynamic_mode", True))
        pic_filename = (
            mw.col.conf.get(f"modern_menu_profile_picture_{'dark' if is_dark else 'light'}", "")
            if pic_dynamic else ""
        ) or mw.col.conf.get("modern_menu_profile_picture", "")
        pic_path = os.path.join(self.addon_path, "user_files", "profile", pic_filename) if pic_filename else ""
        bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "image")
        bg_color = mw.col.conf.get(f"modern_menu_profile_bg_color_{'dark' if is_dark else 'light'}", "#555" if is_dark else "#EEE")
        bg_image_filename = mw.col.conf.get("modern_menu_profile_bg_image", "")
        bg_image_path = os.path.join(self.addon_path, "user_files", "profile_bg", bg_image_filename) if bg_image_filename else ""
        bg_config = {
            'color': bg_color,
            'image': bg_image_path,
            'blur': mw.col.conf.get("modern_menu_profile_bg_blur", 0),
            'opacity': mw.col.conf.get("modern_menu_profile_bg_opacity", 50),
        }
        pic_config = {
            'mode': mw.col.conf.get("modern_menu_profile_picture_mode", "image"),
            'color': mw.col.conf.get(f"modern_menu_profile_picture_color_{'dark' if is_dark else 'light'}", "#B8BDC3" if is_dark else "#8CACB4"),
            'blur': mw.col.conf.get("modern_menu_profile_picture_blur", 0),
            'opacity': mw.col.conf.get("modern_menu_profile_picture_opacity", 100),
        }
        


        # Profile bar removed from the sidebar — Profile is now a normal nav item
        # under "General" (see _add_sidebar_nav_section below).

        self.sidebar_search_button = QPushButton(tr("search"))
        self.sidebar_search_button.setCheckable(True)
        self.sidebar_search_button.setObjectName("sidebarSearchButton")
        self.sidebar_search_button.setMinimumWidth(120)
        self.sidebar_search_button.setMaximumWidth(216)
        self.sidebar_search_button.setFixedHeight(38)
        self.sidebar_search_button.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._decorate_button(self.sidebar_search_button, "search.svg", 16)
        self.sidebar_search_button.clicked.connect(lambda: self.navigate_to_page("Search"))
        self.sidebar_search_button.toggled.connect(lambda checked: self.navigate_to_page("Search") if checked else None)

        # Pinned top — search stays above the scroll area so it is always visible
        # and its width is unaffected by the scrollbar.
        sidebar_top = QWidget()
        sidebar_top.setObjectName("sidebarPinnedTop")
        sidebar_top.setMinimumWidth(144)
        sidebar_top.setMaximumWidth(240)
        # Fixed vertical policy so this block never stretches taller than its
        # content.
        sidebar_top.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sidebar_top_layout = QVBoxLayout(sidebar_top)
        sidebar_top_layout.setContentsMargins(12, 8, 12, 0)
        sidebar_top_layout.setSpacing(0)
        sidebar_top_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        sidebar_top_layout.addWidget(self.sidebar_search_button)
        sidebar_wrapper_layout.insertWidget(0, sidebar_top)

        self.sidebar_buttons = {}
        self.sidebar_button_group = QButtonGroup()
        self.sidebar_button_group.setExclusive(True)
        self.sidebar_buttons["Search"] = self.sidebar_search_button
        self.sidebar_button_group.addButton(self.sidebar_search_button)

        self._add_sidebar_nav_section(sidebar_layout, tr("general"), [
            (tr("profile"), "Profile", "person.svg"),
            (tr("modes"), "Modes", "modes.svg"),
            (tr("languages"), "Languages", "languages.svg"),
            (tr("fonts"), "Fonts", "text.svg"),
            (tr("themes"), "Themes", "themes.svg"),
            (tr("gallery"), "Gallery", "folder.svg"),
            (tr("sync_button"), "Sync", "sync.svg"),
        ])

        self._add_sidebar_nav_section(sidebar_layout, tr("menu"), [
            (tr("main_menu"), "Main menu", "main_menu.svg"),
            (tr("sidebar"), "Sidebar", "sidebar.svg"),
        ])

        self._add_sidebar_nav_section(sidebar_layout, tr("study_pages"), [
            (tr("overviewer"), "Overviewer", "stats.svg"),
            (tr("reviewer"), "Reviewer", "add-card.svg"),
        ])

        self._add_sidebar_nav_section(sidebar_layout, "Study Tools", [
            ("Prep Station", "Prep Station", "stats.svg"),
            ("Hashi Notes", "Hashi Notes", "hashi_notes.svg"),
            ("Pomodoro", "Pomodoro", "pomodoro.svg"),
        ])

        sidebar_layout.addStretch()


        self.donate_button = QPushButton(tr("donate"))
        self.donate_button.setObjectName("sidebarActionButton")
        self.donate_button.setFixedHeight(38)
        self._decorate_button(self.donate_button, "star_outline.svg")
        self.donate_button.clicked.connect(self._open_donate_link)
        self.report_bugs_button = QPushButton(tr("report_bugs"))
        self.report_bugs_button.setObjectName("sidebarActionButton")
        self.report_bugs_button.setFixedHeight(38)
        self._decorate_button(self.report_bugs_button, "info-circle.svg")
        self.report_bugs_button.clicked.connect(self._open_bugs_link)

        self.save_button = QPushButton(tr("save"))
        self.save_button.setObjectName("saveSidebarButton")
        self.save_button.setFixedHeight(38)
        self.save_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._decorate_button(self.save_button, "check.svg")
        self.save_button.setProperty("onigiri_icon_role", "save")
        self.save_button.clicked.connect(self.save_settings)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("cancelSidebarButton")
        self.cancel_button.setFixedHeight(38)
        self.cancel_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(self.reject)
        
        # Bottom actions container — save, donate, bugs.
        # Pinned outside the scroll area so it stays visible at any window height.
        bottom_widget = QWidget()
        bottom_widget.setObjectName("sidebarActionsContainer")
        bottom_widget.setMinimumWidth(120)
        bottom_widget.setMaximumWidth(240)

        sidebar_button_layout = QVBoxLayout(bottom_widget)
        sidebar_button_layout.setSpacing(0)
        sidebar_button_layout.setContentsMargins(12, 8, 12, 12)

        sidebar_button_layout.addWidget(self.donate_button)
        sidebar_button_layout.addSpacing(14)
        sidebar_button_layout.addWidget(self.report_bugs_button)
        sidebar_button_layout.addSpacing(14)

        save_cancel_layout = QHBoxLayout()
        save_cancel_layout.setSpacing(8)
        save_cancel_layout.setContentsMargins(0, 0, 0, 0)
        save_cancel_layout.addWidget(self.save_button)
        save_cancel_layout.addWidget(self.cancel_button)
        
        sidebar_button_layout.addLayout(save_cancel_layout)

        # Pin the action buttons below the scroll area so they are always
        # visible regardless of the window height (they no longer scroll away).
        sidebar_wrapper_layout.addWidget(bottom_widget)

        main_layout.addLayout(content_area_layout)
        self.apply_stylesheet()

        initial_page_name = "Search"
        if isinstance(initial_page_index, str) and initial_page_index in self.page_order:
            initial_page_name = initial_page_index
        elif isinstance(initial_page_index, int) and 0 <= initial_page_index < len(self.page_order):
            initial_page_name = self.page_order[initial_page_index]
        self.navigate_to_page(initial_page_name)

    def closeEvent(self, event):
        # Stop suppressing native tooltips once the settings UI is gone.
        suppressor = getattr(self, "_tooltip_suppressor", None)
        if suppressor is not None and mw is not None and mw.app is not None:
            try:
                mw.app.removeEventFilter(suppressor)
            except RuntimeError:
                pass
        # --- SAVE WINDOW SIZE ---
        try:
            if not getattr(self, "_is_saving", False):
                persisted_config = config.get_config()
                should_write = False
                should_refresh = False

                if not self.isMaximized() and not self.isFullScreen():
                    persisted_config["window_settings"] = {
                        "width": self.width(),
                        "height": self.height(),
                    }
                    should_write = True

                page_indices = {name: i for i, name in enumerate(getattr(self, "page_order", []))}
                if self.tabs_loaded.get(page_indices.get("Languages")):
                    pending_language = self.current_config.get(
                        "language",
                        persisted_config.get("language", "English (Default)"),
                    )
                    if persisted_config.get("language") != pending_language:
                        persisted_config["language"] = pending_language
                        should_write = True
                        should_refresh = True
                    self._apply_language_setting(pending_language)

                if should_write:
                    config.write_config(persisted_config)
                if should_refresh:
                    self._refresh_anki_after_settings_save()
        except Exception as e:
            print(f"Error saving window settings: {e}")
        # ------------------------

        for timer in getattr(self, "_gallery_population_timers", {}).values():
            timer.stop()
            timer.deleteLater()
        self._gallery_population_timers = {}

        for gallery in self.galleries.values():
            if worker := gallery.get('worker'):
                worker.cancel()
            if thread := gallery.get('thread'):
                try:
                    if thread.isRunning():
                        thread.quit()
                        thread.wait(20)
                except RuntimeError:
                    pass
        super().closeEvent(event)

    def navigate_to_page(self, page_name):
        if not page_name: 
            return
        if getattr(self, "_navigating_page", False):
            return

        if page_name not in self.page_order:
            return

        stack_index = self.page_order.index(page_name)
        if self._current_page_name == page_name and self.content_stack.currentIndex() == stack_index:
            return

        self._navigating_page = True
        try:
            if page_name in self.sidebar_buttons:
                button = self.sidebar_buttons[page_name]
                if not button.isChecked():
                    blocker = QSignalBlocker(button)
                    button.setChecked(True)
                    del blocker
            else:
                if btn := self.sidebar_button_group.checkedButton():
                    blocker = QSignalBlocker(btn)
                    btn.setChecked(False)
                    del blocker

            if hasattr(self, "page_title_label"):
                # Page titles removed as redundant — the header keeps only the
                # section nav buttons. Pages with their own built-in header
                # (Sync/Fonts/Gallery) hide the shared header entirely.
                has_custom_header = page_name in {"Sync", "Fonts", "Gallery"}
                self.page_title_label.setVisible(False)
                if hasattr(self, "settings_page_header"):
                    self.settings_page_header.setVisible(not has_custom_header)
                
            building = not self.tabs_loaded.get(stack_index)
            if building:
                create_func = self.pages[page_name]
                self._building_page_name = page_name
                new_widget = create_func()
                self._building_page_name = None
                self._polish_created_page(new_widget)

                old_widget = self.content_stack.widget(stack_index)
                self.content_stack.removeWidget(old_widget)
                self.content_stack.insertWidget(stack_index, new_widget)
                old_widget.deleteLater()
                self.tabs_loaded[stack_index] = True

            self._current_page_name = page_name
            self.content_stack.setCurrentIndex(stack_index)
            self._populate_page_nav(page_name)

            if not self.isVisible():
                # Initial navigation during __init__ (dialog not shown yet): the
                # deferred work runs naturally before the dialog first appears.
                self._animate_page_transition()
            else:
                # Settle the page's own (posted-event) layout synchronously...
                if building:
                    self._settle_page_layout(self.content_stack.widget(stack_index))
                # ...then suspend painting on the WHOLE dialog and RETURN TO THE
                # EVENT LOOP before revealing. This is the crucial part: the things
                # that pop in late — the segmented-control indicators and other
                # widgets that position via QTimer.singleShot(0), plus the header
                # jump-pills' FlowLayout — only settle once control goes back to the
                # event loop. processEvents() cannot fire a singleShot(0) timer, so
                # any synchronous flush was a no-op for them. Keeping updates
                # disabled across one event-loop tick lets all of it happen while
                # nothing is painted; _reveal_current_page then repaints + fades in
                # the finished page in a single frame.
                self.setUpdatesEnabled(False)
                QTimer.singleShot(0, self._reveal_current_page)
        finally:
            self._building_page_name = None
            self._navigating_page = False

    def _reveal_current_page(self):
        """Re-enable painting and fade the page in, after the event loop has had a
        tick (with the dialog painting-suspended) to run all deferred, timer-based
        positioning — segment indicators, jump-pill layout — off-screen."""
        try:
            self.setUpdatesEnabled(True)
            self._animate_page_transition()
        except Exception:
            try:
                self.setUpdatesEnabled(True)
            except Exception:
                pass

    def _preview_expected_width(self):
        """Approximate the width a full-width preview panel will get once laid out.

        Used to size aspect-ratio previews (BackgroundPreviewLabel) correctly at
        build time — before the page is laid out, width() is 0, which would pin the
        minimum-height floor and make the panel grow on the first on-screen layout.
        """
        try:
            width = self.content_stack.width()
            if width <= 0:
                width = self.width()
            # Subtract content-shell margins, scroll frame + scrollbar, and the
            # section/designer padding the preview sits inside.
            return max(720, width - 110)
        except Exception:
            return 720

    def _settle_page_layout(self, page_widget):
        """Compute a freshly built page's layout before it is painted.

        Pages like Main menu and Sidebar contain responsive widgets (the layout
        editors, adaptive mode cards, elided labels) that only reflow on their
        first real resize, and some defer that work via posted layout events or
        QTimer.singleShot(0). If it runs after the page is shown, the user sees
        elements jump from a clipped/misplaced state into position. Forcing the
        layout at the final size and then flushing the posted/deferred work while
        painting is suspended makes all of it happen off-screen, so the page is
        already settled when it fades in.
        """
        if page_widget is None or not self.isVisible():
            return
        try:
            target = self.content_stack.size()
            if target.width() <= 0 or target.height() <= 0:
                return
            page_widget.resize(target)
            page_widget.ensurePolished()
            # Settle in a few passes. Each pass activates the whole layout tree and
            # then flushes posted/deferred work (layout events and
            # QTimer.singleShot(0) relayouts). A single pass clears one wave, but
            # some reflows are second-order — e.g. a grid editor only reaches its
            # final width after the scroll viewport resizes, then re-elides its
            # labels — so a couple of extra passes resolve the cascade off-screen
            # instead of letting it snap in after the page is shown. User input is
            # excluded so this can't re-enter navigation.
            for _ in range(4):
                top_layout = page_widget.layout()
                if top_layout is not None:
                    top_layout.activate()
                for child in page_widget.findChildren(QWidget):
                    child_layout = child.layout()
                    if child_layout is not None:
                        child_layout.activate()
                if mw is None or mw.app is None:
                    break
                try:
                    mw.app.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
                except Exception:
                    mw.app.processEvents()
            # Force a full off-screen render. Unlike layout().activate(), grab()
            # runs a real paint pass, so paint-dependent geometry — grid column
            # widths and DraggableItem labels that elide against their actual
            # painted width — resolves to its final state before the page is
            # shown, instead of snapping on the first on-screen paint.
            try:
                page_widget.grab()
            except Exception:
                pass
        except Exception:
            pass

    def _open_archived_buttons_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("archived_buttons_label", "Archived Buttons"))
        dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        dialog.setMinimumWidth(420)

        if theme_manager.night_mode:
            bg, fg, muted, border = "#2c2c2c", "#e8e8e8", "#a8a8a8", "#4a4a4a"
        else:
            bg, fg, muted, border = "#ffffff", "#202124", "#6f7177", "#e0e0e0"

        outer = QVBoxLayout(dialog)
        outer.setContentsMargins(10, 10, 10, 10)
        container = QFrame()
        container.setObjectName("ArchivedButtonsContainer")
        container.setStyleSheet(
            f"QFrame#ArchivedButtonsContainer {{ background-color: {bg}; border-radius: 18px; border: 1px solid {border}; }}"
        )
        outer.addWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel(tr("archived_buttons_label", "Archived Buttons"))
        title.setStyleSheet(f"font-weight: 700; font-size: 15px; color: {fg}; background: transparent; border: none;")
        close_btn = QPushButton()
        close_btn.setObjectName("archivedButtonsClose")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setToolTip(tr("close", "Close"))
        close_btn.setFlat(True)
        close_btn.setIcon(self._themed_icon("cancel.svg", fg, 16))
        close_btn.setIconSize(QSize(16, 16))
        close_btn.setStyleSheet(
            f"QPushButton#archivedButtonsClose {{ background: transparent; border: none; border-radius: 15px; }}"
            f"QPushButton#archivedButtonsClose:hover {{ background: transparent; }}"
        )
        close_btn.clicked.connect(dialog.reject)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(close_btn)
        layout.addLayout(header)

        help_label = QLabel(tr("archived_buttons_help", "Right-click a button to bring it back to the sidebar."))
        help_label.setWordWrap(True)
        help_label.setStyleSheet(f"color: {muted}; font-size: 12px; background: transparent; border: none;")
        layout.addWidget(help_label)

        listw = QListWidget()
        listw.setObjectName("archivedButtonsList")
        listw.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        listw.setIconSize(QSize(22, 22))
        listw.setSpacing(4)
        listw.setFrameShape(QFrame.Shape.NoFrame)
        listw.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        listw.setStyleSheet(f"""
            QListWidget#archivedButtonsList {{ background: transparent; border: none; outline: none; }}
            QListWidget#archivedButtonsList::item {{
                background: {'rgba(255,255,255,0.04)' if theme_manager.night_mode else 'rgba(0,0,0,0.03)'};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 9px 10px;
                margin: 2px 0px;
                color: {fg};
            }}
            QListWidget#archivedButtonsList::item:hover {{ border-color: {self.accent_color}; }}
        """)
        listw.setMinimumHeight(240)
        listw.customContextMenuRequested.connect(
            lambda pos: self._show_archived_button_context_menu(listw, pos)
        )
        layout.addWidget(listw)

        self._archived_buttons_dialog = dialog
        self._archived_buttons_list = listw
        self._refresh_archived_buttons_dialog()

        dialog.finished.connect(lambda _=0: self._clear_archived_buttons_dialog())
        parent_geo = self.geometry()
        dialog.adjustSize()
        dialog.move(
            parent_geo.x() + (parent_geo.width() - dialog.width()) // 2,
            parent_geo.y() + (parent_geo.height() - dialog.height()) // 2,
        )
        dialog.exec()

    def _open_action_button_icon_picker(self, key):
        current = self._action_icon_preview_value(key)
        if str(current).startswith("emoji:"):
            current = ""
        picker = DeckIconPickerDialog(
            current,
            self.addon_path,
            self,
            allow_emoji=False,
            color_options=self._action_button_icon_picker_color_options(key),
            preview_color_key="icon",
        )

        def on_selected(value):
            if not value or str(value).startswith("emoji:"):
                return
            self._set_action_button_icon(key, value)

        def on_colors(values):
            color = values.get("icon")
            if color and QColor(color).isValid():
                self._action_button_icon_colors[key] = color
                self._refresh_action_button_item(key)
                self._refresh_archived_buttons_dialog()
                self._update_action_buttons_preview()

        picker.iconSelected.connect(on_selected)
        picker.colorsChanged.connect(on_colors)
        parent_geo = self.geometry()
        picker_geo = picker.geometry()
        picker.move(
            parent_geo.x() + (parent_geo.width() - picker_geo.width()) // 2,
            parent_geo.y() + (parent_geo.height() - picker_geo.height()) // 2,
        )
        picker.exec()



# --- MERGED FROM _dialog_core_2.py ---

class DialogCoreMixin2:
    def apply_stylesheet(self):
        palette = self._settings_palette()
        accent_color = self._settings_accent_color()
        if theme_manager.night_mode:
            # ── Dark mode ──────────────────────────────────────────────────
            window_bg        = palette.get("--bg", "#181818")
            panel_bg         = palette.get("--canvas-inset", "#242424")
            sidebar_bg       = window_bg   # sidebar alinhada ao fundo geral
            surface_bg       = palette.get("--highlight-bg", "#303030")
            surface_hover    = palette.get("--hover-bg", "#3a3a3a")
            input_bg         = palette.get("--input-bg", panel_bg)
            button_bg        = surface_bg
            fg               = palette.get("--fg", "#f9fafb")
            fg_secondary     = palette.get("--fg-subtle", "#c4c4c4")
            muted_fg         = palette.get("--muted-fg", "#8a8a8a")
            border           = palette.get("--border", "#454545")
            soft_border      = border
            separator_color  = border
            sidebar_label_color  = fg_secondary
            nav_checked_bg   = surface_hover
            nav_checked_fg   = fg
            save_btn_bg      = palette.get("--button-primary-bg", accent_color)
            c = QColor(save_btn_bg)
            lum = (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) / 255
            save_btn_fg      = "#111827" if lum > 0.5 else "#ffffff"
            save_btn_border  = save_btn_bg
            save_btn_icon    = save_btn_fg
            scroll_thumb_hover = "rgba(255, 255, 255, 0.34)"
            sidebar_scrollbar_thumb = "rgba(255, 255, 255, 0.20)"
            sidebar_scrollbar_thumb_hover = "rgba(255, 255, 255, 0.34)"
        else:
            # ── Light mode — fiel à referência ────────────────────────────
            window_bg        = palette.get("--bg", "#f0f0f0")
            panel_bg         = palette.get("--canvas-inset", "#ffffff")
            sidebar_bg       = window_bg   # sidebar alinhada ao fundo geral
            surface_bg       = palette.get("--highlight-bg", "#f2f2f2")
            surface_hover    = palette.get("--hover-bg", "#e9e9e9")
            input_bg         = palette.get("--input-bg", panel_bg)
            button_bg        = surface_bg
            fg               = palette.get("--fg", "#111827")
            fg_secondary     = palette.get("--fg-subtle", "#6f7177")
            muted_fg         = palette.get("--muted-fg", "#8f9299")
            border           = palette.get("--border", "#e5e7eb")
            soft_border      = border
            separator_color  = border
            sidebar_label_color  = fg_secondary
            nav_checked_bg   = surface_hover
            nav_checked_fg   = fg
            save_btn_bg      = palette.get("--button-primary-bg", accent_color)
            c = QColor(save_btn_bg)
            lum = (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) / 255
            save_btn_fg      = "#111827" if lum > 0.5 else "#ffffff"
            save_btn_border  = save_btn_bg
            save_btn_icon    = save_btn_fg
            scroll_thumb_hover = "rgba(17, 24, 39, 0.28)"
            sidebar_scrollbar_thumb = "rgba(17, 24, 39, 0.16)"
            sidebar_scrollbar_thumb_hover = "rgba(17, 24, 39, 0.28)"

        self.accent_color = accent_color

        self.setStyleSheet(f"""

            /* ── Janela base ─────────────────────────────────────────── */
            QDialog {{
                background-color: {window_bg};
                color: {fg};
                font-size: 13px;
                font-family: 'Poppins', -apple-system, "Segoe UI", sans-serif;
            }}

            /* ── Sidebar ─────────────────────────────────────────────── */
            QWidget#settingsSidebarWrapper {{
                background-color: {sidebar_bg};
                border-right: none;
            }}
            QWidget#settingsContentShell {{
                background-color: {panel_bg};
                border: none;
                border-top-left-radius: 28px;
                border-top-right-radius: 28px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }}

            /* ── Cabeçalho da página ─────────────────────────────────── */
            QWidget#settingsPageHeader {{
                background-color: transparent;
                min-height: 40px;
            }}
            QLabel#settingsPageTitle {{
                color: {fg};
                background: transparent;
                border: none;
                font-size: 22px;
                font-weight: 300;
                padding: 0px;
                letter-spacing: 0px;
            }}
            QWidget#pageNavBar {{
                background-color: transparent;
                border: none;
                min-height: 32px;
                max-height: 32px;
            }}

            /* Botões de navegação de seção (jump) — rounded-square */
            QPushButton#pageNavButton {{
                background-color: {surface_bg};
                border: 1px solid {border};
                border-radius: 10px;
                color: {fg_secondary};
                min-height: 28px;
                padding: 0px 16px;
                font-weight: 500;
                font-size: 12px;
            }}
            QPushButton#pageNavButton:hover {{
                background-color: {surface_hover};
                border-color: {soft_border};
                color: {fg};
            }}
            QPushButton#pageNavButton:pressed {{
                background-color: {nav_checked_bg};
                border-color: {border};
                color: {fg};
            }}

            /* ── Stack de conteúdo ───────────────────────────────────── */
            QStackedWidget#contentStack {{
                background-color: transparent;
                border: none;
            }}
            QWidget#pageContainer {{
                background-color: transparent;
                border: none;
                border-top-left-radius: 28px;
                border-top-right-radius: 28px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }}
            QWidget#settingsPageContent {{
                background-color: transparent;
            }}
            QScrollArea#settingsPageScroll,
            QScrollArea {{
                background-color: transparent;
                border: none;
                border-top-left-radius: 24px;
                border-top-right-radius: 24px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }}
            QScrollArea QWidget#qt_scrollarea_viewport {{
                background-color: transparent;
                border: none;
                border-top-left-radius: 24px;
                border-top-right-radius: 24px;
                border-bottom-left-radius: 0px;
                border-bottom-right-radius: 0px;
            }}

            /* ── Containers da sidebar ───────────────────────────────── */
            #sidebarContainer,
            #sidebarActionsContainer {{
                background-color: transparent;
                border: none;
            }}

            QScrollArea#sidebarNavScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollArea#sidebarNavScrollArea QScrollBar:vertical {{
                border: none;
                background-color: transparent;
                width: 6px;
                margin: 12px 2px 12px 2px;
            }}
            QScrollArea#sidebarNavScrollArea QScrollBar::handle:vertical {{
                background-color: {sidebar_scrollbar_thumb};
                min-height: 38px;
                border-radius: 3px;
            }}
            QScrollArea#sidebarNavScrollArea QScrollBar::handle:vertical:hover {{
                background-color: {sidebar_scrollbar_thumb_hover};
            }}
            QScrollArea#sidebarNavScrollArea QScrollBar::add-line:vertical,
            QScrollArea#sidebarNavScrollArea QScrollBar::sub-line:vertical,
            QScrollArea#sidebarNavScrollArea QScrollBar::add-page:vertical,
            QScrollArea#sidebarNavScrollArea QScrollBar::sub-page:vertical {{
                height: 0;
                width: 0;
                background: none;
                border: none;
            }}

            /* Botões da sidebar — estado padrão */
            #sidebarContainer QPushButton,
            #sidebarActionsContainer QPushButton {{
                min-height: 28px;
                padding: 4px 10px;
                border-radius: 20px;
                text-align: left;
                border: 1px solid transparent;
                background-color: transparent;
                color: {fg_secondary};
                font-weight: 500;
                font-size: 13px;
            }}

            /* Botão de busca no topo da sidebar */
            QPushButton#sidebarSearchButton {{
                min-height: 38px;
                max-height: 38px;
                padding: 0px 14px;
                border-radius: 12px;
                background-color: transparent;
                border: 1px solid transparent;
                color: {muted_fg};
                text-align: left;
                font-weight: 500;
                font-size: 13px;
            }}
            QPushButton#sidebarSearchButton:hover {{
                background-color: {surface_hover};
                border-color: transparent;
                color: {fg};
                border-radius: 12px;
            }}
            QPushButton#sidebarSearchButton:checked {{
                background-color: {nav_checked_bg};
                border-color: transparent;
                color: {nav_checked_fg};
                font-weight: 600;
                border-radius: 12px;
            }}

            QPushButton#searchSidebarButton {{
                background-color: {input_bg};
                border: 1px solid {border};
                border-radius: 20px;
                text-align: left;
                font-weight: 400;
                color: {muted_fg};
            }}
            QPushButton#searchSidebarButton:hover {{
                background-color: {surface_hover};
                border-color: {soft_border};
                color: {fg};
                border-radius: 20px;
            }}
            QPushButton#searchSidebarButton:checked {{
                background-color: {nav_checked_bg};
                color: {nav_checked_fg};
                border-color: transparent;
                font-weight: 600;
                border-radius: 20px;
            }}

            /* Hover e ativo dos botões da sidebar */
            #sidebarContainer QPushButton:hover,
            #sidebarActionsContainer QPushButton:hover {{
                background-color: {surface_hover};
                color: {fg};
                border-color: transparent;
            }}
            #sidebarContainer QPushButton:checked,
            #sidebarActionsContainer QPushButton:checked {{
                background-color: {nav_checked_bg};
                color: {nav_checked_fg};
                border-color: transparent;
                font-weight: 600;
            }}
            QPushButton#sidebarSearchButton:hover {{
                background-color: {surface_hover};
                border-color: transparent;
                color: {fg};
                border-radius: 12px;
            }}
            QPushButton#sidebarSearchButton:checked {{
                background-color: {nav_checked_bg};
                border-color: transparent;
                color: {nav_checked_fg};
                font-weight: 600;
                border-radius: 12px;
            }}

            QPushButton#sidebarActionButton,
            #sidebarActionsContainer QPushButton#sidebarActionButton {{
                min-height: 38px;
                max-height: 38px;
                padding: 0px 14px;
                border-radius: 12px;
                text-align: left;
                background-color: {input_bg};
                border: 1px solid {border};
                color: {fg_secondary};
                font-weight: 700;
                font-size: 13px;
            }}
            QPushButton#sidebarActionButton:hover,
            #sidebarActionsContainer QPushButton#sidebarActionButton:hover {{
                background-color: {surface_hover};
                color: {fg};
                border-color: {soft_border};
                border-radius: 12px;
            }}
            QPushButton#sidebarActionButton:pressed,
            #sidebarActionsContainer QPushButton#sidebarActionButton:pressed {{
                background-color: {nav_checked_bg};
                color: {nav_checked_fg};
                border-color: {border};
                border-radius: 12px;
            }}

            QPushButton#saveSidebarButton,
            #sidebarActionsContainer QPushButton#saveSidebarButton {{
                min-height: 38px;
                max-height: 38px;
                padding: 1px 14px;
                border-radius: 12px;
                text-align: left;
                background-color: {save_btn_bg};
                color: {save_btn_fg};
                border: 1px solid {save_btn_border};
                font-weight: 700;
                font-size: 13px;
            }}
            QPushButton#cancelSidebarButton,
            #sidebarActionsContainer QPushButton#cancelSidebarButton {{
                min-height: 38px;
                max-height: 38px;
                padding: 1px 14px;
                border-radius: 12px;
                text-align: center;
                background-color: {input_bg};
                color: {fg_secondary};
                border: 1px solid {border};
                font-weight: 700;
                font-size: 13px;
            }}
            QPushButton#cancelSidebarButton:hover,
            #sidebarActionsContainer QPushButton#cancelSidebarButton:hover {{
                background-color: {input_bg};
                color: {fg_secondary};
                border-radius: 12px;
            }}
            QPushButton#saveSidebarButton:hover,
            #sidebarActionsContainer QPushButton#saveSidebarButton:hover {{
                background-color: {save_btn_bg};
                color: {save_btn_fg};
                border-color: {save_btn_border};
            }}
            QPushButton#saveSidebarButton:pressed,
            #sidebarActionsContainer QPushButton#saveSidebarButton:pressed {{
                background-color: {save_btn_bg};
                color: #ffffff;
                border-color: {save_btn_border};
            }}

            /* Cabeçalhos expansíveis da sidebar */
            QPushButton#sidebarSectionToggle,
            #sidebarContainer QPushButton#sidebarSectionToggle {{
                color: {sidebar_label_color};
                background: transparent;
                border: none;
                border-radius: 12px;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.7px;
                padding: 4px 8px;
                margin-top: 0px;
                margin-bottom: 0px;
                text-align: left;
            }}
            QPushButton#sidebarSectionToggle:hover,
            #sidebarContainer QPushButton#sidebarSectionToggle:hover {{
                color: {fg};
                background-color: {surface_hover};
                border: none;
                border-radius: 12px;
            }}
            QPushButton#sidebarSectionToggle:checked,
            #sidebarContainer QPushButton#sidebarSectionToggle:checked {{
                color: {sidebar_label_color};
                background: transparent;
                border: none;
                border-radius: 12px;
                font-weight: 700;
            }}
            QWidget#sidebarSectionContent {{
                background: transparent;
                border: none;
            }}

            /* Sub-tipos de nav da sidebar */
            #sidebarContainer QPushButton#mainItemButton {{
                font-weight: 600;
                color: {fg};
            }}
            QPushButton#sidebarNavButton,
            #sidebarContainer QPushButton#sidebarNavButton {{
                min-height: 28px;
                padding: 4px 10px;
                border-radius: 20px;
                background-color: transparent;
                border: 1px solid transparent;
                text-align: left;
                font-weight: 500;
                color: {fg_secondary};
            }}
            QPushButton#sidebarNavButton:hover,
            #sidebarContainer QPushButton#sidebarNavButton:hover {{
                background-color: {surface_hover};
                color: {fg};
                border-color: transparent;
                border-radius: 18px;
            }}
            QPushButton#sidebarNavButton:checked,
            #sidebarContainer QPushButton#sidebarNavButton:checked {{
                background-color: {nav_checked_bg};
                color: {nav_checked_fg};
                border-color: transparent;
                font-weight: 600;
                border-radius: 18px;
            }}
            #sidebarContainer QPushButton#subItemButton {{
                min-height: 28px;
                padding: 5px 10px 5px 20px;
                border-radius: 18px;
                color: {muted_fg};
                font-weight: 400;
                font-size: 12px;
            }}
            #sidebarContainer QPushButton#subItemButton:hover {{
                color: {fg};
                background-color: {surface_hover};
                border-radius: 18px;
            }}
            #sidebarContainer QPushButton#subItemButton:checked {{
                background-color: {nav_checked_bg};
                color: {nav_checked_fg};
                font-weight: 500;
                border-radius: 18px;
            }}

            /* ── Labels genéricas ────────────────────────────────────── */
            QLabel,
            QRadioButton,
            QCheckBox {{
                color: {fg};
                background-color: transparent;
            }}
            QLabel:disabled,
            QRadioButton:disabled,
            QCheckBox:disabled {{
                color: {muted_fg};
            }}

            /* ── Cards de seção de conteúdo ──────────────────────────── */
            QWidget#settingsSection {{
                background-color: transparent;
                border: none;
                border-radius: 18px;
            }}
            QWidget#sectionBody {{
                background-color: transparent;
                border: none;
            }}
            QLabel#sectionTitle {{
                color: {fg};
                background: transparent;
                font-size: 17px;
                font-weight: 400;
            }}
            QLabel#sectionDescription,
            QLabel#settingRowDescription {{
                color: {muted_fg};
                background: transparent;
                font-size: 13px;
            }}
            QLabel#settingRowTitle,
            QLabel#galleryTitleLabel {{
                color: {fg};
                background: transparent;
                font-size: 14px;
                font-weight: 400;
            }}
            #innerGroup {{
                background-color: transparent;
                border: none;
                border-radius: 18px;
            }}

            /* Linhas de setting */
            QFrame#settingRow {{
                background-color: {panel_bg};
                border: 1px solid {border};
                border-radius: 26px;
            }}
            QFrame#settingRow:hover {{
                background-color: {surface_hover};
                border-radius: 26px;
            }}
            QFrame#sidebarCustomizationRow {{
                background-color: {panel_bg};
                border: 1px solid {border};
                border-radius: 22px;
            }}
            QFrame#sidebarCustomizationRow:hover {{
                background-color: {surface_hover};
                border-radius: 22px;
            }}
            QFrame#heatmapVisibilityRow {{
                background-color: transparent;
                border: none;
                border-radius: 12px;
            }}
            QFrame#heatmapVisibilityRow:hover {{
                background-color: {surface_hover};
                border: none;
                border-radius: 12px;
            }}
            QFrame#mainBackgroundDesigner {{
                background-color: {panel_bg};
                border: 1px solid {border};
                border-radius: 26px;
            }}
            QPushButton#mainBackgroundButton,
            QPushButton#mainBackgroundColorButton {{
                background-color: transparent;
                color: {fg};
                border: 1px solid {border};
                border-radius: 12px;
                min-height: 36px;
                max-height: 36px;
                padding: 0px 14px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton#mainBackgroundButton:hover,
            QPushButton#mainBackgroundColorButton:hover,
            QPushButton#mainBackgroundButton:pressed,
            QPushButton#mainBackgroundColorButton:pressed,
            QPushButton#mainBackgroundButton:disabled,
            QPushButton#mainBackgroundColorButton:disabled {{
                background-color: {surface_hover};
                border-radius: 12px;
            }}
            QPushButton#mainBackgroundButton:disabled {{
                color: {muted_fg};
                border-color: {border};
            }}
            QPushButton#mainBackgroundResetButton {{
                background-color: {button_bg};
                color: {fg_secondary};
                border: 1px solid {border};
                border-radius: 17px;
                min-height: 34px;
                max-height: 34px;
                padding: 0px 18px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton#mainBackgroundResetButton:hover,
            QPushButton#mainBackgroundResetButton:pressed {{
                background-color: {surface_hover};
                border-color: {soft_border};
                color: {fg};
                border-radius: 17px;
            }}
            QLabel#mainBackgroundControlLabel,
            QLabel#mainBackgroundValueLabel {{
                color: {fg};
                background: transparent;
                font-size: 13px;
            }}
            QFrame#mainBackgroundDivider {{
                background-color: {border};
                border: none;
            }}

            /* ── GroupBox ────────────────────────────────────────────── */
            QGroupBox {{
                background-color: transparent;
                border: none;
                border-radius: 18px;
                margin-top: 0px;
                padding: 28px 0px 6px 0px;
                font-weight: 600;
            }}
            QGroupBox::title {{
                subcontrol-origin: padding;
                subcontrol-position: top left;
                top: 0px;
                left: 0px;
                padding: 0px;
                color: {fg};
                background-color: transparent;
                font-size: 14px;
                font-weight: 500;
            }}

            /* ── Radio buttons ───────────────────────────────────────── */
            QRadioButton::indicator {{
                border: 2px solid {border};
                background-color: transparent;
                width: 18px;
                height: 18px;
                min-width: 18px;
                min-height: 18px;
                max-width: 18px;
                max-height: 18px;
                border-radius: 11px;
                margin: 0 4px 0 0;
                image: none;
            }}
            QRadioButton::indicator:checked {{
                border: 2px solid {accent_color};
                background-color: {accent_color};
                image: none;
            }}
            QRadioButton::indicator:hover {{
                border-color: {accent_color};
            }}

            /* ── Checkbox selectors: circular, not square ─────────────── */
            QCheckBox::indicator {{
                border: 2px solid {border};
                background-color: transparent;
                width: 18px;
                height: 18px;
                min-width: 18px;
                min-height: 18px;
                max-width: 18px;
                max-height: 18px;
                border-radius: 11px;
                margin: 0 4px 0 0;
                image: none;
            }}
            QCheckBox::indicator:checked {{
                border: 2px solid {accent_color};
                background-color: {accent_color};
                image: none;
            }}
            QCheckBox::indicator:hover {{
                border-color: {accent_color};
            }}

            /* ── Inputs ──────────────────────────────────────────────── */
            QLineEdit,
            QSpinBox,
            QDoubleSpinBox,
            QAbstractSpinBox,
            QComboBox,
            QPlainTextEdit,
            QTextEdit,
            QDateEdit {{
                background-color: {input_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 18px;
                padding: 6px 10px;
                min-height: 30px;
                selection-background-color: {accent_color};
                selection-color: white;
            }}
            QLineEdit:focus,
            QSpinBox:focus,
            QDoubleSpinBox:focus,
            QAbstractSpinBox:focus,
            QComboBox:focus,
            QPlainTextEdit:focus,
            QTextEdit:focus,
            QDateEdit:focus {{
                border-color: {soft_border};
                background-color: {panel_bg};
                outline: none;
            }}

            QSpinBox,
            QDoubleSpinBox,
            QAbstractSpinBox {{
                border-radius: 16px;
                min-height: 32px;
                max-height: 32px;
                padding: 0px 10px;
            }}
            QSpinBox:hover,
            QDoubleSpinBox:hover,
            QAbstractSpinBox:hover {{
                border-radius: 16px;
            }}
            QSpinBox:focus,
            QDoubleSpinBox:focus,
            QAbstractSpinBox:focus {{
                border-radius: 16px;
            }}
            QSpinBox:disabled,
            QDoubleSpinBox:disabled,
            QAbstractSpinBox:disabled {{
                border-radius: 16px;
            }}
            #iconSizeSpinBox {{
                border-radius: 16px;
                min-height: 32px;
                max-height: 32px;
                padding: 0px 10px;
            }}
            #iconSizeSpinBox:hover,
            #iconSizeSpinBox:focus,
            #iconSizeSpinBox:disabled {{
                border-radius: 16px;
            }}

            QLineEdit:disabled,
            QSpinBox:disabled,
            QDoubleSpinBox:disabled,
            QAbstractSpinBox:disabled,
            QComboBox:disabled {{
                background-color: {surface_bg};
                color: {muted_fg};
                border-color: {border};
            }}

            /* ComboBox drop-down */
            QComboBox::drop-down {{
                border: none;
                width: 24px;
                border-top-right-radius: 18px;
                border-bottom-right-radius: 18px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {panel_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 18px;
                selection-background-color: {surface_hover};
                selection-color: {fg};
                padding: 4px;
                outline: none;
            }}

            /* ── Botões genéricos ────────────────────────────────────── */
            QPushButton {{
                background-color: {button_bg};
                color: {fg_secondary};
                border: 1px solid {border};
                padding: 7px 14px;
                border-radius: 18px;
                font-weight: 500;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {surface_hover};
                border-color: {soft_border};
                color: {fg};
            }}
            QPushButton:pressed {{
                background-color: {surface_hover};
                border-color: {soft_border};
            }}
            QPushButton:disabled {{
                background-color: {surface_bg};
                color: {muted_fg};
                border-color: {border};
                border-radius: 18px;
            }}

            /* ── Separadores ─────────────────────────────────────────── */
            QFrame[frameShape="4"] {{
                border: none;
                background-color: {separator_color};
                max-height: 1px;
            }}
            QFrame#MenuSeparator {{
                background-color: {border};
                max-height: 1px;
                border: none;
            }}

            /* ── Tabs ────────────────────────────────────────────────── */
            QTabBar::tab {{
                background: transparent;
                border: 1px solid transparent;
                padding: 6px 14px;
                border-radius: 18px;
                margin-right: 3px;
                color: {muted_fg};
                font-weight: 500;
            }}
            QTabBar::tab:selected {{
                background: {panel_bg};
                color: {fg};
                border-color: {border};
                font-weight: 600;
            }}
            QTabBar::tab:!selected:hover {{
                background: {surface_hover};
                color: {fg};
            }}
            QTabWidget::pane {{
                background-color: transparent;
                border: none;
            }}
            QTabBar {{ qproperty-drawBase: 0; }}

            /* ── Scrollbars — minimalistas ───────────────────────────── */
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 10px;
                margin: 0px 2px 0px 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {border};
                min-height: 32px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {scroll_thumb_hover};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                height: 0; width: 0; background: none; border: none;
            }}
            QScrollBar:horizontal {{
                border: none;
                background: transparent;
                height: 10px;
                margin: 2px 0px 2px 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: {border};
                min-width: 32px;
                border-radius: 5px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: {scroll_thumb_hover};
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                height: 0; width: 0; background: none; border: none;
            }}

            /* ── SpinBox: typing only, without stepper chrome ────────── */
            QSpinBox::up-button {{
                width: 0px;
                height: 0px;
                border: none;
                image: none;
                padding: 0px;
            }}
            QSpinBox::down-button {{
                width: 0px;
                height: 0px;
                border: none;
                image: none;
                padding: 0px;
            }}
            QDoubleSpinBox::up-button {{
                width: 0px;
                height: 0px;
                border: none;
                image: none;
                padding: 0px;
            }}
            QDoubleSpinBox::down-button {{
                width: 0px;
                height: 0px;
                border: none;
                image: none;
                padding: 0px;
            }}

            /* ── Widgets especiais ───────────────────────────────────── */
            #colorPill {{
                background-color: {input_bg};
                border: 1px solid {border};
                border-radius: 18px;
            }}

            QFrame#themeCard {{
                background-color: {panel_bg};
                border: 1px solid {border};
                border-radius: 24px;
                padding: 12px;
            }}
            QFrame#themeCard:hover {{
                border-color: {soft_border};
                background-color: {surface_hover};
            }}

            QFrame#hideModeCard {{
                background-color: {panel_bg};
                border: 1px solid {border};
                border-radius: 24px;
                padding: 16px;
            }}
            QLabel#hideModeTitleLabel {{
                font-size: 15px;
                font-weight: 500;
                color: {fg};
            }}
            QLabel#hideModeDescLabel {{
                color: {muted_fg};
                font-size: 12px;
            }}

            QGroupBox#LayoutGroup,
            QFrame#LayoutGroup {{
                background-color: {surface_bg};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            QGroupBox#LayoutGroup {{
                margin-top: 0px;
                padding: 38px 12px 12px 12px;
            }}
            QGroupBox#LayoutGroup::title {{
                subcontrol-origin: padding;
                subcontrol-position: top left;
                top: 10px;
                left: 14px;
                padding: 0px;
                background-color: transparent;
                color: {fg};
                font-size: 13px;
                font-weight: 600;
            }}
            QLabel#LayoutGroupTitle {{
                color: {fg};
                background-color: transparent;
                font-size: 13px;
                font-weight: 600;
                padding: 0px;
            }}

            #DraggableItem {{
                background-color: {button_bg};
                border: 1px solid {border};
                border-radius: 18px;
                color: {fg};
                font-weight: 500;
                text-align: center;
            }}
            #DropZone {{
                background-color: {input_bg};
                border-radius: 20px;
                padding: 5px;
            }}
            #Shelf {{
                background-color: transparent;
                border: 1.5px dashed {border};
                border-radius: 18px;
            }}
            #Shelf[is_highlighted="true"] {{
                background-color: rgba(99, 132, 255, 0.08);
                border: 1.5px solid {accent_color};
            }}

            #MenuBackground {{
                background-color: {panel_bg};
                border: 1px solid {border};
                border-radius: 14px;
            }}
            QPushButton#MenuButton {{
                background-color: transparent;
                color: {fg};
                border: 1px solid transparent;
                padding: 7px 16px;
                text-align: center;
                border-radius: 10px;
                font-weight: 400;
            }}
            QPushButton#MenuButton:hover {{
                background-color: {surface_hover};
                border-color: transparent;
                border-radius: 10px;
            }}
            QPushButton#MenuButton:checked {{
                background-color: {nav_checked_bg};
                color: {nav_checked_fg};
                border-color: transparent;
                border-radius: 10px;
                font-weight: 600;
            }}
            QLabel#MenuSectionLabel {{
                color: {muted_fg};
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 0.5px;
                padding: 2px 2px 0px 2px;
            }}
            QPushButton#MenuSegmentButton {{
                background-color: transparent;
                color: {fg};
                border: 1px solid {border};
                padding: 6px 4px;
                border-radius: 9px;
                font-weight: 500;
            }}
            QPushButton#MenuSegmentButton:hover {{
                background-color: {surface_hover};
                border-color: {soft_border};
            }}
            QPushButton#MenuSegmentButton:checked {{
                background-color: {nav_checked_bg};
                color: {nav_checked_fg};
                border-color: {border};
                font-weight: 600;
            }}

            /* Barra de jump de página */
            QWidget#pageJumpBar {{
                background-color: {surface_bg};
                border: 1px solid {border};
                border-radius: 18px;
                padding: 2px;
            }}
            QPushButton#pageJumpButton {{
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 12px;
                padding: 5px 12px;
                min-height: 22px;
                font-weight: 500;
                font-size: 12px;
                color: {muted_fg};
            }}
            QPushButton#pageJumpButton:hover {{
                background-color: {panel_bg};
                border-color: {border};
                color: {fg};
            }}
            QPushButton#pageJumpButton:pressed {{
                background-color: {nav_checked_bg};
                border-color: {border};
                color: {nav_checked_fg};
            }}

            /* Página de pesquisa */
            QLineEdit#settingsSearchInput {{
                min-height: 46px;
                max-height: 46px;
                padding: 0px 18px;
                border-radius: 23px;
                font-size: 14px;
                background-color: {panel_bg};
                border: 1px solid {border};
                color: {fg};
            }}
            QLineEdit#settingsSearchInput:focus {{
                border-color: {soft_border};
                background-color: {input_bg};
            }}
            QFrame#searchCard {{
                background-color: {panel_bg};
                border-radius: 22px;
                border: 1px solid {border};
            }}
            QFrame#searchCard:hover {{
                background-color: {surface_hover};
                border-color: {soft_border};
            }}
            QLabel#searchCardTitle {{
                color: {fg};
                font-size: 14px;
                font-weight: 400;
                background: transparent;
            }}
            QLabel#searchCardDescription {{
                color: {muted_fg};
                font-size: 12px;
                background: transparent;
            }}
            QPushButton#searchResult {{
                background-color: {surface_bg};
                border-radius: 18px;
                border: 1px solid {border};
                text-align: left;
                color: {fg_secondary};
            }}
            QPushButton#searchResult:hover {{
                background-color: {surface_hover};
                border-color: {soft_border};
                color: {fg};
            }}

            QPushButton#pageNavButton {{
                background-color: {surface_bg};
                border: 1px solid {border};
                border-radius: 10px;
                min-height: 28px;
                padding: 0px 16px;
                color: {fg_secondary};
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton#pageNavButton:hover {{
                background-color: {surface_hover};
                border-color: {soft_border};
                color: {fg};
            }}

            QPushButton#fontCard {{
                background-color: {surface_bg};
                border: 1.5px solid {border};
                border-radius: 22px;
                color: {fg};
                padding: 10px;
                text-align: center;
            }}
            QPushButton#fontCard:hover {{
                background-color: {surface_hover};
                border-color: {soft_border};
            }}
            QPushButton#fontCard:checked {{
                border: 2px solid {accent_color};
                background-color: {panel_bg};
            }}
            QPushButton#fontAddButton {{
                background-color: transparent;
                border: 1px solid {border};
                border-radius: 22px;
                color: {fg_secondary};
                padding: 0px 18px;
                min-height: 44px;
                max-height: 44px;
                text-align: center;
                font-weight: 600;
            }}
            QPushButton#fontAddButton:hover {{
                background-color: {surface_hover};
                border-color: {soft_border};
                color: {fg};
                border-radius: 22px;
            }}
            QPushButton#fontRestoreButton {{
                background-color: {input_bg};
                color: {fg_secondary};
                border: 1px solid {border};
                border-radius: 22px;
                padding: 0px 18px;
                min-height: 44px;
                max-height: 44px;
                font-weight: 600;
            }}
            QPushButton#fontRestoreButton:hover {{
                background-color: {surface_hover};
                border-color: {soft_border};
                color: {fg};
                border-radius: 22px;
            }}
            QComboBox#fontSelectorCombo {{
                background-color: {input_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 22px;
                padding: 0px 46px 0px 18px;
                min-height: 44px;
                max-height: 44px;
                font-size: 13px;
            }}
            QComboBox#fontSelectorCombo:hover {{
                background-color: {surface_hover};
                border-color: {soft_border};
                border-radius: 22px;
            }}
            QComboBox#fontSelectorCombo:focus,
            QComboBox#fontSelectorCombo:on {{
                background-color: {panel_bg};
                border-color: {soft_border};
                border-radius: 22px;
            }}
            QComboBox#fontSelectorCombo::drop-down {{
                border: none;
                width: 44px;
                border-top-right-radius: 22px;
                border-bottom-right-radius: 22px;
            }}
            QWidget#fontSizePill {{
                background-color: {input_bg};
                border: 1px solid {border};
                border-radius: 22px;
            }}
            QWidget#fontSizePill:hover {{
                background-color: {surface_hover};
                border-color: {soft_border};
            }}
            QSpinBox#fontSizeSpinBox {{
                background-color: transparent;
                color: {fg};
                border: none;
                padding: 0px;
                min-height: 44px;
                max-height: 44px;
                font-size: 13px;
            }}
            QSpinBox#fontSizeSpinBox::up-button {{
                width: 0px;
                height: 0px;
                border: none;
                image: none;
                padding: 0px;
            }}
            QSpinBox#fontSizeSpinBox::down-button {{
                width: 0px;
                height: 0px;
                border: none;
                image: none;
                padding: 0px;
            }}
            QLabel#fontSizeUnitLabel {{
                background-color: transparent;
                color: {muted_fg};
                font-size: 13px;
            }}
            QFrame#fontSelectorPopupFrame {{
                background-color: transparent;
                border: none;
            }}
            QFrame#fontSelectorPopupPanel {{
                background-color: transparent;
                border: none;
            }}
            QScrollArea#fontSelectorPopupScroll {{
                background-color: transparent;
                color: {fg};
                border: none;
                outline: none;
            }}
            QWidget#fontSelectorPopupContent {{
                background-color: transparent;
                border: none;
            }}
            QWidget#fontSelectorPopupViewport {{
                background-color: transparent;
                border: none;
                border-radius: 16px;
            }}
            QWidget#fontSelectorPopupRow {{
                background: transparent;
            }}
            QPushButton#fontSelectorDeleteButton {{
                background-color: transparent;
                border: none;
                border-radius: 12px;
                padding: 0px;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
            }}
            QPushButton#fontSelectorDeleteButton:hover {{
                background-color: rgba(220, 38, 38, 0.12);
            }}
            QWidget#fontRoleControl {{
                background-color: transparent;
                border: none;
            }}
            QFrame#fontPreviewPanel {{
                background-color: {surface_bg};
                border: 1px solid {border};
                border-radius: 22px;
            }}
            QLabel#fontPreviewTitle {{
                color: {fg};
                background: transparent;
                font-weight: 400;
            }}
            QLabel#fontPreviewBody {{
                color: {fg_secondary};
                background: transparent;
            }}
        """)

        self.save_button.setStyleSheet(
            f"QPushButton#saveSidebarButton{{"
            f"background-color:{save_btn_bg};color:{save_btn_fg};"
            f"border:1px solid {save_btn_border};"
            f"min-height:38px;max-height:38px;"
            f"padding:1px 14px;border-radius:12px;text-align:left;"
            f"font-weight:700;font-size:13px;}}"
            f"QPushButton#saveSidebarButton:hover{{"
            f"background-color:{save_btn_bg};color:{save_btn_fg};"
            f"border:1px solid {save_btn_border};border-radius:12px;}}"
            f"QPushButton#saveSidebarButton:pressed{{"
            f"background-color:{save_btn_bg};border-color:{save_btn_bg};color:#ffffff;border-radius:12px;}}"
        )
        self._refresh_save_button_icon()
        self._refresh_theme_dependent_widgets()

    def save_settings(self):
        if getattr(self, "_is_saving", False):
            return
        if self._pending_theme_data is not None and not self._theme_prepare_save_in_progress:
            self._theme_prepare_save_in_progress = True
            self._show_theme_preparing_state()
            QTimer.singleShot(500, self._save_settings_after_theme_prepare)
            return

        self._is_saving = True
        try:
            page_indices = {name: i for i, name in enumerate(self.page_order)}

            # Each save step is isolated: a failure in one page must NOT abort the
            # whole save (which used to leave write_config unreached, so nothing
            # persisted, and _is_saving stuck True so every later Save click was a
            # silent no-op). We log the real error and keep going so the rest of
            # current_config — including live color edits — still gets written.
            def _safe(label, fn):
                try:
                    fn()
                except Exception:
                    import traceback
                    err = traceback.format_exc()
                    print(f"[Onigiri] settings save step '{label}' failed:\n{err}")
                    try:
                        config.log_perf(f"SAVE ERROR [{label}]: {err}")
                    except Exception:
                        pass

            # Always save hide mode settings
            _safe("hide_modes", self._save_hide_modes_settings)

            if self.tabs_loaded.get(page_indices.get("Main menu")):
                _safe("main_menu", self._save_main_menu_settings)
                _safe("organize", self._save_organize_settings)
            if self.tabs_loaded.get(page_indices.get("Sidebar")):
                _safe("sidebar", self._save_sidebar_settings)
                _safe("sidebar_layout", self._save_sidebar_layout_settings)
            if self.tabs_loaded.get(page_indices.get("Overviewer")):
                _safe("overviewer", self._save_overviews_settings)
            if self.tabs_loaded.get(page_indices.get("Fonts")):
                _safe("fonts", self._save_fonts_settings)
            if self.tabs_loaded.get(page_indices.get("Profile")):
                _safe("profile", self._save_profile_settings)
            if self.tabs_loaded.get(page_indices.get("Reviewer")):
                _safe("reviewer", self._save_reviewer_settings)
            if self.tabs_loaded.get(page_indices.get("Languages")):
                _safe("languages", self._save_language_settings)
            if self.tabs_loaded.get(page_indices.get("Prep Station")):
                _safe("prep_station", self._save_prep_station_settings)
            if self.tabs_loaded.get(page_indices.get("Hashi Notes")):
                _safe("hashi_notes", self._save_hashi_notes_settings)
            if self.tabs_loaded.get(page_indices.get("Pomodoro")):
                _safe("pomodoro", self._save_pomodoro_settings)

            # Sync toggle is always present in memory; save unconditionally
            try:
                self.current_config["ankiweb_sync_enabled"] = self.ankiweb_sync_toggle.isChecked()
            except Exception:
                pass

            # When a theme is being applied but the Main menu tab was never opened,
            # propagate the theme's base background color to the menu bg colors.
            # This must ONLY run while applying a theme: otherwise every save made
            # from another tab would clobber the user's custom menu background with
            # the theme's plain --bg (a gray), which is the "reopen settings, change
            # anything, background turns gray" bug.
            if self._pending_theme_data is not None and not self.tabs_loaded.get(page_indices.get("Main menu")):
                light_bg_from_theme = self.current_config['colors']['light'].get('--bg')
                dark_bg_from_theme = self.current_config['colors']['dark'].get('--bg')

                if light_bg_from_theme:
                    mw.col.conf["modern_menu_bg_color_light"] = light_bg_from_theme
                if dark_bg_from_theme:
                    mw.col.conf["modern_menu_bg_color_dark"] = dark_bg_from_theme

            if self._pending_theme_data is not None:
                _safe("apply_theme", lambda: self._apply_theme_payload(
                    self._pending_theme_data, mark_pending=False, refresh_widgets=False))

            if not self.isMaximized() and not self.isFullScreen():
                self.current_config["window_settings"] = {
                    "width": self.width(),
                    "height": self.height(),
                }

            config.write_config(self.current_config)

            from .. import heatmap as _heatmap
            _heatmap.invalidate_heatmap_cache()
            from ..api import sidebar as _sidebar
            _sidebar._ICON_OVERRIDE_CACHE.clear()

            # Ensure Anki writes in-memory col.conf modifications to the database
            if hasattr(mw.col, "setMod"):
                mw.col.setMod()
            if hasattr(mw.col, "mark_changed"):
                mw.col.mark_changed()

            self.accept()
            self._refresh_anki_after_settings_save()
        finally:
            # Never leave the dialog wedged in a permanent "can't save" state.
            self._is_saving = False
