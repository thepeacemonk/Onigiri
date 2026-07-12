# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._widgets import *
from ._layout_base import *
from ._layout_main import *
from ._layout_sidebar import *


class HoldToResetButton(QPushButton):
    """A pill button that must be pressed and held to fire.

    A fill sweeps across the button while held; releasing early cancels it.
    Releasing after the fill completes emits `hold_completed`.
    """

    hold_completed = pyqtSignal()

    def __init__(self, text, hold_duration_ms=800, parent=None):
        super().__init__(text, parent)
        self._hold_duration_ms = hold_duration_ms
        self._tick_ms = 16
        self._progress = 0.0
        self._pressed = False
        self._base_color = QColor(Qt.GlobalColor.transparent)
        self._fill_color = QColor("#00A982")
        self._border_color = QColor("#dcdde1")
        self._hover_color = QColor("#dcdde1")
        self._text_color = QColor("#202124")
        self._hover_text_color = QColor("#202124")
        self._hovered = False
        self._timer = QTimer(self)
        self._timer.setInterval(self._tick_ms)
        self._timer.timeout.connect(self._on_tick)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAutoDefault(False)
        self.setDefault(False)
        self.setFlat(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        # Fully custom-painted (see paintEvent) so no native button chrome
        # (focus ring, pressed flash) can appear as a square over the pill.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("QPushButton { background: transparent; border: none; }")

    def set_fill_color(self, color):
        qcolor = QColor(color)
        if qcolor.isValid():
            self._fill_color = qcolor
            self.update()

    def set_base_color(self, color):
        qcolor = QColor(color)
        if qcolor.isValid():
            self._base_color = qcolor
            self.update()

    def set_border_color(self, color, hover_color=None):
        qcolor = QColor(color)
        if qcolor.isValid():
            self._border_color = qcolor
            self._hover_color = QColor(hover_color) if hover_color and QColor(hover_color).isValid() else qcolor
            self.update()

    def set_text_color(self, color, hover_color=None):
        qcolor = QColor(color)
        if qcolor.isValid():
            self._text_color = qcolor
            self._hover_text_color = QColor(hover_color) if hover_color and QColor(hover_color).isValid() else qcolor
            self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def _on_tick(self):
        self._progress = min(1.0, self._progress + self._tick_ms / self._hold_duration_ms)
        self.update()
        if self._progress >= 1.0:
            self._timer.stop()

    def _cancel_hold(self):
        self._pressed = False
        self._timer.stop()
        self._progress = 0.0
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self._pressed = True
            self._progress = 0.0
            self._timer.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._pressed:
            completed = self._progress >= 1.0
            self._cancel_hold()
            if completed:
                self.hold_completed.emit()
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        if self._pressed:
            self._cancel_hold()
        else:
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        # Entirely self-painted (background, border, and text) so no native
        # button chrome (focus ring, "pressed" flash) can appear as a square
        # over the rounded pill in any state.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        border_width = 1.0
        rect = QRectF(self.rect()).adjusted(border_width / 2, border_width / 2, -border_width / 2, -border_width / 2)
        radius = rect.height() / 2
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)

        painter.save()
        painter.setClipPath(path)
        painter.fillRect(self.rect(), self._base_color)
        if self._progress > 0:
            fill_rect = QRectF(rect.x(), rect.y(), rect.width() * self._progress, rect.height())
            painter.fillRect(fill_rect, self._fill_color)
        painter.restore()

        pen = painter.pen()
        pen.setWidthF(border_width)
        pen.setColor(self._hover_color if self._hovered else self._border_color)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        painter.setPen(self._hover_text_color if self._hovered else self._text_color)
        painter.setFont(self.font())
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        painter.end()


