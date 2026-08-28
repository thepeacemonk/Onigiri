# Qt controls shared outside the settings dialog.
#
# These two came from the old `settings/_widgets.py`, a 3900-line grab bag that
# existed only to build the classic PyQt settings dialog. That dialog is gone
# (everything it configured now lives in `settings_web/`), but the Gamification
# and Prep Station dialogs still draw with these, so they moved here instead of
# being deleted with the rest.

from .common import *
from .common import theme_manager, mw


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
        self._shake_offset = 0.0

        self.animation = QPropertyAnimation(self, b"thumb_x_pos", self)
        self.animation.setDuration(180)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.gooey_animation = QPropertyAnimation(self, b"gooey_amount", self)
        self.gooey_animation.setDuration(230)
        self.gooey_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.shake_animation = QPropertyAnimation(self, b"shake_offset", self)
        self.shake_animation.setDuration(380)
        self.shake_animation.setEasingCurve(QEasingCurve.Type.Linear)
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

    @pyqtProperty(float)
    def shake_offset(self):
        return self._shake_offset

    @shake_offset.setter
    def shake_offset(self, value):
        self._shake_offset = float(value)
        self.update()

    def shake(self):
        """Nudge the switch sideways to point at it as the reason something is locked."""
        if self.shake_animation.state() == QPropertyAnimation.State.Running:
            return
        self.shake_animation.setStartValue(0.0)
        for step, offset in ((0.15, 3.0), (0.35, -3.0), (0.55, 2.4), (0.75, -1.6), (0.9, 0.8)):
            self.shake_animation.setKeyValueAt(step, offset)
        self.shake_animation.setEndValue(0.0)
        self.shake_animation.start()

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
        if abs(self._shake_offset) > 0.01:
            painter.translate(self._shake_offset, 0.0)
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
