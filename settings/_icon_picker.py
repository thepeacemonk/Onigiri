# Icon picker dialogs (split out of the historical _legacy.py).
from ._common import *
from ._common import _contrast_icon_color
from ._widgets import *
from ..emoji_sprites import EMOJI_SPRITES


class LongPressIconCell(QFrame):
    def __init__(self, value, on_select, on_delete, preview_label, bg_color, fill_color="#ef4444", parent=None):
        super().__init__(parent)
        self.value = value
        self.on_select = on_select
        self.on_delete = on_delete
        self.preview_label = preview_label
        self.bg_color = bg_color
        self.fill_color = fill_color
        
        self.progress = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._update_progress)
        self.is_pressing = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_pressing = True
            self.progress = 0.0
            self.timer.start()
            
            if not hasattr(self, "effect"):
                self.effect = QGraphicsColorizeEffect()
                self.effect.setColor(QColor(self.bg_color))
                self.preview_label.setGraphicsEffect(self.effect)
            self.effect.setStrength(0.0)
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_pressing:
            self.is_pressing = False
            self.timer.stop()
            if self.progress >= 1.0:
                pass
            else:
                self.progress = 0.0
                if hasattr(self, "effect"):
                    self.effect.setStrength(0.0)
                self.update()
                if self.on_select:
                    self.on_select(self.value, self)
        super().mouseReleaseEvent(event)

    def _update_progress(self):
        if not getattr(self, "fading_out", False):
            self.progress += 0.02
            if self.progress >= 1.0:
                self.progress = 1.0
                self.effect.setStrength(1.0)
                self.fading_out = True
                
                self.opacity_effect = QGraphicsOpacityEffect()
                self.setGraphicsEffect(self.opacity_effect)
                self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
                self.fade_anim.setDuration(200)
                self.fade_anim.setStartValue(1.0)
                self.fade_anim.setEndValue(0.0)
                self.fade_anim.finished.connect(self._finish_delete)
                self.fade_anim.start()
            else:
                if hasattr(self, "effect"):
                    self.effect.setStrength(self.progress)
            self.update()

    def _finish_delete(self):
        self.timer.stop()
        self.is_pressing = False
        if self.on_delete:
            self.on_delete(self.value)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.progress > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            clip_path = QPainterPath()
            clip_path.addRoundedRect(0, 0, self.width(), self.height(), 14, 14)
            painter.setClipPath(clip_path)
            
            rect = QRectF(0, 0, self.width() * self.progress, self.height())
            color = QColor(self.fill_color)
            color.setAlpha(220)
            painter.fillRect(rect, color)