class PageThemesMixin:
    def _theme_action_button_stylesheet(self, height=36):
        palette = self._settings_palette()
        bg = palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        hover_bg = palette.get("--hover-bg", "#3a3a3a" if theme_manager.night_mode else "#e9e9e9")
        border = palette.get("--border", "#454545" if theme_manager.night_mode else "#dcdde1")
        fg = palette.get("--fg", "#f4f4f5" if theme_manager.night_mode else "#202124")
        accent = palette.get("--accent-color", DEFAULTS["colors"]["dark" if theme_manager.night_mode else "light"]["--accent-color"])
        radius = height // 2
        return f"""
            QPushButton {{
                min-height: {height}px;
                max-height: {height}px;
                padding: 0 20px;
                border: 1px solid {border};
                border-radius: {radius}px;
                background: {bg};
                color: {fg};
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: {hover_bg};
                border-color: {accent};
                border-radius: {radius}px;
            }}
            QPushButton:pressed {{
                background: {accent};
                border-color: {accent};
                border-radius: {radius}px;
                color: #ffffff;
            }}
        """

    def _themed_icon(self, filename, color=None, size=24):
        icon_path = system_icon_path(filename)
        if not os.path.exists(icon_path):
            return QIcon()

        icon = QIcon(icon_path)
        pixmap = icon.pixmap(size, size)
        if pixmap.isNull():
            return icon

        tint = QColor(color or self._settings_icon_color())
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), tint)
        painter.end()
        return QIcon(pixmap)

    def _create_theme_mode_panel(self, title, mode_key):
        panel = QFrame()
        panel.setObjectName(f"themeModePanel_{mode_key}")
        panel.setMinimumWidth(0)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        if mode_key == "dark":
            bg = "#20242b"
            border = "#4b5563"
            title_color = "#f9fafb"
            body_color = "#d1d5db"
            stripe = self.current_config.get("colors", {}).get("dark", {}).get("--accent-color", self.accent_color)
        else:
            bg = "#ffffff"
            border = "#d1d5db"
            title_color = "#111827"
            body_color = "#4b5563"
            stripe = self.current_config.get("colors", {}).get("light", {}).get("--accent-color", self.accent_color)

        panel.setStyleSheet(f"""
            QFrame#themeModePanel_{mode_key} {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 24px;
            }}
            QFrame#themeModePanel_{mode_key} QLabel {{
                color: {body_color};
                background: transparent;
            }}
            QFrame#themeModePanel_{mode_key} QLabel#themeModePanelTitle {{
                color: {title_color};
                font-weight: 500;
                font-size: 13px;
            }}
            QFrame#themeModePanel_{mode_key} QLineEdit {{
                color: {title_color};
                background-color: {'#2f3540' if mode_key == 'dark' else '#f9fafb'};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            QFrame#themeModePanel_{mode_key} QPushButton#galleryActionButton {{
                color: {title_color};
                border-color: {border};
            }}
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        stripe_widget = QFrame()
        stripe_widget.setFixedSize(4, 18)
        stripe_widget.setStyleSheet(f"background-color: {stripe}; border-radius: 2px;")
        title_label = QLabel(title)
        title_label.setObjectName("themeModePanelTitle")
        title_label.setWordWrap(True)
        title_label.setMinimumWidth(0)
        title_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        header.addWidget(stripe_widget)
        header.addWidget(title_label, 1)
        header.addStretch()
        layout.addLayout(header)

        return panel, layout

    def _refresh_theme_dependent_widgets(self):
        for toggle in self.findChildren(AnimatedToggleButton):
            toggle.setAccentColor(self.accent_color)
            toggle.setThemeMode(theme_manager.night_mode)

        palette = self._settings_palette()
        sync_icon_bg = palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        sync_icon_border = palette.get("--border", "#454545" if theme_manager.night_mode else "#e5e7eb")
        for sync_icon in self.findChildren(SyncHeaderIcon):
            sync_icon.setColors(self.accent_color, sync_icon_bg, sync_icon_border, self._settings_icon_color())

        for overlay in self.findChildren(SelectionOverlay):
            overlay.setAccentColor(self.accent_color)

        slider_palette = palette
        slider_track = slider_palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        slider_border = slider_palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")
        for slider in self.findChildren(MainBackgroundEffectSlider):
            slider.setColors(self.accent_color, slider_track, slider_border)

        if hasattr(self, "profile_bar"):
            if hasattr(self.profile_bar, "setAccentColor"):
                self.profile_bar.setAccentColor(self.accent_color)
            elif hasattr(self.profile_bar, "refresh_theme"):
                self.profile_bar.refresh_theme()

        for button in self.findChildren(QPushButton):
            icon_name = button.property("onigiri_icon_filename")
            icon_size = button.property("onigiri_icon_size")
            if icon_name:
                size = int(icon_size or 18)
                icon_color = self._save_button_icon_color() if button.property("onigiri_icon_role") == "save" else self._settings_icon_color()
                button.setIcon(self._themed_icon(icon_name, icon_color, size))
        self._ensure_rounded_buttons()

    def _update_overview_bg_color_theme_mode_visibility(self):
        """Update visibility of single/separate color pickers for overview background based on theme mode selection."""
        is_single = self.overview_bg_color_theme_mode_single.isChecked()
        self.overview_bg_single_color_container.setVisible(is_single)
        self.overview_bg_separate_colors_container.setVisible(not is_single)
        
        # If switching to single theme mode, update the single color picker with light mode color
        if is_single and hasattr(self, 'overview_bg_light_color_row'):
            light_color = self.overview_bg_light_color_row.itemAt(1).widget().text()
            self.overview_bg_single_color_row.itemAt(1).widget().setText(light_color)

    def _update_overview_bg_image_theme_mode_visibility(self):
        """Update visibility of single/separate image galleries for overview background based on theme mode selection."""
        is_single = self.overview_bg_image_theme_mode_single.isChecked()
        self.overview_bg_single_image_container.setVisible(is_single)
        self.overview_bg_separate_images_container.setVisible(not is_single)
        
        # If switching to single theme mode, update the single gallery with light mode image
        if is_single and 'overview_bg_light' in self.galleries and 'overview_bg_single' in self.galleries:
            light_image = self.galleries['overview_bg_light'].get('selected', '')
            if light_image and 'path_input' in self.galleries['overview_bg_single']:
                self.galleries['overview_bg_single']['selected'] = light_image
                self.galleries['overview_bg_single']['path_input'].setText(light_image)

    def _update_reviewer_bg_color_theme_mode_visibility(self):
        """Update visibility of single/separate color pickers for reviewer background based on theme mode selection."""
        is_single = self.reviewer_bg_color_theme_mode_single.isChecked()
        self.reviewer_bg_single_color_container.setVisible(is_single)
        self.reviewer_bg_separate_colors_container.setVisible(not is_single)
        
        # If switching to single theme mode, update the single color picker with light mode color
        if is_single and hasattr(self, 'reviewer_bg_light_color_row'):
            light_color = self.reviewer_bg_light_color_row.itemAt(1).widget().text()
            self.reviewer_bg_single_color_row.itemAt(1).widget().setText(light_color)

    def _update_reviewer_bg_image_theme_mode_visibility(self):
        """Update visibility of single/separate image galleries for reviewer background based on theme mode selection."""
        is_single = self.reviewer_bg_image_theme_mode_single.isChecked()
        self.reviewer_bg_single_image_container.setVisible(is_single)
        self.reviewer_bg_separate_images_container.setVisible(not is_single)
        
        # If switching to single theme mode, update the single gallery with light mode image
        if is_single and 'reviewer_bg_light' in self.galleries and 'reviewer_bg_single' in self.galleries:
            light_image = self.galleries['reviewer_bg_light'].get('selected', '')
            if light_image and 'path_input' in self.galleries['reviewer_bg_single']:
                self.galleries['reviewer_bg_single']['selected'] = light_image
                self.galleries['reviewer_bg_single']['path_input'].setText(light_image)

    def _ensure_ui_for_theme_application(self):
        if not hasattr(self, 'light_accent_color_input'):
            dummy_gallery_page = self.create_gallery_page()
            dummy_gallery_page.deleteLater()
        
        if not hasattr(self, 'color_radio') and not hasattr(self, 'main_bg_color_only_toggle'):
            dummy_bg_page = self.create_main_menu_page()
            dummy_bg_page.deleteLater()

    def _update_color_theme_visibility(self):
        """Update visibility of single/separate color pickers with animation."""
        is_single = self.color_theme_single_radio.isChecked()
        is_separate = self.color_theme_separate_radio.isChecked()
        # is_accent = self.color_theme_accent_radio.isChecked() # Implicitly true if neither above is true

        target_widget = None
        if is_single:
            target_widget = self.bg_color_single_container
        elif is_separate:
            target_widget = self.bg_color_separate_container
        
        # Determine what to hide
        # We must NOT check isVisible() here, because during initialization (before dialog is shown),
        # isVisible() returns False for everything, causing nothing to be added to this list,
        # and thus nothing gets hidden.
        widgets_to_hide = []
        if self.bg_color_single_container is not target_widget:
            widgets_to_hide.append(self.bg_color_single_container)
        if self.bg_color_separate_container is not target_widget:
            widgets_to_hide.append(self.bg_color_separate_container)

        # Optimization: If dialog is not visible (initialization), just set visibility and return.
        # This prevents unnecessary animations and ensures correct initial state.
        if not self.isVisible():
            for w in widgets_to_hide:
                w.setVisible(False)
            if target_widget:
                target_widget.setVisible(True)
                target_widget.setMaximumHeight(16777215)
            return

        # If target is already visible and nothing to hide, we are done
        if target_widget and target_widget.isVisible() and not widgets_to_hide:
            return
        # If no target and nothing to hide (already in accent mode), done
        if not target_widget and not widgets_to_hide:
            return

        # Atomic update to prevent flickering
        self.setUpdatesEnabled(False)
        start_height = 0
        try:
            # Hide unwanted widgets and capture height
            for w in widgets_to_hide:
                if w.isVisible():
                    start_height = max(start_height, w.height())
                w.setVisible(False)
            
            if target_widget:
                # Prepare target widget
                # IMPORTANT: Set max height BEFORE showing to prevent flickering/jumping
                target_widget.setMaximumHeight(start_height)
                target_widget.setVisible(True)
                target_widget.updateGeometry()
                
                # Calculate target height
                target_height = target_widget.sizeHint().height()
                if target_height < 50: target_height = 100 # Fallback
        finally:
            self.setUpdatesEnabled(True)
        
        if target_widget:
            self.color_anim = QPropertyAnimation(target_widget, b"maximumHeight")
            self.color_anim.setDuration(250)
            self.color_anim.setStartValue(start_height)
            self.color_anim.setEndValue(target_height)
            self.color_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            self.color_anim.finished.connect(lambda: target_widget.setMaximumHeight(16777215))
            self.color_anim.start()

    def _update_image_theme_visibility(self):
        """Update visibility of single/separate image galleries with animation."""
        is_single = self.image_theme_single_radio.isChecked()
        target_widget = self.bg_image_single_container if is_single else self.bg_image_separate_container
        other_widget = self.bg_image_separate_container if is_single else self.bg_image_single_container
        
        if target_widget.isVisible():
            return

        # Atomic update to prevent flickering
        self.setUpdatesEnabled(False)
        try:
            # Capture start height from the currently visible widget
            start_height = other_widget.height() if other_widget.isVisible() else 0
            other_widget.setVisible(False)
            
            # Prepare target widget
            # IMPORTANT: Set max height BEFORE showing to prevent flickering/jumping
            target_widget.setMaximumHeight(start_height)
            target_widget.setVisible(True)
            target_widget.updateGeometry()
            
            target_height = target_widget.sizeHint().height()
            if target_height < 100: target_height = 300 # Fallback
        finally:
            self.setUpdatesEnabled(True)
        
        self.image_anim = QPropertyAnimation(target_widget, b"maximumHeight")
        self.image_anim.setDuration(250)
        self.image_anim.setStartValue(start_height)
        self.image_anim.setEndValue(target_height)
        self.image_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.image_anim.finished.connect(lambda: target_widget.setMaximumHeight(16777215))
        self.image_anim.start()

    def _create_theme_preview_mode_widget(self):
        widget, toggle = self._create_light_dark_mode_toggle(
            self.theme_preview_mode,
            self._on_theme_preview_mode_toggled,
        )
        self.theme_preview_mode_toggle = toggle
        return widget

    def _theme_reset_hold_button_font_stylesheet(self, height=32):
        # Font/sizing only: HoldToResetButton paints its own background, border,
        # and text (see its paintEvent), so background/border/color must NOT be
        # set here or they'd reintroduce native button chrome on top of it.
        return f"""
            QPushButton {{
                background: transparent;
                border: none;
                min-height: {height}px;
                max-height: {height}px;
                padding: 0px 16px;
                font-size: 12px;
                font-weight: 700;
            }}
        """

    def _create_theme_header_actions_widget(self):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self._create_theme_preview_mode_widget())

        palette = self._settings_palette()
        reset_bg = palette.get("--canvas-inset", "#242424" if theme_manager.night_mode else "#ffffff")
        border = palette.get("--border", "#454545" if theme_manager.night_mode else "#dcdde1")
        fg = palette.get("--fg-subtle", "#b7bcc5" if theme_manager.night_mode else "#6f7177")
        active_fg = palette.get("--fg", "#f4f4f5" if theme_manager.night_mode else "#202124")
        accent = palette.get("--accent-color", DEFAULTS["colors"]["dark" if theme_manager.night_mode else "light"]["--accent-color"])

        reset_button = HoldToResetButton(tr("reset_theme_to_default"), hold_duration_ms=800)
        reset_button.setToolTip(tr("reset_theme_tooltip"))
        reset_button.setFixedHeight(32)
        reset_button.setStyleSheet(self._theme_reset_hold_button_font_stylesheet())
        reset_button.set_base_color(reset_bg)
        reset_button.set_fill_color(accent)
        reset_button.set_border_color(border, accent)
        reset_button.set_text_color(fg, active_fg)
        reset_button.hold_completed.connect(self._reset_theme_to_default_with_toast)
        self.theme_reset_button = reset_button
        layout.addWidget(reset_button)

        return widget

    def create_themes_page(self):
        page, layout = self._create_scrollable_page()

        # --- Load Themes ---
        official_themes, user_themes = self._load_themes()
        self.theme_preview_mode = "dark" if theme_manager.night_mode else "light"
        self.theme_preview_cards = []
        self.theme_preview_mode_widget = self._create_theme_header_actions_widget()

        # --- Section 1: Your Themes ---
        user_section = SectionGroup(
            tr("your_themes"),
            self,
            border=True,
            description=f"{tr('your_themes_desc')} {tr('hold_to_delete', 'Hold to delete')}."
        )
        theme_actions = QWidget()
        theme_actions_layout = QHBoxLayout(theme_actions)
        theme_actions_layout.setContentsMargins(0, 0, 0, 0)
        theme_actions_layout.setSpacing(8)

        theme_action_height = 36
        import_button = QPushButton(tr("import_theme"))
        import_button.setCursor(Qt.CursorShape.PointingHandCursor)
        import_button.setStyleSheet(self._theme_action_button_stylesheet(theme_action_height))
        import_button.setFixedHeight(theme_action_height)
        import_button.clicked.connect(self._import_theme)

        export_button = QPushButton(tr("export_theme"))
        export_button.setCursor(Qt.CursorShape.PointingHandCursor)
        export_button.setStyleSheet(self._theme_action_button_stylesheet(theme_action_height))
        export_button.setFixedHeight(theme_action_height)
        export_button.setToolTip(tr("export_theme_tooltip"))
        export_button.clicked.connect(self._export_current_theme)

        theme_actions_layout.addWidget(import_button)
        theme_actions_layout.addWidget(export_button)
        user_section.add_header_widget(theme_actions)

        self.user_themes_grid_layout = FlowLayout(spacing=15, stretch_rows=True)
        user_section.add_layout(self.user_themes_grid_layout)
        self._populate_grid_with_themes(self.user_themes_grid_layout, user_themes, deletable=True)
        layout.addWidget(user_section)

        # --- Section 2: Official Themes ---
        official_section = SectionGroup(
            tr("official_themes"),
            self,
            border=True,
            description=tr("official_themes_desc")
        )
        self.official_themes_grid_layout = FlowLayout(spacing=15, stretch_rows=True)
        official_section.add_layout(self.official_themes_grid_layout)
        self._populate_grid_with_themes(self.official_themes_grid_layout, official_themes, deletable=False)
        layout.addWidget(official_section)

        return page

    def _on_theme_preview_mode_toggled(self, mode):
        if isinstance(mode, str):
            self.theme_preview_mode = "dark" if mode == "dark" else "light"
        else:
            self.theme_preview_mode = "dark" if mode else "light"
        for card in getattr(self, "theme_preview_cards", []):
            try:
                card.set_preview_mode(self.theme_preview_mode)
            except RuntimeError:
                continue

    def _theme_asset_config_value(self, path_value):
        values = path_value if isinstance(path_value, list) else [path_value]
        filenames = []
        for value in values:
            if not isinstance(value, str):
                continue
            filename = os.path.basename(value.strip())
            if filename:
                filenames.append(filename)
        if not filenames:
            return None
        return filenames if isinstance(path_value, list) else filenames[0]

    def _apply_theme_payload(self, theme_data: dict, *, mark_pending=False, refresh_widgets=True):
        """Applies every persisted part of a theme to the in-memory configs."""
        if not isinstance(theme_data, dict):
            return

        light_palette = theme_data.get("light", {})
        dark_palette = theme_data.get("dark", {})
        if not isinstance(light_palette, dict):
            light_palette = {}
        if not isinstance(dark_palette, dict):
            dark_palette = {}
        assets = theme_data.get("assets", {})
        if not isinstance(assets, dict):
            assets = {}
        customization = theme_data.get("customization", {})
        customization_collection = (
            customization.get("collection_config", {})
            if isinstance(customization, dict)
            else {}
        )
        if not isinstance(customization_collection, dict):
            customization_collection = {}
        addon_keys, collection_keys = self._theme_customization_key_groups()
        addon_key_set = set(addon_keys)
        collection_key_set = set(collection_keys)

        # 1. Update the internal config dictionary
        self.current_config["colors"]["light"].update(light_palette)
        self.current_config["colors"]["dark"].update(dark_palette)
        
        # 1b. Apply Assets (Images and Icons)
        if isinstance(assets.get("images"), dict):
            for config_key, path_value in assets["images"].items():
                config_value = self._theme_asset_config_value(path_value)
                if config_value is None:
                    continue
                if (
                    config_key in addon_key_set
                    or config_key in self.current_config
                    or config_key.startswith("onigiri_")
                ):
                    self.current_config[config_key] = copy.deepcopy(config_value)
                if config_key in collection_key_set or config_key.startswith("modern_menu_"):
                    mw.col.conf[config_key] = copy.deepcopy(config_value)
                    
        if isinstance(assets.get("icon_config"), dict):
            for icon_key, icon_value in assets["icon_config"].items():
                conf_key = f"modern_menu_icon_{icon_key}"
                filename = os.path.basename(str(icon_value)) if icon_value else ""
                mw.col.conf[conf_key] = "" if not filename or filename == str(icon_key) else filename

        if isinstance(assets.get("icons"), dict):
            for icon_key, icon_value in assets["icons"].items():
                # icon_value should be just the filename (from import)
                # But use basename to be safe
                filename = os.path.basename(icon_value) if icon_value else ""
                if filename:
                    conf_key = f"modern_menu_icon_{icon_key}"
                    mw.col.conf[conf_key] = filename

        # 1c. Apply Fonts
        if isinstance(assets.get("font_config"), dict):
            for type_key, font_key in assets["font_config"].items():
                if type_key in ["main", "subtle", "small_title"]:
                    mw.col.conf[f"onigiri_font_{type_key}"] = font_key
                elif isinstance(type_key, str) and type_key.startswith("size_"):
                    mw.col.conf[f"onigiri_font_{type_key}"] = font_key

        # 1d. Apply Reviewer Settings
        if isinstance(theme_data.get("reviewer_settings"), dict):
            self.current_config.update(theme_data["reviewer_settings"])

        if "modern_menu_bg_color_light" not in customization_collection and light_palette.get("--bg"):
            mw.col.conf["modern_menu_bg_color_light"] = light_palette["--bg"]
        if "modern_menu_bg_color_dark" not in customization_collection and dark_palette.get("--bg"):
            mw.col.conf["modern_menu_bg_color_dark"] = dark_palette["--bg"]

        # Keep the Sidebar and Box Color and Effect backgrounds tied to the
        # applied theme's --bg, so both update on every theme switch and stay
        # equal to each other, unless the theme file customizes them itself.
        customization_addon = (
            customization.get("addon_config", {}) if isinstance(customization, dict) else {}
        )
        if not isinstance(customization_addon, dict):
            customization_addon = {}
        overview_colors = self.current_config.setdefault("overview_style", {}).setdefault("colors", {})
        for mode, palette in (("light", light_palette), ("dark", dark_palette)):
            theme_bg = palette.get("--bg")
            if not theme_bg:
                continue
            if "overview_style" not in customization_addon:
                overview_colors.setdefault(mode, {})["box_bg"] = theme_bg
            sidebar_key = f"modern_menu_sidebar_bg_color_{mode}"
            if sidebar_key not in customization_collection:
                mw.col.conf[sidebar_key] = theme_bg

        self._apply_theme_customization(customization)

        if mark_pending:
            self._pending_theme_data = copy.deepcopy(theme_data)
            self._theme_prepare_save_in_progress = False

        if not refresh_widgets:
            return

        # 2. Update the UI widgets on other pages in real-time
        # This uses hasattr to avoid errors if a page hasn't been loaded yet
        
        # Update Palette page
        for mode, palette in [("light", light_palette), ("dark", dark_palette)]:
            if mode in self.color_widgets:
                for key, widget in self.color_widgets[mode].items():
                    if key in palette:
                        widget.setText(palette[key])
        
        # Update Accent colors
        if hasattr(self, "light_accent_color_input") and "--accent-color" in light_palette:
            self.light_accent_color_input.setText(light_palette["--accent-color"])
        if hasattr(self, "dark_accent_color_input") and "--accent-color" in dark_palette:
            self.dark_accent_color_input.setText(dark_palette["--accent-color"])
            
        # Update Backgrounds page
        if hasattr(self, "bg_light_color_input") and "--bg" in light_palette:
            self.bg_light_color_input.setText(light_palette["--bg"])
        if hasattr(self, "bg_dark_color_input") and "--bg" in dark_palette:
            self.bg_dark_color_input.setText(dark_palette["--bg"])
        if hasattr(self, "main_bg_light_color_input") and "--bg" in light_palette:
            self.main_bg_light_color_input.setText(light_palette["--bg"])
        if hasattr(self, "main_bg_dark_color_input") and "--bg" in dark_palette:
            self.main_bg_dark_color_input.setText(dark_palette["--bg"])

        # Update Sidebar Settings page inputs so a later Save doesn't overwrite
        # the synced color with stale widget text.
        if hasattr(self, "sidebar_bg_light_color_input") and "--bg" in light_palette:
            self.sidebar_bg_light_color_input.setText(light_palette["--bg"])
        if hasattr(self, "sidebar_bg_dark_color_input") and "--bg" in dark_palette:
            self.sidebar_bg_dark_color_input.setText(dark_palette["--bg"])

        # Update Box Color and Effect inputs (Overview page) likewise.
        if hasattr(self, "overview_style_color_inputs"):
            for mode, palette in (("light", light_palette), ("dark", dark_palette)):
                theme_bg = palette.get("--bg")
                if not theme_bg:
                    continue
                box_widget = self.overview_style_color_inputs.get(("box_bg", mode))
                if box_widget is not None:
                    box_widget.setText(theme_bg)
            if hasattr(self, "_update_overview_style_controls"):
                self._update_overview_style_controls()

        # Update Icon previews after applying icons
        if "icons" in assets and hasattr(self, "icon_widgets"):
            for icon_key in assets["icons"].keys():
                if icon_key in self.icon_widgets:
                    control_widget = self.icon_widgets[icon_key]
                    preview_label = getattr(control_widget, "_onigiri_preview_label", None)
                    if preview_label:
                        # Reload the icon preview
                        conf_key = f"modern_menu_icon_{icon_key}"
                        new_filename = mw.col.conf.get(conf_key, "")
                        if new_filename:
                            icon_path = os.path.join(self.addon_path, "user_files", "icons", new_filename)
                            if os.path.exists(icon_path):
                                # Update preview with new icon
                                pixmap = QPixmap(icon_path)
                                if not pixmap.isNull():
                                    scaled = pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                                    preview_label.setPixmap(scaled)

    def _apply_theme(self, theme_data: dict, theme_name: str = None):
        """Applies the selected theme's colors and assets to the config and live UI."""
        self._apply_theme_payload(theme_data, mark_pending=True, refresh_widgets=True)
        self._show_theme_selected_toast(theme_name)

    def _show_theme_selected_toast(self, theme_name):
        if theme_name:
            text = f"{tr('theme_applied_toast', 'Theme selected:')} {theme_name}"
        else:
            text = tr("theme_applied_toast_generic", "Theme selected")
        show_settings_toast(self, text)

    def _theme_customization_key_groups(self):
        explicit_addon_keys = [
            "markerColors",
            "overview_style",
            "showOverviewProfileBar",
            "showCongratsProfileBar",
            "congratsMessage",
            "studyNowText",
            "hideRetentionStars",
            "onigiri_overview_bg_mode",
            "onigiri_overview_bg_main_blur",
            "onigiri_overview_bg_main_opacity",
            "onigiri_overview_bg_light_color",
            "onigiri_overview_bg_dark_color",
            "onigiri_overview_bg_image",
            "onigiri_overview_bg_image_light",
            "onigiri_overview_bg_image_dark",
            "onigiri_overview_bg_image_mode",
            "onigiri_overview_bg_color_theme_mode",
            "onigiri_overview_bg_image_theme_mode",
            "onigiri_overview_bg_blur",
            "onigiri_overview_bg_opacity",
            "onigiri_overview_slideshow_images",
            "onigiri_overview_slideshow_interval",
            "onigiri_reviewer_bg_mode",
            "onigiri_reviewer_bg_main_blur",
            "onigiri_reviewer_bg_main_opacity",
            "onigiri_reviewer_bg_light_color",
            "onigiri_reviewer_bg_dark_color",
            "onigiri_reviewer_bg_image",
            "onigiri_reviewer_bg_image_light",
            "onigiri_reviewer_bg_image_dark",
            "onigiri_reviewer_bg_image_mode",
            "onigiri_reviewer_bg_color_theme_mode",
            "onigiri_reviewer_bg_image_theme_mode",
            "onigiri_reviewer_bg_blur",
            "onigiri_reviewer_bg_opacity",
            "onigiri_reviewer_slideshow_images",
            "onigiri_reviewer_slideshow_interval",
            "onigiri_reviewer_bottom_bar_bg_mode",
            "onigiri_reviewer_bottom_bar_bg_light_color",
            "onigiri_reviewer_bottom_bar_bg_dark_color",
            "onigiri_reviewer_bottom_bar_bg_image",
            "onigiri_reviewer_bottom_bar_bg_blur",
            "onigiri_reviewer_bottom_bar_bg_opacity",
            "onigiri_reviewer_bottom_bar_match_main_blur",
            "onigiri_reviewer_bottom_bar_match_main_opacity",
            "onigiri_reviewer_bottom_bar_match_reviewer_bg_blur",
            "onigiri_reviewer_bottom_bar_match_reviewer_bg_opacity",
            "onigiri_reviewer_bottom_bar_match_overview_bg_blur",
            "onigiri_reviewer_bottom_bar_match_overview_bg_opacity",
            "onigiri_reviewer_btn_border_size",
            "onigiri_reviewer_btn_radius",
            "onigiri_reviewer_btn_padding",
            "onigiri_reviewer_btn_height",
            "onigiri_reviewer_bar_height",
            "onigiri_reviewer_stattxt_visible",
            "onigiri_toolbar_bg_mode",
            "onigiri_toolbar_bg_color_light",
            "onigiri_toolbar_bg_color_dark",
            "onigiri_toolbar_bg_image",
            "onigiri_toolbar_bg_blur",
            "onigiri_sidebar_main_bg_effect_mode",
            "onigiri_sidebar_main_bg_effect_intensity",
            "onigiri_sidebar_opaque_tint_intensity",
            "onigiri_sidebar_opaque_tint_color_light",
            "onigiri_sidebar_opaque_tint_color_dark",
            "onigiri_profile_level_bar_mode",
            "onigiri_profile_level_bar_custom_color",
        ]
        addon_tokens = (
            "bg", "background", "font", "btn", "bar", "color", "blur", "opacity",
            "radius", "padding", "height", "effect", "slideshow", "shadow"
        )
        addon_keys = [
            key for key in DEFAULTS.keys()
            if key != "colors"
            and (key.startswith("onigiri_") or key.startswith("modern_menu_"))
            and any(token in key for token in addon_tokens)
        ]
        addon_keys.extend(explicit_addon_keys)
        addon_keys.extend(REVIEWER_THEME_KEYS)
        addon_keys = sorted(set(addon_keys))

        collection_keys = [
            "modern_menu_studyNowText",
            "onigiri_overview_style",
            "onigiri_overview_sync_box_effect",
            "onigiri_overview_box_color_theme_mode",
            "onigiri_overview_effect_blur",
            "onigiri_overview_effect_opacity",
            "onigiri_overview_border_radius",
            "onigiri_overview_border_width",
            "modern_menu_hide_folder_icon",
            "modern_menu_hide_subdeck_icon",
            "modern_menu_hide_deck_icon",
            "modern_menu_hide_filtered_deck_icon",
            "modern_menu_hide_default_icons",
            "modern_menu_background_mode",
            "modern_menu_bg_color_theme_mode",
            "modern_menu_bg_image_theme_mode",
            "modern_menu_background_image_mode",
            "modern_menu_bg_color_light",
            "modern_menu_bg_color_dark",
            "modern_menu_background_image",
            "modern_menu_background_image_light",
            "modern_menu_background_image_dark",
            "modern_menu_slideshow_images",
            "modern_menu_slideshow_interval",
            "modern_menu_background_blur",
            "modern_menu_background_opacity",
            "modern_menu_sidebar_bg_mode",
            "modern_menu_sidebar_bg_type",
            "modern_menu_sidebar_bg_color_theme_mode",
            "modern_menu_sidebar_bg_image_theme_mode",
            "modern_menu_sidebar_bg_color_light",
            "modern_menu_sidebar_bg_color_dark",
            "modern_menu_sidebar_bg_image",
            "modern_menu_sidebar_bg_image_light",
            "modern_menu_sidebar_bg_image_dark",
            "modern_menu_sidebar_slideshow_images",
            "modern_menu_sidebar_slideshow_interval",
            "modern_menu_sidebar_bg_blur",
            "modern_menu_sidebar_bg_opacity",
            "modern_menu_sidebar_bg_transparency",
            "modern_menu_sidebar_radius",
            "modern_menu_sidebar_stroke",
            "modern_menu_sidebar_margin",
            "modern_menu_profile_bg_mode",
            "modern_menu_profile_bg_dynamic_mode",
            "modern_menu_profile_bg_color_light",
            "modern_menu_profile_bg_color_dark",
            "modern_menu_profile_bg_image",
            "modern_menu_profile_bg_blur",
            "modern_menu_profile_bg_opacity",
            "modern_menu_profile_picture",
            "modern_menu_profile_picture_light",
            "modern_menu_profile_picture_dark",
            "modern_menu_profile_picture_mode",
            "modern_menu_profile_picture_dynamic_mode",
            "modern_menu_profile_picture_color_light",
            "modern_menu_profile_picture_color_dark",
            "modern_menu_profile_picture_blur",
            "modern_menu_profile_picture_opacity",
            "onigiri_profile_page_bg_mode",
            "onigiri_profile_page_bg_dynamic_mode",
            "onigiri_profile_page_bg_light_color1",
            "onigiri_profile_page_bg_light_color2",
            "onigiri_profile_page_bg_dark_color1",
            "onigiri_profile_page_bg_dark_color2",
            "onigiri_canvas_inset_color_theme_mode",
            "onigiri_canvas_inset_effect_mode",
            "onigiri_canvas_inset_effect_intensity",
            "onigiri_canvas_inset_effect_blur",
            "onigiri_canvas_inset_effect_opacity",
            "onigiri_canvas_inset_border_radius",
            "onigiri_canvas_inset_border_width",
            "onigiri_canvas_inset_color_light",
            "onigiri_canvas_inset_color_dark",
            "onigiri_font_main",
            "onigiri_font_subtle",
            "onigiri_font_small_title",
            "onigiri_font_size_main",
            "onigiri_font_size_subtle",
            "onigiri_font_size_small_title",
            "onigiri_toolbar_bg_mode",
            "onigiri_toolbar_bg_color_light",
            "onigiri_toolbar_bg_color_dark",
            "onigiri_toolbar_bg_image",
            "onigiri_toolbar_bg_blur",
            "onigiri_sidebar_main_bg_effect_mode",
            "onigiri_sidebar_main_bg_effect_intensity",
            "onigiri_sidebar_opaque_tint_intensity",
            "onigiri_sidebar_opaque_tint_color_light",
            "onigiri_sidebar_opaque_tint_color_dark",
            "onigiri_profile_level_bar_mode",
            "onigiri_profile_level_bar_custom_color",
        ]
        for icon_key in ICON_DEFAULTS.keys():
            collection_keys.append(f"modern_menu_icon_{icon_key}")
            collection_keys.append(f"modern_menu_icon_size_{icon_key}")
        for icon_key in DEFAULT_ICON_SIZES.keys():
            collection_keys.append(f"modern_menu_icon_size_{icon_key}")
        return addon_keys, sorted(set(collection_keys))

    def _collect_theme_customization(self):
        addon_keys, collection_keys = self._theme_customization_key_groups()
        addon_config = {}
        collection_config = {}

        for key in addon_keys:
            if key in self.current_config:
                addon_config[key] = copy.deepcopy(self.current_config[key])

        for key in collection_keys:
            value = mw.col.conf.get(key, None)
            if value is not None:
                collection_config[key] = copy.deepcopy(value)

        widget_values = {
            "modern_menu_background_blur": getattr(getattr(self, "main_bg_blur_slider", None), "value", lambda: None)(),
            "modern_menu_background_opacity": getattr(getattr(self, "main_bg_opacity_slider", None), "value", lambda: None)(),
            "modern_menu_sidebar_bg_blur": getattr(getattr(self, "sidebar_bg_blur_slider", None), "value", lambda: None)(),
            "modern_menu_sidebar_bg_opacity": getattr(getattr(self, "sidebar_bg_opacity_slider", None), "value", lambda: None)(),
            "modern_menu_sidebar_radius": getattr(getattr(self, "sidebar_bg_radius_slider", None), "value", lambda: None)(),
            "modern_menu_sidebar_stroke": getattr(getattr(self, "sidebar_bg_stroke_slider", None), "value", lambda: None)(),
            "modern_menu_sidebar_margin": getattr(getattr(self, "sidebar_bg_margin_slider", None), "value", lambda: None)(),
            "modern_menu_profile_bg_blur": getattr(getattr(self, "profile_bg_blur_slider", None), "value", lambda: None)(),
            "modern_menu_profile_bg_opacity": getattr(getattr(self, "profile_bg_opacity_slider", None), "value", lambda: None)(),
            "modern_menu_profile_picture_blur": 0,
            "modern_menu_profile_picture_opacity": getattr(getattr(self, "profile_pic_opacity_slider", None), "value", lambda: None)(),
            "onigiri_canvas_inset_effect_blur": getattr(getattr(self, "box_effect_blur_slider", None), "value", lambda: None)(),
            "onigiri_canvas_inset_effect_opacity": getattr(getattr(self, "box_effect_opacity_slider", None), "value", lambda: None)(),
            "onigiri_canvas_inset_border_radius": getattr(getattr(self, "box_effect_radius_slider", None), "value", lambda: None)(),
            "onigiri_canvas_inset_border_width": getattr(getattr(self, "box_effect_stroke_slider", None), "value", lambda: None)(),
        }
        for key, value in widget_values.items():
            if value is not None:
                collection_config[key] = value

        if hasattr(self, "font_selectors"):
            for font_type, selector in self.font_selectors.items():
                collection_config[f"onigiri_font_{font_type}"] = selector["combo"].currentData() or "system"
        for font_type in ["main", "subtle", "small_title"]:
            spinbox = getattr(self, f"font_size_{font_type}", None)
            if spinbox:
                collection_config[f"onigiri_font_size_{font_type}"] = spinbox.value()

        return {
            "addon_config": addon_config,
            "collection_config": collection_config,
        }

    def _apply_theme_customization(self, customization):
        if not isinstance(customization, dict):
            return
        addon_config = customization.get("addon_config", {})
        collection_config = customization.get("collection_config", {})
        if isinstance(addon_config, dict):
            self.current_config.update(copy.deepcopy(addon_config))
        if isinstance(collection_config, dict):
            for key, value in collection_config.items():
                mw.col.conf[key] = copy.deepcopy(value)

    def _load_themes(self):
        """Loads built-in and custom themes, returning them as separate dictionaries."""
        official_themes = dict(THEMES)
        user_themes = {}

        # Load user themes from JSON files
        for filename in os.listdir(self.user_themes_path):
            if filename.lower().endswith(".json"):
                filepath = os.path.join(self.user_themes_path, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        theme_data = json.load(f)

                    # Basic validation
                    if isinstance(theme_data, dict) and "light" in theme_data and "dark" in theme_data:
                        theme_name = os.path.splitext(filename)[0].replace("_", " ").title()
                        user_themes[theme_name] = theme_data
                    else:
                        print(f"Onigiri: Invalid theme file format in {filename}")
                except (json.JSONDecodeError, OSError) as e:
                    print(f"Onigiri: Could not load theme file {filename}: {e}")

        return official_themes, user_themes

    def _create_themes_empty_state(self):
        palette = self._settings_palette()
        border = palette.get("--border", "#454545" if theme_manager.night_mode else "#dcdde1")
        fg = palette.get("--fg", "#f4f4f5" if theme_manager.night_mode else "#202124")
        subtle = palette.get("--fg-subtle", "#c4c4c4" if theme_manager.night_mode else "#6f7177")
        panel_bg = palette.get("--canvas-inset", "#1f1f1f" if theme_manager.night_mode else "#fafafa")
        accent = palette.get("--accent-color", DEFAULTS["colors"]["dark" if theme_manager.night_mode else "light"]["--accent-color"])

        accent_qcolor = QColor(accent if QColor(accent).isValid() else "#00A982")
        badge_bg = QColor(accent_qcolor)
        badge_bg.setAlpha(30 if theme_manager.night_mode else 20)

        panel = QFrame()
        panel.setObjectName("themesEmptyState")
        panel.setMinimumWidth(0)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        panel.setStyleSheet(f"""
            QFrame#themesEmptyState {{
                background-color: {panel_bg};
                border: 1.5px dashed {border};
                border-radius: 20px;
            }}
            QLabel {{
                background: transparent;
            }}
        """)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(28, 34, 28, 34)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        badge = QLabel()
        badge.setFixedSize(56, 56)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"background-color: {badge_bg.name(QColor.NameFormat.HexArgb)}; border-radius: 28px;")
        try:
            with open(system_icon_path("import_file.svg"), "r", encoding="utf-8") as icon_file:
                svg_data = icon_file.read().replace("currentColor", accent)
            renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))
            icon_pixmap = QPixmap(26, 26)
            icon_pixmap.fill(Qt.GlobalColor.transparent)
            icon_painter = QPainter(icon_pixmap)
            icon_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            renderer.render(icon_painter)
            icon_painter.end()
            badge.setPixmap(icon_pixmap)
        except Exception:
            badge.setText("+")

        title = QLabel(tr("no_custom_themes"))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"color: {fg}; font-size: 14px; font-weight: 700;")

        subtitle = QLabel(tr("no_custom_themes_hint", "Import a .onigiri theme file to see it here."))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(f"color: {subtle}; font-size: 12px; font-weight: 500;")

        import_button = QPushButton(tr("import_theme"))
        import_button.setCursor(Qt.CursorShape.PointingHandCursor)
        import_button.setStyleSheet(self._theme_action_button_stylesheet(34))
        import_button.setFixedHeight(34)
        import_button.clicked.connect(self._import_theme)

        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(import_button, 0, Qt.AlignmentFlag.AlignCenter)

        return panel

    def _populate_grid_with_themes(self, grid_layout, themes_dict, deletable=False):
        """Helper function to populate a given layout with theme cards."""
        existing_cards = getattr(self, "theme_preview_cards", [])
        while grid_layout.count():
            child = grid_layout.takeAt(0)
            if child.widget():
                if child.widget() in existing_cards:
                    existing_cards.remove(child.widget())
                child.widget().deleteLater()
        self.theme_preview_cards = existing_cards

        if not themes_dict:
            if deletable:
                empty_state = self._create_themes_empty_state()
                if isinstance(grid_layout, FlowLayout):
                    grid_layout.addWidget(empty_state)
                else:
                    grid_layout.addWidget(empty_state, 0, 0)
            return

        # Create the icon once, before the loop
        delete_icon = self._create_delete_icon() if deletable else None

        row, col = 0, 0
        num_cols = 2

        theme_items = sorted(themes_dict.items(), key=lambda item: item[0].lower())

        for name, data in theme_items:
            card = ThemeCardWidget(
                name,
                data,
                deletable=deletable,
                delete_icon=delete_icon,
                preview_mode=getattr(self, "theme_preview_mode", "light"),
                full_preview=deletable,
            )
            card.theme_selected.connect(lambda data, c=card: self._apply_theme(data, c.display_name))
            if deletable:
                card.delete_requested.connect(self._delete_user_theme) # Connect the new signal
            self.theme_preview_cards.append(card)
            
            if isinstance(grid_layout, FlowLayout):
                grid_layout.addWidget(card)
            else:
                grid_layout.addWidget(card, row, col)

            col += 1
            if col >= num_cols:
                col = 0; row += 1

    def _import_theme(self):
        """Opens a file dialog to import a theme from a .onigiri file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            tr("import_theme_title"),
            "",
            f"{tr('onigiri_theme_files', 'Onigiri Theme Files')} (*.onigiri)"
        )
        if not filepath:
            return

        try:
            filename = os.path.basename(filepath)

            if not filename.lower().endswith(".onigiri"):
                QMessageBox.warning(self, tr("import_error_title"), tr("invalid_theme_file"))
                return

            # Handle .onigiri files (zip)
            import zipfile
            if not zipfile.is_zipfile(filepath):
                QMessageBox.warning(self, "Import Error", "The selected file is not a valid zip archive.")
                return

            with zipfile.ZipFile(filepath, 'r') as zf:
                # 1. Read theme.json
                try:
                    with zf.open('theme.json') as f:
                        theme_data = json.load(f)
                except KeyError:
                    QMessageBox.warning(self, "Import Error", "The .onigiri file is missing 'theme.json'.")
                    return

                # 2. Extract Assets
                # We will modify theme_data to point to the new extracted locations
                assets = theme_data.get("assets", {})
                theme_name = os.path.splitext(filename)[0] # e.g. "My_Theme"
                
                # Prepare directories
                images_dest_dir = os.path.join(self.addon_path, "user_files", "images", theme_name)
                fonts_dest_dir = os.path.join(self.addon_path, "user_files", "fonts")
                icons_dest_dir = os.path.join(self.addon_path, "user_files", "icons")
                
                os.makedirs(images_dest_dir, exist_ok=True)
                os.makedirs(fonts_dest_dir, exist_ok=True)
                os.makedirs(icons_dest_dir, exist_ok=True)

                # Extract Images
                if "images" in assets:
                    def extract_image_asset(archive_path):
                        # archive_path is like "images/main_bg/bg.png" or "images/filename.png"
                        parts = archive_path.split("/")
                        if len(parts) >= 3 and parts[0] == "images":
                            subfolder = parts[1]
                            filename = parts[-1]
                            dest_dir = os.path.join(self.addon_path, "user_files", subfolder)
                        else:
                            dest_dir = images_dest_dir
                            filename = os.path.basename(archive_path)

                        os.makedirs(dest_dir, exist_ok=True)
                        target_path = os.path.join(dest_dir, filename)
                        with zf.open(archive_path) as source, open(target_path, "wb") as target:
                            shutil.copyfileobj(source, target)
                        return target_path

                    for config_key, archive_value in assets["images"].items():
                        archive_paths = archive_value if isinstance(archive_value, list) else [archive_value]
                        extracted_paths = []
                        for archive_path in archive_paths:
                            if not isinstance(archive_path, str):
                                continue
                            try:
                                extracted_paths.append(extract_image_asset(archive_path))
                            except KeyError:
                                print(f"Asset {archive_path} not found in zip.")
                        if extracted_paths:
                            theme_data["assets"]["images"][config_key] = (
                                extracted_paths if isinstance(archive_value, list) else extracted_paths[0]
                            )

                # Extract Fonts
                if "fonts" in assets:
                     for font_key, archive_path in assets["fonts"].items():
                        try:
                            asset_filename = os.path.basename(archive_path)
                            target_path = os.path.join(fonts_dest_dir, asset_filename)
                            with zf.open(archive_path) as source, open(target_path, "wb") as target:
                                shutil.copyfileobj(source, target)
                            # We don't need to update reference in theme_data if it uses filename as key
                            # But if we stored archive_path, we might? 
                            # Export stored key -> archive_path.
                            # Fonts.py loads all from user_files/fonts. 
                            # So by just placing it there, it becomes available.
                        except KeyError:
                            pass

                # Extract Icons
                if "icons" in assets:
                    for icon_key, archive_path in assets["icons"].items():
                        try:
                            asset_filename = os.path.basename(archive_path)
                            archive_parts = archive_path.split("/")
                            if len(archive_parts) >= 3 and archive_parts[0] == "icons" and archive_parts[1] == "custom_deck_icons":
                                target_dir = os.path.join(self.addon_path, "user_files", "custom_deck_icons")
                                os.makedirs(target_dir, exist_ok=True)
                            else:
                                target_dir = icons_dest_dir
                            target_path = os.path.join(target_dir, asset_filename)
                            with zf.open(archive_path) as source, open(target_path, "wb") as target:
                                shutil.copyfileobj(source, target)
                            
                            # Update theme data with just the filename
                            theme_data["assets"]["icons"][icon_key] = asset_filename
                        except KeyError:
                            pass
                
                # Preserve icon_config if it exists (for preview)
                # icon_config contains all icon selections (including defaults)
                # We don't need to modify it, just ensure it's in theme_data

                # 3. Save the modified theme.json to user_themes
                # We rename it to match the .onigiri filename
                json_filename = theme_name + ".json"
                json_dest_path = os.path.join(self.user_themes_path, json_filename)
                
                with open(json_dest_path, 'w', encoding='utf-8') as f:
                    json.dump(theme_data, f, indent=4)

            # Refresh the grid to show the new theme
            _, user_themes = self._load_themes()
            self._populate_grid_with_themes(self.user_themes_grid_layout, user_themes, deletable=True)
            show_settings_toast(self, tr("theme_imported_toast", "Theme imported successfully"))

        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Could not import the theme file:\n{e}")

    def _sync_theme_export_state(self):
        """Flush loaded theme-related controls before building the export payload."""
        if hasattr(self, "box_effect_dynamic_toggle"):
            self._save_box_effect_settings()

        if hasattr(self, "overview_style_sync_toggle"):
            self._save_overview_style_settings()
        if hasattr(self, "overview_mini_radio"):
            mw.col.conf["onigiri_overview_style"] = "mini" if self.overview_mini_radio.isChecked() else "pro"
        if hasattr(self, "show_overview_profile_bar_checkbox"):
            self.current_config["showOverviewProfileBar"] = self.show_overview_profile_bar_checkbox.isChecked()
        if hasattr(self, "show_congrats_profile_bar_checkbox"):
            self.current_config["showCongratsProfileBar"] = self.show_congrats_profile_bar_checkbox.isChecked()
        if hasattr(self, "congrats_message_input"):
            self.current_config["congratsMessage"] = self.congrats_message_input.text()
        if hasattr(self, "study_now_input"):
            self.current_config["studyNowText"] = self.study_now_input.text()
            mw.col.conf["modern_menu_studyNowText"] = self.study_now_input.text()
        if hasattr(self, "hide_retention_stars_check"):
            self.current_config["hideRetentionStars"] = self.hide_retention_stars_check.isChecked()

        for prefix in ("overview", "reviewer"):
            if self._modern_background_spec(prefix) and hasattr(self, f"{prefix}_bg_color_only_toggle"):
                self._save_modern_background_designer_settings(prefix)
                self.current_config[f"onigiri_{prefix}_bg_main_blur"] = self.current_config.get(f"onigiri_{prefix}_bg_blur", 0)
                self.current_config[f"onigiri_{prefix}_bg_main_opacity"] = self.current_config.get(f"onigiri_{prefix}_bg_opacity", 100)

        marker_colors = self.current_config.setdefault("markerColors", copy.deepcopy(DEFAULTS.get("markerColors", {})))
        for marker_key in ["red", "blue", "green", "yellow"]:
            input_widget = getattr(self, f"marker_{marker_key}_color_input", None)
            if input_widget:
                marker_colors[marker_key] = input_widget.text()

        icon_widgets = []
        icon_widgets.extend(getattr(self, "action_button_icon_widgets", []) or [])
        icon_widgets.extend(getattr(self, "icon_assignment_widgets", []) or [])
        if getattr(self, "retention_star_widget", None):
            icon_widgets.append(self.retention_star_widget)
        for widget in icon_widgets:
            key = widget.property("icon_key")
            value = widget.property("icon_filename")
            if key:
                mw.col.conf[f"modern_menu_icon_{key}"] = value or ""

        for key, widget in getattr(self, "icon_size_widgets", {}).items():
            mw.col.conf[f"modern_menu_icon_size_{key}"] = widget.value()

        for attr_name, conf_key in [
            ("hide_folder_cb", "modern_menu_hide_folder_icon"),
            ("hide_subdeck_cb", "modern_menu_hide_subdeck_icon"),
            ("hide_deck_cb", "modern_menu_hide_deck_icon"),
            ("hide_filtered_deck_cb", "modern_menu_hide_filtered_deck_icon"),
            ("hide_default_custom_cb", "modern_menu_hide_default_icons"),
        ]:
            widget = getattr(self, attr_name, None)
            if widget:
                mw.col.conf[conf_key] = widget.isChecked()

        if hasattr(self, "reviewer_bar_light_color_input"):
            self.current_config["onigiri_reviewer_bottom_bar_bg_mode"] = self.reviewer_bottom_bar_mode
            self.current_config["onigiri_reviewer_bottom_bar_match_main_blur"] = self.reviewer_bar_match_main_blur_spinbox.value()
            self.current_config["onigiri_reviewer_bottom_bar_match_main_opacity"] = self.reviewer_bar_match_main_opacity_spinbox.value()
            self.current_config["onigiri_reviewer_bottom_bar_match_reviewer_bg_blur"] = self.reviewer_bar_match_reviewer_bg_blur_spinbox.value()
            self.current_config["onigiri_reviewer_bottom_bar_match_reviewer_bg_opacity"] = self.reviewer_bar_match_reviewer_bg_opacity_spinbox.value()
            if hasattr(self, "reviewer_bar_match_overview_bg_blur_spinbox"):
                self.current_config["onigiri_reviewer_bottom_bar_match_overview_bg_blur"] = self.reviewer_bar_match_overview_bg_blur_spinbox.value()
                self.current_config["onigiri_reviewer_bottom_bar_match_overview_bg_opacity"] = self.reviewer_bar_match_overview_bg_opacity_spinbox.value()
            self.current_config["onigiri_reviewer_bottom_bar_bg_light_color"] = self.reviewer_bar_light_color_input.text()
            self.current_config["onigiri_reviewer_bottom_bar_bg_dark_color"] = self.reviewer_bar_dark_color_input.text()
            self.current_config["onigiri_reviewer_bottom_bar_bg_blur"] = self.reviewer_bar_blur_spinbox.value()
            self.current_config["onigiri_reviewer_bottom_bar_bg_opacity"] = self.reviewer_bar_opacity_spinbox.value()
            if "reviewer_bar_bg" in self.galleries:
                self.current_config["onigiri_reviewer_bottom_bar_bg_image"] = self.galleries["reviewer_bar_bg"]["selected"]

    def _prompt_theme_export_name(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Export Theme")
        dialog.setMinimumWidth(430)

        palette = self._settings_palette()
        bg = palette.get("--canvas-inset", "#ffffff" if not theme_manager.night_mode else "#242424")
        fg = palette.get("--fg", "#202124" if not theme_manager.night_mode else "#f4f4f5")
        border = palette.get("--border", "#dcdde1" if not theme_manager.night_mode else "#454545")
        input_bg = palette.get("--input-bg", bg)

        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {bg};
            }}
            QLabel {{
                color: {fg};
                background: transparent;
                font-size: 15px;
            }}
            QLineEdit {{
                background-color: {input_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 18px;
                min-height: 34px;
                padding: 4px 14px;
                font-size: 15px;
            }}
        """)

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(34, 28, 34, 26)
        main_layout.setSpacing(14)

        label = QLabel("Enter a name for your theme:")
        name_input = QLineEdit()
        name_input.setMinimumHeight(44)
        name_input.setFocus()

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 4, 0, 0)
        button_row.setSpacing(12)
        button_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        cancel_button = QPushButton("Cancel")
        ok_button = QPushButton("OK")
        for button in (cancel_button, ok_button):
            button.setObjectName("themeExportDialogButton")
            button.setFixedHeight(34)
            button.setMinimumWidth(96)
            button.setAutoDefault(False)
            button.setDefault(False)
            button.setStyleSheet(self._settings_pill_button_stylesheet(min_height=34))

        cancel_button.clicked.connect(dialog.reject)
        ok_button.clicked.connect(dialog.accept)
        name_input.returnPressed.connect(dialog.accept)

        button_row.addWidget(cancel_button)
        button_row.addWidget(ok_button)

        main_layout.addWidget(label)
        main_layout.addWidget(name_input)
        main_layout.addLayout(button_row)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return ""
        return name_input.text().strip()

    def _show_theme_export_notice(self):
        palette = self._settings_palette()
        panel_bg = palette.get("--canvas-inset", "#242424" if theme_manager.night_mode else "#ffffff")
        page_bg = palette.get("--bg", "#181818" if theme_manager.night_mode else "#f7f7f7")
        fg = palette.get("--fg", "#f4f4f5" if theme_manager.night_mode else "#202124")
        subtle = palette.get("--fg-subtle", "#c4c4c4" if theme_manager.night_mode else "#6f7177")
        border = palette.get("--border", "#454545" if theme_manager.night_mode else "#dcdde1")
        hover_bg = palette.get("--hover-bg", "#3a3a3a" if theme_manager.night_mode else "#e9e9e9")
        accent = palette.get("--accent-color", DEFAULTS["colors"]["dark" if theme_manager.night_mode else "light"]["--accent-color"])

        accent_qcolor = QColor(accent if QColor(accent).isValid() else "#00A982")
        badge_bg = QColor(accent_qcolor)
        badge_bg.setAlpha(34 if theme_manager.night_mode else 24)
        badge_border = QColor(accent_qcolor)
        badge_border.setAlpha(96 if theme_manager.night_mode else 70)

        dialog = QDialog(self)
        dialog.setWindowTitle(tr("export_theme_notice_title", "Export Current Theme"))
        dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        dialog.setModal(True)
        dialog.setFixedWidth(680)

        dialog.setStyleSheet(f"""
            QDialog {{
                background: transparent;
            }}
            QFrame#themeExportNoticePanel {{
                background-color: {panel_bg};
                border: 1px solid {border};
                border-radius: 24px;
            }}
            QLabel {{
                background: transparent;
            }}
            QLabel#themeExportNoticeBadge {{
                background-color: {badge_bg.name(QColor.NameFormat.HexArgb)};
                border: 1px solid {badge_border.name(QColor.NameFormat.HexArgb)};
                border-radius: 20px;
            }}
            QLabel#themeExportNoticeTitle {{
                color: {fg};
                font-size: 20px;
                font-weight: 800;
            }}
            QLabel#themeExportNoticeBody {{
                color: {subtle};
                font-size: 14px;
                font-weight: 500;
            }}
            QLabel#themeExportNoticeCallout {{
                color: {fg};
                background-color: {page_bg};
                border: 1px solid {border};
                border-radius: 14px;
                padding: 11px 14px;
                font-size: 14px;
                font-weight: 700;
            }}
            QPushButton#themeExportNoticeCancel {{
                min-height: 34px;
                padding: 0 18px;
                border: 1px solid {border};
                border-radius: 17px;
                background-color: transparent;
                color: {fg};
                font-weight: 700;
            }}
            QPushButton#themeExportNoticeCancel:hover {{
                background-color: {hover_bg};
                border-color: {accent};
            }}
            QPushButton#themeExportNoticeContinue {{
                min-height: 34px;
                padding: 0 20px;
                border: 1px solid {accent};
                border-radius: 17px;
                background-color: {accent};
                color: #ffffff;
                font-weight: 800;
            }}
            QPushButton#themeExportNoticeContinue:hover {{
                background-color: {QColor(accent).lighter(112).name() if QColor(accent).isValid() else accent};
                border-color: {QColor(accent).lighter(112).name() if QColor(accent).isValid() else accent};
            }}
        """)

        outer_layout = QVBoxLayout(dialog)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        outer_layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        panel = QFrame(dialog)
        panel.setObjectName("themeExportNoticePanel")
        outer_layout.addWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(0)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(12)
        header_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        badge = QLabel()
        badge.setObjectName("themeExportNoticeBadge")
        badge.setFixedSize(40, 40)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        try:
            with open(system_icon_path("info-circle.svg"), "r", encoding="utf-8") as icon_file:
                svg_data = icon_file.read().replace("currentColor", accent)
            renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))
            icon_pixmap = QPixmap(22, 22)
            icon_pixmap.fill(Qt.GlobalColor.transparent)
            icon_painter = QPainter(icon_pixmap)
            icon_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            renderer.render(icon_painter)
            icon_painter.end()
            badge.setPixmap(icon_pixmap)
        except Exception:
            badge.setText("i")

        title = QLabel(tr("export_theme_notice_title", "Export Current Theme"))
        title.setObjectName("themeExportNoticeTitle")
        title.setWordWrap(True)

        header_row.addWidget(badge, 0, Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(title, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(header_row)
        layout.addSpacing(14)

        body = QLabel(tr(
            "export_theme_notice_details",
            "The .onigiri file will include the current light and dark color palettes, reviewer theme settings, "
            "theme-related customization, selected fonts, selected icons, and selected background/profile/reviewer images."
        ))
        body.setObjectName("themeExportNoticeBody")
        body.setWordWrap(True)
        layout.addWidget(body)
        layout.addSpacing(20)

        callout = QLabel(tr("export_theme_notice_text", "Only your currently active theme settings will be exported."))
        callout.setObjectName("themeExportNoticeCallout")
        callout.setWordWrap(True)
        layout.addWidget(callout)
        layout.addSpacing(18)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(10)
        button_row.addStretch()

        cancel_button = QPushButton(tr("cancel", "Cancel"))
        cancel_button.setObjectName("themeExportNoticeCancel")
        cancel_button.setAutoDefault(False)

        continue_button = QPushButton(tr("continue", "Continue"))
        continue_button.setObjectName("themeExportNoticeContinue")
        continue_button.setAutoDefault(False)
        continue_button.setDefault(True)

        cancel_button.clicked.connect(dialog.reject)
        continue_button.clicked.connect(dialog.accept)

        button_row.addWidget(cancel_button)
        button_row.addWidget(continue_button)
        layout.addLayout(button_row)

        return dialog.exec() == QDialog.DialogCode.Accepted

    def _export_current_theme(self):
        """Gathers ALL current theme colors and assets, saving them to a .onigiri zip file."""
        if not self._show_theme_export_notice():
            return

        name = self._prompt_theme_export_name()
        if not name:
            return

        self._sync_theme_export_state()

        light_palette = {}
        dark_palette = {}

        # 1. Gather Colors
        for mode, palette in [("light", light_palette), ("dark", dark_palette)]:
            for key in ALL_THEME_KEYS:
                # Default to the value in the in-memory config
                value = self.current_config["colors"][mode].get(key)

                # Check UI widgets for latest values
                if key == "--accent-color" and hasattr(self, f"{mode}_accent_color_input"):
                    value = getattr(self, f"{mode}_accent_color_input").text()
                elif key == "--bg" and hasattr(self, f"bg_{mode}_color_input"):
                    value = getattr(self, f"bg_{mode}_color_input").text()
                elif key in self.color_widgets.get(mode, {}):
                    value = self.color_widgets[mode][key].text()
                
                if value is not None:
                    palette[key] = value

        # 1b. Gather Reviewer Settings
        reviewer_settings = {}
        for key in REVIEWER_THEME_KEYS:
            value = self.current_config.get(key)
            if value is not None:
                reviewer_settings[key] = value

        theme_data = {
            "light": light_palette, 
            "dark": dark_palette,
            "reviewer_settings": reviewer_settings,
            "customization": self._collect_theme_customization(),
            "assets": {
                "fonts": {}, # Map: local_filename -> archive_path
                "images": {},
                "icons": {},
                "font_config": {}, # Store selected font keys and sizes
                "icon_config": {} # Store which icons are selected (even if defaults)
            }
        }

        # 2. Gather Assets
        assets_to_zip = [] # List of tuples: (source_path, archive_name)

        # Fonts
        # Check active fonts in config
        for font_type in ["main", "subtle", "small_title"]:
            selector = getattr(self, "font_selectors", {}).get(font_type, {})
            font_key = selector.get("combo").currentData() if selector.get("combo") else mw.col.conf.get(f"onigiri_font_{font_type}")
            if font_key:
                # Save the configuration selection
                theme_data["assets"]["font_config"][font_type] = font_key
                
                # If it's a user font, we assume the key is the filename (as per fonts.py: load_user_fonts)
                # We check if it exists in user_files/fonts
                font_path = os.path.join(self.addon_path, "user_files", "fonts", font_key)
                if os.path.exists(font_path) and os.path.isfile(font_path):
                    archive_path = f"fonts/{font_key}"
                    # Avoid adding duplicates
                    if not any(a[1] == archive_path for a in assets_to_zip):
                        assets_to_zip.append((font_path, archive_path))
                        # We list it in assets["fonts"] just to track what's included
                        theme_data["assets"]["fonts"][font_key] = archive_path
            spinbox = getattr(self, f"font_size_{font_type}", None)
            size_value = spinbox.value() if spinbox else mw.col.conf.get(f"onigiri_font_size_{font_type}")
            if size_value is not None:
                theme_data["assets"]["font_config"][f"size_{font_type}"] = size_value
        
        # Images
        # Map config keys to their respective subfolders in user_files
        image_key_map = {
            "modern_menu_background_image": "main_bg",
            "modern_menu_background_image_light": "main_bg",
            "modern_menu_background_image_dark": "main_bg",
            "modern_menu_slideshow_images": "main_bg",
            "onigiri_overview_bg_image": "main_bg",
            "onigiri_overview_bg_image_light": "main_bg",
            "onigiri_overview_bg_image_dark": "main_bg",
            "onigiri_overview_slideshow_images": "main_bg",
            "modern_menu_profile_bg_image": "profile_bg",
            "modern_menu_profile_picture": "profile",
            "modern_menu_profile_picture_light": "profile",
            "modern_menu_profile_picture_dark": "profile",
            "modern_menu_sidebar_bg_image": "sidebar_bg",
            "modern_menu_sidebar_bg_image_light": "sidebar_bg",
            "modern_menu_sidebar_bg_image_dark": "sidebar_bg",
            "modern_menu_sidebar_slideshow_images": "sidebar_bg",
            "onigiri_reviewer_bg_image": "reviewer_bg", 
            "onigiri_reviewer_bg_image_light": "reviewer_bg",
            "onigiri_reviewer_bg_image_dark": "reviewer_bg",
            "onigiri_reviewer_slideshow_images": "reviewer_bg",
            "onigiri_reviewer_bottom_bar_bg_image": "reviewer_bar_bg",
            "onigiri_toolbar_bg_image": "toolbar_bg",
        }
        
        active_images = {}
        for key, subfolder in image_key_map.items():
            # config often holds just the filename
            # We try self.current_config first, then mw.col.conf
            value = self.current_config.get(key)
            if value in (None, "", []):
                value = mw.col.conf.get(key)

            filenames = value if isinstance(value, list) else [value]
            archive_paths = []
            for filename in filenames:
                if not filename or not isinstance(filename, str):
                    continue

                full_path = os.path.join(self.addon_path, "user_files", subfolder, filename)
                if os.path.exists(full_path) and os.path.isfile(full_path):
                    archive_path = f"images/{subfolder}/{filename}"
                    # Avoid duplicates
                    if not any(a[1] == archive_path for a in assets_to_zip):
                        assets_to_zip.append((full_path, archive_path))
                    archive_paths.append(archive_path)

            if archive_paths:
                active_images[key] = archive_paths if isinstance(value, list) else archive_paths[0]

        theme_data["assets"]["images"] = active_images

        # Icons
        # Similar logic for icons. 
        # We need to find which icons are customized. 
        # `settings.py` creates icon widgets based on `modern_menu_icon_{key}` in `mw.col.conf`.
        # Note: Icons seem to be stored in `mw.col.conf`, not `self.current_config` (which mimics the add-on config).
        # We should check `mw.col.conf` for `modern_menu_icon_*`.
        
        active_icons = {}
        icon_config = {}
        
        # Iterate over all possible icon keys (we can get them from ICON_DEFAULTS)
        for icon_key in ICON_DEFAULTS.keys():
            conf_key = f"modern_menu_icon_{icon_key}"
            filename = mw.col.conf.get(conf_key, "")
            
            # Always save the configuration (even if it's empty/default)
            # This allows preview to show defaults
            icon_config[icon_key] = filename if filename else icon_key  # Use key for defaults
            
            if filename:
                filepath = ""
                icon_subfolder = "icons"
                for candidate_subfolder in ("icons", "custom_deck_icons"):
                    candidate_path = os.path.join(self.addon_path, "user_files", candidate_subfolder, filename)
                    if os.path.exists(candidate_path):
                        filepath = candidate_path
                        icon_subfolder = candidate_subfolder
                        break
                if filepath:
                    archive_path = f"icons/{filename}" if icon_subfolder == "icons" else f"icons/custom_deck_icons/{filename}"
                    if not any(a[1] == archive_path for a in assets_to_zip):
                        assets_to_zip.append((filepath, archive_path))
                    active_icons[icon_key] = archive_path

        theme_data["assets"]["icons"] = active_icons
        theme_data["assets"]["icon_config"] = icon_config

        # 3. Create Zip
        suggested_filename = name.lower().replace(" ", "_") + ".onigiri"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Theme As",
            os.path.join(self.user_themes_path, suggested_filename),
            "Onigiri Theme Files (*.onigiri)"
        )

        if not save_path:
            return

        try:
            import zipfile
            with zipfile.ZipFile(save_path, 'w') as zf:
                # Write theme.json
                zf.writestr('theme.json', json.dumps(theme_data, indent=4))
                
                # Write assets
                for source, dest in assets_to_zip:
                    zf.write(source, dest)
            
            show_settings_toast(self, f"{tr('theme_exported_toast', 'Theme exported:')} {name}")

            # If saved in local themes folder, refresh? 
            # (Currently .onigiri files might not appear until we implement the import/view logic)
            # For now, standard JSON themes are loaded. 
            # We might want to auto-extract it back to be usable immediately if saved locally?
            # Or just leave it as an export file. The user said "Import, export".
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Could not save the theme file:\n{e}")

    def _reset_theme_to_default_with_toast(self):
        self.reset_theme_to_default()
        self._show_theme_selected_toast(tr("default_theme", "Default theme"))

    def reset_theme_to_default(self):
        """Resets theme colors and active image selections to the color-only default theme."""
        # Use a deep copy to avoid modifying the DEFAULTS constant
        default_colors = json.loads(json.dumps(DEFAULTS["colors"]))

        # 1. Update the internal config dictionary with the defaults
        self.current_config["colors"] = default_colors
        self._pending_theme_data = None
        self._theme_prepare_save_in_progress = False
        self._reset_theme_reviewer_settings_to_default()
        self._reset_theme_media_config_to_default(default_colors)
        self._reset_loaded_theme_media_widgets(default_colors)

        # 2. Update all relevant UI widgets if they have been created
        for mode, palette in default_colors.items():
            if mode not in ["light", "dark"]:
                continue

            # Update general color inputs (Palette, Sidebar, Main Menu, etc.)
            if mode in self.color_widgets:
                for key, widget in self.color_widgets[mode].items():
                    if key in palette:
                        widget.setText(palette[key])

            # Update Accent Color inputs
            if hasattr(self, f"{mode}_accent_color_input") and "--accent-color" in palette:
                getattr(self, f"{mode}_accent_color_input").setText(palette["--accent-color"])

            # Update the main Background Color input on the Backgrounds page
            if hasattr(self, f"bg_{mode}_color_input") and "--bg" in palette:
                getattr(self, f"bg_{mode}_color_input").setText(palette["--bg"])

        # 3. Refresh the settings dialog's own appearance
        self.apply_stylesheet()

    def _reset_theme_reviewer_settings_to_default(self):
        for key in REVIEWER_THEME_KEYS:
            if key in DEFAULTS:
                self.current_config[key] = copy.deepcopy(DEFAULTS[key])

        for key in [
            "onigiri_reviewer_btn_border_size",
            "onigiri_reviewer_btn_radius",
            "onigiri_reviewer_btn_padding",
            "onigiri_reviewer_btn_height",
            "onigiri_reviewer_bar_height",
            "onigiri_reviewer_stattxt_visible",
        ]:
            if key in DEFAULTS:
                self.current_config[key] = copy.deepcopy(DEFAULTS[key])

    def _reset_theme_media_config_to_default(self, default_colors):
        light_bg = default_colors["light"].get("--bg", "#f3f3f3")
        dark_bg = default_colors["dark"].get("--bg", "#2c2c2c")
        # Sidebar background mirrors Box Color and Effect so the two stay in sync.
        box_colors_defaults = DEFAULTS.get("overview_style", {}).get("colors", {})
        box_bg_light = box_colors_defaults.get("light", {}).get("box_bg", "#f3f3f3")
        box_bg_dark = box_colors_defaults.get("dark", {}).get("box_bg", "#2c2c2c")

        collection_theme_defaults = {
            "modern_menu_background_mode": "color",
            "modern_menu_bg_color_theme_mode": "separate",
            "modern_menu_bg_image_theme_mode": "separate",
            "modern_menu_background_image_mode": "single",
            "modern_menu_bg_color_light": light_bg,
            "modern_menu_bg_color_dark": dark_bg,
            "modern_menu_background_image": "",
            "modern_menu_background_image_light": "",
            "modern_menu_background_image_dark": "",
            "modern_menu_slideshow_images": [],
            "modern_menu_slideshow_interval": 10,
            "modern_menu_background_blur": 0,
            "modern_menu_background_opacity": 100,

            "modern_menu_sidebar_bg_mode": "custom",
            "modern_menu_sidebar_bg_type": "color",
            "modern_menu_sidebar_bg_color_theme_mode": "separate",
            "modern_menu_sidebar_bg_image_theme_mode": "separate",
            "modern_menu_sidebar_bg_color_light": box_bg_light,
            "modern_menu_sidebar_bg_color_dark": box_bg_dark,
            "modern_menu_sidebar_bg_image": "",
            "modern_menu_sidebar_bg_image_light": "",
            "modern_menu_sidebar_bg_image_dark": "",
            "modern_menu_sidebar_slideshow_images": [],
            "modern_menu_sidebar_slideshow_interval": 10,
            "modern_menu_sidebar_bg_blur": 0,
            "modern_menu_sidebar_bg_opacity": 100,
            "modern_menu_sidebar_bg_transparency": 0,
            "modern_menu_sidebar_radius": 15,
            "modern_menu_sidebar_stroke": 1,
            "modern_menu_sidebar_margin": 10,

            "modern_menu_profile_bg_mode": "image",
            "modern_menu_profile_bg_dynamic_mode": True,
            "modern_menu_profile_bg_color_light": "#EEEEEE",
            "modern_menu_profile_bg_color_dark": "#3C3C3C",
            "modern_menu_profile_bg_image": "",
            "modern_menu_profile_bg_blur": 0,
            "modern_menu_profile_bg_opacity": 50,
            "modern_menu_profile_picture": "",
            "modern_menu_profile_picture_light": "",
            "modern_menu_profile_picture_dark": "",
            "modern_menu_profile_picture_mode": "image",
            "modern_menu_profile_picture_dynamic_mode": True,
            "modern_menu_profile_picture_color_light": "#8CACB4",
            "modern_menu_profile_picture_color_dark": "#B8BDC3",
            "modern_menu_profile_picture_blur": 0,
            "modern_menu_profile_picture_opacity": 100,

            "onigiri_profile_page_bg_mode": "color",
            "onigiri_profile_page_bg_dynamic_mode": True,
            "onigiri_profile_page_bg_light_color1": "#F5F5F5",
            "onigiri_profile_page_bg_light_color2": "#F5F5F5",
            "onigiri_profile_page_bg_dark_color1": "#2c2c2c",
            "onigiri_profile_page_bg_dark_color2": "#2c2c2c",

            "onigiri_canvas_inset_color_theme_mode": "separate",
            "onigiri_canvas_inset_effect_mode": "none",
            "onigiri_canvas_inset_effect_intensity": 50,
            "onigiri_canvas_inset_effect_blur": 0,
            "onigiri_canvas_inset_effect_opacity": 100,
            "onigiri_canvas_inset_border_radius": 20,
            "onigiri_canvas_inset_border_width": 1,

            "onigiri_toolbar_bg_mode": "color",
            "onigiri_toolbar_bg_color_light": light_bg,
            "onigiri_toolbar_bg_color_dark": dark_bg,
            "onigiri_toolbar_bg_image": "",
            "onigiri_toolbar_bg_blur": 0,
        }
        for key, value in collection_theme_defaults.items():
            mw.col.conf[key] = copy.deepcopy(value)

        for key in [
            "modern_menu_background_mode",
            "modern_menu_bg_color_theme_mode",
            "modern_menu_bg_image_theme_mode",
            "modern_menu_background_image_mode",
            "modern_menu_bg_color_light",
            "modern_menu_bg_color_dark",
            "modern_menu_background_image",
            "modern_menu_background_image_light",
            "modern_menu_background_image_dark",
            "modern_menu_slideshow_images",
            "modern_menu_slideshow_interval",
            "modern_menu_background_blur",
            "modern_menu_background_opacity",
            "modern_menu_sidebar_bg_mode",
            "modern_menu_sidebar_bg_type",
            "modern_menu_sidebar_bg_color_theme_mode",
            "modern_menu_sidebar_bg_image_theme_mode",
            "modern_menu_sidebar_bg_color_light",
            "modern_menu_sidebar_bg_color_dark",
            "modern_menu_sidebar_bg_image",
            "modern_menu_sidebar_bg_image_light",
            "modern_menu_sidebar_bg_image_dark",
            "modern_menu_sidebar_slideshow_images",
            "modern_menu_sidebar_slideshow_interval",
            "modern_menu_sidebar_bg_blur",
            "modern_menu_sidebar_bg_opacity",
            "modern_menu_sidebar_bg_transparency",
            "modern_menu_sidebar_radius",
            "modern_menu_sidebar_stroke",
            "modern_menu_sidebar_margin",
            "modern_menu_profile_bg_mode",
            "modern_menu_profile_bg_dynamic_mode",
            "modern_menu_profile_bg_color_light",
            "modern_menu_profile_bg_color_dark",
            "modern_menu_profile_bg_image",
            "modern_menu_profile_bg_blur",
            "modern_menu_profile_bg_opacity",
            "modern_menu_profile_picture",
            "modern_menu_profile_picture_light",
            "modern_menu_profile_picture_dark",
            "modern_menu_profile_picture_mode",
            "modern_menu_profile_picture_dynamic_mode",
            "modern_menu_profile_picture_color_light",
            "modern_menu_profile_picture_color_dark",
            "modern_menu_profile_picture_blur",
            "modern_menu_profile_picture_opacity",
            "onigiri_profile_page_bg_mode",
            "onigiri_profile_page_bg_dynamic_mode",
            "onigiri_profile_page_bg_light_color1",
            "onigiri_profile_page_bg_light_color2",
            "onigiri_profile_page_bg_dark_color1",
            "onigiri_profile_page_bg_dark_color2",
            "onigiri_canvas_inset_color_theme_mode",
            "onigiri_canvas_inset_effect_mode",
            "onigiri_canvas_inset_effect_intensity",
            "onigiri_canvas_inset_effect_blur",
            "onigiri_canvas_inset_effect_opacity",
            "onigiri_canvas_inset_border_radius",
            "onigiri_canvas_inset_border_width",
        ]:
            self.current_config.pop(key, None)

        self.current_config.update({
            "onigiri_overview_bg_mode": "color",
            "onigiri_overview_bg_main_blur": 0,
            "onigiri_overview_bg_main_opacity": 100,
            "onigiri_overview_bg_light_color": "#f2f2f2",
            "onigiri_overview_bg_dark_color": "#2C2C2C",
            "onigiri_overview_bg_image": "",
            "onigiri_overview_bg_image_light": "",
            "onigiri_overview_bg_image_dark": "",
            "onigiri_overview_bg_image_mode": "single",
            "onigiri_overview_bg_color_theme_mode": "separate",
            "onigiri_overview_bg_image_theme_mode": "separate",
            "onigiri_overview_bg_blur": 0,
            "onigiri_overview_bg_opacity": 100,
            "onigiri_overview_slideshow_images": [],
            "onigiri_overview_slideshow_interval": 10,

            "onigiri_reviewer_bg_mode": "color",
            "onigiri_reviewer_bg_main_blur": 0,
            "onigiri_reviewer_bg_main_opacity": 100,
            "onigiri_reviewer_bg_light_color": "#f2f2f2",
            "onigiri_reviewer_bg_dark_color": "#2C2C2C",
            "onigiri_reviewer_bg_image": "",
            "onigiri_reviewer_bg_image_light": "",
            "onigiri_reviewer_bg_image_dark": "",
            "onigiri_reviewer_bg_image_mode": "single",
            "onigiri_reviewer_bg_color_theme_mode": "separate",
            "onigiri_reviewer_bg_image_theme_mode": "separate",
            "onigiri_reviewer_bg_blur": 0,
            "onigiri_reviewer_bg_opacity": 100,
            "onigiri_reviewer_slideshow_images": [],
            "onigiri_reviewer_slideshow_interval": 10,

            "onigiri_reviewer_bottom_bar_bg_mode": "match_reviewer_bg",
            "onigiri_reviewer_bottom_bar_bg_light_color": "#f2f2f2",
            "onigiri_reviewer_bottom_bar_bg_dark_color": "#2C2C2C",
            "onigiri_reviewer_bottom_bar_bg_image": "",
            "onigiri_reviewer_bottom_bar_bg_blur": 0,
            "onigiri_reviewer_bottom_bar_bg_opacity": 100,
            "onigiri_reviewer_bottom_bar_match_main_blur": 0,
            "onigiri_reviewer_bottom_bar_match_main_opacity": 100,
            "onigiri_reviewer_bottom_bar_match_reviewer_bg_blur": 0,
            "onigiri_reviewer_bottom_bar_match_reviewer_bg_opacity": 100,
            "onigiri_reviewer_bottom_bar_match_overview_bg_blur": 0,
            "onigiri_reviewer_bottom_bar_match_overview_bg_opacity": 100,

            "onigiri_toolbar_bg_mode": "color",
            "onigiri_toolbar_bg_color_light": light_bg,
            "onigiri_toolbar_bg_color_dark": dark_bg,
            "onigiri_toolbar_bg_image": "",
            "onigiri_toolbar_bg_blur": 0,
        })

    def _clear_theme_gallery_selection(self, key):
        gallery = getattr(self, "galleries", {}).get(key)
        if not gallery:
            return
        gallery["selected"] = ""
        if gallery.get("path_input"):
            gallery["path_input"].setText("")
        if gallery.get("grid_layout"):
            self._refresh_gallery(key)



# --- MERGED FROM _page_themes_2.py ---

class PageThemesMixin2:
    def _reset_loaded_theme_media_widgets(self, default_colors):
        light_bg = default_colors["light"].get("--bg", "#f3f3f3")
        dark_bg = default_colors["dark"].get("--bg", "#2c2c2c")
        box_colors_defaults = DEFAULTS.get("overview_style", {}).get("colors", {})
        box_bg_light = box_colors_defaults.get("light", {}).get("box_bg", "#f3f3f3")
        box_bg_dark = box_colors_defaults.get("dark", {}).get("box_bg", "#2c2c2c")

        if hasattr(self, "main_bg_color_only_toggle"):
            self.main_bg_color_only_toggle.setChecked(True)
            self.main_bg_slideshow_toggle.setChecked(False)
            self.main_bg_dynamic_toggle.setChecked(True)
            self.main_bg_single_color_input.setText(light_bg)
            self.main_bg_light_color_input.setText(light_bg)
            self.main_bg_dark_color_input.setText(dark_bg)
            self.main_bg_slideshow_images = []
            self.main_bg_slideshow_index = 0
            self.main_bg_slideshow_interval_spinbox.setValue(10)
            self.main_bg_blur_slider.setValue(0)
            self.main_bg_opacity_slider.setValue(100)
            for key in ("main_single", "main_light", "main_dark"):
                self._clear_theme_gallery_selection(key)
            self._update_main_background_controls()
        elif hasattr(self, "color_radio"):
            self.color_radio.setChecked(True)
            if hasattr(self, "bg_single_color_input"):
                self.bg_single_color_input.setText(light_bg)
            if hasattr(self, "bg_light_color_input"):
                self.bg_light_color_input.setText(light_bg)
            if hasattr(self, "bg_dark_color_input"):
                self.bg_dark_color_input.setText(dark_bg)
            for key in ("main_single", "main_light", "main_dark"):
                self._clear_theme_gallery_selection(key)
            if hasattr(self, "bg_blur_spinbox"):
                self.bg_blur_spinbox.setValue(0)
            if hasattr(self, "bg_opacity_spinbox"):
                self.bg_opacity_spinbox.setValue(100)

        self._reset_loaded_modern_background_widgets("sidebar", box_bg_light, box_bg_dark)
        self._reset_loaded_modern_background_widgets("overview", "#f2f2f2", "#2C2C2C")
        self._reset_loaded_modern_background_widgets("reviewer", "#f2f2f2", "#2C2C2C")

        if hasattr(self, "reviewer_bar_match_reviewer_toggle"):
            self.reviewer_bottom_bar_mode = "match_reviewer_bg"
            for toggle, checked in (
                (self.reviewer_bar_match_main_toggle, False),
                (self.reviewer_bar_match_overview_toggle, False),
                (self.reviewer_bar_match_reviewer_toggle, True),
                (self.reviewer_bar_color_only_toggle, False),
            ):
                with QSignalBlocker(toggle):
                    toggle.setChecked(checked)
            self.reviewer_bar_light_color_input.setText("#f2f2f2")
            self.reviewer_bar_dark_color_input.setText("#2C2C2C")
            self.reviewer_bar_blur_spinbox.setValue(0)
            self.reviewer_bar_opacity_spinbox.setValue(100)
            self.reviewer_bar_match_main_blur_spinbox.setValue(0)
            self.reviewer_bar_match_main_opacity_spinbox.setValue(100)
            self.reviewer_bar_match_reviewer_bg_blur_spinbox.setValue(0)
            self.reviewer_bar_match_reviewer_bg_opacity_spinbox.setValue(100)
            if hasattr(self, "reviewer_bar_match_overview_bg_blur_spinbox"):
                self.reviewer_bar_match_overview_bg_blur_spinbox.setValue(0)
                self.reviewer_bar_match_overview_bg_opacity_spinbox.setValue(100)
            self._clear_theme_gallery_selection("reviewer_bar_bg")
            self._sync_reviewer_bottom_bar_controls()

        if hasattr(self, "profile_pic_color_only_toggle"):
            self.profile_pic_dynamic_toggle.setChecked(True)
            self.profile_pic_color_only_toggle.setChecked(True)
            self.profile_pic_accent_toggle.setChecked(True)
            self.profile_pic_single_color_input.setText("#8CACB4")
            self.profile_pic_light_color_input.setText("#8CACB4")
            self.profile_pic_dark_color_input.setText("#B8BDC3")
            self.profile_pic_opacity_slider.setValue(100)
            for key in ("profile_pic", "profile_pic_light", "profile_pic_dark"):
                self._clear_theme_gallery_selection(key)
            self._update_profile_picture_controls()

        if hasattr(self, "profile_bg_color_only_toggle"):
            self.profile_bg_dynamic_toggle.setChecked(True)
            self.profile_bg_color_only_toggle.setChecked(True)
            self.profile_bg_accent_toggle.setChecked(True)
            self.profile_bg_single_color_input.setText("#EEEEEE")
            self.profile_bg_light_color_input.setText("#EEEEEE")
            self.profile_bg_dark_color_input.setText("#3C3C3C")
            self.profile_bg_blur_slider.setValue(0)
            self.profile_bg_opacity_slider.setValue(100)
            self._clear_theme_gallery_selection("profile_bg")
            self._update_profile_background_controls()

        if hasattr(self, "box_effect_dynamic_toggle"):
            self._reset_box_effect_to_default()

        self._reset_loaded_reviewer_button_widgets_to_default()

    def _delete_user_theme(self, theme_name: str):
        """Confirms and deletes a user theme after the hold-to-delete gesture completes."""
        filename = theme_name.lower().replace(" ", "_") + ".json"
        filepath = os.path.join(self.user_themes_path, filename)

        if not self._confirm_delete_dialog(
            "Delete Theme",
            "Delete theme?",
            f"'{theme_name}' will be permanently removed from Your themes.",
        ):
            return

        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                show_settings_toast(self, f"{tr('theme_deleted_toast', 'Theme deleted:')} {theme_name}")
                _, user_themes = self._load_themes()
                self._populate_grid_with_themes(self.user_themes_grid_layout, user_themes, deletable=True)
            else:
                QMessageBox.warning(self, "Error", f"Could not find theme file: {filename}")
        except OSError as e:
            QMessageBox.critical(self, "Error", f"Could not delete theme file:\n{e}")

    def _show_theme_preparing_state(self):
        if self._theme_preparing_overlay is not None:
            return

        palette = self._settings_palette()
        accent = self._settings_accent_color()
        overlay_bg = "rgba(0, 0, 0, 120)" if theme_manager.night_mode else "rgba(17, 24, 39, 70)"
        panel_bg = palette.get("--canvas-inset", "#242424" if theme_manager.night_mode else "#ffffff")
        fg = palette.get("--fg", "#f4f4f5" if theme_manager.night_mode else "#111827")
        border = palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")

        overlay = QFrame(self)
        overlay.setObjectName("themePreparingOverlay")
        overlay.setGeometry(self.rect())
        overlay.setStyleSheet(f"""
            QFrame#themePreparingOverlay {{
                background-color: {overlay_bg};
                border: none;
            }}
            QFrame#themePreparingPanel {{
                background-color: {panel_bg};
                border: 1px solid {border};
                border-radius: 24px;
            }}
            QLabel#themePreparingText {{
                color: {fg};
                background: transparent;
                font-size: 17px;
                font-weight: 600;
            }}
        """)

        overlay_layout = QVBoxLayout(overlay)
        overlay_layout.setContentsMargins(24, 24, 24, 24)
        overlay_layout.addStretch()

        panel = QFrame(overlay)
        panel.setObjectName("themePreparingPanel")
        panel.setFixedSize(460, 190)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(28, 26, 28, 26)
        panel_layout.setSpacing(12)

        message = QLabel("Preparing your Onigiri")
        message.setObjectName("themePreparingText")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setWordWrap(True)

        panel_layout.addStretch()
        panel_layout.addWidget(message)
        panel_layout.addWidget(ThemePreparingPulseAnimation(accent, panel), 0, Qt.AlignmentFlag.AlignCenter)
        panel_layout.addStretch()

        overlay_layout.addWidget(panel, 0, Qt.AlignmentFlag.AlignCenter)
        overlay_layout.addStretch()

        self._theme_preparing_overlay = overlay
        overlay.raise_()
        overlay.show()
        if hasattr(self, "save_button"):
            self.save_button.setEnabled(False)
        if hasattr(self, "cancel_button"):
            self.cancel_button.setEnabled(False)
        try:
            mw.app.processEvents()
        except Exception:
            pass

    def _save_settings_after_theme_prepare(self):
        try:
            self.save_settings()
        except Exception:
            if hasattr(self, "save_button"):
                self.save_button.setEnabled(True)
            if hasattr(self, "cancel_button"):
                self.cancel_button.setEnabled(True)
            self._theme_prepare_save_in_progress = False
            raise
