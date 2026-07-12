# Auto-split from the historical settings/_legacy.py. Do not hand-edit alongside _legacy.
from ._common import *
from ._common import _contrast_icon_color, _font_popup_svg_icon


class AnimatedRadioButton(QRadioButton):
    """Radio button with the same smooth inner-bubble animation used by language selectors."""
    def __init__(self, text="", parent=None, accent_color="#008cff"):
        super().__init__(text, parent)
        self._accent_color = QColor(accent_color)
        self._border_color = QColor("#d7d9de")
        self._fill_progress = 0.0
        self._hover_progress = 0.0
        self._gooey_amount = 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.setMinimumHeight(30)
        self.setStyleSheet("QRadioButton { background: transparent; spacing: 0px; padding: 0px; }")

        self._fill_animation = QPropertyAnimation(self, b"fill_progress", self)
        self._fill_animation.setDuration(190)
        self._fill_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._hover_animation = QPropertyAnimation(self, b"hover_progress", self)
        self._hover_animation.setDuration(150)
        self._hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._gooey_animation = QPropertyAnimation(self, b"gooey_amount", self)
        self._gooey_animation.setDuration(260)
        self._gooey_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._start_animation)

    @pyqtProperty(float)
    def fill_progress(self):
        return self._fill_progress

    @fill_progress.setter
    def fill_progress(self, value):
        self._fill_progress = max(0.0, min(1.0, float(value)))
        self.update()

    @pyqtProperty(float)
    def hover_progress(self):
        return self._hover_progress

    @hover_progress.setter
    def hover_progress(self, value):
        self._hover_progress = max(0.0, min(1.0, float(value)))
        self.update()

    @pyqtProperty(float)
    def gooey_amount(self):
        return self._gooey_amount

    @gooey_amount.setter
    def gooey_amount(self, value):
        self._gooey_amount = max(0.0, min(1.0, float(value)))
        self.update()

    def setAccentColor(self, accent_color):
        self._accent_color = QColor(accent_color)
        self.update()

    def setChecked(self, checked):
        super().setChecked(checked)
        if self.signalsBlocked() or not self.isVisible():
            self._fill_animation.stop()
            self._gooey_animation.stop()
            self._gooey_amount = 0.0
            self._fill_progress = 1.0 if checked else 0.0
            self.update()

    def sizeHint(self):
        text_width = self.fontMetrics().horizontalAdvance(self.text())
        return QSize(text_width + 44, 32)

    def minimumSizeHint(self):
        return self.sizeHint()

    def enterEvent(self, event):
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def _animate_hover(self, end_value):
        self._hover_animation.stop()
        self._hover_animation.setStartValue(self._hover_progress)
        self._hover_animation.setEndValue(float(end_value))
        self._hover_animation.start()

    def _start_animation(self, checked):
        if self.signalsBlocked() or not self.isVisible():
            self._fill_progress = 1.0 if checked else 0.0
            self._gooey_amount = 0.0
            self.update()
            return

        self._fill_animation.stop()
        self._fill_animation.setStartValue(self._fill_progress)
        self._fill_animation.setEndValue(1.0 if checked else 0.0)
        self._fill_animation.start()

        self._gooey_animation.stop()
        if checked:
            self._gooey_animation.setStartValue(1.0)
            self._gooey_animation.setEndValue(0.0)
            self._gooey_animation.start()
        else:
            self._gooey_amount = 0.0

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        indicator_size = 22.0
        indicator_x = 0.0
        indicator_y = (self.height() - indicator_size) / 2.0
        rect = QRectF(indicator_x, indicator_y, indicator_size, indicator_size).adjusted(2, 2, -2, -2)
        center = rect.center()
        radius = rect.width() / 2.0

        border_color = QColor(self._accent_color) if (
            self.isChecked() or self.underMouse() or self.isDown() or self._hover_progress > 0.01
        ) else QColor(self._border_color)
        border_width = 2.0 + (0.6 * self._hover_progress)
        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(QBrush(QColor(0, 0, 0, 0)))
        painter.drawEllipse(rect)

        if self._hover_progress > 0.01 and not self.isChecked():
            hover_color = QColor(self._accent_color)
            hover_color.setAlpha(int(22 * self._hover_progress))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(hover_color))
            painter.drawEllipse(rect.adjusted(2, 2, -2, -2))

        if self._fill_progress > 0.01 or self._gooey_amount > 0.01:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self._accent_color))
            fill_radius = max(0.0, (radius - 2.8) * self._fill_progress)
            if fill_radius > 0.1:
                painter.save()
                clip_path = QPainterPath()
                clip_path.addEllipse(rect.adjusted(1.5, 1.5, -1.5, -1.5))
                painter.setClipPath(clip_path)
                effective_gooey = self._gooey_amount * min(1.0, self._fill_progress * 2.0)
                squash_x = 1.0 + (0.16 * effective_gooey)
                squash_y = 1.0 - (0.10 * effective_gooey)
                painter.drawEllipse(
                    QRectF(
                        center.x() - (fill_radius * squash_x),
                        center.y() - (fill_radius * squash_y),
                        fill_radius * 2 * squash_x,
                        fill_radius * 2 * squash_y,
                    )
                )
                painter.restore()

        text_color = self.palette().color(self.foregroundRole())
        if not self.isEnabled():
            text_color.setAlpha(135)
        painter.setPen(text_color)
        text_rect = QRectF(34, 0, max(1, self.width() - 34), self.height())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.text())


class AnimatedToggleButton(QAbstractButton):
    """Modern toggle switch that follows the active user accent color."""
    def __init__(self, parent=None, accent_color="#00A982"):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.accent_color = QColor(accent_color)
        self.track_color_off = QColor("#d1d5db") if not theme_manager.night_mode else QColor("#4b5563")
        self.thumb_color = QColor("#ffffff")

        self.setFixedSize(50, 30)
        self._thumb_x_pos = 0.0
        self._gooey_amount = 0.0
        self._gooey_direction = 1.0

        self.animation = QPropertyAnimation(self, b"thumb_x_pos", self)
        self.animation.setDuration(180)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.gooey_animation = QPropertyAnimation(self, b"gooey_amount", self)
        self.gooey_animation.setDuration(230)
        self.gooey_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._start_animation)

    def _track_rect(self):
        return QRectF(3, 3, self.width() - 6, self.height() - 6)

    def _checked_thumb_position(self, checked=None):
        if checked is None:
            checked = self.isChecked()
        track = self._track_rect()
        thumb_r = (track.height() / 2.0) - 3
        if checked:
            return float(track.right() - 3 - (thumb_r * 2))
        return float(track.left() + 3)

    def _sync_thumb_to_checked(self):
        self._thumb_x_pos = self._checked_thumb_position()
        self.update()

    def setChecked(self, checked):
        super().setChecked(checked)
        if self.signalsBlocked() or not self.isVisible():
            self.animation.stop()
            self.gooey_animation.stop()
            self._gooey_amount = 0.0
            self._sync_thumb_to_checked()

    def setAccentColor(self, accent_color):
        self.accent_color = QColor(accent_color)
        self.update()

    def setThemeMode(self, is_dark):
        self.track_color_off = QColor("#4b5563") if is_dark else QColor("#d1d5db")
        self.update()

    @pyqtProperty(float)
    def thumb_x_pos(self):
        return self._thumb_x_pos

    @thumb_x_pos.setter
    def thumb_x_pos(self, value):
        self._thumb_x_pos = value
        self.update()

    @pyqtProperty(float)
    def gooey_amount(self):
        return self._gooey_amount

    @gooey_amount.setter
    def gooey_amount(self, value):
        self._gooey_amount = max(0.0, min(1.0, float(value)))
        self.update()

    def _start_animation(self, checked):
        end_pos = self._checked_thumb_position(checked)
        self._gooey_direction = 1.0 if checked else -1.0
        self.animation.setStartValue(self.thumb_x_pos)
        self.animation.setEndValue(float(end_pos))
        self.animation.start()
        self.gooey_animation.stop()
        self.gooey_animation.setStartValue(1.0)
        self.gooey_animation.setEndValue(0.0)
        self.gooey_animation.start()

    @staticmethod
    def draw_lock_icon(painter, center, color, scale=1.0):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor(color), max(1.2, 1.6 * scale))
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        body_w = 8.0 * scale
        body_h = 6.2 * scale
        body_x = center.x() - body_w / 2
        body_y = center.y() - body_h / 2 + 1.6 * scale
        painter.drawRoundedRect(QRectF(body_x, body_y, body_w, body_h), 1.5 * scale, 1.5 * scale)
        shackle_w = 5.2 * scale
        shackle_h = 7.0 * scale
        shackle_x = center.x() - shackle_w / 2
        shackle_y = body_y - shackle_h * 0.62
        painter.drawArc(QRectF(shackle_x, shackle_y, shackle_w, shackle_h), 0, 180 * 16)
        painter.restore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track_rect = self._track_rect()
        radius = track_rect.height() / 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        locked = not self.isEnabled()
        if locked:
            track_color = QColor("#cfd6df" if not theme_manager.night_mode else "#3f4652")
        else:
            track_color = self.accent_color if self.isChecked() else self.track_color_off
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, radius, radius)
        thumb_r = radius - 3
        thumb_color = QColor("#f8fafc" if locked else self.thumb_color.name())
        thumb_center = QPointF(self._thumb_x_pos + thumb_r, track_rect.center().y())
        if self._gooey_amount > 0.01:
            gooey_path = QPainterPath()
            stretch = (3.5 + 4.5 * self._gooey_amount) * self._gooey_direction
            min_center_x = track_rect.left() + 3 + thumb_r
            max_center_x = track_rect.right() - 3 - thumb_r
            trail_x = max(min_center_x, min(max_center_x, thumb_center.x() - stretch))
            trail_center = QPointF(trail_x, thumb_center.y())
            trail_r = max(thumb_r * 0.56, thumb_r * (0.70 - 0.12 * self._gooey_amount))
            gooey_path.addEllipse(thumb_center, thumb_r + 0.8 * self._gooey_amount, thumb_r)
            gooey_path.addEllipse(trail_center, trail_r, trail_r * 0.94)
            bridge_left = min(thumb_center.x(), trail_center.x())
            bridge_width = abs(thumb_center.x() - trail_center.x())
            gooey_path.addRoundedRect(
                QRectF(bridge_left, track_rect.center().y() - trail_r, bridge_width, trail_r * 2),
                trail_r,
                trail_r,
            )
            painter.setBrush(thumb_color)
            painter.drawPath(gooey_path)
        painter.setBrush(thumb_color)
        painter.drawEllipse(thumb_center, thumb_r, thumb_r)
        if locked:
            lock_color = "#6b7280" if not theme_manager.night_mode else "#cbd5e1"
            thumb_center_x = self._thumb_x_pos + thumb_r
            lock_center_x = track_rect.left() + radius if thumb_center_x > self.width() / 2 else track_rect.right() - radius
            self.draw_lock_icon(painter, QPointF(lock_center_x, track_rect.center().y()), lock_color, 1.0)

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_thumb_to_checked()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_thumb_to_checked()


class BackgroundGalleryDialog(QDialog):
    keyAssignmentRequested = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hovered_tile = None

    def setHoveredTile(self, tile):
        self.hovered_tile = tile

    def keyPressEvent(self, event):
        if self.hovered_tile:
            key_text = event.text().lower()
            if key_text in set("dl123456789"):
                self.keyAssignmentRequested.emit(self.hovered_tile.filename, key_text)
                return
        super().keyPressEvent(event)


class GalleryBadgeOverlay(QWidget):
    """Small selection badge for background gallery modal items."""
    def __init__(self, parent=None, accent_color="#00A982"):
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self._badges = []
        self.accent_color = QColor(accent_color)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def setBadge(self, text):
        text = str(text or "")
        self.setBadges([{"text": text}] if text else [])

    def setBadges(self, badges):
        self._badges = [badge for badge in badges if badge]
        width = max(28, (28 * len(self._badges)) + (4 * max(0, len(self._badges) - 1)))
        self.setFixedSize(width, 28)
        self.update()

    def _render_svg_icon(self, painter, icon_path, rect):
        if not icon_path or not os.path.exists(icon_path):
            return False
        try:
            with open(icon_path, "r", encoding="utf-8") as icon_file:
                svg_xml = icon_file.read()
            svg_xml = svg_xml.replace("<path ", '<path fill="#ffffff" ', 1)
            renderer = QSvgRenderer(svg_xml.encode("utf-8"))
            renderer.render(painter, rect)
            return True
        except Exception:
            return False

    def paintEvent(self, event):
        if not self._badges:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        for index, badge in enumerate(self._badges):
            rect = QRect(index * 32, 0, 28, 28)
            painter.setBrush(self.accent_color)
            painter.drawEllipse(rect)
            icon_path = badge.get("icon")
            if icon_path and self._render_svg_icon(painter, icon_path, QRectF(rect).adjusted(7, 7, -7, -7)):
                continue
            painter.setPen(QColor("#ffffff"))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(badge.get("text", "")))
            painter.setPen(Qt.PenStyle.NoPen)


class BackgroundGalleryTile(QWidget):
    clicked = pyqtSignal(str)
    hovered = pyqtSignal(object)

    def __init__(self, filename, image_path, accent_color="#00A982", parent=None):
        super().__init__(parent)
        self.filename = filename
        self._hovered = False
        self._flash = False
        self.accent_color = QColor(accent_color)
        self._thumb_width = 206
        self._thumb_height = 116
        self.setFixedSize(self._thumb_width, self._thumb_height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        self._pixmap = QPixmap()
        source = QImage(image_path)
        if not source.isNull():
            self._pixmap = QPixmap.fromImage(create_rounded_thumbnail_image(source, self._thumb_width, self._thumb_height, 10))

        self.badge = GalleryBadgeOverlay(self, accent_color)
        self._position_badge()

    def _position_badge(self):
        self.badge.move(max(8, self.width() - self.badge.width() - 8), 8)

    def setBadge(self, text):
        self.badge.setBadge(text)
        self._position_badge()

    def setBadges(self, badges):
        self.badge.setBadges(badges)
        self._position_badge()

    def flash(self):
        self._flash = True
        self.update()
        QTimer.singleShot(220, self._clear_flash)

    def _clear_flash(self):
        self._flash = False
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.hovered.emit(self)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.hovered.emit(None)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.clicked.emit(self.filename)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)
        painter.setClipPath(path)
        if self._pixmap.isNull():
            painter.fillPath(path, QColor("#2b2f35" if theme_manager.night_mode else "#eef0f3"))
        else:
            painter.drawPixmap(self.rect(), self._pixmap)
        if self._hovered or self._flash:
            painter.fillPath(path, QColor(255, 255, 255, 24 if theme_manager.night_mode else 42))
        painter.setClipping(False)
        if self._hovered or self._flash:
            pen = QPen(self.accent_color if self._flash else QColor("#ffffff" if theme_manager.night_mode else "#111827"))
            pen.setWidth(2 if self._flash else 1)
            painter.setPen(pen)
            painter.drawPath(path)


