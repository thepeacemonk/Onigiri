# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._icon_picker import DeckIconPickerDialog, IconPickerDialog
from ._widgets import *
from ._layout_base import *
from ._layout_main import *
from ._layout_sidebar import *
from ..emoji_sprites import path_for_emoji



class InfraMixin:
    def _system_icon(self, filename):
        icon_path = system_icon_path(filename)
        return QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

    def _settings_pill_button_stylesheet(self, min_height=32):
        palette = self._settings_palette()
        if theme_manager.night_mode:
            bg = palette.get("--highlight-bg", palette.get("--canvas-inset", "#303030"))
            hover_bg = palette.get("--highlight-bg", "#3a3a3a")
            border = palette.get("--border", "#454545")
            fg = palette.get("--fg", "#f9fafb")
            accent = palette.get("--accent-color", DEFAULTS["colors"]["dark"]["--accent-color"])
        else:
            bg = palette.get("--highlight-bg", palette.get("--canvas-inset", "#f9fafb"))
            hover_bg = palette.get("--highlight-bg", "#f3f4f6")
            border = palette.get("--border", "#e5e7eb")
            fg = palette.get("--fg", "#111827")
            accent = palette.get("--accent-color", DEFAULTS["colors"]["light"]["--accent-color"])

        radius = max(12, min_height // 2)
        content_height = max(1, min_height - 2)
        return f"""
            QPushButton {{
                min-height: {content_height}px;
                padding: 0 16px;
                border: 1px solid {border};
                border-radius: {radius}px;
                background-color: {bg};
                color: {fg};
                font-weight: 600;
            }}
            QPushButton:checked {{
                background-color: {accent};
                border-color: {accent};
                border-radius: {radius}px;
                color: #ffffff;
                font-weight: 700;
            }}
            QPushButton:hover:!checked {{
                background-color: {hover_bg};
                border-color: {accent};
                border-radius: {radius}px;
            }}
        """

    def _create_mode_segmented_control(self, current_mode, on_change):
        palette = self._settings_palette()
        accent = self.accent_color
        wrapper = QWidget()
        wrapper.setObjectName("modeSegmentedControl")
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        group = QButtonGroup(wrapper)
        group.setExclusive(True)
        buttons = {}
        for mode, label in [("light", tr("light_mode", "Light")), ("dark", tr("dark_mode", "Dark"))]:
            button = QPushButton(label)
            button.setObjectName("modeSegmentButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedHeight(42)
            button.setMinimumWidth(124)
            button.setChecked(mode == current_mode)
            group.addButton(button)
            buttons[mode] = button
            layout.addWidget(button)

        wrapper.setStyleSheet(f"""
            QPushButton#modeSegmentButton {{
                background-color: {palette.get("--canvas-inset", "#ffffff")};
                border: 1px solid {palette.get("--border", "#dcdde1")};
                border-radius: 21px;
                color: {palette.get("--fg-subtle", "#6f7177")};
                padding: 0 18px;
                font-size: 15px;
                font-weight: 700;
            }}
            QPushButton#modeSegmentButton:checked {{
                background-color: {accent};
                border-color: {accent};
                color: #ffffff;
            }}
            QPushButton#modeSegmentButton:hover:!checked {{
                background-color: {palette.get("--hover-bg", "#e9e9e9")};
                color: {palette.get("--fg", "#202124")};
            }}
        """)

        for mode, button in buttons.items():
            button.toggled.connect(lambda checked, m=mode: on_change(m) if checked else None)

        return wrapper

    def _rounded_setting_row_stylesheet(self, extra_style=""):
        palette = self._settings_palette()
        bg = palette.get("--canvas-inset", "#242424" if theme_manager.night_mode else "#ffffff")
        hover_bg = palette.get("--hover-bg", "#3a3a3a" if theme_manager.night_mode else "#f2f2f2")
        border = palette.get("--border", "#454545" if theme_manager.night_mode else "#dcdde1")
        return f"""
            QFrame {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 22px;
                {extra_style}
            }}
            QFrame:hover {{
                background-color: {hover_bg};
                border-radius: 22px;
            }}
            QLabel {{
                background-color: transparent;
                border: none;
            }}
        """

    def _reset_button_stylesheet(self, min_height=38):
        palette = self._settings_palette()
        bg = palette.get("--canvas-inset", "#242424" if theme_manager.night_mode else "#ffffff")
        hover_bg = palette.get("--hover-bg", "#3a3a3a" if theme_manager.night_mode else "#f2f2f2")
        border = palette.get("--border", "#454545" if theme_manager.night_mode else "#dcdde1")
        fg = palette.get("--fg-subtle", "#b7bcc5" if theme_manager.night_mode else "#6f7177")
        active_fg = palette.get("--fg", "#f4f4f5" if theme_manager.night_mode else "#202124")
        radius = max(12, min_height // 2)
        return f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: {radius}px;
                min-height: {min_height}px;
                padding: 0px 22px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover,
            QPushButton:pressed {{
                background-color: {hover_bg};
                color: {active_fg};
                border-color: {border};
                border-radius: {radius}px;
            }}
        """

    def _decorate_button(self, button, icon_filename=None, icon_size=18):
        if icon_filename:
            button.setIcon(self._themed_icon(icon_filename, self._settings_icon_color(), icon_size))
            button.setIconSize(QSize(icon_size, icon_size))
            button.setProperty("onigiri_icon_filename", icon_filename)
            button.setProperty("onigiri_icon_size", icon_size)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setAutoDefault(False)

    def _refresh_save_button_icon(self):
        if hasattr(self, "save_button"):
            self.save_button.setIcon(self._themed_icon("hg-check.svg", self._save_button_icon_color(), 16))
            self.save_button.setIconSize(QSize(18, 18))

    def _decorate_nav_sub_buttons(self, toggle_widget, icon_map):
        for page_name, icon_filename in icon_map.items():
            button = toggle_widget.sub_buttons.get(page_name)
            if button:
                self._decorate_button(button, icon_filename, 16)

    def create_search_page(self):
        page = SettingsSearchPage(self)
        page.page_requested.connect(self.navigate_to_page)
        return page

    def _clear_page_nav(self):
        if not hasattr(self, "page_nav_layout"):
            return
        while self.page_nav_layout.count():
            item = self.page_nav_layout.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()

    def _populate_page_nav(self, page_name):
        self._clear_page_nav()
        sections = self._page_nav_sections.get(page_name, [])
        # Keep the (transparent) nav bar visible even when empty so its expanding
        # size policy keeps reserving the stretch space that pushes header action
        # widgets (e.g. the Themes light/dark toggle) to the top-right.
        self.page_nav_bar.setVisible(True)
        for title, target_widget in sections:
            btn = QPushButton(title)
            btn.setObjectName("pageNavButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(30)
            btn.setMinimumWidth(btn.fontMetrics().horizontalAdvance(title) + 42)
            btn.clicked.connect(lambda checked=False, w=target_widget: self._scroll_to_widget(self.content_stack.currentWidget().findChild(QScrollArea), w))
            self.page_nav_layout.addWidget(btn)
        self._refresh_page_header_actions(page_name)

    def _set_page_header_action_widget(self, widget):
        if not hasattr(self, "page_header_actions_layout"):
            return
        while self.page_header_actions_layout.count():
            item = self.page_header_actions_layout.takeAt(0)
            if existing := item.widget():
                existing.setParent(None)
        self.page_header_actions_layout.addWidget(widget)
        self.page_header_actions.setVisible(True)

    def _refresh_page_header_actions(self, page_name):
        if not hasattr(self, "page_header_actions"):
            return
        if page_name == "Themes" and hasattr(self, "theme_preview_mode_widget"):
            self._set_page_header_action_widget(self.theme_preview_mode_widget)
            return
        self.page_header_actions.setVisible(False)

    def _animate_page_transition(self):
        current_widget = self.content_stack.currentWidget()
        if not current_widget:
            return
        effect = QGraphicsOpacityEffect(current_widget)
        current_widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(150)
        animation.setStartValue(0.82)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda w=current_widget: w.setGraphicsEffect(None))
        self._page_transition_animation = animation
        animation.start()

    def _polish_created_page(self, page_widget):
        scroll_area = page_widget.findChild(QScrollArea)
        content_widget = scroll_area.widget() if scroll_area else None
        content_layout = content_widget.layout() if content_widget else None
        if content_layout:
            self._remove_trailing_layout_stretches(content_layout)
        self._ensure_rounded_buttons()

    def _on_section_toggled(self, toggled_widget, checked):
        return

    def _create_inner_group(self, title):
        container = QFrame()
        container.setObjectName("innerGroup")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(14, 12, 14, 12)
        main_layout.setSpacing(8)

        container.header_layout = QHBoxLayout()
        container.header_layout.setContentsMargins(0, 0, 0, 0)
        container.header_layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        container.header_layout.addWidget(title_label)
        container.header_layout.addStretch()
        main_layout.addLayout(container.header_layout)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 5, 0, 0)
        main_layout.addWidget(content_widget)

        return container, content_layout

    def _create_responsive_row(self, spacing=8):
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = FlowLayout(container, margin=0, spacing=spacing)
        layout.setContentsMargins(0, 2, 0, 2)
        return container, layout

    def _create_control_row(self, title, control_widget):
        row = QFrame()
        row.setObjectName("settingRow")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(row)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        label = QLabel(title)
        label.setObjectName("settingRowTitle")
        label.setWordWrap(True)
        layout.addWidget(label)
        layout.addWidget(control_widget)

        return row

    def _add_header_widget(self, container, widget):
        header_layout = getattr(container, "header_layout", None)
        if header_layout:
            header_layout.addWidget(widget)

    def _set_dynamic_mode_widgets_dimmed(self, widgets, dimmed):
        for widget in widgets:
            widget.setEnabled(not dimmed)
            effect = widget.graphicsEffect()
            if dimmed:
                if not isinstance(effect, QGraphicsOpacityEffect):
                    effect = QGraphicsOpacityEffect(widget)
                    widget.setGraphicsEffect(effect)
                effect.setOpacity(0.4)
            elif isinstance(effect, QGraphicsOpacityEffect):
                widget.setGraphicsEffect(None)

    def _background_config_value(self, spec, key, default=None):
        source = mw.col.conf if spec.get("storage") == "col" else self.current_config
        return source.get(key, default)

    def _background_cover_image_with_effect(self, image_path, width, height, blur=0, offset=None, vertical_anchor="center"):
        source = QImage(image_path)
        if source.isNull():
            return QPixmap()

        scaled = source.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        offset = offset or QPoint(0, 0)
        max_x = max(0, scaled.width() - width)
        max_y = max(0, scaled.height() - height)
        x = max(0, min(max_x, int((scaled.width() - width) / 2 - offset.x())))
        if vertical_anchor == "bottom":
            y = max_y
        else:
            y = max(0, min(max_y, int((scaled.height() - height) / 2 - offset.y())))
        cropped = scaled.copy(x, y, width, height)
        pixmap = QPixmap.fromImage(cropped)

        blur = int(blur or 0)
        if blur > 0:
            radius = float(blur) / 3.0
            bleed = max(12, int(radius * 3.0))
            padded = QPixmap(width + bleed * 2, height + bleed * 2)
            padded.fill(Qt.GlobalColor.transparent)
            painter = QPainter(padded)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.drawPixmap(bleed, bleed, pixmap)
            painter.drawPixmap(QRect(bleed, 0, width, bleed), pixmap, QRect(0, 0, width, 1))
            painter.drawPixmap(QRect(bleed, bleed + height, width, bleed), pixmap, QRect(0, height - 1, width, 1))
            painter.drawPixmap(QRect(0, bleed, bleed, height), pixmap, QRect(0, 0, 1, height))
            painter.drawPixmap(QRect(bleed + width, bleed, bleed, height), pixmap, QRect(width - 1, 0, 1, height))
            painter.drawPixmap(QRect(0, 0, bleed, bleed), pixmap, QRect(0, 0, 1, 1))
            painter.drawPixmap(QRect(bleed + width, 0, bleed, bleed), pixmap, QRect(width - 1, 0, 1, 1))
            painter.drawPixmap(QRect(0, bleed + height, bleed, bleed), pixmap, QRect(0, height - 1, 1, 1))
            painter.drawPixmap(QRect(bleed + width, bleed + height, bleed, bleed), pixmap, QRect(width - 1, height - 1, 1, 1))
            painter.end()
            blurred = self._qt_blurred_pixmap(padded, radius)
            return blurred.copy(bleed, bleed, width, height)

        return pixmap

    def _qt_blurred_pixmap(self, pixmap, radius):
        if pixmap.isNull() or radius <= 0:
            return pixmap

        pad = max(8, int(radius * 2))
        padded = QPixmap(pixmap.width() + pad * 2, pixmap.height() + pad * 2)
        padded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(padded)
        painter.drawPixmap(pad, pad, pixmap)
        painter.end()

        scene = QGraphicsScene()
        item = QGraphicsPixmapItem(padded)
        effect = QGraphicsBlurEffect()
        effect.setBlurRadius(radius)
        item.setGraphicsEffect(effect)
        scene.addItem(item)
        scene.setSceneRect(QRectF(0, 0, padded.width(), padded.height()))

        blurred = QPixmap(padded.size())
        blurred.fill(Qt.GlobalColor.transparent)
        painter = QPainter(blurred)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        scene.render(
            painter,
            QRectF(0, 0, padded.width(), padded.height()),
            QRectF(0, 0, padded.width(), padded.height()),
        )
        painter.end()
        return blurred.copy(pad, pad, pixmap.width(), pixmap.height())

    def _action_buttons_preview_mode(self):
        return getattr(self, "actionbtns_preview_mode", "dark" if theme_manager.night_mode else "light")

    def _on_action_buttons_preview_mode_toggled(self, mode):
        self.actionbtns_preview_mode = "dark" if mode == "dark" else "light"
        self._populate_action_buttons_reorder_list()
        self._update_action_buttons_preview()

    def _action_button_order(self):
        # Visible action buttons (and any unarchived external entries), in order.
        # May legitimately be empty if the user archived every button.
        return self._action_button_visible_ids()

    def _measure_action_buttons_list(self, ids, card_width):
        row_height = max(22.0, min(30.0, card_width * 0.11))
        gap = max(4.0, card_width * 0.03)
        sub_row = row_height * 0.9
        total = 0.0
        for action_id in ids:
            if action_id == "add":
                total += row_height * 1.25 + gap
            elif action_id == "more":
                total += row_height + gap + len(self.ACTION_BUTTON_MORE_CHILDREN) * sub_row + gap * 0.5
            else:
                total += row_height + gap
        return max(0.0, total - gap)

    def _draw_action_buttons_list(self, painter, rect, mode, ids):
        # Row metrics must match _measure_action_buttons_list so the card height
        # the preview computes actually fits the rows we paint here.
        row_height = max(22.0, min(30.0, rect.width() * 0.11))
        gap = max(4.0, rect.width() * 0.03)
        sub_row = row_height * 0.9
        icon_size = row_height * 0.56
        left_pad = max(6.0, rect.width() * 0.05)
        text_color = QColor(self._deck_icon_text_color(mode))
        label_font = QFont(self.font())
        label_font.setPointSize(max(7, int(row_height * 0.40)))
        metrics = QFontMetrics(label_font)

        def draw_row(action_id, x_offset, height, dashed=False):
            row_rect = QRectF(rect.x() + x_offset, draw_row.y, rect.width() - x_offset, height)
            icon_rect = QRectF(
                row_rect.x() + left_pad,
                row_rect.y() + (height - icon_size) / 2,
                icon_size,
                icon_size,
            )
            icon_color = self._action_button_preview_icon_color(action_id, mode)
            if dashed:
                button_path = QPainterPath()
                button_path.addRoundedRect(row_rect.adjusted(0, gap * 0.2, 0, -gap * 0.2), height * 0.28, height * 0.28)
                dash_color = QColor(text_color)
                dash_color.setAlpha(120)
                dash_pen = QPen(dash_color)
                dash_pen.setWidthF(1.0)
                dash_pen.setStyle(Qt.PenStyle.DashLine)
                painter.setPen(dash_pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(button_path)
            self._draw_box_effect_preview_icon(painter, icon_rect, self._action_icon_preview_value(action_id), icon_color)
            painter.setFont(label_font)
            painter.setPen(text_color)
            avail = max(0.0, row_rect.right() - icon_rect.right() - left_pad)
            label = self._sidebar_preview_action_label(action_id)
            label = metrics.elidedText(label, Qt.TextElideMode.ElideRight, int(avail))
            painter.drawText(
                QRectF(icon_rect.right() + left_pad * 0.7, row_rect.y(), avail, height),
                Qt.AlignmentFlag.AlignVCenter,
                label,
            )

        draw_row.y = rect.y()
        for action_id in ids:
            if draw_row.y > rect.bottom() + 0.5:
                break
            if action_id == "add":
                height = row_height * 1.25
                draw_row(action_id, 0.0, height, dashed=True)
                draw_row.y += height + gap
            elif action_id == "more":
                draw_row(action_id, 0.0, row_height)
                draw_row.y += row_height + gap * 0.5
                for child in self.ACTION_BUTTON_MORE_CHILDREN:
                    if draw_row.y > rect.bottom() + 0.5:
                        break
                    draw_row(child, left_pad * 1.4, sub_row)
                    draw_row.y += sub_row
                draw_row.y += gap * 0.5
            else:
                draw_row(action_id, 0.0, row_height)
                draw_row.y += row_height + gap

    def _draw_action_buttons_collapsed(self, painter, rect, mode, ids):
        n = len(ids)
        if n <= 0:
            return
        text_color = QColor(self._deck_icon_text_color(mode))
        min_gap = max(4.0, rect.width() * 0.02)
        max_button = min(34.0, rect.width() * 0.16)
        button_size = max(12.0, min(max_button, (rect.width() - (n - 1) * min_gap) / n))
        gap = (rect.width() - n * button_size) / (n - 1) if n > 1 else 0.0
        gap = max(0.0, gap)
        y = rect.y() + max(0.0, (rect.height() - button_size) / 2)
        for index, action_id in enumerate(ids):
            x = rect.x() + index * (button_size + gap)
            button_rect = QRectF(x, y, button_size, button_size)
            pill_path = QPainterPath()
            pill_path.addRoundedRect(button_rect, button_size * 0.3, button_size * 0.3)
            tint = QColor(text_color)
            tint.setAlpha(26)
            painter.fillPath(pill_path, QBrush(tint))
            icon_rect = button_rect.adjusted(
                button_size * 0.24, button_size * 0.24, -button_size * 0.24, -button_size * 0.24
            )
            self._draw_box_effect_preview_icon(
                painter, icon_rect, self._action_icon_preview_value(action_id), self._action_button_preview_icon_color(action_id, mode)
            )

    def _render_action_buttons_preview_pixmap(self):
        preview = getattr(self, "actionbtns_preview", None)
        if preview is None:
            return QPixmap()
        size = preview.size()
        width = max(1, size.width())
        height = max(1, size.height())
        mode = self._action_buttons_preview_mode()
        action_mode = self._sidebar_actions_mode()
        dpr = max(1.0, preview.devicePixelRatioF())
        target = QPixmap(int(width * dpr), int(height * dpr))
        target.setDevicePixelRatio(dpr)
        target.fill(Qt.GlobalColor.transparent)
        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        rect = QRectF(1, 1, width - 2, height - 2)
        outer_path = QPainterPath()
        outer_path.addRoundedRect(rect, 22, 22)
        painter.setClipPath(outer_path)

        background = QPixmap(width, height)
        background.fill(Qt.GlobalColor.transparent)
        bg_painter = QPainter(background)
        bg_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bg_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self._draw_box_effect_background_layer(bg_painter, QRectF(0, 0, width, height), mode)
        bg_painter.end()
        painter.drawPixmap(0, 0, background)

        margin = max(0, self._sidebar_frame_slider_value("margin", "modern_menu_sidebar_margin", 10))
        radius = max(0, self._sidebar_frame_slider_value("radius", "modern_menu_sidebar_radius", 15))
        stroke_width = max(0, self._sidebar_frame_slider_value("stroke", "modern_menu_sidebar_stroke", 1))
        blur = max(0, self._sidebar_frame_slider_value("blur", "modern_menu_sidebar_bg_blur", 0))
        opacity = max(0, min(100, self._sidebar_frame_slider_value("opacity", "modern_menu_sidebar_bg_opacity", 100)))

        available = rect.adjusted(margin, margin, -margin, -margin)
        ids = self._action_button_order()

        card_width = max(190.0, min(available.width() * 0.66, available.width(), 320.0))
        pad = max(10.0, card_width * 0.07)
        content_rect_width = card_width - 2 * pad

        if action_mode == "archived":
            content_height = 40.0
        elif action_mode == "collapsed":
            content_height = max(28.0, min(40.0, content_rect_width * 0.18))
        else:
            content_height = self._measure_action_buttons_list(ids, content_rect_width)
        card_height = min(available.height(), content_height + 2 * pad)
        card_height = max(card_height, 60.0)

        card_rect = QRectF(
            available.center().x() - card_width / 2,
            available.center().y() - card_height / 2,
            card_width,
            card_height,
        )
        card_path = QPainterPath()
        card_path.addRoundedRect(card_rect, radius, radius)

        painter.save()
        painter.setClipPath(card_path, Qt.ClipOperation.IntersectClip)
        if blur > 0 and not background.isNull():
            blurred = self._qt_blurred_pixmap(background, float(blur) / 3.0)
            if not blurred.isNull():
                painter.drawPixmap(0, 0, blurred)
        fill_color = QColor(self._sidebar_preview_fill_color(mode))
        fill_color.setAlphaF(max(0.0, min(1.0, opacity / 100.0)))
        painter.fillPath(card_path, QBrush(fill_color))
        image_path = self._sidebar_preview_image_path(mode)
        if image_path:
            image = self._background_cover_image_with_effect(
                image_path,
                max(1, int(card_rect.width())),
                max(1, int(card_rect.height())),
                blur,
            )
            if not image.isNull():
                painter.setOpacity(max(0.0, min(1.0, opacity / 100.0)))
                painter.drawPixmap(int(card_rect.x()), int(card_rect.y()), image)
                painter.setOpacity(1.0)

        content_rect = card_rect.adjusted(pad, pad, -pad, -pad)
        if action_mode == "archived":
            text_color = QColor(self._deck_icon_text_color(mode))
            text_color.setAlpha(150)
            painter.setPen(text_color)
            font = QFont(self.font())
            font.setPointSize(max(8, int(content_rect.width() * 0.06)))
            painter.setFont(font)
            painter.drawText(content_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, tr("archived_hidden_short", "Hidden"))
        elif action_mode == "collapsed":
            self._draw_action_buttons_collapsed(painter, content_rect, mode, ids)
        else:
            self._draw_action_buttons_list(painter, content_rect, mode, ids)
        painter.restore()

        if stroke_width > 0:
            border_color = QColor(self.current_config.get("colors", {}).get(mode, {}).get(
                "--border", "#4b5563" if mode == "dark" else "#d1d5db"
            ))
            border_pen = QPen(border_color)
            border_pen.setWidth(stroke_width)
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(card_path)

        painter.setClipping(False)
        painter.setPen(QPen(QColor("#4b5563" if theme_manager.night_mode else "#d1d5db"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(outer_path)
        painter.end()
        return target

    def _update_action_buttons_preview(self):
        preview = getattr(self, "actionbtns_preview", None)
        if preview is None:
            return
        pixmap = self._render_action_buttons_preview_pixmap()
        if not pixmap.isNull():
            preview.setPixmap(pixmap)

    def _create_action_buttons_designer(self):
        """Dedicated 'Action Button Customization' card: a preview that mirrors
        the sidebar frame plus controls to switch the layout mode and reorder /
        restyle the individual action buttons."""
        if not hasattr(self, "_action_button_icon_colors"):
            self._action_button_icon_colors = {}
            for key in self.ACTION_BUTTON_ORDER_IDS + self.ACTION_BUTTON_MORE_CHILDREN:
                stored = mw.col.conf.get(f"modern_menu_icon_color_{key}", "")
                if stored and QColor(stored).isValid():
                    self._action_button_icon_colors[key] = stored
        if not hasattr(self, "_action_button_icon_overrides"):
            self._action_button_icon_overrides = {}
        # Seed/normalize the working layout (source of truth for both previews).
        self._sidebar_layout_working_config()

        designer = QFrame()
        designer.setObjectName("mainBackgroundDesigner")
        designer_layout = QVBoxLayout(designer)
        designer_layout.setContentsMargins(0, 8, 0, 8)
        designer_layout.setSpacing(14)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title_label = QLabel(tr("action_button_customization", "Action Button Customization"))
        title_label.setObjectName("sectionTitle")
        title_label.setWordWrap(False)
        title_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        header.addWidget(title_label)
        header.addStretch()

        self.actionbtns_preview_mode = "dark" if theme_manager.night_mode else "light"
        mode_widget, mode_toggle = self._create_light_dark_mode_toggle(
            self.actionbtns_preview_mode,
            self._on_action_buttons_preview_mode_toggled,
        )
        self.actionbtns_preview_mode_widget = mode_widget
        self.actionbtns_preview_mode_toggle = mode_toggle
        header.addWidget(mode_widget)

        reset_button = QPushButton(tr("reset_bg_default"))
        reset_button.setObjectName("mainBackgroundResetButton")
        reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        reset_button.setFixedHeight(34)
        reset_button.setMinimumWidth(160)
        reset_button.setMaximumWidth(240)
        reset_button.clicked.connect(self._reset_action_buttons_to_default)
        header.addSpacing(10)
        header.addWidget(reset_button)
        designer_layout.addLayout(header)

        body = QWidget()
        outer = QHBoxLayout(body)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(24)
        designer_layout.addWidget(body)

        preview = BackgroundPreviewLabel(aspect_ratio=1.2, minimum_preview_height=420)
        preview.setObjectName("mainBackgroundPreview")
        preview.setMinimumSize(300, 420)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview.setProperty("action_buttons_preview", True)
        preview.installEventFilter(self)
        self.actionbtns_preview = preview

        controls = QWidget()
        controls.setMinimumWidth(0)
        controls.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(14)

        # Copy of the "Action Buttons" mode selector that lives in the Sidebar
        # Customization card; kept in sync with it both ways.
        self.action_buttons_mode_group = QButtonGroup(self)
        self.action_buttons_mode_group.setExclusive(True)
        current_actions_mode = self.current_config.get("sidebarActionsMode", "list")
        if current_actions_mode not in {"list", "collapsed", "archived"}:
            current_actions_mode = "list"
        mode_container = self._create_organize_segmented_control(
            [
                ("list", tr("list_default_short", "List")),
                ("collapsed", tr("collapsed_toolbar_short", "Collapsed")),
                ("archived", tr("archived_hidden_short", "Hidden")),
            ],
            self.action_buttons_mode_group,
            current_actions_mode,
            "sidebar_actions_mode",
            fill_width=True,
            segment_height=28,
            min_button_width=62,
        )
        self.action_buttons_mode_group.buttonToggled.connect(
            lambda button, checked: self._on_action_buttons_mode_selected(button) if checked else None
        )
        controls_layout.addWidget(
            self._create_main_bg_value_row(tr("action_buttons_position_label", "Action Buttons Position"), mode_container)
        )

        order_header = QHBoxLayout()
        order_header.setContentsMargins(0, 0, 0, 0)
        order_header.setSpacing(10)
        order_title = QLabel(tr("organize_action_buttons", "Organize Action Buttons"))
        order_title.setObjectName("mainBackgroundControlLabel")
        order_title.setStyleSheet("font-weight: 600;")
        order_header.addWidget(order_title)
        order_header.addStretch()

        archived_button = QPushButton(tr("archived_buttons_label", "Archived Buttons"))
        archived_button.setObjectName("mainBackgroundResetButton")
        archived_button.setCursor(Qt.CursorShape.PointingHandCursor)
        archived_button.setFixedHeight(30)
        archived_button.clicked.connect(self._open_archived_buttons_dialog)
        order_header.addWidget(archived_button)
        controls_layout.addLayout(order_header)

        order_help = QLabel(tr("action_buttons_reorder_help_v2", "Drag to reorder. Right-click a button to archive or customize it."))
        order_help.setObjectName("sectionDescription")
        order_help.setWordWrap(True)
        controls_layout.addWidget(order_help)

        controls_layout.addWidget(self._create_action_buttons_reorder_list())
        controls_layout.addStretch()

        outer.addWidget(preview, 4)
        outer.addWidget(controls, 6)

        self._update_action_buttons_preview()
        # Recompute the (scrollbar-less) list height once it has been laid out
        # and styled, so the very first paint already shows every row.
        QTimer.singleShot(0, self._resize_reorder_list_to_contents)
        return designer

    def _create_action_buttons_reorder_list(self):
        palette = self._settings_palette()
        surface = palette.get("--canvas-inset", "#ffffff")
        fg = palette.get("--fg", "#202124")
        border = palette.get("--border", "#dcdde1")
        hover = palette.get("--hover-bg", "#ececec")
        accent = palette.get("--accent-color", self.accent_color)

        listw = QListWidget()
        listw.setObjectName("actionButtonReorderList")
        listw.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        listw.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        listw.setDefaultDropAction(Qt.DropAction.MoveAction)
        listw.setUniformItemSizes(True)
        listw.setSpacing(4)
        listw.setIconSize(QSize(22, 22))
        listw.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        listw.setFrameShape(QFrame.Shape.NoFrame)
        listw.setStyleSheet(f"""
            QListWidget#actionButtonReorderList {{
                background: transparent;
                border: none;
                outline: none;
            }}
            QListWidget#actionButtonReorderList::item {{
                background: {surface};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 9px 10px;
                margin: 2px 0px;
                color: {fg};
            }}
            QListWidget#actionButtonReorderList::item:hover {{
                background: {hover};
                border-color: {accent};
            }}
            QListWidget#actionButtonReorderList::item:selected {{
                background: {hover};
                border-color: {accent};
                color: {fg};
            }}
        """)
        # Show every row at once (no internal scrollbar); the card grows to fit
        # and the preview, sharing the row height, grows with it.
        listw.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        listw.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        listw.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        listw.customContextMenuRequested.connect(
            lambda pos: self._show_action_button_context_menu(listw, pos)
        )
        # InternalMove drags can surface as either rowsMoved or remove+insert, so
        # read the settled order back on the next event-loop tick from both.
        listw.model().rowsMoved.connect(
            lambda *args: QTimer.singleShot(0, lambda: self._on_action_buttons_reordered(listw))
        )
        listw.model().rowsRemoved.connect(
            lambda *args: QTimer.singleShot(0, lambda: self._on_action_buttons_reordered(listw))
        )
        self.action_buttons_reorder_list = listw
        self._populate_action_buttons_reorder_list()
        return listw

    def _populate_action_buttons_reorder_list(self):
        listw = getattr(self, "action_buttons_reorder_list", None)
        if listw is None:
            return
        self._populating_action_list = True
        listw.blockSignals(True)
        listw.clear()
        mode = self._action_buttons_preview_mode()
        icon_color = self._deck_icon_text_color(mode)
        for key in self._action_button_order():
            item = QListWidgetItem(self._sidebar_preview_action_label(key))
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsDragEnabled
            )
            pixmap = self._render_icon_value_pixmap(
                self._action_icon_preview_value(key),
                self._action_button_preview_icon_color(key, mode) or icon_color,
                22,
            )
            if not pixmap.isNull():
                item.setIcon(QIcon(native_safe_pixmap(pixmap)))
            listw.addItem(item)
        listw.blockSignals(False)
        self._populating_action_list = False
        self._resize_reorder_list_to_contents()

    def _resize_reorder_list_to_contents(self):
        listw = getattr(self, "action_buttons_reorder_list", None)
        if listw is None:
            return
        count = listw.count()
        if count <= 0:
            listw.setFixedHeight(60)
            return
        spacing = listw.spacing()
        row = listw.sizeHintForRow(0)
        if row <= 0:
            row = 46
        frame = 2 * listw.frameWidth()
        # Each item is inset by `spacing` on all sides, so the column adds
        # spacing between rows plus the top and bottom margins. A small per-row
        # buffer guards against the stylesheet padding being under-counted (so
        # the last row is never clipped — a few extra px is harmless).
        total = count * (row + 6) + (count + 1) * spacing + frame + 6
        listw.setFixedHeight(int(total))

    def _on_action_buttons_reordered(self, listw):
        if getattr(self, "_populating_action_list", False):
            return
        order = []
        for i in range(listw.count()):
            key = listw.item(i).data(Qt.ItemDataRole.UserRole)
            if key:
                order.append(key)
        if not order:
            return
        # Rebuild the working 'visible' list: keep non-managed entries (e.g. the
        # profile bar) where they are, and drop the reordered block in at the
        # first managed slot.
        working = self._sidebar_layout_working_config()
        managed = self._action_managed_ids()
        result = []
        inserted = False
        for key in working.get("visible", []):
            if key in managed:
                if not inserted:
                    result.extend(order)
                    inserted = True
            else:
                result.append(key)
        if not inserted:
            result.extend(order)
        working["visible"] = result
        self._update_action_buttons_preview()
        if hasattr(self, "sidebar_bg_preview"):
            self._update_modern_background_preview("sidebar")

    def _style_context_menu(self, menu):
        if theme_manager.night_mode:
            bg, fg, border, hover = "#2c2c2c", "#e8e8e8", "#4a4a4a", "#3a3a3a"
        else:
            bg, fg, border, hover = "#ffffff", "#202124", "#e0e0e0", "#f0f0f0"
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 10px;
                padding: 6px;
            }}
            QMenu::item {{
                background: transparent;
                padding: 7px 16px 7px 14px;
                border-radius: 6px;
                margin: 1px 2px;
            }}
            QMenu::item:selected {{
                background-color: {hover};
            }}
            QMenu::separator {{
                height: 1px;
                background: {border};
                margin: 4px 8px;
            }}
        """)

    def _show_action_button_context_menu(self, listw, pos):
        item = listw.itemAt(pos)
        if item is None:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(listw)
        self._style_context_menu(menu)
        archive_action = menu.addAction(tr("archive_button", "Archive button"))
        custom_action = menu.addAction(tr("custom_button", "Custom button"))
        chosen = menu.exec(listw.mapToGlobal(pos))
        if chosen is archive_action:
            self._archive_action_button(key)
        elif chosen is custom_action:
            self._open_action_button_icon_picker(key)

    def _archive_action_button(self, key):
        working = self._sidebar_layout_working_config()
        visible = working.setdefault("visible", [])
        archived = working.setdefault("archived", [])
        if key in visible:
            visible.remove(key)
        if key not in archived:
            archived.append(key)
        self._populate_action_buttons_reorder_list()
        self._refresh_archived_buttons_dialog()
        self._update_action_buttons_preview()
        if hasattr(self, "sidebar_bg_preview"):
            self._update_modern_background_preview("sidebar")

    def _unarchive_action_button(self, key):
        working = self._sidebar_layout_working_config()
        visible = working.setdefault("visible", [])
        archived = working.setdefault("archived", [])
        if key in archived:
            archived.remove(key)
        if key not in visible:
            visible.append(key)
        self._populate_action_buttons_reorder_list()
        self._refresh_archived_buttons_dialog()
        self._update_action_buttons_preview()
        if hasattr(self, "sidebar_bg_preview"):
            self._update_modern_background_preview("sidebar")

    def _clear_archived_buttons_dialog(self):
        self._archived_buttons_dialog = None
        self._archived_buttons_list = None

    def _refresh_archived_buttons_dialog(self):
        listw = getattr(self, "_archived_buttons_list", None)
        if listw is None:
            return
        listw.clear()
        mode = self._action_buttons_preview_mode()
        empty_color = self._deck_icon_text_color(mode)
        archived = self._action_button_archived_ids()
        if not archived:
            item = QListWidgetItem(tr("archived_buttons_empty", "No archived buttons."))
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            listw.addItem(item)
            return
        for key in archived:
            item = QListWidgetItem(self._action_button_display_label(key))
            item.setData(Qt.ItemDataRole.UserRole, key)
            pixmap = self._render_icon_value_pixmap(
                self._action_icon_preview_value(key),
                self._action_button_preview_icon_color(key, mode) or empty_color,
                22,
            )
            if not pixmap.isNull():
                item.setIcon(QIcon(native_safe_pixmap(pixmap)))
            listw.addItem(item)

    def _show_archived_button_context_menu(self, listw, pos):
        item = listw.itemAt(pos)
        if item is None:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if not key:
            return
        menu = QMenu(listw)
        self._style_context_menu(menu)
        unarchive_action = menu.addAction(tr("unarchive_button", "Unarchive button"))
        custom_action = menu.addAction(tr("custom_button", "Custom button"))
        chosen = menu.exec(listw.mapToGlobal(pos))
        if chosen is unarchive_action:
            self._unarchive_action_button(key)
        elif chosen is custom_action:
            self._open_action_button_icon_picker(key)

    def _set_action_button_icon(self, key, value):
        # The reorder list / archived dialog own the action-button icons now, so
        # stash the chosen filename as an override that the Save loop persists as
        # modern_menu_icon_<key>.
        if not hasattr(self, "_action_button_icon_overrides"):
            self._action_button_icon_overrides = {}
        self._action_button_icon_overrides[key] = value
        self._refresh_action_button_item(key)
        self._refresh_archived_buttons_dialog()
        self._update_action_buttons_preview()

    def _reset_action_button_icon(self, key):
        self._action_button_icon_colors.pop(key, None)
        self._set_action_button_icon(key, "")

    def _refresh_action_button_item(self, key):
        listw = getattr(self, "action_buttons_reorder_list", None)
        if listw is None:
            return
        mode = self._action_buttons_preview_mode()
        for i in range(listw.count()):
            item = listw.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == key:
                pixmap = self._render_icon_value_pixmap(
                    self._action_icon_preview_value(key),
                    self._action_button_preview_icon_color(key, mode),
                    22,
                )
                if not pixmap.isNull():
                    item.setIcon(QIcon(native_safe_pixmap(pixmap)))
                break

    def _on_action_buttons_mode_selected(self, button):
        mode = button.property("sidebar_actions_mode") if button else None
        if mode not in {"list", "collapsed", "archived"}:
            return
        # Keep the Sidebar Customization selector in sync.
        group = getattr(self, "sidebar_actions_mode_group", None)
        if group is not None:
            for other in group.buttons():
                if other.property("sidebar_actions_mode") == mode and not other.isChecked():
                    other.setChecked(True)
        self._update_action_buttons_preview()
        self._update_sidebar_actions_editor_visibility()

    def _reset_action_buttons_to_default(self):
        default_layout = DEFAULTS.get("sidebarButtonLayout", {})
        working = self._sidebar_layout_working_config()
        working["visible"] = list(default_layout.get("visible", []))
        working["archived"] = list(default_layout.get("archived", []))
        # External entries are archived by default.
        external = self._action_external_ids()
        for ext in external:
            if ext not in working["visible"] and ext not in working["archived"]:
                working["archived"].append(ext)
        self._action_button_icon_colors = {}
        self._action_button_icon_overrides = {}
        for key in self.ACTION_BUTTON_ORDER_IDS + self.ACTION_BUTTON_MORE_CHILDREN:
            self._action_button_icon_overrides[key] = ""
        # Default mode is "list".
        group = getattr(self, "action_buttons_mode_group", None)
        if group is not None:
            for button in group.buttons():
                if button.property("sidebar_actions_mode") == "list":
                    button.setChecked(True)
        self._populate_action_buttons_reorder_list()
        self._refresh_archived_buttons_dialog()
        self._update_action_buttons_preview()
        if hasattr(self, "sidebar_bg_preview"):
            self._update_modern_background_preview("sidebar")
        show_settings_toast(self, tr("action_buttons_reset_toast", "Action buttons reset to default"))

    def _action_external_ids(self):
        try:
            return set(sidebar_api.get_sidebar_entries().keys())
        except Exception:
            return set()

    def _action_managed_ids(self):
        return set(self.ACTION_BUTTON_ORDER_IDS) | self._action_external_ids()

    def _action_button_visible_ids(self):
        working = self._sidebar_layout_working_config()
        managed = self._action_managed_ids()
        return [k for k in working.get("visible", []) if k in managed]

    def _action_button_archived_ids(self):
        working = self._sidebar_layout_working_config()
        return list(working.get("archived", []))

    def _action_button_display_label(self, key):
        working = self._sidebar_layout_working_config()
        labels = working.get("labels", {}) if isinstance(working.get("labels"), dict) else {}
        override = labels.get(key)
        if isinstance(override, str) and override.strip():
            return override.strip()
        base = {
            "add": "add", "browse": "browse", "stats": "stats", "sync": "sync",
            "settings": "settings", "gamification": "onigiri_games", "more": "more",
            "get_shared": "get_shared", "create_deck": "create_deck", "import_file": "import_file",
        }
        if key in base:
            return tr(base[key]) or key.replace("_", " ").title()
        entry = sidebar_api.get_sidebar_entries().get(key)
        if entry is not None and getattr(entry, "label", None):
            return entry.label
        return key.replace("_", " ").title()

    def _action_icon_preview_value(self, key):
        overrides = getattr(self, "_action_button_icon_overrides", {})
        if key in overrides:
            filename = overrides[key]
        else:
            widget = next((w for w in getattr(self, "action_button_icon_widgets", []) if w.property("icon_key") == key), None)
            filename = widget.property("icon_filename") if widget else mw.col.conf.get(f"modern_menu_icon_{key}", "")
        if filename:
            return filename
        return f"system:{ICON_DEFAULTS.get(key, f'{key}.svg')}"

    def _schedule_stylesheet_apply(self, delay_ms=80):
        timer = getattr(self, "_pending_stylesheet_timer", None)
        if timer:
            timer.start(delay_ms)
        else:
            self.apply_stylesheet()

    def _ensure_rounded_buttons(self):
        palette = self._settings_palette()
        if theme_manager.night_mode:
            button_bg = palette.get("--highlight-bg", palette.get("--canvas-inset", "#303030"))
            hover_bg = palette.get("--highlight-bg", "#2d3748")
            fg = palette.get("--fg", "#f9fafb")
            muted_fg = palette.get("--fg-subtle", "#d1d5db")
            border = palette.get("--border", "#454545")
        else:
            button_bg = palette.get("--highlight-bg", palette.get("--canvas-inset", "#f9fafb"))
            hover_bg = palette.get("--highlight-bg", "#f3f4f6")
            fg = palette.get("--fg", "#111827")
            muted_fg = palette.get("--fg-subtle", "#6f7177")
            border = palette.get("--border", "#e5e7eb")

        full_button_style = f"""
            QPushButton {{
                background-color: {button_bg};
                color: {muted_fg};
                border: 1px solid {border};
                border-radius: 18px;
                padding: 7px 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            QPushButton:pressed,
            QPushButton:checked {{
                background-color: {hover_bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            QPushButton:disabled {{
                background-color: {button_bg};
                color: {muted_fg};
                border: 1px solid {border};
                border-radius: 18px;
            }}
        """
        radius_patch = """
            QPushButton { border-radius: 18px; }
            QPushButton:hover { border-radius: 18px; }
            QPushButton:pressed { border-radius: 18px; }
            QPushButton:checked { border-radius: 18px; }
            QPushButton:disabled { border-radius: 18px; }
        """
        for button in self.findChildren(QPushButton):
            style = button.styleSheet() or ""
            object_name = button.objectName() or ""
            if object_name in {"sidebarNavButton", "sidebarSectionToggle", "subItemButton", "saveSidebarButton", "cancelSidebarButton", "sidebarActionButton", "sidebarSearchButton", "searchSidebarButton", "fontAddButton", "fontRestoreButton", "fontColorLabelPill", "fontColorValuePill"}:
                continue
            if "onigiri-rounded-button-fix" in style:
                continue
            if style.strip():
                button.setStyleSheet(style + "\n/* onigiri-rounded-button-fix */\n" + radius_patch)
            else:
                button.setStyleSheet("/* onigiri-rounded-button-fix */\n" + full_button_style)

    def _create_toggle_row(self, toggle_widget, text_label, style_sheet=""):
        row = QFrame()
        row.setObjectName("settingRow")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row.setStyleSheet(self._rounded_setting_row_stylesheet(style_sheet))
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)
        layout.addWidget(QLabel(text_label))
        layout.addStretch()
        layout.addWidget(toggle_widget)
        return row

    def _create_goal_setting_row(self, title, description, spinbox, toggle_widget):
        row = QFrame()
        row.setObjectName("settingRow")
        row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("settingRowTitle")
        text_layout.addWidget(title_label)

        if description:
            desc_label = QLabel(description)
            desc_label.setWordWrap(True)
            desc_label.setObjectName("settingRowDescription")
            text_layout.addWidget(desc_label)

        text_layout.addStretch()
        layout.addWidget(text_container, 1)

        spinbox.setMaximumWidth(120)
        layout.addWidget(spinbox)
        layout.addSpacing(8)
        layout.addWidget(toggle_widget)

        return row

    def create_under_construction_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(tr("under_construction"))
        label.setStyleSheet("font-size: 20px; color: #888;")
        layout.addWidget(label)
        return page

    def _get_hook_name(self, hook):
        """Creates a unique, stable identifier for a hook function."""
        # Defer to the implementation in patcher.py to ensure consistency.
        from .. import patcher
        return patcher._get_hook_name(hook)

    def _get_external_hooks(self):
        """
        Calls the hook-finding logic from patcher.py, which is known to work,
        to prevent issues from code duplication or timing.
        """
        from .. import patcher
        # patcher._get_external_hooks() returns a list of FUNCTION objects.
        external_hook_functions = patcher._get_external_hooks()

        # We need a list of STRING identifiers for the settings dialog.
        return [patcher._get_hook_name(hook) for hook in external_hook_functions]

    @staticmethod
    def _create_layout_group(title, parent=None):
        group = QFrame(parent)
        group.setObjectName("LayoutGroup")
        group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(14, 12, 14, 14)
        group_layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("LayoutGroupTitle")
        title_label.setWordWrap(True)
        title_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        group_layout.addWidget(title_label)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        group_layout.addLayout(content_layout)

        return group, content_layout

    def _create_box_effect_retention_star_section(self):
        group = QWidget()
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Color cards live here now; only the cards matching the current
        # light/dark preview mode are shown (see _update_box_effect_controls).
        self.box_effect_color_stack = QStackedWidget()
        self.box_effect_color_stack.addWidget(self.box_effect_light_color_card)
        self.box_effect_color_stack.addWidget(self.box_effect_dark_color_card)
        layout.addWidget(self.box_effect_color_stack)

        self.box_effect_border_color_stack = QStackedWidget()
        self.box_effect_border_color_stack.addWidget(self.box_effect_border_light_color_card)
        self.box_effect_border_color_stack.addWidget(self.box_effect_border_dark_color_card)
        layout.addWidget(self.box_effect_border_color_stack)

        title_label = QLabel(tr("retention_stars_section", "Retention Stars"))
        title_label.setObjectName("sectionTitle")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        self.hide_retention_stars_check = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_retention_stars_check.setChecked(self.current_config.get("hideRetentionStars", False))
        self.hide_retention_stars_check.toggled.connect(self._on_hide_retention_stars_changed)
        card_palette = self._settings_palette()
        card_bg = card_palette.get("--canvas-inset", "#242424" if theme_manager.night_mode else "#ffffff")
        card_border = card_palette.get("--border", "#454545" if theme_manager.night_mode else "#dcdde1")
        hide_retention_stars_row = QFrame()
        hide_retention_stars_row.setObjectName("colorSelectorCard")
        hide_retention_stars_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hide_retention_stars_row.setStyleSheet(f"""
            QFrame#colorSelectorCard {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 16px;
            }}
        """)
        hide_retention_stars_layout = QHBoxLayout(hide_retention_stars_row)
        hide_retention_stars_layout.setContentsMargins(16, 8, 10, 8)
        hide_retention_stars_layout.setSpacing(12)
        hide_retention_stars_label = QLabel(tr("hide_stars_retention"))
        hide_retention_stars_label.setObjectName("mainBackgroundControlLabel")
        hide_retention_stars_layout.addWidget(hide_retention_stars_label)
        hide_retention_stars_layout.addStretch(1)
        hide_retention_stars_layout.addWidget(self.hide_retention_stars_check)

        if self.retention_star_widget is None:
            self.retention_star_widget = self._create_icon_control_widget(
                "retention_star", display_name=tr("retention_star"), compact=True
            )
        self.retention_star_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.retention_star_widget.setFixedWidth(96)

        for card in (
            self.box_effect_star_light_color_card,
            self.box_effect_star_dark_color_card,
            self.box_effect_empty_star_light_color_card,
            self.box_effect_empty_star_dark_color_card,
        ):
            card.hide()

        combined_row = QWidget()
        combined_row_layout = QHBoxLayout(combined_row)
        combined_row_layout.setContentsMargins(0, 0, 0, 0)
        combined_row_layout.setSpacing(10)
        combined_row_layout.addWidget(hide_retention_stars_row, 1)
        combined_row_layout.addWidget(self.retention_star_widget, 0, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(combined_row)

        return group

    def _on_box_effect_changed(self, *args):
        self._update_box_effect_controls()
        if hasattr(self, "overview_style_sync_toggle") and self.overview_style_sync_toggle.isChecked():
            self._update_overview_style_controls()
        if hasattr(self, "sidebar_bg_sync_box_toggle") and self.sidebar_bg_sync_box_toggle.isChecked():
            self._update_modern_background_preview("sidebar")

    def _update_box_effect_controls(self):
        if not hasattr(self, "box_effect_preview"):
            return
        dynamic = self.box_effect_dynamic_toggle.isChecked()
        color_label = "Light Color" if dynamic else "Color"
        self.box_effect_light_color_button.setText(color_label)
        self.box_effect_border_light_color_button.setText("Border Light" if dynamic else "Border Color")
        self.box_effect_star_light_color_button.setText("Star Light" if dynamic else "Star")
        self.box_effect_empty_star_light_color_button.setText("Empty Star Light" if dynamic else "Empty Star")
        if hasattr(self, "box_effect_preview_mode_widget"):
            self.box_effect_preview_mode_widget.setEnabled(dynamic)
            self.box_effect_preview_mode_widget.setToolTip("" if dynamic else "Enable Dynamic mode to switch light/dark palettes.")

        # The right column shows the cards for the active light/dark preview
        # mode only. When dynamic mode is off there is a single colour, so the
        # "light" cards stand in for it regardless of the preview mode.
        mode = self._box_effect_preview_mode()
        show_dark = dynamic and mode == "dark"
        if hasattr(self, "box_effect_color_stack"):
            self.box_effect_color_stack.setCurrentIndex(1 if show_dark else 0)
            self.box_effect_border_color_stack.setCurrentIndex(1 if show_dark else 0)
        else:
            self.box_effect_light_color_card.setVisible(not show_dark)
            self.box_effect_dark_color_card.setVisible(show_dark)
            self.box_effect_border_light_color_card.setVisible(not show_dark)
            self.box_effect_border_dark_color_card.setVisible(show_dark)

        single_color = self._box_effect_color_for_input(self.box_effect_single_color_input)
        light_color = self._box_effect_color_for_input(self.box_effect_light_color_input, single_color)
        dark_color = self._box_effect_color_for_input(self.box_effect_dark_color_input, single_color)
        self._style_main_background_color_button(self.box_effect_light_color_value_button, light_color)
        self._style_main_background_color_button(self.box_effect_dark_color_value_button, dark_color)

        border_single_color = self._box_effect_color_for_input(self.box_effect_border_single_color_input)
        border_light_color = self._box_effect_color_for_input(self.box_effect_border_light_color_input, border_single_color)
        border_dark_color = self._box_effect_color_for_input(self.box_effect_border_dark_color_input, border_single_color)
        self._style_main_background_color_button(self.box_effect_border_light_color_value_button, border_light_color)
        self._style_main_background_color_button(self.box_effect_border_dark_color_value_button, border_dark_color)

        star_single_color = self._box_effect_color_for_input(self.box_effect_star_single_color_input)
        star_light_color = self._box_effect_color_for_input(self.box_effect_star_light_color_input, star_single_color)
        star_dark_color = self._box_effect_color_for_input(self.box_effect_star_dark_color_input, star_single_color)
        empty_star_single_color = self._box_effect_color_for_input(self.box_effect_empty_star_single_color_input)
        empty_star_light_color = self._box_effect_color_for_input(self.box_effect_empty_star_light_color_input, empty_star_single_color)
        empty_star_dark_color = self._box_effect_color_for_input(self.box_effect_empty_star_dark_color_input, empty_star_single_color)
        self._style_main_background_color_button(self.box_effect_star_light_color_value_button, star_light_color)
        self._style_main_background_color_button(self.box_effect_star_dark_color_value_button, star_dark_color)
        self._style_main_background_color_button(self.box_effect_empty_star_light_color_value_button, empty_star_light_color)
        self._style_main_background_color_button(self.box_effect_empty_star_dark_color_value_button, empty_star_dark_color)
        self.box_effect_blur_value_label.setText(f"{self.box_effect_blur_slider.value()}%")
        self.box_effect_opacity_value_label.setText(f"{self.box_effect_opacity_slider.value()}%")
        self.box_effect_radius_value_label.setText(f"{self.box_effect_radius_slider.value()}px")
        self.box_effect_stroke_value_label.setText(f"{self.box_effect_stroke_slider.value()}px")
        self._sync_box_effect_color_config()
        self._update_box_effect_preview()

    def _reset_box_effect_to_default(self):
        self.box_effect_dynamic_toggle.setChecked(True)
        self.box_effect_single_color_input.setText(DEFAULTS["colors"]["light"]["--canvas-inset"])
        self.box_effect_light_color_input.setText(DEFAULTS["colors"]["light"]["--canvas-inset"])
        self.box_effect_dark_color_input.setText(DEFAULTS["colors"]["dark"]["--canvas-inset"])
        self.box_effect_border_single_color_input.setText(DEFAULTS["colors"]["light"]["--border"])
        self.box_effect_border_light_color_input.setText(DEFAULTS["colors"]["light"]["--border"])
        self.box_effect_border_dark_color_input.setText(DEFAULTS["colors"]["dark"]["--border"])
        self.box_effect_blur_slider.setValue(0)
        self.box_effect_opacity_slider.setValue(100)
        self.box_effect_radius_slider.setValue(20)
        self.box_effect_stroke_slider.setValue(1)
        self._update_box_effect_controls()
        if hasattr(self, "sidebar_bg_sync_box_toggle") and self.sidebar_bg_sync_box_toggle.isChecked():
            self._update_modern_background_preview("sidebar")
        show_settings_toast(self, tr("box_effect_reset_toast", "Box effect reset to default"))

    def _draw_box_effect_background_layer(self, painter, rect, mode):
        state = self._main_background_state_for_box_preview(mode)
        painter.fillRect(rect, QColor(state["color"]))
        image_path = state.get("image_path", "")
        if image_path and os.path.exists(image_path):
            image = self._background_cover_image_with_effect(
                image_path,
                int(rect.width()),
                int(rect.height()),
                int(state.get("blur", 0) or 0),
            )
            if not image.isNull():
                painter.setOpacity(max(0.0, min(1.0, float(state.get("opacity", 100)) / 100.0)))
                painter.drawPixmap(int(rect.x()), int(rect.y()), image)
                painter.setOpacity(1.0)

    def _box_effect_preview_mode(self):
        return getattr(self, "box_effect_preview_mode", "dark" if theme_manager.night_mode else "light")

    def _on_box_effect_preview_mode_toggled(self, mode):
        self.box_effect_preview_mode = "dark" if mode == "dark" else "light"
        self._update_box_effect_controls()
        if hasattr(self, "overview_style_sync_toggle") and self.overview_style_sync_toggle.isChecked():
            self._update_overview_style_preview()

    def _box_effect_preview_icon_path(self, key):
        if key == "retention_star" and hasattr(self, "retention_star_widget") and self.retention_star_widget:
            filename = self.retention_star_widget.property("icon_filename")
            if filename:
                return filename
        filename = mw.col.conf.get(f"modern_menu_icon_{key}", "")
        if filename:
            return filename
        return f"system:{ICON_DEFAULTS.get(key, f'{key}.svg')}"

    def _icon_value_path(self, icon_value):
        if not icon_value or str(icon_value).startswith("emoji:"):
            return ""
        icon_value = str(icon_value)
        if icon_value.startswith("system:"):
            path = system_icon_path(icon_value[len("system:"):])
            return path if os.path.exists(path) else ""
        for folder in ("custom_deck_icons", "icons"):
            path = os.path.join(self.addon_path, "user_files", folder, icon_value)
            if os.path.exists(path):
                return path
        path = system_icon_path(icon_value)
        return path if os.path.exists(path) else ""

    def _emoji_sprite_path(self, emoji):
        return path_for_emoji(self.addon_path, emoji)

    def _render_icon_value_pixmap(self, icon_value, color, size):
        size = max(1, int(size))
        dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
        pixmap = QPixmap(int(size * dpr), int(size * dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        if not icon_value:
            return pixmap
        icon_value = str(icon_value)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        try:
            if icon_value.startswith("emoji:"):
                emoji = icon_value[len("emoji:"):]
                sprite_path = self._emoji_sprite_path(emoji)
                if sprite_path:
                    renderer = QSvgRenderer(sprite_path)
                    if renderer.isValid():
                        renderer.render(painter, svg_contain_rect(renderer, size))
                else:
                    font = QFont(self.font())
                    font.setPointSize(max(8, int(size * 0.72)))
                    painter.setFont(font)
                    painter.setPen(QColor(color))
                    painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, emoji)
            else:
                path = self._icon_value_path(icon_value)
                if path.lower().endswith(".svg"):
                    with open(path, "r", encoding="utf-8") as icon_file:
                        svg_xml = icon_file.read()
                    if "currentColor" in svg_xml:
                        svg_xml = svg_xml.replace("currentColor", color)
                    renderer = QSvgRenderer(svg_xml.encode("utf-8"))
                    if renderer.isValid():
                        renderer.render(painter, svg_contain_rect(renderer, size))
                elif path:
                    source = QPixmap(path)
                    if not source.isNull():
                        scaled = source.scaled(int(size * dpr), int(size * dpr), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        scaled.setDevicePixelRatio(dpr)
                        painter.drawPixmap(int((size - scaled.width()) / 2), int((size - scaled.height()) / 2), scaled)
                if path:
                    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                    painter.fillRect(QRectF(0, 0, size, size), QColor(color))
        except Exception:
            pass
        painter.end()
        return pixmap

    def _draw_box_effect_preview_icon(self, painter, rect, icon_path, color):
        if not icon_path:
            return
        painter.save()
        try:
            icon_width = max(1, int(rect.width()))
            icon_height = max(1, int(rect.height()))
            icon_pixmap = self._render_icon_value_pixmap(icon_path, color, max(icon_width, icon_height))
            painter.drawPixmap(rect.toRect(), icon_pixmap)
        except Exception:
            pass
        painter.restore()

    def _draw_box_effect_sample(self, painter, rect, mode, background_pixmap):
        box_color = QColor(self._box_effect_color(mode))
        blur_radius = (self.box_effect_blur_slider.value() / 100.0) * 20.0
        fill_alpha = max(0.0, min(1.0, self.box_effect_opacity_slider.value() / 100.0))
        if blur_radius > 0:
            fill_alpha = min(fill_alpha, 0.62)
        box_color.setAlphaF(fill_alpha)

        painter.save()
        path = QPainterPath()
        radius = float(self.box_effect_radius_slider.value() if hasattr(self, "box_effect_radius_slider") else 20)
        path.addRoundedRect(rect, radius, radius)
        if blur_radius > 0 and background_pixmap and not background_pixmap.isNull():
            blurred = self._qt_blurred_pixmap(background_pixmap, blur_radius)
            if not blurred.isNull():
                painter.save()
                painter.setClipPath(path, Qt.ClipOperation.IntersectClip)
                painter.drawPixmap(0, 0, blurred)
                painter.restore()
        painter.fillPath(path, QBrush(box_color))
        stroke_width = max(0, int(self.box_effect_stroke_slider.value() if hasattr(self, "box_effect_stroke_slider") else 1))
        if stroke_width > 0:
            border_pen = QPen(QColor(self._box_effect_border_color(mode)))
            border_pen.setWidth(stroke_width)
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        hide_stars = hasattr(self, "hide_retention_stars_check") and self.hide_retention_stars_check.isChecked()
        title_top = 0.13 if not hide_stars else 0.24
        small_title_top = 0.34 if not hide_stars else 0.43
        body_top = 0.49 if not hide_stars else 0.58

        painter.setPen(QColor(self._box_effect_title_color(mode)))
        title_font = self._box_effect_preview_font("subtle", max(18, int(rect.height() * 0.12)))
        title_font.setPointSize(max(18, int(rect.height() * 0.12)))
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(rect.adjusted(0, int(rect.height() * title_top), 0, 0), Qt.AlignmentFlag.AlignHCenter, "Title")

        painter.setPen(QColor(self._box_effect_small_title_color(mode)))
        small_title_font = self._box_effect_preview_font("small_title", max(12, int(rect.height() * 0.065)))
        small_title_font.setPointSize(max(12, int(rect.height() * 0.065)))
        small_title_font.setBold(True)
        painter.setFont(small_title_font)
        painter.drawText(rect.adjusted(0, int(rect.height() * small_title_top), 0, 0), Qt.AlignmentFlag.AlignHCenter, "Small titles")

        painter.setPen(QColor(self._box_effect_text_color(mode)))
        body_font = self._box_effect_preview_font("main", max(15, int(rect.height() * 0.09)))
        body_font.setPointSize(max(15, int(rect.height() * 0.09)))
        painter.setFont(body_font)
        painter.drawText(rect.adjusted(0, int(rect.height() * body_top), 0, 0), Qt.AlignmentFlag.AlignHCenter, "Information")

        icon_count = 5
        star_icon_path = self._box_effect_preview_icon_path("retention_star")
        icon_size = max(14, min(24, int(rect.height() * 0.105)))
        gap = max(8, int(icon_size * 0.58))
        total_width = icon_size * icon_count + gap * (icon_count - 1)
        start_x = rect.x() + (rect.width() - total_width) / 2
        icon_y = rect.y() + rect.height() * 0.68
        if not hide_stars:
            for index in range(icon_count):
                icon_rect = QRectF(start_x + index * (icon_size + gap), icon_y, icon_size, icon_size)
                icon_color = self._box_effect_star_color(mode, filled=index < 3)
                self._draw_box_effect_preview_icon(painter, icon_rect, star_icon_path, icon_color)
        painter.restore()

    def _render_box_effect_background_for_mode(self, mode, width, height):
        background = QPixmap(width, height)
        background.fill(Qt.GlobalColor.transparent)
        painter = QPainter(background)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self._draw_box_effect_background_layer(painter, QRectF(0, 0, width, height), mode)
        painter.end()
        return background

    def _render_box_effect_preview_pixmap(self):
        size = self.box_effect_preview.size()
        width = max(1, size.width())
        height = max(1, size.height())
        radius = 22
        dpr = max(1.0, self.box_effect_preview.devicePixelRatioF())
        target = QPixmap(int(width * dpr), int(height * dpr))
        target.setDevicePixelRatio(dpr)
        target.fill(Qt.GlobalColor.transparent)

        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        preview_rect = QRectF(1, 1, width - 2, height - 2)
        path = QPainterPath()
        path.addRoundedRect(preview_rect, radius, radius)
        painter.setClipPath(path)

        background = QPixmap(width, height)
        background.fill(Qt.GlobalColor.transparent)
        bg_painter = QPainter(background)
        bg_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bg_painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        mode = self._box_effect_preview_mode()
        self._draw_box_effect_background_layer(bg_painter, QRectF(0, 0, width, height), mode)
        bg_painter.end()

        painter.drawPixmap(0, 0, background)

        box_size = min(height * 0.78, width * 0.46, 380)
        y = (height - box_size) / 2
        box_rect = QRectF((width - box_size) / 2, y, box_size, box_size)
        self._draw_box_effect_sample(painter, box_rect, mode, background)

        painter.setClipping(False)
        border_color = QColor("#4b5563" if theme_manager.night_mode else "#d1d5db")
        pen = QPen(border_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.end()
        return target

    def _update_box_effect_preview(self):
        if not hasattr(self, "box_effect_preview"):
            return
        self.box_effect_preview.setStyleSheet("QLabel#mainBackgroundPreview { background: transparent; border: none; }")
        self.box_effect_preview.setPixmap(self._render_box_effect_preview_pixmap())
        self.box_effect_preview.setText("")

    def _save_box_effect_settings(self):
        if not hasattr(self, "box_effect_dynamic_toggle"):
            return
        self._sync_box_effect_color_config()
        dynamic = self.box_effect_dynamic_toggle.isChecked()
        mw.col.conf["onigiri_canvas_inset_color_theme_mode"] = "separate" if dynamic else "single"
        blur = self.box_effect_blur_slider.value()
        opacity = self.box_effect_opacity_slider.value()
        radius = self.box_effect_radius_slider.value()
        stroke = self.box_effect_stroke_slider.value()
        mw.col.conf["onigiri_canvas_inset_effect_blur"] = blur
        mw.col.conf["onigiri_canvas_inset_effect_opacity"] = opacity
        mw.col.conf["onigiri_canvas_inset_border_radius"] = radius
        mw.col.conf["onigiri_canvas_inset_border_width"] = stroke
        if opacity < 100:
            mw.col.conf["onigiri_canvas_inset_effect_mode"] = "opacity"
            mw.col.conf["onigiri_canvas_inset_effect_intensity"] = opacity
        else:
            mw.col.conf["onigiri_canvas_inset_effect_mode"] = "none"
            mw.col.conf["onigiri_canvas_inset_effect_intensity"] = 50

    def _create_mode_option_card(self, title, summary, toggle_widget, items, icon_filename):
        palette = self._settings_palette()
        card_bg = palette.get("--canvas-inset", "#242424" if theme_manager.night_mode else "#ffffff")
        item_bg = palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        text_col = palette.get("--fg", "#f9fafb" if theme_manager.night_mode else "#111827")
        muted_col = palette.get("--fg-subtle", "#d1d5db" if theme_manager.night_mode else "#4b5563")
        border_col = palette.get("--border", "#454545" if theme_manager.night_mode else "#e5e7eb")
        accent = self.accent_color

        card = QFrame()
        card.setObjectName("modeOptionCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        card.setMinimumHeight(92)
        card.setStyleSheet(f"""
            QFrame#modeOptionCard {{
                background-color: {card_bg};
                border: 1px solid {border_col};
                border-radius: 16px;
            }}
            QFrame#modeFeaturePill {{
                background-color: {item_bg};
                border: 1px solid {border_col};
                border-radius: 11px;
            }}
            QLabel#modeIconBadge {{
                background-color: {accent};
                border-radius: 22px;
            }}
        """)

        layout = QGridLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(8)
        layout.setColumnStretch(1, 1)

        badge = QLabel()
        badge.setObjectName("modeIconBadge")
        badge.setFixedSize(44, 44)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_pixmap = self._themed_icon(icon_filename, "#ffffff", 23).pixmap(23, 23)
        if not icon_pixmap.isNull():
            badge.setPixmap(icon_pixmap)
        layout.addWidget(badge, 0, 0, 1, 1, Qt.AlignmentFlag.AlignTop)

        text_stack_widget = QWidget()
        text_stack_widget.setStyleSheet("background: transparent;")
        text_stack = QVBoxLayout(text_stack_widget)
        text_stack.setContentsMargins(0, 0, 0, 0)
        text_stack.setSpacing(2)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: 16px; font-weight: 500; color: {text_col}; background: transparent;")
        text_stack.addWidget(title_label)

        summary_label = QLabel(summary)
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet(f"font-size: 12px; color: {muted_col}; background: transparent; line-height: 130%;")
        text_stack.addWidget(summary_label)
        layout.addWidget(text_stack_widget, 0, 1, 1, 1, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(toggle_widget, 0, 2, 1, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        features = QWidget()
        features.setStyleSheet("background: transparent;")
        features_layout = QVBoxLayout(features)
        features_layout.setContentsMargins(0, 0, 0, 0)
        features_layout.setSpacing(6)

        for item in items:
            pill = QFrame()
            pill.setObjectName("modeFeaturePill")
            pill_layout = QHBoxLayout(pill)
            pill_layout.setContentsMargins(10, 6, 10, 6)
            label = QLabel(item)
            label.setWordWrap(True)
            label.setStyleSheet(f"font-size: 11px; color: {text_col}; background: transparent;")
            pill_layout.addWidget(label)
            features_layout.addWidget(pill)

        layout.addWidget(features, 1, 1, 1, 2)
        return card



# --- MERGED FROM _infra_2.py ---

class InfraMixin2:
    def _create_deck_icon_designer_group(self):
        designer = QFrame()
        designer.setObjectName("mainBackgroundDesigner")
        outer = QVBoxLayout(designer)
        outer.setContentsMargins(0, 8, 0, 8)
        outer.setSpacing(14)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        title_label = QLabel(tr("deck_icons"))
        title_label.setObjectName("sectionTitle")
        title_label.setWordWrap(True)
        header_layout.addWidget(title_label)



        header_layout.addStretch()

        self.deck_icon_preview_mode = "dark" if theme_manager.night_mode else "light"
        self.deck_icon_preview_mode_widget, self.deck_icon_preview_mode_toggle = self._create_light_dark_mode_toggle(
            self.deck_icon_preview_mode,
            self._on_deck_icon_preview_mode_toggled,
        )
        header_layout.addWidget(self.deck_icon_preview_mode_widget)

        self.deck_reset_button = QPushButton(tr("reset_to_default_tooltip"))
        self.deck_reset_button.setObjectName("mainBackgroundResetButton")
        self.deck_reset_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.deck_reset_button.clicked.connect(self.reset_deck_to_default)
        header_layout.addWidget(self.deck_reset_button)

        outer.addLayout(header_layout)

        self.deck_icon_preview = BackgroundPreviewLabel(aspect_ratio=3.4, minimum_preview_height=210)
        self.deck_icon_preview.setObjectName("mainBackgroundPreview")
        self.deck_icon_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.deck_icon_preview.setProperty("deck_icon_preview", True)
        self.deck_icon_preview.installEventFilter(self)
        outer.addWidget(self.deck_icon_preview)

        self.indentation_mode_group = QButtonGroup(self)
        self.indentation_mode_group.setExclusive(True)
        indentation_mode_container = self._create_organize_segmented_control(
            [
                ("default", tr("default")),
                ("smaller", tr("smaller")),
                ("bigger", tr("bigger")),
                ("custom", tr("custom")),
            ],
            self.indentation_mode_group,
            self.current_config.get("deck_indentation_mode", "default"),
            "indent_mode",
            fill_width=True,
            segment_height=28,
            min_button_width=72,
        )
        outer.addWidget(self._create_main_bg_value_row(tr("decks_indentation"), indentation_mode_container))

        self.indentation_custom_spin = QSpinBox()
        self.indentation_custom_spin.setRange(0, 100)
        self.indentation_custom_spin.setValue(self.current_config.get("deck_indentation_custom_px", 20))
        self.indentation_custom_spin.setSuffix(" px")
        self.indentation_custom_spin.setFixedHeight(32)
        self.indentation_custom_spin.setMinimumWidth(120)
        self.indentation_custom_spin.valueChanged.connect(self._update_deck_icon_preview)
        self.indentation_custom_row_widget = self._create_main_bg_value_row(
            tr("custom_indentation_px"),
            self.indentation_custom_spin,
        )
        outer.addWidget(self.indentation_custom_row_widget)
        self.indentation_mode_group.buttonClicked.connect(self._on_indentation_mode_btn_clicked)
        self._on_indentation_mode_btn_clicked(self.indentation_mode_group.checkedButton())

        icons_label = QLabel(tr("deck_icon_assignment_label", "Click an icon below to change it"))
        icons_label.setObjectName("sectionDescription")
        icons_label.setWordWrap(True)
        outer.addWidget(icons_label)

        deck_icons_layout = QHBoxLayout()
        deck_icons_layout.setContentsMargins(0, 0, 0, 0)
        deck_icons_layout.setSpacing(10)
        deck_icons_to_configure = {"folder": tr("folder_icon"), "deck": tr("deck_icon"), "subdeck": tr("subdeck_icon"), "filtered_deck": tr("filtered_deck_icon"), "options": tr("options_icon"), "collapse_closed": tr("collapse_icon"), "collapse_open": tr("expand_icon")}
        for index, (key, label_text) in enumerate(deck_icons_to_configure.items()):
            control_widget = self._create_icon_control_widget(key, display_name=label_text, compact=True)
            self.icon_assignment_widgets.append(control_widget)
            deck_icons_layout.addWidget(control_widget, 1)
        outer.addLayout(deck_icons_layout)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        outer.addWidget(divider)

        bottom_h_layout = QHBoxLayout()
        bottom_h_layout.setSpacing(12)
        bottom_h_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Use the same inner-group wrapper as the palettes so the "Deck Icon
        # Settings" title lines up with the palette titles.
        settings_group, sizing_layout = self._create_inner_group(tr("deck_icon_settings"))
        sizing_layout.setSpacing(8)

        palette = self._settings_palette()
        border_color = palette.get("--border", "#dcdde1")
        hover_bg = palette.get("--hover-bg", "#e9e9e9")
        fg_color = palette.get("--fg", "#202124")

        def create_setting_row(label_text, widget):
            row = QFrame()
            row.setObjectName("settingRow")
            row.setFixedHeight(48)
            row.setStyleSheet(f"""
                QFrame#settingRow {{
                    background-color: transparent;
                    border: 1px solid {border_color};
                    border-radius: 12px;
                }}
                QFrame#settingRow:hover {{
                    background-color: {hover_bg};
                }}
            """)
            h_layout = QHBoxLayout(row)
            h_layout.setContentsMargins(15, 0, 15, 0)
            
            label = QLabel(label_text)
            label.setStyleSheet(f"font-weight: bold; border: none; background: transparent; color: {fg_color};")
            h_layout.addWidget(label)
            
            h_layout.addStretch()
            h_layout.addWidget(widget)
            return row

        light_deck_colors_group, light_deck_colors_layout = self._create_inner_group(f"{tr('light_mode')} {tr('palette')}")
        light_deck_colors_layout.setSpacing(5)
        self._populate_pills_for_keys(light_deck_colors_layout, "light", ["--deck-list-bg", "--highlight-bg", "--highlight-fg", "--icon-color", "--icon-color-filtered"])
        self._populate_overview_count_pills(light_deck_colors_layout, "light")

        dark_deck_colors_group, dark_deck_colors_layout = self._create_inner_group(f"{tr('dark_mode')} {tr('palette')}")
        dark_deck_colors_layout.setSpacing(5)
        self._populate_pills_for_keys(dark_deck_colors_layout, "dark", ["--deck-list-bg", "--highlight-bg", "--highlight-fg", "--icon-color", "--icon-color-filtered"])
        self._populate_overview_count_pills(dark_deck_colors_layout, "dark")

        self.deck_icon_palette_stack = QStackedWidget()
        self.deck_icon_palette_stack.addWidget(light_deck_colors_group)
        self.deck_icon_palette_stack.addWidget(dark_deck_colors_group)
        self.deck_icon_palette_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        # Lay the settings and active palette columns side by side, each hugging the top so their
        # section titles align on the same baseline regardless of column height.
        for column_group in (settings_group, self.deck_icon_palette_stack):
            column_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
            column_wrapper = QVBoxLayout()
            column_wrapper.setContentsMargins(0, 0, 0, 0)
            column_wrapper.addWidget(column_group)
            column_wrapper.addStretch()
            bottom_h_layout.addLayout(column_wrapper, 1)

        outer.addLayout(bottom_h_layout)
        self._update_deck_icon_palette_controls()

        # --- Add Hide Icon Toggles ---
        # Note: Using mw.col.conf.get directly to ensure we load the saved state correctly
        self.hide_folder_cb = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_folder_cb.setChecked(mw.col.conf.get("modern_menu_hide_folder_icon", False))
        self.hide_folder_cb.toggled.connect(self._update_deck_icon_state)
        sizing_layout.addWidget(create_setting_row(tr("hide_folder_icon"), self.hide_folder_cb))

        self.hide_subdeck_cb = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_subdeck_cb.setChecked(mw.col.conf.get("modern_menu_hide_subdeck_icon", False))
        self.hide_subdeck_cb.toggled.connect(self._update_deck_icon_state)
        sizing_layout.addWidget(create_setting_row(tr("hide_subdeck_icon"), self.hide_subdeck_cb))

        self.hide_deck_cb = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_deck_cb.setChecked(mw.col.conf.get("modern_menu_hide_deck_icon", False))
        self.hide_deck_cb.toggled.connect(self._update_deck_icon_state)
        sizing_layout.addWidget(create_setting_row(tr("hide_deck_icon"), self.hide_deck_cb))

        self.hide_filtered_deck_cb = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_filtered_deck_cb.setChecked(mw.col.conf.get("modern_menu_hide_filtered_deck_icon", False))
        self.hide_filtered_deck_cb.toggled.connect(self._update_deck_icon_state)
        sizing_layout.addWidget(create_setting_row(tr("hide_filtered_deck_icon"), self.hide_filtered_deck_cb))

        # Hide default, show custom setting
        self.hide_default_custom_cb = AnimatedToggleButton(accent_color=self.accent_color)
        self.hide_default_custom_cb.setChecked(mw.col.conf.get("modern_menu_hide_default_icons", False))
        self.hide_default_custom_cb.toggled.connect(self._update_deck_icon_state)
        self.hide_default_custom_cb.setToolTip("If enabled, default icons will be hidden, but custom deck icons will still be shown.")
        sizing_layout.addWidget(create_setting_row(tr("hide_default_show_custom"), self.hide_default_custom_cb))

        self.hide_deck_counts_checkbox.toggled.connect(self._update_deck_icon_preview)
        sizing_layout.addWidget(create_setting_row(tr("hide_zero_counts"), self.hide_deck_counts_checkbox))

        self.hide_all_deck_counts_checkbox.toggled.connect(self._update_deck_icon_preview)
        sizing_layout.addWidget(create_setting_row(tr("hide_all_counts"), self.hide_all_deck_counts_checkbox))

        icon_sizes_to_configure = {"deck_folder": tr("deck_folder_icons_label"), "action_button": tr("action_button_icons"), "collapse": tr("expand_collapse_icons_label"), "options_gear": tr("deck_options_gear_label")}
        for key, label in icon_sizes_to_configure.items():
            size_spinbox = self.create_icon_size_spinbox(key, DEFAULT_ICON_SIZES[key])
            if key in ("deck_folder", "collapse"):
                size_spinbox.valueChanged.connect(self._update_deck_icon_preview)
            sizing_layout.addWidget(create_setting_row(label, size_spinbox))

        return designer

    def _on_deck_icon_preview_mode_toggled(self, mode):
        self.deck_icon_preview_mode = "dark" if mode == "dark" else "light"
        self._update_deck_icon_palette_controls()
        self._update_deck_icon_preview()

    def _deck_icon_preview_mode(self):
        return getattr(self, "deck_icon_preview_mode", "dark" if theme_manager.night_mode else "light")

    def _update_deck_icon_palette_controls(self):
        if not hasattr(self, "deck_icon_palette_stack"):
            return
        self.deck_icon_palette_stack.setCurrentIndex(1 if self._deck_icon_preview_mode() == "dark" else 0)

    def _deck_icon_preview_icon_value(self, key):
        widget = next((w for w in getattr(self, "icon_assignment_widgets", []) if w.property("icon_key") == key), None)
        filename = widget.property("icon_filename") if widget else mw.col.conf.get(f"modern_menu_icon_{key}", "")
        if filename:
            return filename
        return f"system:{ICON_DEFAULTS.get(key, f'{key}.svg')}"

    def _deck_icon_preview_visible(self, key):
        hide_widget = {
            "folder": getattr(self, "hide_folder_cb", None),
            "subdeck": getattr(self, "hide_subdeck_cb", None),
            "deck": getattr(self, "hide_deck_cb", None),
            "filtered_deck": getattr(self, "hide_filtered_deck_cb", None),
        }.get(key)
        if hide_widget and hide_widget.isChecked():
            return False
        hide_default_widget = getattr(self, "hide_default_custom_cb", None)
        if key in ("folder", "subdeck", "deck", "filtered_deck") and hide_default_widget and hide_default_widget.isChecked():
            widget = next((w for w in getattr(self, "icon_assignment_widgets", []) if w.property("icon_key") == key), None)
            filename = widget.property("icon_filename") if widget else ""
            if not filename:
                return False
        return True

    def _deck_icon_preview_size(self, key):
        widget = getattr(self, "icon_size_widgets", {}).get(key)
        if widget:
            return widget.value()
        return DEFAULT_ICON_SIZES.get(key, 16)

    def _deck_icon_preview_indent_px(self):
        mode = "default"
        if hasattr(self, "indentation_mode_group"):
            checked = self.indentation_mode_group.checkedButton()
            if checked:
                mode = checked.property("indent_mode") or "default"
        if mode == "smaller":
            return 10
        if mode == "bigger":
            return 40
        if mode == "custom":
            return int(self.indentation_custom_spin.value()) if hasattr(self, "indentation_custom_spin") else 20
        return 20

    def _deck_icon_count_bubble_specs(self, mode):
        return [
            (
                self._overview_count_color_value("new_bubble", "--new-count-bubble-bg", mode),
                self._overview_count_color_value("new_text", "--new-count-bubble-fg", mode),
            ),
            (
                self._overview_count_color_value("learn_bubble", "--learn-count-bubble-bg", mode),
                self._overview_count_color_value("learn_text", "--learn-count-bubble-fg", mode),
            ),
            (
                self._overview_count_color_value("review_bubble", "--review-count-bubble-bg", mode),
                self._overview_count_color_value("review_text", "--review-count-bubble-fg", mode),
            ),
        ]

    def _draw_deck_icon_preview_counts(self, painter, row_rect, mode, counts, right_pad):
        # Pill-shaped count bubbles, mirroring tr.deck .new-count-bubble in menu.css:
        # fixed small height + border-radius >= half height keeps them a true pill
        # regardless of the user's main font size.
        if getattr(self, "hide_all_deck_counts_checkbox", None) and self.hide_all_deck_counts_checkbox.isChecked():
            return row_rect.right() - right_pad
        hide_zero = bool(getattr(self, "hide_deck_counts_checkbox", None) and self.hide_deck_counts_checkbox.isChecked())

        specs = self._deck_icon_count_bubble_specs(mode)
        bubble_height = max(11, min(18, row_rect.height() * 0.5))
        gap = 4

        font = QFont(self.font())
        font.setPointSize(max(6, int(bubble_height * 0.46)))
        font.setBold(True)
        metrics = QFontMetrics(font)

        x = row_rect.right() - right_pad
        for (bg, fg), count in zip(reversed(specs), reversed(counts)):
            if count == 0 and hide_zero:
                continue
            text = str(count)
            text_width = metrics.horizontalAdvance(text)
            bubble_width = max(bubble_height, text_width + 10)
            bubble_rect = QRectF(x - bubble_width, row_rect.y() + (row_rect.height() - bubble_height) / 2, bubble_width, bubble_height)
            bubble_path = QPainterPath()
            bubble_path.addRoundedRect(bubble_rect, bubble_height / 2, bubble_height / 2)
            color = QColor(bg)
            if count == 0:
                color.setAlphaF(0.6)
            painter.fillPath(bubble_path, QBrush(color))
            painter.setFont(font)
            painter.setPen(QColor(fg))
            painter.drawText(bubble_rect, Qt.AlignmentFlag.AlignCenter, text)
            x -= bubble_width + gap

        return x + gap

    def _draw_deck_icon_preview_rows(self, painter, rect, mode):
        # _draw_box_effect_preview_icon -> _render_icon_value_pixmap does a plain
        # str.replace("currentColor", color); passing a QColor there raises
        # (silently swallowed) instead of tinting the icon, so keep these as hex strings.
        icon_color = self._deck_icon_color(mode)
        filtered_color = self._deck_icon_filtered_color(mode)
        text_color = QColor(self._deck_icon_text_color(mode))
        highlight_color = QColor(self._deck_icon_highlight_color(mode))

        icon_size = max(10, min(40, self._deck_icon_preview_size("deck_folder")))
        chevron_size = max(8, min(28, self._deck_icon_preview_size("collapse")))
        indent_px = self._deck_icon_preview_indent_px()

        rows = [
            {"key": "folder", "chevron": "collapse_open", "indent": 0,
             "label": tr("deck_icon_preview_folder", "Folder"), "counts": (15, 12, 18)},
            {"key": "subdeck", "chevron": None, "indent": indent_px,
             "label": tr("deck_icon_preview_subdeck", "Subdeck"), "counts": (13, 11, 14)},
            {"key": "subdeck", "chevron": None, "indent": indent_px,
             "label": tr("deck_icon_preview_subdeck", "Subdeck"), "counts": (0, 0, 12)},
            {"key": "deck", "chevron": None, "indent": 0,
             "label": tr("deck_icon_preview_deck", "Deck"), "highlight": True, "counts": (10, 0, 15)},
            {"key": "filtered_deck", "chevron": None, "indent": 0,
             "label": tr("deck_icon_preview_filtered", "Filtered Deck"), "counts": (17, 0, 0)},
            {"key": "folder", "chevron": "collapse_closed", "indent": 0,
             "label": tr("deck_icon_preview_folder", "Folder"), "counts": (12, 13, 20)},
        ]

        row_height = rect.height() / len(rows)
        chevron_col_width = chevron_size + 10
        left_pad = 14

        label_font = QFont(self.font())
        label_font.setPointSize(max(9, int(row_height * 0.30)))

        for index, row in enumerate(rows):
            row_rect = QRectF(rect.x(), rect.y() + index * row_height, rect.width(), row_height)

            if row.get("highlight"):
                highlight_rect = row_rect.adjusted(6, 2, -6, -2)
                highlight_path = QPainterPath()
                highlight_path.addRoundedRect(highlight_rect, 8, 8)
                painter.fillPath(highlight_path, QBrush(highlight_color))

            x = row_rect.x() + left_pad + row["indent"]

            chevron_rect = QRectF(x, row_rect.y() + (row_rect.height() - chevron_size) / 2, chevron_size, chevron_size)
            if row["chevron"]:
                chevron_icon = self._deck_icon_preview_icon_value(row["chevron"])
                self._draw_box_effect_preview_icon(painter, chevron_rect, chevron_icon, icon_color)
            x += chevron_col_width

            icon_rect = QRectF(x, row_rect.y() + (row_rect.height() - icon_size) / 2, icon_size, icon_size)
            if self._deck_icon_preview_visible(row["key"]):
                icon_value = self._deck_icon_preview_icon_value(row["key"])
                tint = filtered_color if row["key"] == "filtered_deck" else icon_color
                self._draw_box_effect_preview_icon(painter, icon_rect, icon_value, tint)
            x += icon_size + 8

            counts_left_edge = self._draw_deck_icon_preview_counts(painter, row_rect, mode, row.get("counts", (0, 0, 0)), left_pad)

            painter.setFont(label_font)
            painter.setPen(text_color)
            text_rect = QRectF(x, row_rect.y(), max(0.0, counts_left_edge - x - 8), row_rect.height())
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, row["label"])

    def _render_deck_icon_preview_pixmap(self):
        size = self.deck_icon_preview.size()
        width = max(1, size.width())
        height = max(1, size.height())
        radius = 22
        dpr = max(1.0, self.deck_icon_preview.devicePixelRatioF())
        target = QPixmap(int(width * dpr), int(height * dpr))
        target.setDevicePixelRatio(dpr)
        target.fill(Qt.GlobalColor.transparent)

        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        preview_rect = QRectF(1, 1, width - 2, height - 2)
        path = QPainterPath()
        path.addRoundedRect(preview_rect, radius, radius)
        painter.setClipPath(path)

        mode = self._deck_icon_preview_mode()
        self._draw_deck_icon_sidebar_background_layer(painter, QRectF(0, 0, width, height), mode)

        content_rect = preview_rect.adjusted(0, 6, 0, -6)
        self._draw_deck_icon_preview_rows(painter, content_rect, mode)

        painter.setClipping(False)
        border_color = QColor("#4b5563" if theme_manager.night_mode else "#d1d5db")
        pen = QPen(border_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.end()
        return target

    def _update_deck_icon_preview(self):
        if not hasattr(self, "deck_icon_preview"):
            return
        self.deck_icon_preview.setStyleSheet("QLabel#mainBackgroundPreview { background: transparent; border: none; }")
        self.deck_icon_preview.setPixmap(self._render_deck_icon_preview_pixmap())

    def _confirm_delete_dialog(self, window_title, title_text, message_text):
        palette = self._settings_palette()
        panel = palette.get("--canvas-inset", "#242424" if theme_manager.night_mode else "#ffffff")
        highlight = palette.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")
        border = palette.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")
        fg = palette.get("--fg", "#f4f4f5" if theme_manager.night_mode else "#111827")
        muted = palette.get("--fg-subtle", "#d1d5db" if theme_manager.night_mode else "#4b5563")
        accent = palette.get("--accent-color", self.accent_color)

        dialog = QDialog(self)
        dialog.setWindowTitle(window_title)
        dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        dialog.setModal(True)
        dialog.setStyleSheet(f"""
            QDialog {{
                background: transparent;
            }}
            QFrame#galleryDeletePanel {{
                background-color: {panel};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            QLabel {{
                color: {fg};
                background: transparent;
            }}
            QLabel#galleryDeleteHint {{
                color: {muted};
                font-size: 12px;
            }}
            QPushButton {{
                background-color: {panel};
                color: {fg};
                border: 1px solid {border};
                border-radius: 16px;
                min-height: 32px;
                padding: 0px 18px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {highlight};
            }}
            QPushButton#galleryDeleteConfirm {{
                background-color: {accent};
                color: #ffffff;
                border-color: {accent};
            }}
        """)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        panel_frame = QFrame()
        panel_frame.setObjectName("galleryDeletePanel")
        panel_layout = QVBoxLayout(panel_frame)
        panel_layout.setContentsMargins(24, 22, 24, 20)
        panel_layout.setSpacing(14)
        panel_frame.setMinimumWidth(420)
        layout.addWidget(panel_frame)

        title = QLabel(title_text)
        title.setStyleSheet("font-size: 18px; font-weight: 800;")
        message = QLabel(message_text)
        message.setObjectName("galleryDeleteHint")
        message.setWordWrap(True)
        panel_layout.addWidget(title)
        panel_layout.addWidget(message)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 8, 0, 0)
        buttons.setSpacing(10)
        buttons.addStretch()
        cancel_button = QPushButton("Cancel")
        delete_button = QPushButton("Delete")
        delete_button.setObjectName("galleryDeleteConfirm")
        cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_button.clicked.connect(dialog.reject)
        delete_button.clicked.connect(dialog.accept)
        buttons.addWidget(cancel_button)
        buttons.addWidget(delete_button)
        panel_layout.addLayout(buttons)

        return dialog.exec() == QDialog.DialogCode.Accepted

    def _toggle_canvas_intensity_spinbox(self):
        if not hasattr(self, "canvas_effect_none_radio"):
            return
        is_disabled = self.canvas_effect_none_radio.isChecked()
        self.canvas_effect_intensity_spinbox.setEnabled(not is_disabled)

    def _populate_pills_for_keys(self, layout, mode, keys):
        local_defaults = {
            "--star-color": "#FFD700",
            "--empty-star-color": "#e0e0e0" if mode == 'light' else '#4a4a4a'
        }

        colors = self.current_config.get("colors", {}).get(mode, {})
        
        for name in keys:
            if name not in COLOR_LABELS:
                continue

            label_info = COLOR_LABELS[name]
            default_value = DEFAULTS["colors"][mode].get(name, local_defaults.get(name))
            
            if default_value is not None:
                value = colors.get(name, default_value)
                pill_widget = self._create_color_pill(name, value, mode, label_info)
                layout.addWidget(pill_widget)

    def _create_slideshow_images_selector(self, image_files_cache):
        """Creates a gallery widget for selecting multiple images for slideshow mode."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)
        
        # Instructions label
        instructions = QLabel(tr("slideshow_instructions"))
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Scroll area for image gallery
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(400)
        
        scroll_content = QWidget()
        scroll_layout = QGridLayout(scroll_content)
        scroll_layout.setSpacing(10)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        
        # Get saved slideshow images
        saved_images = mw.col.conf.get("modern_menu_slideshow_images", [])
        
        # Get the user files path - CORRECTED PATH
        addon_path = ADDON_ROOT
        user_bg_folder = os.path.join(addon_path, "user_files", "main_bg")
        
        # Create gallery items for each image
        self.slideshow_image_items = []
        row, col = 0, 0
        max_cols = 4  # 4 images per row
        
        for img_file in image_files_cache:
            # Create container for image + checkbox
            item_widget = QWidget()
            item_widget.setObjectName("galleryItem")
            item_widget.setFixedSize(120, 90)
            item_widget.setCursor(Qt.CursorShape.PointingHandCursor)
            
            # Store the filename and checked state
            item_widget.img_filename = img_file
            item_widget.is_checked = img_file in saved_images
            
            # Create the image label
            img_path = os.path.join(user_bg_folder, img_file)
            img_label = QLabel(item_widget)
            img_label.setFixedSize(120, 90)
            img_label.setScaledContents(False)
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Load and display the image with rounded corners
            if os.path.exists(img_path):
                pixmap = QPixmap(img_path)
                if not pixmap.isNull():
                    # Scale to fit while maintaining aspect ratio
                    scaled_pixmap = pixmap.scaled(
                        120, 90,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    # Crop from center
                    crop_x = (scaled_pixmap.width() - 120) / 2
                    crop_y = (scaled_pixmap.height() - 90) / 2
                    cropped_pixmap = scaled_pixmap.copy(int(crop_x), int(crop_y), 120, 90)
                    
                    # Apply rounded corners
                    rounded_pixmap = create_rounded_pixmap(cropped_pixmap, 10)
                    img_label.setPixmap(rounded_pixmap)
            
            # Create custom selection overlay using accent color
            overlay = SelectionOverlay(item_widget, accent_color=self.accent_color)
            overlay.setChecked(item_widget.is_checked)
            overlay.move(90, 5)  # Top-right corner (120 - 24 - 6 padding)
            
            # Store overlay reference
            item_widget.overlay = overlay
            
            # Apply border styling based on selection
            self._update_slideshow_item_border(item_widget)
            
            # Connect click events
            def make_click_handler(widget):
                def handler(event):
                    widget.is_checked = not widget.is_checked
                    widget.overlay.setChecked(widget.is_checked)
                    self._update_slideshow_item_border(widget)
                return handler
            
            item_widget.mousePressEvent = make_click_handler(item_widget)
            
            # Add to grid
            scroll_layout.addWidget(item_widget, row, col)
            self.slideshow_image_items.append(item_widget)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        # Add/Remove buttons
        button_layout = QHBoxLayout()
        select_all_btn = QPushButton(tr("select_all_btn"))
        select_all_btn.clicked.connect(lambda: self._toggle_all_slideshow_images(True))
        deselect_all_btn = QPushButton(tr("deselect_all_btn"))
        deselect_all_btn.clicked.connect(lambda: self._toggle_all_slideshow_images(False))
        button_layout.addWidget(select_all_btn)
        button_layout.addWidget(deselect_all_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        return widget

    def _update_slideshow_item_border(self, item_widget):
        """Update the border style of a slideshow gallery item based on selection state."""
        if item_widget.is_checked:
            item_widget.setStyleSheet(f"""
                #galleryItem {{
                    border: 3px solid {self.accent_color};
                    border-radius: 10px;
                    background: transparent;
                }}
            """)
        else:
            item_widget.setStyleSheet("""
                #galleryItem {
                    border: 2px solid transparent;
                    border-radius: 10px;
                    background: transparent;
                }
                #galleryItem:hover {
                    border: 2px solid #888888;
                }
            """)

    def _on_slideshow_checkbox_toggled(self, item_widget, checked):
        """Handle checkbox toggle for slideshow gallery items."""
        item_widget.is_checked = checked
        item_widget.overlay.setChecked(checked)
        self._update_slideshow_item_border(item_widget)

    def _toggle_all_slideshow_images(self, checked):
        """Toggle all slideshow image gallery items."""
        for item in self.slideshow_image_items:
            item.is_checked = checked
            item.overlay.setChecked(checked)
            self._update_slideshow_item_border(item)

    def _get_svg_icon(self, path: str, icon_color=None) -> Union[QIcon, None]:
        if not os.path.exists(path):
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                svg_data = f.read()

            icon_color = icon_color or ("#e0e0e0" if theme_manager.night_mode else "#212121")
            if 'currentColor' in svg_data:
                colored_svg = svg_data.replace('currentColor', icon_color)
            else:
                colored_svg = svg_data.replace('<svg', f'<svg fill="{icon_color}"', 1)

            renderer = QSvgRenderer(colored_svg.encode('utf-8'))
            pixmap = QPixmap(renderer.defaultSize())
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            return QIcon(pixmap)
        except Exception as e:
            print(f"Onigiri: Error rendering SVG icon at {path}: {e}")
            return None

    def _create_delete_icon(self) -> Union[QIcon, None]:
        """Loads and colors the xmark.svg icon for the delete button."""
        icon_path = system_icon_path("xmark.svg")
        if not os.path.exists(icon_path):
            return None

        # Use a subtle text color for the icon
        conf = config.get_config()
        if theme_manager.night_mode:
            icon_color = conf.get("colors", {}).get("dark", {}).get("--fg-subtle", "#908caa")
        else:
            icon_color = conf.get("colors", {}).get("light", {}).get("--fg-subtle", "#797593")

        try:
            with open(icon_path, 'r', encoding='utf-8') as f:
                svg_data = f.read()

            # Replace currentColor if it exists, otherwise add a fill attribute
            if 'currentColor' in svg_data:
                colored_svg = svg_data.replace('currentColor', icon_color)
            else:
                colored_svg = svg_data.replace('<svg', f'<svg fill="{icon_color}"', 1)

            renderer = QSvgRenderer(colored_svg.encode('utf-8'))
            pixmap = QPixmap(renderer.defaultSize())
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            return QIcon(pixmap)
        except Exception as e:
            print(f"Onigiri: Error rendering SVG icon at {icon_path}: {e}")
            return None

    def _on_shape_selected(self):
        sender = self.sender()
        if sender and sender.isChecked():
            self.selected_heatmap_shape = sender.property("shape_filename")
            if hasattr(self, "heatmap_preview"):
                self._update_heatmap_preview()

    def _create_shape_selector(self) -> QWidget:
        widget = QWidget()
        self.shape_selector_widget = widget
        widget.installEventFilter(self)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll_area = QScrollArea()
        self.shape_scroll_area = scroll_area
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setMinimumHeight(96)
        scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.shape_scroll_content = QWidget()
        self.shape_scroll_content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.shape_button_size = 48
        self.shape_grid_spacing = 10
        scroll_area.setWidget(self.shape_scroll_content)
        
        layout.addWidget(scroll_area)
        
        if theme_manager.night_mode:
            input_bg, border, accent_color = "#3a3a3a", "#4a4a4a", self.accent_color
        else:
            input_bg, border, accent_color = "#f5f5f5", "#e0e0e0", self.accent_color

        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
                border-radius: 18px;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: transparent;
                border-radius: 18px;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 4px 0 4px 0;
            }}
            QScrollBar::handle:vertical {{
                background: {border};
                border-radius: 4px;
                min-height: 24px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)
            
        icons_path = os.path.join(self.addon_path, "system_files", "system_icons", "available_for_users")
        self.shape_buttons = []
        
        if os.path.isdir(icons_path):
            for filename in sorted(os.listdir(icons_path)):
                if filename.lower() == "onigiri.svg":
                    continue
                if filename.lower().endswith(".svg"):
                    shape_name = os.path.splitext(filename)[0].replace("_", " ").title()

                    card = HeatmapShapeButton(input_bg, border, accent_color)
                    card.setAutoExclusive(True)
                    card.setProperty("shape_filename", filename)
                    card.setFixedSize(self.shape_button_size, self.shape_button_size)
                    card.setToolTip(shape_name)

                    icon_path = os.path.join(icons_path, filename)
                    icon = self._get_svg_icon(icon_path)
                    accent_icon = self._get_svg_icon(icon_path, accent_color)
                    if icon:
                        card.setIcon(icon)
                        card.setIconSize(QSize(28, 28))
                    if accent_icon:
                        card.setAccentIcon(accent_icon)

                    card.clicked.connect(self._on_shape_selected)
                    self.shape_buttons.append(card)

        self.heatmap_custom_shape_button = HeatmapShapeButton(input_bg, border, accent_color)
        self.heatmap_custom_shape_button.setAutoExclusive(True)
        self.heatmap_custom_shape_button.setProperty("shape_filename", self.current_config.get("heatmapShape", "system:square.svg"))
        self.heatmap_custom_shape_button.setFixedSize(self.shape_button_size, self.shape_button_size)
        self.heatmap_custom_shape_button.setToolTip(tr("select_icon", "Select Icon"))
        self.heatmap_custom_shape_button.clicked.connect(self._open_heatmap_icon_selector)
        self.shape_buttons.append(self.heatmap_custom_shape_button)

        # Populate once; resize events recalculate the responsive column count.
        self._reflow_shape_icons()
        QTimer.singleShot(0, self._reflow_shape_icons)
                    
        self.selected_heatmap_shape = self.current_config.get("heatmapShape", "square.svg")
        if self.selected_heatmap_shape == "onigiri.svg":
            self.selected_heatmap_shape = "square.svg"
        for btn in self.shape_buttons:
            if btn.property("shape_filename") == self.selected_heatmap_shape:
                btn.setChecked(True)
                break
        else:
            if self.heatmap_custom_shape_button and (
                str(self.selected_heatmap_shape).startswith("system:")
                or str(self.selected_heatmap_shape).startswith("emoji:")
                or self._icon_value_path(self.selected_heatmap_shape)
            ):
                self.heatmap_custom_shape_button.setProperty("shape_filename", self.selected_heatmap_shape)
                self.heatmap_custom_shape_button.setChecked(True)
            elif self.shape_buttons:
                self.shape_buttons[0].setChecked(True)
                self.selected_heatmap_shape = self.shape_buttons[0].property("shape_filename")
        self._refresh_heatmap_custom_shape_button()
            
        return widget

    def _create_scrollable_page(self):
        scroll = QScrollArea()
        scroll.setObjectName("settingsPageScroll")
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.viewport().setStyleSheet("background: transparent;")

        content_widget = QWidget()
        content_widget.setObjectName("settingsPageContent")
        content_widget.setAutoFillBackground(False)
        content_widget.setMinimumWidth(0)
        content_widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        scroll.setWidget(content_widget)
        
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 12, 8, 24)
        content_layout.setSpacing(14)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        page_container = QWidget()
        # We give the container a name so we can style it from the main stylesheet.
        page_container.setObjectName("pageContainer")
        page_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        page_container.setMinimumWidth(0)
        page_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        page_layout = QVBoxLayout(page_container)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)
        page_layout.addWidget(scroll)
        
        return page_container, content_layout

    def _add_navigation_buttons(self, page_container, scroll_area, sections_map, buttons_per_row=None):
        """
        Registers compact top navigation for the page currently being built.
        """
        if not sections_map:
            return

        content_widget = scroll_area.widget()
        content_layout = content_widget.layout() if content_widget else None
        if content_layout:
            self._remove_trailing_layout_stretches(content_layout)

        page_name = self._building_page_name
        if page_name:
            self._page_nav_sections[page_name] = list(sections_map.items())

    def _remove_trailing_layout_stretches(self, layout):
        while layout.count():
            item = layout.itemAt(layout.count() - 1)
            if item and item.spacerItem() is not None:
                layout.takeAt(layout.count() - 1)
                continue
            break

    def _scroll_to_widget(self, scroll_area, widget):
        # Get the y coordinate of the widget relative to the scroll area's content widget
        content_widget = scroll_area.widget()
        if content_widget:
            target_y = widget.mapTo(content_widget, QPoint(0, 0)).y()
            scroll_area.verticalScrollBar().setValue(target_y)

    def _on_thumbnail_ready(self, key, index, image, filename):
        gallery = self.galleries.get(key)
        if not gallery or index >= len(gallery['labels']): return
        
        label = gallery['labels'][index]
        pixmap = QPixmap.fromImage(image)
        label.setPixmap(pixmap)
        label.setToolTip(filename)
        label.setProperty("image_filename", filename)
        
        # Clear placeholder style
        label.setStyleSheet("background: transparent;")

        if 'overlays' not in gallery and gallery['selected'] == filename:
            label.setStyleSheet(THUMBNAIL_STYLE_SELECTED)

    def eventFilter(self, source, event):
        # Guard against callbacks on C++ objects that are mid-destruction.
        # Calling .property() on a being-destroyed widget can return a QVariant
        # wrapping a partially-freed Qt object (e.g. QSvgRenderer), and PyQt6/SIP
        # will crash with a pointer authentication failure (SIGSEGV) trying to
        # convert it back to Python.  sip.isdeleted() is the safe check.
        try:
            if sip is not None and sip.isdeleted(source):
                return False
        except Exception:
            return False
        if event.type() == QEvent.Type.DeferredDelete:
            return False
        # QWidget::~QWidget() sends Hide/Destroy/ParentChange synchronously
        # *before* sip marks the object deleted, so the isdeleted() check above
        # cannot catch this case. None of this filter's logic needs to react to
        # teardown events, so skip straight past every .property() call below.
        # Looked up by name (not all of these exist on every PyQt6 build).
        if event.type() in TEARDOWN_EVENT_TYPES:
            return False

        if hasattr(self, 'main_bg_preview') and source is self.main_bg_preview:
            if event.type() == QEvent.Type.Resize:
                QTimer.singleShot(0, self._update_main_background_preview)
                return False
            if event.type() in {
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseMove,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.Enter,
                QEvent.Type.Leave,
            }:
                return self._handle_main_background_preview_mouse_event(event)

        try:
            modern_bg_prefix = source.property("modern_bg_prefix") if hasattr(source, "property") else None
        except Exception:
            modern_bg_prefix = None
        if modern_bg_prefix and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, lambda p=modern_bg_prefix: self._update_modern_background_preview(p))
            return False

        try:
            is_action_preview = bool(source.property("action_buttons_preview")) if hasattr(source, "property") else False
        except Exception:
            is_action_preview = False
        if is_action_preview and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self._update_action_buttons_preview)
            return False

        if hasattr(self, 'sidebar_bg_preview') and source is self.sidebar_bg_preview and event.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self._update_sidebar_background_preview)
            return False

        if hasattr(self, 'bottom_bar_preview') and source is self.bottom_bar_preview:
            if event.type() == QEvent.Type.Resize:
                QTimer.singleShot(0, self._update_reviewer_bottom_bar_preview)
                return False
            if event.type() in {
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseMove,
                QEvent.Type.MouseButtonRelease,
                QEvent.Type.Enter,
                QEvent.Type.Leave,
            }:
                return self._handle_bottom_bar_preview_mouse_event(event)

        try:
            if source.property("profile_asset_preview") and event.type() == QEvent.Type.Resize:
                QTimer.singleShot(0, self._update_profile_asset_preview)
                return False

            if source.property("overview_surface_lock_container") or source.property("overview_surface_lock_content"):
                if event.type() in {QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.LayoutRequest}:
                    QTimer.singleShot(0, self._update_overview_style_surface_lock_overlay)
                    return False

            if source.property("gallery_import_key") and event.type() == QEvent.Type.Resize:
                key = source.property("gallery_import_key")
                new_size = event.size()
                if source.property("last_preview_size") != new_size:
                    source.setProperty("last_preview_size", new_size)
                    QTimer.singleShot(0, lambda k=key: self._update_gallery_background_preview(k))
                return False
        except Exception:
            pass

        if (
            hasattr(self, 'shape_selector_widget')
            and source is self.shape_selector_widget
            and event.type() == QEvent.Type.Resize
        ):
            try:
                QTimer.singleShot(0, lambda w=event.size().width(): self._reflow_shape_icons(w))
            except Exception as e:
                print(f"Warning: Shape reflow error: {e}")
            return False

        try:
            if source.property("box_effect_preview") and event.type() == QEvent.Type.Resize:
                QTimer.singleShot(0, self._update_box_effect_preview)
                return False

            if source.property("deck_icon_preview") and event.type() == QEvent.Type.Resize:
                QTimer.singleShot(0, self._update_deck_icon_preview)
                return False

            if source.property("heatmap_preview") and event.type() == QEvent.Type.Resize:
                QTimer.singleShot(0, self._update_heatmap_preview)
                return False

            if source.property("overview_style_preview") and event.type() == QEvent.Type.Resize:
                QTimer.singleShot(0, self._update_overview_style_preview)
                return False
        except Exception:
            pass

        if event.type() == QEvent.Type.MouseButtonPress:
            try:
                if source.property("gallery_import_key"):
                    self._choose_file_for_gallery(source.property("gallery_import_key"))
                    return True

                if source.property("gallery_key"):
                    key = source.property("gallery_key")
                    filename = source.property("image_filename")
                    if filename:
                        gallery = self.galleries[key]
                        
                        # Toggle selection: if already selected, deselect it
                        if gallery['selected'] == filename:
                            gallery['selected'] = ""
                            if gallery.get('path_input'): 
                                gallery['path_input'].setText("")
                                gallery['path_input'].setPlaceholderText(tr("no_item_selected"))
                        else:
                            gallery['selected'] = filename
                            if gallery.get('path_input'): 
                                gallery['path_input'].setText(filename)
                        
                        if 'overlays' in gallery:
                            for overlay in gallery['overlays']:
                                overlay.setChecked(overlay.property("image_filename") == gallery['selected'])
                        else:
                            for label in gallery['labels']:
                                is_selected = label.property("image_filename") == gallery['selected']
                                label.setStyleSheet(THUMBNAIL_STYLE_SELECTED if is_selected else THUMBNAIL_STYLE)
                                
                        self._update_delete_button_state(key)
                        self._update_gallery_background_preview(key)
                        return True

                if source.property("heatmap_shape_control"):
                    self._open_heatmap_icon_selector()
                    return True

                if source.property("heatmap_streak_icon_control"):
                    self._open_heatmap_streak_icon_selector()
                    return True

                icon_source = source
                if not source.property("icon_key"):
                    icon_source = self._icon_control_for_child(source)
                if icon_source is not None and icon_source.property("icon_key"):
                    self._change_icon(icon_source)
                    return True
            except Exception:
                pass

        try:
            text_stack = getattr(source, "_onigiri_text_stack", None)
            if text_stack and (sip is None or not sip.isdeleted(text_stack)):
                hex_widget = text_stack.widget(1)

                if event.type() == QEvent.Type.Enter:
                    text_stack.setCurrentIndex(1)
                elif event.type() == QEvent.Type.Leave:
                    if not (hex_widget and hex_widget.hasFocus()):
                        text_stack.setCurrentIndex(0)
                return True
        except Exception:
            pass
            
        return super().eventFilter(source, event)

    def _icon_control_for_child(self, source):
        """Return the icon control that owns a child receiving mouse events."""
        if source is None or not hasattr(source, "parentWidget"):
            return None
        icon_widgets = []
        icon_widgets.extend(getattr(self, "icon_assignment_widgets", []) or [])
        icon_widgets.extend(getattr(self, "action_button_icon_widgets", []) or [])
        retention_widget = getattr(self, "retention_star_widget", None)
        if retention_widget is not None:
            icon_widgets.append(retention_widget)
        parent = source.parentWidget()
        while parent is not None:
            if parent in icon_widgets:
                return parent
            parent = parent.parentWidget()
        return None

    def _update_delete_button_state(self, key):
        gallery = self.galleries[key]
        if delete_button := gallery.get('delete_button'):
            delete_button.setEnabled(bool(gallery['selected']))

    def _create_icon_control_widget(self, key, display_name=None, config_key_prefix="modern_menu_icon_", compact=False):
        # Modern Card-like widget for icon control
        control_widget = QWidget()
        control_widget.setObjectName("iconControlWidget")
        control_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        control_widget.setCursor(Qt.CursorShape.PointingHandCursor)

        # Determine background and border colors based on theme
        if theme_manager.night_mode:
            bg_color = "rgba(255, 255, 255, 0.05)"
            border_color = "rgba(255, 255, 255, 0.1)"
            hover_color = "rgba(255, 255, 255, 0.1)"
            text_color = "#e0e0e0"
        else:
            bg_color = "rgba(0, 0, 0, 0.03)"
            border_color = "rgba(0, 0, 0, 0.1)"
            hover_color = "rgba(0, 0, 0, 0.06)"
            text_color = "#212121"

        radius = 14 if compact else 18
        control_widget.setStyleSheet(f"""
            QWidget#iconControlWidget {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: {radius}px;
            }}
            QWidget#iconControlWidget:hover {{
                background-color: {hover_color};
                border-color: {text_color};
            }}
        """)

        # Icon Preview
        preview_label = QLabel()
        preview_label.setFixedSize(32, 32)
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_label.setStyleSheet("background: transparent; border: none;") # Reset style for label inside card
        preview_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        display_text = display_name or tr(key) or key.replace("_", " ").title()
        name_label = QLabel(display_text)
        sub_label = QLabel(tr("click_to_change"))
        name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        sub_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # Delete / reset Button (Small trash icon or X)
        delete_btn = QPushButton()
        delete_btn.setFixedSize(24, 24)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setToolTip(tr("reset_to_default_tooltip"))

        trash_icon_path = system_icon_path("cancel.svg") # Using cancel.svg as delete icon

        if theme_manager.night_mode:
             delete_btn.setStyleSheet("/* onigiri-rounded-button-fix */\nQPushButton { background-color: transparent; border: 1px solid transparent; border-radius: 12px; } QPushButton:hover { background-color: rgba(255,0,0,0.2); border: 1px solid transparent; border-radius: 12px; }")
             trash_color = "#ff6b6b"
        else:
             delete_btn.setStyleSheet("/* onigiri-rounded-button-fix */\nQPushButton { background-color: transparent; border: 1px solid transparent; border-radius: 12px; } QPushButton:hover { background-color: rgba(255,0,0,0.1); border: 1px solid transparent; border-radius: 12px; }")
             trash_color = "#d32f2f"

        if os.path.exists(trash_icon_path):
            pixmap = QPixmap(trash_icon_path)
            if not pixmap.isNull():
                painter = QPainter(pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), QColor(trash_color))
                painter.end()
                delete_btn.setIcon(QIcon(pixmap))
            else:
                delete_btn.setText("âœ•")
                delete_btn.setStyleSheet(delete_btn.styleSheet() + f"color: {trash_color}; font-weight: bold;")
        else:
            delete_btn.setText("âœ•")
            delete_btn.setStyleSheet(delete_btn.styleSheet() + f"color: {trash_color}; font-weight: bold;")

        delete_btn.clicked.connect(lambda: self._delete_icon(control_widget))

        if compact:
            # Small button: icon on top, short caption below. The buttons share
            # the row equally so the strip spans the full container width.
            control_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            control_widget.setMinimumWidth(72)
            control_widget.setToolTip(f"{display_text} — {tr('click_to_change')}")

            layout = QVBoxLayout(control_widget)
            layout.setContentsMargins(6, 12, 6, 10)
            layout.setSpacing(6)

            name_label.setWordWrap(True)
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_label.setStyleSheet(f"background: transparent; border: none; font-weight: bold; color: {text_color}; font-size: 10px;")

            layout.addWidget(preview_label, 0, Qt.AlignmentFlag.AlignHCenter)
            layout.addWidget(name_label, 0, Qt.AlignmentFlag.AlignHCenter)

            # Reset still works via _delete_icon, but the per-button "x" is hidden
            # to keep the strip clean.
            delete_btn.hide()
        else:
            layout = QHBoxLayout(control_widget)
            layout.setContentsMargins(10, 8, 10, 8)
            layout.setSpacing(10)

            # Info/Edit Text
            text_layout = QVBoxLayout()
            text_layout.setSpacing(2)
            name_label.setStyleSheet(f"background: transparent; border: none; font-weight: bold; color: {text_color}; font-size: 13px;")
            sub_label.setStyleSheet(f"background: transparent; border: none; color: {text_color}; opacity: 0.7; font-size: 10px;")

            text_layout.addWidget(name_label)
            text_layout.addWidget(sub_label)
            text_layout.addStretch()

            layout.addWidget(preview_label)
            layout.addLayout(text_layout)
            layout.addStretch()
            layout.addWidget(delete_btn)

        # Properties
        control_widget.setProperty("icon_key", key)
        control_widget.setProperty("config_key_prefix", config_key_prefix)
        control_widget.setProperty("icon_filename", mw.col.conf.get(f"{config_key_prefix}{key}", ""))
        # Plain Python attributes, not Qt properties: see the comment on
        # _onigiri_text_stack above for why .property()/.setProperty() is unsafe
        # for cross-widget references that may outlive the referenced widget.
        control_widget._onigiri_preview_label = preview_label
        control_widget._onigiri_sub_label = sub_label # To update text if needed

        def open_icon_picker(event, widget=control_widget):
            if event.button() == Qt.MouseButton.LeftButton:
                event.accept()
                self._change_icon(widget)
                return
            event.ignore()

        control_widget.mousePressEvent = open_icon_picker
        control_widget.installEventFilter(self)
        
        self._update_icon_preview_for_widget(control_widget)
        return control_widget

    def _update_icon_preview_for_widget(self, widget, size=24):
        key = widget.property("icon_key"); filename = widget.property("icon_filename"); preview_label = getattr(widget, "_onigiri_preview_label", None)
        icon_color = "#e0e0e0" if theme_manager.night_mode else "#212121"; svg_xml = ""
        if key == "retention_star" and hasattr(self, "box_effect_star_light_color_input"):
            icon_color = self._box_effect_color_for_input(
                self.box_effect_star_light_color_input,
                DEFAULTS["colors"]["light"].get("--star-color", "#FFD700"),
            )
        if key == "retention_star" and filename:
            pixmap = self._render_icon_value_pixmap(filename, icon_color, size)
            if not pixmap.isNull():
                preview_label.setPixmap(pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                return
        if filename and (str(filename).startswith(("system:", "emoji:")) or self._icon_value_path(filename)):
            pixmap = self._render_icon_value_pixmap(filename, icon_color, size)
            if not pixmap.isNull():
                preview_label.setPixmap(pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                return
        if filename:
            filepath = os.path.join(self.addon_path, "user_files/icons", filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f: svg_xml = f.read()
        if not svg_xml:
            default_key = 'star_filled' if key == 'retention_star' else key
            default_filename = {
                "create_deck": "add-deck.svg",
                "filtered_deck": "filtered-deck.svg",
            }.get(default_key, ICON_DEFAULTS.get(default_key, ""))
            if default_filename and not default_filename.startswith("data:image/svg+xml,"):
                default_path = system_icon_path(default_filename)
                if os.path.exists(default_path):
                    try:
                        with open(default_path, "r", encoding="utf-8") as df:
                            svg_xml = df.read()
                    except Exception:
                        svg_xml = ""
            if not svg_xml:
                data_uri = ICON_DEFAULTS.get(default_key, "")
                if data_uri.startswith("data:image/svg+xml,"):
                    encoded_svg = data_uri.split(",", 1)[1]
                    svg_xml = urllib.parse.unquote(encoded_svg)
        if not svg_xml:
            entry = sidebar_api.get_sidebar_entries().get(key)
            if entry and entry.icon_svg:
                icon_value = entry.icon_svg.strip()
                if icon_value.startswith("data:image/svg+xml"):
                    try:
                        header, data = icon_value.split(",", 1)
                        if ";base64" in header:
                            svg_xml = base64.b64decode(data).decode("utf-8", errors="ignore")
                        else:
                            svg_xml = urllib.parse.unquote(data)
                    except Exception:
                        svg_xml = ""
                elif icon_value.lstrip().startswith("<svg"):
                    svg_xml = icon_value
        if not svg_xml: preview_label.setPixmap(QPixmap()); return
        if "currentColor" in svg_xml: colored_svg = svg_xml.replace("currentColor", icon_color)
        else: colored_svg = svg_xml.replace('<svg', f'<svg fill="{icon_color}" stroke="{icon_color}"', 1)
        
        renderer = QSvgRenderer(colored_svg.encode('utf-8'))
        dpr = preview_label.devicePixelRatioF() if hasattr(preview_label, "devicePixelRatioF") else 1.0
        pixmap = QPixmap(int(size * dpr), int(size * dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        renderer.render(painter, svg_contain_rect(renderer, size))
        painter.end()
        preview_label.setPixmap(pixmap)

    def _change_icon(self, widget):
        if not widget: return
        
        current_filename = widget.property("icon_filename")
        
        if widget in getattr(self, "icon_assignment_widgets", []):
            if str(current_filename).startswith("emoji:"):
                current_filename = ""
            preview_color_key = "light_filtered" if widget.property("icon_key") == "filtered_deck" else "light_icon"
            picker = DeckIconPickerDialog(
                current_filename,
                self.addon_path,
                self,
                allow_emoji=False,
                color_options=self._deck_icon_picker_color_options(),
                preview_color_key=preview_color_key,
            )
        elif widget.property("icon_key") == "retention_star":
            if str(current_filename).startswith("emoji:"):
                current_filename = ""
            picker = DeckIconPickerDialog(
                current_filename,
                self.addon_path,
                self,
                allow_emoji=False,
                color_options=self._retention_star_picker_color_options(),
                preview_color_key="star_light",
            )
        else:
            picker = IconPickerDialog(current_filename, self.addon_path, self)
        
        def on_selected(filename):
            if widget.property("icon_key") == "retention_star" and str(filename).startswith("emoji:"):
                return
            widget.setProperty("icon_filename", filename)
            self._update_icon_preview_for_widget(widget)
            if widget.property("icon_key") == "retention_star" and hasattr(self, "box_effect_preview"):
                self._update_box_effect_preview()
            if widget in getattr(self, "icon_assignment_widgets", []) and hasattr(self, "deck_icon_preview"):
                self._update_deck_icon_preview()

            # If this is part of the icon assignment widgets, confirm update?
            # The original code just updated the property and waited for Save?
            # Yes, mw.col.conf is read in _update_icon_preview... wait.
            # _update_icon_preview uses: filename = widget.property("icon_filename")
            # But the SAVE function needs to know.
            # The properties are read back during save?
            # Actually, `self._save_config` probably iterates widgets.
            # Let's check how saving works later, but updating the property should be enough for now.
            
            # If we need to trigger immediate "apply" (like applying theme), we might need more.
            # But for Settings Dialog, changes usually apply on "Save" or "Apply".
            
            # Update the config key immediately for preview purposes if needed?
            # mw.col.conf[f"modern_menu_icon_{widget.property('icon_key')}"] = filename # This might be premature if user cancels settings.
            # But `_update_icon_preview_for_widget` reads from widget property primarily.
        
        picker.iconSelected.connect(on_selected)
        if widget.property("icon_key") == "retention_star" and hasattr(picker, "colorsChanged"):
            picker.colorsChanged.connect(self._apply_retention_star_picker_colors)
        elif widget in getattr(self, "icon_assignment_widgets", []) and hasattr(picker, "colorsChanged"):
            picker.colorsChanged.connect(self._apply_deck_icon_picker_colors)
        
        # Center picker
        parent_geo = self.geometry()
        picker_geo = picker.geometry()
        x = parent_geo.x() + (parent_geo.width() - picker_geo.width()) // 2
        y = parent_geo.y() + (parent_geo.height() - picker_geo.height()) // 2
        picker.move(x, y)
        picker.exec()

    def _delete_icon(self, widget):
        widget.setProperty("icon_filename", "")
        self._update_icon_preview_for_widget(widget)
        if widget.property("icon_key") == "retention_star" and hasattr(self, "box_effect_preview"):
            self._update_box_effect_preview()
        if widget in getattr(self, "icon_assignment_widgets", []) and hasattr(self, "deck_icon_preview"):
            self._update_deck_icon_preview()

    def reset_icons_to_default(self):
        for widget in self.icon_assignment_widgets: self._delete_icon(widget)
        for widget in self.action_button_icon_widgets: self._delete_icon(widget)
        if hasattr(self, "retention_star_widget") and self.retention_star_widget:
            self._delete_icon(self.retention_star_widget)

    def create_icon_size_spinbox(self, key, default_value):
        spinbox = QSpinBox()
        spinbox.setObjectName("iconSizeSpinBox")
        spinbox.setMinimum(8)
        spinbox.setMaximum(48)
        spinbox.setSuffix(" px")
        spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        spinbox.setFixedHeight(32)
        spinbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        spinbox.setValue(mw.col.conf.get(f"modern_menu_icon_size_{key}", default_value))

        # Keep the caret out of the " px" suffix so the user can edit the number
        # but never alter (or delete) the unit text.
        line_edit = spinbox.lineEdit()

        def _clamp_cursor(*_):
            suffix_len = len(spinbox.suffix())
            max_pos = max(0, len(line_edit.text()) - suffix_len)
            if line_edit.cursorPosition() > max_pos:
                line_edit.setCursorPosition(max_pos)

        line_edit.cursorPositionChanged.connect(_clamp_cursor)

        self.icon_size_widgets[key] = spinbox
        return spinbox

    def reset_icon_sizes_to_default(self):[widget.setValue(DEFAULT_ICON_SIZES[key])for key,widget in self.icon_size_widgets.items()]

    def reset_deck_to_default(self):
        for widget in getattr(self, "icon_assignment_widgets", []):
            self._delete_icon(widget)

        for key, widget in getattr(self, "icon_size_widgets", {}).items():
            if key in DEFAULT_ICON_SIZES:
                widget.setValue(DEFAULT_ICON_SIZES[key])

        for attr, default in (
            ("hide_folder_cb", False),
            ("hide_subdeck_cb", False),
            ("hide_deck_cb", False),
            ("hide_filtered_deck_cb", False),
            ("hide_default_custom_cb", False),
            ("hide_deck_counts_checkbox", DEFAULTS.get("hideDeckCounts", True)),
            ("hide_all_deck_counts_checkbox", DEFAULTS.get("hideAllDeckCounts", False)),
        ):
            widget = getattr(self, attr, None)
            if widget is not None:
                widget.setChecked(default)

        if hasattr(self, "indentation_mode_group"):
            for button in self.indentation_mode_group.buttons():
                if button.property("indent_mode") == DEFAULTS.get("deck_indentation_mode", "default"):
                    button.setChecked(True)
                    break
            self._on_indentation_mode_btn_clicked(self.indentation_mode_group.checkedButton())
        if hasattr(self, "indentation_custom_spin"):
            self.indentation_custom_spin.setValue(DEFAULTS.get("deck_indentation_custom_px", 20))

        deck_color_keys = [
            "--deck-list-bg", "--highlight-bg", "--highlight-fg",
            "--icon-color", "--icon-color-filtered",
        ]
        for mode in ("light", "dark"):
            for key in deck_color_keys:
                widget = self.color_widgets.get(mode, {}).get(key)
                default = DEFAULTS.get("colors", {}).get(mode, {}).get(key)
                if widget is not None and default:
                    widget.setText(default)
                    self.current_config.setdefault("colors", {}).setdefault(mode, {})[key] = default

        overview_colors = self.current_config.setdefault("overview_style", {}).setdefault("colors", {})
        for mode in ("light", "dark"):
            mode_overview = overview_colors.setdefault(mode, {})
            for key, fallback_key, _label in self._overview_count_color_specs():
                mode_overview.pop(key, None)
                widget = getattr(self, "deck_overview_count_color_widgets", {}).get((mode, key))
                default = DEFAULTS.get("colors", {}).get(mode, {}).get(fallback_key)
                if widget is not None and default:
                    widget.setText(default)

        self._update_deck_icon_state()
        self._update_deck_icon_preview()
        show_settings_toast(self, tr("deck_reset_toast", "Deck settings reset to default"))

    def _on_settings_accent_changed(self, mode, value):
        color = QColor(value)
        if not color.isValid():
            return
        theme_key = "dark" if mode.startswith("dark") else "light"
        self.current_config.setdefault("colors", {}).setdefault(theme_key, {})["--accent-color"] = value
        if (theme_manager.night_mode and theme_key == "dark") or (not theme_manager.night_mode and theme_key == "light"):
            self.accent_color = value
            self._schedule_stylesheet_apply()

    def reset_background_to_default(self):
        if hasattr(self, "main_bg_color_only_toggle"):
            self.main_bg_color_only_toggle.setChecked(True)
            self.main_bg_slideshow_toggle.setChecked(False)
            self.main_bg_dynamic_toggle.setChecked(True)
            self.main_bg_single_color_input.setText(DEFAULTS["colors"]["light"]["--bg"])
            self.main_bg_light_color_input.setText(DEFAULTS["colors"]["light"]["--bg"])
            self.main_bg_dark_color_input.setText(DEFAULTS["colors"]["dark"]["--bg"])
            self.main_bg_slideshow_images = []
            self.main_bg_slideshow_index = 0
            self.main_bg_slideshow_interval_spinbox.setValue(10)
        elif hasattr(self, "color_radio"):
            self.color_radio.setChecked(True)
            if hasattr(self, 'bg_single_color_input'):
                 self.bg_single_color_input.setText(DEFAULTS["colors"]["light"]["--bg"])
            self.bg_light_color_input.setText(DEFAULTS["colors"]["light"]["--bg"])
            self.bg_dark_color_input.setText(DEFAULTS["colors"]["dark"]["--bg"])
        
        for key in ['main_single', 'main_light', 'main_dark']:
            if key in self.galleries:
                self.galleries[key]['selected'] = ""
                if self.galleries[key].get('path_input'): 
                    self.galleries[key]['path_input'].setText("")
                if self.galleries[key].get('grid_layout'):
                    self._refresh_gallery(key)
        
        if hasattr(self, "main_bg_blur_slider"):
            self.main_bg_blur_slider.setValue(0)
            self.main_bg_opacity_slider.setValue(100)
            self._update_main_background_controls()
        else:
            self.bg_blur_spinbox.setValue(0)
            self.bg_opacity_spinbox.setValue(100)

        show_settings_toast(self, tr("main_bg_reset_toast", "Main background reset to default"))

    def _animate_visibility(self, widget, should_be_visible, animate=True):
        """Animates the visibility of a widget by changing its height."""
        # If animation is disabled or dialog not visible, set state immediately
        if not animate or not self.isVisible():
            widget.setVisible(should_be_visible)
            if should_be_visible:
                widget.setMaximumHeight(16777215)
                widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
            else:
                widget.setMaximumHeight(0)
                widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Maximum)
            return

        # Stop any running animation
        if hasattr(widget, '_visibility_anim') and widget._visibility_anim.state() == QPropertyAnimation.State.Running:
            widget._visibility_anim.stop()
            widget._visibility_anim.deleteLater()

        if should_be_visible:
            # Already visible and expanded - nothing to do
            if widget.isVisible() and widget.maximumHeight() == 16777215:
                return

            # Make widget visible but collapsed before animating
            if not widget.isVisible():
                widget.setMaximumHeight(0)
                widget.setVisible(True)

            # Set size policy for animation
            widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
            
            # Force layout update to get accurate size hint
            widget.adjustSize()
            widget.updateGeometry()
            QGuiApplication.processEvents()
            
            target_height = widget.sizeHint().height()
            
            # Create and configure animation
            anim = QPropertyAnimation(widget, b"maximumHeight", self)
            anim.setDuration(250)
            anim.setStartValue(0)
            anim.setEndValue(target_height)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            
            def on_show_finish():
                if widget.isVisible():
                    widget.setMaximumHeight(16777215)
                    widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
                    widget.updateGeometry()

            anim.finished.connect(on_show_finish)
            
            widget._visibility_anim = anim
            anim.start()
        else:
            # Already hidden - nothing to do
            if not widget.isVisible():
                return
            
            # Immediately hide the widget to prevent flickering
            widget.setVisible(False)
            widget.setMaximumHeight(0)
            widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Maximum)
            widget.updateGeometry()

    def toggle_background_options(self, checked=None): 
        # Prevent flickering by ignoring the signal from the button being unchecked
        if isinstance(self.sender(), QRadioButton) and not self.sender().isChecked():
            return

        # Atomic update for initial visibility state
        self.setUpdatesEnabled(False)
        try:
            is_color = self.color_radio.isChecked()
            is_image = self.image_color_radio.isChecked()
            is_slideshow = self.slideshow_radio.isChecked()

            should_animate_color_group = False
            
            # Handle Accent Color radio button visibility
            # Show only when "Solid Color" is selected
            if hasattr(self, 'color_theme_accent_radio'):
                self.color_theme_accent_radio.setVisible(is_color)
                # If accent was selected but we're switching to Image/Slideshow, reset to "One theme color"
                if not is_color and self.color_theme_accent_radio.isChecked():
                    self.color_theme_single_radio.setChecked(True)
            
            # Handle Color Group Visibility
            if hasattr(self, 'main_bg_color_group'):
                should_be_visible = is_color or is_image or is_slideshow
                is_currently_visible = self.main_bg_color_group.isVisible()
                
                if should_be_visible and not is_currently_visible:
                    # Transitioning from Hidden -> Visible (e.g. Accent -> Color)
                    # Prepare for animation
                    self.main_bg_color_group.setMaximumHeight(0)
                    self.main_bg_color_group.setVisible(True)
                    should_animate_color_group = True
                elif not should_be_visible:
                    self.main_bg_color_group.setVisible(False)
                # If already visible and staying visible, do nothing

            # Handle Image/Slideshow Groups with Animation ("Enlarge First")
            target_widget = None
            start_height = 0
            
            if hasattr(self, 'main_bg_image_group') and hasattr(self, 'main_bg_slideshow_group'):
                if is_image:
                    target_widget = self.main_bg_image_group
                    if self.main_bg_slideshow_group.isVisible():
                        start_height = self.main_bg_slideshow_group.height()
                elif is_slideshow:
                    target_widget = self.main_bg_slideshow_group
                    if self.main_bg_image_group.isVisible():
                        start_height = self.main_bg_image_group.height()
                
                # Hide non-selected widgets immediately
                if not is_image:
                    self.main_bg_image_group.setVisible(False)
                if not is_slideshow:
                    self.main_bg_slideshow_group.setVisible(False)

                if target_widget:
                    # If widget is already visible, do nothing (or maybe just ensure it's fully visible)
                    if target_widget.isVisible() and target_widget.maximumHeight() > 0:
                        pass # Already visible
                    else:
                        # Prepare for animation
                        # IMPORTANT: Set max height BEFORE showing to prevent flickering/jumping
                        target_widget.setMaximumHeight(start_height)
                        target_widget.setVisible(True)
                        
                        # Calculate target height based on content
                        # We force the layout to calculate the size hint
                        target_widget.updateGeometry()
        finally:
            self.setUpdatesEnabled(True)

        # Start animations AFTER updates are re-enabled
        
        # 1. Animate Color Group if needed
        if should_animate_color_group:
            self.main_bg_color_group.updateGeometry()
            color_target_height = self.main_bg_color_group.sizeHint().height()
            if color_target_height < 50: color_target_height = 100
            
            self.color_group_anim = QPropertyAnimation(self.main_bg_color_group, b"maximumHeight")
            self.color_group_anim.setDuration(300)
            self.color_group_anim.setStartValue(0)
            self.color_group_anim.setEndValue(color_target_height)
            self.color_group_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            self.color_group_anim.finished.connect(lambda: self.main_bg_color_group.setMaximumHeight(16777215))
            self.color_group_anim.start()

        # 2. Animate Image/Slideshow Group if needed
        if hasattr(self, 'main_bg_image_group') and hasattr(self, 'main_bg_slideshow_group'):
             if target_widget:
                # Check if we need to animate (if max height is restricted or we are switching)
                # If start_height > 0 (switching) or max height is 0 (opening), we animate.
                # If it's already open and fully visible, we might skip, but re-animating is safer to ensure correct state.
                
                target_height = target_widget.sizeHint().height()
                if target_height < 100: target_height = 500
                
                # Animate height
                self.anim = QPropertyAnimation(target_widget, b"maximumHeight")
                self.anim.setDuration(300) # 300ms duration
                self.anim.setStartValue(start_height)
                self.anim.setEndValue(target_height)
                self.anim.setEasingCurve(QEasingCurve.Type.OutQuad)
                
                # On finished, reset maximum height to allow dynamic resizing
                self.anim.finished.connect(lambda: target_widget.setMaximumHeight(16777215))
                self.anim.start()        

    def _create_light_dark_mode_toggle(self, current_mode, on_change):
        palette = self._settings_palette()
        muted = palette.get("--fg-subtle", "#6f7177")
        accent = self._settings_accent_color()

        widget = QWidget()
        widget.setObjectName("lightDarkModeToggle")
        widget.setFixedHeight(32)
        widget.setStyleSheet(f"""
            QWidget#lightDarkModeToggle {{
                background: transparent;
            }}
            QLabel#lightDarkModeIcon {{
                background: transparent;
                border: none;
                outline: none;
                padding: 0px;
            }}
        """)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        sun_button = QLabel()
        sun_button.setObjectName("lightDarkModeIcon")
        sun_button.setToolTip(tr("light_mode", "Light"))
        sun_button.setFixedSize(28, 28)
        sun_button.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sun_button.setCursor(Qt.CursorShape.PointingHandCursor)
        sun_button.setStyleSheet("background: transparent; border: none; padding: 0px;")

        moon_button = QLabel()
        moon_button.setObjectName("lightDarkModeIcon")
        moon_button.setToolTip(tr("dark_mode", "Dark"))
        moon_button.setFixedSize(28, 28)
        moon_button.setAlignment(Qt.AlignmentFlag.AlignCenter)
        moon_button.setCursor(Qt.CursorShape.PointingHandCursor)
        moon_button.setStyleSheet("background: transparent; border: none; padding: 0px;")

        toggle = AnimatedToggleButton(self, accent)
        toggle.setChecked(current_mode == "dark")

        def refresh_icons(checked):
            sun_color = muted if checked else accent
            moon_color = accent if checked else muted
            sun_button.setPixmap(self._themed_icon("sun.svg", sun_color, 17).pixmap(17, 17))
            moon_button.setPixmap(self._themed_icon("moon.svg", moon_color, 16).pixmap(16, 16))

        def handle_toggle(checked):
            refresh_icons(checked)
            on_change("dark" if checked else "light")

        sun_button.mousePressEvent = lambda event: toggle.setChecked(False)
        moon_button.mousePressEvent = lambda event: toggle.setChecked(True)
        toggle.toggled.connect(handle_toggle)
        refresh_icons(toggle.isChecked())

        layout.addWidget(sun_button)
        layout.addWidget(toggle)
        layout.addWidget(moon_button)
        return widget, toggle

    def _on_indentation_mode_btn_clicked(self, button):
        if not button: return
        mode = button.property("indent_mode")
        is_custom = (mode == "custom")
        if hasattr(self, 'indentation_custom_row_widget'):
            self.indentation_custom_row_widget.setVisible(is_custom)
        self._update_deck_icon_preview()

    def _update_deck_icon_state(self):
        # Disable the deck_folder size spinbox if either hide toggle is ON
        if "deck_folder" in self.icon_size_widgets:
            should_disable = (self.hide_folder_cb.isChecked() or
                            self.hide_subdeck_cb.isChecked() or
                            self.hide_deck_cb.isChecked())
            self.icon_size_widgets["deck_folder"].setEnabled(not should_disable)
        self._update_deck_icon_preview()


    def _refresh_anki_after_settings_save(self):
        try:
            from ..refresh import schedule_ui_refresh

            schedule_ui_refresh()
        except Exception:
            pass
