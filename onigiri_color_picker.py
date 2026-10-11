import os

from aqt import mw
from aqt.qt import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QColor,
    QBrush,
    QFont,
    QGraphicsDropShadowEffect,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPoint,
    QCursor,
    QRectF,
    QSize,
    Qt,
    QEvent,
)
from aqt.theme import theme_manager
from PyQt6.QtCore import QByteArray, QEventLoop, QTimer, pyqtSignal
from PyQt6.QtSvg import QSvgRenderer

from .translations import tr


DEFAULT_COLOR = "#FF5985"
POPUP_WIDTH = 260
ADDON_ROOT = os.path.dirname(__file__)
SYSTEM_ICONS_DIR = os.path.join(ADDON_ROOT, "system_files", "system_icons")
SYSTEM_ICONS_AVAILABLE_DIR = os.path.join(SYSTEM_ICONS_DIR, "available_for_users")
SYSTEM_ICONS_UNAVAILABLE_DIR = os.path.join(SYSTEM_ICONS_DIR, "unavailable_for_users")
_SVG_CACHE = {}


def _system_icon_path(filename):
    filename = os.path.basename(str(filename or ""))
    for directory in (SYSTEM_ICONS_UNAVAILABLE_DIR, SYSTEM_ICONS_AVAILABLE_DIR, SYSTEM_ICONS_DIR):
        path = os.path.join(directory, filename)
        if os.path.exists(path):
            return path
    return os.path.join(SYSTEM_ICONS_UNAVAILABLE_DIR, filename)


def _contrast_icon_color(background):
    color = QColor(background)
    red = color.redF()
    green = color.greenF()
    blue = color.blueF()
    luminance = (0.2126 * red) + (0.7152 * green) + (0.0722 * blue)
    return QColor("#111111") if luminance > 0.56 else QColor("#ffffff")


REMOVE_ICON_PATH = _system_icon_path("cancel.svg")
CHECK_ICON_PATH = _system_icon_path("check-simple.svg")


def _normalized_hex(value, fallback=DEFAULT_COLOR):
    text = str(value or "").strip()
    if text.lower() == "transparent":
        return "transparent"
    if text and not text.startswith("#") and len(text) in (3, 6):
        text = f"#{text}"
    color = QColor(text)
    if not color.isValid():
        color = QColor(fallback)
    return color.name().upper()


def _is_dark_mode():
    try:
        return bool(theme_manager.night_mode)
    except Exception:
        return False


def _render_svg_icon(painter, path, rect, color):
    try:
        svg = _SVG_CACHE.get(path)
        if svg is None:
            with open(path, "r", encoding="utf-8") as handle:
                svg = handle.read()
            _SVG_CACHE[path] = svg
        tinted = svg.replace("currentColor", color.name())
        if tinted == svg and "<path " in tinted:
            tinted = tinted.replace("<path ", f'<path fill="{color.name()}" ', 1)
        renderer = QSvgRenderer(QByteArray(tinted.encode("utf-8")))
        renderer.render(painter, QRectF(rect))
    except Exception:
        pass