class BackgroundPreviewLabel(QLabel):
    """Keep background preview geometry independent from the current text or pixmap."""
    def __init__(self, parent=None, aspect_ratio=2.0, minimum_preview_height=230):
        super().__init__(parent)
        self._aspect_ratio = max(0.1, float(aspect_ratio))
        self._minimum_preview_height = int(minimum_preview_height)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.setMinimumHeight(self._minimum_preview_height)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return max(self._minimum_preview_height, int(max(1, width) / self._aspect_ratio))

    def sizeHint(self):
        width = max(720, self.width(), super().sizeHint().width())
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self):
        return QSize(320, self.heightForWidth(320))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        desired_height = self.heightForWidth(event.size().width())
        if self.minimumHeight() != desired_height:
            self.setMinimumHeight(desired_height)
            self.updateGeometry()


class BirthdayWidget(QWidget):
    def __init__(self, accent_color="#00A982", parent=None):
        super().__init__(parent)
        
        mode = "dark" if theme_manager.night_mode else "light"
        palette = config.get_config().get("colors", {}).get(mode, {})
        defaults = DEFAULTS["colors"][mode]
        accent_color = palette.get("--accent-color", accent_color or defaults["--accent-color"])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        self.accent_color = accent_color

        if theme_manager.night_mode:
            bg_color = palette.get("--highlight-bg", palette.get("--canvas-inset", "#303030"))
            text_color = palette.get("--fg", "#f9fafb")
            border_color = palette.get("--border", "#454545")
            hover_border_color = palette.get("--fg-subtle", "#d1d5db")
        else:
            bg_color = palette.get("--highlight-bg", palette.get("--canvas-inset", "#f9fafb"))
            text_color = palette.get("--fg", "#111827")
            border_color = palette.get("--border", "#e5e7eb")
            hover_border_color = palette.get("--fg-subtle", "#4b5563")

        input_style = f"""
            QLineEdit {{
                min-height: 32px;
                max-height: 32px;
                padding: 3px 9px;
                border: 1px solid {border_color};
                border-radius: 10px;
                background-color: {bg_color};
                color: {text_color};
                font-size: 13px;
                selection-background-color: {accent_color};
                outline: none;
            }}
            QLineEdit:hover {{
                border-color: {hover_border_color};
            }}
            QLineEdit:focus {{
                border: 1px solid {accent_color};
                background-color: {bg_color};
            }}
        """

        # Day Input
        self.day_input = QLineEdit()
        self.day_input.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.day_input.setPlaceholderText("Day")
        self.day_input.setValidator(QIntValidator(1, 31))
        self.day_input.setMinimumWidth(62)
        self.day_input.setFixedHeight(32)
        self.day_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.day_input.setStyleSheet(input_style)
        self.day_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Month Input
        self.month_input = QLineEdit()
        self.month_input.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.month_input.setPlaceholderText("Month")
        self.month_input.setValidator(QIntValidator(1, 12))
        self.month_input.setMinimumWidth(78)
        self.month_input.setFixedHeight(32)
        self.month_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.month_input.setStyleSheet(input_style)
        self.month_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Year Input
        self.year_input = QLineEdit()
        self.year_input.setAttribute(Qt.WidgetAttribute.WA_MacShowFocusRect, False)
        self.year_input.setPlaceholderText("Year")
        self.year_input.setValidator(QIntValidator(1900, 2100))
        self.year_input.setMinimumWidth(72)
        self.year_input.setFixedHeight(32)
        self.year_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.year_input.setStyleSheet(input_style)
        self.year_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self.day_input, 1)
        layout.addWidget(self.month_input, 1)
        layout.addWidget(self.year_input, 1)

    def setDate(self, date):
        if not date.isValid():
            return
        
        # Set Day
        self.day_input.setText(str(date.day()))
        
        # Set Month
        self.month_input.setText(str(date.month()))
        
        # Set Year
        self.year_input.setText(str(date.year()))

    def date(self):
        try:
            if not self.day_input.text() or not self.month_input.text() or not self.year_input.text():
                return QDate()
            
            day = int(self.day_input.text())
            month = int(self.month_input.text())
            year = int(self.year_input.text())
            
            return QDate(year, month, day)
        except:
            return QDate()