class IconPickerDialog(QDialog):
    iconSelected = pyqtSignal(str)

    def __init__(self, current_filename, addon_path, parent=None):
        super().__init__(parent)
        self.addon_path = addon_path
        self.current_filename = current_filename
        self.setWindowTitle("Select Icon")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.setFixedSize(400, 500)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.container = QFrame()
        self.container.setObjectName("IconPickerContainer")
        if theme_manager.night_mode:
             self.container.setStyleSheet("QFrame#IconPickerContainer { background-color: #2c2c2c; border-radius: 12px; border: 1px solid #4a4a4a; }")
        else:
             self.container.setStyleSheet("QFrame#IconPickerContainer { background-color: #ffffff; border-radius: 12px; border: 1px solid #e0e0e0; }")

        container_layout = QVBoxLayout(self.container)
        container_layout.setSpacing(15)
        
        # --- Header ---
        header_layout = QHBoxLayout()
        title_label = QLabel(tr("select_icon"))
        if theme_manager.night_mode:
            title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #e0e0e0;")
        else:
            title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #212121;")
            
        close_btn = QPushButton()
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        
        # Load xmark.svg
        xmark_path = system_icon_path("xmark.svg")
        
        if theme_manager.night_mode:
            close_btn.setStyleSheet("""
                QPushButton { background-color: transparent; border: none; border-radius: 12px; }
                QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }
            """)
            icon_color = "#e0e0e0"
        else:
            close_btn.setStyleSheet("""
                QPushButton { background-color: transparent; border: none; border-radius: 12px; }
                QPushButton:hover { background-color: rgba(0, 0, 0, 0.05); }
            """)
            icon_color = "#555555"

        if os.path.exists(xmark_path):
            self._render_svg_to_icon(xmark_path, close_btn, icon_color)
        else:
            close_btn.setText("x")
            close_btn.setStyleSheet(close_btn.styleSheet() + f"color: {icon_color}; font-weight: bold; font-size: 16px;")

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(close_btn)
        container_layout.addLayout(header_layout)
        
        # --- Tools & Add ---
        tools_layout = QHBoxLayout()
            
        add_btn = QPushButton(tr("add_icon"))
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._add_icon_from_file)
        if theme_manager.night_mode:
            add_btn.setStyleSheet("QPushButton { background-color: #3a3a3a; border: 1px solid #555; border-radius: 16px; padding: 4px 10px; color: #e0e0e0; } QPushButton:hover { background-color: #4a4a4a; }")
        else:
            add_btn.setStyleSheet("QPushButton { background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 16px; padding: 4px 10px; color: #212121; } QPushButton:hover { background-color: #e0e0e0; }")
            
        tools_layout.addWidget(add_btn)

        # Use Default Button
        default_btn = QPushButton(tr("use_default"))
        default_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        default_btn.clicked.connect(lambda: (self.iconSelected.emit(""), self.close()))
        if theme_manager.night_mode:
            default_btn.setStyleSheet("QPushButton { background-color: transparent; border: 1px solid #555; border-radius: 16px; padding: 4px 10px; color: #e0e0e0; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.05); }")
        else:
            default_btn.setStyleSheet("QPushButton { background-color: transparent; border: 1px solid #ccc; border-radius: 16px; padding: 4px 10px; color: #212121; } QPushButton:hover { background-color: rgba(0, 0, 0, 0.02); }")
        
        tools_layout.addWidget(default_btn)
        container_layout.addLayout(tools_layout)
        
        # --- Icon Grid ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; } QWidget { background: transparent; }")
        
        self.grid_content = QWidget()
        self.grid_layout = FlowLayout(self.grid_content, margin=0, spacing=10)
        
        scroll_area.setWidget(self.grid_content)
        container_layout.addWidget(scroll_area)
        
        self.icons = [] # List of (filename, widget)
        self._load_icons()
        
        layout.addWidget(self.container)

    def _render_svg_to_icon(self, filepath, button, color_hex):
        try:
            with open(filepath, 'r', encoding='utf-8') as f: svg_xml = f.read()
            if "currentColor" in svg_xml: colored_svg = svg_xml.replace("currentColor", color_hex)
            else: colored_svg = svg_xml.replace('<svg', f'<svg fill="{color_hex}" stroke="{color_hex}"', 1)
            
            renderer = QSvgRenderer(colored_svg.encode('utf-8'))
            dpr = button.devicePixelRatioF() if hasattr(button, "devicePixelRatioF") else 1.0
            pixmap = QPixmap(int(12 * dpr), int(12 * dpr))
            pixmap.setDevicePixelRatio(dpr)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            renderer.render(painter, QRectF(0, 0, 12, 12))
            painter.end()
            
            # Simple scaling if needed, but for icon button usually best to let QIcon handle or pre-scale
            button.setIcon(QIcon(pixmap))
            button.setIconSize(QSize(12, 12))
        except:
             button.setText("x")

    def _load_icons(self):
        # Clear existing
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.icons = []

        icons_dir = os.path.join(self.addon_path, "user_files/icons")
        if not os.path.exists(icons_dir):
            os.makedirs(icons_dir)
            
        files = sorted([f for f in os.listdir(icons_dir) if f.lower().endswith(".svg")])
        
        row, col = 0, 0
        num_cols = 4
        
        for filename in files:
            container = QWidget()
            container.setFixedSize(70, 70)
            container.setObjectName("IconItem")
            
            # Highlight if selected
            is_selected = (filename == self.current_filename)
            
            # Style
            bg_normal = "transparent"
            bg_hover = "rgba(255,255,255,0.1)" if theme_manager.night_mode else "rgba(0,0,0,0.05)"
            bg_selected = "rgba(255,255,255,0.2)" if theme_manager.night_mode else "rgba(0,0,0,0.1)"
            border_selected = "#777" if theme_manager.night_mode else "#aaa"
            
            container.setStyleSheet(f"""
                QWidget#IconItem {{
                    background-color: {bg_selected if is_selected else bg_normal};
                    border-radius: 18px;
                    border: {("1px solid " + border_selected) if is_selected else "1px solid transparent"};
                }}
                QWidget#IconItem:hover {{
                    background-color: {bg_hover};
                    border: 1px solid {border_selected};
                }}
            """)
            
            # Image
            layout = QVBoxLayout(container)
            layout.setContentsMargins(5, 5, 5, 5)
            
            preview = QLabel()
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Load SVG
            filepath = os.path.join(icons_dir, filename)
            # Render SVG
            self._render_svg_to_label(filepath, preview)
            
            layout.addWidget(preview)
            
            # Clickable overlay for selection
            btn = QPushButton(container)
            btn.setStyleSheet("background: transparent; border: none;")
            btn.setFixedSize(70, 70)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, f=filename: self._select_icon(f))
            btn.move(0, 0)
            
            # Delete Button (Top Right)
            del_btn = QPushButton(container)
            del_btn.setFixedSize(20, 20)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.move(45, 5) # Position top-right
            
            # Load xmark icon
            xmark_path = system_icon_path("xmark.svg")
            
            # Style for delete button: No background, no hover effect as requested
            btn_style = "QPushButton { background-color: transparent; border: none; }"
            
            if theme_manager.night_mode:
                del_btn.setStyleSheet(btn_style)
                icon_color = "#e0e0e0"
            else:
                del_btn.setStyleSheet(btn_style)
                icon_color = "#555555"

            if os.path.exists(xmark_path):
                self._render_svg_to_icon(xmark_path, del_btn, icon_color)
            else:
                del_btn.setText("×")
                del_btn.setStyleSheet(del_btn.styleSheet() + f"color: {icon_color}; font-weight: bold; padding-bottom: 2px;")

            del_btn.clicked.connect(lambda _, f=filename: self._delete_icon_file(f))
            del_btn.raise_() # Ensure it's on top of the selection buttton
            
            if isinstance(self.grid_layout, FlowLayout):
                self.grid_layout.addWidget(container)
            else:
                self.grid_layout.addWidget(container, row, col)
            self.icons.append((filename, container))
            
            col += 1
            if col >= num_cols:
                col = 0
                row += 1

    def _delete_icon_file(self, filename):
        confirm = QMessageBox.question(self, "Delete Icon", f"Are you sure you want to delete '{filename}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                os.remove(os.path.join(self.addon_path, "user_files/icons", filename))
                self._load_icons() # Reload grid
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not delete file: {e}")

    def _render_svg_to_label(self, filepath, label):
        color = "#e0e0e0" if theme_manager.night_mode else "#212121"
        try:
            with open(filepath, 'r', encoding='utf-8') as f: svg_xml = f.read()
            if "currentColor" in svg_xml: colored_svg = svg_xml.replace("currentColor", color)
            else: colored_svg = svg_xml.replace('<svg', f'<svg fill="{color}" stroke="{color}"', 1)
            
            renderer = QSvgRenderer(colored_svg.encode('utf-8'))
            dpr = label.devicePixelRatioF() if hasattr(label, "devicePixelRatioF") else 1.0
            pixmap = QPixmap(int(32 * dpr), int(32 * dpr))
            pixmap.setDevicePixelRatio(dpr)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            renderer.render(painter, QRectF(0, 0, 32, 32))
            painter.end()
            label.setPixmap(pixmap)
        except:
             label.setText("?")

    def _filter_icons(self, text):
        text = text.lower()
        # Simple hide/show logic. Since it's a grid, hiding items leaves gaps in QGridLayout.
        # We should probably clear and rebuild grid if we want to remove gaps, or use a FlowLayout.
        # For simplicity/speed: Rebuild grid.
        
        # Clear grid
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            
        files = [f for f, _ in self.icons] # We are effectively just using self.icons as a cache of available files + widgets? 
        # Re-read files probably easier or reuse logic.
        
        icons_dir = os.path.join(self.addon_path, "user_files/icons")
        all_files = sorted([f for f in os.listdir(icons_dir) if f.lower().endswith(".svg")])
        filtered_files = [f for f in all_files if text in f.lower()]
        
        row, col = 0, 0
        num_cols = 4
        
        for filename in filtered_files:
            container = QWidget()
            container.setFixedSize(70, 70)
            is_selected = (filename == self.current_filename)
            
            bg_normal = "transparent"
            bg_hover = "rgba(255,255,255,0.1)" if theme_manager.night_mode else "rgba(0,0,0,0.05)"
            bg_selected = "rgba(255,255,255,0.2)" if theme_manager.night_mode else "rgba(0,0,0,0.1)"
            border_selected = "#777" if theme_manager.night_mode else "#aaa"
            
            container.setStyleSheet(f"QWidget {{ background-color: {bg_selected if is_selected else bg_normal}; border-radius: 18px; border: {('1px solid ' + border_selected) if is_selected else '1px solid transparent'}; }} QWidget:hover {{ background-color: {bg_hover}; border: 1px solid {border_selected}; border-radius: 18px; }}")
            
            layout = QVBoxLayout(container); layout.setContentsMargins(5, 5, 5, 5)
            preview = QLabel(); preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._render_svg_to_label(os.path.join(icons_dir, filename), preview)
            layout.addWidget(preview)
            
            btn = QPushButton(container)
            btn.setStyleSheet("background: transparent; border: none;")
            btn.setFixedSize(70, 70); btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, f=filename: self._select_icon(f))
            btn.move(0, 0)
            
            if isinstance(self.grid_layout, FlowLayout):
                self.grid_layout.addWidget(container)
            else:
                self.grid_layout.addWidget(container, row, col)

    def _select_icon(self, filename):
        self.iconSelected.emit(filename)
        self.close()

    def _add_icon_from_file(self):
        icons_dir = os.path.join(self.addon_path, "user_files/icons")
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Icon", os.path.expanduser("~"), "SVG Files (*.svg)")
        if filepath:
            filename = os.path.basename(filepath)
            dest_path = os.path.join(icons_dir, filename)
            if not os.path.exists(dest_path) or not os.path.samefile(filepath, dest_path):
                try: shutil.copy(filepath, dest_path)
                except Exception as e: QMessageBox.warning(self, "Error", f"Could not copy icon: {e}"); return
            
            self._load_icons() # Reload grid
            # self.search_input.setText("")

    def focusOutEvent(self, event):
        self.close()