class _ColorArea(QWidget):
    colorChanged = pyqtSignal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(84)
        self.setMinimumWidth(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._hue = 0.0
        self._sat = 1.0
        self._val = 1.0

    def setColor(self, color):
        hue = color.hueF()
        self._hue = 0.0 if hue < 0 else hue
        self._sat = max(0.0, color.saturationF())
        self._val = max(0.0, color.valueF())
        self.update()

    def setHue(self, hue):
        self._hue = max(0.0, min(1.0, hue))
        self.update()

    def setValue(self, value):
        self._val = max(0.0, min(1.0, value))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(rect, 16, 16)
        painter.setClipPath(path)

        painter.fillRect(rect, QColor.fromHsvF(self._hue, 1.0, 1.0))

        saturation = QLinearGradient(0, 0, self.width(), 0)
        saturation.setColorAt(0, QColor(255, 255, 255))
        saturation.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(rect, saturation)

        brightness = QLinearGradient(0, 0, 0, self.height())
        brightness.setColorAt(0, QColor(0, 0, 0, 0))
        brightness.setColorAt(1, QColor(0, 0, 0, 210))
        painter.fillRect(rect, brightness)

        x = int(self._sat * self.width())
        y = int((1.0 - self._val) * self.height())
        marker_margin = 16
        center = QPoint(
            max(marker_margin, min(x, self.width() - marker_margin)),
            max(marker_margin, min(y, self.height() - marker_margin)),
        )
        painter.setPen(QPen(QColor("#ffffff"), 4))
        painter.setBrush(QColor.fromHsvF(self._hue, self._sat, self._val))
        painter.drawEllipse(center, 8, 8)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pick(event.pos())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._pick(event.pos())

    def _pick(self, pos):
        self._sat = max(0.0, min(1.0, pos.x() / max(1, self.width())))
        self._val = 1.0 - max(0.0, min(1.0, pos.y() / max(1, self.height())))
        self.update()
        self.colorChanged.emit(QColor.fromHsvF(self._hue, self._sat, self._val))


class _GradientSlider(QWidget):
    valueChanged = pyqtSignal(float)

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self.kind = kind
        self._value = 0.0
        self.setFixedHeight(22)
        self.setMinimumWidth(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setValue(self, value):
        self._value = max(0.0, min(1.0, value))
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._pick(event.pos())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._pick(event.pos())

    def _pick(self, pos):
        self._value = max(0.0, min(1.0, pos.x() / max(1, self.width())))
        self.update()
        self.valueChanged.emit(self._value)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())

        if self.kind == "hue":
            gradient = QLinearGradient(0, 0, self.width(), 0)
            for i in range(7):
                gradient.setColorAt(i / 6.0, QColor.fromHsvF(i / 6.0, 0.9, 1.0))
        else:
            gradient = QLinearGradient(0, 0, self.width(), 0)
            gradient.setColorAt(0, QColor("#000000"))
            gradient.setColorAt(1, QColor("#ffffff"))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(rect, self.height() / 2, self.height() / 2)

        x = int(self._value * self.width())
        radius = max(7, (self.height() - 6) // 2)
        center = QPoint(max(radius + 4, min(x, self.width() - radius - 4)), self.height() // 2)
        if self.kind == "value":
            knob_fill = QColor.fromHsvF(0, 0, self._value)
            ring_color = QColor("#ffffff") if self._value < 0.5 else QColor("#111111")
        else:
            knob_fill = QColor("#ffffff")
            ring_color = QColor("#ffffff")
        painter.setPen(QPen(ring_color, 2))
        painter.setBrush(knob_fill)
        painter.drawEllipse(center, radius, radius)


def _paint_checkerboard(painter, rect, dark, cell=5):
    path = QPainterPath()
    path.addEllipse(QRectF(rect))
    painter.save()
    painter.setClipPath(path)
    light = QColor(70, 70, 70) if dark else QColor(230, 230, 230)
    shade = QColor(45, 45, 45) if dark else QColor(190, 190, 190)
    y = 0.0
    row = 0
    while y < rect.height():
        x = 0.0
        col = 0
        while x < rect.width():
            painter.fillRect(QRectF(rect.x() + x, rect.y() + y, cell, cell), light if (row + col) % 2 == 0 else shade)
            x += cell
            col += 1
        y += cell
        row += 1
    painter.restore()


class _PreviewCircle(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self._color = QColor(DEFAULT_COLOR)

    def setColor(self, color):
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        if self._color.alpha() == 0:
            _paint_checkerboard(painter, rect, _is_dark_mode())
            return
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        painter.drawEllipse(rect)


class _TransparentSwatchButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, dark=False, parent=None):
        super().__init__(parent)
        self.dark = dark
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tr("make_transparent"))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        _paint_checkerboard(painter, rect, self.dark)
        painter.setPen(QPen(QColor(255, 255, 255, 90) if self.dark else QColor(0, 0, 0, 60), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class _IconButton(QWidget):
    clicked = pyqtSignal()
    hoverChanged = pyqtSignal(bool)

    def __init__(self, icon_path, dark=False, filled=False, parent=None):
        super().__init__(parent)
        self.icon_path = icon_path
        self.dark = dark
        self.filled = filled
        self.accent_color = QColor("#FF5985")
        self._hovered = False
        self.setFixedSize(22, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def setAccentColor(self, color):
        next_color = QColor(color)
        if next_color.isValid() and next_color != self.accent_color:
            self.accent_color = next_color
            self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        self.hoverChanged.emit(True)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        self.hoverChanged.emit(False)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fill = None
        if self.filled or self._hovered:
            fill = self.accent_color if self.filled else (QColor(255, 255, 255, 32) if self.dark else QColor(0, 0, 0, 18))
            if self.filled and self._hovered:
                fill = fill.lighter(108)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawEllipse(QRectF(self.rect()).adjusted(1, 1, -1, -1))
        color = _contrast_icon_color(fill) if self.filled and fill else (QColor("#f4f4f5") if self.dark else QColor("#242426"))
        inset = 6 if not self.filled else 5
        _render_svg_icon(painter, self.icon_path, QRectF(self.rect()).adjusted(inset, inset, -inset, -inset), color)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


class _OnigiriPalettePopup(QFrame):
    finished = pyqtSignal(str, bool)

    def __init__(self, initial_color, parent=None, anchor=None, allow_transparent=False):
        super().__init__(parent)
        self._anchor = anchor
        self._dark = _is_dark_mode()
        self._finished = False
        self._event_filter_installed = False
        self._allow_transparent = allow_transparent
        self._color = QColor(_normalized_hex(initial_color))
        # The compact picker is a miniature of Settings' web modal. Its save
        # affordance therefore uses the app accent, not the draft colour — a
        # red draft must not turn the confirmation action red.
        self._accent = QColor("#0077C8")

        hue = self._color.hueF()
        self._hue = 0.0 if hue < 0 else hue
        self._sat = max(0.0, self._color.saturationF())
        self._val = max(0.0, self._color.valueF())

        self.setObjectName("OnigiriPalettePopup")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedWidth(POPUP_WIDTH)

        bg = "#28282A" if self._dark else "#FFFFFF"
        border = "#3F3F44" if self._dark else "#E3E4E7"
        self.setStyleSheet(
            f"""
            QFrame#OnigiriPalettePopup {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 20px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame(self)
        header.setFixedHeight(50)
        header.setStyleSheet(
            f"background: {'#303033' if self._dark else '#F0F0EF'}; "
            f"border: none; border-bottom: 1px solid {'#3F3F44' if self._dark else '#E3E4E7'}; "
            "border-top-left-radius: 20px; border-top-right-radius: 20px;"
        )
        close_row = QHBoxLayout(header)
        close_row.setContentsMargins(12, 0, 12, 0)
        close_row.setSpacing(8)
        title = QLabel(tr("color", "Color"), header)
        title.setStyleSheet(
            f"background: transparent; border: none; color: {'#F4F4F5' if self._dark else '#202124'}; "
            "font-size: 13px; font-weight: 600;"
        )
        close_row.addWidget(title)
        close_row.addStretch()
        self.cancel_button = _IconButton(REMOVE_ICON_PATH, self._dark, parent=header)
        self.cancel_button.clicked.connect(self.cancel)
        close_row.addWidget(self.cancel_button)
        self.close_button = _IconButton(CHECK_ICON_PATH, self._dark, filled=True, parent=header)
        self.close_button.clicked.connect(self.accept)
        self.close_button.setAccentColor(self._accent)
        close_row.addWidget(self.close_button)
        layout.addWidget(header)

        content = QFrame(self)
        self._content = content
        content.setStyleSheet("background: transparent; border: none;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(8)
        layout.addWidget(content)

        self.color_area = _ColorArea(content)
        self.color_area.colorChanged.connect(self._set_color_from_area)
        content_layout.addWidget(self.color_area)

        self.value_slider = _GradientSlider("value", content)
        self.value_slider.valueChanged.connect(self._set_value)
        content_layout.addWidget(self.value_slider)

        self.hue_slider = _GradientSlider("hue", content)
        self.hue_slider.valueChanged.connect(self._set_hue)
        content_layout.addWidget(self.hue_slider)

        hex_frame = QFrame(content)
        hex_frame.setObjectName("OnigiriHexFrame")
        hex_frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        hex_frame.setFixedHeight(38)
        pill_bg = "#3A3A3D" if self._dark else "#F0F0EF"
        hex_frame.setStyleSheet(
            f"QFrame#OnigiriHexFrame {{ background-color: {pill_bg}; border: 0px; border-radius: 19px; }}"
        )
        hex_layout = QHBoxLayout(hex_frame)
        hex_layout.setContentsMargins(5, 5, 12, 5)
        hex_layout.setSpacing(7)

        self.preview = _PreviewCircle(hex_frame)
        hex_layout.addWidget(self.preview)

        prefix_color = "#D5D5D8" if self._dark else "#28282A"
        self.hex_prefix = QLabel("#", hex_frame)
        self.hex_prefix.setStyleSheet(
            f"background: transparent; border: none; color: {prefix_color}; "
            "font-family: Arial; font-size: 13px; font-weight: 400;"
        )
        hex_layout.addWidget(self.hex_prefix)

        self.hex_input = QLineEdit(hex_frame)
        self.hex_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Seven characters accepts a pasted legacy value with '#'; the input
        # is immediately normalized to six visible HEX digits below.
        self.hex_input.setMaxLength(7)
        self.hex_input.setFont(QFont("Arial", 13, QFont.Weight.Normal))
        text_color = "#F5F5F6" if self._dark else "#000000"
        self.hex_input.setStyleSheet(
            f"""
            QLineEdit {{
                background: transparent;
                border: none;
                color: {text_color};
                padding: 0px;
            }}
            """
        )
        self.hex_input.textChanged.connect(self._set_color_from_hex)
        hex_layout.addWidget(self.hex_input, 1)

        if self._allow_transparent:
            self.transparent_button = _TransparentSwatchButton(self._dark, hex_frame)
            self.transparent_button.clicked.connect(self._select_transparent)
            hex_layout.addWidget(self.transparent_button)

        content_layout.addWidget(hex_frame)

        self._sync_widgets()

    def _position_at_top(self):
        self.adjustSize()
        parent = self.parentWidget()
        if parent:
            width = min(POPUP_WIDTH, max(232, parent.width() - 16))
            self.setFixedWidth(width)
            self.adjustSize()
            margin = 8

            if self._anchor and self._anchor.window() is parent:
                anchor_pos = self._anchor.mapTo(parent, QPoint(0, 0))
                below_y = anchor_pos.y() + self._anchor.height() + 6
                above_y = anchor_pos.y() - self.height() - 6
                x = anchor_pos.x()
                y = below_y if below_y + self.height() <= parent.height() - margin else max(margin, above_y)
            else:
                cursor_pos = parent.mapFromGlobal(QCursor.pos())
                x = cursor_pos.x() - 18
                y = cursor_pos.y() + 10
                if y + self.height() > parent.height() - margin:
                    y = cursor_pos.y() - self.height() - 10

            x = max(margin, min(x, parent.width() - self.width() - margin))
            y = max(margin, min(y, parent.height() - self.height() - margin))
            self.move(x, y)

    def show_at_top(self):
        self._position_at_top()
        if not self._event_filter_installed:
            QApplication.instance().installEventFilter(self)
            self._event_filter_installed = True
        self.show()
        self.raise_()
        self.setFocus(Qt.FocusReason.PopupFocusReason)

    def eventFilter(self, obj, event):
        if self._finished or not self.isVisible():
            return False

        if obj is self.parentWidget() and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            self._position_at_top()
            return False

        if event.type() == QEvent.Type.MouseButtonPress:
            global_pos = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
            widget = QApplication.widgetAt(global_pos)
            while widget:
                if widget is self:
                    return False
                widget = widget.parentWidget()
            self.accept()
            return True

        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self.cancel()
            return True

        return False

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if not self._finished:
            self.cancel()
        super().closeEvent(event)

    def accept(self):
        color_hex = "transparent" if self._color.alpha() == 0 else self._color.name().upper()
        self._finish(color_hex, True)

    def cancel(self):
        self._finish(self._color.name().upper(), False)

    def _select_transparent(self):
        self._color = QColor(0, 0, 0, 0)
        self._sync_widgets()
        self.accept()

    def _finish(self, color_hex, accepted):
        if self._finished:
            return
        self._finished = True
        try:
            if self._event_filter_installed:
                QApplication.instance().removeEventFilter(self)
                self._event_filter_installed = False
        except Exception:
            pass
        self.hide()
        self.finished.emit(color_hex, accepted)

    def _set_color_from_area(self, color):
        self._color = QColor(color)
        self._hue = 0.0 if self._color.hueF() < 0 else self._color.hueF()
        self._sat = max(0.0, self._color.saturationF())
        self._val = max(0.0, self._color.valueF())
        self._sync_widgets(update_area=False)

    def _set_value(self, value):
        self._val = max(0.0, min(1.0, value))
        self._color = QColor.fromHsvF(self._hue, self._sat, self._val)
        self._sync_widgets()

    def _set_hue(self, hue):
        self._hue = max(0.0, min(1.0, hue))
        self._color = QColor.fromHsvF(self._hue, self._sat, self._val)
        self._sync_widgets()

    def _set_color_from_hex(self, text):
        raw = str(text).strip().lstrip("#")[:6]
        if raw != text:
            self.hex_input.blockSignals(True)
            self.hex_input.setText(raw)
            self.hex_input.blockSignals(False)
        candidate = f"#{raw}" if raw and len(raw) in (3, 6) else raw
        color = QColor(candidate)
        if not color.isValid():
            return
        self._color = color
        hue = color.hueF()
        self._hue = 0.0 if hue < 0 else hue
        self._sat = max(0.0, color.saturationF())
        self._val = max(0.0, color.valueF())
        self._sync_widgets(update_hex=False)

    def _sync_widgets(self, update_area=True, update_hex=True):
        if update_area:
            self.color_area.setColor(self._color)
        else:
            self.color_area.setHue(self._hue)
            self.color_area.setValue(self._val)

        self.value_slider.setValue(self._val)
        self.hue_slider.setValue(self._hue)
        self.preview.setColor(self._color)
        self.close_button.setAccentColor(self._accent)

        if update_hex:
            self.hex_input.blockSignals(True)
            self.hex_input.setText(self._color.name().lstrip("#").upper())
            self.hex_input.blockSignals(False)

class OnigiriColorDialog:
    @staticmethod
    def getColor(initial_color, parent=None, anchor=None, allow_transparent=False):
        app = QApplication.instance()
        if app is None:
            return _normalized_hex(initial_color), False

        root = parent.window() if parent else app.activeWindow()
        if root is None:
            root = mw.app.activeWindow() if mw and mw.app else None
        if root is None:
            return _normalized_hex(initial_color), False

        result = {"color": _normalized_hex(initial_color), "ok": False}
        loop = QEventLoop()
        popup = _OnigiriPalettePopup(initial_color, root, anchor=anchor, allow_transparent=allow_transparent)

        def finish(color_hex, accepted):
            result["color"] = color_hex
            result["ok"] = accepted
            loop.quit()

        popup.finished.connect(finish)
        popup.show_at_top()
        loop.exec()
        popup.deleteLater()
        return result["color"], result["ok"]