class CircularColorButton(QPushButton):
    """Botão de cor circular limpo — borda fina, sem sombra."""
    def __init__(self, color=QColor("white"), parent=None):
        super().__init__("", parent)
        self.setFixedSize(28, 28)
        self._color = QColor(color)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Escolher cor")

    def color(self):
        return self._color

    def setColor(self, color):
        qcolor = QColor(color)
        if self._color != qcolor:
            self._color = qcolor
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        painter.setBrush(QBrush(self._color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(rect)
        pen = QPen(QColor("#d1d5db"))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(rect)


class ColorSwatch(QWidget):
    """A simple widget to display a circle of a solid color."""
    def __init__(self, color_hex, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.color = QColor(color_hex)
        self.setToolTip(color_hex.upper())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(self.color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(self.rect())


class DonationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Support Onigiri")
        self.setFixedWidth(300)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)

        title = QLabel(tr("choose_donation_platform"))
        title.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 5px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # --- Theme Detection for Base Button Style ---
        is_dark = theme_manager.night_mode
        
        if is_dark:
            btn_bg = "#3a3a3a"
            btn_text = "white"
            btn_border = "#555"
        else:
            btn_bg = "#f0f0f0"
            btn_text = "black"
            btn_border = "#ccc"

        base_style = f"""
            QPushButton {{
                padding: 12px;
                border-radius: 20px;
                background-color: {btn_bg};
                color: {btn_text};
                border: 1px solid {btn_border};
                font-weight: bold;
                font-size: 13px;
            }}
        """

        # BMC Button
        self.bmc_button = QPushButton(tr("buy_me_a_coffee"))
        self.bmc_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bmc_button.setStyleSheet(base_style + """
            QPushButton:hover {
                background-color: #FFDD04;
                border: 1px solid #FFDD04;
                color: black;
            }
        """)
        self.bmc_button.clicked.connect(lambda: self._open_url("https://buymeacoffee.com/peacemonk"))
        layout.addWidget(self.bmc_button)

        # Ko-Fi Button
        self.kofi_button = QPushButton(tr("ko_fi"))
        self.kofi_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.kofi_button.setStyleSheet(base_style + """
            QPushButton:hover {
                background-color: #FF5A16;
                border: 1px solid #FF5A16;
                color: white;
            }
        """)
        self.kofi_button.clicked.connect(lambda: self._open_url("https://ko-fi.com/peacemonk"))
        layout.addWidget(self.kofi_button)

    def _open_url(self, url):
        QDesktopServices.openUrl(QUrl(url))
        self.accept()


class FontCardWidget(QPushButton):
    """A custom button widget to display and select a font."""
    # <<< START NEW CODE >>>
    delete_requested = pyqtSignal(str) # Signal with font_key (filename)
    # <<< END NEW CODE >>>

    def __init__(self, font_key, accent_color, parent=None, is_system_card=False, delete_icon=None):
        super().__init__(parent)
        self.font_key = font_key
        self.setObjectName("fontCard")
        all_fonts = get_all_fonts(ADDON_ROOT)
        font_info = all_fonts.get(font_key)
        
        self.setCheckable(True)
        self.setAutoExclusive(False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        if is_system_card:
            self.setMinimumHeight(54)
            layout = QHBoxLayout(self) # Horizontal layout
            layout.setContentsMargins(15, 10, 15, 10)
            
            # Localize "System" label
            display_name = tr("system") if font_key == "system" else font_info["name"]
            name_label = QLabel(display_name)
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(name_label)
        else:
            self.setMinimumSize(132, 92)
            layout = QVBoxLayout(self) # Vertical layout
            layout.setContentsMargins(10, 10, 10, 10)

            aa_label = QLabel("Aa")
            aa_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            name_label = QLabel(font_info["name"])
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            layout.addWidget(aa_label, 1)
            layout.addWidget(name_label, 0)
        
        if font_info and font_info.get("file"):
            addon_path = ADDON_ROOT
            # Correctly handles user-uploaded fonts
            if font_info.get("user"):
                font_path = os.path.join(addon_path, "user_files", "fonts", font_info["file"])
            # Correctly handles the built-in system fonts
            else:
                # FIX: Corrected the path to the system_fonts subfolder
                font_path = os.path.join(addon_path, "system_files", "fonts", "system_fonts", font_info["file"])

            if os.path.exists(font_path):
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1:
                    font_families = QFontDatabase.applicationFontFamilies(font_id)
                    if font_families:
                        font_size = 14 if is_system_card else 12
                        name_label.setFont(QFont(font_families[0], font_size))
                        if not is_system_card:
                            aa_label.setFont(QFont(font_families[0], 20))

        self.delete_button = None
        if font_info.get("user"):
            self.delete_button = QPushButton(self)
            self.delete_button.setFixedSize(22, 22)
            if delete_icon:
                self.delete_button.setIcon(delete_icon)
                self.delete_button.setIconSize(QSize(14, 14))
            else:
                self.delete_button.setText("✕")
            self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.delete_button.setToolTip("Delete this font")
            self.delete_button.clicked.connect(self._on_delete_clicked)
            self.delete_button.setStyleSheet(f"""
                QPushButton {{
                    font-size: 14px;
                    font-weight: bold;
                    color: hsl(0, 0, 63, 0.5);
                    background: transparent; 
                    border: none;
                    border-radius: 11px;
                }}
                QPushButton:hover {{ 
                    background: transparent; 
                    color: hsl(0, 0, 63);
                }}
            """)

        self.setStyleSheet("")
    
    # <<< START NEW CODE >>>
    def _on_delete_clicked(self):
        self.delete_requested.emit(self.font_key)

    def resizeEvent(self, event):
        """Ensure the delete button stays in the top-right corner."""
        super().resizeEvent(event)
        if self.delete_button:
            self.delete_button.move(self.width() - self.delete_button.width() - 5, 5)


class FontEditorResponsiveWidget(QWidget):
    """Places font controls beside their preview, then stacks with matching widths."""
    def __init__(self, controls_widget, preview_widget, parent=None, spacing=18, breakpoint=820):
        super().__init__(parent)
        self.controls_widget = controls_widget
        self.preview_widget = preview_widget
        self.breakpoint = breakpoint
        self._stacked = None
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(spacing)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._apply_layout(stacked=False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_layout(stacked=self.width() < self.breakpoint)

    def refresh_widths(self):
        self._sync_preview_width()

    def _sync_preview_width(self):
        if self._stacked:
            width = self.controls_widget.maximumWidth()
            self.preview_widget.setMaximumWidth(width if width > 0 else 16777215)
        else:
            self.preview_widget.setMaximumWidth(16777215)

    def _apply_layout(self, stacked):
        if self._stacked == stacked:
            self._sync_preview_width()
            return
        self._stacked = stacked
        self.grid.removeWidget(self.controls_widget)
        self.grid.removeWidget(self.preview_widget)
        if stacked:
            self.grid.addWidget(self.controls_widget, 0, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self.grid.addWidget(self.preview_widget, 1, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self.grid.setColumnStretch(0, 0)
            self.grid.setColumnStretch(1, 0)
        else:
            self.grid.addWidget(self.controls_widget, 0, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self.grid.addWidget(self.preview_widget, 0, 1)
            self.grid.setColumnStretch(0, 0)
            self.grid.setColumnStretch(1, 1)
        self._sync_preview_width()


# --- MERGED FROM _widgets_2.py ---

class FontSelectorPopupPanel(QFrame):
    """Inset rounded popup shell so the outer border is never clipped."""
    def __init__(self, background_color, border_color, parent=None):
        super().__init__(parent)
        self._background_color = QColor(background_color)
        self._border_color = QColor(border_color)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(2.0, 2.0, -2.0, -2.0)
        path = QPainterPath()
        path.addRoundedRect(rect, 16, 16)
        painter.fillPath(path, QBrush(self._background_color))
        painter.setPen(QPen(self._border_color, 1.4))
        painter.drawPath(path)
        super().paintEvent(event)


class FontSelectorPopupRow(QWidget):
    """Paints a rounded hover background inside the popup viewport."""
    def __init__(self, hover_color, parent=None):
        super().__init__(parent)
        self._hover_color = QColor(hover_color)
        self._hovered = False
        self.setMouseTracking(True)

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        if self._hovered:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            path = QPainterPath()
            path.addRoundedRect(rect, 12, 12)
            painter.fillPath(path, QBrush(self._hover_color))
        super().paintEvent(event)


class FontSelectorComboBox(QComboBox):
    """Combo box with a frameless popup so the font menu has one clean border."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._font_popup = None
        self._addon_path = ""
        self._font_family_resolver = None
        self._delete_callback = None
        self._check_icon_path = ""
        self._minus_icon_path = ""
        self._accent_color = "#00A982"
        self._muted_color = "#8f9299"
        self._text_color = "#202124"
        self._hover_color = "#e9e9e9"
        self._panel_color = "#ffffff"
        self._border_color = "#dcdde1"

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(self._muted_color), 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        center_x = self.width() - 24
        center_y = self.height() / 2
        painter.drawLine(QPointF(center_x - 4, center_y - 2), QPointF(center_x, center_y + 2))
        painter.drawLine(QPointF(center_x, center_y + 2), QPointF(center_x + 4, center_y - 2))
        painter.end()

    def setPopupContext(self, addon_path, font_family_resolver, delete_callback, check_icon_path, minus_icon_path, accent_color, muted_color, text_color, hover_color, panel_color, border_color):
        self._addon_path = addon_path
        self._font_family_resolver = font_family_resolver
        self._delete_callback = delete_callback
        self._check_icon_path = check_icon_path
        self._minus_icon_path = minus_icon_path
        self._accent_color = accent_color
        self._muted_color = muted_color
        self._text_color = text_color
        self._hover_color = hover_color
        self._panel_color = panel_color
        self._border_color = border_color

    def showPopup(self):
        if self.count() <= 0:
            return
        if self._font_popup is not None:
            self._font_popup.close()

        popup = QFrame(self.window(), Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
        popup.setObjectName("fontSelectorPopupFrame")
        popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        if self.window() and self.window().styleSheet():
            popup.setStyleSheet(self.window().styleSheet())
        self._font_popup = popup

        popup_layout = QVBoxLayout(popup)
        popup_layout.setContentsMargins(4, 4, 4, 4)
        popup_layout.setSpacing(0)

        panel = FontSelectorPopupPanel(self._panel_color, self._border_color, popup)
        panel.setObjectName("fontSelectorPopupPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(2, 2, 2, 2)
        panel_layout.setSpacing(0)

        scroll = QScrollArea(panel)
        scroll.setObjectName("fontSelectorPopupScroll")
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll.viewport().setObjectName("fontSelectorPopupViewport")

        content = QWidget(scroll)
        content.setObjectName("fontSelectorPopupContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(6, 6, 14, 6)
        content_layout.setSpacing(2)

        all_fonts = get_all_fonts(self._addon_path) if self._addon_path else {}
        minus_icon = _font_popup_svg_icon(self._minus_icon_path, self._muted_color, 14)

        for row in range(self.count()):
            font_key = self.itemData(row)
            display_name = self.itemText(row)
            font_info = all_fonts.get(font_key, {})
            is_selected = row == self.currentIndex()
            is_user_font = bool(font_info.get("user"))

            row_widget = FontSelectorPopupRow(self._hover_color, content)
            row_widget.setObjectName("fontSelectorPopupRow")
            row_widget.setFixedHeight(38)

            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(10, 0, 8, 0)
            row_layout.setSpacing(8)

            check_label = QLabel(row_widget)
            check_label.setObjectName("fontSelectorCheckIcon")
            check_label.setFixedSize(16, 16)
            check_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            if is_selected:
                check_label.setPixmap(_font_popup_svg_pixmap(self._check_icon_path, self._accent_color, 15, check_label.devicePixelRatioF()))
            row_layout.addWidget(check_label)

            name_label = QLabel(display_name, row_widget)
            name_label.setObjectName("fontSelectorName")
            name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            name_label.setStyleSheet(f"color: {self._text_color}; background: transparent;")
            family = self._font_family_resolver(font_key) if self._font_family_resolver else ""
            row_font = QFont(family, 14) if family else QFont()
            row_font.setPointSize(14)
            name_label.setFont(row_font)
            row_layout.addWidget(name_label, 1)

            if is_user_font:
                delete_btn = QPushButton(row_widget)
                delete_btn.setObjectName("fontSelectorDeleteButton")
                delete_btn.setFixedSize(24, 24)
                delete_btn.setIcon(minus_icon)
                delete_btn.setIconSize(QSize(14, 14))
                delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                delete_btn.setToolTip("Delete font")
                delete_btn.clicked.connect(lambda checked=False, key=font_key: self._delete_popup_font(key, popup))
                row_layout.addWidget(delete_btn)
            else:
                spacer = QLabel(row_widget)
                spacer.setFixedSize(24, 24)
                spacer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                row_layout.addWidget(spacer)

            def select_font(event, index=row):
                if event.button() == Qt.MouseButton.LeftButton:
                    self.setCurrentIndex(index)
                    popup.close()

            row_widget.mousePressEvent = select_font

            content_layout.addWidget(row_widget)

        popup.destroyed.connect(lambda: setattr(self, "_font_popup", None))
        content_layout.addStretch(0)
        scroll.setWidget(content)
        panel_layout.addWidget(scroll)
        popup_layout.addWidget(panel)

        visible_rows = min(max(self.maxVisibleItems(), 1), self.count())
        popup.resize(max(self.width(), 240) + 8, (visible_rows * 40) + 26)
        popup.move(self.mapToGlobal(QPoint(-4, self.height())))
        popup.show()

    def _delete_popup_font(self, font_key, popup):
        if self._delete_callback:
            popup.close()
            self._delete_callback(font_key)


class GalleryAssetPreviewDialog(QDialog):
    def __init__(self, image_path, filename="", parent=None, palette=None):
        super().__init__(parent)
        self.image_path = image_path
        self.filename = filename
        self.palette_colors = palette or {}
        self.setWindowTitle(filename or "Image Preview")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(True)
        self.resize(720, 520)

        panel = self.palette_colors.get("--canvas-inset", "#242424" if theme_manager.night_mode else "#ffffff")
        border = self.palette_colors.get("--border", "#454545" if theme_manager.night_mode else "#d1d5db")
        fg = self.palette_colors.get("--fg", "#f4f4f5" if theme_manager.night_mode else "#111827")

        self.setStyleSheet(f"""
            QDialog {{
                background: transparent;
            }}
            QFrame#galleryPreviewPanel {{
                background-color: {panel};
                border: 1px solid {border};
                border-radius: 18px;
            }}
            QLabel {{
                color: {fg};
                background: transparent;
            }}
            QPushButton#galleryPreviewClose {{
                background-color: {panel};
                color: {fg};
                border: 1px solid {border};
                border-radius: 15px;
                min-height: 30px;
                padding: 0px 14px;
                font-weight: 700;
            }}
            QPushButton#galleryPreviewClose:hover {{
                background-color: {self.palette_colors.get("--highlight-bg", "#303030" if theme_manager.night_mode else "#f3f4f6")};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        panel_frame = QFrame()
        panel_frame.setObjectName("galleryPreviewPanel")
        panel_layout = QVBoxLayout(panel_frame)
        panel_layout.setContentsMargins(16, 16, 16, 16)
        panel_layout.setSpacing(10)
        layout.addWidget(panel_frame)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setMinimumSize(320, 300)
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(680, 430, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            image_label.setPixmap(scaled)
        else:
            image_label.setText("?")
        panel_layout.addWidget(image_label, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        title = QLabel(filename)
        title.setStyleSheet("font-size: 12px; font-weight: 600;")
        close_button = QPushButton("Done")
        close_button.setObjectName("galleryPreviewClose")
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.clicked.connect(self.accept)
        footer.addWidget(title, 1)
        footer.addWidget(close_button)
        panel_layout.addLayout(footer)


class GooeySegmentButton(QPushButton):
    """Text-only segment; the parent shell paints the animated selection blob."""
    def __init__(self, text, fg, checked_fg="#ffffff", hover_fg=None, parent=None):
        super().__init__(text, parent)
        self._fg = QColor(fg)
        self._checked_fg = QColor(checked_fg)
        self._hover_fg = QColor(hover_fg or fg)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet("QPushButton { border: none; background: transparent; padding: 0px; }")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        if self.isChecked():
            color = self._checked_fg
        elif self.underMouse():
            color = self._hover_fg
        else:
            color = self._fg
        painter.setPen(color)
        painter.setFont(self.font())
        painter.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter, self.text())
        painter.end()


class GooeySegmentShell(QFrame):
    """Compact segmented control with a stretchy animated selection blob."""
    def __init__(self, bg, border, accent, parent=None):
        super().__init__(parent)
        self._bg = QColor(bg)
        self._border = QColor(border)
        self._accent = QColor(accent)
        self._start_rect = QRectF()
        self._end_rect = QRectF()
        self._progress = 1.0
        self._animation = QPropertyAnimation(self, b"gooeyProgress", self)
        self._animation.setDuration(220)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setObjectName("organizeSegmentShell")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("QFrame#organizeSegmentShell { background: transparent; border: none; }")

        self.segment_layout = QHBoxLayout(self)
        self.segment_layout.setContentsMargins(3, 3, 3, 3)
        self.segment_layout.setSpacing(2)

    def add_segment_button(self, button):
        self.segment_layout.addWidget(button)
        button.toggled.connect(lambda checked, b=button: self._animate_to_button(b) if checked else None)
        if button.isChecked():
            QTimer.singleShot(0, lambda b=button: self._sync_to_button(b))

    def _button_rect(self, button):
        # button is captured by a QTimer.singleShot(0, ...) callback; the page
        # holding it may be torn down (navigated away from) before the timer
        # fires, leaving button a deleted C++ object.
        if sip is not None and sip.isdeleted(button):
            return QRectF()
        return QRectF(button.geometry()).adjusted(0.5, 0.5, -0.5, -0.5)

    def _sync_to_button(self, button):
        if sip is not None and sip.isdeleted(self):
            return
        rect = self._button_rect(button)
        if rect.isValid() and rect.width() > 0:
            self._start_rect = QRectF(rect)
            self._end_rect = QRectF(rect)
            self._progress = 1.0
            self.update()

    def _animate_to_button(self, button):
        end_rect = self._button_rect(button)
        if not end_rect.isValid() or end_rect.width() <= 0:
            QTimer.singleShot(0, lambda b=button: self._sync_to_button(b))
            return
        if not self._end_rect.isValid() or self._end_rect.width() <= 0:
            self._sync_to_button(button)
            return
        self._start_rect = self._current_blob_rect()
        self._end_rect = QRectF(end_rect)
        self._animation.stop()
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.start()

    def _current_blob_rect(self):
        if not self._start_rect.isValid():
            return QRectF(self._end_rect)
        p = max(0.0, min(1.0, self._progress))
        start_center = self._start_rect.center()
        end_center = self._end_rect.center()
        cx = start_center.x() + (end_center.x() - start_center.x()) * p
        cy = start_center.y() + (end_center.y() - start_center.y()) * p
        width = self._start_rect.width() + (self._end_rect.width() - self._start_rect.width()) * p
        height = self._start_rect.height() + (self._end_rect.height() - self._start_rect.height()) * p
        distance = abs(end_center.x() - start_center.x())
        width += distance * math.sin(math.pi * p) * 0.34
        return QRectF(cx - width / 2, cy - height / 2, width, height)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        checked = self.findChild(QPushButton)
        for button in self.findChildren(QPushButton):
            if button.isChecked():
                checked = button
                break
        if checked:
            QTimer.singleShot(0, lambda b=checked: self._sync_to_button(b))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        outer = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setPen(QPen(self._border, 1))
        painter.setBrush(QBrush(self._bg))
        painter.drawRoundedRect(outer, outer.height() / 2, outer.height() / 2)

        blob = self._current_blob_rect()
        if blob.isValid() and blob.width() > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self._accent))
            painter.drawRoundedRect(blob, blob.height() / 2, blob.height() / 2)
        painter.end()

    def getGooeyProgress(self):
        return self._progress

    def setGooeyProgress(self, value):
        self._progress = float(value)
        self.update()

    gooeyProgress = pyqtProperty(float, fget=getGooeyProgress, fset=setGooeyProgress)


class HeatmapShapeButton(QPushButton):
    """Paints the shape picker tile without native square button fills."""
    def __init__(self, background_color, border_color, accent_color, parent=None):
        super().__init__("", parent)
        self._background_color = QColor(background_color)
        self._border_color = QColor(border_color)
        self._accent_color = QColor(accent_color)
        self._accent_icon = QIcon()
        self.setCheckable(True)
        self.setFlat(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setStyleSheet("QPushButton { background: transparent; border: none; padding: 0; margin: 0; }")

    def setAccentIcon(self, icon):
        self._accent_icon = icon if icon is not None else QIcon()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)

        is_active = self.isChecked() or self.isDown()
        border_color = self._accent_color if (is_active or self.underMouse()) else self._border_color

        painter.fillPath(path, QBrush(self._background_color))
        painter.setPen(QPen(border_color, 2))
        painter.drawPath(path)

        icon = self._accent_icon if self.isChecked() and not self._accent_icon.isNull() else self.icon()
        if not icon.isNull():
            icon_size = self.iconSize()
            pixmap = icon.pixmap(icon_size)
            x = (self.width() - icon_size.width()) // 2
            y = (self.height() - icon_size.height()) // 2
            painter.drawPixmap(x, y, pixmap)


class LanguageOptionRow(QFrame):
    """Rounded language option container with explicit hover painting."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._background_color = QColor("#ffffff")
        self._hover_color = QColor("#e9e9e9")
        self._border_color = QColor("#dcdde1")
        self._hovered = False
        self._radius = 14
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setFrameShape(QFrame.Shape.NoFrame)

    def setColors(self, background_color, hover_color, border_color):
        self._background_color = QColor(background_color)
        self._hover_color = QColor(hover_color)
        self._border_color = QColor(border_color)
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)

        painter.fillPath(path, QBrush(self._hover_color if self._hovered else self._background_color))
        painter.setPen(QPen(self._border_color, 1))
        painter.drawPath(path)


class LanguageSelectorButton(QPushButton):
    """Always paints as a gooey circle, independent of the native button style."""
    def __init__(self, parent=None):
        super().__init__("", parent)
        self._accent_color = QColor("#00A982")
        self._border_color = QColor("#e0e0e0")
        self._fill_progress = 0.0
        self._hover_progress = 0.0
        self._gooey_amount = 0.0
        self._gooey_direction = 1.0
        self.setCheckable(True)
        self.setFlat(True)
        self.setFixedSize(22, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("QPushButton#languageSelector { background: transparent; border: none; padding: 0; margin: 0; }")

        self._fill_animation = QPropertyAnimation(self, b"fill_progress", self)
        self._fill_animation.setDuration(190)
        self._fill_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._hover_animation = QPropertyAnimation(self, b"hover_progress", self)
        self._hover_animation.setDuration(150)
        self._hover_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._gooey_animation = QPropertyAnimation(self, b"gooey_amount", self)
        self._gooey_animation.setDuration(260)
        self._gooey_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.toggled.connect(self._start_gooey_animation)

    @pyqtProperty(float)
    def fill_progress(self):
        return self._fill_progress

    @fill_progress.setter
    def fill_progress(self, value):
        self._fill_progress = max(0.0, min(1.0, float(value)))
        self.update()

    @pyqtProperty(float)
    def hover_progress(self):
        return self._hover_progress

    @hover_progress.setter
    def hover_progress(self, value):
        self._hover_progress = max(0.0, min(1.0, float(value)))
        self.update()

    @pyqtProperty(float)
    def gooey_amount(self):
        return self._gooey_amount

    @gooey_amount.setter
    def gooey_amount(self, value):
        self._gooey_amount = max(0.0, min(1.0, float(value)))
        self.update()

    def setChecked(self, checked):
        super().setChecked(checked)
        if self.signalsBlocked() or not self.isVisible():
            self._fill_animation.stop()
            self._gooey_animation.stop()
            self._gooey_amount = 0.0
            self._fill_progress = 1.0 if checked else 0.0
            self.update()

    def setColors(self, accent_color, border_color):
        self._accent_color = QColor(accent_color)
        self._border_color = QColor(border_color)
        self.update()

    def enterEvent(self, event):
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def _animate_hover(self, end_value):
        self._hover_animation.stop()
        self._hover_animation.setStartValue(self._hover_progress)
        self._hover_animation.setEndValue(float(end_value))
        self._hover_animation.start()

    def _start_gooey_animation(self, checked):
        if self.signalsBlocked() or not self.isVisible():
            self._fill_progress = 1.0 if checked else 0.0
            self._gooey_amount = 0.0
            self.update()
            return

        self._gooey_direction = 1.0 if checked else -1.0
        self._fill_animation.stop()
        self._fill_animation.setStartValue(self._fill_progress)
        self._fill_animation.setEndValue(1.0 if checked else 0.0)
        self._fill_animation.start()

        self._gooey_animation.stop()
        if checked:
            self._gooey_animation.setStartValue(1.0)
            self._gooey_animation.setEndValue(0.0)
            self._gooey_animation.start()
        else:
            self._gooey_amount = 0.0

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        center = rect.center()
        radius = rect.width() / 2.0
        border_color = self._accent_color if (self.isChecked() or self.underMouse() or self.isDown() or self._hover_progress > 0.01) else self._border_color
        border_width = 2.0 + (0.6 * self._hover_progress)

        painter.setPen(QPen(border_color, border_width))
        painter.setBrush(QBrush(QColor(0, 0, 0, 0)))
        painter.drawEllipse(rect)

        if self._hover_progress > 0.01 and not self.isChecked():
            hover_color = QColor(self._accent_color)
            hover_color.setAlpha(int(22 * self._hover_progress))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(hover_color))
            painter.drawEllipse(rect.adjusted(2, 2, -2, -2))

        if self._fill_progress <= 0.01 and self._gooey_amount <= 0.01:
            return

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._accent_color))

        fill_radius = max(0.0, (radius - 2.8) * self._fill_progress)
        if fill_radius <= 0.1:
            return

        painter.save()
        clip_path = QPainterPath()
        clip_path.addEllipse(rect.adjusted(1.5, 1.5, -1.5, -1.5))
        painter.setClipPath(clip_path)

        effective_gooey = self._gooey_amount * min(1.0, self._fill_progress * 2.0)
        squash_x = 1.0 + (0.16 * effective_gooey)
        squash_y = 1.0 - (0.10 * effective_gooey)
        painter.drawEllipse(
            QRectF(
                center.x() - (fill_radius * squash_x),
                center.y() - (fill_radius * squash_y),
                fill_radius * 2 * squash_x,
                fill_radius * 2 * squash_y,
            )
        )
        painter.restore()


class LockOverlay(QWidget):
    """Centered lock overlay used for read-only color panels."""
    def __init__(self, parent=None, mode=None):
        super().__init__(parent)
        self.mode = mode
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        center = QPointF(max(14, self.width() - 18), self.height() / 2)
        is_dark_surface = self.mode == "dark" or (self.mode is None and theme_manager.night_mode)
        AnimatedToggleButton.draw_lock_icon(
            painter,
            center,
            "#ffffff" if is_dark_surface else "#111827",
            1.65,
        )
        painter.end()


class LockableColorPill(QWidget):
    """Wraps a color pill so sync locks can cover it individually."""
    def __init__(self, button, parent=None, mode=None):
        super().__init__(parent)
        self.button = button
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(button)
        self.lock_overlay = LockOverlay(self, mode=mode)
        self.lock_overlay.raise_()

    def setLocked(self, locked):
        self.button.setEnabled(not locked)
        self.lock_overlay.setVisible(bool(locked))
        if locked:
            self.lock_overlay.setGeometry(self.rect())
            self.lock_overlay.raise_()
            self.lock_overlay.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.lock_overlay.setGeometry(self.rect())


class MainBackgroundEffectSlider(QSlider):
    """Rounded, segmented slider used by the main background effect controls."""
    def __init__(self, accent_color, track_color, border_color, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._accent_color = QColor(accent_color)
        self._track_color = QColor(track_color)
        self._border_color = QColor(border_color)
        self._handle_color = QColor("#ffffff")
        self.setFixedHeight(30)
        self.setMouseTracking(True)

    def wheelEvent(self, event):
        event.ignore()

    @staticmethod
    def draw_lock_icon(painter, center, color, scale=1.0):
        AnimatedToggleButton.draw_lock_icon(painter, center, color, scale)

    def setColors(self, accent_color, track_color, border_color):
        self._accent_color = QColor(accent_color)
        self._track_color = QColor(track_color)
        self._border_color = QColor(border_color)
        self.update()

    def sizeHint(self):
        hint = super().sizeHint()
        return QSize(max(220, hint.width()), 30)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        locked = not self.isEnabled()

        paint_pad = 4
        track_height = 22
        handle_radius = (track_height / 2) - 3
        track_left = paint_pad
        track_right = max(track_left + track_height + 1, self.width() - paint_pad)
        track_width = track_right - track_left
        track_top = (self.height() - track_height) / 2
        track_rect = QRectF(track_left, track_top, track_width, track_height)
        handle_min_x = track_rect.left() + (track_height / 2)
        handle_max_x = track_rect.right() - (track_height / 2)

        value_range = max(1, self.maximum() - self.minimum())
        progress = max(0.0, min(1.0, (self.value() - self.minimum()) / value_range))
        handle_x = handle_min_x + (handle_max_x - handle_min_x) * progress

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(self._track_color))
        painter.drawRoundedRect(track_rect, track_height / 2, track_height / 2)

        if progress <= 0.0:
            active_width = 0.0
        elif progress >= 1.0:
            active_width = track_width
        else:
            active_width = min(track_width, max(0.0, handle_x + handle_radius - track_left))
        if active_width > 0:
            active_rect = QRectF(track_left, track_top, active_width, track_height)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(self._accent_color))
            painter.drawRoundedRect(active_rect, track_height / 2, track_height / 2)

        for step in range(1, 6):
            x = track_left + track_width * step / 6
            if x <= track_left + active_width:
                continue
            mark_color = QColor(self._border_color)
            mark_color.setAlpha(95)
            painter.setPen(QPen(mark_color, 1))
            painter.drawLine(QPointF(x, track_top + 4), QPointF(x, track_top + track_height - 4))

        handle_rect = QRectF(
            handle_x - handle_radius,
            (self.height() / 2) - handle_radius,
            handle_radius * 2,
            handle_radius * 2,
        )
        painter.setBrush(QBrush(self._handle_color))
        painter.setPen(QPen(self._accent_color, 3))
        painter.drawEllipse(handle_rect)
        if locked:
            self.draw_lock_icon(
                painter,
                QPointF(handle_rect.center().x(), handle_rect.center().y()),
                "#6b7280" if not theme_manager.night_mode else "#6f6f6f",
                0.88,
            )


class PillSegmentButton(QPushButton):
    """A segmented button that is painted as a pill in every Qt state."""
    def __init__(self, text, bg, fg, checked_bg, checked_fg="#ffffff", hover_bg=None, checkable=True, parent=None):
        super().__init__(text, parent)
        self._pill_bg = QColor(bg)
        self._pill_fg = QColor(fg)
        self._pill_checked_bg = QColor(checked_bg)
        self._pill_checked_fg = QColor(checked_fg)
        self._pill_hover_bg = QColor(hover_bg or bg)
        self.setCheckable(checkable)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)
        self.setStyleSheet("QPushButton { border: none; background: transparent; padding: 0px; }")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2

        if not self.isEnabled():
            bg = QColor(self._pill_bg)
            bg.setAlpha(140)
            fg = QColor(self._pill_fg)
            fg.setAlpha(150)
        elif self.isChecked() or self.isDown():
            bg = QColor(self._pill_checked_bg)
            fg = QColor(self._pill_checked_fg)
        elif self.underMouse():
            bg = QColor(self._pill_hover_bg)
            fg = QColor(self._pill_fg)
        else:
            bg = QColor(self._pill_bg)
            fg = QColor(self._pill_fg)

        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.fillPath(path, QBrush(bg))
        painter.setPen(fg)
        painter.setFont(self.font())
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text())
        painter.end()


class ProfileBarWidget(QWidget):
    """Barra de perfil na sidebar — fundo branco, avatar circular, nome escuro."""
    clicked = pyqtSignal()

    def __init__(self, user_name, pic_path, bg_mode, bg_config, accent_color, parent=None, pic_config=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(58)
        self.setToolTip("Abrir configurações de perfil")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        self._pic_path = pic_path
        self._user_name = user_name
        self._bg_mode = bg_mode
        self._bg_config = bg_config or {}
        self._accent_color = accent_color
        self._bg_image_path = self._bg_config.get("image", "")
        self._using_default_bg = False
        if self._bg_mode != "image":
            self._bg_image_path = ""
        elif not self._bg_image_path or not os.path.exists(self._bg_image_path):
            default_bg = os.path.join(ADDON_ROOT, "system_files", "profile_default", "onigiri-bg.png")
            if os.path.exists(default_bg):
                self._bg_image_path = default_bg
                self._using_default_bg = True
        self._bg_pixmap = QPixmap(self._bg_image_path) if self._bg_image_path and os.path.exists(self._bg_image_path) else QPixmap()
        self._bg_blur = max(0, min(100, int(self._bg_config.get("blur", 0) or 0)))
        self._bg_opacity = max(0.0, min(1.0, float(self._bg_config.get("opacity", 100) if self._bg_config.get("opacity", 100) is not None else 100) / 100.0))
        self._pic_config = pic_config or {}
        self._name_color_override = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 12, 6)
        layout.setSpacing(12)

        # Avatar circular
        self.pic_label = QLabel()
        self.pic_label.setFixedSize(38, 38)
        self.pic_label.setStyleSheet("background: transparent; border: none;")

        circular_pixmap = self._render_avatar_pixmap(38)
        if not circular_pixmap.isNull():
            self.pic_label.setPixmap(circular_pixmap)

        # Nome
        text_widget = QWidget()
        text_widget.setStyleSheet("background: transparent;")
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)

        self.name_label = QLabel(user_name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        name_color = "#f9fafb" if theme_manager.night_mode else "#111827"
        self.name_label.setStyleSheet(
            f"font-weight: 500; font-size: 16px; color: {name_color}; background: transparent;"
        )
        text_layout.addStretch()
        text_layout.addWidget(self.name_label)
        text_layout.addStretch()

        layout.addWidget(self.pic_label)
        layout.addWidget(text_widget, 1)

        try:
            from gamification import nook_level
            rl_payload = nook_level.manager.get_progress_payload()
            if rl_payload.get("enabled") and rl_payload.get("showProfileBar"):
                chip_widget = QWidget()
                chip_bg = "rgba(0, 0, 0, 0.24)" if theme_manager.night_mode else "rgba(255, 255, 255, 0.16)"
                chip_widget.setStyleSheet(f"background: {chip_bg}; border-radius: 12px;")
                chip_widget.setFixedHeight(24)
                chip_layout = QHBoxLayout(chip_widget)
                chip_layout.setContentsMargins(10, 0, 10, 0)
                chip_layout.setSpacing(10)
                
                lvl_label = QLabel(f"Level {rl_payload.get('level', 0)}")
                name_color = "#ffffff" if self._bg_mode == "image" else ("#f9fafb" if theme_manager.night_mode else "#111827")
                lvl_label.setStyleSheet(f"font-weight: 600; font-size: 12px; color: {name_color}; background: transparent;")
                
                prog_bg = QWidget()
                prog_bg.setFixedSize(72, 6)
                prog_bg_color = "rgba(0, 0, 0, 0.35)" if theme_manager.night_mode else "rgba(255, 255, 255, 0.25)"
                prog_bg.setStyleSheet(f"background: {prog_bg_color}; border-radius: 3px;")
                
                percent = rl_payload.get("progressFraction") or 0.0
                percent = max(0.0, min(1.0, float(percent)))
                if rl_payload.get("xpToNextLevel", 0) == 0:
                    percent = 0
                fill_width = int(72 * percent)
                if fill_width > 0:
                    prog_fill = QWidget(prog_bg)
                    prog_fill.setFixedSize(fill_width, 6)
                    theme_color = nook_level.manager.get_current_theme_color() or "#ffb347"
                    prog_fill.setStyleSheet(f"background: {theme_color}; border-radius: 3px;")
                
                chip_layout.addWidget(lvl_label)
                chip_layout.addWidget(prog_bg)
                
                layout.addWidget(chip_widget)
        except Exception:
            pass

        self.refresh_theme()

    def _profile_background_color(self):
        if self._bg_mode in ("custom", "image"):
            return QColor(self._bg_config.get("color") or self._accent_color)
        return QColor(self._accent_color)

    def _avatar_background_color(self):
        bg = self._profile_background_color()
        return bg.lighter(130) if bg.lightness() < 128 else bg.darker(105)

    def _render_avatar_pixmap(self, size):
        mode = self._pic_config.get("mode", "image")
        color = QColor(self._pic_config.get("color") or self._avatar_background_color())
        use_default_pic = not self._pic_path or not os.path.exists(self._pic_path)
        if mode in {"accent", "custom"}:
            dpr = 2.0
            target = QPixmap(size * 2, size * 2)
            target.setDevicePixelRatio(dpr)
            target.fill(Qt.GlobalColor.transparent)
            painter = QPainter(target)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setBrush(QBrush(QColor(self._accent_color) if mode == "accent" else color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QRectF(0, 0, size, size))
            painter.setPen(QColor("#111827") if color.lightness() > 150 and mode != "accent" else QColor("#ffffff"))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(max(12, int(size * 0.52)))
            painter.setFont(font)
            painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, (self._user_name[:1] or "U").upper())
            painter.end()
            return target

        if self._pic_path and os.path.exists(self._pic_path):
            source_image = QImage(self._pic_path)
        else:
            default_pic = os.path.join(ADDON_ROOT, "system_files", "profile_default", "onigiri-san.png")
            source_image = QImage(default_pic)
        if source_image.isNull():
            return QPixmap()
        pixmap = create_circular_contained_pixmap(source_image, size, color, cover=not use_default_pic)
        blur = max(0, min(100, int(self._pic_config.get("blur", 0) or 0)))
        opacity = max(0.0, min(1.0, float(self._pic_config.get("opacity", 100) if self._pic_config.get("opacity", 100) is not None else 100) / 100.0))
        if blur > 0:
            pixmap = self._blur_pixmap(pixmap, blur * 0.2)
        if opacity < 1.0 and not pixmap.isNull():
            faded = QPixmap(pixmap.size())
            faded.setDevicePixelRatio(pixmap.devicePixelRatio())
            faded.fill(Qt.GlobalColor.transparent)
            painter = QPainter(faded)
            painter.setOpacity(opacity)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
            pixmap = faded
        return pixmap

    def _custom_name_color(self):
        from ._common import theme_manager, mw
        override = getattr(self, "_name_color_override", None)
        if override is not None:
            enabled, light, dark, dynamic = override
        else:
            enabled = mw.col.conf.get("modern_menu_profile_name_color_enabled", False)
            dynamic = mw.col.conf.get("modern_menu_profile_name_dynamic_mode", True)
            light = mw.col.conf.get("modern_menu_profile_name_color_light", "#111827")
            dark = mw.col.conf.get("modern_menu_profile_name_color_dark", "#f9fafb")
        if not enabled:
            return None
        if not dynamic:
            return light
        return dark if theme_manager.night_mode else light

    def set_name_color_override(self, enabled, light, dark, dynamic):
        self._name_color_override = (bool(enabled), light, dark, bool(dynamic))
        self.refresh_theme()

    def _text_colors(self):
        name, subtitle = self._auto_text_colors()
        override = self._custom_name_color()
        if override and QColor(override).isValid():
            name = override
        return name, subtitle

    def _auto_text_colors(self):
        from ._common import theme_manager, mw
        dynamic_mode = mw.col.conf.get("modern_menu_profile_bg_dynamic_mode", True)
        if self._using_default_bg and dynamic_mode:
            if theme_manager.night_mode:
                return "#f9fafb", "#d1d5db"
            else:
                return "#111827", "#4b5563"
        elif (self._bg_mode == "image" and self._bg_config.get("image")) or self._using_default_bg:
            return "#ffffff", "#d1d5db"

        bg = self._profile_background_color()
        if bg.lightness() > 150:
            return "#111827", "#4b5563"
        return "#ffffff", "#d1d5db"

    def setAccentColor(self, accent_color):
        self._accent_color = accent_color
        self.refresh_theme()

    def update_profile(self, user_name, pic_path, bg_mode, bg_config, pic_config=None):
        self._pic_path = pic_path
        self._user_name = user_name
        self._bg_mode = bg_mode
        self._bg_config = bg_config or {}
        self._bg_image_path = self._bg_config.get("image", "")
        self._using_default_bg = False
        if self._bg_mode != "image":
            self._bg_image_path = ""
        elif not self._bg_image_path or not os.path.exists(self._bg_image_path):
            default_bg = os.path.join(ADDON_ROOT, "system_files", "profile_default", "onigiri-bg.png")
            if os.path.exists(default_bg):
                self._bg_image_path = default_bg
                self._using_default_bg = True
        self._bg_pixmap = QPixmap(self._bg_image_path) if self._bg_image_path and os.path.exists(self._bg_image_path) else QPixmap()
        self._bg_blur = max(0, min(100, int(self._bg_config.get("blur", 0) or 0)))
        self._bg_opacity = max(0.0, min(1.0, float(self._bg_config.get("opacity", 100) if self._bg_config.get("opacity", 100) is not None else 100) / 100.0))
        self._pic_config = pic_config or {}

        circular_pixmap = self._render_avatar_pixmap(38)
        self.pic_label.setPixmap(circular_pixmap if not circular_pixmap.isNull() else QPixmap())
        self.name_label.setText(user_name)
        self.refresh_theme()

    def refresh_theme(self):
        name_color, _ = self._text_colors()
        self.name_label.setStyleSheet(
            f"font-weight: 500; font-size: 16px; color: {name_color}; background: transparent;"
        )
        self.update()

    def _blur_pixmap(self, pixmap, radius):
        if pixmap.isNull() or radius <= 0:
            return pixmap
        scene = QGraphicsScene()
        item = QGraphicsPixmapItem(pixmap)
        effect = QGraphicsBlurEffect()
        effect.setBlurRadius(radius)
        item.setGraphicsEffect(effect)
        scene.addItem(item)
        scene.setSceneRect(QRectF(0, 0, pixmap.width(), pixmap.height()))
        blurred = QPixmap(pixmap.size())
        blurred.fill(Qt.GlobalColor.transparent)
        painter = QPainter(blurred)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        scene.render(painter)
        painter.end()
        return blurred

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)

        painter.setClipPath(path)
        
        # Always draw the background color first
        painter.fillPath(path, self._profile_background_color())
        
        if (self._bg_mode == "image" or self._using_default_bg) and not self._bg_pixmap.isNull():
            scale_factor = 1.0 + (self._bg_blur * 0.2 / 50.0) if self._bg_blur > 0 else 1.0
            scaled_size = QSize(int(self.width() * scale_factor), int(self.height() * scale_factor))
            scaled = self._bg_pixmap.scaled(
                scaled_size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (scaled.width() - self.width()) // 2
            y = (scaled.height() - self.height()) // 2
            cropped = scaled.copy(x, y, self.width(), self.height())
            if self._bg_blur > 0:
                cropped = self._blur_pixmap(cropped, self._bg_blur * 0.2)
            painter.setOpacity(self._bg_opacity)
            painter.drawPixmap(0, 0, cropped)
            painter.setOpacity(1.0)
            
            painter.fillPath(path, QColor(0, 0, 0, PROFILE_BAR_IMAGE_OVERLAY_ALPHA))

        painter.setClipping(False)
        border = QColor(255, 255, 255, 38) if theme_manager.night_mode else QColor(17, 24, 39, 25)
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(rect, radius, radius)
        painter.end()

        super().paintEvent(event)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class ResponsiveHBoxWidget(QWidget):
    """Wraps a simple horizontal row into multiple lines on narrow settings pages."""
    def __init__(self, parent=None, spacing=8):
        super().__init__(parent)
        self.flow_layout = FlowLayout(self, margin=0, spacing=spacing)
        self.flow_layout.setContentsMargins(0, 0, 0, 0)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def addWidget(self, widget):
        self.flow_layout.addWidget(widget)

    def addSpacing(self, spacing):
        spacer = QWidget()
        spacer.setFixedSize(spacing, 1)
        self.flow_layout.addWidget(spacer)


class ResponsivePairWidget(QWidget):
    """Keeps paired setting panels usable: two columns (optionally uneven), or stacked on narrow widths."""
    def __init__(self, left_widget, right_widget, parent=None, spacing=12, breakpoint=760, left_stretch=1, right_stretch=1, left_alignment=None, right_alignment=None):
        super().__init__(parent)
        self.left_widget = left_widget
        self.right_widget = right_widget
        self.breakpoint = breakpoint
        self.left_stretch = left_stretch
        self.right_stretch = right_stretch
        self.left_alignment = left_alignment or Qt.AlignmentFlag(0)
        self.right_alignment = right_alignment or Qt.AlignmentFlag(0)
        self._stacked = None
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(spacing)
        self.grid.setColumnStretch(0, self.left_stretch)
        self.grid.setColumnStretch(1, self.right_stretch)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._apply_layout(stacked=False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_layout(stacked=self.width() < self.breakpoint)

    def _apply_layout(self, stacked):
        if self._stacked == stacked:
            return
        self._stacked = stacked
        self.grid.removeWidget(self.left_widget)
        self.grid.removeWidget(self.right_widget)
        if stacked:
            self.grid.addWidget(self.left_widget, 0, 0, self.left_alignment)
            self.grid.addWidget(self.right_widget, 1, 0, self.right_alignment)
            self.grid.setColumnStretch(0, 1)
            self.grid.setColumnStretch(1, 0)
        else:
            self.grid.addWidget(self.left_widget, 0, 0, self.left_alignment)
            self.grid.addWidget(self.right_widget, 0, 1, self.right_alignment)
            self.grid.setColumnStretch(0, self.left_stretch)
            self.grid.setColumnStretch(1, self.right_stretch)


class RoundedScrollArea(QScrollArea):
    """A QScrollArea that clips its viewport to a rounded rectangle.
    This ensures the pill shape is always properly rounded even when scrolling."""
    def __init__(self, radius=25, parent=None):
        super().__init__(parent)
        self._radius = radius
        # Install event filter on the viewport so we can respond to resize events
        self.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.viewport() and event.type() == QEvent.Type.Resize:
            self._apply_mask()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_mask()

    def _apply_mask(self):
        vp = self.viewport()
        # Use a QBitmap for pixel-perfect rounded masking (no polygon approximation error)
        bm = QBitmap(vp.size())
        bm.fill(Qt.GlobalColor.color0)  # transparent/clear
        painter = QPainter(bm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(Qt.GlobalColor.color1)  # white = opaque
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, vp.width(), vp.height(), self._radius, self._radius)
        painter.end()
        vp.setMask(bm)


# --- MERGED FROM _widgets_3.py ---

class SearchResultWidget(QPushButton):
    def __init__(self, title, subtitle, target_page, parent=None):
        super().__init__(parent)
        self.target_page = target_page
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(70)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(4)
        
        # Determine colors based on theme
        if theme_manager.night_mode:
            bg_color = "#3a3a3a"
            text_color = "#e0e0e0"
            sub_text_color = "#aaaaaa"
            hover_bg = "#4a4a4a"
            border_color = "#3a3a3a"
        else:
            bg_color = "#dddddd"
            text_color = "#212121"
            sub_text_color = "#555555"
            hover_bg = "#e0e0e0"
            border_color = "#dddddd"

        # Resolve real accent color from theme
        current_theme = mw.col.conf.get("modern_menu_theme", "Tokyo Drift")
        accent_color = "#00A982"
        if current_theme in THEMES:
            mode = "dark" if theme_manager.night_mode else "light"
            accent_color = THEMES[current_theme][mode].get("--accent-color", accent_color)

        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {text_color}; background: transparent;")
        layout.addWidget(title_label)
        
        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setWordWrap(True)
            sub_label.setStyleSheet(f"font-size: 12px; color: {sub_text_color}; background: transparent;")
            layout.addWidget(sub_label)
            
        self.setObjectName("searchResult")


class SectionGroup(QWidget):
    """Flat section wrapper that provides title/spacing without outer chrome."""
    def __init__(self, title="", parent=None, border=True, description=""):
        super().__init__(parent)
        self.setObjectName("settingsSection")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(0, 8, 0, 12)

        self.header_layout = None
        if title:
            self.header_layout = QHBoxLayout()
            self.header_layout.setContentsMargins(0, 0, 0, 0)
            self.header_layout.setSpacing(8)
            title_label = QLabel(title)
            title_label.setObjectName("sectionTitle")
            self.header_layout.addWidget(title_label)
            self.header_layout.addStretch()
            main_layout.addLayout(self.header_layout)

        if description:
            desc_label = QLabel(description)
            desc_label.setObjectName("sectionDescription")
            desc_label.setWordWrap(True)
            main_layout.addWidget(desc_label)

        self.content_area = QWidget()
        self.content_area.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        if border:
            self.content_area.setObjectName("sectionBody")

        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(0, 2, 0, 0)
        self.content_layout.setSpacing(10)
        main_layout.addWidget(self.content_area)

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)

    def add_header_widget(self, widget):
        if self.header_layout:
            self.header_layout.addWidget(widget)


class SelectionOverlay(QWidget):
    """Overlay de seleção — ícone de check minimalista sobre thumbnails."""
    def __init__(self, parent=None, accent_color="#00A982"):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self._checked = False
        self.accent_color = QColor(accent_color)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def setChecked(self, checked):
        self._checked = checked
        self.update()

    def setAccentColor(self, accent_color):
        self.accent_color = QColor(accent_color)
        self.update()

    def isChecked(self):
        return self._checked

    def paintEvent(self, event):
        if not self._checked:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Círculo sólido com a cor accent
        painter.setBrush(self.accent_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(self.rect())
        # Checkmark branco
        pen = QPen(QColor("#ffffff"))
        pen.setWidth(2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        path = QPainterPath()
        path.moveTo(6, 11)
        path.lineTo(9, 14)
        path.lineTo(16, 7)
        painter.drawPath(path)


class _DeferredEntry:
    """Lightweight holder for a search entry whose cross-language term list is
    expanded lazily (on first search) instead of when Settings opens."""
    __slots__ = ("label", "target_page", "keys", "aliases")

    def __init__(self, label, target_page, keys, aliases):
        self.label = label
        self.target_page = target_page
        self.keys = keys
        self.aliases = aliases


class _DeferredSectionAliases:
    """Lightweight holder for a section's alias terms, expanded lazily."""
    __slots__ = ("pages", "keys", "aliases")

    def __init__(self, pages, keys, aliases):
        self.pages = pages
        self.keys = keys
        self.aliases = aliases


class SettingsSearchPage(QWidget):
    page_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("pageContainer")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 0)
        self.layout.setSpacing(14)

        # --- Search Bar ---
        self.search_bar = QLineEdit()
        self.search_bar.setObjectName("settingsSearchInput")
        self.search_bar.setPlaceholderText(tr("search_settings_placeholder"))
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.setMinimumHeight(46)
        self.search_bar.textChanged.connect(self._filter_cards)
        self.layout.addWidget(self.search_bar)

        # --- Scroll Area for Cards ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent;")
        
        self.content_wrapper = QWidget()
        self.wrapper_layout = QVBoxLayout(self.content_wrapper)
        self.wrapper_layout.setContentsMargins(0, 0, 0, 0)
        self.wrapper_layout.setSpacing(0)

        # Cards Container (List)
        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setSpacing(12)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.wrapper_layout.addWidget(self.cards_container)

        # Results Container (List)
        self.results_container = QWidget()
        self.results_layout = QVBoxLayout(self.results_container)
        self.results_layout.setSpacing(10)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.wrapper_layout.addWidget(self.results_container)
        self.results_container.hide()
        
        self.scroll_area.setWidget(self.content_wrapper)
        self.layout.addWidget(self.scroll_area)

        self.cards = []
        self._terms_ready = False
        self._create_cards()

    @staticmethod
    @functools.lru_cache(maxsize=4096)
    def _normalize_search_text(value):
        if value is None:
            return ""
        text = str(value)
        spaced = []
        previous = ""
        for char in text:
            if previous and previous.islower() and char.isupper():
                spaced.append(" ")
            spaced.append(char)
            previous = char
        text = "".join(spaced).casefold()
        normalized = unicodedata.normalize("NFKD", text)
        cleaned = []
        for char in normalized:
            if unicodedata.category(char) == "Mn":
                continue
            cleaned.append(char if char.isalnum() else " ")
        return " ".join("".join(cleaned).split())

    @classmethod
    def _search_matches(cls, query, terms):
        if not query:
            return False
        query_compact = query.replace(" ", "")
        query_tokens = query.split()
        for term in terms:
            normalized = cls._normalize_search_text(term)
            if not normalized:
                continue
            normalized_compact = normalized.replace(" ", "")
            if query in normalized or query_compact in normalized_compact:
                return True
            if query_tokens and all(token in normalized for token in query_tokens):
                return True
        return False

    # Translations are static for the session, so the (label-key -> term list)
    # expansion is cached at class level and reused across every Settings open.
    _translation_terms_cache = {}

    def _translation_terms(self, keys):
        if isinstance(keys, str):
            keys = [keys]
        cache_key = tuple(keys)
        cached = SettingsSearchPage._translation_terms_cache.get(cache_key)
        if cached is not None:
            return cached
        terms = []
        seen = set()
        for key in keys:
            for language_data in TRANSLATIONS.values():
                value = language_data.get(key)
                if not value:
                    continue
                normalized = self._normalize_search_text(value)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    terms.append(value)
        SettingsSearchPage._translation_terms_cache[cache_key] = terms
        return terms

    def _setting_entry(self, label, target_page, keys=None, aliases=None):
        # Defer the cross-language term expansion until the first search so
        # opening Settings (which lands on this page) stays fast.
        return _DeferredEntry(label, target_page, keys or [], list(aliases or []))

    def _section_aliases(self, pages, keys=None, aliases=None):
        return _DeferredSectionAliases(list(pages), keys or [], list(aliases or []))

    def _ensure_search_terms(self):
        """Expand the deferred per-entry / per-section term lists in place.
        Runs once, on the first non-empty search."""
        if self._terms_ready:
            return
        expanded_cards = []
        for card, title, desc, pages, settings, aliases in self.cards:
            new_settings = []
            for item in settings:
                if isinstance(item, _DeferredEntry):
                    terms = [item.label, item.target_page]
                    terms.extend(self._translation_terms(item.keys))
                    terms.extend(item.aliases)
                    new_settings.append((item.label, item.target_page, terms))
                else:
                    new_settings.append(item)
            if isinstance(aliases, _DeferredSectionAliases):
                section_terms = list(aliases.pages)
                section_terms.extend(self._translation_terms(aliases.keys))
                section_terms.extend(aliases.aliases)
            else:
                section_terms = aliases
            expanded_cards.append((card, title, desc, pages, new_settings, section_terms))
        self.cards = expanded_cards
        self._terms_ready = True

    def _create_cards(self):
        # Format: (Title, Description, [Pages], [Keywords])
        # Keywords are tuples of (keyword, target_page) to allow fine-grained navigation
        s = self._setting_entry
        section_aliases = self._section_aliases
        sections = [
            (tr("profile"), tr("profile_desc"), ["Profile"],
             # (keyword, page)
             [s(tr("user_details"), "Profile", "user_details", ["details", "detalhes", "dados", "usuario", "usuário", "account", "conta"]),
              s(tr("profile_picture"), "Profile", "profile_picture", ["avatar", "photo", "foto", "imagem", "picture", "pfp"]),
              s(tr("profile_bar_bg"), "Profile", "profile_bar_bg", ["profile background", "fundo do perfil", "background do perfil"]),
              s(tr("level_bar_color"), "Profile", "level_bar_color", ["xp", "level", "nivel", "nível", "progress", "progresso"]),
              s("Bio", "Profile", aliases=["biography", "biografia", "about", "sobre"]),
              s("Status", "Profile", aliases=["mood", "estado", "estado de perfil"]),
              s("Music", "Profile", aliases=["musica", "música", "song", "spotify"]),
              s("Spotify", "Profile", aliases=["music link", "link de musica", "link de música"]),
              s(tr("user_name"), "Profile", "user_name", ["name", "nome", "username", "apelido"]),
              s(tr("avatar"), "Profile", "avatar", ["profile image", "foto de perfil"])],
             section_aliases(["Profile"], ["profile"], ["perfil", "profil", "プロフィール", "个人资料", "프로필"])),
            (tr("general"), tr("general_desc"), ["Modes", "Languages", "Fonts", "Themes", "Gallery"],
             [s(tr("modes"), "Modes", "modes", ["mode", "modo", "modos", "hide mode", "max mode", "pro mode"]),
              s(tr("hide"), "Modes", "hide", ["hide", "ocultar", "esconder", "hidden"]),
              s(tr("pro"), "Modes", "pro", ["pro mode", "modo pro"]),
              s(tr("max"), "Modes", "max", ["max mode", "modo max", "maximum"]),
              s(tr("languages"), "Languages", "languages", ["language", "idioma", "idiomas", "langue", "语言", "言語", "언어"]),
              s(tr("translation"), "Languages", "translation", ["translate", "traducao", "tradução", "traduire", "translation"]),
              s(tr("portuguese"), "Languages", "portuguese", ["portugues", "português", "pt br", "pt-br"]),
              s(tr("spanish"), "Languages", "spanish", ["espanol", "español", "es-es"]),
              s(tr("english"), "Languages", "english", ["ingles", "inglês", "en"]),
              s(tr("chinese"), "Languages", "chinese", ["chines", "chinês", "中文", "zh"]),
              s(tr("japanese"), "Languages", "japanese", ["japones", "japonês", "日本語", "ja"]),
              s(tr("fonts"), "Fonts", "fonts", ["font", "fonte", "fontes", "police", "typography", "tipografia"]),
              s(tr("text"), "Fonts", "text", ["texto", "body", "corpo"]),
              s(tr("typography"), "Fonts", "typography", ["tipografia", "letter", "letters", "letras"]),
              s(tr("font_size"), "Fonts", "font_size", ["size", "tamanho", "tamanho da fonte"]),
              s(tr("titles"), "Fonts", "titles", ["headers", "headings", "titulos", "títulos"]),
              s(tr("title"), "Fonts", "title", ["titulo", "título", "heading"]),
              s(tr("official_themes"), "Themes", "official_themes", ["official", "oficial"]),
              s(tr("your_themes"), "Themes", "your_themes", ["custom themes", "meus temas", "temas personalizados"]),
              s(tr("themes"), "Themes", "themes", ["theme", "tema", "temas", "appearance", "aparencia", "aparência"]),
              s(tr("gallery"), "Gallery", "gallery", ["galeria", "assets", "library", "biblioteca"]),
              s(tr("colors_gallery"), "Gallery", "colors_gallery", ["colors", "cores", "palette", "paleta"]),
              s(tr("images_gallery"), "Gallery", "images_gallery", ["image gallery", "galeria de imagens"]),
              s(tr("images"), "Gallery", "images", ["imagem", "imagens", "pictures", "fotos"]),
              s(tr("backgrounds"), "Gallery", "backgrounds", ["background", "fundo", "fundos"]),
              s(tr("pictures"), "Gallery", "pictures", ["picture", "foto", "fotos"]),
              s(tr("accent_color"), "Gallery", "accent_color", ["accent", "cor de destaque", "cor principal"])],
             section_aliases(["Modes", "Languages", "Fonts", "Themes", "Gallery"],
                             ["general", "modes", "languages", "fonts", "themes", "gallery"],
                             ["geral", "general settings", "configuracoes gerais", "configurações gerais", "appearance", "aparencia", "aparência"])),
            (tr("menu"), tr("menu_desc"), ["Main menu", "Sidebar"],
             [s(tr("organize"), "Main menu", "organize", ["arrange", "ordenar", "organizar"]),
              s(tr("widget_grid"), "Main menu", "widget_grid", ["widgets", "grid", "grade", "dashboard grid"]),
              s(tr("title"), "Main menu", "title", ["titulo", "título", "heading"]),
              s(tr("stats_title"), "Main menu", "stats_title", ["stats", "estatisticas", "estatísticas", "statistics"]),
              s(tr("heatmap"), "Main menu", "heatmap", ["heat map", "mapa de calor"]),
              s(tr("main_background"), "Main menu", "main_background", ["main background", "fundo principal", "dashboard background"]),
              s(tr("background_image"), "Main menu", "background_image", ["background", "imagem de fundo", "fundo"]),
              s(tr("boxes_color_effect"), "Main menu", "boxes_color_effect", ["boxes", "cards", "caixas", "efeitos", "effects"]),
              s(tr("visibility"), "Main menu", "visibility", ["visible", "mostrar", "ocultar", "visibilidade"]),
              s(tr("congratulations"), "Main menu", "congratulations", ["congrats", "parabens", "parabéns"]),
              s(tr("star_icon"), "Main menu", "star_icon", ["star", "estrela", "icon"]),
              s(tr("sidebar_customization"), "Sidebar", "sidebar_customization", ["sidebar customization", "personalizacao da barra lateral", "personalização da barra lateral"]),
              s(tr("organize_action_buttons"), "Sidebar", "organize_action_buttons", ["action buttons", "botoes de acao", "botões de ação"]),
              s(tr("sidebar_background"), "Sidebar", "sidebar_background", ["sidebar background", "fundo da sidebar", "fundo da barra lateral"]),
              s(tr("sidebar"), "Sidebar", "sidebar", ["side bar", "barra lateral", "navigation", "navegacao", "navegação"]),
              s(tr("save"), "Sidebar", "save", ["save button", "salvar"]),
              s(tr("scroll"), "Sidebar", "scroll", ["rolagem", "scrollbar", "barra de rolagem"]),
              s(tr("deck"), "Sidebar", "deck", ["decks", "baralhos"]),
              s(tr("icon_sizing"), "Sidebar", "icon_sizing", ["icon size", "tamanho dos icones", "tamanho dos ícones"]),
              s(tr("icons"), "Sidebar", "icons", ["icon", "icone", "ícone", "icones", "ícones"])],
             section_aliases(["Main menu", "Sidebar"], ["menu", "main_menu", "sidebar"],
                             ["menu principal", "barra lateral", "side bar", "mainmenu", "dashboard", "navigation", "navegacao", "navegação"])),
            (tr("study_pages"), tr("study_pages_desc"), ["Overviewer", "Reviewer"],
             [s(tr("overviewer_background"), "Overviewer", "overviewer_background", ["overview background", "fundo da visao geral", "fundo da visão geral"]),
              s(tr("overview_style"), "Overviewer", "overview_style", ["overview style", "estilo da visao geral", "estilo da visão geral"]),
              s(tr("overviewer"), "Overviewer", "overviewer", ["overview", "visao geral", "visão geral", "deck overview"]),
              s(tr("congratulations"), "Overviewer", "congratulations", ["congrats", "parabens", "parabéns"]),
              s(tr("reviewer_background"), "Reviewer", "reviewer_background", ["review background", "fundo do revisor"]),
              s(tr("bottom_bar_background"), "Reviewer", "bottom_bar_background", ["bottom bar background", "fundo da barra inferior"]),
              s(tr("answer_buttons"), "Reviewer", "answer_buttons", ["answer buttons", "botoes de resposta", "botões de resposta", "again good easy"]),
              s(tr("reviewer"), "Reviewer", "reviewer", ["review", "reviews", "revisor", "revisao", "revisão", "card review"]),
              s(tr("notification_widget"), "Reviewer", "notification_widget", ["notification", "notificacao", "notificação", "alert"]),
              s(tr("widget_position"), "Reviewer", "widget_position", ["position", "posicao", "posição"]),
              s(tr("bar_background"), "Reviewer", "bar_background", ["bar background", "fundo da barra"]),
              s(tr("corners"), "Reviewer", "corners", ["corner", "cantos"]),
              s(tr("radius"), "Reviewer", "radius", ["border radius", "raio", "arredondamento"]),
              s(tr("shadows"), "Reviewer", "shadows", ["shadow", "sombra", "sombras"]),
              s(tr("scroll"), "Reviewer", "scroll", ["rolagem", "scrollbar"]),
              s(tr("bottom_bar"), "Reviewer", "bottom_bar", ["bottom bar", "barra inferior"]),
              s(tr("button"), "Reviewer", "button", ["buttons", "botao", "botão", "botoes", "botões"]),
              s(tr("grid"), "Reviewer", "grid", ["grade", "layout"]),
              s(tr("widget_grid"), "Overviewer", "widget_grid", ["widgets", "grade de widgets"])],
             section_aliases(["Overviewer", "Reviewer"], ["study_pages", "overviewer", "reviewer"],
                             ["study", "estudo", "paginas de estudo", "páginas de estudo", "review", "revisao", "revisão", "overview", "visao geral", "visão geral"])),
        ]

        for title, desc, pages, settings, aliases in sections:
            card = self._create_card_widget(title, desc, pages)
            # Store settings as list of (keyword, page) tuples
            self.cards.append((card, title, desc, pages, settings, aliases))
            self.cards_layout.addWidget(card)
        
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    def _create_card_widget(self, title, desc, pages):
        card = QFrame()
        card.setObjectName("searchCard")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setMinimumHeight(82)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(5)
        
        title_lbl = QLabel(title)
        title_lbl.setObjectName("searchCardTitle")
        layout.addWidget(title_lbl)
        
        desc_lbl = QLabel(desc)
        desc_lbl.setObjectName("searchCardDescription")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        # Container for matches (initially hidden)
        matches_container = QWidget()
        matches_layout = QVBoxLayout(matches_container)
        matches_layout.setContentsMargins(0, 5, 0, 0)
        matches_layout.setSpacing(2)
        matches_container.hide()
        layout.addWidget(matches_container)
        
        # Store references for dynamic updates
        card.title_label = title_lbl
        card.desc_label = desc_lbl
        card.matches_container = matches_container
        card.matches_layout = matches_layout
        card.match_text_color = "#a8adb8" if theme_manager.night_mode else "#6f7683"
        card.current_target_page = pages[0]
        
        # Use a method for the click handler to access the current target
        card.mousePressEvent = lambda event: self.page_requested.emit(card.current_target_page)
        
        return card

    def _filter_cards(self, text):
        text = self._normalize_search_text(text)
        
        if not text:
            self.results_container.hide()
            self.cards_container.show()
            
            # Clear results to free memory
            while self.results_layout.count():
                child = self.results_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            return

        # Build the search-term index lazily on the first real query.
        self._ensure_search_terms()

        self.cards_container.hide()
        self.results_container.show()

        # Clear previous results
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        results_found = False
        seen_results = set()  # Deduplicate results
        
        for card, title, desc, pages, settings, aliases in self.cards:
            # Check for Title/Desc match
            if self._search_matches(text, [title, desc] + list(aliases)):
                result_key = (title, pages[0])
                if result_key not in seen_results:
                    seen_results.add(result_key)
                    widget = SearchResultWidget(title, desc, pages[0])
                    widget.clicked.connect(lambda _, p=pages[0]: self.page_requested.emit(p))
                    self.results_layout.addWidget(widget)
                    results_found = True

            # Check for Settings keyword match
            # settings is a list of (keyword, target_page) tuples
            for item in settings:
                item_aliases = []
                if isinstance(item, tuple):
                    keyword, target_page = item[0], item[1]
                    if len(item) > 2:
                        item_aliases = item[2]
                else:
                    # Legacy flat string support
                    keyword = item
                    target_page = pages[0]
                    for p in pages:
                        if self._search_matches(self._normalize_search_text(p), [keyword]):
                            target_page = p
                            break

                if self._search_matches(text, [keyword, target_page] + list(item_aliases)):
                    result_key = (keyword, target_page)
                    if result_key not in seen_results:
                        seen_results.add(result_key)
                        widget = SearchResultWidget(keyword, f"In {title}", target_page)
                        widget.clicked.connect(lambda _, p=target_page: self.page_requested.emit(p))
                        self.results_layout.addWidget(widget)
                        results_found = True

        if not results_found:
            no_results = QLabel(tr("no_results_found"))
            no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_results.setStyleSheet("color: #888; font-size: 14px; margin-top: 20px;")
            self.results_layout.addWidget(no_results)
        
        self.results_layout.addStretch()


class SidebarToggleButton(QWidget):
    """Grupo expansível na sidebar — título clicável expande sub-itens."""
    page_selected = pyqtSignal(str)

    def __init__(self, title, items, parent=None):
        super().__init__(parent)
        self.items = items
        self.title = title
        self.is_open = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.toggle_button = QPushButton(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setAutoDefault(False)
        self.toggle_button.setObjectName("mainItemButton")
        self.toggle_button.clicked.connect(self._toggle_content)
        main_layout.addWidget(self.toggle_button)

        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(12, 2, 0, 4)
        self.content_layout.setSpacing(2)

        self.sub_button_group = QButtonGroup()
        self.sub_button_group.setExclusive(True)

        self.sub_buttons = {}
        for item in items:
            if isinstance(item, tuple):
                display_label, internal_key = item
            else:
                display_label, internal_key = item, item

            button = QPushButton(display_label)
            button.setCheckable(True)
            button.setAutoDefault(False)
            button.setObjectName("subItemButton")
            button.clicked.connect(lambda _, key=internal_key: self.page_selected.emit(key))
            self.sub_buttons[internal_key] = button
            self.content_layout.addWidget(button)
            self.sub_button_group.addButton(button)

        main_layout.addWidget(self.content_widget)
        self.content_widget.hide()

    def _toggle_content(self, checked):
        self.is_open = checked
        self.content_widget.setVisible(checked)
        if not checked:
            if btn := self.sub_button_group.checkedButton():
                btn.blockSignals(True)
                btn.setChecked(False)
                btn.blockSignals(False)
                self.page_selected.emit("")

    def select_page(self, page_name):
        if page_name in self.sub_buttons:
            if not self.is_open:
                self.toggle_button.click()
            self.sub_buttons[page_name].setChecked(True)
            return True
        return False

    def deselect_all(self):
        self.toggle_button.setChecked(False)
        self.is_open = False
        self.content_widget.hide()
        if btn := self.sub_button_group.checkedButton():
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)


class SyncHeaderIcon(QWidget):
    """Animated sync icon used by the AnkiWeb Sync settings header."""
    def __init__(self, icon_path, accent_color, inactive_bg, border_color, icon_color, parent=None):
        super().__init__(parent)
        self.setFixedSize(52, 52)
        self._icon_path = icon_path
        self._accent_color = QColor(accent_color)
        self._inactive_bg = QColor(inactive_bg)
        self._border_color = QColor(border_color)
        self._icon_color = QColor(icon_color)
        self._active_progress = 0.0
        self._pulse_phase = 0.0
        self._kick = 0.0
        self._is_active = False
        self._icon_svg = ""
        self._renderer_cache = {}
        if os.path.exists(icon_path):
            try:
                with open(icon_path, "r", encoding="utf-8") as icon_file:
                    self._icon_svg = icon_file.read()
            except OSError:
                self._icon_svg = ""

        self._active_animation = QPropertyAnimation(self, b"active_progress", self)
        self._active_animation.setDuration(220)
        self._active_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._kick_animation = QPropertyAnimation(self, b"kick", self)
        self._kick_animation.setDuration(360)
        self._kick_animation.setEasingCurve(QEasingCurve.Type.OutBack)

        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._tick_pulse)

    def setColors(self, accent_color, inactive_bg, border_color, icon_color):
        self._accent_color = QColor(accent_color)
        self._inactive_bg = QColor(inactive_bg)
        self._border_color = QColor(border_color)
        self._icon_color = QColor(icon_color)
        self.update()

    def setActive(self, active):
        active = bool(active)
        if self._is_active == active:
            return
        self._is_active = active
        self._active_animation.stop()
        self._active_animation.setStartValue(self._active_progress)
        self._active_animation.setEndValue(1.0 if active else 0.0)
        self._active_animation.start()

        self._kick_animation.stop()
        self._kick_animation.setStartValue(1.0 if active else -0.55)
        self._kick_animation.setEndValue(0.0)
        self._kick_animation.start()

        if active and not self._pulse_timer.isActive():
            self._pulse_timer.start(33)
        elif not active:
            self._pulse_timer.stop()
            self._pulse_phase = 0.0
        self.update()

    @pyqtProperty(float)
    def active_progress(self):
        return self._active_progress

    @active_progress.setter
    def active_progress(self, value):
        self._active_progress = max(0.0, min(1.0, float(value)))
        self.update()

    @pyqtProperty(float)
    def kick(self):
        return self._kick

    @kick.setter
    def kick(self, value):
        self._kick = float(value)
        self.update()

    def _tick_pulse(self):
        self._pulse_phase = (self._pulse_phase + 0.024) % 1.0
        self.update()

    @staticmethod
    def _blend_color(start, end, amount):
        amount = max(0.0, min(1.0, float(amount)))
        return QColor(
            round(start.red() + (end.red() - start.red()) * amount),
            round(start.green() + (end.green() - start.green()) * amount),
            round(start.blue() + (end.blue() - start.blue()) * amount),
            round(start.alpha() + (end.alpha() - start.alpha()) * amount),
        )

    def _icon_renderer(self, color):
        if not self._icon_svg:
            return None
        color_name = QColor(color).name()
        renderer = self._renderer_cache.get(color_name)
        if renderer is None:
            svg = self._icon_svg.replace("currentColor", color_name)
            renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")), self)
            if renderer.isValid():
                self._renderer_cache[color_name] = renderer
            else:
                renderer = None
        return renderer

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        progress = self._active_progress
        accent = QColor(self._accent_color)
        active_bg = self._blend_color(self._inactive_bg, accent, 0.16 if theme_manager.night_mode else 0.11)
        bg = self._blend_color(self._inactive_bg, active_bg, progress)

        border = self._blend_color(self._border_color, accent, progress)
        border.setAlpha(255)
        painter.setPen(QPen(border, 1.1))
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, 8, 8)

        if progress > 0.01:
            pulse = (math.sin(self._pulse_phase * math.tau) + 1.0) / 2.0
            halo = QColor(accent)
            halo.setAlpha(int((14 + 20 * pulse) * progress))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(halo)
            inset = 6.0 - (2.5 * pulse)
            painter.drawRoundedRect(rect.adjusted(inset, inset, -inset, -inset), 8, 8)

        icon_color = self._blend_color(self._icon_color, accent, progress)
        renderer = self._icon_renderer(icon_color)
        if renderer:
            center = QPointF(self.width() / 2, self.height() / 2)
            rotation = (360.0 * self._kick) + (math.sin(self._pulse_phase * math.tau) * 5.0 * progress)
            painter.translate(center)
            painter.rotate(rotation)
            painter.translate(-center)
            renderer.render(painter, QRectF(center.x() - 15, center.y() - 15, 30, 30))
        else:
            painter.setPen(QPen(icon_color, 2))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "S")

        painter.end()


