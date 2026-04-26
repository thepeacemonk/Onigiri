class InfrastructureMixin:
    def _create_image_gallery_group(self, key, folder, config_key, extensions=(".png", ".jpg", ".jpeg", ".gif", ".webp"), show_path=True, is_sub_group=False, title="", image_files_cache=None):
        group_container = QWidget()
        layout = QVBoxLayout(group_container)
        layout.setContentsMargins(0, 0 if is_sub_group else 10, 0, 0)
        
        if title: layout.addWidget(QLabel(title))

        scroll_area, grid_layout = self._create_gallery_ui()
        layout.addWidget(scroll_area)
        
        button_row = QHBoxLayout()
        choose_button = QPushButton("Choose Image..." if show_path else "Add Icon..."); choose_button.clicked.connect(lambda: self._choose_file_for_gallery(key)); button_row.addWidget(choose_button)
        delete_button = QPushButton("Delete Selected"); delete_button.clicked.connect(lambda: self._delete_from_gallery(key)); button_row.addWidget(delete_button)
        
        path_input = QLineEdit(); path_input.setPlaceholderText("No item selected"); path_input.setReadOnly(True)
        if show_path:
            layout.addWidget(QLabel("Selected File:")); layout.addWidget(path_input)

        # Determine which config source to use based on the config key pattern
        if config_key and (
            config_key.startswith("onigiri_reviewer_bg_image")
            or config_key.startswith("onigiri_overview_bg_image")
        ):
            # Reviewer and overview background images are stored in the addon config
            selected_image = self.current_config.get(config_key, "")
        elif config_key:
            # Other images are stored in Anki's collection config
            selected_image = mw.col.conf.get(config_key, "")
        else:
            # Fallback for cases where config_key is empty
            selected_image = ""

        gallery_data = {
            'selected': selected_image,
            'folder': folder, 'extensions': extensions,
            'grid_layout': grid_layout, 'labels': [], 'thread': None, 'worker': None,
            'path_input': path_input if show_path else None, 'delete_button': delete_button
        }
        self.galleries[key].update(gallery_data)

        # Defer gallery population to avoid blocking UI
        self._defer_gallery_population(key)
        
        layout.addLayout(button_row)
        self._update_delete_button_state(key)
        return group_container

    def _create_gallery_ui(self):
        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True); scroll_area.setFixedHeight(140)
        content_widget = QWidget(); grid_layout = QGridLayout(content_widget)
        grid_layout.setSpacing(10); grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll_area.setWidget(content_widget)
        return scroll_area, grid_layout

    def _defer_gallery_population(self, key):
        """Populate gallery after a short delay to avoid blocking UI"""
        QTimer.singleShot(100, lambda: self._populate_gallery_if_exists(key))
    
    def _populate_gallery_if_exists(self, key):
        """Populate gallery if it exists in the galleries dict"""
        if key in self.galleries:
            self._populate_gallery_placeholders(key)

    def _on_thumbnail_ready(self, key, index, pixmap, filename):
        gallery = self.galleries.get(key)
        if not gallery or index >= len(gallery['labels']): return
        
        label = gallery['labels'][index]
        label.setPixmap(pixmap)
        label.setToolTip(filename)
        label.setProperty("image_filename", filename)
        
        # Clear placeholder style
        label.setStyleSheet("background: transparent;")

        if 'overlays' not in gallery and gallery['selected'] == filename:
            label.setStyleSheet(THUMBNAIL_STYLE_SELECTED)

    def _populate_gallery_placeholders(self, key, image_files_cache=None):
        gallery = self.galleries[key]
        full_folder_path = os.path.join(self.addon_path, gallery['folder'])
        os.makedirs(full_folder_path, exist_ok=True)
        
        if image_files_cache is not None:
            image_files = image_files_cache
        else:
            try:
                image_files = sorted([f for f in os.listdir(full_folder_path) if f.lower().endswith(gallery['extensions'])])
            except OSError: image_files = []

        if not image_files:
            no_files_label = QLabel("No files here")
            no_files_label.setFixedSize(100, 100)
            no_files_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            bg = "rgba(255, 255, 255, 0.05)" if theme_manager.night_mode else "rgba(0, 0, 0, 0.05)"
            color = "#aaaaaa" if theme_manager.night_mode else "#666666"
            
            no_files_label.setStyleSheet(f"""
                background-color: {bg};
                border-radius: 10px;
                color: {color};
                font-size: 12px;
            """)
            gallery['grid_layout'].addWidget(no_files_label, 0, 0)
            return

        gallery['overlays'] = []
        
        # Determine sizes based on key
        if key == 'profile_pic':
            item_width, item_height = 110, 110
            img_width, img_height = 100, 100
            shape = 'circular'
        else: # profile_bg and others
            item_width, item_height = 120, 75
            img_width, img_height = 100, 55
            shape = 'rounded'

        for i, filename in enumerate(image_files):
            # Container
            container = QWidget()
            container.setFixedSize(item_width, item_height)
            container.setCursor(Qt.CursorShape.PointingHandCursor)
            
            # Image Label
            img_label = QLabel(container)
            img_label.setFixedSize(img_width, img_height)
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            # Center the image in the container
            img_label.move((item_width - img_width) // 2, (item_height - img_height) // 2)
            
            # Placeholder content
            img_label.setText("⏳")
            img_label.setStyleSheet("background-color: rgba(128,128,128,0.1); border-radius: 10px;")

            # Selection Overlay
            overlay = SelectionOverlay(container, accent_color=self.accent_color)
            is_selected = (filename == gallery['selected'])
            overlay.setChecked(is_selected)
            
            # Position overlay (Top Right)
            overlay.move(item_width - 30, 5)
            overlay.setProperty("image_filename", filename)

            # Install event filter on container
            container.setProperty("gallery_key", key)
            container.setProperty("image_filename", filename)
            container.installEventFilter(self)

            gallery['grid_layout'].addWidget(container, i // 4, i % 4)
            gallery['labels'].append(img_label)
            gallery['overlays'].append(overlay)
        
        thread = QThread(); worker = ThumbnailWorker(key, full_folder_path, image_files, shape=shape)
        worker.moveToThread(thread)
        worker.thumbnail_ready.connect(self._on_thumbnail_ready)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        
        gallery['thread'] = thread
        gallery['worker'] = worker

    def eventFilter(self, source, event):
        # Disabled dynamic resize for shape gallery - using fixed horizontal layout instead
        # if hasattr(self, 'shape_scroll_content') and source is self.shape_scroll_content and event.type() == QEvent.Type.Resize:
        #     try:
        #         self._reflow_shape_icons(event.size().width())
        #     except Exception as e:
        #         # Silently handle any reflow errors to prevent crashes
        #         print(f"Warning: Shape reflow error: {e}")
        #     return False

        if event.type() == QEvent.Type.MouseButtonPress:
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
                            gallery['path_input'].setPlaceholderText("No item selected")
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
                    return True

            if source.property("icon_key"):
                self._change_icon(source)
                return True

        if source.property("text_stack"):
            text_stack = source.property("text_stack")
            hex_widget = text_stack.widget(1)

            if event.type() == QEvent.Type.Enter:
                text_stack.setCurrentIndex(1)
            elif event.type() == QEvent.Type.Leave:
                if not (hex_widget and hex_widget.hasFocus()):
                    text_stack.setCurrentIndex(0)
            return True
            
        return super().eventFilter(self, event)

    def _choose_file_for_gallery(self, key):
        gallery = self.galleries[key]
        ext_filter = f"Files (*{' *'.join(gallery['extensions'])})"; filepath, _ = QFileDialog.getOpenFileName(self, "Select File", "", ext_filter)
        if not filepath: return
        
        filename = os.path.basename(filepath)
        dest_path = os.path.join(self.addon_path, gallery['folder'], filename)
        
        try:
            shutil.copy(filepath, dest_path)
            self._refresh_gallery(key)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not copy file: {e}")

    def _delete_from_gallery(self, key):
        gallery = self.galleries[key]
        filename = gallery['selected']
        if not filename: return
        
        reply = QMessageBox.question(self, "Confirm Delete", f"Are you sure you want to permanently delete '{filename}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            filepath = os.path.join(self.addon_path, gallery['folder'], filename)
            try:
                os.remove(filepath)
                gallery['selected'] = ""
                if gallery.get('path_input'): gallery['path_input'].clear()
                self._refresh_gallery(key)
            except OSError as e:
                QMessageBox.warning(self, "Error", f"Could not delete file: {e}")

    def _refresh_gallery(self, key):
        gallery = self.galleries[key]

        try:
            if gallery.get('thread') and gallery['thread'].isRunning():
                gallery['worker'].cancel()
                gallery['thread'].quit()
                gallery['thread'].wait()
        except RuntimeError:
            pass
        
        # Clear all items from the grid layout
        layout = gallery['grid_layout']
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        gallery['labels'] = []
        if 'overlays' in gallery:
            gallery['overlays'] = []
            
        self._populate_gallery_placeholders(key)
        self._update_delete_button_state(key)

    def _update_delete_button_state(self, key):
        gallery = self.galleries[key]
        if delete_button := gallery.get('delete_button'):
            delete_button.setEnabled(bool(gallery['selected']))

    def _create_icon_control_widget(self, key, display_name=None, config_key_prefix="modern_menu_icon_"):
        # Modern Card-like widget for icon control
        control_widget = QWidget()
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

        control_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QWidget:hover {{
                background-color: {hover_color};
                border-color: {text_color};
            }}
        """)
        
        layout = QHBoxLayout(control_widget)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)
        
        # Icon Preview
        preview_label = QLabel()
        preview_label.setFixedSize(32, 32)
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_label.setStyleSheet("background: transparent; border: none;") # Reset style for label inside card
        
        # Info/Edit Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        name_label = QLabel(display_name or key.replace("_", " ").title())
        name_label.setStyleSheet(f"background: transparent; border: none; font-weight: bold; color: {text_color}; font-size: 13px;")
        
        sub_label = QLabel("Click to change")
        sub_label.setStyleSheet(f"background: transparent; border: none; color: {text_color}; opacity: 0.7; font-size: 10px;")
        
        text_layout.addWidget(name_label)
        text_layout.addWidget(sub_label)
        text_layout.addStretch()

        # Delete Button (Small trash icon or X)
        delete_btn = QPushButton()
        delete_btn.setFixedSize(24, 24)
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setToolTip("Reset to Default")
        
        trash_icon_path = os.path.join(os.path.dirname(__file__), "system_files", "system_icons", "xmark-simple.svg") # Using xmark-simple.svg as delete icon
        
        if theme_manager.night_mode:
             delete_btn.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 4px; } QPushButton:hover { background: rgba(255,0,0,0.2); }")
             trash_color = "#ff6b6b"
        else:
             delete_btn.setStyleSheet("QPushButton { background: transparent; border: none; border-radius: 4px; } QPushButton:hover { background: rgba(255,0,0,0.1); }")
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

        layout.addWidget(preview_label)
        layout.addLayout(text_layout)
        layout.addStretch()
        layout.addWidget(delete_btn)
        
        # Properties
        control_widget.setProperty("icon_key", key)
        control_widget.setProperty("config_key_prefix", config_key_prefix)
        control_widget.setProperty("icon_filename", mw.col.conf.get(f"{config_key_prefix}{key}", ""))
        control_widget.setProperty("preview_label", preview_label)
        control_widget.setProperty("sub_label", sub_label) # To update text if needed
        
        # Make the whole widget clickable
        # We can't connect signals to QWidget directly, so we install an eventFilter or perform a trick.
        # But QWidget doesn't have clicked signal. 
        # Easier: wrap content in a transparent QPushButton overlay or use mousePressEvent.
        # Here we will use event filter in Settings class for simplicity as in original gallery:
        control_widget.installEventFilter(self)
        
        self._update_icon_preview_for_widget(control_widget)
        return control_widget

    def _update_icon_preview_for_widget(self, widget, size=24):
        key = widget.property("icon_key"); filename = widget.property("icon_filename"); preview_label = widget.property("preview_label")
        icon_color = "#e0e0e0" if theme_manager.night_mode else "#212121"; svg_xml = ""
        if filename:
            filepath = os.path.join(self.addon_path, "user_files/icons", filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f: svg_xml = f.read()
        if not svg_xml:
            default_key = 'star' if key == 'retention_star' else key
            data_uri = ICON_DEFAULTS.get(default_key, ""); 
            if data_uri.startswith("data:image/svg+xml,"): encoded_svg = data_uri.split(",", 1)[1]; svg_xml = urllib.parse.unquote(encoded_svg)
            entry = sidebar_api.get_sidebar_entries().get(key) if not svg_xml else None
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
        if 'stroke="currentColor"' in svg_xml: colored_svg = svg_xml.replace('stroke="currentColor"', f'stroke="{icon_color}"')
        elif 'fill="currentColor"' in svg_xml: colored_svg = svg_xml.replace('fill="currentColor"', f'fill="{icon_color}"')
        else: colored_svg = svg_xml.replace('<svg', f'<svg fill="{icon_color}" stroke="{icon_color}"', 1)
        renderer = QSvgRenderer(colored_svg.encode('utf-8')); pixmap = QPixmap(renderer.defaultSize()); pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap); renderer.render(painter); painter.end()
        preview_label.setPixmap(pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def _change_icon(self, widget):
        if not widget: return
        
        current_filename = widget.property("icon_filename")
        
        picker = IconPickerDialog(current_filename, self.addon_path, self)
        
        def on_selected(filename):
            widget.setProperty("icon_filename", filename)
            self._update_icon_preview_for_widget(widget)
            
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
        
        # Center picker
        parent_geo = self.geometry()
        picker_geo = picker.geometry()
        x = parent_geo.x() + (parent_geo.width() - picker_geo.width()) // 2
        y = parent_geo.y() + (parent_geo.height() - picker_geo.height()) // 2
        picker.move(x, y)
        picker.exec()

    def _delete_icon(self, widget): widget.setProperty("icon_filename", ""); self._update_icon_preview_for_widget(widget)
    def reset_icons_to_default(self):
        for widget in self.icon_assignment_widgets: self._delete_icon(widget)
        for widget in self.action_button_icon_widgets: self._delete_icon(widget)
        if hasattr(self, "retention_star_widget") and self.retention_star_widget:
            self._delete_icon(self.retention_star_widget)

    def create_icon_size_spinbox(self,key,default_value): spinbox=QSpinBox();spinbox.setMinimum(8);spinbox.setMaximum(48);spinbox.setSuffix(" px");spinbox.setValue(mw.col.conf.get(f"modern_menu_icon_size_{key}",default_value));self.icon_size_widgets[key]=spinbox;return spinbox
    def reset_icon_sizes_to_default(self):[widget.setValue(DEFAULT_ICON_SIZES[key])for key,widget in self.icon_size_widgets.items()]

    def apply_stylesheet(self):
        conf = config.get_config()
        if theme_manager.night_mode:
            bg, fg, border, input_bg, button_bg, sidebar_bg = "#2c2c2c", "#e0e0e0", "#4a4a4a", "#3a3a3a", "#4a4a4a", "#3a3a3a"
            separator_color, secondary_button_bg, secondary_button_fg = "#444444", "#555", "#e0e0e0"
            accent_color = conf.get("colors", {}).get("dark", {}).get("--accent-color", DEFAULTS["colors"]["dark"]["--accent-color"])
        else:
            bg, fg, border, input_bg, button_bg, sidebar_bg = "#f3f3f3", "#212121", "#e0e0e0", "#f5f5f5", "#f0f0f0", "#dddddd"
            separator_color, secondary_button_bg, secondary_button_fg = "#e0e0e0", "#c9c9c9", "#ffffff"
            accent_color = conf.get("colors", {}).get("light", {}).get("--accent-color", DEFAULTS["colors"]["light"]["--accent-color"])

        mode_key = "dark" if theme_manager.night_mode else "light"
        fg_subtle = conf.get("colors", {}).get(mode_key, {}).get("--fg-subtle", DEFAULTS["colors"][mode_key]["--fg-subtle"])

        hero_gradient_top = "#343a40" if theme_manager.night_mode else "#d9dee7"
        sidebar_selected_bg, primary_button_bg = accent_color, accent_color

        # Icons for spinbox
        up_icon_path = os.path.join(self.addon_path, "system_files", "system_icons", "up.svg").replace("\\", "/")
        down_icon_path = os.path.join(self.addon_path, "system_files", "system_icons", "down.svg").replace("\\", "/")

        self.setStyleSheet(f"""
            QFrame#MenuSeparator {{
                background-color: {border};
            }}

            QDialog {{ background-color: {bg}; color: {fg}; }}
            
            /* This rule gives the page a solid background to prevent flickering */
            #pageContainer {{
                background-color: {bg};
            }}

            #sidebarContainer {{
                background-color: {sidebar_bg};
                border-radius: 25px;
            }}
            #sidebarContainer QPushButton {{
                padding: 12px;
                border-radius: 20px;
                text-align: left;
                border: none;
                background-color: transparent;
            }}
            #sidebarContainer QPushButton:checked {{
                background-color: {sidebar_selected_bg};
                color: white;
            }}
            QPushButton#searchSidebarButton {{
                padding: 12px;
                border-radius: 20px;
                background-color: {sidebar_bg};
                color: {fg};
                text-align: center;
                margin-bottom: 0px; /* Spacing handled by layout now */
                border: none;
            }}
            QPushButton#searchSidebarButton:hover {{
                background-color: {border}; /* Slightly lighter/darker on hover */
            }}
            QPushButton#searchSidebarButton:checked {{
                background-color: {sidebar_bg};
                color: {fg};
            }}
            QPushButton#searchSidebarButton:pressed {{
                color: {sidebar_selected_bg};
            }}
            #sidebarContainer QPushButton#subItemButton {{
                background-color: transparent;
                color: {fg};
            }}
            #sidebarContainer QPushButton#subItemButton:checked {{
                background-color: transparent;
                font-weight: bold;
                color: {sidebar_selected_bg};
            }}
            #innerGroup {{ border: 1px solid {border}; border-radius: 12px; margin-top: 5px; }}
            QGroupBox {{ border-radius: 16px; margin-top: 8px; padding: 0px; }}
            
            QLabel, QRadioButton {{ color: {fg}; }}
            QRadioButton::indicator {{
                border: 2px solid {border};
                background-color: transparent;
                width: 16px;
                height: 16px;
                border-radius: 10px;
            }}
            QRadioButton::indicator:checked {{
                border: 2px solid {accent_color};
                background-color: {accent_color};
                image: url();
            }}
            QLineEdit, QSpinBox {{ background-color: {input_bg}; color: {fg}; border: 1px solid {border}; border-radius: 4px; padding: 5px; }}

            QPushButton {{ background-color: {button_bg}; color: {fg}; border: 1px solid {border}; padding: 8px 12px; border-radius: 4px; }}
            QPushButton:pressed {{ background-color: {border}; }}
        
            QFrame[frameShape="4"] {{ border: 1px solid {separator_color}; }}
            QTabBar::tab {{ background: transparent; border: none; padding: 8px 12px; border-radius: 4px; margin-right: 2px; }}
            QTabBar::tab:selected {{ background: {accent_color}; color: white; }}
            QTabBar::tab:!selected:hover {{ background: {border}; }}
            QTabWidget::pane {{ background-color: transparent; border: none; }}
            QTabBar {{ qproperty-drawBase: 0; }}
            QScrollBar:vertical {{ border: none; background: {bg}; width: 12px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: {border}; min-height: 20px; border-radius: 6px; margin: 2px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                height: 0px;
                width: 0px;
                background: none;
                border: none;
            }}
            QScrollBar:horizontal {{ border: none; background: {bg}; height: 12px; margin: 0; }}
            QScrollBar::handle:horizontal {{ background: {border}; min-width: 20px; border-radius: 6px; margin: 2px; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                height: 0px;
                width: 0px;
                background: none;
                border: none;
            }}

            QSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 16px;
                border-left: 1px solid {border};
                image: url({up_icon_path});
                padding: 2px;
            }}
            QSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 16px;
                border-left: 1px solid {border};
                image: url({down_icon_path});
                padding: 2px;
            }}
            #colorPill {{ background-color: {input_bg}; border: 1px solid {border}; border-radius: 18px; 
            }}
            QFrame#themeCard {{
                background-color: {input_bg};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 10px;
            }}
            QFrame#themeCard:hover {{
                border-color: {accent_color};
            }}

            /* <<< START NEW CODE >>> */
            QFrame#hideModeCard {{
                background-color: {sidebar_bg};
                border: 1px solid {border};
                border-radius: 16px;
                padding: 20px;
            }}
            QLabel#hideModeTitleLabel {{
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 5px;
            }}
            QLabel#hideModeDescLabel {{
                color: {fg};
                font-size: 12px;
            }}
            /* <<< END NEW CODE >>> */

            /* <<< START NEW CODE >>> */

            QGroupBox#LayoutGroup {{
                border: 1px solid {border};
                border-radius: 8px;
                margin-top: 10px;
                padding: 15px 10px 10px 10px;
            }}
            QGroupBox#LayoutGroup::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                /* Use page BG to "cut out" the border */
                background-color: {bg};
                /* Make title visible again, overriding default */
                color: {fg};
            }}
            #DraggableItem {{
                background-color: {button_bg};
                border: 1px solid {border};
                border-radius: 4px;
                color: {fg};
                font-weight: 500;
                text-align: center;
            }}
            #DropZone {{
                background-color: {input_bg};
                border-radius: 6px;
                padding: 5px;
            }}
            #Shelf {{
                background-color: transparent;
                border: 2px dashed {border};
                border-radius: 10px;
            }}
            /* <<< START NEW CODE >>> */
            #Shelf[is_highlighted="true"] {{
                background-color: rgba(0, 123, 255, 0.3);
                border: 2px solid {accent_color};
            }}
            /* <<< START NEW CODE >>> */
            #MenuBackground {{
                background-color: {input_bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            QPushButton#MenuButton {{
                background-color: transparent;
                color: {fg};
                border: none;
                padding: 8px 20px;
                text-align: center;
                border-radius: 6px;
            }}
            QPushButton#MenuButton:hover {{
                background-color: {border};
            }}
            QPushButton#MenuButton:checked {{
                background-color: {accent_color};
                color: white;
            }}
                border: 1px solid {border};
                border-radius: 4px;
            }}
        """)
        self.save_button.setStyleSheet(
            f"QPushButton{{background-color:{accent_color};color:white;border:none;padding:10px;border-radius:12px}}"
            f"QPushButton:pressed{{background-color:{border};color:white}}"
        )
    
