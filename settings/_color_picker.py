import os
from aqt.qt import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QWidget, QColor, QColorDialog,
    QGridLayout, QPixmap, Qt, QPainter, QPainterPath,
    QFrame, QSizePolicy,
    QMenu, QAction,
    QPoint,
)
from PyQt6.QtCore import pyqtSignal, QSize, QTimer, QPointF
from PyQt6.QtGui import QLinearGradient, QMouseEvent, QGuiApplication, QCursor, QImage

from aqt import mw


class ColorMapWidget(QWidget):
    colorChanged = pyqtSignal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 150)
        self._hue = 0.0
        self._sat = 0.0
        self._val = 0.0
        self._cursor_pos = QPoint(0, 0)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def setHue(self, hue):
        self._hue = hue
        self.update()
        self._emit_color()

    def setColor(self, color):
        self._hue = color.hueF()
        self._sat = color.saturationF()
        self._val = color.valueF()
        if self._hue == -1: self._hue = 0
        self._update_cursor_from_color()
        self.update()

    def _update_cursor_from_color(self):
        x = int(self._sat * self.width())
        y = int((1 - self._val) * self.height())
        self._cursor_pos = QPoint(x, y)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._hue == -1: hue_color = QColor(255, 255, 255)
        else: hue_color = QColor.fromHsvF(max(0, self._hue), 1.0, 1.0)
        
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 12, 12)
        painter.setClipPath(path)
        
        painter.setBrush(hue_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)

        sat_grad = QLinearGradient(0, 0, self.width(), 0)
        sat_grad.setColorAt(0, QColor(255, 255, 255, 255))
        sat_grad.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(self.rect(), sat_grad)

        val_grad = QLinearGradient(0, 0, 0, self.height())
        val_grad.setColorAt(0, QColor(0, 0, 0, 0))
        val_grad.setColorAt(1, QColor(0, 0, 0, 255))
        painter.fillRect(self.rect(), val_grad)


        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(self._cursor_pos, 6, 6)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawEllipse(self._cursor_pos, 6, 6)

    def mousePressEvent(self, event):
        self._update_color(event.pos())

    def mouseMoveEvent(self, event):
        self._update_color(event.pos())

    def _update_color(self, pos):
        x = max(0, min(pos.x(), self.width()))
        y = max(0, min(pos.y(), self.height()))
        self._cursor_pos = QPoint(x, y)
        
        self._sat = x / self.width()
        self._val = 1.0 - (y / self.height())
        
        self._emit_color()
        self.update()

    def _emit_color(self):
        color = QColor.fromHsvF(max(0, self._hue), self._sat, self._val)
        self.colorChanged.emit(color)