class ThemeBackgroundPreview(QWidget):
    """Paints a clipped, centered main-background thumbnail for saved themes."""
    def __init__(self, parent=None, rounded_bottom=True):
        super().__init__(parent)
        self.image_path = ""
        self.fallback_colors = ["#e5e7eb", "#d1d5db", "#cbd5e1"]
        self.rounded_bottom = rounded_bottom
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_preview(self, image_path, fallback_colors):
        self.image_path = image_path or ""
        self.fallback_colors = list(fallback_colors or self.fallback_colors)[:3]
        while len(self.fallback_colors) < 3:
            self.fallback_colors.append(self.fallback_colors[-1] if self.fallback_colors else "#e5e7eb")
        self.setToolTip(os.path.basename(self.image_path) if self.image_path else "")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(0, 0, self.width(), self.height())
        clip_path = QPainterPath()
        if self.rounded_bottom:
            radius = max(4, min(14, self.height() * 0.18))
            clip_path.addRoundedRect(rect, radius, radius)
        else:
            radius = min(18, self.width() / 2, self.height())
            clip_path.moveTo(rect.left(), rect.bottom())
            clip_path.lineTo(rect.left(), rect.top() + radius)
            clip_path.quadTo(rect.left(), rect.top(), rect.left() + radius, rect.top())
            clip_path.lineTo(rect.right() - radius, rect.top())
            clip_path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + radius)
            clip_path.lineTo(rect.right(), rect.bottom())
            clip_path.closeSubpath()
        painter.setClipPath(clip_path)

        if self.image_path:
            pixmap = QPixmap(self.image_path)
            if not pixmap.isNull():
                source = QRectF(pixmap.rect())
                target_ratio = self.width() / max(1, self.height())
                source_ratio = source.width() / max(1, source.height())
                if source_ratio > target_ratio:
                    new_width = source.height() * target_ratio
                    source.setX((source.width() - new_width) / 2)
                    source.setWidth(new_width)
                else:
                    new_height = source.width() / target_ratio
                    source.setY((source.height() - new_height) / 2)
                    source.setHeight(new_height)
                painter.drawPixmap(rect, pixmap, source)
                painter.end()
                return

        gradient = QLinearGradient(0, 0, self.width(), 0)
        gradient.setColorAt(0.0, QColor(self.fallback_colors[0]))
        gradient.setColorAt(0.5, QColor(self.fallback_colors[1]))
        gradient.setColorAt(1.0, QColor(self.fallback_colors[2]))
        painter.fillRect(rect, gradient)
        painter.end()


