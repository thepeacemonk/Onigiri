import os
import shutil
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QWidget, QColor, QCheckBox,
    QGridLayout, QPixmap, Qt, QPainter,
    QScrollArea, QFrame, QSizePolicy,
    QIcon, QFileDialog, QTabWidget,
    QButtonGroup, QRadioButton,
)
from PyQt6.QtCore import QSize
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import QImage

from aqt import mw
from aqt.theme import theme_manager


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
        title_label = QLabel("Select Icon")
        if theme_manager.night_mode:
            title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #e0e0e0;")
        else:
            title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #212121;")
            
        close_btn = QPushButton()
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        
        # Load xmark.svg
        xmark_path = os.path.join(os.path.dirname(__file__), "system_files", "system_icons", "xmark.svg")
        
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
        
        # --- Search & Add ---
        tools_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search icons...")
        self.search_input.textChanged.connect(self._filter_icons)
        if theme_manager.night_mode:
            self.search_input.setStyleSheet("QLineEdit { background-color: #3a3a3a; border: 1px solid #555; border-radius: 6px; padding: 4px; color: #e0e0e0; } QLineEdit:focus { border-color: #777; }")
        else:
            self.search_input.setStyleSheet("QLineEdit { background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 6px; padding: 4px; color: #212121; } QLineEdit:focus { border-color: #aaa; }")
            
        add_btn = QPushButton("Add Icon")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._add_icon_from_file)
        if theme_manager.night_mode:
            add_btn.setStyleSheet("QPushButton { background-color: #3a3a3a; border: 1px solid #555; border-radius: 6px; padding: 4px 10px; color: #e0e0e0; } QPushButton:hover { background-color: #4a4a4a; }")
        else:
            add_btn.setStyleSheet("QPushButton { background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 6px; padding: 4px 10px; color: #212121; } QPushButton:hover { background-color: #e0e0e0; }")
            
        tools_layout.addWidget(self.search_input)
        tools_layout.addWidget(add_btn)

        # Use Default Button
        default_btn = QPushButton("Use Default")
        default_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        default_btn.clicked.connect(lambda: (self.iconSelected.emit(""), self.close()))
        if theme_manager.night_mode:
            default_btn.setStyleSheet("QPushButton { background-color: transparent; border: 1px solid #555; border-radius: 6px; padding: 4px 10px; color: #e0e0e0; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.05); }")
        else:
            default_btn.setStyleSheet("QPushButton { background-color: transparent; border: 1px solid #ccc; border-radius: 6px; padding: 4px 10px; color: #212121; } QPushButton:hover { background-color: rgba(0, 0, 0, 0.02); }")
        
        tools_layout.addWidget(default_btn)
        container_layout.addLayout(tools_layout)
        
        # --- Icon Grid ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; } QWidget { background: transparent; }")
        
        self.grid_content = QWidget()
        self.grid_layout = QGridLayout(self.grid_content)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        scroll_area.setWidget(self.grid_content)
        container_layout.addWidget(scroll_area)
        
        self.icons = [] # List of (filename, widget)
        self._load_icons()
        
        layout.addWidget(self.container)

    def _render_svg_to_icon(self, filepath, button, color_hex):
        try:
            with open(filepath, 'r', encoding='utf-8') as f: svg_xml = f.read()
            if 'stroke="currentColor"' in svg_xml: colored_svg = svg_xml.replace('stroke="currentColor"', f'stroke="{color_hex}"')
            elif 'fill="currentColor"' in svg_xml: colored_svg = svg_xml.replace('fill="currentColor"', f'fill="{color_hex}"')
            else: colored_svg = svg_xml.replace('<svg', f'<svg fill="{color_hex}" stroke="{color_hex}"', 1)
            
            renderer = QSvgRenderer(colored_svg.encode('utf-8'))
            pixmap = QPixmap(renderer.defaultSize())
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            
            # Simple scaling if needed, but for icon button usually best to let QIcon handle or pre-scale
            scaled = pixmap.scaled(12, 12, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            button.setIcon(QIcon(scaled))
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
                    border-radius: 8px;
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
            del_btn.setToolTip("Delete Icon")
            del_btn.move(45, 5) # Position top-right
            
            # Load xmark icon
            xmark_path = os.path.join(os.path.dirname(__file__), "system_files", "system_icons", "xmark.svg")
            
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
            if 'stroke="currentColor"' in svg_xml: colored_svg = svg_xml.replace('stroke="currentColor"', f'stroke="{color}"')
            elif 'fill="currentColor"' in svg_xml: colored_svg = svg_xml.replace('fill="currentColor"', f'fill="{color}"')
            else: colored_svg = svg_xml.replace('<svg', f'<svg fill="{color}" stroke="{color}"', 1)
            
            renderer = QSvgRenderer(colored_svg.encode('utf-8'))
            pixmap = QPixmap(renderer.defaultSize())
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            label.setPixmap(pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
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
            
            container.setStyleSheet(f"QWidget {{ background-color: {bg_selected if is_selected else bg_normal}; border-radius: 8px; border: {('1px solid ' + border_selected) if is_selected else '1px solid transparent'}; }} QWidget:hover {{ background-color: {bg_hover}; border: 1px solid {border_selected}; }}")
            
            layout = QVBoxLayout(container); layout.setContentsMargins(5, 5, 5, 5)
            preview = QLabel(); preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._render_svg_to_label(os.path.join(icons_dir, filename), preview)
            layout.addWidget(preview)
            
            btn = QPushButton(container)
            btn.setStyleSheet("background: transparent; border: none;")
            btn.setFixedSize(70, 70); btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, f=filename: self._select_icon(f))
            btn.move(0, 0)
            
            self.grid_layout.addWidget(container, row, col)
            col += 1
            if col >= num_cols: col = 0; row += 1

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