class GradientSlider(QWidget):
    valueChanged = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(280, 12)
        self._value = 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setValue(self, value):
        self._value = max(0.0, min(1.0, value))
        self.update()

    def mousePressEvent(self, event):
        self._update_value(event.pos())

    def mouseMoveEvent(self, event):
        self._update_value(event.pos())

    def _update_value(self, pos):
        val = pos.x() / self.width()
        self._value = max(0.0, min(1.0, val))
        self.valueChanged.emit(self._value)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.draw_track(painter)
        thumb_x = int(self._value * self.width())
        thumb_x = max(6, min(thumb_x, self.width() - 6))
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.setBrush(Qt.GlobalColor.transparent)
        painter.drawEllipse(QPoint(thumb_x, self.height() // 2), 5, 5)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.drawEllipse(QPoint(thumb_x, self.height() // 2), 5, 5)

    def draw_track(self, painter):
        pass

class HueSlider(GradientSlider):
    def draw_track(self, painter):
        grad = QLinearGradient(0, 0, self.width(), 0)
        for i in range(7):
            grad.setColorAt(i / 6.0, QColor.fromHsvF(i / 6.0, 1.0, 1.0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 6, 6)

class AlphaSlider(GradientSlider):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self._color = QColor(255, 0, 0)

    def setColor(self, color):
        self._color = color
        self.update()

    def draw_track(self, painter):
        painter.save()
        painter.setClipRect(self.rect())
        check_size = 4
        for y in range(0, self.height(), check_size):
            for x in range(0, self.width(), check_size):
                if (x // check_size + y // check_size) % 2 == 0:
                    painter.fillRect(x, y, check_size, check_size, QColor(200, 200, 200))
                else:
                    painter.fillRect(x, y, check_size, check_size, QColor(255, 255, 255))
        painter.restore()
        grad = QLinearGradient(0, 0, self.width(), 0)
        c1 = QColor(self._color); c1.setAlpha(0)
        c2 = QColor(self._color); c2.setAlpha(255)
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 6, 6)

class FavoriteColorButton(QWidget):
    def __init__(self, color_hex, on_select, on_remove, parent=None):
        super().__init__(parent)
        self.setFixedSize(24, 24)
        self.color_hex = color_hex
        self.on_select = on_select
        self.on_remove = on_remove
        
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Long click to delete")
        
        self._long_press_timer = QTimer(self)
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.setInterval(800) 
        self._long_press_timer.timeout.connect(self._handle_long_press)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(self.color_hex))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 12, 12)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._long_press_timer.start()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._long_press_timer.isActive():
                self._long_press_timer.stop()
                self.on_select(self.color_hex)

    def _handle_long_press(self):
        self.on_remove(self.color_hex)





class ModernColorPickerDialog(QDialog):
    colorSelected = pyqtSignal(QColor)

    def __init__(self, initial_color=QColor("white"), parent=None, favorite_colors=None):
        super().__init__(parent)
        self.setWindowTitle("Select Color")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._color = QColor(initial_color)
        self.favorite_colors = favorite_colors[:] if favorite_colors else []
        self._drag_pos = None

        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        self.container = QFrame()
        self.container.setObjectName("ColorPickerContainer")
        if theme_manager.night_mode:
             self.container.setStyleSheet("QFrame#ColorPickerContainer { background-color: #2c2c2c; border-radius: 12px; border: 1px solid #4a4a4a; }")
        else:
             self.container.setStyleSheet("QFrame#ColorPickerContainer { background-color: #ffffff; border-radius: 12px; border: 1px solid #e0e0e0; }")

        container_layout = QVBoxLayout(self.container)
        container_layout.setSpacing(15)
        
        # --- Header with Close Button ---
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("Select Color")
        
        close_btn = QPushButton()
        close_btn.setFixedSize(24, 24)
        close_btn.setMaximumSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        
        icon_path = os.path.join(os.path.dirname(__file__), "system_files", "system_icons", "xmark-simple.svg")
        
        # Style the close button and title to be adapted to the theme
        if theme_manager.night_mode:
            title_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #d0d0d0;")
            close_btn.setStyleSheet("""
                QPushButton { 
                    background-color: transparent; 
                    border: none; 
                    border-radius: 12px; 
                    padding: 0px;
                    margin: 0px;
                    min-width: 24px; 
                    min-height: 24px;
                    max-width: 24px;
                    max-height: 24px;
                }
                QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }
            """)
            icon_color = QColor("#ffffff")
        else:
            title_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #333333;")
            close_btn.setStyleSheet("""
                QPushButton { 
                    background-color: transparent; 
                    border: none; 
                    border-radius: 12px; 
                    padding: 0px;
                    margin: 0px;
                    min-width: 24px; 
                    min-height: 24px;
                    max-width: 24px;
                    max-height: 24px;
                }
                QPushButton:hover { background-color: rgba(0, 0, 0, 0.05); }
            """)
            icon_color = QColor("#555555")

            
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            if not pixmap.isNull():
                # Colorize the icon
                painter = QPainter(pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), icon_color)
                painter.end()
                
                close_btn.setIcon(QIcon(pixmap))
                close_btn.setIconSize(QSize(12, 12))
            else:
                close_btn.setText("x")
                close_btn.setStyleSheet(close_btn.styleSheet() + f"color: {icon_color.name()}; font-weight: bold; font-size: 16px; font-family: Arial, sans-serif; padding-bottom: 2px;")
        else:
            close_btn.setText("x")
            close_btn.setStyleSheet(close_btn.styleSheet() + f"color: {icon_color.name()}; font-weight: bold; font-size: 16px; font-family: Arial, sans-serif; padding-bottom: 2px;")
            
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(close_btn)
        container_layout.addLayout(header_layout)
        # --------------------------------
        
        self.color_map = ColorMapWidget()
        self.color_map.colorChanged.connect(self._on_map_color_changed)
        container_layout.addWidget(self.color_map, 0, Qt.AlignmentFlag.AlignCenter)
        
        sliders_layout = QVBoxLayout()
        sliders_layout.setSpacing(8)
        self.hue_slider = HueSlider()
        self.hue_slider.valueChanged.connect(self._on_hue_changed)
        sliders_layout.addWidget(self.hue_slider, 0, Qt.AlignmentFlag.AlignCenter)
        # Alpha slider removed
        container_layout.addLayout(sliders_layout)
        
        input_layout = QHBoxLayout()
        self.preview_circle = QLabel()
        self.preview_circle.setFixedSize(32, 32)
        
        self.hex_input = QLineEdit(self._color.name())
        self.hex_input.setFixedWidth(100)
        self.hex_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if theme_manager.night_mode:
            self.hex_input.setStyleSheet("QLineEdit { background-color: #333; color: #fff; border: 1px solid #555; border-radius: 12px; padding: 4px; }")
        else:
            self.hex_input.setStyleSheet("QLineEdit { background-color: #fff; color: #000; border: 1px solid #ccc; border-radius: 12px; padding: 4px; }")
        self.hex_input.textChanged.connect(self._on_hex_changed)

        
        input_layout.addWidget(self.preview_circle)
        input_layout.addWidget(self.hex_input)
        input_layout.addStretch()
        container_layout.addLayout(input_layout)
        
        # --- Favorites Section ---
        fav_header = QHBoxLayout()
        fav_label = QLabel("Favorite Colors")
        if theme_manager.night_mode:
            fav_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #888;")
        else:
            fav_label.setStyleSheet("font-weight: bold; font-size: 11px; color: #666;")
            
        add_fav_btn = QPushButton()
        add_fav_btn.setFixedSize(24, 24)
        add_fav_btn.setMaximumSize(24, 24)
        add_fav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_fav_btn.setToolTip("Add current color to favorites")
        add_fav_btn.clicked.connect(self.add_current_to_favorites)
        
        add_icon_path = os.path.join(os.path.dirname(__file__), "system_files", "system_icons", "add.svg")
        
        if theme_manager.night_mode:
            add_fav_btn.setStyleSheet("""
                QPushButton { 
                    background-color: #3a3a3a; 
                    border: 1px solid #555; 
                    border-radius: 12px; 
                    padding: 0px;
                    margin: 0px;
                    min-width: 24px; 
                    min-height: 24px;
                    max-width: 24px;
                    max-height: 24px;
                }
                QPushButton:hover { background-color: #4a4a4a; }
            """)
            add_icon_color = QColor("#cccccc")
        else:
            add_fav_btn.setStyleSheet("""
                QPushButton { 
                    background-color: #f0f0f0; 
                    border: 1px solid #ccc; 
                    border-radius: 12px; 
                    padding: 0px;
                    margin: 0px;
                    min-width: 24px; 
                    min-height: 24px;
                    max-width: 24px;
                    max-height: 24px;
                }
                QPushButton:hover { background-color: #e0e0e0; }
            """)
            add_icon_color = QColor("#555555")

            
        if os.path.exists(add_icon_path):
            pixmap = QPixmap(add_icon_path)
            if not pixmap.isNull():
                painter = QPainter(pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), add_icon_color)
                painter.end()
                add_fav_btn.setIcon(QIcon(pixmap))
                add_fav_btn.setIconSize(QSize(12, 12))
            else:
                add_fav_btn.setText("+")
        else:
            add_fav_btn.setText("+")
            
        fav_header.addWidget(fav_label)
        fav_header.addStretch()
        fav_header.addWidget(add_fav_btn)
        container_layout.addLayout(fav_header)
        
        self.favorites_grid = QGridLayout()
        self.favorites_grid.setSpacing(8)
        container_layout.addLayout(self.favorites_grid)
        
        self.refresh_favorites()
        
        layout.addWidget(self.container)
        self.setColor(self._color)



    def refresh_favorites(self):
        # Clear grid
        while self.favorites_grid.count():
            child = self.favorites_grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        for i, color_hex in enumerate(self.favorite_colors):
            btn = FavoriteColorButton(
                color_hex, 
                lambda c: self.setColor(QColor(c)), 
                self.remove_favorite
            )
            
            row, col = divmod(i, 8)
            self.favorites_grid.addWidget(btn, row, col)
            
    def add_current_to_favorites(self):
        color_hex = self._color.name()
        if color_hex not in self.favorite_colors:
            self.favorite_colors.append(color_hex)
            self.refresh_favorites()
            
    def show_context_menu(self, pos, color_hex, btn):
        menu = QMenu(self)
        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(lambda: self.remove_favorite(color_hex))
        menu.addAction(remove_action)
        menu.exec(btn.mapToGlobal(pos))
        
    def remove_favorite(self, color_hex):
        if color_hex in self.favorite_colors:
            self.favorite_colors.remove(color_hex)
            self.refresh_favorites()

    def setColor(self, color):
        self._color = color
        self.color_map.setColor(color)
        self.hue_slider.setValue(max(0, color.hueF()))
        # Alpha slider update removed
        self.preview_circle.setStyleSheet(f"background-color: {color.name(QColor.NameFormat.HexArgb)}; border-radius: 16px; border: 1px solid #888;")
        self.hex_input.blockSignals(True)
        self.hex_input.setText(color.name())
        self.hex_input.blockSignals(False)
        self.colorSelected.emit(self._color)

    def _on_map_color_changed(self, color):
        # Preserve existing alpha if needed, though slider is gone
        alpha = self._color.alpha()
        self._color = color
        self._color.setAlpha(alpha)
        self._update_ui_from_internal()

    def _on_hue_changed(self, hue):
        self.color_map.setHue(hue)

    def _on_hex_changed(self, text):
        if QColor.isValidColor(text):
            self.setColor(QColor(text))

    def _update_ui_from_internal(self):
        # Alpha slider update removed
        self.preview_circle.setStyleSheet(f"background-color: {self._color.name(QColor.NameFormat.HexArgb)}; border-radius: 16px; border: 1px solid #888;")
        self.hex_input.blockSignals(True)
        self.hex_input.setText(self._color.name())
        self.hex_input.blockSignals(False)
        self.colorSelected.emit(self._color)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self._drag_pos:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None