class ThemePreviewNameLabel(QLabel):
    """Draws the compact theme title without Qt stylesheet font clipping."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._text_color = QColor("#111827")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_text_color(self, color):
        parsed = QColor(str(color))
        self._text_color = parsed if parsed.isValid() else QColor("#111827")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setPen(self._text_color)
        painter.setFont(self.font())

        metrics = painter.fontMetrics()
        text = metrics.elidedText(self.text(), Qt.TextElideMode.ElideRight, max(1, self.width()))
        baseline = int((self.height() - metrics.height()) / 2) + metrics.ascent()
        baseline = max(metrics.ascent(), min(baseline, self.height() - metrics.descent() - 1))
        painter.drawText(0, baseline, text)
        painter.end()


class ThemeCardWidget(QFrame):
    """A clickable card widget to display and select a theme."""
    theme_selected = pyqtSignal(dict)
    delete_requested = pyqtSignal(str) # Signal to request deletion

    def __init__(self, theme_name, theme_data, parent=None, deletable=False, delete_icon=None, preview_mode="light", full_preview=False):
        super().__init__(parent)
        self.theme_name = theme_name
        self.theme_data = theme_data
        self.preview_mode = preview_mode if preview_mode in {"light", "dark"} else "light"
        self.deletable = deletable
        self.full_preview = full_preview
        self._delete_hold_started_at = None
        self._delete_hold_duration_ms = 950
        self._delete_triggered = False

        # Localize official theme names, fallback to original name for user themes
        clean_name = theme_name.lower().replace(' ', '_').replace("'", "").replace('é', 'e').replace('è', 'e')
        trans_key = f"theme_{clean_name}"
        display_name = tr(trans_key, theme_name)
        if isinstance(display_name, str) and display_name.startswith("Catppuccin "):
            display_name = display_name[len("Catppuccin "):]
        self.display_name = display_name

        self.setObjectName("themeCard")
        # Fixed height, but flexible width: the parent FlowLayout (in
        # stretch_rows mode) resizes each row's cards to fill the full grid
        # width, so the card must be allowed to grow horizontally.
        if self.full_preview:
            self.setFixedHeight(118)
            self.setMinimumWidth(154)
        else:
            self.setFixedHeight(74)
            self.setMinimumWidth(138)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        main_layout = QVBoxLayout(self)
        if self.full_preview:
            main_layout.setContentsMargins(5, 2, 5, 0)
        else:
            main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(3 if self.full_preview else 6)

        self.name_label = ThemePreviewNameLabel(display_name) if self.full_preview else QLabel(display_name)
        self.name_label.setObjectName("themeFullPreviewName" if self.full_preview else "themePreviewName")
        self.name_label.setToolTip(display_name)
        self.name_label.setWordWrap(False)

        self.background_preview = None
        self.font_samples = []
        if self.full_preview:
            main_layout.addStretch(1)
            self.background_preview = ThemeBackgroundPreview(rounded_bottom=True)
            self.background_preview.setObjectName("themeBackgroundPreview")
            self.background_preview.setFixedHeight(32)
            main_layout.addWidget(self.background_preview)

            content_widget = QWidget()
            content_widget.setObjectName("themePreviewContent")
            content_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            content_layout = QVBoxLayout(content_widget)
            content_layout.setContentsMargins(0, 0, 0, 0)
            content_layout.setSpacing(1)

            self.font_layout = QHBoxLayout()
            self.font_layout.setSpacing(3)
            self.font_layout.setContentsMargins(0, 0, 0, 0)
            for role, label in (
                ("main", tr("text", "Body")),
                ("subtle", tr("titles", "Titles")),
                ("small_title", tr("small_titles", "Small Titles")),
            ):
                sample = QLabel("A")
                sample.setObjectName("themeFontSample")
                sample.setFixedSize(15, 15)
                sample.setAlignment(Qt.AlignmentFlag.AlignCenter)
                sample.setProperty("font_role", role)
                sample.setProperty("font_label", label)
                self.font_samples.append(sample)
                self.font_layout.addWidget(sample)
            self.font_layout.addStretch()

        self.swatch_layout = QHBoxLayout()
        self.swatch_layout.setSpacing(3 if self.full_preview else 6)
        self.swatch_layout.setContentsMargins(0, 0, 0, 0)
        self.swatches = []
        swatch_count = 6
        for _ in range(swatch_count):
            swatch = QLabel()
            if self.full_preview:
                swatch.setFixedSize(15, 15)
            else:
                swatch.setFixedSize(14, 14)
            swatch.setObjectName("themePreviewSwatch")
            self.swatches.append(swatch)
            self.swatch_layout.addWidget(swatch)
        # Trailing (rather than leading) stretch keeps the swatch row flush with
        # the name label below it, no matter how wide the card is stretched.
        self.swatch_layout.addStretch()
        if self.full_preview:
            content_layout.addLayout(self.font_layout)
            content_layout.addSpacing(1)
            content_layout.addLayout(self.swatch_layout)

            self.name_label.setFixedHeight(30)
            self.name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            content_layout.addWidget(self.name_label)
            main_layout.addWidget(content_widget)
            main_layout.addStretch(1)
        else:
            main_layout.addLayout(self.swatch_layout)

        if not self.full_preview:
            footer_layout = QHBoxLayout()
            footer_layout.setContentsMargins(0, 0, 0, 0)
            footer_layout.setSpacing(6)
            self.name_label.setFixedHeight(18)
            footer_layout.addWidget(self.name_label, 1)
            main_layout.addLayout(footer_layout)

        self.delete_progress = QFrame(self)
        self.delete_progress.setObjectName("themeDeleteProgress")
        self.delete_progress.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.delete_progress.hide()
        self.delete_progress.lower()
        self.delete_hold_timer = QTimer(self)
        self.delete_hold_timer.setInterval(16)
        self.delete_hold_timer.timeout.connect(self._update_delete_hold_progress)

        self.refresh_preview()

    def set_preview_mode(self, mode):
        self.preview_mode = mode if mode in {"light", "dark"} else "light"
        self.refresh_preview()

    def _theme_palette_colors(self):
        preview_colors = self.theme_data.get(self.preview_mode, {})
        fallback_colors = self.theme_data.get("light", {})
        color_keys = [
            "--accent-color", "--button-primary-bg", "--heatmap-color",
            "--star-color", "--bg", "--highlight-bg", "--canvas-inset",
            "--fg-subtle", "--fg", "--border",
        ]
        colors = []
        for key in color_keys:
            value = preview_colors.get(key, fallback_colors.get(key))
            if value and QColor(str(value)).isValid() and value not in colors:
                colors.append(value)
            if len(colors) == 6:
                break

        while len(colors) < 6:
            colors.append("#e5e7eb" if self.preview_mode == "light" else "#3f4652")
        return colors, preview_colors, fallback_colors

    def _flatten_theme_asset_values(self, value):
        if isinstance(value, list):
            flattened = []
            for item in value:
                flattened.extend(self._flatten_theme_asset_values(item))
            return flattened
        return [value] if value else []

    def _resolve_theme_image_path(self, value):
        if not isinstance(value, str) or not value.strip():
            return ""
        value = value.strip()
        if os.path.isabs(value) and os.path.exists(value):
            return value

        normalized = value.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part]
        filename = os.path.basename(normalized)
        candidate_paths = []

        if parts and parts[0] == "images" and len(parts) >= 3:
            candidate_paths.append(os.path.join(ADDON_ROOT, "user_files", parts[1], parts[-1]))
        candidate_paths.extend([
            os.path.join(ADDON_ROOT, normalized),
            os.path.join(ADDON_ROOT, "user_files", normalized),
            os.path.join(ADDON_ROOT, "user_files", "main_bg", filename),
            os.path.join(ADDON_ROOT, "user_files", "images", self.theme_name.lower().replace(" ", "_"), filename),
            os.path.join(ADDON_ROOT, "user_files", "sidebar_bg", filename),
            os.path.join(ADDON_ROOT, "user_files", "reviewer_bg", filename),
        ])

        for path in candidate_paths:
            if path and os.path.exists(path):
                return path
        return ""

    def _theme_main_background_path(self):
        assets = self.theme_data.get("assets", {})
        assets = assets if isinstance(assets, dict) else {}
        images = assets.get("images", {})
        images = images if isinstance(images, dict) else {}

        customization = self.theme_data.get("customization", {})
        customization = customization if isinstance(customization, dict) else {}
        collection_config = customization.get("collection_config", {})
        addon_config = customization.get("addon_config", {})

        sources = [images]
        if isinstance(collection_config, dict):
            sources.append(collection_config)
        if isinstance(addon_config, dict):
            sources.append(addon_config)

        mode_keys = [
            f"modern_menu_background_image_{self.preview_mode}",
            "modern_menu_background_image",
            "modern_menu_slideshow_images",
            f"onigiri_overview_bg_image_{self.preview_mode}",
            "onigiri_overview_bg_image",
            "onigiri_overview_slideshow_images",
        ]
        for source in sources:
            for key in mode_keys:
                for value in self._flatten_theme_asset_values(source.get(key)):
                    resolved = self._resolve_theme_image_path(value)
                    if resolved:
                        return resolved
        return ""

    def _theme_font_config(self):
        assets = self.theme_data.get("assets", {})
        assets = assets if isinstance(assets, dict) else {}
        font_config = assets.get("font_config", {})
        if isinstance(font_config, dict) and font_config:
            return font_config

        customization = self.theme_data.get("customization", {})
        customization = customization if isinstance(customization, dict) else {}
        collection_config = customization.get("collection_config", {})
        if not isinstance(collection_config, dict):
            return {}
        return {
            "main": collection_config.get("onigiri_font_main", "system"),
            "subtle": collection_config.get("onigiri_font_subtle", "system"),
            "small_title": collection_config.get("onigiri_font_small_title", "system"),
        }

    def _font_for_theme_key(self, font_key, size=22):
        all_fonts = get_all_fonts(ADDON_ROOT)
        font_info = all_fonts.get(font_key or "system", all_fonts.get("system", {}))
        if not font_key or font_key == "system":
            font = QFont()
            font.setPointSize(size)
            return font, font_info.get("name", "System")

        family = font_info.get("family", "")
        font_file = font_info.get("file")
        if font_file:
            font_path = os.path.join(
                ADDON_ROOT,
                "user_files" if font_info.get("user") else os.path.join("system_files", "fonts"),
                "fonts" if font_info.get("user") else "system_fonts",
                font_file,
            )
            if os.path.exists(font_path):
                font_id = QFontDatabase.addApplicationFont(font_path)
                if font_id != -1:
                    families = QFontDatabase.applicationFontFamilies(font_id)
                    if families:
                        family = families[0]
        font = QFont(family, size) if family else QFont()
        font.setPointSize(size)
        return font, font_info.get("name", str(font_key or "System"))

    def _refresh_full_preview(self, colors, preview_colors, fallback_colors):
        text_color = preview_colors.get(
            "--fg",
            fallback_colors.get("--fg", "#111827" if self.preview_mode == "light" else "#f9fafb"),
        )
        border_color = preview_colors.get(
            "--border",
            fallback_colors.get("--border", "#d1d5db" if self.preview_mode == "light" else "#454545"),
        )
        card_bg = preview_colors.get(
            "--bg",
            fallback_colors.get("--bg", "#ffffff" if self.preview_mode == "light" else "#242424"),
        )
        hover_border = preview_colors.get("--accent-color", fallback_colors.get("--accent-color", border_color))
        font_chip_bg = preview_colors.get(
            "--highlight-bg",
            fallback_colors.get("--highlight-bg", "#eef0f2" if self.preview_mode == "light" else "#343a40"),
        )

        image_path = self._theme_main_background_path()
        self.background_preview.set_preview(image_path, colors[:3])

        font_config = self._theme_font_config()
        for sample in self.font_samples:
            role = sample.property("font_role")
            role_label = sample.property("font_label") or role
            font_key = font_config.get(role, "system")
            font, font_name = self._font_for_theme_key(font_key, 12)
            sample.setFont(font)
            sample.setToolTip(f"{role_label}: {font_name}")
            sample.setStyleSheet(
                f"background-color: {font_chip_bg}; "
                f"border: 1px solid {border_color}; "
                "border-radius: 5px; "
                f"color: {text_color};"
            )

        for swatch, color in zip(self.swatches, colors):
            swatch.setToolTip(str(color).upper())
            swatch.setStyleSheet(
                f"background-color: {color}; "
                f"border: 1px solid {border_color}; "
                "border-radius: 5px;"
            )

        title_font = QFont(self.name_label.font())
        title_font.setPixelSize(15)
        self.name_label.setFont(title_font)
        if hasattr(self.name_label, "set_text_color"):
            self.name_label.set_text_color(text_color)

        label_width = self.width() - 24
        self.name_label.setText(
            self.name_label.fontMetrics().elidedText(
                self.display_name,
                Qt.TextElideMode.ElideRight,
                max(80, label_width),
            )
        )
        self.setStyleSheet(f"""
            QFrame#themeCard {{
                background-color: {card_bg};
                border: 1px solid {border_color};
                border-radius: 9px;
            }}
            QFrame#themeCard:hover {{
                border-color: {hover_border};
            }}
        """)
        self.delete_progress.setStyleSheet(
            f"background-color: {hover_border}; border: none; border-radius: 9px;"
        )

    def refresh_preview(self):
        colors, preview_colors, fallback_colors = self._theme_palette_colors()
        if self.full_preview:
            self._refresh_full_preview(colors, preview_colors, fallback_colors)
            return

        label_width = self.width() - 20
        self.name_label.setText(
            self.name_label.fontMetrics().elidedText(
                self.display_name,
                Qt.TextElideMode.ElideRight,
                max(42, label_width),
            )
        )

        text_color = preview_colors.get("--fg", fallback_colors.get("--fg", "#111827" if self.preview_mode == "light" else "#f9fafb"))
        border_color = preview_colors.get("--border", fallback_colors.get("--border", "#d1d5db" if self.preview_mode == "light" else "#454545"))
        card_bg = preview_colors.get(
            "--bg",
            preview_colors.get(
                "--canvas-inset",
                fallback_colors.get("--bg", "#ffffff" if self.preview_mode == "light" else "#242424"),
            ),
        )
        hover_border = preview_colors.get("--accent-color", fallback_colors.get("--accent-color", border_color))
        accent_color = preview_colors.get("--accent-color", fallback_colors.get("--accent-color", hover_border))
        for swatch, color in zip(self.swatches, colors):
            swatch.setToolTip(str(color).upper())
            swatch.setStyleSheet(
                f"background-color: {color}; "
                f"border: 1px solid {border_color}; "
                "border-radius: 4px;"
            )

        self.setStyleSheet(f"""
            QFrame#themeCard {{
                background-color: {card_bg};
                border: 1px solid {border_color};
                border-radius: 16px;
            }}
            QFrame#themeCard:hover {{
                border-color: {hover_border};
            }}
            QLabel#themePreviewName {{
                color: {text_color};
                font-size: 12px;
                font-weight: 400;
                background: transparent;
            }}
        """)
        self.delete_progress.setStyleSheet(
            f"background-color: {accent_color}; border: none; border-radius: 16px;"
        )

    def _set_delete_progress(self, ratio):
        width = int(max(0.0, min(1.0, ratio)) * self.width())
        self.delete_progress.setGeometry(0, 0, width, self.height())
        self.delete_progress.setVisible(width > 0)
        self.delete_progress.lower()

    def _cancel_delete_hold(self, reset_trigger=True):
        self.delete_hold_timer.stop()
        self._delete_hold_started_at = None
        if reset_trigger:
            self._delete_triggered = False
        self._set_delete_progress(0)

    def _update_delete_hold_progress(self):
        if self._delete_hold_started_at is None:
            self._cancel_delete_hold()
            return
        elapsed_ms = (time.monotonic() - self._delete_hold_started_at) * 1000
        ratio = elapsed_ms / self._delete_hold_duration_ms
        self._set_delete_progress(ratio)
        if ratio >= 1.0 and not self._delete_triggered:
            self._delete_triggered = True
            self.delete_hold_timer.stop()
            self._set_delete_progress(1.0)
            self.delete_requested.emit(self.theme_name)
            if self.isVisible():
                self._cancel_delete_hold(reset_trigger=False)

    def mousePressEvent(self, event):
        if self.deletable and event.button() == Qt.MouseButton.LeftButton:
            self._delete_hold_started_at = time.monotonic()
            self._delete_triggered = False
            self._set_delete_progress(0)
            self.delete_hold_timer.start()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.deletable and event.button() == Qt.MouseButton.LeftButton:
            if self._delete_triggered:
                self._delete_triggered = False
                return
            self._cancel_delete_hold()
            self.theme_selected.emit(self.theme_data)
            return
        if event.button() == Qt.MouseButton.LeftButton:
            self.theme_selected.emit(self.theme_data)
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        if self.deletable and self.delete_hold_timer.isActive():
            self._cancel_delete_hold()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.delete_progress.isVisible() and self._delete_hold_started_at is not None:
            elapsed_ms = (time.monotonic() - self._delete_hold_started_at) * 1000
            self._set_delete_progress(elapsed_ms / self._delete_hold_duration_ms)


class ThemePreparingPulseAnimation(QFrame):
    """Modern rotating-arc loading indicator shown while a saved theme is being persisted."""
    def __init__(self, accent="#007aff", parent=None):
        super().__init__(parent)
        self.accent = QColor(accent if QColor(accent).isValid() else "#007aff")
        self._angle = 0.0
        self.setFixedSize(46, 46)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def _tick(self):
        self._angle = (self._angle + 5.5) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        stroke = 4
        rect = QRectF(stroke / 2, stroke / 2, self.width() - stroke, self.height() - stroke)

        track_pen = QPen(QColor(self.accent))
        track_color = QColor(self.accent)
        track_color.setAlpha(32)
        track_pen.setColor(track_color)
        track_pen.setWidth(stroke)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawEllipse(rect)

        arc_pen = QPen(QColor(self.accent))
        arc_pen.setWidth(stroke)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(arc_pen)
        span_degrees = 100
        start_angle = int(-self._angle * 16)
        span_angle = int(-span_degrees * 16)
        painter.drawArc(rect, start_angle, span_angle)


class ThemeSelectedToast(QFrame):
    """Floating pill confirming a theme was applied, fades out on its own."""
    def __init__(self, text, accent="#007aff", parent=None):
        super().__init__(parent)
        self.setObjectName("themeSelectedToast")
        accent_color = QColor(accent if QColor(accent).isValid() else "#007aff")

        self.setStyleSheet(f"""
            QFrame#themeSelectedToast {{
                background-color: rgba(28, 29, 33, 235);
                border: 1px solid rgba(255, 255, 255, 35);
                border-radius: 19px;
            }}
            QLabel {{
                color: #f4f4f5;
                background: transparent;
                font-size: 13px;
                font-weight: 600;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 9, 18, 9)
        layout.setSpacing(9)

        check_badge = QLabel("✓")
        check_badge.setFixedSize(18, 18)
        check_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        check_badge.setStyleSheet(f"""
            color: #ffffff;
            background-color: {accent_color.name()};
            border-radius: 9px;
            font-size: 11px;
            font-weight: 700;
        """)
        layout.addWidget(check_badge)

        label = QLabel(text)
        layout.addWidget(label)
        self.adjustSize()

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def play(self, visible_ms=5000, fade_ms=220):
        self.show()
        self.raise_()
        self._fade_anim.stop()
        self._fade_anim.setDuration(fade_ms)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()
        QTimer.singleShot(visible_ms, self._fade_out)

    def _fade_out(self):
        self._fade_anim.stop()
        self._fade_anim.setDuration(280)
        self._fade_anim.setStartValue(self._opacity_effect.opacity())
        self._fade_anim.setEndValue(0.0)
        try:
            self._fade_anim.finished.disconnect()
        except TypeError:
            pass
        self._fade_anim.finished.connect(self.deleteLater)
        self._fade_anim.start()


def show_settings_toast(dialog, text, accent=None):
    """Shows the floating confirmation pill (as used for theme selection) anchored to
    a settings dialog/page, replacing any toast already in flight on it."""
    existing = getattr(dialog, "_active_settings_toast", None)
    if existing is not None:
        try:
            existing._fade_anim.stop()
            existing.deleteLater()
        except RuntimeError:
            pass
        dialog._active_settings_toast = None

    if accent is None:
        accent = dialog._settings_accent_color()

    toast = ThemeSelectedToast(text, accent, parent=dialog)
    toast.move((dialog.width() - toast.width()) // 2, 22)
    dialog._active_settings_toast = toast
    toast.play()
    return toast


class ThumbnailWorker(QObject):
    thumbnail_ready = pyqtSignal(str, int, QImage, str)
    finished = pyqtSignal()

    def __init__(self, key, full_folder_path, image_files, shape='rounded', thumb_size=None):
        super().__init__()
        self.key = key
        self.full_folder_path = full_folder_path
        self.image_files = image_files
        self.is_cancelled = False
        self.shape = shape
        self.thumb_width, self.thumb_height = thumb_size or (142, 80)

    def run(self):
        for index, filename in enumerate(self.image_files):
            if self.is_cancelled:
                break
            try:
                image_path = os.path.join(self.full_folder_path, filename)
                source_image = QImage(image_path)
                if source_image.isNull():
                    continue

                if self.shape == 'circular':
                    final_image = create_circular_thumbnail_image(source_image, 96, QColor("#e5e7eb"))
                else: # 'rounded'
                    final_image = create_rounded_thumbnail_image(source_image, self.thumb_width, self.thumb_height, 10)
                
                if not final_image.isNull():
                    self.thumbnail_ready.emit(self.key, index, final_image, filename)
            except Exception as e:
                print(f"Onigiri ThumbnailWorker Error for '{filename}': {e}")
        self.finished.emit()

    def cancel(self):
        self.is_cancelled = True


class _TooltipSuppressor(QObject):
    """Application-wide event filter that swallows native Qt tooltip popups.

    Installed while the settings dialog is open so none of the widgets in this
    module (or its child dialogs) show the native OS hover tooltips, regardless
    of any setToolTip() calls.
    """
    def eventFilter(self, obj, event):
        try:
            if event.type() == QEvent.Type.ToolTip:
                return True  # eat the event -> tooltip never shown
        except RuntimeError:
            pass
        return False
