class ProfilePageMixin:
    def create_profile_tab(self):
        page, layout = self._create_scrollable_page()
        layout.setSpacing(15)

        details_section = SectionGroup("User Details", self)
        form_layout = QFormLayout()
        self.name_input = QLineEdit(self.current_config.get("userName", DEFAULTS["userName"]))
        form_layout.addRow("User Name:", self.name_input)

        # Birthday date picker
        accent_color = mw.col.conf.get("modern_menu_accent_color", "#007bff")
        self.birthday_input = BirthdayWidget(accent_color=accent_color)
        birthday_str = self.current_config.get("userBirthday", "")
        if birthday_str:
            try:
                birthday_date = QDate.fromString(birthday_str, "yyyy-MM-dd")
                if birthday_date.isValid():
                    self.birthday_input.setDate(birthday_date)
            except:
                pass

        form_layout.addRow("Birthday:", self.birthday_input)

        details_section.add_layout(form_layout)
        layout.addWidget(details_section)

        pic_section = SectionGroup("Profile Picture", self)
        self.galleries["profile_pic"] = {} 
        pic_section.add_widget(self._create_image_gallery_group("profile_pic", "user_files/profile", "modern_menu_profile_picture"))
        layout.addWidget(pic_section)

        # --- REBUILT PROFILE BAR BACKGROUND SECTION ---
        bg_section = SectionGroup("Profile Bar Background", self)

        # 1. Create Radio Buttons
        bg_mode = mw.col.conf.get("modern_menu_profile_bg_mode", "accent")
        mode_layout = QHBoxLayout()
        self.profile_bg_accent_radio = QRadioButton("Accent Color")
        self.profile_bg_custom_radio = QRadioButton("Custom Color")
        self.profile_bg_image_radio = QRadioButton("Image")
        mode_layout.addWidget(self.profile_bg_accent_radio)
        mode_layout.addWidget(self.profile_bg_custom_radio)
        mode_layout.addWidget(self.profile_bg_image_radio)
        mode_layout.addStretch()
        bg_section.add_layout(mode_layout)

        # 2. Create the panels for each radio button option
        # Panel for "Custom Color"
        self.profile_bg_color_group = QWidget()
        custom_color_layout = QVBoxLayout(self.profile_bg_color_group)
        custom_color_layout.setContentsMargins(0, 10, 0, 0)
        self.profile_bg_light_row = self._create_color_picker_row("Light Mode", mw.col.conf.get("modern_menu_profile_bg_color_light", "#EEEEEE"), "profile_bg_light")
        self.profile_bg_dark_row = self._create_color_picker_row("Dark Mode", mw.col.conf.get("modern_menu_profile_bg_color_dark", "#3C3C3C"), "profile_bg_dark")
        custom_color_layout.addLayout(self.profile_bg_light_row)
        custom_color_layout.addLayout(self.profile_bg_dark_row)
        custom_color_layout.addStretch(1)


        # Panel for "Image"
        self.galleries["profile_bg"] = {}
        self.profile_bg_image_group = self._create_image_gallery_group("profile_bg", "user_files/profile_bg", "modern_menu_profile_bg_image", is_sub_group=True)

        # 3. Use a QStackedWidget for flicker-free switching
        options_stack = QStackedWidget()
        options_stack.addWidget(QWidget()) # Index 0: A blank widget for "Accent Color"
        options_stack.addWidget(self.profile_bg_color_group)  # Index 1: Custom color panel
        options_stack.addWidget(self.profile_bg_image_group)   # Index 2: Image gallery panel
        bg_section.add_widget(options_stack)

        # 4. Connect radio buttons to the QStackedWidget
        self.profile_bg_accent_radio.clicked.connect(lambda: options_stack.setCurrentIndex(0))
        self.profile_bg_custom_radio.clicked.connect(lambda: options_stack.setCurrentIndex(1))
        self.profile_bg_image_radio.clicked.connect(lambda: options_stack.setCurrentIndex(2))

        # 5. Set the initial state
        if bg_mode == "custom":
            self.profile_bg_custom_radio.setChecked(True)
            options_stack.setCurrentIndex(1)
        elif bg_mode == "image":
            self.profile_bg_image_radio.setChecked(True)
            options_stack.setCurrentIndex(2)
        else: # accent
            self.profile_bg_accent_radio.setChecked(True)
            options_stack.setCurrentIndex(0)

        layout.addWidget(bg_section)
        # --- END OF REBUILT SECTION ---

        bar_color_section = SectionGroup("Level Bar Color", self)
        bar_color_mode = mw.col.conf.get("onigiri_profile_level_bar_mode", "theme")
        bar_mode_layout = QHBoxLayout()
        self.profile_level_bar_theme_radio = QRadioButton("Current Restaurant Theme")
        self.profile_level_bar_custom_radio = QRadioButton("Custom Color")
        self.profile_level_bar_theme_radio.setChecked(bar_color_mode == "theme")
        self.profile_level_bar_custom_radio.setChecked(bar_color_mode == "custom")
        bar_mode_layout.addWidget(self.profile_level_bar_theme_radio)
        bar_mode_layout.addWidget(self.profile_level_bar_custom_radio)
        bar_mode_layout.addStretch()
        bar_color_section.add_layout(bar_mode_layout)

        self.profile_level_bar_color_group = QWidget()
        bar_color_picker_layout = QVBoxLayout(self.profile_level_bar_color_group)
        bar_color_picker_layout.setContentsMargins(0, 10, 0, 0)
        self.profile_level_bar_custom_row = self._create_color_picker_row("Level Bar Custom Color", mw.col.conf.get("onigiri_profile_level_bar_custom_color", "#4CAF50"), "profile_level_bar_custom_color")
        bar_color_picker_layout.addLayout(self.profile_level_bar_custom_row)
        bar_color_section.add_widget(self.profile_level_bar_color_group)

        self.profile_level_bar_custom_radio.toggled.connect(self.toggle_profile_level_bar_options)
        self.toggle_profile_level_bar_options()
        layout.addWidget(bar_color_section)

        page_bg_section = SectionGroup("Profile Page Background", self)
        page_bg_mode = mw.col.conf.get("onigiri_profile_page_bg_mode", "color")
        page_mode_layout = QHBoxLayout()
        self.profile_page_bg_color_radio = QRadioButton("Solid Color"); self.profile_page_bg_gradient_radio = QRadioButton("Gradient")
        self.profile_page_bg_color_radio.setChecked(page_bg_mode == "color"); self.profile_page_bg_gradient_radio.setChecked(page_bg_mode == "gradient")
        page_mode_layout.addWidget(self.profile_page_bg_color_radio); page_mode_layout.addWidget(self.profile_page_bg_gradient_radio); page_mode_layout.addStretch(); page_bg_section.add_layout(page_mode_layout)

        self.profile_page_color_group = QWidget(); page_color_layout = QVBoxLayout(self.profile_page_color_group); page_color_layout.setContentsMargins(0, 10, 0, 0)
        self.profile_page_light_color_row = self._create_color_picker_row("Light Mode Color", mw.col.conf.get("onigiri_profile_page_bg_light_color1", "#F5F5F5"), "profile_page_light_color1"); page_color_layout.addLayout(self.profile_page_light_color_row)
        self.profile_page_dark_color_row = self._create_color_picker_row("Dark Mode Color", mw.col.conf.get("onigiri_profile_page_bg_dark_color1", "#2c2c2c"), "profile_page_dark_color1"); page_color_layout.addLayout(self.profile_page_dark_color_row); page_bg_section.add_widget(self.profile_page_color_group)

        self.profile_page_gradient_group = QWidget(); page_gradient_layout = QVBoxLayout(self.profile_page_gradient_group); page_gradient_layout.setContentsMargins(0, 10, 0, 0)
        self.profile_page_light_gradient1_row = self._create_color_picker_row("Light Mode From", mw.col.conf.get("onigiri_profile_page_bg_light_color1", "#FFFFFF"), "profile_page_light_gradient1"); page_gradient_layout.addLayout(self.profile_page_light_gradient1_row)
        self.profile_page_light_gradient2_row = self._create_color_picker_row("Light Mode To", mw.col.conf.get("onigiri_profile_page_bg_light_color2", "#E0E0E0"), "profile_page_light_gradient2"); page_gradient_layout.addLayout(self.profile_page_light_gradient2_row)
        self.profile_page_dark_gradient1_row = self._create_color_picker_row("Dark Mode From", mw.col.conf.get("onigiri_profile_page_bg_dark_color1", "#424242"), "profile_page_dark_gradient1"); page_gradient_layout.addLayout(self.profile_page_dark_gradient1_row)
        self.profile_page_dark_gradient2_row = self._create_color_picker_row("Dark Mode To", mw.col.conf.get("onigiri_profile_page_bg_dark_color2", "#212121"), "profile_page_dark_gradient2"); page_gradient_layout.addLayout(self.profile_page_dark_gradient2_row); page_bg_section.add_widget(self.profile_page_gradient_group)

        self.profile_page_bg_color_radio.toggled.connect(self.toggle_profile_page_bg_options); self.toggle_profile_page_bg_options(); layout.addWidget(page_bg_section)

        visibility_section = SectionGroup("Profile Page Sections Visibility", self)
        self.profile_show_theme_light_check = AnimatedToggleButton(accent_color=self.accent_color); self.profile_show_theme_light_check.setChecked(mw.col.conf.get("onigiri_profile_show_theme_light", True)); visibility_section.add_widget(self._create_toggle_row(self.profile_show_theme_light_check, "Show 'Theme Colors (Light)' Section"))
        self.profile_show_theme_dark_check = AnimatedToggleButton(accent_color=self.accent_color); self.profile_show_theme_dark_check.setChecked(mw.col.conf.get("onigiri_profile_show_theme_dark", True)); visibility_section.add_widget(self._create_toggle_row(self.profile_show_theme_dark_check, "Show 'Theme Colors (Dark)' Section"))
        self.profile_show_backgrounds_check = AnimatedToggleButton(accent_color=self.accent_color); self.profile_show_backgrounds_check.setChecked(mw.col.conf.get("onigiri_profile_show_backgrounds", True)); visibility_section.add_widget(self._create_toggle_row(self.profile_show_backgrounds_check, "Show 'Background Images' Section"))
        self.profile_show_stats_check = AnimatedToggleButton(accent_color=self.accent_color); self.profile_show_stats_check.setChecked(mw.col.conf.get("onigiri_profile_show_stats", True)); visibility_section.add_widget(self._create_toggle_row(self.profile_show_stats_check, "Show 'Daily Stats' Section"))

        # Restaurant Level visibility
        self.profile_show_restaurant_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.profile_show_restaurant_check.setChecked(restaurant_level.manager.get_progress().show_profile_page_progress)
        visibility_section.add_widget(self._create_toggle_row(self.profile_show_restaurant_check, "Show 'Restaurant Level' Section"))

        layout.addWidget(visibility_section)

        layout.addStretch()
        sections = {
            "User Details": details_section,
            "Profile Picture": pic_section,
            "Profile Bar Background": bg_section,
            "Level Bar Color": bar_color_section,
            "Profile Page Background": page_bg_section,
            "Profile Page Sections Visibility": visibility_section
        }
        self._add_navigation_buttons(page, page.findChild(QScrollArea), sections, buttons_per_row=3)

        return page


    def toggle_profile_page_bg_options(self): is_gradient = self.profile_page_bg_gradient_radio.isChecked(); self.profile_page_color_group.setVisible(not is_gradient); self.profile_page_gradient_group.setVisible(is_gradient)


    def toggle_profile_level_bar_options(self):
        self.profile_level_bar_color_group.setVisible(self.profile_level_bar_custom_radio.isChecked())


    def _save_profile_settings(self):
        self.current_config["userName"] = self.name_input.text()
        mw.col.conf["modern_menu_userName"] = self.name_input.text()

        # Save birthday in ISO format (YYYY-MM-DD)
        if hasattr(self, 'birthday_input'):
            birthday_date = self.birthday_input.date()
            if birthday_date.isValid():
                 self.current_config["userBirthday"] = birthday_date.toString("yyyy-MM-dd")
            else:
                 self.current_config["userBirthday"] = ""

        if 'profile_pic' in self.galleries:
            mw.col.conf["modern_menu_profile_picture"] = self.galleries['profile_pic']['selected']
        if 'profile_bg' in self.galleries:
            mw.col.conf["modern_menu_profile_bg_image"] = self.galleries['profile_bg']['selected']

        if self.profile_bg_image_radio.isChecked(): mw.col.conf["modern_menu_profile_bg_mode"] = "image"
        elif self.profile_bg_custom_radio.isChecked(): mw.col.conf["modern_menu_profile_bg_mode"] = "custom"
        else: mw.col.conf["modern_menu_profile_bg_mode"] = "accent"

        mw.col.conf["modern_menu_profile_bg_color_light"] = self.profile_bg_light_color_input.text()
        mw.col.conf["modern_menu_profile_bg_color_dark"] = self.profile_bg_dark_color_input.text()
        mw.col.conf["onigiri_profile_show_theme_light"] = self.profile_show_theme_light_check.isChecked()
        mw.col.conf["onigiri_profile_show_theme_dark"] = self.profile_show_theme_dark_check.isChecked()
        mw.col.conf["onigiri_profile_show_backgrounds"] = self.profile_show_backgrounds_check.isChecked()
        mw.col.conf["onigiri_profile_show_stats"] = self.profile_show_stats_check.isChecked()
        if self.profile_page_bg_gradient_radio.isChecked():
            mw.col.conf["onigiri_profile_page_bg_mode"] = "gradient"
            mw.col.conf["onigiri_profile_page_bg_light_color1"] = self.profile_page_light_gradient1_color_input.text()
            mw.col.conf["onigiri_profile_page_bg_light_color2"] = self.profile_page_light_gradient2_color_input.text()
            mw.col.conf["onigiri_profile_page_bg_dark_color1"] = self.profile_page_dark_gradient1_color_input.text()
            mw.col.conf["onigiri_profile_page_bg_dark_color2"] = self.profile_page_dark_gradient2_color_input.text()
        else:
            mw.col.conf["onigiri_profile_page_bg_mode"] = "color"
            mw.col.conf["onigiri_profile_page_bg_light_color1"] = self.profile_page_light_color1_color_input.text()
            mw.col.conf["onigiri_profile_page_bg_dark_color1"] = self.profile_page_dark_color1_color_input.text()

        # Profile Level Bar Color
        if hasattr(self, 'profile_level_bar_custom_radio'):
            if self.profile_level_bar_custom_radio.isChecked():
                mw.col.conf["onigiri_profile_level_bar_mode"] = "custom"
            else:
                mw.col.conf["onigiri_profile_level_bar_mode"] = "theme"
            if hasattr(self, 'profile_level_bar_custom_color_color_input'):
                mw.col.conf["onigiri_profile_level_bar_custom_color"] = self.profile_level_bar_custom_color_color_input.text()
        # Save Restaurant Level visibility
        restaurant_level.manager.set_profile_page_visibility(self.profile_show_restaurant_check.isChecked())


    def _save_achievements_settings(self):
        # Save restaurant_level to top-level config
        restaurant_conf = self.current_config.setdefault("restaurant_level", {})
        # Also ensure it's removed from achievements if present (cleanup)
        if "restaurant_level" in self.achievements_config:
            # We might want to preserve it there for a moment or just rely on the top level
            # But let's just make sure we are editing the top level one
            pass

        restaurant_enabled = self.restaurant_level_toggle.isChecked()
        restaurant_conf["enabled"] = restaurant_enabled
        restaurant_conf["notifications_enabled"] = self.restaurant_notifications_toggle.isChecked()
        restaurant_conf["show_profile_bar_progress"] = self.restaurant_bar_toggle.isChecked()
        # show_profile_page_progress is now saved in _save_profile_settings
        restaurant_conf["show_reviewer_header"] = self.restaurant_reviewer_toggle.isChecked()

        # Save Focus Dango setting
        focus_dango_conf = self.achievements_config.setdefault("focusDango", {})
        focus_dango_conf["enabled"] = self.focus_dango_toggle.isChecked()

        from ..gamification import focus_dango
        focus_dango.set_focus_dango_enabled(self.focus_dango_toggle.isChecked())



        # Save restaurant name if input exists
        if hasattr(self, 'restaurant_name_input'):
            new_name = self.restaurant_name_input.text().strip()
            if new_name:
                restaurant_level.manager.set_restaurant_name(new_name)
            else:
                restaurant_level.manager.set_restaurant_name("Restaurant Level")

        restaurant_level.manager.set_enabled(restaurant_enabled)
        restaurant_level.manager.set_notifications_enabled(restaurant_conf["notifications_enabled"])
        restaurant_level.manager.set_profile_bar_visibility(restaurant_conf["show_profile_bar_progress"])
        restaurant_level.manager.set_profile_page_visibility(restaurant_conf["show_profile_page_progress"])

        defaults = config.DEFAULTS["achievements"].get("custom_goals", {})
        custom_goals = self.achievements_config.setdefault(
            "custom_goals",
            copy.deepcopy(defaults),
        )
        custom_goals.setdefault("last_modified_at", defaults.get("last_modified_at"))

        previous_goals = copy.deepcopy(custom_goals)
        daily_prev = previous_goals.get("daily", {})
        weekly_prev = previous_goals.get("weekly", {})

        daily_enabled = self.daily_goal_toggle.isChecked()
        daily_target = self.daily_goal_spinbox.value()
        weekly_enabled = self.weekly_goal_toggle.isChecked()
        weekly_target = self.weekly_goal_spinbox.value()

        daily_changed = (
            bool(daily_prev.get("enabled", False)) != daily_enabled
            or int(daily_prev.get("target", 0)) != daily_target
        )
        weekly_changed = (
            bool(weekly_prev.get("enabled", False)) != weekly_enabled
            or int(weekly_prev.get("target", 0)) != weekly_target
        )
        changes_requested = daily_changed or weekly_changed

        if changes_requested:
            last_modified_at = previous_goals.get("last_modified_at")
            unlock_at = last_modified_at + CUSTOM_GOAL_COOLDOWN_SECONDS if last_modified_at else None
            remaining = (unlock_at - int(time.time())) if unlock_at else 0
            if remaining > 0:
                self._restore_custom_goal_inputs(previous_goals)
                self.achievements_config["custom_goals"] = previous_goals
                self._show_custom_goal_lock_warning(remaining, unlock_at)
                self._refresh_custom_goal_cooldown_label()
                return

        daily_conf = custom_goals.setdefault("daily", copy.deepcopy(defaults.get("daily", {})))
        daily_conf["enabled"] = daily_enabled
        daily_conf["target"] = daily_target
        daily_conf.setdefault("last_notified_day", daily_prev.get("last_notified_day"))
        daily_conf.setdefault("completion_count", daily_prev.get("completion_count", 0))

        weekly_conf = custom_goals.setdefault("weekly", copy.deepcopy(defaults.get("weekly", {})))
        weekly_conf["enabled"] = weekly_enabled
        weekly_conf["target"] = weekly_target
        weekly_conf.setdefault("last_notified_week", weekly_prev.get("last_notified_week"))
        weekly_conf.setdefault("completion_count", weekly_prev.get("completion_count", 0))

        if changes_requested:
            custom_goals["last_modified_at"] = int(time.time())
        else:
            custom_goals["last_modified_at"] = previous_goals.get("last_modified_at")

        self._refresh_custom_goal_cooldown_label()


    def _save_mochi_messages_settings(self) -> None:
        mochi_defaults = config.DEFAULTS.get("mochi_messages", {})
        mochi_conf = self.current_config.setdefault("mochi_messages", copy.deepcopy(mochi_defaults))

        mochi_conf["enabled"] = self.mochi_messages_toggle.isChecked()
        mochi_conf["cards_interval"] = max(1, int(self.mochi_interval_spinbox.value()))

        raw_text = self.mochi_messages_editor.toPlainText()
        messages = [line.strip() for line in raw_text.splitlines() if line.strip()]
        if not messages:
            messages = copy.deepcopy(mochi_defaults.get("messages", []))
        mochi_conf["messages"] = messages


    def _save_focus_dango_settings(self) -> None:
        if not hasattr(self, 'focus_dango_message_editor'):
            # Page was never loaded, so don't save
            return

        focus_dango_defaults = config.DEFAULTS.get("achievements", {}).get("focusDango", {})
        focus_dango_conf = self.achievements_config.setdefault("focusDango", copy.deepcopy(focus_dango_defaults))

        # --- START MODIFICATION ---
        raw_text = self.focus_dango_message_editor.toPlainText()
        messages = [line.strip() for line in raw_text.splitlines() if line.strip()]

        if not messages:
            # Fallback to new default "messages" list
            messages = copy.deepcopy(focus_dango_defaults.get("messages", []))
            # If that's empty, try old default "message" string
            if not messages:
                old_default_message = focus_dango_defaults.get("message")
                if isinstance(old_default_message, str) and old_default_message:
                    messages = [old_default_message]
            # If still empty, use hardcoded default
            if not messages:
                messages = ["Don't give up!", "Stay focused!", "Almost there!"]

        focus_dango_conf["messages"] = messages

        # Clean up old "message" key if it exists
        if "message" in focus_dango_conf:
            del focus_dango_conf["message"]
        # --- END MODIFICATION ---


    def _custom_goal_cooldown_state(self):
        custom_goals = self.achievements_config.get("custom_goals", {})
        last_modified = custom_goals.get("last_modified_at")
        if not last_modified:
            return 0, None
        unlock_at = last_modified + CUSTOM_GOAL_COOLDOWN_SECONDS
        remaining = max(0, unlock_at - int(time.time()))
        return remaining, unlock_at


    def _format_duration(self, seconds):
        total_seconds = max(0, int(seconds))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        parts = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if not parts:
            parts.append("less than a minute")
        return " ".join(parts)


    def _refresh_custom_goal_cooldown_label(self):
        label = getattr(self, "custom_goal_cooldown_label", None)
        if not label:
            return
        remaining, unlock_at = self._custom_goal_cooldown_state()
        if remaining <= 0 or not unlock_at:
            message = "You can update your Custom Goals right now."
        else:
            duration = self._format_duration(remaining)
            available_time = datetime.fromtimestamp(unlock_at).strftime("%b %d, %Y %I:%M %p")
            message = f"You can update your Custom Goals again in {duration} (after {available_time})."
        label.setText(message)


    def _restore_custom_goal_inputs(self, goals_conf):
        daily_conf = goals_conf.get("daily", {})
        weekly_conf = goals_conf.get("weekly", {})

        self.daily_goal_toggle.setChecked(bool(daily_conf.get("enabled", False)))
        self.daily_goal_spinbox.setValue(int(daily_conf.get("target", 0)))

        self.weekly_goal_toggle.setChecked(bool(weekly_conf.get("enabled", False)))
        self.weekly_goal_spinbox.setValue(int(weekly_conf.get("target", 0)))


    def _show_custom_goal_lock_warning(self, remaining_seconds, unlock_at):
        duration = self._format_duration(remaining_seconds)
        if unlock_at:
            available_time = datetime.fromtimestamp(unlock_at).strftime("%b %d, %Y %I:%M %p")
            message = (
                "Custom Goals can be updated once every 24 hours.\n"
                f"You can make adjustments again in {duration} (after {available_time})."
            )
        else:
            message = (
                "Custom Goals can be updated once every 24 hours.\n"
                "Please try again soon."
            )
        showInfo(message)