class DeckIconPickerDialog(QDialog):
    iconSelected = pyqtSignal(str)
    colorsChanged = pyqtSignal(dict)

    EMOJIS = EMOJI_SPRITES
    ICON_PRIORITY = [
        "deck.svg", "folder.svg", "star.svg", "filtered-deck.svg",
        "add-card.svg", "add-deck.svg", "add-subdeck.svg",
        "add.svg", "browse.svg", "stats.svg", "sync.svg", "settings.svg",
        "rename.svg", "mark_circle.svg", "focus.svg", "gamepad.svg",
    ]

    def __init__(self, current_icon, addon_path, parent=None, allow_emoji=True, color_options=None, preview_color_key=None, night_mode=None):
        super().__init__(parent)
        self.addon_path = addon_path
        # Callers (e.g. Hashi Notes) can force the picker to match their own
        # light/dark state so its colours stay aligned; defaults to Anki's theme.
        self._dark = bool(theme_manager.night_mode) if night_mode is None else bool(night_mode)
        self.current_icon = current_icon or ""
        self.allow_emoji = allow_emoji
        self.color_options = color_options or []
        self.color_values = {
            option.get("key"): option.get("value", "#00A982")
            for option in self.color_options
            if option.get("key")
        }
        self.preview_color_key = preview_color_key or (self.color_options[0].get("key") if self.color_options else None)
        self._color_buttons = {}
        self._cell_widgets = {}
        self._has_color_mode_pairs = self._color_options_have_mode_pairs()
        self.setWindowTitle("Edit Icon")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(620 if self.color_options else 540, 700 if self.color_options else 610)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        self.container = QFrame()
        self.container.setObjectName("IconPickerContainer")
        if self._dark:
            self.container.setStyleSheet("QFrame#IconPickerContainer { background-color: #161616; border-radius: 20px; border: 1px solid #343434; }")
            self._fg = "#f4f4f5"
            self._muted = "#b6b6b8"
            self._surface = "#2a2a2a"
            self._border = "#3a3a3a"
        else:
            self.container.setStyleSheet("QFrame#IconPickerContainer { background-color: #ffffff; border-radius: 20px; border: 1px solid #e5e7eb; }")
            self._fg = "#1f2933"
            self._muted = "#4b5563"
            self._surface = "#f1f1f0"
            self._border = "#e5e7eb"
        outer.addWidget(self.container)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        self.title_label = QLabel("Edit Icon")
        self.title_label.setStyleSheet(f"font-weight: 700; font-size: 15px; color: {self._fg};")
        self.close_btn = QPushButton()
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setStyleSheet(f"QPushButton {{ background: transparent; border: none; border-radius: 14px; color: {self._muted}; font-size: 20px; }} QPushButton:hover {{ color: {self._fg}; background: rgba(128, 128, 128, 0.14); }}")
        self._update_close_button_icon()
        self.close_btn.clicked.connect(self.close)
        header.addWidget(self.title_label)
        header.addStretch()

        self.preview_mode = "dark" if self._dark else "light"
        if self.parent() and hasattr(self.parent(), "_create_light_dark_mode_toggle"):
            self.preview_mode_widget, self.preview_mode_toggle = self.parent()._create_light_dark_mode_toggle(
                self.preview_mode,
                self._on_preview_mode_toggled,
            )
            header.addWidget(self.preview_mode_widget)

        header.addWidget(self.close_btn)
        layout.addLayout(header)

        if self.color_options:
            layout.addWidget(self._colors_panel())
            self._sync_preview_mode_availability()

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: transparent; }}
            QTabBar::tab {{
                min-height: 30px;
                padding: 0 14px;
                border: none;
                border-radius: 10px;
                color: {self._muted};
                background: transparent;
            }}
            QTabBar::tab:selected {{
                color: {self._fg};
                background: {self._surface};
            }}
            QTabBar {{ qproperty-drawBase: 0; }}
        """)
        self.tabs.tabBar().setDrawBase(False)
        layout.addWidget(self.tabs, 1)

        self._build_tabs()

        footer = QHBoxLayout()
        footer.setSpacing(10)
        save_btn = QPushButton(tr("save"))
        cancel_btn = QPushButton("Cancel")
        reset_btn = QPushButton("Reset to Default")
        self.cancel_btn = cancel_btn
        self.reset_btn = reset_btn
        for btn in (save_btn, cancel_btn, reset_btn):
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(36)
        accent = getattr(self.parent(), "accent_color", "#00A982") if self.parent() else "#00A982"
        if type(accent) is QColor:
            accent = accent.name()
        hover = QColor(accent).lighter(110).name()
        save_btn.setStyleSheet(f"QPushButton {{ background: {accent}; color: #ffffff; border: none; border-radius: 18px; padding: 0 20px; font-weight: 700; }} QPushButton:hover {{ background: {hover}; }}")
        for btn in (cancel_btn, reset_btn):
            btn.setStyleSheet(f"QPushButton {{ background: {self._surface}; color: {self._fg}; border: 1px solid {self._border}; border-radius: 18px; padding: 0 18px; }}")
        save_btn.clicked.connect(self._save_and_close)
        reset_btn.clicked.connect(lambda: (self.iconSelected.emit(""), self.close()))
        cancel_btn.clicked.connect(self.close)
        footer.addStretch()
        footer.addWidget(save_btn)
        footer.addWidget(cancel_btn)
        footer.addWidget(reset_btn)
        footer.addStretch()
        layout.addLayout(footer)

    def _save_and_close(self):
        self.iconSelected.emit(self.current_icon)
        self.close()

    def _on_preview_mode_toggled(self, mode):
        self.preview_mode = mode
        if mode == "dark":
            self.container.setStyleSheet("QFrame#IconPickerContainer { background-color: #161616; border-radius: 20px; border: 1px solid #343434; }")
            self._fg = "#f4f4f5"
            self._muted = "#b6b6b8"
            self._surface = "#2a2a2a"
            self._border = "#3a3a3a"
        else:
            self.container.setStyleSheet("QFrame#IconPickerContainer { background-color: #ffffff; border-radius: 20px; border: 1px solid #e5e7eb; }")
            self._fg = "#1f2933"
            self._muted = "#4b5563"
            self._surface = "#f1f1f0"
            self._border = "#e5e7eb"

        if hasattr(self, 'title_label'):
            self.title_label.setStyleSheet(f"font-weight: 700; font-size: 15px; color: {self._fg};")
            self.close_btn.setStyleSheet(f"QPushButton {{ background: transparent; border: none; border-radius: 14px; color: {self._muted}; font-size: 20px; }} QPushButton:hover {{ color: {self._fg}; background: rgba(128, 128, 128, 0.14); }}")
            self._update_close_button_icon()
            for btn in (self.cancel_btn, self.reset_btn):
                btn.setStyleSheet(f"QPushButton {{ background: {self._surface}; color: {self._fg}; border: 1px solid {self._border}; border-radius: 18px; padding: 0 18px; }}")

        if self.color_options and hasattr(self, "colors_panel_widget"):
            self.colors_panel_widget.setStyleSheet(f"""
                QFrame#IconPickerColorPanel {{
                    background: {self._surface};
                    border: 1px solid {self._border};
                    border-radius: 16px;
                }}
                QLabel {{
                    background: transparent;
                    border: none;
                    color: {self._fg};
                }}
            """)
            for label in getattr(self, "colors_panel_labels", []):
                label.setStyleSheet(f"font-weight: 700; font-size: 12px; color: {self._fg};")
            for btn in getattr(self, "_color_buttons", {}).values():
                self._style_color_option_button(btn, btn.text())
            self._update_colors_panel_mode()

        if hasattr(self, 'tabs'):
            self.tabs.setStyleSheet(f"""
                QTabWidget::pane {{ border: none; background: transparent; }}
                QTabBar::tab {{
                    min-height: 30px;
                    padding: 0 14px;
                    border: none;
                    border-radius: 10px;
                    color: {self._muted};
                    background: transparent;
                }}
                QTabBar::tab:selected {{
                    color: {self._fg};
                    background: {self._surface};
                }}
                QTabBar {{ qproperty-drawBase: 0; }}
            """)
            self.tabs.tabBar().setDrawBase(False)

        self._build_tabs()

    def _update_close_button_icon(self):
        if not hasattr(self, "close_btn"):
            return
        xmark_icon = self._render_svg_to_icon(system_icon_path("cancel.svg"), self._fg, 16)
        if not xmark_icon.isNull():
            self.close_btn.setText("")
            self.close_btn.setIcon(xmark_icon)
            self.close_btn.setIconSize(QSize(16, 16))
        else:
            self.close_btn.setIcon(QIcon())
            self.close_btn.setText("×")

    def _custom_icon_dir(self):
        path = os.path.join(self.addon_path, "user_files", "custom_deck_icons")
        os.makedirs(path, exist_ok=True)
        return path

    def _icon_label(self, filename):
        stem = os.path.splitext(os.path.basename(filename))[0]
        return stem.replace("_", " ").replace("-", " ").title()

    def _emoji_svg_path(self, filename):
        return os.path.join(self.addon_path, "system_files", "emojis", os.path.basename(filename))

    def _delete_custom_icon(self, name):
        for folder in (self._custom_icon_dir(), os.path.join(self.addon_path, "user_files", "icons")):
            path = os.path.join(folder, name)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        if self.current_icon == name:
            self.current_icon = ""
        self._build_tabs()

    def _system_icon_items(self):
        system_dir = os.path.join(self.addon_path, "system_files", "system_icons", "available_for_users")
        if not os.path.isdir(system_dir):
            return []
        priority = {name: index for index, name in enumerate(self.ICON_PRIORITY)}
        files = [name for name in os.listdir(system_dir) if name.lower().endswith(".svg")]
        return [
            {"name": f"system:{name}", "label": self._icon_label(name), "path": os.path.join(system_dir, name), "system": True}
            for name in sorted(files, key=lambda item: (priority.get(item, 999), item.lower()))
        ]

    def _custom_items(self, extensions):
        items = []
        seen = set()
        for folder in (self._custom_icon_dir(), os.path.join(self.addon_path, "user_files", "icons")):
            if not os.path.isdir(folder):
                continue
            for name in sorted(os.listdir(folder), key=str.lower):
                lower = name.lower()
                if name in seen or not any(lower.endswith(ext) for ext in extensions):
                    continue
                seen.add(name)
                items.append({"name": name, "label": self._icon_label(name), "path": os.path.join(folder, name), "system": False})
        return items

    def _build_tabs(self):
        current_tab = self.tabs.currentIndex() if hasattr(self, "tabs") else 0
        self.tabs.clear()
        self._cell_widgets = {}
        if self.allow_emoji:
            self.tabs.addTab(self._emoji_tab(), "Emoji")
        self.tabs.addTab(self._icons_tab(), "Icons")
        
        if self.tabs.count() <= 1:
            self.tabs.tabBar().hide()
        else:
            self.tabs.tabBar().show()

        if current_tab >= 0:
            self.tabs.setCurrentIndex(min(current_tab, self.tabs.count() - 1))

    def _valid_color(self, value, fallback="#00A982"):
        return value if QColor(value).isValid() else fallback

    def _gallery_icon_color(self):
        mode = getattr(self, "preview_mode", "dark" if theme_manager.night_mode else "light")
        key = self.preview_color_key
        if key:
            if mode == "dark":
                if key == "light_icon": key = "dark_icon"
                elif key == "light_filtered": key = "dark_filtered"
                elif key == "star_light": key = "star_dark"
                elif key == "empty_light": key = "empty_dark"
                elif key == "light_shape": key = "dark_shape"
                elif key == "light_zero": key = "dark_zero"
            elif mode == "light":
                if key == "dark_icon": key = "light_icon"
                elif key == "dark_filtered": key = "light_filtered"
                elif key == "star_dark": key = "star_light"
                elif key == "empty_dark": key = "empty_light"
                elif key == "dark_shape": key = "light_shape"
                elif key == "dark_zero": key = "light_zero"
            return self._valid_color(self.color_values.get(key, self.color_values.get(self.preview_color_key, "#00A982")))
        return "#e0e0e0" if mode == "dark" else "#212121"

    def _color_option_mode(self, option):
        explicit_mode = option.get("mode")
        if explicit_mode in {"light", "dark", "single"}:
            return explicit_mode

        key = str(option.get("key", ""))
        if key.startswith("light_") or key.endswith("_light"):
            return "light"
        if key.startswith("dark_") or key.endswith("_dark"):
            return "dark"
        return "single"

    def _color_options_have_mode_pairs(self):
        modes = {self._color_option_mode(option) for option in self.color_options}
        return "light" in modes and "dark" in modes

    def _color_options_for_mode(self, mode):
        if not self._has_color_mode_pairs:
            return self.color_options
        return [
            option
            for option in self.color_options
            if self._color_option_mode(option) in {mode, "single"}
        ]

    def _clean_color_option_label(self, label, mode):
        text = str(label or "Color").strip()
        mode_title = mode.title()
        replacements = (
            (f"{mode_title} (", "("),
            (f"{mode_title} ", ""),
            (f" {mode_title}", ""),
            (f" ({mode_title})", ""),
        )
        for old, new in replacements:
            text = text.replace(old, new)
        return text.strip() or "Color"

    def _sync_preview_mode_availability(self):
        widget = getattr(self, "preview_mode_widget", None)
        if widget is None or not self.color_options:
            return
        widget.setEnabled(self._has_color_mode_pairs)
        widget.setToolTip("" if self._has_color_mode_pairs else "Only one palette is available for this icon.")

    def _update_colors_panel_mode(self):
        stack = getattr(self, "colors_mode_stack", None)
        if stack is None:
            return
        stack.setCurrentIndex(1 if self._has_color_mode_pairs and self.preview_mode == "dark" else 0)

    def _create_color_options_page(self, options, mode):
        page = QWidget()
        page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        layout = QGridLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(8)

        for index, option in enumerate(options):
            key = option.get("key")
            if not key:
                continue

            option_mode = self._color_option_mode(option)
            label_text = option.get("label", "Color")
            if option_mode in {"light", "dark"}:
                label_text = self._clean_color_option_label(label_text, mode)

            label = QLabel(label_text)
            label.setStyleSheet(f"font-weight: 700; font-size: 12px; color: {self._fg};")
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.colors_panel_labels.append(label)

            button = QPushButton()
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedHeight(34)
            button.setMinimumWidth(120)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            self._color_buttons[key] = button
            self._style_color_option_button(button, self.color_values.get(key, "#00A982"))
            button.clicked.connect(lambda _=False, k=key, b=button: self._choose_picker_color(k, b))

            row = index // 2
            col = (index % 2) * 2
            layout.addWidget(label, row, col)
            layout.addWidget(button, row, col + 1, Qt.AlignmentFlag.AlignRight)

        layout.setColumnStretch(0, 1)
        if len(options) > 1:
            layout.setColumnStretch(2, 1)
        return page

    def _colors_panel(self):
        panel = QFrame()
        self.colors_panel_widget = panel
        self.colors_panel_labels = []
        panel.setObjectName("IconPickerColorPanel")
        panel.setStyleSheet(f"""
            QFrame#IconPickerColorPanel {{
                background: {self._surface};
                border: 1px solid {self._border};
                border-radius: 16px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                color: {self._fg};
            }}
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)

        self.colors_mode_stack = QStackedWidget()
        self.colors_mode_stack.addWidget(self._create_color_options_page(self._color_options_for_mode("light"), "light"))
        if self._has_color_mode_pairs:
            self.colors_mode_stack.addWidget(self._create_color_options_page(self._color_options_for_mode("dark"), "dark"))
        layout.addWidget(self.colors_mode_stack)
        self._update_colors_panel_mode()
        return panel

    def _style_color_option_button(self, button, color):
        color = self._valid_color(color)
        button.setText(color.upper())
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: {_contrast_icon_color(color).name()};
                border: 1px solid {self._border};
                border-radius: 17px !important;
                font-weight: normal;
                font-size: 13px;
                font-family: monospace;
                letter-spacing: 0.5px;
                padding: 0 12px;
                outline: none;
            }}
            QPushButton:hover {{
                border-color: #00A982;
            }}
        """)

    def _choose_picker_color(self, key, anchor=None):
        current = self._valid_color(self.color_values.get(key, "#00A982"))
        chosen, ok = OnigiriColorDialog.getColor(current, self, anchor=anchor)
        if not ok:
            return
        chosen = self._valid_color(chosen, current)
        self.color_values[key] = chosen
        button = self._color_buttons.get(key)
        if button is not None:
            self._style_color_option_button(button, chosen)
        self.colorsChanged.emit(dict(self.color_values))
        self._build_tabs()

    def _scroll_style(self):
        """Modern, theme-aware scrollbar matching the rest of Onigiri's dialogs."""
        return f"""
            QScrollArea {{ border: none; background: transparent; }}
            QWidget {{ background: transparent; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; margin: 4px 2px 4px 0; }}
            QScrollBar::handle:vertical {{ background: {self._border}; border-radius: 4px; min-height: 24px; }}
            QScrollBar::handle:vertical:hover {{ background: {self._muted}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
            QScrollBar:horizontal {{ height: 0; }}
        """

    def _icons_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(self._scroll_style())
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(2, 2, 2, 12)
        content_layout.setSpacing(10)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        def add_group(title, items, filter_text=""):
            visible = [
                item for item in items
                if not filter_text or f"{item.get('label', '')} {item.get('name', '')}".lower().find(filter_text) >= 0
            ]
            if not visible:
                return
            label = QLabel(title)
            label.setStyleSheet(f"background: transparent; color: {self._muted}; font-size: 11px; font-weight: 700; text-transform: uppercase;")
            content_layout.addWidget(label)
            group = QWidget()
            flow = FlowLayout(group, margin=0, spacing=8)
            for item in visible:
                flow.addWidget(self._icon_cell(item, image_mode=False))
            content_layout.addWidget(group)

        user_items = [{"is_add_button": True}] + self._custom_items((".svg",))
        system_items = self._system_icon_items()

        def render():
            while content_layout.count():
                item = content_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            user_title = f"User Icons <span style='font-weight: 400; text-transform: none; font-size: 10px; color: {self._muted}; margin-left: 6px;'>{tr('hold_to_delete')}</span>"
            add_group(user_title, user_items, "")
            add_group("System Icons", system_items, "")
            content_layout.addStretch()

        render()
        return tab

    def _grid_tab(self, items, image_mode=False):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)
        search = QLineEdit()
        search.setPlaceholderText("Search images" if image_mode else "Search icons")
        search.setFixedHeight(38)
        search.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        search.setStyleSheet(f"QLineEdit {{ background-color: {self._surface}; border: 1px solid {self._border}; border-radius: 19px; color: {self._fg}; padding: 0 14px; }} QLineEdit:focus {{ border: 1px solid #00A982; }}")
        layout.addWidget(search)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(self._scroll_style())
        content = QWidget()
        flow = FlowLayout(content, margin=2, spacing=8)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        def render(filter_text=""):
            while flow.count():
                item = flow.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            for item in items:
                haystack = f"{item.get('label', '')} {item.get('name', '')}".lower()
                if filter_text and filter_text not in haystack:
                    continue
                flow.addWidget(self._icon_cell(item, image_mode=image_mode))

        search.textChanged.connect(lambda text: render(text.strip().lower()))
        render()
        return tab

    def _emoji_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(self._scroll_style())
        content = QWidget()
        flow = FlowLayout(content, margin=2, spacing=8)
        for emoji in self.EMOJIS:
            flow.addWidget(self._emoji_cell(emoji))
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        layout.addWidget(self._custom_emoji_row())
        return tab

    def _upload_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)
        for label, extensions in (("Upload SVG icon", "*.svg"), ("Upload PNG image", "*.png")):
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(56)
            btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {self._fg}; border: 1px dashed {self._border}; border-radius: 14px; text-align: left; padding-left: 16px; }} QPushButton:hover {{ border-color: {self._fg}; }}")
            btn.clicked.connect(lambda _, ext=extensions: self._upload_files(ext))
            layout.addWidget(btn)
        layout.addStretch()
        return tab

    def _cell_style(self, selected):
        icon_color = self._gallery_icon_color()
        if type(icon_color) is QColor:
            icon_color = icon_color.name()
        c = QColor(icon_color)
        bg = f"rgba({c.red()}, {c.green()}, {c.blue()}, 0.16)" if selected else self._surface
        border = icon_color if selected else self._border
        return f"QFrame {{ background: {bg}; border: 1px solid {border}; border-radius: 14px; }} QFrame:hover {{ border-color: {icon_color}; }}"

    def _select_pending_icon(self, value, cell):
        previous = self.current_icon
        self.current_icon = value
        cell.setStyleSheet(self._cell_style(True))
        if previous != value:
            old_cell = self._cell_widgets.get(previous)
            if old_cell is not None:
                try:
                    if sip is None or not sip.isdeleted(old_cell):
                        old_cell.setStyleSheet(self._cell_style(False))
                except Exception:
                    pass
        self._cell_widgets[value] = cell

    def _emoji_cell(self, emoji):
        value = f"emoji:{emoji['value']}"
        cell = QFrame()
        cell.setFixedSize(60, 60)
        cell.setToolTip(emoji.get("label", emoji["value"]))
        cell.setStyleSheet(self._cell_style(value == self.current_icon))
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(6, 6, 6, 6)
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("background: transparent; border: none;")
        svg_path = self._emoji_svg_path(emoji.get("asset", ""))
        if os.path.exists(svg_path):
            self._render_emoji_svg_to_label(svg_path, label)
        else:
            label.setText(emoji["value"])
            label.setStyleSheet("background: transparent; border: none; font-size: 26px;")
        layout.addWidget(label)
        cell.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cell_widgets[value] = cell
        def select_emoji(event, v=value, c=cell):
            self._select_pending_icon(v, c)
            return None
        cell.mousePressEvent = select_emoji
        return cell

    def _custom_emoji_row(self):
        row = QFrame()
        row.setObjectName("CustomEmojiRow")
        row.setStyleSheet(f"""
            QFrame#CustomEmojiRow {{
                background: {self._surface};
                border: 1px solid {self._border};
                border-radius: 16px;
            }}
            QPushButton {{
                background: rgba(128, 128, 128, 0.12);
                color: {self._fg};
                border: 1px solid {self._border};
                border-radius: 14px;
                padding: 0 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                border-color: #00A982;
            }}
            QLineEdit {{
                background: transparent;
                color: {self._fg};
                border: 1px solid {self._border};
                border-radius: 14px;
                padding: 0 10px;
                font-size: 18px;
            }}
            QLineEdit:focus {{
                border-color: #00A982;
            }}
        """)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        button = QPushButton("Type your own:")
        button.setFixedHeight(34)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        custom_input = QLineEdit()
        custom_input.setFixedHeight(34)
        custom_input.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        preset_values = {f"emoji:{item['value']}" for item in self.EMOJIS}
        if self.current_icon.startswith("emoji:") and self.current_icon not in preset_values:
            custom_input.setText(self.current_icon[len("emoji:"):])

        def select_custom():
            emoji = custom_input.text().strip()
            if emoji:
                previous = self.current_icon
                self.current_icon = f"emoji:{emoji}"
                old_cell = self._cell_widgets.get(previous)
                if old_cell is not None:
                    try:
                        if sip is None or not sip.isdeleted(old_cell):
                            old_cell.setStyleSheet(self._cell_style(False))
                    except Exception:
                        pass

        button.clicked.connect(lambda: (custom_input.setFocus(), select_custom()))
        custom_input.textChanged.connect(lambda _: select_custom())
        custom_input.returnPressed.connect(select_custom)
        layout.addWidget(button)
        layout.addWidget(custom_input, 1)
        return row

    def _render_emoji_svg_to_label(self, filepath, label):
        try:
            renderer = QSvgRenderer(filepath)
            dpr = label.devicePixelRatioF() if hasattr(label, "devicePixelRatioF") else 1.0
            pixmap = QPixmap(int(40 * dpr), int(40 * dpr))
            pixmap.setDevicePixelRatio(dpr)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            renderer.render(painter, svg_contain_rect(renderer, 40))
            painter.end()
            label.setPixmap(pixmap)
        except Exception:
            label.setText("?")

    def _icon_cell(self, item, image_mode=False):
        icon_color = self._gallery_icon_color()
        if type(icon_color) is QColor:
            icon_color = icon_color.name()

        if item.get("is_add_button"):
            cell = QFrame()
            cell.setFixedSize(60, 60)
            cell.setCursor(Qt.CursorShape.PointingHandCursor)
            bg = self._surface
            border = self._border
            cell.setStyleSheet(f"QFrame {{ background: rgba(128, 128, 128, 0.05); border: 1px solid {border}; border-radius: 14px; }} QFrame:hover {{ border-color: {icon_color}; background: rgba(128, 128, 128, 0.1); }}")
            layout = QVBoxLayout(cell)
            layout.setContentsMargins(6, 6, 6, 6)
            preview = QLabel()
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview.setStyleSheet("background: transparent; border: none;")
            self._render_svg_to_label(system_icon_path("unavailable_for_users/add.svg"), preview)
            layout.addWidget(preview)
            
            def on_add(event):
                self._upload_files(["*.svg"])
                return None
            cell.mousePressEvent = on_add
            return cell

        preview = QLabel()
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setStyleSheet("background: transparent; border: none;")

        is_custom = item.get("system") is False
        if is_custom:
            def on_delete(v):
                self._delete_custom_icon(v)
            cell = LongPressIconCell(item["name"], self._select_pending_icon, on_delete, preview, bg_color=self._surface, fill_color=icon_color)
        else:
            cell = QFrame()
            def select_icon(event, v=item["name"], c=cell):
                self._select_pending_icon(v, c)
                return None
            cell.mousePressEvent = select_icon

        cell.setFixedSize(60, 60)
        cell.setStyleSheet(self._cell_style(item["name"] == self.current_icon))
        layout = QVBoxLayout(cell)
        layout.setContentsMargins(6, 6, 6, 6)
        if image_mode:
            pixmap = QPixmap(item["path"])
            if not pixmap.isNull():
                dpr = preview.devicePixelRatioF() if hasattr(preview, "devicePixelRatioF") else 1.0
                scaled = pixmap.scaled(
                    int(34 * dpr), int(34 * dpr),
                    Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                scaled.setDevicePixelRatio(dpr)
                preview.setPixmap(scaled)
        else:
            self._render_svg_to_label(item["path"], preview)
        layout.addWidget(preview)
        if not is_custom:
            cell.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cell_widgets[item["name"]] = cell
        return cell

    def _render_svg_to_icon(self, filepath, color, size=16):
        if not filepath or not os.path.exists(filepath):
            return QIcon()
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                svg_xml = f.read()
            if "currentColor" in svg_xml:
                svg_xml = svg_xml.replace("currentColor", color)
            renderer = QSvgRenderer(svg_xml.encode("utf-8"))
            dpr = self.devicePixelRatioF() if hasattr(self, "devicePixelRatioF") else 1.0
            pixmap = QPixmap(int(size * dpr), int(size * dpr))
            pixmap.setDevicePixelRatio(dpr)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            renderer.render(painter, svg_contain_rect(renderer, size))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(QRectF(0, 0, size, size), QColor(color))
            painter.end()
            return QIcon(pixmap)
        except Exception:
            return QIcon()

    def _render_svg_to_label(self, filepath, label):
        color = self._gallery_icon_color()
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                svg_xml = f.read()
            if "currentColor" in svg_xml:
                svg_xml = svg_xml.replace("currentColor", color)
            renderer = QSvgRenderer(svg_xml.encode("utf-8"))
            dpr = label.devicePixelRatioF() if hasattr(label, "devicePixelRatioF") else 1.0
            pixmap = QPixmap(int(34 * dpr), int(34 * dpr))
            pixmap.setDevicePixelRatio(dpr)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            renderer.render(painter, svg_contain_rect(renderer, 34))
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
            painter.fillRect(QRectF(0, 0, 34, 34), QColor(color))
            painter.end()
            label.setPixmap(pixmap)
        except Exception:
            label.setText("?")

    def _upload_files(self, extension):
        title = "Select PNG images" if extension == "*.png" else "Select SVG icons"
        pattern = "PNG Images (*.png)" if extension == "*.png" else "SVG Icons (*.svg)"
        files, _ = QFileDialog.getOpenFileNames(self, title, "", pattern)
        if not files:
            return
        dest_dir = self._custom_icon_dir()
        for path in files:
            if not os.path.isfile(path):
                continue
            base, ext = os.path.splitext(os.path.basename(path))
            dest = os.path.join(dest_dir, base + ext)
            index = 2
            while os.path.exists(dest):
                dest = os.path.join(dest_dir, f"{base}-{index}{ext}")
                index += 1
            try:
                shutil.copy2(path, dest)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not copy icon: {e}")
        self._build_tabs()
